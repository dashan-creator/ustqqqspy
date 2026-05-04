from __future__ import annotations


class PositionManager:
    """Track and manage position sizing."""

    def __init__(self, max_position_pct: float = 2.0, account_value: float = 100_000.0):
        self.max_position_pct = max_position_pct
        self.account_value = account_value

    def calculate_quantity(self, price: float, position_pct: float) -> int:
        capped_pct = min(position_pct, self.max_position_pct)
        position_value = self.account_value * (capped_pct / 100.0)
        return int(position_value / price)

    def check_stop_loss(self, current_price: float, stop_loss: float) -> bool:
        return current_price <= stop_loss

    def check_take_profit(self, current_price: float, take_profit: float) -> bool:
        return current_price >= take_profit

    def trailing_stop(self, current_price: float, highest_price: float, atr: float) -> float:
        return highest_price - atr
