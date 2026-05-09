"""Extreme strategy edge cases."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.strategy.breakout import BreakoutStrategy
from app.strategy.mean_reversion import MeanReversionStrategy


def _make_bars(closes, volumes=None, highs=None, lows=None):
    """Helper to create a bars DataFrame."""
    n = len(closes)
    if volumes is None:
        volumes = [1000.0] * n
    if highs is None:
        highs = [c + 1.0 for c in closes]
    if lows is None:
        lows = [c - 1.0 for c in closes]
    return pd.DataFrame({
        "open": closes, "high": highs, "low": lows,
        "close": closes, "volume": volumes,
    })


class TestBreakoutEdgeCases:

    def test_single_bar_returns_none(self):
        bars = _make_bars([100.0])
        strategy = BreakoutStrategy()
        result = strategy.evaluate("SPY", bars, {"rsi": 50, "vwap": 100, "atr": 2}, {"change_pct": 0})
        assert result is None

    def test_all_same_price_no_breakout(self):
        closes = [100.0] * 25
        bars = _make_bars(closes)
        strategy = BreakoutStrategy()
        result = strategy.evaluate("SPY", bars, {"rsi": 50, "vwap": 100, "atr": 0}, {"change_pct": 0})
        assert result is None

    def test_breakout_with_low_volume_rejected(self):
        """Price breaks high but volume is low."""
        closes = [100.0] * 20 + [105.0]
        volumes = [1000.0] * 20 + [500.0]  # Low volume on breakout
        bars = _make_bars(closes, volumes)
        strategy = BreakoutStrategy()
        result = strategy.evaluate("SPY", bars, {"rsi": 60, "vwap": 100, "atr": 2}, {"change_pct": 0})
        assert result is None

    def test_breakout_market_decline_rejected(self):
        """Breakout signal but market is down > 0.7%."""
        closes = [100.0] * 20 + [105.0]
        volumes = [1000.0] * 20 + [3000.0]
        bars = _make_bars(closes, volumes)
        strategy = BreakoutStrategy()
        result = strategy.evaluate("SPY", bars, {"rsi": 60, "vwap": 99, "atr": 2}, {"change_pct": -1.0})
        assert result is None

    def test_breakout_valid_signal(self):
        """Valid breakout with volume surge and bullish market."""
        closes = [100.0] * 20 + [105.0]
        volumes = [1000.0] * 20 + [2500.0]
        bars = _make_bars(closes, volumes)
        strategy = BreakoutStrategy()
        result = strategy.evaluate("SPY", bars, {"rsi": 60, "vwap": 99.0, "atr": 2.0}, {"change_pct": 0.5})
        assert result is not None
        assert result["direction"] == "long"
        assert result["stop_loss"] < result["entry_price"]
        assert result["take_profit"] > result["entry_price"]

    def test_breakout_stop_loss_within_bounds(self):
        """Stop loss should be reasonable (not too far from entry)."""
        closes = [100.0] * 20 + [105.0]
        volumes = [1000.0] * 20 + [2500.0]
        bars = _make_bars(closes, volumes)
        strategy = BreakoutStrategy()
        result = strategy.evaluate("SPY", bars, {"rsi": 60, "vwap": 99.0, "atr": 2.0}, {"change_pct": 0.5})
        assert result is not None
        # Stop loss should be within 5% of entry
        stop_distance = (result["entry_price"] - result["stop_loss"]) / result["entry_price"]
        assert stop_distance < 0.05


class TestMeanReversionEdgeCases:

    def test_rsi_above_threshold_no_signal(self):
        closes = [100.0] * 20
        bars = _make_bars(closes)
        strategy = MeanReversionStrategy()
        result = strategy.evaluate("AAPL", bars, {"rsi": 50, "vwap": 100, "atr": 2}, {"change_pct": 0})
        assert result is None

    def test_negative_news_blocks_signal(self):
        closes = [100.0] * 20
        bars = _make_bars(closes)
        strategy = MeanReversionStrategy()
        news = {"has_major_negative": True, "sentiment": "negative"}
        result = strategy.evaluate("AAPL", bars, {"rsi": 20, "vwap": 105, "atr": 2}, {"change_pct": 0}, news=news)
        assert result is None

    def test_price_near_vwap_no_signal(self):
        """Price is near VWAP (not oversold enough)."""
        closes = [100.0] * 20
        bars = _make_bars(closes)
        strategy = MeanReversionStrategy()
        result = strategy.evaluate("AAPL", bars, {"rsi": 22, "vwap": 100.5, "atr": 2}, {"change_pct": 0})
        assert result is None  # deviation < 2%

    def test_extreme_oversold_signal(self):
        """RSI very low, price far below VWAP."""
        closes = [100.0] * 15 + [90.0, 88.0, 86.0, 84.0, 82.0]
        bars = _make_bars(closes)
        strategy = MeanReversionStrategy()
        result = strategy.evaluate("AAPL", bars, {"rsi": 15, "vwap": 100.0, "atr": 3.0}, {"change_pct": -0.5})
        assert result is not None
        assert result["direction"] == "long"
        assert result["take_profit"] == 100.0  # Target is VWAP

    def test_zero_vwap_no_signal(self):
        """VWAP = 0 should not produce a signal."""
        closes = [80.0] * 20
        bars = _make_bars(closes)
        strategy = MeanReversionStrategy()
        result = strategy.evaluate("AAPL", bars, {"rsi": 20, "vwap": 0, "atr": 2}, {"change_pct": 0})
        assert result is None
