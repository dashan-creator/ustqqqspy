from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.strategy.breakout import BreakoutStrategy


@pytest.fixture
def breakout_data():
    closes = [100 + i * 0.1 for i in range(20)] + [103, 105]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [1000] * 20 + [2500, 3000]
    return pd.DataFrame({"open": closes, "high": highs, "low": lows, "close": closes, "volume": volumes})


def test_breakout_generates_signal(breakout_data):
    strategy = BreakoutStrategy()
    indicators = {"rsi": 60.0, "vwap": 101.0, "atr": 1.5}
    market = {"is_bullish": True, "change_pct": 0.5}
    signal = strategy.evaluate("NVDA", breakout_data, indicators, market)
    assert signal is not None
    assert signal["ticker"] == "NVDA"
    assert signal["direction"] == "long"
    assert signal["strategy_name"] == "breakout"
    assert signal["entry_price"] > 0
    assert signal["stop_loss"] < signal["entry_price"]
    assert signal["take_profit"] > signal["entry_price"]


def test_breakout_no_signal_when_market_weak(breakout_data):
    strategy = BreakoutStrategy()
    indicators = {"rsi": 60.0, "vwap": 101.0, "atr": 1.5}
    market = {"is_bullish": False, "change_pct": -1.5}
    signal = strategy.evaluate("NVDA", breakout_data, indicators, market)
    assert signal is None


def test_breakout_no_signal_low_volume(breakout_data):
    strategy = BreakoutStrategy()
    breakout_data.loc[breakout_data.index[-1], "volume"] = 500
    indicators = {"rsi": 60.0, "vwap": 101.0, "atr": 1.5}
    market = {"is_bullish": True, "change_pct": 0.5}
    signal = strategy.evaluate("NVDA", breakout_data, indicators, market)
    assert signal is None
