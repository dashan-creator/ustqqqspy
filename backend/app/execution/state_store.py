from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent.parent.parent / "data" / "trader_state.json"


def save_state(cash: float, positions: dict, trades: list, highest_prices: dict | None = None, risk_state: dict | None = None) -> None:
    """Save trader state to disk (survives restarts)."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "cash": cash,
            "positions": positions,
            "trades": trades,
            "highest_prices": highest_prices or {},
            "risk_state": risk_state or {},
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
    """Reconcile in-memory state with DB. State file is primary; DB is backup."""
    actions = []

    # State file already loaded in PaperTrader.__init__
    # If we have positions or trades from file, we're good
    risk_state = {
        "consecutive_losses": getattr(trader, "consecutive_losses", 0),
        "daily_pnl": getattr(trader, "daily_pnl", 0.0),
        "weekly_pnl": getattr(trader, "weekly_pnl", 0.0),
    }

    if trader.positions or trader.trades:
        save_state(trader.cash, trader.positions, trader.trades, risk_state=risk_state)
        actions.append(f"State from file: cash={trader.cash:.2f}, positions={len(trader.positions)}, trades={len(trader.trades)}")
        return actions

    # State file empty — try to rebuild cash from DB orders
    try:
        from app.models.db import async_session
        from app.models.order import Order
        from sqlalchemy import select

        async with async_session() as session:
            result = await session.execute(
                select(Order).where(Order.status == "filled").order_by(Order.id)
            )
            db_orders = result.scalars().all()

            if db_orders:
                db_cash = 100_000.0
                for order in db_orders:
                    cost = order.quantity * (order.filled_price or 0)
                    if order.side == "buy":
                        db_cash -= cost
                    elif order.side == "sell":
                        db_cash += cost
                trader.cash = db_cash
                save_state(trader.cash, trader.positions, trader.trades)
                actions.append(f"Rebuilt cash from DB: ${db_cash:.2f} ({len(db_orders)} orders)")
            else:
                save_state(trader.cash, trader.positions, trader.trades)
                actions.append("Fresh start: no prior state found")

    except Exception as e:
        logger.warning("DB sync failed: %s", e)
        save_state(trader.cash, trader.positions, trader.trades)
        actions.append(f"DB sync failed: {e}")

    except Exception as e:
        logger.warning("DB sync failed: %s", e)
        actions.append(f"DB sync failed: {e}")

    return actions
