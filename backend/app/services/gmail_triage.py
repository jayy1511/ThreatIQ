"""
Gmail inbox triage orchestration service.

Coordinates the workflow of fetching emails, analyzing with ThreatIQ,
and applying labels based on classification results.
"""

import logging
import time
from typing import List, Dict
from datetime import datetime
from app.services.gmail_oauth import gmail_oauth_service, GmailOAuthError
from app.services.gmail_client import GmailClient, GmailClientError
from app.services.analysis_client import call_analysis_service_for_triage
from app.models.database import Database

logger = logging.getLogger(__name__)


class GmailTriageError(Exception):
    """Raised when Gmail triage operations fail."""
    pass


class GmailTriageService:
    """
    Service for triaging Gmail inbox using ThreatIQ analysis.
    
    Orchestrates the complete workflow:
    1. Fetch unread messages
    2. Analyze each with ThreatIQ
    3. Apply appropriate Gmail labels
    4. Store triage records
    """
    
    LABEL_MAPPING = {
        'SAFE': 'SAFE',
        'LEGITIMATE': 'SAFE',
        'SUSPICIOUS': 'SUSPICIOUS',
        'PHISHING': 'PHISHING',
    }
    
    async def triage_inbox(
        self,
        user_id: str,
        limit: int = 10,
        mark_spam: bool = False,
        archive_safe: bool = False
    ) -> Dict:
        """
        Triage user's Gmail inbox.
        
        Args:
            user_id: Firebase user ID
            limit: Maximum number of messages to process
            mark_spam: If True, mark PHISHING messages as spam
            archive_safe: If True, archive SAFE messages
            
        Returns:
            Dict with processed count and results list
            
        Raises:
            GmailTriageError: If triage fails
        """
        try:
            logger.info(f"Starting Gmail triage for user {user_id}, limit={limit}")
            
            tokens = await gmail_oauth_service.get_tokens(user_id)
            if not tokens:
                raise GmailTriageError("Gmail not connected. Please connect your Gmail account first.")
            
            gmail_client = GmailClient(tokens['access_token'])
            
            label_ids = gmail_client.ensure_labels_exist()
            
            messages = gmail_client.list_unread_messages(max_results=limit)
            
            if not messages:
                logger.info(f"No unread messages found for user {user_id}")
                return {
                    "processed": 0,
                    "results": []
                }
            
            results = []
            
            for msg in messages:
                try:
                    result = await self._process_message(
                        gmail_client=gmail_client,
                        message_id=msg['id'],
                        thread_id=msg.get('threadId', ''),
                        user_id=user_id,
                        label_ids=label_ids,
                        mark_spam=mark_spam,
                        archive_safe=archive_safe
                    )
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"Error processing message {msg['id']}: {e}", exc_info=True)
                    results.append({
                        "message_id": msg['id'],
                        "error": str(e),
                        "success": False
                    })
            
            logger.info(f"Triage complete: processed {len(results)} messages")
            
            return {
                "processed": len(results),
                "results": results
            }
            
        except GmailOAuthError as e:
            logger.error(f"OAuth error during triage: {e}")
            raise GmailTriageError(f"Gmail authentication error: {str(e)}") from e
        except GmailClientError as e:
            logger.error(f"Gmail client error during triage: {e}")
            raise GmailTriageError(f"Gmail API error: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error during triage: {e}", exc_info=True)
            raise GmailTriageError("Failed to triage inbox") from e
    
    async def _process_message(
        self,
        gmail_client: GmailClient,
        message_id: str,
        thread_id: str,
        user_id: str,
        label_ids: Dict[str, str],
        mark_spam: bool,
        archive_safe: bool
    ) -> Dict:
        """
        Process a single message through the ThreatIQ pipeline.
        
        Args:
            gmail_client: Initialized Gmail client
            message_id: Gmail message ID
            thread_id: Gmail thread ID
            user_id: Firebase user ID
            label_ids: Mapping of category to label ID
            mark_spam: Whether to mark phishing as spam
            archive_safe: Whether to archive safe messages
            
        Returns:
            Dict with processing result
        """
        message = gmail_client.get_message(message_id)
        
        from_header = gmail_client.get_header(message, 'From')
        subject = gmail_client.get_header(message, 'Subject')
        date_header = gmail_client.get_header(message, 'Date')
        snippet = message.get('snippet', '')
        
        body = gmail_client.parse_message_body(message)
        
        analysis_text = f"From: {from_header}\nSubject: {subject}\n\n{body[:1000]}"
        
        # C5: extract sender-relevant headers from Gmail payload so the
        # analysis service can run sender verification automatically.
        # Only headers that carry authentication / routing signals are included.
        # Raw values are never logged; they are forwarded to the service only.
        _SV_HEADERS = (
            'Reply-To',
            'Return-Path',
            'Authentication-Results',
            'Received-SPF',
        )
        header_lines = [f"From: {from_header}"] if from_header else []
        for hname in _SV_HEADERS:
            hval = gmail_client.get_header(message, hname)
            if hval:
                header_lines.append(f"{hname}: {hval}")
        header_text = "\n".join(header_lines) if header_lines else None
        
        logger.info(f"Analyzing message {message_id}: {subject[:50]}")
        
        # Call the canonical analysis microservice (not the legacy root_agent)
        analysis_result = await call_analysis_service_for_triage(
            analysis_text,
            header_text=header_text,
        )
        
        if not analysis_result:
            # Analysis service unavailable – skip gracefully
            logger.warning(f"Analysis service unavailable for message {message_id}, skipping")
            return {
                "message_id": message_id,
                "from": from_header,
                "subject": subject,
                "label": "UNKNOWN",
                "confidence": 0.0,
                "reasons": [],
                "label_applied": False,
                "success": False,
                "error": "Analysis service unavailable"
            }
        
        classification = analysis_result.get('classification', {})
        label_category = self.LABEL_MAPPING.get(
            classification.get('label', 'suspicious').upper(),
            'SUSPICIOUS'
        )
        
        label_applied = False
        try:
            if label_category in label_ids:
                gmail_client.apply_label(message_id, label_ids[label_category])
                label_applied = True
                
                if mark_spam and label_category == 'PHISHING':
                    gmail_client.mark_as_spam(message_id)
                    logger.info(f"Marked message {message_id} as spam")
                
                if archive_safe and label_category == 'SAFE':
                    gmail_client.archive_message(message_id)
                    logger.info(f"Archived message {message_id}")
                    
        except GmailClientError as e:
            logger.warning(f"Failed to apply label to message {message_id}: {e}")
        
        triage_record = {
            "user_id": user_id,
            "gmail_message_id": message_id,
            "thread_id": thread_id,
            "from": from_header,
            "subject": subject,
            "date": date_header,
            "snippet": snippet,
            # body_excerpt intentionally excluded to avoid storing raw email content
            "label": label_category,
            "confidence": classification.get('confidence', 0),
            "reasons": classification.get('reason_tags', []),
            "label_applied": label_applied,
            "created_at": datetime.utcnow()
        }
        
        await self._save_triage_record(triage_record)
        
        return {
            "message_id": message_id,
            "from": from_header,
            "subject": subject,
            "label": label_category,
            "confidence": classification.get('confidence', 0),
            "reasons": classification.get('reason_tags', []),
            "label_applied": label_applied,
            "success": True
        }
    
    async def _save_triage_record(self, record: Dict) -> None:
        """
        Save triage record to MongoDB.
        
        Args:
            record: Triage record dict
        """
        try:
            db = Database.get_db()
            triage_collection = db["gmail_triage"]
            await triage_collection.insert_one(record)
            logger.info(f"Saved triage record for message {record['gmail_message_id']}")
        except Exception as e:
            logger.error(f"Failed to save triage record: {e}", exc_info=True)
    
    async def get_triage_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """
        Get triage history for a user.
        
        Args:
            user_id: Firebase user ID
            limit: Maximum number of records to return
            
        Returns:
            List of triage records
        """
        try:
            db = Database.get_db()
            triage_collection = db["gmail_triage"]
            
            cursor = triage_collection.find(
                {"user_id": user_id}
            ).sort("created_at", -1).limit(limit)
            
            records = await cursor.to_list(length=limit)
            
            for record in records:
                record['_id'] = str(record['_id'])
            
            return records
            
        except Exception as e:
            logger.error(f"Error fetching triage history: {e}", exc_info=True)
            return []


gmail_triage_service = GmailTriageService()
