"""
Service to interact with Rutabaga Answer Service (/v2/answer endpoint).
"""
import httpx
from typing import Dict, Any, Optional
from flask import current_app


class AnswerServiceClient:
    """Client for calling Rutabaga answer service."""

    def __init__(self):
        self.base_url = None
        self.api_key = None

    def _get_config(self):
        """Get configuration from Flask app context."""
        if not self.base_url:
            self.base_url = current_app.config['ANSWER_SERVICE_URL']
            self.api_key = current_app.config.get('ANSWER_SERVICE_API_KEY')

    async def generate_response(
        self,
        intent: str,
        slots: Dict[str, Any],
        message_id: str = "qa-test",
        confidence: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Generate response from answer service.

        Args:
            intent: Intent name (e.g., 'interaction', 'dosing')
            slots: Slot values for the query
            message_id: Unique message identifier
            confidence: NLU confidence score

        Returns:
            Response data or None if error
        """
        self._get_config()

        # Build request payload matching DirectAnswerRequest schema
        payload = {
            "message_id": message_id,
            "intent": intent,
            "slots": slots,
            "confidence": confidence,
            "app_version": "qa-website-1.0",
            "device_class": "qa_testing"
        }

        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            current_app.logger.error(f"Answer service error: {e}")
            return None
        except Exception as e:
            current_app.logger.error(f"Unexpected error calling answer service: {e}")
            return None


# Singleton instance
answer_service = AnswerServiceClient()
