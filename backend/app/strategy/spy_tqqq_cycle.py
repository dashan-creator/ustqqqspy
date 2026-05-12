from __future__ import annotations

import numpy as np
import pandas as pd

from app.strategy.base import StrategyBase


class SpyTqqqCycleStrategy(StrategyBase):
    """Cycle-aware allocation signals for SPY and TQQQ.

    The strategy keeps leverage selective: TQQQ is used only when broad-market
    trend, volatility, and event risk are aligned. SPY is used for defensive
    bounce or steady risk-on exposure.
    """

    name = "spy_tqqq_cycle"
    tickers = {"SPY", "TQQQ"}
    min_bars = 55

    risk_on_vix = 20.0
    transition_vix = 28.0
    panic_vix = 35.0
    high_vvix = 115.0
    max_tqqq_rsi = 72.0
    min_recovery_rsi = 35.0

    def evaluate(
        self,
        ticker: str,
        bars: pd.DataFrame,
        indicators: dict,
        market: dict,
        news: dict | None = None,
    ) -> dict | None:
        ticker = ticker.upper()
        if ticker not in self.tickers or len(bars) < self.min_bars:
            return None

        if news and news.get("has_major_negative", False):
            return None

        closes = bars["close"].astype(float).values
        current_price = float(closes[-1])
        sma20 = float(np.mean(closes[-20:]))
        sma50 = float(np.mean(closes[-50:]))
        prev_sma20 = float(np.mean(closes[-25:-5]))

        atr_val = float(indicators.get("atr", 0) or 0)
        if atr_val <= 0:
            atr_val = current_price * 0.02

        rsi_val = float(indicators.get("rsi", 50) or 50)
        volume_ratio = float(indicators.get("volume_ratio", 1.0) or 1.0)
        market_change = float(market.get("change_pct", 0) or 0)
        vix = float(market.get("vix", 20) or 20)
        vix3m = float(market.get("vix3m", 22) or 22)
        vvix = float(market.get("vvix", 95) or 95)
        move = float(market.get("move", 120) or 120)
        fomc_days = market.get("fomc_days_to_event")
        fed_event_risk = bool(market.get("fed_event_risk", False))
        if fomc_days is not None:
            fed_event_risk = fed_event_risk or abs(float(fomc_days)) <= 1

        trend_up = current_price > sma20 > sma50 and sma20 >= prev_sma20
        trend_repairing = current_price > sma20 and sma20 >= prev_sma20 and rsi_val >= self.min_recovery_rsi
        backwardation = vix3m > 0 and vix / vix3m >= 1.0
        panic = vix >= self.panic_vix or (backwardation and vix >= self.transition_vix) or vvix >= self.high_vvix
        bond_stress = move >= 150

        if ticker == "TQQQ":
            return self._evaluate_tqqq(
                current_price=current_price,
                atr_val=atr_val,
                rsi_val=rsi_val,
                volume_ratio=volume_ratio,
                market_change=market_change,
                vix=vix,
                trend_up=trend_up,
                trend_repairing=trend_repairing,
                panic=panic,
                bond_stress=bond_stress,
                fed_event_risk=fed_event_risk,
            )

        return self._evaluate_spy(
            current_price=current_price,
            atr_val=atr_val,
            rsi_val=rsi_val,
            volume_ratio=volume_ratio,
            market_change=market_change,
            vix=vix,
            trend_up=trend_up,
            trend_repairing=trend_repairing,
            panic=panic,
            fed_event_risk=fed_event_risk,
        )

    def _evaluate_tqqq(
        self,
        *,
        current_price: float,
        atr_val: float,
        rsi_val: float,
        volume_ratio: float,
        market_change: float,
        vix: float,
        trend_up: bool,
        trend_repairing: bool,
        panic: bool,
        bond_stress: bool,
        fed_event_risk: bool,
    ) -> dict | None:
        if fed_event_risk or bond_stress or panic or rsi_val > self.max_tqqq_rsi:
            return None

        risk_on = trend_up and vix <= self.risk_on_vix and market_change > -0.4
        recovery = trend_repairing and self.risk_on_vix < vix <= self.transition_vix and market_change >= 0.2 and volume_ratio >= 1.1
        if not (risk_on or recovery):
            return None

        stop_mult = 1.8 if risk_on else 1.4
        target_mult = 3.2 if risk_on else 2.4
        strength = 0.75 if risk_on else 0.55
        if vix < 16 and rsi_val < 65:
            strength += 0.1

        return self._signal(
            ticker="TQQQ",
            strength=min(strength, 0.9),
            entry_price=current_price,
            stop_loss=current_price - stop_mult * atr_val,
            take_profit=current_price + target_mult * atr_val,
            reason=f"TQQQ cycle long: trend={'risk-on' if risk_on else 'repair'}, VIX={vix:.1f}, RSI={rsi_val:.0f}",
        )

    def _evaluate_spy(
        self,
        *,
        current_price: float,
        atr_val: float,
        rsi_val: float,
        volume_ratio: float,
        market_change: float,
        vix: float,
        trend_up: bool,
        trend_repairing: bool,
        panic: bool,
        fed_event_risk: bool,
    ) -> dict | None:
        steady_trend = trend_up and vix <= self.transition_vix and not fed_event_risk and rsi_val <= 70
        panic_reversal = panic and trend_repairing and rsi_val >= 38 and market_change >= 0.3 and volume_ratio >= 1.2
        defensive_repair = not panic and trend_repairing and market_change > -0.2 and rsi_val < 62
        if not (steady_trend or panic_reversal or defensive_repair):
            return None

        stop_mult = 1.6 if panic_reversal else 1.3
        target_mult = 2.4 if panic_reversal else 2.0
        strength = 0.65 if steady_trend else 0.58
        if panic_reversal:
            strength = 0.7
        elif defensive_repair:
            strength = 0.5

        return self._signal(
            ticker="SPY",
            strength=strength,
            entry_price=current_price,
            stop_loss=current_price - stop_mult * atr_val,
            take_profit=current_price + target_mult * atr_val,
            reason=f"SPY cycle long: VIX={vix:.1f}, RSI={rsi_val:.0f}, mode={'panic-reversal' if panic_reversal else 'trend'}",
        )

    def _signal(
        self,
        *,
        ticker: str,
        strength: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        reason: str,
    ) -> dict:
        return {
            "ticker": ticker,
            "strategy_name": self.name,
            "direction": "long",
            "strength": round(strength, 2),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(max(stop_loss, 0.01), 2),
            "take_profit": round(take_profit, 2),
            "reason": reason,
        }
