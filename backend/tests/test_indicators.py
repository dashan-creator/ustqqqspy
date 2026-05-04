from __future__ import annotations

import numpy as np
import pytest

from app.market.indicators import atr, rsi, vwap


def test_rsi_basic():
    closes = np.array([10, 10.5, 10, 10.5, 10, 10.5, 10, 10.5, 10, 10.5, 10, 10.5, 10, 10.5, 10])
    result = rsi(closes, period=14)
    assert isinstance(result, float)
    assert 0 <= result <= 100


def test_rsi_all_up():
    closes = np.array(range(1, 20), dtype=float)
    result = rsi(closes, period=14)
    assert result > 70


def test_rsi_all_down():
    closes = np.array(range(20, 1, -1), dtype=float)
    result = rsi(closes, period=14)
    assert result < 30


def test_vwap_basic():
    highs = np.array([105, 106, 107], dtype=float)
    lows = np.array([95, 96, 97], dtype=float)
    closes = np.array([100, 101, 102], dtype=float)
    volumes = np.array([1000, 1500, 2000], dtype=float)
    result = vwap(highs, lows, closes, volumes)
    assert isinstance(result, float)
    tp = (highs + lows + closes) / 3
    expected = np.sum(tp * volumes) / np.sum(volumes)
    assert abs(result - expected) < 0.01


def test_atr_basic():
    highs = np.array([110, 112, 111, 113, 115], dtype=float)
    lows = np.array([100, 101, 102, 103, 104], dtype=float)
    closes = np.array([105, 106, 107, 108, 109], dtype=float)
    result = atr(highs, lows, closes, period=3)
    assert isinstance(result, float)
    assert result > 0
