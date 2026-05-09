from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class GateDecision:
    needs_llm: bool
    reason: str
    auto_action: str = "approve"  # approve / reduce_size / reject


class SmartGate:
    """Decides whether LLM review is needed based on market conditions.
    Skips LLM for normal conditions to save tokens and reduce latency.
    Uses recent bar data as secondary validation when skipping LLM."""

    def evaluate(
        self,
        rsi: float,
        volume_ratio: float,
        market_change_pct: float,
        signal_strength: float,
        has_news: bool,
        consecutive_losses: int,
        bars: pd.DataFrame | None = None,
        direction: str = "long",
    ) -> GateDecision:
        """Return whether LLM is needed and auto-action if skipping."""

        # === Tier 1: Always call LLM for extreme conditions ===
        if rsi < 20 or rsi > 80:
            return GateDecision(True, f"RSI极端: {rsi:.0f}")

        if volume_ratio > 3.0:
            return GateDecision(True, f"异常放量: {volume_ratio:.1f}x")

        if abs(market_change_pct) > 1.5:
            return GateDecision(True, f"大盘剧烈波动: {market_change_pct:+.2f}%")

        if has_news:
            return GateDecision(True, "有新闻事件")

        if consecutive_losses >= 2:
            return GateDecision(True, f"连续亏损{consecutive_losses}笔")

        if signal_strength < 0.3:
            return GateDecision(True, f"信号强度低: {signal_strength:.2f}")

        # === Tier 2: Use recent bars for trend validation ===
        if bars is not None and len(bars) >= 5:
            trend_ok = self._validate_trend(bars, direction)
            if not trend_ok:
                return GateDecision(True, "近期趋势与信号方向矛盾")

        # === Tier 3: Moderate conditions - reduce size but skip LLM ===
        if rsi < 30 or rsi > 70:
            return GateDecision(False, f"RSI偏极端但可接受: {rsi:.0f}", "reduce_size")

        if volume_ratio > 2.0:
            return GateDecision(False, f"放量但可接受: {volume_ratio:.1f}x", "reduce_size")

        if abs(market_change_pct) > 0.8:
            return GateDecision(False, f"大盘波动中等: {market_change_pct:+.2f}%", "reduce_size")

        # === Tier 4: Normal - skip LLM, use bars as final check ===
        if bars is not None and len(bars) >= 3:
            trend_ok = self._validate_trend(bars, direction)
            if not trend_ok:
                return GateDecision(False, "趋势微弱，降仓", "reduce_size")

        return GateDecision(False, "条件正常，跳过LLM审查", "approve")

    def _validate_trend(self, bars: pd.DataFrame, direction: str) -> bool:
        """Check if recent bars support the signal direction. Flat market is neutral (OK)."""
        closes = bars["close"].values[-5:]
        if len(closes) < 3:
            return True

        # Count up/down/flat bars in last 5
        comparisons = len(closes) - 1
        up_bars = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        down_bars = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])
        flat_bars = comparisons - up_bars - down_bars

        # Flat market (most bars unchanged) → neutral, allow
        if flat_bars >= len(closes) // 2:
            return True

        if direction == "long":
            # At least 3/5 bars should be up for long, or final > start
            return up_bars >= 3 or closes[-1] > closes[0]
        else:
            return down_bars >= 3 or closes[-1] < closes[0]


smart_gate = SmartGate()
