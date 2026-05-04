from __future__ import annotations

import numpy as np


def rsi(closes: np.ndarray, period: int = 14) -> float:
    """Relative Strength Index."""
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def vwap(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> float:
    """Volume Weighted Average Price."""
    typical_price = (highs + lows + closes) / 3.0
    cumulative_tp_vol = np.sum(typical_price * volumes)
    cumulative_vol = np.sum(volumes)
    if cumulative_vol == 0:
        return float(closes[-1])
    return float(cumulative_tp_vol / cumulative_vol)


def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Average True Range."""
    if len(closes) < 2:
        return float(highs[-1] - lows[-1])

    prev_closes = closes[:-1]
    tr1 = highs[1:] - lows[1:]
    tr2 = np.abs(highs[1:] - prev_closes)
    tr3 = np.abs(lows[1:] - prev_closes)
    true_range = np.maximum(tr1, np.maximum(tr2, tr3))

    if len(true_range) < period:
        return float(np.mean(true_range))
    return float(np.mean(true_range[-period:]))
