from __future__ import annotations

import numpy as np
import pandas as pd

from app.strategy.base import StrategyBase


class BreakoutStrategy(StrategyBase):
    """Trend breakout: price breaks above N-bar high with volume surge."""

    name = "breakout"
    lookback = 20
    volume_ratio = 1.8
    max_market_drop = -0.7

    def evaluate(self, ticker: str, bars: pd.DataFrame, indicators: dict, market: dict, news: dict | None = None) -> dict | None:
        if len(bars) < self.lookback + 1:
            return None

        if market.get("change_pct", 0) < self.max_market_drop:
            return None

        closes = bars["close"].values
        highs = bars["high"].values
        volumes = bars["volume"].values

        current_price = closes[-1]
        recent_high = np.max(highs[-(self.lookback + 1):-1])

        if current_price <= recent_high:
            return None

        avg_volume = np.mean(volumes[-(self.lookback + 1):-1])
        if avg_volume == 0 or volumes[-1] < avg_volume * self.volume_ratio:
            return None

        vwap_val = indicators.get("vwap", 0)
        if vwap_val > 0 and current_price < vwap_val:
            return None

        atr_val = indicators.get("atr", current_price * 0.02)
        if atr_val <= 0:
            atr_val = current_price * 0.02

        entry_price = current_price
        stop_loss = entry_price - 1.5 * atr_val
        take_profit = entry_price + 3.0 * atr_val

        vol_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        strength = min(1.0, vol_ratio / 3.0)

        return {
            "ticker": ticker,
            "strategy_name": self.name,
            "direction": "long",
            "strength": round(strength, 2),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "reason": f"Breakout above {self.lookback}-bar high {recent_high:.2f}, volume {vol_ratio:.1f}x avg",
        }
