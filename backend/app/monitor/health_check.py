from __future__ import annotations

import logging
from dataclasses import dataclass

from app.market.data_service import market_data_service

logger = logging.getLogger(__name__)


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


async def check_health(ibkr_broker=None) -> HealthStatus:
    """Check all external dependencies."""
    status = HealthStatus()

    # Network check (try fetching a known endpoint)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://httpbin.org/get")
            status.network_up = resp.status_code == 200
    except Exception:
        status.network_up = False

    # Market data check
    try:
        quote = await market_data_service.get_quote("SPY")
        status.market_data = quote.get("price", 0) > 0
    except Exception:
        status.market_data = False

    # IBKR check
    if ibkr_broker:
        status.ibkr_connected = ibkr_broker.is_connected

    # LLM check (lightweight - just check if endpoint responds)
    try:
        from app.config import settings
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.llm_base_url}/models",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
            status.llm_available = resp.status_code == 200
    except Exception:
        status.llm_available = False

    return status
