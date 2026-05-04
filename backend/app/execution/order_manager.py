from __future__ import annotations

import logging

from app.execution.paper_trader import PaperTrader

logger = logging.getLogger(__name__)


class OrderManager:
    """Manage order lifecycle. V0: paper trading only."""

    def __init__(self, trader: PaperTrader):
        self.trader = trader

    def execute_signal(self, signal: dict, quantity: int) -> dict:
        ticker = signal["ticker"]
        price = signal["entry_price"]
        strategy = signal["strategy_name"]
        reason = signal.get("reason", "")
        order = self.trader.buy(ticker, quantity, price, strategy, reason)
        logger.info("Paper BUY %s x%d @ %.2f [%s]", ticker, quantity, price, strategy)
        return order

    def close_position(self, ticker: str, price: float, reason: str) -> dict:
        if ticker not in self.trader.positions:
            return {"status": "rejected", "reason": "no position"}
        pos = self.trader.positions[ticker]
        order = self.trader.sell(ticker, pos["quantity"], price, reason)
        logger.info("Paper SELL %s @ %.2f [%s]", ticker, price, reason)
        return order

    def check_exits(self, prices: dict[str, float], stop_losses: dict[str, float]) -> list[dict]:
        exits = []
        for ticker, pos in list(self.trader.positions.items()):
            current_price = prices.get(ticker, 0)
            stop = stop_losses.get(ticker, 0)
            if stop > 0 and current_price <= stop:
                order = self.close_position(ticker, current_price, f"Stop loss triggered at {stop}")
                exits.append(order)
        return exits
