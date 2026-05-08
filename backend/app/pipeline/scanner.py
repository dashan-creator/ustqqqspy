from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import settings
from app.market.data_service import market_data_service
from app.strategy import STRATEGIES
from app.news import NewsService
from app.news.adapters.finnhub import FinnhubAdapter
from app.news.adapters.polygon import PolygonAdapter
from app.risk import CircuitBreaker, HardRiskChecker, PositionManager
from app.execution.paper_trader import PaperTrader
from app.execution.order_manager import OrderManager
from app.execution.persistence import persist_signal, persist_order

logger = logging.getLogger(__name__)


class ScannerPipeline:
    """Core scanning pipeline — runs every N minutes."""

    def __init__(self):
        self._last_trade_review = ""  # 上次交易复盘，传给下次 LLM 调用
        self.risk_checker = HardRiskChecker(
            max_daily_loss_pct=settings.max_daily_loss_pct,
            max_weekly_loss_pct=settings.max_weekly_loss_pct,
            max_concurrent_positions=settings.max_concurrent_positions,
            max_single_position_pct=settings.max_single_position_pct,
            consecutive_loss_limit=settings.consecutive_loss_limit,
        )
        self.circuit_breaker = CircuitBreaker()
        self.trader = PaperTrader(initial_cash=settings.initial_cash)
        self.position_manager = PositionManager(account_value=settings.initial_cash)
        self.order_manager = OrderManager(self.trader)
        # Initialize news service with available adapters
        news_adapters = []
        if settings.finnhub_api_key:
            news_adapters.append(FinnhubAdapter(api_key=settings.finnhub_api_key))
        if settings.polygon_api_key:
            news_adapters.append(PolygonAdapter(api_key=settings.polygon_api_key))
        self.news_service = NewsService(adapters=news_adapters, cache_ttl=settings.news_cache_ttl_seconds)
        self.ibkr_broker = None  # Set by main.py if IBKR mode enabled
        self.last_scan_results: list[dict] = []

    @property
    def daily_pnl(self) -> float:
        return getattr(self.trader, "daily_pnl", 0.0)

    @property
    def weekly_pnl(self) -> float:
        return getattr(self.trader, "weekly_pnl", 0.0)

    @property
    def consecutive_losses(self) -> int:
        return getattr(self.trader, "consecutive_losses", 0)

    async def run_scan(self) -> list[dict]:
        events = []

        allowed, reason = self.circuit_breaker.check_trading_allowed()
        if not allowed:
            logger.warning("Scan skipped: %s", reason)
            events.append({"type": "skipped", "reason": reason})
            return events

        # Health check before scanning
        from app.monitor.health_check import check_health
        health = await check_health(self.ibkr_broker)
        if not health.can_scan:
            logger.warning("System unhealthy, skipping scan: %s", health.to_dict())
            events.append({"type": "scan_skipped", "reason": f"unhealthy: {health.to_dict()}"})
            return events

        market = await market_data_service.get_market_context("QQQ")

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
        bars = await market_data_service.get_bars(ticker, interval="15m", period="5d")
        if bars.empty:
            return None

        indicators = market_data_service.compute_indicators(bars)

        # Fetch news before strategy evaluation (used by mean reversion filter)
        news_items = await self.news_service.get_ticker_news(ticker)
        news_context = {"has_major_negative": False, "sentiment": "neutral"}
        if news_items:
            news_context["headlines"] = [n.headline for n in news_items[:5]]

        for strategy in STRATEGIES:
            signal = strategy.evaluate(ticker, bars, indicators, market, news=news_context)
            if signal is None:
                continue

            # Block if already holding this ticker
            if ticker in self.trader.positions:
                logger.info("SKIP %s: already holding %d shares", ticker, self.trader.positions[ticker]["quantity"])
                return None

            # Estimate daily volume: use the most recent full day's volume * close
            # For 15m bars, ~26 bars per day; use last 26 bars as proxy for one day
            day_bars = bars.tail(26) if len(bars) >= 26 else bars
            total_vol = float(day_bars["volume"].sum() * day_bars["close"].mean()) if len(day_bars) > 0 else 0

            risk_result = self.risk_checker.check(
                position_pct=settings.max_single_position_pct,
                current_positions=len(self.trader.positions),
                daily_pnl_pct=self.daily_pnl / self.trader.initial_cash if self.trader.initial_cash > 0 else 0,
                weekly_pnl_pct=self.weekly_pnl / self.trader.initial_cash if self.trader.initial_cash > 0 else 0,
                consecutive_losses=self.consecutive_losses,
                daily_volume_usd=total_vol,
            )

            if not risk_result.approved:
                return {
                    "type": "signal_rejected", "ticker": ticker,
                    "strategy": signal["strategy_name"],
                    "reason": risk_result.reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Smart Gate: decide if LLM is needed
            from app.llm.smart_gate import smart_gate
            volume_ratio = indicators.get("volume_ratio", 1.0)
            if volume_ratio == 0:
                volume_ratio = 1.0

            gate = smart_gate.evaluate(
                rsi=indicators.get("rsi", 50),
                volume_ratio=volume_ratio,
                market_change_pct=market.get("change_pct", 0),
                signal_strength=signal.get("strength", 0.5),
                has_news=len(news_items) > 0,
                consecutive_losses=self.consecutive_losses,
                bars=bars,
                direction=signal.get("direction", "long"),
            )

            llm_result = {"action": gate.auto_action, "risk_score": 1, "reason": gate.reason}
            llm_skipped = not gate.needs_llm

            if gate.needs_llm:
                logger.info("LLM GATE [%s]: %s → calling LLM", ticker, gate.reason)

                from app.llm.unified import pre_trade_analysis
                news_summary = "; ".join(n.headline for n in news_items[:5]) or "无相关新闻"
                pos_lines = []
                for t, p in self.trader.positions.items():
                    pos_lines.append(f"  {t}: {p['quantity']}股 @ ${p['avg_price']:.2f} [{p['strategy']}]")
                current_positions = "\n".join(pos_lines) if pos_lines else "无持仓"
                account_state = f"可用资金: ${self.trader.cash:,.2f}\n累计盈亏: ${self.trader.get_total_pnl():,.2f}\n当日盈亏: ${self.daily_pnl:,.2f}\n连续亏损: {self.consecutive_losses}笔"

                llm_result = await pre_trade_analysis(
                    ticker=ticker,
                    strategy=signal["strategy_name"],
                    entry_price=signal["entry_price"],
                    stop_loss=signal["stop_loss"],
                    take_profit=signal["take_profit"],
                    position_pct=settings.max_single_position_pct,
                    market_state=f"QQQ {market['change_pct']:+.2f}%",
                    rsi=indicators.get("rsi", 50),
                    atr=indicators.get("atr", 0),
                    volume_ratio=volume_ratio,
                    news_headlines=news_summary,
                    current_positions=current_positions,
                    account_state=account_state,
                    last_trade_review=getattr(self, "_last_trade_review", ""),
                )
            else:
                logger.info("LLM GATE [%s]: %s → skip LLM, auto=%s", ticker, gate.reason, gate.auto_action)

            llm_action = llm_result.get("action", "approve")
            if llm_action == "reject":
                return {
                    "type": "signal_rejected", "ticker": ticker,
                    "strategy": signal["strategy_name"],
                    "reason": f"LLM rejected: {llm_result.get('reason', 'unknown')}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Apply LLM suggested position size if available
            effective_pct = settings.max_single_position_pct
            if llm_action == "reduce_size":
                suggested = llm_result.get("suggested_position_pct")
                if suggested and suggested < effective_pct:
                    effective_pct = suggested
                    logger.info("Reducing position to %.1f%% per LLM", effective_pct)

            # Update account value with current market prices
            market_value = 0
            for t, p in self.trader.positions.items():
                q = await market_data_service.get_quote(t)
                cp = q.get("price", p.get("avg_price", 0))
                market_value += cp * p.get("quantity", 0)
            self.position_manager.account_value = self.trader.cash + market_value

            raw_qty = self.position_manager.calculate_quantity(
                signal["entry_price"], effective_pct, stop_loss=signal["stop_loss"],
            )
            # Round to 4 decimal places (IBKR minimum lot)
            quantity = round(raw_qty, 4) if raw_qty > 0 else 0
            if quantity <= 0:
                continue

            # Persist signal to DB
            await persist_signal(signal)

            # Execute via IBKR if available, otherwise paper trader
            if self.ibkr_broker and self.ibkr_broker.is_connected:
                order = await self.ibkr_broker.place_market_order(ticker, quantity, "buy")
                order["strategy"] = signal["strategy_name"]
                # Only sync local position when actually filled
                if order.get("status") == "filled":
                    price = order.get("filled_price", signal["entry_price"])
                    if price > 0:
                        if ticker in self.trader.positions:
                            pos = self.trader.positions[ticker]
                            total_qty = pos["quantity"] + quantity
                            pos["avg_price"] = (pos["avg_price"] * pos["quantity"] + price * quantity) / total_qty
                            pos["quantity"] = total_qty
                        else:
                            self.trader.positions[ticker] = {
                                "quantity": quantity, "avg_price": price,
                                "strategy": signal["strategy_name"],
                            }
                        self.trader.cash -= quantity * price
                else:
                    logger.warning("IBKR order not filled: %s status=%s", ticker, order.get("status"))
                    return {
                        "type": "signal_pending", "ticker": ticker,
                        "strategy": signal["strategy_name"],
                        "reason": f"IBKR order not filled: {order.get('status')}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            else:
                order = self.order_manager.execute_signal(signal, quantity)

            # Persist order to DB
            await persist_order(order)

            # Store stop_loss/take_profit/atr in position for PositionMonitor
            if ticker in self.trader.positions:
                self.trader.positions[ticker]["stop_loss"] = signal["stop_loss"]
                self.trader.positions[ticker]["take_profit"] = signal["take_profit"]
                self.trader.positions[ticker]["entry_reason"] = signal.get("reason", "")
                self.trader.positions[ticker]["atr"] = indicators.get("atr", signal["entry_price"] * 0.02)

            actual_entry = order.get("filled_price", signal["entry_price"]) or signal["entry_price"]

            return {
                "type": "signal_executed", "ticker": ticker,
                "broker": "ibkr" if (self.ibkr_broker and self.ibkr_broker.is_connected) else "paper",
                "strategy": signal["strategy_name"],
                "direction": signal["direction"],
                "entry_price": actual_entry,
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


scanner_pipeline = ScannerPipeline()
