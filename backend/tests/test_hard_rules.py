from __future__ import annotations

import pytest

from app.risk.hard_rules import HardRiskChecker, RiskCheckResult


@pytest.fixture
def checker():
    return HardRiskChecker(
        max_daily_loss_pct=0.01,
        max_weekly_loss_pct=0.04,
        max_concurrent_positions=2,
        max_single_position_pct=2.0,
        consecutive_loss_limit=3,
    )


def test_approve_normal_trade(checker):
    result = checker.check(position_pct=2.0, current_positions=0, daily_pnl_pct=0.0, weekly_pnl_pct=0.0, consecutive_losses=0, daily_volume_usd=10_000_000, spread_pct=0.001)
    assert result.approved is True


def test_reject_position_too_large(checker):
    result = checker.check(position_pct=5.0, current_positions=0, daily_pnl_pct=0.0, weekly_pnl_pct=0.0, consecutive_losses=0, daily_volume_usd=10_000_000, spread_pct=0.001)
    assert result.approved is False


def test_reject_too_many_positions(checker):
    result = checker.check(position_pct=2.0, current_positions=2, daily_pnl_pct=0.0, weekly_pnl_pct=0.0, consecutive_losses=0, daily_volume_usd=10_000_000, spread_pct=0.001)
    assert result.approved is False


def test_reject_daily_loss_limit(checker):
    result = checker.check(position_pct=2.0, current_positions=0, daily_pnl_pct=-0.012, weekly_pnl_pct=-0.02, consecutive_losses=0, daily_volume_usd=10_000_000, spread_pct=0.001)
    assert result.approved is False


def test_reject_consecutive_losses(checker):
    result = checker.check(position_pct=2.0, current_positions=0, daily_pnl_pct=-0.005, weekly_pnl_pct=-0.02, consecutive_losses=3, daily_volume_usd=10_000_000, spread_pct=0.001)
    assert result.approved is False


def test_reject_low_volume(checker):
    result = checker.check(position_pct=2.0, current_positions=0, daily_pnl_pct=0.0, weekly_pnl_pct=0.0, consecutive_losses=0, daily_volume_usd=1_000_000, spread_pct=0.001)
    assert result.approved is False
