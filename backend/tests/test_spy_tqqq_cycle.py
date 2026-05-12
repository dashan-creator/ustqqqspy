from __future__ import annotations

import pandas as pd

from app.strategy.spy_tqqq_cycle import SpyTqqqCycleStrategy


def _make_bars(closes: list[float], volume: float = 1000.0) -> pd.DataFrame:
    return pd.DataFrame({
        "open": closes,
        "high": [c + 0.8 for c in closes],
        "low": [c - 0.8 for c in closes],
        "close": closes,
        "volume": [volume] * len(closes),
    })


def _market(**overrides) -> dict:
    base = {
        "change_pct": 0.4,
        "vix": 17.0,
        "vix3m": 22.0,
        "vvix": 92.0,
        "move": 110.0,
        "fed_event_risk": False,
        "fomc_days_to_event": None,
    }
    base.update(overrides)
    return base


def test_tqqq_risk_on_signal():
    closes = [90 + i * 0.35 for i in range(60)]
    strategy = SpyTqqqCycleStrategy()

    result = strategy.evaluate(
        "TQQQ",
        _make_bars(closes),
        {"rsi": 61, "atr": 1.4, "volume_ratio": 1.0},
        _market(vix=16.5, change_pct=0.5),
    )

    assert result is not None
    assert result["ticker"] == "TQQQ"
    assert result["strategy_name"] == "spy_tqqq_cycle"
    assert result["stop_loss"] < result["entry_price"] < result["take_profit"]


def test_tqqq_blocked_by_fomc_event_risk():
    closes = [90 + i * 0.35 for i in range(60)]
    strategy = SpyTqqqCycleStrategy()

    result = strategy.evaluate(
        "TQQQ",
        _make_bars(closes),
        {"rsi": 61, "atr": 1.4, "volume_ratio": 1.0},
        _market(vix=16.5, fomc_days_to_event=1),
    )

    assert result is None


def test_tqqq_blocked_by_panic_regime():
    closes = [90 + i * 0.35 for i in range(60)]
    strategy = SpyTqqqCycleStrategy()

    result = strategy.evaluate(
        "TQQQ",
        _make_bars(closes),
        {"rsi": 55, "atr": 1.4, "volume_ratio": 1.5},
        _market(vix=36, vix3m=30, vvix=118, change_pct=0.8),
    )

    assert result is None


def test_spy_panic_reversal_signal():
    closes = [110 - i * 0.25 for i in range(35)] + [101 + i * 0.45 for i in range(25)]
    strategy = SpyTqqqCycleStrategy()

    result = strategy.evaluate(
        "SPY",
        _make_bars(closes, volume=2500),
        {"rsi": 45, "atr": 2.1, "volume_ratio": 1.4},
        _market(vix=38, vix3m=31, vvix=120, change_pct=0.7),
    )

    assert result is not None
    assert result["ticker"] == "SPY"
    assert "panic-reversal" in result["reason"]


def test_non_core_ticker_is_ignored():
    closes = [90 + i * 0.35 for i in range(60)]
    strategy = SpyTqqqCycleStrategy()

    result = strategy.evaluate(
        "AAPL",
        _make_bars(closes),
        {"rsi": 61, "atr": 1.4, "volume_ratio": 1.0},
        _market(),
    )

    assert result is None
