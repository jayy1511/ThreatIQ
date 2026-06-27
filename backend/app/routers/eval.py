from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.routers.auth import verify_admin_user
from app.core.rate_limit import check_rate_limit
from app.core.redact import redact_sensitive_info
from app.config import settings
from app.models.database import Database
from app.llm.gemini_client import get_gemini_client
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()


EVAL_SYSTEM_INSTRUCTION = """
You are an evaluation agent for a phishing detection system.

For each interaction, you will receive:
- the original message,
- the system's classification (label and confidence).

Your job is to decide whether the system's label is CORRECT or INCORRECT,
and, if incorrect, what the corrected label should be.

Return a JSON array of objects with this exact shape:

[
  {
    "interaction_id": "...",
    "system_label": "phishing|safe|unclear",
    "system_confidence": 0.0-1.0,
    "evaluation": "correct|incorrect",
    "corrected_label": "phishing|safe|unclear",
    "comment": "short explanation"
  },
  ...
]

Be concise but precise in your comments.
"""


@router.post("/admin/eval-sample")
async def evaluate_sample(
    http_request: Request,
    limit: int = Query(5, ge=1, le=20),
    user_data: dict = Depends(verify_admin_user),
):
    """
    Run evaluation agent on a small sample of recent interactions.

    Admin-only: requires the ``admin`` Firebase custom claim.
    """
    try:
        # Rate limit by admin user
        check_rate_limit(
            http_request,
            max_requests=settings.rate_limit_admin,
            window_seconds=settings.rate_limit_admin_window,
            user_id=user_data.get('uid'),
        )
        
        db = Database.get_db()

        cursor = (
            db.interactions.find(
                {},
                {
                    "_id": 1,
                    "message": 1,
                    "classification": 1,
                    "timestamp": 1,
                },
            )
            .sort("timestamp", -1)
            .limit(limit)
        )

        interactions = []
        async for doc in cursor:
            clf = doc.get("classification", {}) or {}
            raw_msg = doc.get("message", "")
            redacted_msg = redact_sensitive_info(raw_msg)
            
            interactions.append(
                {
                    "interaction_id": str(doc["_id"]),
                    "message": redacted_msg,
                    "system_label": clf.get("label", "unknown"),
                    "system_confidence": float(clf.get("confidence", 0.0)),
                    "timestamp": doc.get("timestamp"),
                }
            )

        if not interactions:
            return {"evaluated": 0, "message": "No interactions to evaluate."}

        prompt = (
            EVAL_SYSTEM_INSTRUCTION
            + "\n\nHere is the list of interactions to evaluate:\n\n"
        )
        prompt += json.dumps(interactions, ensure_ascii=False, indent=2)
        
        try:
            gemini_client = get_gemini_client()
            raw_text = await gemini_client.generate(
                prompt=prompt,
                system_instruction=EVAL_SYSTEM_INSTRUCTION,
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.9,
                },
                use_cache=False
            )
            raw_text = raw_text.strip()
        except Exception as e:
            logger.error(f"Error generating evaluation content: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to generate evaluation content from LLM.")

        logger.info("Evaluation raw response: %s", raw_text[:300])

        try:
            eval_data = json.loads(raw_text)
        except json.JSONDecodeError:
            if "[" in raw_text and "]" in raw_text:
                start = raw_text.find("[")
                end = raw_text.rfind("]") + 1
                eval_data = json.loads(raw_text[start:end])
            else:
                raise

        if not isinstance(eval_data, list):
            raise ValueError("Evaluation response is not a list")

        now = datetime.utcnow()
        inserted = 0

        for item in eval_data:
            try:
                record = {
                    "interaction_id": item.get("interaction_id"),
                    "system_label": item.get("system_label"),
                    "system_confidence": item.get("system_confidence"),
                    "evaluation": item.get("evaluation"),
                    "corrected_label": item.get("corrected_label"),
                    "comment": item.get("comment"),
                    "evaluated_at": now,
                    "evaluator": user_data.get("uid"),
                }
                await db.model_evaluations.insert_one(record)
                inserted += 1
            except Exception as e:
                logger.error(f"Error saving evaluation record: {e}", exc_info=True)

        return {
            "evaluated": inserted,
            "sample_size": len(interactions),
            "message": "Evaluation completed.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running evaluation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to run evaluation",
        )
