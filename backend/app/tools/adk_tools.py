"""
Custom ADK Tools for ThreatIQ

These tools are used by ADK agents to:
1. Search phishing dataset
2. Manage user profiles
3. Log interactions
"""

from typing import List, Dict, Optional
from app.models.database import Database
from app.models.schemas import UserProfile
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

# Global dataset cache
_dataset_df = None
_vectorizer = None
_tfidf_matrix = None


def load_phishing_dataset() -> Dict[str, int]:
    """
    Load phishing dataset into memory.
    
    Returns:
        Dictionary with dataset stats
    """
    global _dataset_df, _vectorizer, _tfidf_matrix
    
    try:
        import os
        dataset_path = "data/phishing_dataset.csv"
        
        if not os.path.exists(dataset_path):
            # Create dummy dataset
            _create_dummy_dataset(dataset_path)
        
        _dataset_df = pd.read_csv(dataset_path)
        # Reset vectorizer cache to force rebuild with new data
        _vectorizer = None
        _tfidf_matrix = None
        logger.info(f"Loaded {len(_dataset_df)} examples from dataset")
        
        return {
            "total_examples": len(_dataset_df),
            "phishing_count": len(_dataset_df[_dataset_df['label'] == 1]),
            "safe_count": len(_dataset_df[_dataset_df['label'] == 0])
        }
        
    except Exception as e:
        logger.error(f"Error loading dataset: {e}")
        return {"error": str(e)}


def _create_dummy_dataset(path: str):
    """Create dummy phishing dataset for testing."""
    dummy_data = [
        {"text": "URGENT: Your bank account has been suspended. Click here to verify: http://fake-bank.com/verify", "label": 1, "category": "fake_bank"},
        {"text": "Congratulations! You've won $1,000,000. Send your details to claim your prize now!", "label": 1, "category": "prize_scam"},
        {"text": "Your package delivery failed. Update your address: http://fake-shipping.com", "label": 1, "category": "fake_shipping"},
        {"text": "Dear customer, your monthly bank statement is ready for review in your online banking portal.", "label": 0, "category": "legitimate_bank"},
        {"text": "Security Alert: Suspicious login attempt detected. If this wasn't you, change your password immediately at: http://phishing-site.com", "label": 1, "category": "account_alert"},
        {"text": "Your Amazon order #12345 has been shipped and will arrive tomorrow.", "label": 0, "category": "legitimate_shipping"},
        {"text": "IRS NOTICE: You have unpaid taxes. Pay immediately to avoid legal action: http://fake-irs.com", "label": 1, "category": "tax_scam"},
        {"text": "Verify your Netflix account to continue streaming: http://netflix-verify.phishing.com", "label": 1, "category": "account_verification"},
        {"text": "Your credit card ending in 1234 was charged $99.99. If you didn't make this purchase, contact us.", "label": 0, "category": "legitimate_transaction"},
        {"text": "FINAL WARNING: Your PayPal account will be closed unless you verify now!", "label": 1, "category": "account_alert"},
    ]
    
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame(dummy_data)
    df.to_csv(path, index=False)
    logger.info(f"Created dummy dataset at {path}")


