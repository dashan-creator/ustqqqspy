"""Extreme SmartGate and LLM edge cases."""
from __future__ import annotations

import pandas as pd
import pytest

from app.llm.smart_gate import SmartGate


def _make_bars(n=25, base=100.0, trend=0.0):
    closes = [base + i * trend for i in range(n)]
    return pd.DataFrame({
        "open": closes, "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes], "close": closes,
        "volume": [1000.0] * n,
    })


class TestSmartGateEdgeCases:

    def setup_method(self):
        self.gate = SmartGate()

    def test_extreme_rsi_oversold(self):
        result = self.gate.evaluate(rsi=5, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=0, bars=_make_bars(), direction="long")
        assert result.needs_llm is True

    def test_extreme_rsi_overbought(self):
        result = self.gate.evaluate(rsi=95, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=0, bars=_make_bars(), direction="long")
        assert result.needs_llm is True

    def test_extreme_volume_spike(self):
        result = self.gate.evaluate(rsi=50, volume_ratio=5.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=0, bars=_make_bars(), direction="long")
        assert result.needs_llm is True

    def test_extreme_market_move(self):
        result = self.gate.evaluate(rsi=50, volume_ratio=1.0, market_change_pct=-3.0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=0, bars=_make_bars(), direction="long")
        assert result.needs_llm is True

    def test_consecutive_losses_triggers_llm(self):
        result = self.gate.evaluate(rsi=50, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=2, bars=_make_bars(), direction="long")
        assert result.needs_llm is True

    def test_weak_signal_triggers_llm(self):
        result = self.gate.evaluate(rsi=50, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.1, has_news=False,
                                     consecutive_losses=0, bars=_make_bars(), direction="long")
        assert result.needs_llm is True

    def test_news_triggers_llm(self):
        result = self.gate.evaluate(rsi=50, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=True,
                                     consecutive_losses=0, bars=_make_bars(), direction="long")
        assert result.needs_llm is True

    def test_normal_conditions_skip_llm(self):
        result = self.gate.evaluate(rsi=50, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=0, bars=_make_bars(), direction="long")
        assert result.needs_llm is False
        assert result.auto_action == "approve"

    def test_moderate_conditions_reduce_size(self):
        result = self.gate.evaluate(rsi=72, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=0, bars=_make_bars(), direction="long")
        assert result.needs_llm is False
        assert result.auto_action == "reduce_size"

    def test_downtrend_triggers_llm_for_long(self):
        """Downtrend bars should require LLM for long signals."""
        bars = _make_bars(n=5, base=100.0, trend=-2.0)  # Declining
        result = self.gate.evaluate(rsi=50, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=0, bars=bars, direction="long")
        assert result.needs_llm is True

    def test_uptrend_approves_long(self):
        """Uptrend bars should approve long signals."""
        bars = _make_bars(n=5, base=100.0, trend=2.0)  # Rising
        result = self.gate.evaluate(rsi=50, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=0, bars=bars, direction="long")
        assert result.auto_action == "approve"

    def test_empty_bars_handled(self):
        """Empty bars should not crash."""
        bars = _make_bars(n=2, base=100.0)
        result = self.gate.evaluate(rsi=50, volume_ratio=1.0, market_change_pct=0,
                                     signal_strength=0.5, has_news=False,
                                     consecutive_losses=0, bars=bars, direction="long")
        assert result is not None

    def test_all_conditions_combined(self):
        """Multiple extreme conditions → definitely needs LLM."""
        result = self.gate.evaluate(rsi=10, volume_ratio=4.0, market_change_pct=-2.0,
                                     signal_strength=0.1, has_news=True,
                                     consecutive_losses=3, bars=_make_bars(), direction="long")
        assert result.needs_llm is True
        # auto_action defaults to "approve" when needs_llm=True (LLM will decide)
