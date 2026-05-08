from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class PendingOrder:
    ticker: str
    side: str
    quantity: float
    signal: dict
    order_id: str | None = None
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OrderTracker:
    """Track pending IBKR orders and resolve them on fill/timeout."""

    def __init__(self, timeout_seconds: int = 300):
        self.pending: dict[str, PendingOrder] = {}  # order_id -> PendingOrder
        self.timeout_seconds = timeout_seconds

    def add_pending(self, ticker: str, side: str, quantity: float, signal: dict, order_id: str = "") -> str:
        key = order_id or f"{ticker}_{side}_{datetime.now(timezone.utc).timestamp()}"
        self.pending[key] = PendingOrder(
            ticker=ticker, side=side, quantity=quantity,
            signal=signal, order_id=key,
        )
        logger.info("Tracking pending order: %s %s x%.4f [%s]", side, ticker, quantity, key)
        return key

    def resolve_filled(self, order_id: str, filled_price: float) -> PendingOrder | None:
        order = self.pending.pop(order_id, None)
        if order:
            order.status = "filled"
            logger.info("Order resolved: %s filled @ %.2f", order_id, filled_price)
        return order

    def cancel(self, order_id: str) -> PendingOrder | None:
        return self.pending.pop(order_id, None)

    def get_expired(self) -> list[PendingOrder]:
        """Return orders that have exceeded timeout."""
        now = datetime.now(timezone.utc)
        expired = []
        for oid, order in list(self.pending.items()):
            elapsed = (now - order.created_at).total_seconds()
            if elapsed > self.timeout_seconds:
                expired.append(order)
                del self.pending[oid]
                logger.warning("Order expired: %s %s x%.4f after %ds",
                               order.side, order.ticker, order.quantity, elapsed)
        return expired

    @property
    def count(self) -> int:
        return len(self.pending)
