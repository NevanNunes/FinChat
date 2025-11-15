"""User Profile Manager - Handles user profiles and conversation history"""
import json
import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class UserProfileManager:
    def __init__(self, storage_path: str = "user_profiles") -> None:
        """Initialize UserProfileManager with storage path

        Args:
            storage_path: Directory path for storing user profiles
        """
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        logger.info(f"UserProfileManager initialized with storage path: {storage_path}")

    def create_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new user profile

        Args:
            user_id: User identifier
            profile_data: Profile information dictionary

        Returns:
            Created profile dictionary
        """
        logger.info(f"Creating new profile for user: {user_id}")
        profile = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "profile": profile_data,
            "conversation_history": [],
            "financial_goals": [],
            "portfolio": {}
        }
        self._save_profile(user_id, profile)
        logger.debug(f"Profile created successfully for user: {user_id}")
        return profile

    def load_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load existing user profile

        Args:
            user_id: User identifier

        Returns:
            Profile dictionary or None if not found
        """
        file_path = os.path.join(self.storage_path, f"{user_id}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                logger.debug(f"Profile loaded successfully for user: {user_id}")
                return profile
            except Exception as e:
                logger.error(f"Error loading profile for {user_id}: {str(e)}", exc_info=True)
                return None
        else:
            logger.debug(f"No profile found for user: {user_id}")
            return None

    def _save_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        """Save profile to file

        Args:
            user_id: User identifier
            profile: Profile dictionary to save
        """
        try:
            file_path = os.path.join(self.storage_path, f"{user_id}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)
            logger.debug(f"Profile saved successfully for user: {user_id}")
        except Exception as e:
            logger.error(f"Error saving profile for {user_id}: {str(e)}", exc_info=True)

    def add_conversation(self, user_id: str, question: str, answer: str) -> None:
        """Add conversation to history

        Args:
            user_id: User identifier
            question: User question
            answer: System answer
        """
        profile = self.load_profile(user_id)
        if profile:
            profile['conversation_history'].append({
                "timestamp": datetime.now().isoformat(),
                "question": question,
                "answer": answer
            })
            # Keep only last 50 conversations
            if len(profile['conversation_history']) > 50:
                profile['conversation_history'] = profile['conversation_history'][-50:]
            self._save_profile(user_id, profile)
            logger.debug(f"Conversation added to history for user: {user_id}")
        else:
            logger.warning(f"Cannot add conversation - no profile found for user: {user_id}")

    def get_context_summary(self, user_id: str) -> str:
        """Get user context summary for LLM

        Args:
            user_id: User identifier

        Returns:
            Formatted context summary string
        """
        profile = self.load_profile(user_id)
        if not profile:
            logger.debug(f"No context available for new user: {user_id}")
            return "New user, no previous context."

        age = profile['profile'].get('age', 'N/A')
        income = profile['profile'].get('income', 'N/A')
        risk = profile['profile'].get('risk_appetite', 'N/A')

        context = f"User Profile:\n"
        context += f"- Age: {age} years old\n"
        
        # Format income properly - check if it's numeric first
        if isinstance(income, (int, float)):
            context += f"- Annual Income: ₹{income:,}\n"
        else:
            context += f"- Annual Income: {income}\n"
        
        context += f"- Risk Appetite: {risk.title() if isinstance(risk, str) else risk}\n"

        if isinstance(income, (int, float)):
            monthly_investable = int(income * 0.20 / 12)
            context += f"- Suggested Monthly SIP: ₹{monthly_investable:,}\n"

        if isinstance(age, int):
            if age < 30:
                context += f"- Investment Horizon: Long-term (30+ years)\n"
            elif age < 45:
                context += f"- Investment Horizon: Medium-term (15-30 years)\n"
            else:
                context += f"- Investment Horizon: Short-term (5-20 years)\n"

        logger.debug(f"Context summary generated for user: {user_id}")
        return context
