from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.execution.state_store import save_state

logger = logging.getLogger(__name__)


class PaperTrader:
    """Simulated trading engine for V0/V1."""

    def __init__(self, initial_cash: float = 100_000.0, restore: bool = True):
        self.initial_cash = initial_cash
        self.positions: dict[str, dict] = {}
        self.trades: list[dict] = []
        self.orders: list[dict] = []
        self.cash = initial_cash
        if restore:
            self._load_state()

    def _load_state(self):
        """Restore state from disk on startup."""
        from app.execution.state_store import load_state
        state = load_state()
        if state and state.get("positions"):
            self.cash = state.get("cash", self.initial_cash)
            self.positions = state.get("positions", {})
            logger.info("Restored state: cash=%.2f, positions=%d", self.cash, len(self.positions))

    def _save(self, highest_prices: dict | None = None):
        """Persist state to disk after every trade."""
        save_state(self.cash, self.positions, self.trades, highest_prices)

    def buy(self, ticker: str, quantity: int, price: float, strategy: str, reason: str) -> dict:
        if quantity <= 0 or price <= 0:
            return {'ticker': ticker, 'side': 'buy', 'quantity': quantity, 'filled_price': price, 'status': 'rejected', 'strategy': strategy, 'reason': 'invalid order', 'timestamp': ''}

        cost = quantity * price
        if cost > self.cash:
            return {'ticker': ticker, 'side': 'buy', 'quantity': quantity, 'filled_price': price, 'status': 'rejected', 'strategy': strategy, 'reason': 'insufficient cash', 'timestamp': ''}

        self.cash -= cost

        if ticker in self.positions:
            pos = self.positions[ticker]
            total_qty = pos["quantity"] + quantity
            pos["avg_price"] = (pos["avg_price"] * pos["quantity"] + price * quantity) / total_qty
            pos["quantity"] = total_qty
        else:
            self.positions[ticker] = {"quantity": quantity, "avg_price": price, "strategy": strategy}

        order = {
            "ticker": ticker, "side": "buy", "quantity": quantity,
            "filled_price": price, "status": "filled", "strategy": strategy,
            "reason": reason, "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.orders.append(order)
        self._save()
        return order

    def sell(self, ticker: str, quantity: int, price: float, reason: str) -> dict:
        if ticker not in self.positions:
            return {"ticker": ticker, "side": "sell", "status": "rejected", "reason": "no position"}

        pos = self.positions[ticker]
        sell_qty = min(quantity, pos["quantity"])
        revenue = sell_qty * price
        self.cash += revenue

        pnl = (price - pos["avg_price"]) * sell_qty
        pnl_pct = ((price - pos["avg_price"]) / pos["avg_price"]) * 100

        trade = {
            "ticker": ticker, "side": "sell", "quantity": sell_qty,
            "entry_price": pos["avg_price"], "exit_price": price,
            "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
            "strategy": pos["strategy"], "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.trades.append(trade)

        pos["quantity"] -= sell_qty
        if pos["quantity"] <= 0:
            del self.positions[ticker]

        order = {
            "ticker": ticker, "side": "sell", "quantity": sell_qty,
            "filled_price": price, "status": "filled", "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.orders.append(order)
        self._save()
        return order

    def get_unrealized_pnl(self, ticker: str, current_price: float) -> float:
        if ticker not in self.positions:
            return 0.0
        pos = self.positions[ticker]
        return round((current_price - pos["avg_price"]) * pos["quantity"], 2)

    def get_portfolio_value(self, prices: dict[str, float]) -> float:
        positions_value = sum(
            prices.get(ticker, pos["avg_price"]) * pos["quantity"]
            for ticker, pos in self.positions.items()
        )
        return self.cash + positions_value

    def get_total_pnl(self) -> float:
        return sum(t["pnl"] for t in self.trades)

    def get_stats(self) -> dict:
        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]
        total = len(self.trades)
        return {
            "total_trades": total, "wins": len(wins), "losses": len(losses),
            "win_rate": len(wins) / total if total > 0 else 0,
            "total_pnl": round(self.get_total_pnl(), 2), "cash": round(self.cash, 2),
        }
