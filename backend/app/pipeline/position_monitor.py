from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.execution.paper_trader import PaperTrader
from app.execution.order_manager import OrderManager
from app.execution.persistence import persist_trade
from app.journal.trade_journal import write_trade_note
from app.llm import review_trade
from app.market.data_service import market_data_service

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Monitors open positions and auto-executes stop-loss / take-profit / trailing stop."""

    def __init__(self, trader: PaperTrader, order_manager: OrderManager, ibkr_broker=None):
        self.trader = trader
        self.order_manager = order_manager
        self.ibkr_broker = ibkr_broker
        self.highest_prices: dict[str, float] = {}

    async def check_positions(self) -> list[dict]:
        """Check all open positions. Execute stop-loss/take-profit. Return close events."""
        events = []
        for ticker, pos in list(self.trader.positions.items()):
            current_price = await self._get_current_price(ticker)
            if current_price <= 0:
                continue

            # Track highest price for trailing stop
            self.highest_prices[ticker] = max(
                self.highest_prices.get(ticker, 0), current_price
            )

            # Check stop-loss
            stop = pos.get("stop_loss", 0)
            if stop > 0 and current_price <= stop:
                event = await self._close_position(ticker, current_price, f"止损触发 (${stop:.2f})")
                events.append(event)
                continue

            # Check take-profit
            tp = pos.get("take_profit", 0)
            if tp > 0 and current_price >= tp:
                event = await self._close_position(ticker, current_price, f"止盈触发 (${tp:.2f})")
                events.append(event)
                continue

            # Check trailing stop (1.5x ATR from highest)
            highest = self.highest_prices.get(ticker, 0)
            atr = pos.get("atr", current_price * 0.02)
            trailing_stop = highest - 1.5 * atr
            if highest > 0 and current_price <= trailing_stop:
                event = await self._close_position(ticker, current_price, f"移动止盈触发 (最高${highest:.2f}, 回落至${current_price:.2f})")
                events.append(event)

        return events

    async def _get_current_price(self, ticker: str) -> float:
        """Get current price from market data service."""
        try:
            quote = await market_data_service.get_quote(ticker)
            return quote.get("price", 0.0)
        except Exception:
            logger.warning("Failed to get price for %s", ticker)
            return 0.0

    async def _close_position(self, ticker: str, current_price: float, reason: str) -> dict:
        """Close a position and trigger post-trade actions."""
        pos = self.trader.positions[ticker]
        quantity = pos["quantity"]
        entry_price = pos.get("avg_price", 0)
        strategy = pos.get("strategy", "")

        # Execute close
        if self.ibkr_broker and self.ibkr_broker.is_connected:
            try:
                order = await self.ibkr_broker.place_market_order(ticker, quantity, "sell")
                broker = "ibkr"
            except Exception as e:
                logger.error("IBKR sell failed for %s: %s", ticker, e)
                order = self.trader.sell(ticker, quantity, current_price, reason)
                broker = "paper_fallback"
        else:
            order = self.trader.sell(ticker, quantity, current_price, reason)
            broker = "paper"

        pnl = (current_price - entry_price) * quantity
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        # Persist trade
        trade_record = {
            "ticker": ticker,
            "strategy": strategy,
            "entry_price": entry_price,
            "exit_price": current_price,
            "quantity": quantity,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await persist_trade(trade_record)

        # LLM post-trade review
        llm_review = {}
        try:
            llm_review = await review_trade(
                ticker=ticker,
                strategy=strategy,
                entry_price=entry_price,
                exit_price=current_price,
                pnl_pct=round(pnl_pct, 2),
                entry_reason=pos.get("entry_reason", ""),
                exit_reason=reason,
            )
        except Exception:
            logger.warning("LLM trade review failed for %s", ticker)

        # Write Obsidian trade note
        await write_trade_note(trade_record, llm_review)

        # Update stats
        if pnl < 0:
            self.trader.consecutive_losses = getattr(self.trader, "consecutive_losses", 0) + 1
        else:
            self.trader.consecutive_losses = 0

        # Clean up tracking
        self.highest_prices.pop(ticker, None)

        logger.info("CLOSED %s @ %.2f [%s] PnL: $%.2f (%.2f%%)", ticker, current_price, reason, pnl, pnl_pct)

        return {
            "type": "position_closed",
            "ticker": ticker,
            "entry_price": entry_price,
            "exit_price": current_price,
            "quantity": quantity,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "strategy": strategy,
            "broker": broker,
            "llm_review": llm_review,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
position_monitor: PositionMonitor | None = None


def init_position_monitor(trader, order_manager, ibkr_broker=None):
    global position_monitor
    position_monitor = PositionMonitor(trader, order_manager, ibkr_broker)
    return position_monitor
