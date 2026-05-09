"""Extreme risk control edge cases."""
from __future__ import annotations

import pytest

from app.risk.hard_rules import HardRiskChecker
from app.risk.position_manager import PositionManager


class TestHardRiskEdgeCases:

    def test_daily_loss_exactly_at_limit(self):
        """Exactly at limit is allowed (< not <=)."""
        checker = HardRiskChecker(max_daily_loss_pct=0.01, max_single_position_pct=5.0)
        result = checker.check(
            position_pct=2.0, current_positions=0,
            daily_pnl_pct=-0.01, weekly_pnl_pct=0,
            consecutive_losses=0, daily_volume_usd=10_000_000,
        )
        assert result.approved is True

    def test_daily_loss_just_below_limit(self):
        checker = HardRiskChecker(max_daily_loss_pct=0.01, max_single_position_pct=5.0)
        result = checker.check(
            position_pct=2.0, current_positions=0,
            daily_pnl_pct=-0.009, weekly_pnl_pct=0,
            consecutive_losses=0, daily_volume_usd=10_000_000,
        )
        assert result.approved is True

    def test_daily_loss_exceeds_limit(self):
        checker = HardRiskChecker(max_daily_loss_pct=0.01, max_single_position_pct=5.0)
        result = checker.check(
            position_pct=2.0, current_positions=0,
            daily_pnl_pct=-0.015, weekly_pnl_pct=0,
            consecutive_losses=0, daily_volume_usd=10_000_000,
        )
        assert result.approved is False

    def test_consecutive_losses_exactly_at_limit(self):
        checker = HardRiskChecker(consecutive_loss_limit=3, max_single_position_pct=5.0)
        result = checker.check(
            position_pct=2.0, current_positions=0,
            daily_pnl_pct=0, weekly_pnl_pct=0,
            consecutive_losses=3, daily_volume_usd=10_000_000,
        )
        assert result.approved is False

    def test_consecutive_losses_just_below_limit(self):
        checker = HardRiskChecker(consecutive_loss_limit=3, max_single_position_pct=5.0)
        result = checker.check(
            position_pct=2.0, current_positions=0,
            daily_pnl_pct=0, weekly_pnl_pct=0,
            consecutive_losses=2, daily_volume_usd=10_000_000,
        )
        assert result.approved is True

    def test_positions_exactly_at_limit(self):
        checker = HardRiskChecker(max_concurrent_positions=2)
        result = checker.check(
            position_pct=2.0, current_positions=2,
            daily_pnl_pct=0, weekly_pnl_pct=0,
            consecutive_losses=0, daily_volume_usd=10_000_000,
        )
        assert result.approved is False

    def test_zero_position_pct(self):
        checker = HardRiskChecker(max_single_position_pct=2.0)
        result = checker.check(
            position_pct=0, current_positions=0,
            daily_pnl_pct=0, weekly_pnl_pct=0,
            consecutive_losses=0, daily_volume_usd=10_000_000,
        )
        assert result.approved is True  # 0% position should pass

    def test_extreme_position_pct(self):
        checker = HardRiskChecker(max_single_position_pct=2.0)
        result = checker.check(
            position_pct=100, current_positions=0,
            daily_pnl_pct=0, weekly_pnl_pct=0,
            consecutive_losses=0, daily_volume_usd=10_000_000,
        )
        assert result.approved is False

    def test_zero_volume_rejected(self):
        checker = HardRiskChecker()
        result = checker.check(
            position_pct=2.0, current_positions=0,
            daily_pnl_pct=0, weekly_pnl_pct=0,
            consecutive_losses=0, daily_volume_usd=0,
        )
        assert result.approved is False

    def test_extreme_spread_rejected(self):
        checker = HardRiskChecker()
        result = checker.check(
            position_pct=2.0, current_positions=0,
            daily_pnl_pct=0, weekly_pnl_pct=0,
            consecutive_losses=0, daily_volume_usd=10_000_000,
            spread_pct=0.1,
        )
        assert result.approved is False


class TestPositionManagerEdgeCases:

    def test_zero_price_returns_zero(self):
        pm = PositionManager(max_position_pct=2.0, account_value=100_000)
        qty = pm.calculate_quantity(0, 2.0)
        assert qty == 0

    def test_negative_price_returns_zero(self):
        pm = PositionManager(max_position_pct=2.0, account_value=100_000)
        qty = pm.calculate_quantity(-10, 2.0)
        assert qty == 0

    def test_zero_account_value(self):
        pm = PositionManager(max_position_pct=2.0, account_value=0)
        qty = pm.calculate_quantity(100, 2.0)
        assert qty == 0

    def test_very_small_position(self):
        pm = PositionManager(max_position_pct=2.0, account_value=100)
        qty = pm.calculate_quantity(50000, 2.0)
        assert qty == 0  # $2 / $50000 = 0.00004 shares → rounds to 0

    def test_fractional_share(self):
        pm = PositionManager(max_position_pct=2.0, account_value=100)
        qty = pm.calculate_quantity(100, 2.0)
        assert qty == 0.02  # $2 / $100 = 0.02 shares

    def test_risk_based_sizing_limits_loss(self):
        pm = PositionManager(max_position_pct=45.0, account_value=200, max_risk_per_trade_pct=1.0)
        qty = pm.calculate_quantity(100, 45.0, stop_loss=95.0)
        # Risk-based: $2 max loss / $5 risk per share = 0.4 shares
        # Fixed: $90 / $100 = 0.9 shares
        # Should use min(0.9, 0.4) = 0.4
        assert qty == 0.4

    def test_stop_loss_above_price_uses_fixed(self):
        """When stop_loss > price (invalid), fall back to fixed sizing."""
        pm = PositionManager(max_position_pct=2.0, account_value=100_000)
        qty = pm.calculate_quantity(100, 2.0, stop_loss=110.0)
        assert qty == 20  # $100000 * 2% / $100 = 20 shares
