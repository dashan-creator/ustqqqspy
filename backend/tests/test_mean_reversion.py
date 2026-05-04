from __future__ import annotations

import pandas as pd
import pytest

from app.strategy.mean_reversion import MeanReversionStrategy


@pytest.fixture
def oversold_data():
    closes = [100] * 10 + [97, 94, 91]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    volumes = [1000] * 13
    return pd.DataFrame({"open": closes, "high": highs, "low": lows, "close": closes, "volume": volumes})


def test_mean_reversion_generates_signal(oversold_data):
    strategy = MeanReversionStrategy()
    indicators = {"rsi": 22.0, "vwap": 98.0, "atr": 2.0}
    market = {"is_bullish": True, "change_pct": 0.2}
    news = {"sentiment": "neutral", "has_major_negative": False}
    signal = strategy.evaluate("AAPL", oversold_data, indicators, market, news)
    assert signal is not None
    assert signal["direction"] == "long"
    assert signal["strategy_name"] == "mean_reversion"


def test_mean_reversion_no_signal_with_negative_news(oversold_data):
    strategy = MeanReversionStrategy()
    indicators = {"rsi": 22.0, "vwap": 98.0, "atr": 2.0}
    market = {"is_bullish": True, "change_pct": 0.2}
    news = {"sentiment": "negative", "has_major_negative": True}
    signal = strategy.evaluate("AAPL", oversold_data, indicators, market, news)
    assert signal is None
