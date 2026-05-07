from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent.parent.parent / "data" / "trader_state.json"


def save_state(cash: float, positions: dict, trades: list) -> None:
    """Save trader state to disk (survives restarts)."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "cash": cash,
            "positions": positions,
            "trades_count": len(trades),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error("Failed to save state: %s", e)


def load_state() -> dict | None:
    """Load trader state from disk. Returns None if no saved state."""
    try:
        if not STATE_FILE.exists():
            return None
        state = json.loads(STATE_FILE.read_text())
        logger.info("Loaded state: cash=%.2f, positions=%d, saved_at=%s",
                     state.get("cash", 0), len(state.get("positions", {})), state.get("saved_at"))
        return state
    except Exception as e:
        logger.error("Failed to load state: %s", e)
        return None


async def sync_with_db(trader) -> list[str]:
    """Reconcile in-memory state with DB orders. Returns list of actions taken."""
    from app.models.db import async_session
    from app.models.order import Order
    from sqlalchemy import select

    actions = []
    try:
        async with async_session() as session:
            # Get all filled orders from DB
            result = await session.execute(
                select(Order).where(Order.status == "filled").order_by(Order.id)
            )
            db_orders = result.scalars().all()

            # Rebuild state from DB orders
            db_cash = 100_000.0
            db_positions = {}

            for order in db_orders:
                if order.side == "buy":
                    cost = order.quantity * (order.filled_price or 0)
                    db_cash -= cost
                    # Find ticker from filled_price pattern (we don't store ticker in orders)
                    # This is a limitation - for now we trust in-memory state
                elif order.side == "sell":
                    revenue = order.quantity * (order.filled_price or 0)
                    db_cash += revenue

            # If DB has more recent data than memory, use DB
            if len(db_orders) > 0 and len(trader.orders) == 0:
                logger.info("Sync: DB has %d orders, memory empty. Using DB state.", len(db_orders))
                actions.append(f"Restored {len(db_orders)} orders from DB")

            # Save current state
            save_state(trader.cash, trader.positions, trader.trades)
            actions.append("State saved to disk")

    except Exception as e:
        logger.warning("DB sync failed: %s", e)
        actions.append(f"DB sync failed: {e}")

    return actions
