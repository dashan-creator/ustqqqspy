from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Trading circuit breaker."""

    def __init__(self):
        self._paused = False
        self._pause_reason = ""
        self._paused_at: datetime | None = None

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def pause_reason(self) -> str:
        return self._pause_reason

    def pause(self, reason: str):
        self._paused = True
        self._pause_reason = reason
        self._paused_at = datetime.now(timezone.utc)
        logger.warning("CIRCUIT BREAKER TRIGGERED: %s", reason)

    def resume(self):
        logger.info("Circuit breaker resumed")
        self._paused = False
        self._pause_reason = ""
        self._paused_at = None

    def check_trading_allowed(self) -> tuple[bool, str]:
        if self._paused:
            return False, f"交易已暂停: {self._pause_reason}"
        return True, ""
