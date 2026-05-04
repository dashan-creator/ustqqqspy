from __future__ import annotations

import pandas as pd

from app.strategy.base import StrategyBase


class MeanReversionStrategy(StrategyBase):
    """Oversold bounce: RSI < 25, price far below VWAP, no major negative news."""

    name = "mean_reversion"
    rsi_threshold = 25
    vwap_deviation_pct = 0.02

    def evaluate(self, ticker: str, bars: pd.DataFrame, indicators: dict, market: dict, news: dict | None = None) -> dict | None:
        if len(bars) < 5:
            return None

        if news and news.get("has_major_negative", False):
            return None

        rsi_val = indicators.get("rsi", 50)
        vwap_val = indicators.get("vwap", 0)
        atr_val = indicators.get("atr", 0)
        closes = bars["close"].values
        current_price = closes[-1]

        if rsi_val >= self.rsi_threshold:
            return None

        if vwap_val <= 0:
            return None
        deviation = (vwap_val - current_price) / vwap_val
        if deviation < self.vwap_deviation_pct:
            return None

        if atr_val <= 0:
            atr_val = current_price * 0.02

        entry_price = current_price
        stop_loss = entry_price - 1.5 * atr_val
        take_profit = vwap_val

        strength = min(1.0, (self.rsi_threshold - rsi_val) / self.rsi_threshold)

        return {
            "ticker": ticker,
            "strategy_name": self.name,
            "direction": "long",
            "strength": round(strength, 2),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "reason": f"Oversold bounce: RSI={rsi_val:.0f}, {deviation*100:.1f}% below VWAP",
        }
