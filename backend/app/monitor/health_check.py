from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.market.data_service import market_data_service

logger = logging.getLogger(__name__)

_last_check_time = 0
_last_status: HealthStatus | None = None
_CACHE_TTL = 30  # cache health check for 30 seconds


@dataclass
class HealthStatus:
    market_data: bool = False
    ibkr_connected: bool = False
    llm_available: bool = False
    network_up: bool = False

    @property
    def can_trade(self) -> bool:
        return self.market_data and self.ibkr_connected and self.network_up

    @property
    def can_scan(self) -> bool:
        return self.market_data and self.network_up

    def to_dict(self) -> dict:
        return {
            "market_data": self.market_data,
            "ibkr_connected": self.ibkr_connected,
            "llm_available": self.llm_available,
            "network_up": self.network_up,
            "can_trade": self.can_trade,
            "can_scan": self.can_scan,
        }


async def check_health(ibkr_broker=None, force: bool = False) -> HealthStatus:
    """Check all external dependencies. Results cached for 2 minutes."""
    global _last_check_time, _last_status

    now = time.monotonic()
    if not force and _last_status and (now - _last_check_time) < _CACHE_TTL:
        return _last_status

    status = HealthStatus()

    # Market data check (if data works, network is up)
    try:
        quote = await market_data_service.get_quote("SPY")
        status.market_data = quote.get("price", 0) > 0
        status.network_up = status.market_data
    except Exception:
        status.market_data = False
        status.network_up = False

    # IBKR check
    if ibkr_broker:
        status.ibkr_connected = ibkr_broker.is_connected

    # LLM check (lightweight ping)
    try:
        from app.config import settings
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.llm_base_url}/models",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
            status.llm_available = resp.status_code in (200, 401, 403)
    except Exception:
        status.llm_available = False

    _last_check_time = now
    _last_status = status
    return status
