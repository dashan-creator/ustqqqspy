from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import settings
from app.market.data_service import market_data_service
from app.strategy import STRATEGIES
from app.llm import review_risk
from app.risk import CircuitBreaker, HardRiskChecker, PositionManager
from app.execution.paper_trader import PaperTrader
from app.execution.order_manager import OrderManager

logger = logging.getLogger(__name__)


class ScannerPipeline:
    """Core scanning pipeline — runs every N minutes."""

    def __init__(self):
        self.risk_checker = HardRiskChecker(
            max_daily_loss_pct=settings.max_daily_loss_pct,
            max_weekly_loss_pct=settings.max_weekly_loss_pct,
            max_concurrent_positions=settings.max_concurrent_positions,
            max_single_position_pct=settings.max_single_position_pct,
            consecutive_loss_limit=settings.consecutive_loss_limit,
        )
        self.circuit_breaker = CircuitBreaker()
        self.position_manager = PositionManager()
        self.trader = PaperTrader()
        self.order_manager = OrderManager(self.trader)
        self.ibkr_broker = None  # Set by main.py if IBKR mode enabled
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.consecutive_losses = 0
        self.last_scan_results: list[dict] = []

    async def run_scan(self) -> list[dict]:
        events = []

        allowed, reason = self.circuit_breaker.check_trading_allowed()
        if not allowed:
            logger.warning("Scan skipped: %s", reason)
            events.append({"type": "skipped", "reason": reason})
            return events

        market = market_data_service.get_market_context("QQQ")

        for ticker in settings.symbol_list:
            try:
                result = await self._scan_symbol(ticker, market)
                if result:
                    events.append(result)
            except Exception as e:
                logger.error("Error scanning %s: %s", ticker, e)
                events.append({"type": "error", "ticker": ticker, "error": str(e)})

        self.last_scan_results = events
        return events

    async def _scan_symbol(self, ticker: str, market: dict) -> dict | None:
        bars = market_data_service.get_bars(ticker, interval="15m", period="5d")
        if bars.empty:
            return None

        indicators = market_data_service.compute_indicators(bars)

        for strategy in STRATEGIES:
            signal = strategy.evaluate(ticker, bars, indicators, market)
            if signal is None:
                continue

            risk_result = self.risk_checker.check(
                position_pct=settings.max_single_position_pct,
                current_positions=len(self.trader.positions),
                daily_pnl_pct=self.daily_pnl / self.trader.initial_cash,
                weekly_pnl_pct=self.weekly_pnl / self.trader.initial_cash,
                consecutive_losses=self.consecutive_losses,
                daily_volume_usd=bars["volume"].iloc[-1] * bars["close"].iloc[-1],
            )

            if not risk_result.approved:
                return {
                    "type": "signal_rejected", "ticker": ticker,
                    "strategy": signal["strategy_name"],
                    "reason": risk_result.reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            llm_result = await review_risk(
                ticker=ticker,
                strategy=signal["strategy_name"],
                entry_price=signal["entry_price"],
                stop_loss=signal["stop_loss"],
                position_pct=settings.max_single_position_pct,
                market_state=f"QQQ {market['change_pct']:+.2f}%",
                news_summary="V0: no news service yet",
            )

            llm_action = llm_result.get("action", "approve")
            if llm_action == "reject":
                return {
                    "type": "signal_rejected", "ticker": ticker,
                    "strategy": signal["strategy_name"],
                    "reason": f"LLM rejected: {llm_result.get('reason', 'unknown')}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            quantity = self.position_manager.calculate_quantity(
                signal["entry_price"], settings.max_single_position_pct,
            )
            if quantity <= 0:
                continue

            # Execute via IBKR if available, otherwise paper trader
            if self.ibkr_broker and self.ibkr_broker.is_connected:
                order = self.ibkr_broker.place_market_order(ticker, quantity, "buy")
                order["strategy"] = signal["strategy_name"]
            else:
                order = self.order_manager.execute_signal(signal, quantity)

            return {
                "type": "signal_executed", "ticker": ticker,
                "broker": "ibkr" if (self.ibkr_broker and self.ibkr_broker.is_connected) else "paper",
                "strategy": signal["strategy_name"],
                "direction": signal["direction"],
                "entry_price": signal["entry_price"],
                "stop_loss": signal["stop_loss"],
                "take_profit": signal["take_profit"],
                "quantity": quantity,
                "llm_action": llm_action,
                "llm_risk_score": llm_result.get("risk_score"),
                "reason": signal["reason"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return None

    def get_status(self) -> dict:
        ibkr_status = "not_configured"
        ibkr_account = {}
        if self.ibkr_broker:
            if self.ibkr_broker.is_connected:
                ibkr_status = "connected"
                ibkr_account = self.ibkr_broker.get_account_summary()
            else:
                ibkr_status = "disconnected"

        return {
            "circuit_breaker_paused": self.circuit_breaker.is_paused,
            "circuit_breaker_reason": self.circuit_breaker.pause_reason,
            "positions": dict(self.trader.positions),
            "cash": self.trader.cash,
            "stats": self.trader.get_stats(),
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "broker": "ibkr" if (self.ibkr_broker and self.ibkr_broker.is_connected) else "paper",
            "ibkr_status": ibkr_status,
            "ibkr_account": ibkr_account,
        }


scanner_pipeline = ScannerPipeline()
