"""Extreme market data edge cases."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.market.indicators import atr, rsi, vwap


def test_rsi_all_same_price():
    """All bars same price → no losses → RSI = 100 (convention)."""
    closes = np.full(20, 100.0)
    result = rsi(closes, period=14)
    assert result == 100.0  # No losses = max RSI


def test_rsi_single_change():
    """Only one price change in entire series."""
    closes = np.full(20, 100.0)
    closes[-1] = 101.0
    result = rsi(closes, period=14)
    assert result > 90  # Almost all gains


def test_rsi_extreme_drop():
    """Price drops from 100 to 1."""
    closes = np.array([100.0] * 14 + [1.0])
    result = rsi(closes, period=14)
    assert result < 5


def test_vwap_zero_volume():
    """Zero volume → should return last close."""
    highs = np.array([105.0, 106.0])
    lows = np.array([95.0, 96.0])
    closes = np.array([100.0, 101.0])
    volumes = np.array([0.0, 0.0])
    result = vwap(highs, lows, closes, volumes)
    assert result == 101.0


def test_vwap_single_bar():
    """Single bar VWAP."""
    result = vwap(
        np.array([110.0]),
        np.array([90.0]),
        np.array([100.0]),
        np.array([1000.0]),
    )
    expected = (110 + 90 + 100) / 3  # typical price
    assert abs(result - expected) < 0.01


def test_atr_single_bar():
    """ATR with only 1 bar → high - low."""
    result = atr(
        np.array([110.0]),
        np.array([90.0]),
        np.array([100.0]),
        period=14,
    )
    assert result == 20.0


def test_atr_zero_range():
    """All bars identical → ATR = 0."""
    vals = np.full(20, 100.0)
    result = atr(vals, vals, vals, period=14)
    assert result == 0.0


def test_atr_with_gap():
    """Price gaps up significantly."""
    highs = np.array([100.0, 100.0, 115.0, 115.0, 115.0])
    lows = np.array([98.0, 98.0, 110.0, 110.0, 110.0])
    closes = np.array([99.0, 99.0, 112.0, 112.0, 112.0])
    result = atr(highs, lows, closes, period=3)
    assert result > 5.0  # Gap should increase ATR
