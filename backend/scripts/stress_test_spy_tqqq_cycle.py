#!/usr/bin/env python3
"""Robustness checks for the SPY/TQQQ allocation backtest.

This script intentionally uses the same cached daily data and the same default
allocation rules as backtest_spy_tqqq_cycle.py, but runs them through a compact
array engine so parameter perturbations and execution-pressure scenarios are
fast enough to run routinely.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_spy_tqqq_cycle import BacktestConfig, REGIMES, parse_weight_map, strategy_universe


REQUIRED_MARKET_SERIES = ["^VIX", "^VIX3M", "^VVIX", "^MOVE"]


def cache_file(ticker: str, start: str, end: str | None) -> Path:
    return Path("data/backtest_cache") / f"{ticker.replace('^', '')}_{start}_{end or 'latest'}.csv"


def load_close(ticker: str, cfg: BacktestConfig) -> pd.Series:
    path = cache_file(ticker, cfg.start, cfg.end)
    if not path.exists():
        raise FileNotFoundError(f"missing cached data for {ticker}: {path}")
    return pd.read_csv(path, parse_dates=["date"], index_col="date")["close"].astype(float)


def load_data(cfg: BacktestConfig) -> tuple[pd.DatetimeIndex, dict[str, np.ndarray]]:
    symbols = list(dict.fromkeys(strategy_universe(cfg) + REQUIRED_MARKET_SERIES))
    closes = {ticker: load_close(ticker, cfg) for ticker in symbols}
    dates = closes["SPY"].index.intersection(closes["TQQQ"].index)
    if cfg.end:
        dates = dates[dates <= pd.Timestamp(cfg.end)]
    dates = dates[dates >= pd.Timestamp(cfg.start)]
    data = {ticker: series.reindex(dates).ffill().bfill().to_numpy(dtype=float) for ticker, series in closes.items()}
    return dates, data


def date_pos(dates: pd.DatetimeIndex, date: str | None, side: str) -> int:
    if date is None:
        return len(dates) - 1
    return int(np.searchsorted(dates.values, np.datetime64(date), side=side))


def summarize_equity(dates: pd.DatetimeIndex, equity: np.ndarray, start_i: int, end_i: int) -> dict:
    window = equity[start_i : end_i + 1]
    returns = np.diff(window) / window[:-1]
    years = max((dates[end_i] - dates[start_i]).days / 365.25, 1 / 365.25)
    total_return = window[-1] / window[0] - 1
    cagr = (window[-1] / window[0]) ** (1 / years) - 1
    drawdown = window / np.maximum.accumulate(window) - 1
    sharpe = math.sqrt(252) * returns.mean() / returns.std(ddof=1) if len(returns) > 2 and returns.std(ddof=1) > 0 else 0.0
    return {
        "start": dates[start_i].date().isoformat(),
        "end": dates[end_i].date().isoformat(),
        "total_return_pct": round(float(total_return * 100), 2),
        "cagr_pct": round(float(cagr * 100), 2),
        "max_drawdown_pct": round(float(drawdown.min() * 100), 2),
        "sharpe": round(float(sharpe), 2),
    }


def run_fast_allocation(
    dates: pd.DatetimeIndex,
    data: dict[str, np.ndarray],
    cfg: BacktestConfig,
    *,
    fee_bps: float | None = None,
    slippage_bps: float | None = None,
    cash_yield_pct: float | None = None,
    execution_delay_days: int = 0,
) -> tuple[np.ndarray, list[dict]]:
    symbols = strategy_universe(cfg)
    prices = np.vstack([data[ticker] for ticker in symbols]).T
    symbol_index = {ticker: idx for idx, ticker in enumerate(symbols)}
    spy = data["SPY"]
    tqqq = data["TQQQ"]
    vix = data["^VIX"]
    vix3m = data["^VIX3M"]
    vvix = data["^VVIX"]
    move = data["^MOVE"]
    weekdays = np.array([date.weekday() for date in dates])

    spy_series = pd.Series(spy)
    tqqq_series = pd.Series(tqqq)
    sma_fast = spy_series.rolling(cfg.sma_fast).mean().to_numpy()
    sma_slow = spy_series.rolling(cfg.sma_slow).mean().to_numpy()
    inflation_sma = spy_series.rolling(cfg.inflation_sma).mean().to_numpy()
    recent_high = spy_series.rolling(cfg.recent_high_days).max().to_numpy()
    tqqq_momentum = (tqqq_series / tqqq_series.shift(cfg.momentum_days) - 1).to_numpy()
    min_bars = max(cfg.sma_slow, cfg.momentum_days, cfg.recent_high_days, cfg.inflation_sma)

    risk_off = parse_weight_map(cfg.risk_off_symbols, cfg.risk_off_weights)
    inflation_off = parse_weight_map(cfg.inflation_off_symbols, cfg.inflation_off_weights)

    fee = (cfg.fee_bps if fee_bps is None else fee_bps) / 10_000
    slippage = (cfg.slippage_bps if slippage_bps is None else slippage_bps) / 10_000
    cash_yield = (cfg.cash_yield_pct if cash_yield_pct is None else cash_yield_pct) / 100

    cash = cfg.initial_cash
    shares = np.zeros(len(symbols), dtype=float)
    current_weights = np.zeros(len(symbols), dtype=float)
    pending_weights: list[np.ndarray] = []
    equity = np.empty(len(dates), dtype=float)
    transitions: list[dict] = []
    current_state = "warmup"

    for i in range(len(dates)):
        cash *= 1 + cash_yield / 252
        price_row = prices[i]
        value = cash + float(shares.dot(price_row))
        weights = np.zeros(len(symbols), dtype=float)
        state = "cash"

        if i >= min_bars:
            price = spy[i]
            recent_drawdown_pct = (price / recent_high[i] - 1) * 100 if recent_high[i] > 0 else 0.0
            backwardation = vix3m[i] > 0 and vix[i] / vix3m[i] >= cfg.vix_backwardation_ratio
            panic = (
                vix[i] >= cfg.vix_risk_off
                or (backwardation and vix[i] >= cfg.vix_backwardation_level)
                or vvix[i] >= cfg.vvix_risk_off
                or recent_drawdown_pct <= -cfg.drawdown_guard_pct
            )
            long_trend = price > sma_slow[i]
            fast_trend = price > sma_fast[i]
            inflation_stress = (
                move[i] >= cfg.move_inflation_risk
                and recent_drawdown_pct <= -cfg.inflation_drawdown_pct
                and price < inflation_sma[i]
            )
            risk_on = (
                long_trend
                and fast_trend
                and tqqq_momentum[i] > cfg.risk_on_momentum_min
                and vix[i] <= cfg.vix_risk_on
                and not inflation_stress
            )
            repair = (
                long_trend
                and not panic
                and not inflation_stress
                and tqqq_momentum[i] > cfg.repair_momentum_min
                and vix[i] <= cfg.repair_vix_max
            )
            if inflation_stress:
                state = "inflation_stress"
                for ticker, weight in inflation_off.items():
                    weights[symbol_index[ticker]] = weight
            elif panic or not long_trend:
                state = "risk_off"
                for ticker, weight in risk_off.items():
                    weights[symbol_index[ticker]] = weight
                if cfg.hedge_weight > 0 and cfg.hedge_symbol in symbol_index:
                    weights[symbol_index[cfg.hedge_symbol]] = cfg.hedge_weight
            elif risk_on:
                state = "risk_on"
                weights[symbol_index["SPY"]] = max(0.0, 1.0 - cfg.tqqq_weight)
                weights[symbol_index["TQQQ"]] = cfg.tqqq_weight
            elif repair:
                state = "repair"
                weights[symbol_index["SPY"]] = cfg.repair_spy_weight
                weights[symbol_index["TQQQ"]] = cfg.repair_tqqq_weight
            else:
                state = "defensive_spy"
                weights[symbol_index["SPY"]] = cfg.defensive_spy_weight

        if state != current_state:
            transitions.append({"date": dates[i].date().isoformat(), "state": state})
            current_state = state

        target_weights = weights
        if execution_delay_days > 0:
            pending_weights.append(weights)
            if len(pending_weights) <= execution_delay_days:
                target_weights = current_weights
            else:
                target_weights = pending_weights.pop(0)

        weights_changed = np.any(np.abs(target_weights - current_weights) > 0.001)
        if weights_changed or weekdays[i] == 0:
            for j in range(len(symbols)):
                target_value = value * target_weights[j]
                delta_value = target_value - shares[j] * price_row[j]
                if abs(delta_value) < value * 0.002:
                    continue
                fill = price_row[j] * (1 + slippage if delta_value > 0 else 1 - slippage)
                delta_qty = delta_value / fill
                cash -= delta_qty * fill + abs(delta_qty * fill) * fee
                shares[j] += delta_qty
            current_weights = target_weights.copy()
        equity[i] = cash + float(shares.dot(price_row))
    return equity, transitions


def evaluate_case(dates: pd.DatetimeIndex, data: dict[str, np.ndarray], cfg: BacktestConfig, **kwargs) -> dict:
    equity, transitions = run_fast_allocation(dates, data, cfg, **kwargs)
    full = summarize_equity(dates, equity, 0, len(dates) - 1)
    regimes = []
    for name, start, end in REGIMES:
        start_i = date_pos(dates, start, "left")
        end_i = len(dates) - 1 if end is None else date_pos(dates, end, "right") - 1
        result = summarize_equity(dates, equity, start_i, end_i)
        result["regime"] = name
        regimes.append(result)
    return {"full": full, "continuous_regimes": regimes, "transitions": transitions[:50], "transition_count": len(transitions)}


def pass_gates(case: dict, spy_benchmark: dict) -> tuple[bool, list[str]]:
    full = case["full"]
    reasons = []
    if full["total_return_pct"] <= spy_benchmark["total_return_pct"]:
        reasons.append("does not beat SPY total return")
    if full["max_drawdown_pct"] <= spy_benchmark["max_drawdown_pct"]:
        reasons.append("drawdown not better than SPY")
    if full["sharpe"] < 0.80:
        reasons.append("Sharpe below 0.80")
    for regime in case["continuous_regimes"]:
        if regime["total_return_pct"] <= 0:
            reasons.append(f"{regime['regime']} not profitable")
    return not reasons, reasons


def benchmark_spy(dates: pd.DatetimeIndex, data: dict[str, np.ndarray], cfg: BacktestConfig) -> dict:
    shares = cfg.initial_cash / data["SPY"][0]
    equity = shares * data["SPY"]
    return summarize_equity(dates, equity, 0, len(dates) - 1)


def build_cases(base_cfg: BacktestConfig) -> list[tuple[str, BacktestConfig, dict]]:
    cases: list[tuple[str, BacktestConfig, dict]] = [("baseline_fast_engine", base_cfg, {})]
    perturbations = {
        "sma_fast_down": {"sma_fast": 80},
        "sma_fast_up": {"sma_fast": 120},
        "sma_slow_down": {"sma_slow": 180},
        "sma_slow_up": {"sma_slow": 220},
        "momentum_down": {"momentum_days": 150},
        "momentum_up": {"momentum_days": 210},
        "move_threshold_down": {"move_inflation_risk": 105.0},
        "move_threshold_up": {"move_inflation_risk": 125.0},
        "inflation_drawdown_down": {"inflation_drawdown_pct": 8.0},
        "inflation_drawdown_up": {"inflation_drawdown_pct": 12.0},
        "tqqq_weight_down": {"tqqq_weight": 0.30},
        "tqqq_weight_up": {"tqqq_weight": 0.40},
    }
    for name, patch in perturbations.items():
        cases.append((name, BacktestConfig(**{**asdict(base_cfg), **patch}), {}))
    pressures = {
        "slippage_5bps": {"slippage_bps": 5.0},
        "slippage_10bps": {"slippage_bps": 10.0},
        "zero_cash_yield": {"cash_yield_pct": 0.0},
        "fee_5bps": {"fee_bps": 5.0},
        "one_day_execution_delay": {"execution_delay_days": 1},
    }
    for name, kwargs in pressures.items():
        cases.append((name, base_cfg, kwargs))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="stress_spy_tqqq_cycle_results.json")
    args = parser.parse_args()

    base_cfg = BacktestConfig()
    dates, data = load_data(base_cfg)
    spy_bh = benchmark_spy(dates, data, base_cfg)
    results = []
    for name, cfg, kwargs in build_cases(base_cfg):
        case = evaluate_case(dates, data, cfg, **kwargs)
        passed, reasons = pass_gates(case, spy_bh)
        results.append({
            "case": name,
            "passed": passed,
            "reasons": reasons,
            "overrides": {k: v for k, v in asdict(cfg).items() if asdict(base_cfg).get(k) != v},
            "execution_overrides": kwargs,
            **case,
        })

    summary = {
        "total_cases": len(results),
        "passed_cases": sum(1 for row in results if row["passed"]),
        "failed_cases": sum(1 for row in results if not row["passed"]),
    }
    report = {
        "description": "Parameter perturbation and execution pressure checks for the SPY/TQQQ allocation.",
        "base_config": asdict(base_cfg),
        "spy_benchmark": spy_bh,
        "summary": summary,
        "cases": results,
    }
    output = Path(args.output)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("SPY/TQQQ Robustness Stress Test")
    print("=" * 72)
    print(f"cases={summary['total_cases']} passed={summary['passed_cases']} failed={summary['failed_cases']}")
    for row in results:
        full = row["full"]
        status = "PASS" if row["passed"] else "FAIL"
        print(
            f"{status:<4} {row['case']:<28} return={full['total_return_pct']:>7.2f}% "
            f"DD={full['max_drawdown_pct']:>7.2f}% Sharpe={full['sharpe']:>4.2f}"
        )
        if row["reasons"]:
            print("     " + "; ".join(row["reasons"]))
    print(f"\nWrote {output}")


if __name__ == "__main__":
    main()
