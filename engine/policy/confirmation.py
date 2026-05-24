import uuid
import time
import logging
from typing import Dict, Any, Tuple
import threading

logger = logging.getLogger("databox.security.confirmation")

class ConfirmationManager:
    def __init__(self, ttl_seconds: int = 300):
        self._confirmations: Dict[str, Tuple[float, dict]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def create_confirmation(self, datasource_id: str, action: str, details: dict, expected_confirm_text: str) -> str:
        with self._lock:
            # Clean expired first
            now = time.time()
            self._cleanup(now)
            
            token = str(uuid.uuid4())
            self._confirmations[token] = (
                now + self._ttl,
                {
                    "datasource_id": datasource_id,
                    "action": action,
                    "details": details,
                    "expected_confirm_text": expected_confirm_text
                }
            )
            logger.info(f"Created confirmation token {token} for action {action} on datasource {datasource_id}")
            return token

    def validate_and_consume(self, token: str, confirm_text: str) -> Tuple[bool, str, dict]:
        """
        Validates and consumes a confirmation token.
        Returns (is_valid, error_message, details_dict)
        """
        with self._lock:
            now = time.time()
            self._cleanup(now)
            
            if not token or token not in self._confirmations:
                return False, "确认令牌无效或已过期，请重新发起操作。", {}
                
            expire_at, data = self._confirmations[token]
            # Consume token immediately (one-time use)
            del self._confirmations[token]
            
            if now > expire_at:
                return False, "确认令牌已过期，请重新发起操作。", {}
                
            expected = data["expected_confirm_text"].strip()
            if confirm_text.strip() != expected:
                return False, f"二次确认文本不匹配！请输入 '{expected}' 进行确认。", {}
                
            logger.info(f"Successfully consumed confirmation token {token} for action {data['action']}")
            return True, "", data

    def _cleanup(self, now: float):
        expired = [token for token, (exp_time, _) in self._confirmations.items() if now > exp_time]
        for token in expired:
            del self._confirmations[token]

# Global confirmation manager instance
confirmation_manager = ConfirmationManager()
