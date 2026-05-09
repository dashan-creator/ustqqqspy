#!/usr/bin/env python3
"""Historical backtest for breakout and mean reversion strategies (daily bars)."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

from app.market.indicators import rsi, vwap, atr
from app.strategy.base import StrategyBase


class DailyBreakout(StrategyBase):
    """Breakout strategy tuned for daily bars."""
    name = "breakout"
    lookback = 10
    volume_ratio = 1.1
    max_market_drop = -2.0

    def evaluate(self, ticker, bars, indicators, market, news=None):
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
        atr_val = indicators.get("atr", current_price * 0.02)
        if atr_val <= 0:
            atr_val = current_price * 0.02
        entry_price = current_price
        stop_loss = round(entry_price - 1.5 * atr_val, 2)
        take_profit = round(entry_price + 3.0 * atr_val, 2)
        strength = min(1.0, (volumes[-1] / avg_volume) / 3.0) if avg_volume > 0 else 0.5
        return {
            "ticker": ticker, "strategy_name": self.name, "direction": "long",
            "strength": round(strength, 2), "entry_price": round(entry_price, 2),
            "stop_loss": stop_loss, "take_profit": take_profit,
            "reason": f"Breakout {recent_high:.2f}, vol {volumes[-1]/avg_volume:.1f}x",
        }


class DailyMeanReversion(StrategyBase):
    """Mean reversion tuned for daily bars."""
    name = "mean_reversion"
    rsi_threshold = 30
    vwap_deviation_pct = 0.015

    def evaluate(self, ticker, bars, indicators, market, news=None):
        if len(bars) < 5:
            return None
        if news and news.get("has_major_negative"):
            return None
        rsi_val = indicators.get("rsi", 50)
        vwap_val = indicators.get("vwap", 0)
        atr_val = indicators.get("atr", 0)
        current_price = bars["close"].values[-1]
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
        stop_loss = round(entry_price - 1.5 * atr_val, 2)
        take_profit = round(vwap_val, 2)
        strength = min(1.0, (self.rsi_threshold - rsi_val) / self.rsi_threshold)
        return {
            "ticker": ticker, "strategy_name": self.name, "direction": "long",
            "strength": round(strength, 2), "entry_price": round(entry_price, 2),
            "stop_loss": stop_loss, "take_profit": take_profit,
            "reason": f"Oversold RSI={rsi_val:.0f}, {deviation*100:.1f}% below VWAP",
        }


def download_data(tickers, period="6mo", interval="1d"):
    data = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            if not df.empty:
                df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
                df = df[["open","high","low","close","volume"]]
                data[ticker] = df
                print(f"  {ticker}: {len(df)} bars, last={df['close'].iloc[-1]:.2f}")
        except Exception as e:
            print(f"  {ticker}: error - {e}")
    return data


def run_backtest(ticker, bars, strategy, initial_cash=200.0, position_pct=45.0, max_hold_bars=10):
    cash = initial_cash
    position = None
    trades = []
    equity_curve = []
    lookback = 25

    for i in range(lookback, len(bars)):
        window = bars.iloc[:i + 1]
        current_price = bars.iloc[i]["close"]

        closes = window["close"].values
        highs = window["high"].values
        lows = window["low"].values
        volumes = window["volume"].values.astype(float)

        period = min(14, len(closes) - 1)
        indicators = {
            "rsi": rsi(closes, period=period),
            "vwap": vwap(highs, lows, closes, volumes),
            "atr": atr(highs, lows, closes, period=period),
            "volume_ratio": volumes[-1] / np.mean(volumes[-period:]) if np.mean(volumes[-period:]) > 0 else 1.0,
        }
        market = {"change_pct": 0, "is_bullish": True}

        if position:
            bars_held = i - position["entry_bar"]
            pnl_pct = (current_price - position["entry_price"]) / position["entry_price"] * 100

            exit_reason = None
            if current_price <= position["stop_loss"]:
                exit_reason = "stop_loss"
            elif current_price >= position["take_profit"]:
                exit_reason = "take_profit"
            elif bars_held >= max_hold_bars:
                exit_reason = "max_hold"

            if exit_reason:
                pnl = (current_price - position["entry_price"]) * position["quantity"]
                cash += position["quantity"] * current_price
                trades.append({
                    "ticker": ticker, "strategy": strategy.name,
                    "entry_price": position["entry_price"], "exit_price": current_price,
                    "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": exit_reason, "bars_held": bars_held,
                })
                position = None

        if position is None:
            signal = strategy.evaluate(ticker, window, indicators, market)
            if signal:
                qty = int(cash * (position_pct / 100) / signal["entry_price"])
                if qty > 0 and cash >= qty * signal["entry_price"]:
                    cash -= qty * signal["entry_price"]
                    position = {
                        "entry_price": signal["entry_price"],
                        "quantity": qty, "entry_bar": i,
                        "stop_loss": signal["stop_loss"],
                        "take_profit": signal["take_profit"],
                    }

        equity = cash + (position["quantity"] * current_price if position else 0)
        equity_curve.append({"bar": i, "equity": equity})

    if position:
        last_price = bars.iloc[-1]["close"]
        pnl = (last_price - position["entry_price"]) * position["quantity"]
        cash += position["quantity"] * last_price
        trades.append({
            "ticker": ticker, "strategy": strategy.name,
            "entry_price": position["entry_price"], "exit_price": last_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round((last_price - position["entry_price"]) / position["entry_price"] * 100, 2),
            "exit_reason": "end_of_backtest", "bars_held": len(bars) - 1 - position["entry_bar"],
        })

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    total = len(trades)
    peak = 0
    max_dd = 0
    for ec in equity_curve:
        peak = max(peak, ec["equity"])
        dd = (peak - ec["equity"]) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    return {
        "ticker": ticker, "strategy": strategy.name,
        "initial_cash": initial_cash, "final_cash": round(cash, 2),
        "total_return_pct": round((cash - initial_cash) / initial_cash * 100, 2),
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / total * 100, 1) if total > 0 else 0,
        "avg_win": round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0,
        "max_drawdown_pct": round(max_dd * 100, 2),
        "trades": trades,
    }


def main():
    tickers = ["SPY", "QQQ", "AAPL", "NVDA", "TSLA", "META", "AMZN", "GOOGL", "AMD", "MSFT"]
    strategies = [DailyBreakout(), DailyMeanReversion()]

    print("=" * 80)
    print("  USStock 回测系统 — 日线策略")
    print("=" * 80)
    print(f"\n标的: {', '.join(tickers)}")
    print(f"策略: {', '.join(s.name for s in strategies)}")
    print(f"周期: 6个月 日线")
    print(f"初始资金: $200 | 单笔仓位: 45%")
    print(f"\n下载数据...")

    data = download_data(tickers, period="6mo", interval="1d")
    if not data:
        print("无法下载数据")
        return

    print(f"\n运行回测...")
    print("-" * 80)

    all_results = []
    for strategy in strategies:
        for ticker, bars in data.items():
            result = run_backtest(ticker, bars, strategy)
            all_results.append(result)

    print(f"\n{'='*80}")
    print(f"{'策略':<15} {'标的':<8} {'收益%':>8} {'胜率':>6} {'交易':>5} {'盈亏':>8} {'最大回撤':>8}")
    print(f"{'='*80}")

    for r in sorted(all_results, key=lambda x: x["total_return_pct"], reverse=True):
        if r["total_trades"] > 0:
            print(
                f"{r['strategy']:<15} {r['ticker']:<8} "
                f"{r['total_return_pct']:>+7.1f}% "
                f"{r['win_rate']:>5.0f}% "
                f"{r['total_trades']:>4} "
                f"${r['final_cash'] - r['initial_cash']:>+7.0f} "
                f"{r['max_drawdown_pct']:>7.1f}%"
            )

    # Per-strategy summary
    for s in strategies:
        s_results = [r for r in all_results if r["strategy"] == s.name and r["total_trades"] > 0]
        if s_results:
            total_trades = sum(r["total_trades"] for r in s_results)
            total_wins = sum(r["wins"] for r in s_results)
            total_pnl = sum(r["final_cash"] - r["initial_cash"] for r in s_results)
            print(f"\n{s.name}: {total_trades}笔, 胜率{total_wins/total_trades*100:.0f}%, 总盈亏${total_pnl:+.0f}")

    # Detailed trades
    print(f"\n{'='*80}")
    print("详细交易记录:")
    print(f"{'='*80}")
    for r in all_results:
        for t in r.get("trades", []):
            icon = "+" if t["pnl"] > 0 else ""
            print(f"  {t['ticker']:<6} {t['strategy']:<15} ${t['entry_price']:>8.2f} → ${t['exit_price']:>8.2f}  {icon}{t['pnl']:>7.2f} ({t['pnl_pct']:>+.1f}%) [{t['exit_reason']}]")

    import json
    with open("backtest_results.json", "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
