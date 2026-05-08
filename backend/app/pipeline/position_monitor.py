from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.execution.paper_trader import PaperTrader
from app.execution.order_manager import OrderManager
from app.execution.persistence import persist_trade
from app.journal.trade_journal import write_trade_note
from app.llm.unified import post_trade_review, position_review
from app.market.data_service import market_data_service

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Monitors open positions and auto-executes stop-loss / take-profit / trailing stop."""

    def __init__(self, trader: PaperTrader, order_manager: OrderManager, ibkr_broker=None):
        self.trader = trader
        self.order_manager = order_manager
        self.ibkr_broker = ibkr_broker
        self.highest_prices: dict[str, float] = {}
        # Restore highest_prices from saved state
        from app.execution.state_store import load_state
        state = load_state()
        if state and state.get("highest_prices"):
            saved = {k: float(v) for k, v in state["highest_prices"].items()}
            # Only keep prices for tickers we actually hold
            self.highest_prices = {k: v for k, v in saved.items() if k in self.trader.positions}
            if self.highest_prices:
                logger.info("Restored highest_prices: %s", self.highest_prices)

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

        # Save state (highest_prices + positions + cash)
        self.trader._save(self.highest_prices or None)

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
        actual_exit_price = current_price
        if self.ibkr_broker and self.ibkr_broker.is_connected:
            try:
                order = await self.ibkr_broker.place_market_order(ticker, quantity, "sell")
                broker = "ibkr"
                if order.get("status") == "filled":
                    actual_exit_price = order.get("filled_price", current_price) or current_price
                    self.trader.cash += quantity * actual_exit_price
                    if ticker in self.trader.positions:
                        del self.trader.positions[ticker]
                else:
                    logger.warning("IBKR sell not filled: %s status=%s, NOT clearing position", ticker, order.get("status"))
                    return {
                        "type": "position_close_failed", "ticker": ticker,
                        "reason": f"IBKR sell not filled: {order.get('status')}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            except Exception as e:
                logger.error("IBKR sell failed for %s: %s, NOT falling back to paper (position may still exist)", ticker, e)
                return {
                    "type": "position_close_failed", "ticker": ticker,
                    "reason": f"IBKR sell exception: {e}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        else:
            self.trader.sell(ticker, quantity, current_price, reason)
            broker = "paper"

        pnl = (actual_exit_price - entry_price) * quantity
        pnl_pct = ((actual_exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        # Persist trade
        trade_record = {
            "ticker": ticker,
            "strategy": strategy,
            "entry_price": entry_price,
            "exit_price": actual_exit_price,
            "quantity": quantity,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await persist_trade(trade_record)

        # Update trader stats (paper/paper_fallback: trader.sell already appended; IBKR: we need to)
        if broker == "ibkr":
            self.trader.trades.append(trade_record)
        self.trader.daily_pnl += pnl
        self.trader.weekly_pnl += pnl

        # LLM post-trade review
        llm_review = {}
        try:
            llm_review = await post_trade_review(
                ticker=ticker,
                strategy=strategy,
                entry_price=entry_price,
                exit_price=actual_exit_price,
                pnl_pct=round(pnl_pct, 2),
                entry_reason=pos.get("entry_reason", ""),
                exit_reason=reason,
            )
        except Exception:
            logger.warning("LLM trade review failed for %s", ticker)

        # Write Obsidian trade note
        await write_trade_note(trade_record, llm_review)

        # Store review for next LLM call in scanner
        if llm_review and not llm_review.get("error"):
            try:
                from app.pipeline.scanner import scanner_pipeline
                scanner_pipeline._last_trade_review = (
                    f"{ticker} {strategy} {'盈利' if pnl > 0 else '亏损'} {pnl_pct:+.1f}%\n"
                    f"教训: {llm_review.get('key_lesson', llm_review.get('suggestion', ''))}"
                )
            except Exception:
                pass

        # Update stats
        if pnl < 0:
            self.trader.consecutive_losses = getattr(self.trader, "consecutive_losses", 0) + 1
        else:
            self.trader.consecutive_losses = 0

        # Clean up tracking
        self.highest_prices.pop(ticker, None)

        logger.info("CLOSED %s @ %.2f [%s] PnL: $%.2f (%.2f%%)", ticker, actual_exit_price, reason, pnl, pnl_pct)

        return {
            "type": "position_closed",
            "ticker": ticker,
            "entry_price": entry_price,
            "exit_price": actual_exit_price,
            "quantity": quantity,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "strategy": strategy,
            "broker": broker,
            "llm_review": llm_review,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def review_positions(self, market_state: str = "", account_state: str = "") -> str | None:
        """LLM 审视所有持仓，返回报告文本。无持仓时返回 None。"""
        if not self.trader.positions:
            return None

        pos_list = []
        for ticker, pos in self.trader.positions.items():
            quote = await market_data_service.get_quote(ticker)
            current_price = quote.get("price", pos["avg_price"])
            pnl_pct = ((current_price - pos["avg_price"]) / pos["avg_price"]) * 100 if pos["avg_price"] > 0 else 0
            pos_list.append({
                "ticker": ticker,
                "strategy": pos.get("strategy", ""),
                "quantity": pos.get("quantity", 0),
                "avg_price": pos.get("avg_price", 0),
                "current_price": current_price,
                "pnl_pct": round(pnl_pct, 2),
                "stop_loss": pos.get("stop_loss", 0),
                "take_profit": pos.get("take_profit", 0),
            })

        if not market_state:
            market = await market_data_service.get_market_context("QQQ")
            market_state = f"QQQ {market['change_pct']:+.2f}%"

        try:
            return await position_review(
                positions=pos_list,
                market_state=market_state,
                account_state=account_state,
            )
        except Exception as e:
            logger.warning("Position review failed: %s", e)
            return None


# Singleton
position_monitor: PositionMonitor | None = None


def init_position_monitor(trader, order_manager, ibkr_broker=None):
    global position_monitor
    position_monitor = PositionMonitor(trader, order_manager, ibkr_broker)
    return position_monitor
