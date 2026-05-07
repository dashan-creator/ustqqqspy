from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models.db import async_session
from app.models.trade import Trade
from app.models.signal import Signal
from app.models.order import Order
from app.models.symbol import Symbol
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def _get_or_create_symbol(ticker: str) -> int:
    """Get symbol_id by ticker, create if not exists."""
    async with async_session() as session:
        result = await session.execute(select(Symbol).where(Symbol.ticker == ticker))
        symbol = result.scalar_one_or_none()
        if symbol:
            return symbol.id
        symbol = Symbol(ticker=ticker, name=ticker, is_active=True)
        session.add(symbol)
        await session.commit()
        await session.refresh(symbol)
        return symbol.id


async def persist_order(order: dict, symbol_id: int | None = None) -> None:
    """Persist a filled order to the database."""
    if order.get("status") != "filled":
        return
    ticker = order.get("ticker", "")
    if not symbol_id and ticker:
        symbol_id = await _get_or_create_symbol(ticker)
    try:
        async with async_session() as session:
            db_order = Order(
                symbol_id=symbol_id or 0,
                side=order["side"],
                order_type="market",
                quantity=order["quantity"],
                filled_price=order.get("filled_price"),
                filled_at=datetime.now(timezone.utc),
                status="filled",
            )
            session.add(db_order)
            await session.commit()
    except Exception:
        logger.exception("Failed to persist order")


async def persist_trade(trade: dict, symbol_id: int | None = None) -> None:
    """Persist a completed trade to the database."""
    ticker = trade.get("ticker", "")
    if not symbol_id and ticker:
        symbol_id = await _get_or_create_symbol(ticker)
    try:
        async with async_session() as session:
            db_trade = Trade(
                symbol_id=symbol_id or 0,
                strategy_name=trade.get("strategy", ""),
                side="sell",
                entry_price=trade["entry_price"],
                exit_price=trade["exit_price"],
                quantity=trade["quantity"],
                pnl=trade["pnl"],
                pnl_pct=trade["pnl_pct"],
                entry_reason="",
                exit_reason=trade.get("reason", ""),
                opened_at=datetime.now(timezone.utc),
                closed_at=datetime.now(timezone.utc),
            )
            session.add(db_trade)
            await session.commit()
    except Exception:
        logger.exception("Failed to persist trade")


async def persist_signal(signal: dict, symbol_id: int | None = None) -> int | None:
    """Persist a trading signal to the database. Returns signal ID."""
    ticker = signal.get("ticker", "")
    if not symbol_id and ticker:
        symbol_id = await _get_or_create_symbol(ticker)
    try:
        async with async_session() as session:
            db_signal = Signal(
                symbol_id=symbol_id or 0,
                strategy_name=signal.get("strategy_name", ""),
                direction=signal.get("direction", "long"),
                strength=signal.get("strength", 0.0),
                entry_price=signal["entry_price"],
                stop_loss=signal["stop_loss"],
                take_profit=signal["take_profit"],
                reason=signal.get("reason", ""),
                status="pending",
            )
            session.add(db_signal)
            await session.commit()
            return db_signal.id
    except Exception:
        logger.exception("Failed to persist signal")
        return None
