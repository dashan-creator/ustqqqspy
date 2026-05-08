from __future__ import annotations


class PositionManager:
    """Track and manage position sizing with risk-based calculation."""

    def __init__(self, max_position_pct: float = 2.0, account_value: float = 100_000.0, max_risk_per_trade_pct: float = 1.0):
        self.max_position_pct = max_position_pct
        self.account_value = account_value
        self.max_risk_per_trade_pct = max_risk_per_trade_pct  # max loss per trade as % of account

    def calculate_quantity(self, price: float, position_pct: float, stop_loss: float = 0) -> int:
        """Calculate position size. If stop_loss provided, use risk-based sizing (smaller of two methods)."""
        capped_pct = min(position_pct, self.max_position_pct)

        # Method 1: Fixed percentage of account
        fixed_qty = int(self.account_value * (capped_pct / 100.0) / price) if price > 0 else 0

        # Method 2: Risk-based (limit max loss to max_risk_per_trade_pct of account)
        if stop_loss > 0 and stop_loss < price:
            risk_per_share = price - stop_loss
            max_risk_dollars = self.account_value * (self.max_risk_per_trade_pct / 100.0)
            risk_qty = int(max_risk_dollars / risk_per_share) if risk_per_share > 0 else fixed_qty
            return min(fixed_qty, risk_qty)

        return fixed_qty

    def check_stop_loss(self, current_price: float, stop_loss: float) -> bool:
        return current_price <= stop_loss

    def check_take_profit(self, current_price: float, take_profit: float) -> bool:
        return current_price >= take_profit

    def trailing_stop(self, current_price: float, highest_price: float, atr: float) -> float:
        return highest_price - atr
