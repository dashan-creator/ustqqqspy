#!/usr/bin/env python3
"""Walk-forward style backtest for the SPY/TQQQ cycle strategy.

The report is intentionally conservative: it compares against buy-and-hold
benchmarks, breaks results into known market regimes, and fails the stability
gate unless profitability is broad rather than concentrated in one window.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.market.indicators import atr, rsi, vwap
from app.strategy.spy_tqqq_cycle import SpyTqqqCycleStrategy


REGIMES = [
    ("post_gfc_bull", "2011-01-01", "2015-12-31"),
    ("late_cycle_chop", "2016-01-01", "2019-12-31"),
    ("covid_crash_recovery", "2020-01-01", "2021-12-31"),
    ("inflation_bear", "2022-01-01", "2022-12-31"),
    ("ai_liquidity_bull", "2023-01-01", None),
]


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000.0
    spy_position_pct: float = 55.0
    tqqq_position_pct: float = 35.0
    max_hold_days: int = 25
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    start: str = "2011-01-01"
    end: str | None = None
    sma_fast: int = 100
    sma_slow: int = 200
    recent_high_days: int = 42
    momentum_days: int = 210
    risk_on_momentum_min: float = 0.0
    repair_momentum_min: float = 0.03
    vix_risk_on: float = 24.0
    vix_risk_off: float = 28.0
    repair_vix_max: float = 22.0
    vix_backwardation_ratio: float = 1.0
    vix_backwardation_level: float = 28.0
    vvix_risk_off: float = 115.0
    move_inflation_risk: float = 115.0
    inflation_drawdown_pct: float = 10.0
    inflation_sma: int = 200
    tqqq_weight: float = 0.35
    repair_tqqq_weight: float = 0.20
    repair_spy_weight: float = 0.80
    defensive_spy_weight: float = 0.6
    drawdown_guard_pct: float = 20.0
    cash_yield_pct: float = 2.0
    hedge_symbol: str = "SH"
    hedge_weight: float = 0.0
    risk_off_symbols: str = "UUP,DBC"
    risk_off_weights: str = "0.4,0.25"
    inflation_off_symbols: str = "BIL,UUP"
    inflation_off_weights: str = "0.5,0.25"


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    return df[["open", "high", "low", "close", "volume"]].dropna()


def parse_weight_map(symbols: str, weights: str) -> dict[str, float]:
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    weight_list = [float(w.strip()) for w in weights.split(",") if w.strip()]
    if not symbol_list:
        return {}
    if len(symbol_list) != len(weight_list):
        raise ValueError("risk-off symbols and weights must have the same length")
    total = sum(weight_list)
    if total > 1.0 + 1e-9:
        raise ValueError("risk-off weights cannot exceed 1.0")
    return dict(zip(symbol_list, weight_list))


def strategy_universe(cfg: BacktestConfig) -> list[str]:
    symbols = ["SPY", "TQQQ"]
    if cfg.hedge_symbol:
        symbols.append(cfg.hedge_symbol.upper())
    symbols.extend(parse_weight_map(cfg.risk_off_symbols, cfg.risk_off_weights).keys())
    symbols.extend(parse_weight_map(cfg.inflation_off_symbols, cfg.inflation_off_weights).keys())
    return list(dict.fromkeys(symbols))


def download_history(start: str, end: str | None, extra_tickers: list[str] | None = None) -> dict[str, pd.DataFrame]:
    tickers = ["SPY", "TQQQ", "SH", "^VIX", "^VIX3M", "^VVIX", "^MOVE"]
    tickers.extend(extra_tickers or [])
    tickers = list(dict.fromkeys(tickers))
    cache_dir = Path("data/backtest_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached: dict[str, pd.DataFrame] = {}
    missing_tickers = []
    for ticker in tickers:
        cache_file = cache_dir / f"{ticker.replace('^', '')}_{start}_{end or 'latest'}.csv"
        if cache_file.exists():
            df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date")
            if not df.empty:
                cached[ticker] = df
                continue
        missing_tickers.append(ticker)

    if not missing_tickers:
        return cached

    raw = yf.download(
        missing_tickers,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    data: dict[str, pd.DataFrame] = dict(cached)
    for ticker in missing_tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                df = raw[ticker].copy()
            else:
                df = raw.copy()
            df = _normalize_ohlcv(df)
            if not df.empty:
                df.index = pd.to_datetime(df.index).tz_localize(None)
                df.to_csv(cache_dir / f"{ticker.replace('^', '')}_{start}_{end or 'latest'}.csv", index_label="date")
                data[ticker] = df
        except Exception as exc:
            print(f"WARN: {ticker} download/parse failed: {exc}")
    missing = [ticker for ticker in ["SPY", "TQQQ"] if ticker not in data]
    if missing:
        raise RuntimeError(f"missing required price data: {', '.join(missing)}")
    return data


def compute_indicators(window: pd.DataFrame) -> dict:
    closes = window["close"].values.astype(float)
    highs = window["high"].values.astype(float)
    lows = window["low"].values.astype(float)
    volumes = window["volume"].values.astype(float)
    period = min(14, len(closes) - 1)
    avg_volume = np.mean(volumes[-period:]) if period > 0 else 0
    return {
        "rsi": rsi(closes, period=period),
        "vwap": vwap(highs, lows, closes, volumes),
        "atr": atr(highs, lows, closes, period=period),
        "volume_ratio": float(volumes[-1] / avg_volume) if avg_volume > 0 else 1.0,
    }


def latest_value(data: dict[str, pd.DataFrame], ticker: str, date: pd.Timestamp, default: float) -> float:
    df = data.get(ticker)
    if df is None or df.empty:
        return default
    available = df.loc[df.index <= date]
    if available.empty:
        return default
    value = available["close"].iloc[-1]
    return float(value) if np.isfinite(value) and value > 0 else default


def market_context(data: dict[str, pd.DataFrame], date: pd.Timestamp) -> dict:
    spy = data["SPY"].loc[data["SPY"].index <= date]
    if len(spy) >= 2:
        change_pct = float((spy["close"].iloc[-1] / spy["close"].iloc[-2] - 1) * 100)
        price = float(spy["close"].iloc[-1])
    else:
        change_pct = 0.0
        price = latest_value(data, "SPY", date, 0.0)
    vix = latest_value(data, "^VIX", date, 20.0)
    vix3m = latest_value(data, "^VIX3M", date, 22.0)
    vvix = latest_value(data, "^VVIX", date, 95.0)
    move = latest_value(data, "^MOVE", date, 120.0)
    return {
        "benchmark": "SPY",
        "price": price,
        "change_pct": change_pct,
        "is_bullish": change_pct > -0.7 and vix < 28,
        "vix": vix,
        "vix3m": vix3m,
        "vvix": vvix,
        "move": move,
        "vix_term_structure": "backwardation" if vix3m > 0 and vix / vix3m >= 1 else "contango",
        "fed_event_risk": False,
        "fomc_days_to_event": None,
    }


def mark_to_market(cash: float, positions: dict[str, dict], data: dict[str, pd.DataFrame], date: pd.Timestamp) -> float:
    equity = cash
    for ticker, pos in positions.items():
        price = latest_value(data, ticker, date, pos["entry_price"])
        equity += pos["quantity"] * price
    return float(equity)


def close_position(
    ticker: str,
    pos: dict,
    exit_price: float,
    date: pd.Timestamp,
    reason: str,
    cfg: BacktestConfig,
) -> tuple[float, dict]:
    fill = exit_price * (1 - cfg.slippage_bps / 10_000)
    gross = pos["quantity"] * fill
    fee = gross * cfg.fee_bps / 10_000
    cash_in = gross - fee
    pnl = cash_in - pos["cost"]
    trade = {
        "ticker": ticker,
        "entry_date": pos["entry_date"].date().isoformat(),
        "exit_date": date.date().isoformat(),
        "entry_price": round(pos["entry_price"], 2),
        "exit_price": round(fill, 2),
        "quantity": round(pos["quantity"], 4),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl / pos["cost"] * 100, 2),
        "reason": reason,
        "bars_held": int(pos["bars_held"]),
    }
    return cash_in, trade


def run_backtest(data: dict[str, pd.DataFrame], cfg: BacktestConfig, strategy: SpyTqqqCycleStrategy) -> dict:
    dates = data["SPY"].index.intersection(data["TQQQ"].index)
    dates = dates[dates >= pd.Timestamp(cfg.start)]
    if cfg.end:
        dates = dates[dates <= pd.Timestamp(cfg.end)]

    cash = cfg.initial_cash
    positions: dict[str, dict] = {}
    trades: list[dict] = []
    equity_curve: list[dict] = []

    for date in dates:
        # Exit logic first, using same-day close as a conservative daily proxy.
        for ticker in list(positions):
            pos = positions[ticker]
            price = latest_value(data, ticker, date, pos["entry_price"])
            pos["bars_held"] += 1
            pos["highest_price"] = max(pos["highest_price"], price)
            trailing_stop = pos["highest_price"] - 1.8 * pos["atr"]
            exit_reason = None
            if price <= pos["stop_loss"]:
                exit_reason = "stop_loss"
            elif price >= pos["take_profit"]:
                exit_reason = "take_profit"
            elif price <= trailing_stop and pos["bars_held"] >= 5:
                exit_reason = "trailing_stop"
            elif pos["bars_held"] >= cfg.max_hold_days:
                exit_reason = "max_hold"
            if exit_reason:
                cash_in, trade = close_position(ticker, pos, price, date, exit_reason, cfg)
                cash += cash_in
                trades.append(trade)
                del positions[ticker]

        ctx = market_context(data, date)
        for ticker in ["SPY", "TQQQ"]:
            if ticker in positions:
                continue
            ticker_bars = data[ticker].loc[data[ticker].index <= date]
            if len(ticker_bars) < strategy.min_bars:
                continue
            indicators = compute_indicators(ticker_bars)
            signal = strategy.evaluate(ticker, ticker_bars, indicators, ctx)
            if not signal:
                continue
            pct = cfg.tqqq_position_pct if ticker == "TQQQ" else cfg.spy_position_pct
            entry = float(signal["entry_price"]) * (1 + cfg.slippage_bps / 10_000)
            budget = min(cash, mark_to_market(cash, positions, data, date) * pct / 100)
            qty = math.floor((budget / entry) * 10_000) / 10_000
            cost = qty * entry
            fee = cost * cfg.fee_bps / 10_000
            if qty <= 0 or cost + fee > cash:
                continue
            cash -= cost + fee
            positions[ticker] = {
                "entry_date": date,
                "entry_price": entry,
                "quantity": qty,
                "cost": cost + fee,
                "stop_loss": float(signal["stop_loss"]),
                "take_profit": float(signal["take_profit"]),
                "atr": indicators.get("atr", entry * 0.02),
                "highest_price": entry,
                "bars_held": 0,
                "reason": signal["reason"],
            }

        equity_curve.append({"date": date.date().isoformat(), "equity": mark_to_market(cash, positions, data, date)})

    if dates.empty:
        raise RuntimeError("no overlapping SPY/TQQQ dates for backtest")
    last_date = dates[-1]
    for ticker in list(positions):
        pos = positions[ticker]
        price = latest_value(data, ticker, last_date, pos["entry_price"])
        cash_in, trade = close_position(ticker, pos, price, last_date, "end_of_backtest", cfg)
        cash += cash_in
        trades.append(trade)
        del positions[ticker]

    return summarize(cfg.initial_cash, cash, equity_curve, trades, dates[0], last_date)


def allocation_state(data: dict[str, pd.DataFrame], date: pd.Timestamp, cfg: BacktestConfig) -> tuple[str, dict[str, float]]:
    universe = strategy_universe(cfg)
    zero = {ticker: 0.0 for ticker in universe}
    spy = data["SPY"].loc[data["SPY"].index <= date]
    tqqq = data["TQQQ"].loc[data["TQQQ"].index <= date]
    min_bars = max(cfg.sma_slow, cfg.momentum_days, cfg.recent_high_days, cfg.inflation_sma)
    if len(spy) <= min_bars or len(tqqq) <= cfg.momentum_days:
        return "warmup", zero

    spy_close = spy["close"]
    tqqq_close = tqqq["close"]
    sma_fast = float(spy_close.iloc[-cfg.sma_fast:].mean())
    sma_slow = float(spy_close.iloc[-cfg.sma_slow:].mean())
    price = float(spy_close.iloc[-1])
    tqqq_momentum = float(tqqq_close.iloc[-1] / tqqq_close.iloc[-cfg.momentum_days] - 1)
    inflation_sma = float(spy_close.iloc[-cfg.inflation_sma:].mean())
    recent_high = float(spy_close.iloc[-cfg.recent_high_days:].max())
    recent_drawdown_pct = (price / recent_high - 1) * 100 if recent_high > 0 else 0.0

    ctx = market_context(data, date)
    vix = ctx["vix"]
    vix3m = ctx["vix3m"]
    vvix = ctx["vvix"]
    move = ctx["move"]
    backwardation = vix3m > 0 and vix / vix3m >= cfg.vix_backwardation_ratio
    panic = (
        vix >= cfg.vix_risk_off
        or (backwardation and vix >= cfg.vix_backwardation_level)
        or vvix >= cfg.vvix_risk_off
        or recent_drawdown_pct <= -cfg.drawdown_guard_pct
    )
    long_trend = price > sma_slow
    fast_trend = price > sma_fast
    inflation_stress = (
        move >= cfg.move_inflation_risk
        and recent_drawdown_pct <= -cfg.inflation_drawdown_pct
        and price < inflation_sma
    )
    risk_on = long_trend and fast_trend and tqqq_momentum > cfg.risk_on_momentum_min and vix <= cfg.vix_risk_on and not inflation_stress
    repair = long_trend and not panic and not inflation_stress and tqqq_momentum > cfg.repair_momentum_min and vix <= cfg.repair_vix_max
    hedge_ready = cfg.hedge_symbol in data and len(data[cfg.hedge_symbol].loc[data[cfg.hedge_symbol].index <= date]) > 0
    hedge_weight = cfg.hedge_weight if hedge_ready and (panic or not long_trend) else 0.0
    risk_off_weights = {
        ticker: weight
        for ticker, weight in parse_weight_map(cfg.risk_off_symbols, cfg.risk_off_weights).items()
        if ticker in data and len(data[ticker].loc[data[ticker].index <= date]) > 0
    }
    inflation_off_weights = {
        ticker: weight
        for ticker, weight in parse_weight_map(cfg.inflation_off_symbols, cfg.inflation_off_weights).items()
        if ticker in data and len(data[ticker].loc[data[ticker].index <= date]) > 0
    }

    if inflation_stress:
        weights = dict(zero)
        weights.update(inflation_off_weights)
        return "inflation_stress", weights
    if panic or not long_trend:
        weights = dict(zero)
        weights[cfg.hedge_symbol] = hedge_weight
        weights.update(risk_off_weights)
        return "risk_off", weights
    if risk_on:
        weights = dict(zero)
        weights.update({"SPY": max(0.0, 1.0 - cfg.tqqq_weight), "TQQQ": cfg.tqqq_weight})
        return "risk_on_attack", weights
    if repair:
        weights = dict(zero)
        weights.update({"SPY": cfg.repair_spy_weight, "TQQQ": cfg.repair_tqqq_weight})
        return "repair", weights
    weights = dict(zero)
    weights["SPY"] = cfg.defensive_spy_weight
    return "normal_defense", weights


def target_weights(data: dict[str, pd.DataFrame], date: pd.Timestamp, cfg: BacktestConfig) -> dict[str, float]:
    _, weights = allocation_state(data, date, cfg)
    return weights


def run_allocation_backtest(data: dict[str, pd.DataFrame], cfg: BacktestConfig) -> dict:
    dates = data["SPY"].index.intersection(data["TQQQ"].index)
    dates = dates[dates >= pd.Timestamp(cfg.start)]
    if cfg.end:
        dates = dates[dates <= pd.Timestamp(cfg.end)]
    if dates.empty:
        raise RuntimeError("no overlapping SPY/TQQQ dates for allocation backtest")

    cash = cfg.initial_cash
    shares = {ticker: 0.0 for ticker in strategy_universe(cfg)}
    trades: list[dict] = []
    equity_curve: list[dict] = []
    current_weights = {ticker: 0.0 for ticker in shares}
    state_history: list[dict] = []

    for date in dates:
        cash *= 1 + (cfg.cash_yield_pct / 100) / 252
        value = cash + sum(shares[t] * latest_value(data, t, date, 0.0) for t in shares)
        state, weights = allocation_state(data, date, cfg)
        state_history.append({
            "date": date.date().isoformat(),
            "state": state,
            "weights": {ticker: round(weight, 4) for ticker, weight in weights.items() if abs(weight) > 0.0001},
        })
        weights_changed = any(abs(weights[t] - current_weights[t]) > 0.001 for t in shares)
        is_weekly_rebalance = date.weekday() == 0
        if weights_changed or is_weekly_rebalance:
            for ticker in shares:
                target_value = value * weights[ticker]
                price = latest_value(data, ticker, date, 0.0)
                if price <= 0:
                    continue
                old_qty = shares[ticker]
                old_value = old_qty * price
                delta_value = target_value - old_value
                if abs(delta_value) < value * 0.002:
                    continue
                fill = price * (1 + cfg.slippage_bps / 10_000 if delta_value > 0 else 1 - cfg.slippage_bps / 10_000)
                delta_qty = delta_value / fill
                fee = abs(delta_qty * fill) * cfg.fee_bps / 10_000
                shares[ticker] += delta_qty
                cash -= delta_qty * fill + fee
                trades.append({
                    "date": date.date().isoformat(),
                    "ticker": ticker,
                    "side": "buy" if delta_qty > 0 else "sell",
                    "price": round(fill, 2),
                    "quantity": round(abs(delta_qty), 4),
                    "target_weight": round(weights[ticker], 3),
                    "fee": round(fee, 2),
                })
            current_weights = weights
        value = cash + sum(shares[t] * latest_value(data, t, date, 0.0) for t in shares)
        equity_curve.append({"date": date.date().isoformat(), "equity": float(value)})

    final_cash = equity_curve[-1]["equity"]
    result = summarize(cfg.initial_cash, final_cash, equity_curve, [], dates[0], dates[-1])
    result["rebalance_trades"] = trades
    result["total_rebalances"] = len(trades)
    result["state_history"] = state_history
    result["state_exposure"] = summarize_state_exposure(state_history, strategy_universe(cfg))
    return result


def summarize_state_exposure(state_history: list[dict], universe: list[str]) -> dict:
    if not state_history:
        return {"total_days": 0, "states": [], "average_weights": {}, "state_changes": 0}
    total_days = len(state_history)
    state_counts: dict[str, int] = {}
    weight_sums = {ticker: 0.0 for ticker in universe}
    previous_state = None
    state_changes = 0
    for row in state_history:
        state = row["state"]
        state_counts[state] = state_counts.get(state, 0) + 1
        if previous_state is not None and state != previous_state:
            state_changes += 1
        previous_state = state
        weights = row.get("weights", {})
        for ticker in universe:
            weight_sums[ticker] += float(weights.get(ticker, 0.0))
    states = [
        {"state": state, "days": days, "pct_days": round(days / total_days * 100, 2)}
        for state, days in sorted(state_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    average_weights = {
        ticker: round(total / total_days, 4)
        for ticker, total in weight_sums.items()
        if abs(total) > 0.0001
    }
    return {"total_days": total_days, "states": states, "average_weights": average_weights, "state_changes": state_changes}


def summarize(initial_cash: float, final_cash: float, equity_curve: list[dict], trades: list[dict], start: pd.Timestamp, end: pd.Timestamp) -> dict:
    equity = pd.Series({pd.Timestamp(row["date"]): row["equity"] for row in equity_curve}).sort_index()
    returns = equity.pct_change().dropna()
    years = max((end - start).days / 365.25, 1 / 365.25)
    total_return = final_cash / initial_cash - 1
    cagr = (final_cash / initial_cash) ** (1 / years) - 1
    running_max = equity.cummax()
    drawdown = (equity / running_max - 1).fillna(0)
    sharpe = math.sqrt(252) * returns.mean() / returns.std() if len(returns) > 2 and returns.std() > 0 else 0.0
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    return {
        "start": start.date().isoformat(),
        "end": end.date().isoformat(),
        "initial_cash": round(initial_cash, 2),
        "final_cash": round(final_cash, 2),
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "max_drawdown_pct": round(drawdown.min() * 100, 2),
        "sharpe": round(float(sharpe), 2),
        "total_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
        "avg_trade_pct": round(float(np.mean([t["pnl_pct"] for t in trades])), 2) if trades else 0.0,
        "trades": trades,
        "equity_curve": equity_curve,
    }


def summarize_equity_slice(equity: pd.Series, initial_cash: float, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    window = equity.loc[equity.index >= start]
    window = window.loc[window.index <= end]
    if window.empty:
        raise RuntimeError(f"no equity data between {start.date()} and {end.date()}")
    normalized = window / float(window.iloc[0]) * initial_cash
    curve = [{"date": idx.date().isoformat(), "equity": float(value)} for idx, value in normalized.items()]
    return summarize(initial_cash, float(normalized.iloc[-1]), curve, [], window.index[0], window.index[-1])


def buy_hold(data: dict[str, pd.DataFrame], ticker: str, cfg: BacktestConfig) -> dict:
    df = data[ticker].loc[data[ticker].index >= pd.Timestamp(cfg.start)].copy()
    if cfg.end:
        df = df.loc[df.index <= pd.Timestamp(cfg.end)]
    start_price = float(df["close"].iloc[0])
    shares = cfg.initial_cash / start_price
    equity_curve = [
        {"date": idx.date().isoformat(), "equity": float(shares * row["close"])}
        for idx, row in df.iterrows()
    ]
    return summarize(cfg.initial_cash, float(equity_curve[-1]["equity"]), equity_curve, [], df.index[0], df.index[-1])


def regime_slices(data: dict[str, pd.DataFrame], cfg: BacktestConfig, strategy: SpyTqqqCycleStrategy) -> list[dict]:
    slices = []
    for name, start, end in REGIMES:
        regime_start = max(pd.Timestamp(start), pd.Timestamp(cfg.start)).date().isoformat()
        regime_end = end or cfg.end
        sub_cfg = BacktestConfig(**{**asdict(cfg), "start": regime_start, "end": regime_end})
        try:
            result = run_backtest(data, sub_cfg, strategy)
            result.pop("trades", None)
            result.pop("equity_curve", None)
            result["regime"] = name
            slices.append(result)
        except Exception as exc:
            slices.append({"regime": name, "error": str(exc)})
    return slices


def allocation_regime_slices(data: dict[str, pd.DataFrame], cfg: BacktestConfig) -> list[dict]:
    slices = []
    for name, start, end in REGIMES:
        regime_start = max(pd.Timestamp(start), pd.Timestamp(cfg.start)).date().isoformat()
        regime_end = end or cfg.end
        sub_cfg = BacktestConfig(**{**asdict(cfg), "start": regime_start, "end": regime_end})
        try:
            result = run_allocation_backtest(data, sub_cfg)
            result.pop("rebalance_trades", None)
            result.pop("equity_curve", None)
            result.pop("state_history", None)
            result["regime"] = name
            slices.append(result)
        except Exception as exc:
            slices.append({"regime": name, "error": str(exc)})
    return slices


def continuous_regime_slices(strategy_result: dict, cfg: BacktestConfig) -> list[dict]:
    equity_curve = strategy_result.get("equity_curve") or []
    if not equity_curve:
        return []
    equity = pd.Series({pd.Timestamp(row["date"]): row["equity"] for row in equity_curve}).sort_index()
    slices = []
    for name, start, end in REGIMES:
        regime_start = max(pd.Timestamp(start), equity.index[0])
        regime_end = pd.Timestamp(end) if end else equity.index[-1]
        regime_end = min(regime_end, equity.index[-1])
        try:
            result = summarize_equity_slice(equity, cfg.initial_cash, regime_start, regime_end)
            result.pop("trades", None)
            result.pop("equity_curve", None)
            result["regime"] = name
            slices.append(result)
        except Exception as exc:
            slices.append({"regime": name, "error": str(exc)})
    return slices


def grid_search_allocation(data: dict[str, pd.DataFrame], base_cfg: BacktestConfig, limit: int = 10) -> list[dict]:
    candidates = []
    for sma_slow in [150, 180, 200, 220]:
        for momentum_days in [40, 60, 100, 126]:
            for vix_risk_on in [18.0, 20.0, 22.0, 24.0]:
                for vix_risk_off in [28.0, 32.0, 36.0]:
                    for tqqq_weight in [0.35, 0.50, 0.65, 0.80]:
                        cfg = BacktestConfig(**{
                            **asdict(base_cfg),
                            "sma_slow": sma_slow,
                            "momentum_days": momentum_days,
                            "vix_risk_on": vix_risk_on,
                            "vix_risk_off": vix_risk_off,
                            "tqqq_weight": tqqq_weight,
                        })
                        result = run_allocation_backtest(data, cfg)
                        score = (
                            result["sharpe"] * 50
                            + result["cagr_pct"]
                            - max(0.0, abs(result["max_drawdown_pct"]) - 35) * 2
                        )
                        candidates.append({
                            "score": round(score, 2),
                            "_cfg": cfg,
                            "config": {
                                "sma_slow": sma_slow,
                                "momentum_days": momentum_days,
                                "vix_risk_on": vix_risk_on,
                                "vix_risk_off": vix_risk_off,
                                "tqqq_weight": tqqq_weight,
                            },
                            "result": {k: v for k, v in result.items() if k not in {"equity_curve", "rebalance_trades"}},
                        })
    ranked = sorted(candidates, key=lambda row: row["score"], reverse=True)[: max(limit * 2, 20)]
    verified = []
    for row in ranked:
        cfg = row.pop("_cfg")
        regimes = allocation_regime_slices(data, cfg)
        completed = [r for r in regimes if "error" not in r]
        profitable = sum(1 for r in completed if r["total_return_pct"] > 0)
        row["profitable_regimes"] = profitable
        row["regimes"] = regimes
        row["stability_gate"] = allocation_stability_gate(
            row["result"],
            regimes,
            {k: v for k, v in buy_hold(data, "SPY", cfg).items() if k not in {"trades", "equity_curve"}},
            {k: v for k, v in buy_hold(data, "TQQQ", cfg).items() if k not in {"trades", "equity_curve"}},
        )
        row["score"] = round(row["score"] + profitable * 6 + (20 if row["stability_gate"]["passed"] else 0), 2)
        verified.append(row)
    return sorted(verified, key=lambda row: row["score"], reverse=True)[:limit]


def stability_gate(strategy_result: dict, regimes: list[dict], spy_bh: dict, tqqq_bh: dict) -> dict:
    completed = [r for r in regimes if "error" not in r]
    profitable_regimes = [r for r in completed if r["total_return_pct"] > 0]
    reasons = []
    if strategy_result["total_return_pct"] <= spy_bh["total_return_pct"]:
        reasons.append("strategy did not outperform buy-and-hold SPY")
    if strategy_result["max_drawdown_pct"] <= tqqq_bh["max_drawdown_pct"]:
        reasons.append("strategy drawdown was not better than buy-and-hold TQQQ")
    if strategy_result["sharpe"] < 0.7:
        reasons.append("strategy Sharpe below 0.70")
    if strategy_result["total_trades"] < 20:
        reasons.append("fewer than 20 trades across the full sample")
    if len(profitable_regimes) < max(3, math.ceil(len(completed) * 0.6)):
        reasons.append("not profitable in enough market regimes")
    if strategy_result["profit_factor"] is not None and strategy_result["profit_factor"] < 1.2:
        reasons.append("profit factor below 1.20")
    return {"passed": not reasons, "reasons": reasons}


def allocation_stability_gate(strategy_result: dict, regimes: list[dict], spy_bh: dict, tqqq_bh: dict) -> dict:
    completed = [r for r in regimes if "error" not in r]
    profitable_regimes = [r for r in completed if r["total_return_pct"] > 0]
    reasons = []
    if strategy_result["total_return_pct"] <= spy_bh["total_return_pct"]:
        reasons.append("allocation did not outperform buy-and-hold SPY")
    if strategy_result["max_drawdown_pct"] <= max(spy_bh["max_drawdown_pct"], -35.0):
        reasons.append("allocation drawdown was worse than the SPY/35% drawdown gate")
    if strategy_result["max_drawdown_pct"] <= tqqq_bh["max_drawdown_pct"]:
        reasons.append("allocation drawdown was not better than buy-and-hold TQQQ")
    if strategy_result["sharpe"] < 0.8:
        reasons.append("allocation Sharpe below 0.80")
    if len(profitable_regimes) < max(4, math.ceil(len(completed) * 0.8)):
        reasons.append("allocation not profitable in at least 80% of tested regimes")
    return {"passed": not reasons, "reasons": reasons}


def all_cycle_profit_gate(base_gate: dict, continuous_regimes: list[dict]) -> dict:
    completed = [r for r in continuous_regimes if "error" not in r]
    reasons = list(base_gate["reasons"])
    if not completed:
        reasons.append("continuous regime slices were not available")
    losing = [r for r in completed if r["total_return_pct"] <= 0]
    for regime in losing:
        reasons.append(
            f"continuous {regime['regime']} return was not profitable ({regime['total_return_pct']:.2f}%)"
        )
    return {"passed": not reasons, "reasons": reasons}


def print_summary(report: dict) -> None:
    print("\nSPY/TQQQ Cycle Backtest")
    print("=" * 88)
    for name in ["strategy", "buy_hold_spy", "buy_hold_tqqq"]:
        r = report[name]
        print(
            f"{name:<14} return={r['total_return_pct']:>8.2f}% "
            f"CAGR={r['cagr_pct']:>6.2f}% DD={r['max_drawdown_pct']:>7.2f}% "
            f"Sharpe={r['sharpe']:>5.2f} trades={r['total_trades']:>3} win={r['win_rate_pct']:>5.1f}%"
        )
    print("\nRegimes")
    for r in report["regimes"]:
        if "error" in r:
            print(f"{r['regime']:<22} ERROR {r['error']}")
            continue
        print(
            f"{r['regime']:<22} return={r['total_return_pct']:>8.2f}% "
            f"DD={r['max_drawdown_pct']:>7.2f}% trades={r['total_trades']:>3}"
        )
    if report.get("continuous_regimes"):
        print("\nContinuous full-run regime slices")
        for r in report["continuous_regimes"]:
            if "error" in r:
                print(f"{r['regime']:<22} ERROR {r['error']}")
                continue
            print(
                f"{r['regime']:<22} return={r['total_return_pct']:>8.2f}% "
                f"DD={r['max_drawdown_pct']:>7.2f}%"
            )
    state_exposure = report["strategy"].get("state_exposure")
    if state_exposure:
        print("\nAllocation state exposure")
        for row in state_exposure["states"]:
            print(f"{row['state']:<22} days={row['days']:>4} pct={row['pct_days']:>6.2f}%")
        weights = ", ".join(
            f"{ticker}={weight * 100:.1f}%" for ticker, weight in state_exposure["average_weights"].items()
        )
        print(f"average weights: {weights}")
        print(f"state changes: {state_exposure['state_changes']}")
    gate = report["stability_gate"]
    print("\nStability gate:", "PASS" if gate["passed"] else "FAIL")
    for reason in gate["reasons"]:
        print(f"- {reason}")
    if report.get("all_cycle_profit_gate"):
        strict_gate = report["all_cycle_profit_gate"]
        print("\nAll-cycle profit gate:", "PASS" if strict_gate["passed"] else "FAIL")
        for reason in strict_gate["reasons"]:
            print(f"- {reason}")

    if report.get("top_grid"):
        print("\nTop allocation grid candidates")
        for row in report["top_grid"][:5]:
            r = row["result"]
            print(
                f"score={row['score']:>6.2f} return={r['total_return_pct']:>8.2f}% "
                f"CAGR={r['cagr_pct']:>6.2f}% DD={r['max_drawdown_pct']:>7.2f}% "
                f"Sharpe={r['sharpe']:>5.2f} regimes={row['profitable_regimes']} cfg={row['config']}"
            )


def compact_report(report: dict) -> dict:
    compact = dict(report)
    compact["strategy"] = {
        k: v
        for k, v in report["strategy"].items()
        if k not in {"trades", "equity_curve", "rebalance_trades", "state_history"}
    }
    if "top_grid" in compact:
        compact["top_grid"] = [
            {
                **row,
                "result": {
                    k: v
                    for k, v in row["result"].items()
                    if k not in {"trades", "equity_curve", "rebalance_trades", "state_history"}
                },
            }
            for row in compact["top_grid"]
        ]
    return compact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2011-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--output", default="backtest_spy_tqqq_cycle_results.json")
    parser.add_argument("--spy-position-pct", type=float, default=55.0)
    parser.add_argument("--tqqq-position-pct", type=float, default=35.0)
    parser.add_argument("--max-hold-days", type=int, default=25)
    parser.add_argument("--mode", choices=["signals", "allocation"], default="allocation")
    parser.add_argument("--grid-search", action="store_true")
    parser.add_argument("--sma-fast", type=int, default=BacktestConfig.sma_fast)
    parser.add_argument("--sma-slow", type=int, default=BacktestConfig.sma_slow)
    parser.add_argument("--recent-high-days", type=int, default=BacktestConfig.recent_high_days)
    parser.add_argument("--momentum-days", type=int, default=BacktestConfig.momentum_days)
    parser.add_argument("--risk-on-momentum-min", type=float, default=BacktestConfig.risk_on_momentum_min)
    parser.add_argument("--repair-momentum-min", type=float, default=BacktestConfig.repair_momentum_min)
    parser.add_argument("--vix-risk-on", type=float, default=BacktestConfig.vix_risk_on)
    parser.add_argument("--vix-risk-off", type=float, default=BacktestConfig.vix_risk_off)
    parser.add_argument("--repair-vix-max", type=float, default=BacktestConfig.repair_vix_max)
    parser.add_argument("--vix-backwardation-ratio", type=float, default=BacktestConfig.vix_backwardation_ratio)
    parser.add_argument("--vix-backwardation-level", type=float, default=BacktestConfig.vix_backwardation_level)
    parser.add_argument("--vvix-risk-off", type=float, default=BacktestConfig.vvix_risk_off)
    parser.add_argument("--move-inflation-risk", type=float, default=BacktestConfig.move_inflation_risk)
    parser.add_argument("--inflation-drawdown-pct", type=float, default=BacktestConfig.inflation_drawdown_pct)
    parser.add_argument("--inflation-sma", type=int, default=BacktestConfig.inflation_sma)
    parser.add_argument("--tqqq-weight", type=float, default=BacktestConfig.tqqq_weight)
    parser.add_argument("--repair-tqqq-weight", type=float, default=BacktestConfig.repair_tqqq_weight)
    parser.add_argument("--repair-spy-weight", type=float, default=BacktestConfig.repair_spy_weight)
    parser.add_argument("--defensive-spy-weight", type=float, default=BacktestConfig.defensive_spy_weight)
    parser.add_argument("--drawdown-guard-pct", type=float, default=BacktestConfig.drawdown_guard_pct)
    parser.add_argument("--cash-yield-pct", type=float, default=BacktestConfig.cash_yield_pct)
    parser.add_argument("--hedge-symbol", default=BacktestConfig.hedge_symbol)
    parser.add_argument("--hedge-weight", type=float, default=BacktestConfig.hedge_weight)
    parser.add_argument("--risk-off-symbols", default=BacktestConfig.risk_off_symbols)
    parser.add_argument("--risk-off-weights", default=BacktestConfig.risk_off_weights)
    parser.add_argument("--inflation-off-symbols", default=BacktestConfig.inflation_off_symbols)
    parser.add_argument("--inflation-off-weights", default=BacktestConfig.inflation_off_weights)
    parser.add_argument("--include-equity", action="store_true")
    args = parser.parse_args()

    cfg = BacktestConfig(
        start=args.start,
        end=args.end,
        spy_position_pct=args.spy_position_pct,
        tqqq_position_pct=args.tqqq_position_pct,
        max_hold_days=args.max_hold_days,
        sma_fast=args.sma_fast,
        sma_slow=args.sma_slow,
        recent_high_days=args.recent_high_days,
        momentum_days=args.momentum_days,
        risk_on_momentum_min=args.risk_on_momentum_min,
        repair_momentum_min=args.repair_momentum_min,
        vix_risk_on=args.vix_risk_on,
        vix_risk_off=args.vix_risk_off,
        repair_vix_max=args.repair_vix_max,
        vix_backwardation_ratio=args.vix_backwardation_ratio,
        vix_backwardation_level=args.vix_backwardation_level,
        vvix_risk_off=args.vvix_risk_off,
        move_inflation_risk=args.move_inflation_risk,
        inflation_drawdown_pct=args.inflation_drawdown_pct,
        inflation_sma=args.inflation_sma,
        tqqq_weight=args.tqqq_weight,
        repair_tqqq_weight=args.repair_tqqq_weight,
        repair_spy_weight=args.repair_spy_weight,
        defensive_spy_weight=args.defensive_spy_weight,
        drawdown_guard_pct=args.drawdown_guard_pct,
        cash_yield_pct=args.cash_yield_pct,
        hedge_symbol=args.hedge_symbol,
        hedge_weight=args.hedge_weight,
        risk_off_symbols=args.risk_off_symbols,
        risk_off_weights=args.risk_off_weights,
        inflation_off_symbols=args.inflation_off_symbols,
        inflation_off_weights=args.inflation_off_weights,
    )
    data = download_history(cfg.start, cfg.end, extra_tickers=strategy_universe(cfg))
    strategy = SpyTqqqCycleStrategy()
    if args.mode == "allocation":
        strategy_result = run_allocation_backtest(data, cfg)
    else:
        strategy_result = run_backtest(data, cfg, strategy)
    spy_bh = buy_hold(data, "SPY", cfg)
    tqqq_bh = buy_hold(data, "TQQQ", cfg)
    regimes = allocation_regime_slices(data, cfg) if args.mode == "allocation" else regime_slices(data, cfg, strategy)
    continuous_regimes = continuous_regime_slices(strategy_result, cfg)
    report = {
        "mode": args.mode,
        "config": asdict(cfg),
        "strategy": strategy_result,
        "buy_hold_spy": {k: v for k, v in spy_bh.items() if k not in {"trades", "equity_curve"}},
        "buy_hold_tqqq": {k: v for k, v in tqqq_bh.items() if k not in {"trades", "equity_curve"}},
        "regimes": regimes,
        "continuous_regimes": continuous_regimes,
    }
    if args.mode == "allocation":
        report["stability_gate"] = allocation_stability_gate(report["strategy"], regimes, report["buy_hold_spy"], report["buy_hold_tqqq"])
    else:
        report["stability_gate"] = stability_gate(report["strategy"], regimes, report["buy_hold_spy"], report["buy_hold_tqqq"])
    report["all_cycle_profit_gate"] = all_cycle_profit_gate(report["stability_gate"], continuous_regimes)
    if args.grid_search:
        report["top_grid"] = grid_search_allocation(data, cfg)
    print_summary(report)
    output = Path(args.output)
    output_report = report if args.include_equity else compact_report(report)
    output.write_text(json.dumps(output_report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nWrote {output}")


if __name__ == "__main__":
    main()
