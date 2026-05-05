from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import settings
from app.market.data_service import market_data_service
from app.strategy import STRATEGIES
from app.llm import review_risk, analyze_news
from app.news import NewsService
from app.news.adapters.finnhub import FinnhubAdapter
from app.news.adapters.polygon import PolygonAdapter
from app.models.llm_report import LLMReport
from app.models.db import async_session
from app.risk import CircuitBreaker, HardRiskChecker, PositionManager
from app.execution.paper_trader import PaperTrader
from app.execution.order_manager import OrderManager
from app.execution.persistence import persist_signal, persist_order, persist_trade

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
        # Initialize news service with available adapters
        news_adapters = []
        if settings.finnhub_api_key:
            news_adapters.append(FinnhubAdapter(api_key=settings.finnhub_api_key))
        if settings.polygon_api_key:
            news_adapters.append(PolygonAdapter(api_key=settings.polygon_api_key))
        self.news_service = NewsService(adapters=news_adapters, cache_ttl=settings.news_cache_ttl_seconds)
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

        # Broadcast events via WebSocket
        try:
            from app.api.websocket import broadcast
            for event in events:
                await broadcast(event)
        except Exception:
            logger.warning("WebSocket broadcast failed")

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

            # Fetch news for this ticker
            news_items = await self.news_service.get_ticker_news(ticker)
            news_summary = "; ".join(n.headline for n in news_items[:5]) or "无相关新闻"

            # Analyze news with LLM (best-effort)
            if news_items:
                try:
                    await analyze_news(
                        ticker=ticker,
                        headline=news_items[0].headline,
                        price_change=f"{market['change_pct']:+.2f}%",
                        market_state=f"QQQ {market['change_pct']:+.2f}%",
                    )
                except Exception:
                    logger.warning("News analysis failed for %s", ticker)

            # Build position and account context for LLM
            pos_lines = []
            for t, p in self.trader.positions.items():
                pos_lines.append(f"  {t}: {p['quantity']}股 @ ${p['avg_price']:.2f} [{p['strategy']}]")
            current_positions = "\n".join(pos_lines) if pos_lines else "无持仓"
            account_state = f"可用资金: ${self.trader.cash:,.2f}\n累计盈亏: ${self.trader.get_total_pnl():,.2f}\n当日盈亏: ${self.daily_pnl:,.2f}\n连续亏损: {self.consecutive_losses}笔"

            llm_result = await review_risk(
                ticker=ticker,
                strategy=signal["strategy_name"],
                entry_price=signal["entry_price"],
                stop_loss=signal["stop_loss"],
                position_pct=settings.max_single_position_pct,
                market_state=f"QQQ {market['change_pct']:+.2f}%",
                news_summary=news_summary,
                current_positions=current_positions,
                account_state=account_state,
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

            # Persist signal to DB
            await persist_signal(signal)

            # Execute via IBKR if available, otherwise paper trader
            if self.ibkr_broker and self.ibkr_broker.is_connected:
                order = await self.ibkr_broker.place_market_order(ticker, quantity, "buy")
                order["strategy"] = signal["strategy_name"]
            else:
                order = self.order_manager.execute_signal(signal, quantity)

            # Persist order to DB
            await persist_order(order)

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

    async def get_status(self) -> dict:
        ibkr_status = "not_configured"
        ibkr_account = {}
        if self.ibkr_broker:
            if self.ibkr_broker.is_connected:
                ibkr_status = "connected"
                try:
                    ibkr_account = await self.ibkr_broker.get_account_summary()
                except Exception:
                    ibkr_account = {}
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


    async def _persist_llm_report(self, symbol_id: int | None, report_type: str, source_text: str, llm_result: dict) -> None:
        try:
            async with async_session() as session:
                report = LLMReport(
                    symbol_id=symbol_id,
                    report_type=report_type,
                    source_text=source_text,
                    summary=llm_result.get('reason'),
                    sentiment=llm_result.get('sentiment'),
                    impact_score=llm_result.get('impact_score'),
                    risk_score=llm_result.get('risk_score'),
                    risk_flags=llm_result.get('risk_flags'),
                    suggested_action=llm_result.get('action'),
                    model_used=llm_result.get('_model'),
                    latency_ms=llm_result.get('_latency_ms'),
                )
                session.add(report)
                await session.commit()
        except Exception:
            logger.exception('Failed to persist LLM report')

scanner_pipeline = ScannerPipeline()