def find_similar_phishing(message: str, category: str = None, max_results: int = 3) -> List[Dict]:
    """
    Find similar phishing examples from the dataset using TF-IDF similarity.
    
    Args:
        message: The message to find similar examples for
        category: Optional category filter
        max_results: Maximum number of results to return
        
    Returns:
        List of similar phishing examples
    """
    global _dataset_df, _vectorizer, _tfidf_matrix
    
    try:
        if _dataset_df is None:
            load_phishing_dataset()
        
        if _dataset_df is None or len(_dataset_df) == 0:
            return []
        
        # Build TF-IDF index if not exists
        if _vectorizer is None or _tfidf_matrix is None:
            _vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
            _tfidf_matrix = _vectorizer.fit_transform(_dataset_df['text'].fillna(''))
        
        # Get phishing examples only and reset index for consistent alignment
        phishing_df = _dataset_df[_dataset_df['label'] == 1].reset_index(drop=True)
        
        if len(phishing_df) == 0:
            return []
        
        # Vectorize input message
        message_vec = _vectorizer.transform([message])
        
        # Get the original indices of phishing examples in the main dataframe
        phishing_mask = _dataset_df['label'] == 1
        phishing_original_indices = _dataset_df[phishing_mask].index.tolist()
        
        # Get TF-IDF vectors for phishing examples
        phishing_tfidf = _tfidf_matrix[phishing_original_indices]
        
        # Calculate similarities
        similarities = cosine_similarity(message_vec, phishing_tfidf)[0]
        
        # Get top results (indices now correspond to phishing_df rows)
        top_indices = np.argsort(similarities)[::-1][:max_results]
        
        results = []
        for idx in top_indices:
            sim_score = similarities[idx]
            # Handle NaN or invalid similarity scores
            if np.isnan(sim_score) or sim_score < 0:
                sim_score = 0.0
            
            row = phishing_df.iloc[idx]
            results.append({
                "message": row['text'][:200] if pd.notna(row['text']) else "",
                "category": row['category'] if pd.notna(row['category']) else "unknown",
                "similarity": round(sim_score, 3)  # Return as decimal (0-1), frontend multiplies by 100
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error finding similar examples: {e}")
        return []


async def get_user_profile(user_id: str) -> Dict:
    """
    Load user profile from MongoDB.
    
    Args:
        user_id: Firebase UID
        
    Returns:
        User profile dictionary
    """
    try:
        db = Database.get_db()
        profile_data = await db.user_profiles.find_one({"user_id": user_id})
        
        if profile_data:
            profile_data.pop('_id', None)
            return profile_data
        else:
            # Return new profile structure
            return {
                "user_id": user_id,
                "total_messages": 0,
                "correct_guesses": 0,
                "by_category": {},
                "weak_spots": [],
                "created_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return {"user_id": user_id, "total_messages": 0, "correct_guesses": 0, "by_category": {}, "weak_spots": []}


async def update_user_profile(user_id: str, category: str, was_correct: Optional[bool]) -> Dict:
    """
    Update user profile after an interaction.
    
    Args:
        user_id: Firebase UID
        category: Phishing category
        was_correct: Whether user's guess was correct
        
    Returns:
        Updated profile dictionary
    """
    try:
        profile = await get_user_profile(user_id)
        
        # Update stats
        profile['total_messages'] = profile.get('total_messages', 0) + 1
        
        if was_correct is not None and was_correct:
            profile['correct_guesses'] = profile.get('correct_guesses', 0) + 1
        
        # Update category stats
        by_category = profile.get('by_category', {})
        if category not in by_category:
            by_category[category] = {"seen": 0, "mistakes": 0}
        
        by_category[category]["seen"] += 1
        
        if was_correct is not None and not was_correct:
            by_category[category]["mistakes"] += 1
        
        profile['by_category'] = by_category
        
        # Calculate weak spots
        weak_spots = []
        for cat, stats in by_category.items():
            if stats["seen"] >= 2:
                mistake_rate = stats["mistakes"] / stats["seen"]
                if mistake_rate > 0.5:
                    weak_spots.append(cat)
        
        profile['weak_spots'] = weak_spots
        profile['updated_at'] = datetime.utcnow().isoformat()
        
        # Save to MongoDB
        db = Database.get_db()
        await db.user_profiles.update_one(
            {"user_id": user_id},
            {"$set": profile},
            upsert=True
        )
        
        return profile
        
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        return profile


async def log_interaction(
    user_id: str, 
    message: str, 
    classification: Dict, 
    was_correct: Optional[bool], 
    session_id: str, 
    request_id: str,
    full_response: Optional[Dict] = None
) -> bool:
    """
    Log an interaction to MongoDB with idempotency support.
    
    Args:
        user_id: Firebase UID
        message: The analyzed message
        classification: Classification result
        was_correct: Whether user was correct
        session_id: Session ID
        request_id: Unique request ID for idempotency
        full_response: The complete API response for returning on duplicate requests

        
    Returns:
        True if successful
    """
    try:
        db = Database.get_db()
        
        # Check if interaction with this request_id already exists (idempotency)
        existing = await db.interactions.find_one({
            "user_id": user_id,
            "request_id": request_id
        })
        
        if existing:
            logger.info(f"Interaction with request_id {request_id} already logged, skipping duplicate")
            return True
        
        interaction = {
            "user_id": user_id,
            "message": message,
            "classification": classification,
            "was_correct": was_correct,
            "timestamp": datetime.utcnow(),
            "session_id": session_id,
            "request_id": request_id,
            "full_response": full_response
        }
        
        await db.interactions.insert_one(interaction)
        logger.info(f"Logged interaction with request_id: {request_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")
        return False


# Tool registry for ADK
ADK_TOOLS = {
    "load_phishing_dataset": load_phishing_dataset,
    "find_similar_phishing": find_similar_phishing,
    "get_user_profile": get_user_profile,
    "update_user_profile": update_user_profile,
    "log_interaction": log_interaction,
}
