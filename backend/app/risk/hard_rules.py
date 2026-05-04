from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str = ""
    suggested_position_pct: float | None = None


class HardRiskChecker:
    """Hard risk rules. Cannot be overridden by LLM or config."""

    def __init__(
        self,
        max_daily_loss_pct: float = 0.01,
        max_weekly_loss_pct: float = 0.04,
        max_concurrent_positions: int = 2,
        max_single_position_pct: float = 0.02,
        consecutive_loss_limit: int = 3,
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_weekly_loss_pct = max_weekly_loss_pct
        self.max_concurrent_positions = max_concurrent_positions
        self.max_single_position_pct = max_single_position_pct
        self.consecutive_loss_limit = consecutive_loss_limit
        self.min_volume_usd = 5_000_000
        self.max_spread_pct = 0.005

    def check(
        self,
        position_pct: float,
        current_positions: int,
        daily_pnl_pct: float,
        weekly_pnl_pct: float,
        consecutive_losses: int,
        daily_volume_usd: float,
        spread_pct: float = 0.0,
    ) -> RiskCheckResult:
        if position_pct > self.max_single_position_pct:
            return RiskCheckResult(False, f"仓位 {position_pct}% 超过上限 {self.max_single_position_pct}%", self.max_single_position_pct)
        if current_positions >= self.max_concurrent_positions:
            return RiskCheckResult(False, f"持仓数 {current_positions} 已达上限 {self.max_concurrent_positions}")
        if daily_pnl_pct <= -self.max_daily_loss_pct:
            return RiskCheckResult(False, f"当日亏损 {daily_pnl_pct*100:.2f}% 达到上限 {self.max_daily_loss_pct*100}%")
        if weekly_pnl_pct <= -self.max_weekly_loss_pct:
            return RiskCheckResult(False, f"本周亏损 {weekly_pnl_pct*100:.2f}% 达到上限 {self.max_weekly_loss_pct*100}%")
        if consecutive_losses >= self.consecutive_loss_limit:
            return RiskCheckResult(False, f"连续亏损 {consecutive_losses} 笔，达到上限 {self.consecutive_loss_limit}")
        if daily_volume_usd < self.min_volume_usd:
            return RiskCheckResult(False, f"日成交额 ${daily_volume_usd:,.0f} 低于最低要求 ${self.min_volume_usd:,.0f}")
        if spread_pct > self.max_spread_pct:
            return RiskCheckResult(False, f"点差 {spread_pct*100:.2f}% 超过上限 {self.max_spread_pct*100}%")
        return RiskCheckResult(True, "风控通过")
