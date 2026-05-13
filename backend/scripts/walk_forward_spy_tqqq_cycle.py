#!/usr/bin/env python3
"""Walk-forward validation for the SPY/TQQQ allocation strategy.

The normal backtest answers "how did the chosen default perform over the full
sample?"  This script answers a stricter question: if a small parameter family
is selected using only data available up to a cutoff, how does the selected
configuration behave in the next unseen window?
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_spy_tqqq_cycle import BacktestConfig
from scripts.stress_test_spy_tqqq_cycle import (
    benchmark_spy,
    date_pos,
    evaluate_case,
    load_data,
    run_fast_allocation,
    summarize_equity,
)


FOLDS = [
    {
        "name": "late_cycle_validation",
        "train_start": "2011-01-01",
        "train_end": "2016-12-31",
        "test_start": "2017-01-01",
        "test_end": "2019-12-31",
    },
    {
        "name": "covid_validation",
        "train_start": "2011-01-01",
        "train_end": "2019-12-31",
        "test_start": "2020-01-01",
        "test_end": "2021-12-31",
    },
    {
        "name": "inflation_bear_validation",
        "train_start": "2011-01-01",
        "train_end": "2021-12-31",
        "test_start": "2022-01-01",
        "test_end": "2022-12-31",
    },
    {
        "name": "ai_liquidity_validation",
        "train_start": "2011-01-01",
        "train_end": "2022-12-31",
        "test_start": "2023-01-01",
        "test_end": None,
    },
]


def build_candidate_configs(base_cfg: BacktestConfig, limit: int) -> list[BacktestConfig]:
    base = asdict(base_cfg)
    candidates: list[BacktestConfig] = [base_cfg]
    for sma_fast in [80, 100, 120]:
        for sma_slow in [180, 200, 220]:
            if sma_fast >= sma_slow:
                continue
            for momentum_days in [180, 210, 252]:
                for tqqq_weight in [0.30, 0.35, 0.40]:
                    for move_inflation_risk in [105.0, 115.0, 125.0]:
                        for inflation_drawdown_pct in [8.0, 10.0, 12.0]:
                            cfg = BacktestConfig(**{
                                **base,
                                "sma_fast": sma_fast,
                                "sma_slow": sma_slow,
                                "momentum_days": momentum_days,
                                "tqqq_weight": tqqq_weight,
                                "move_inflation_risk": move_inflation_risk,
                                "inflation_drawdown_pct": inflation_drawdown_pct,
                            })
                            candidates.append(cfg)
                            if len(candidates) >= limit:
                                return candidates
    return candidates


def slice_metrics(dates: pd.DatetimeIndex, equity: np.ndarray, start: str, end: str | None) -> dict:
    start_i = date_pos(dates, start, "left")
    end_i = len(dates) - 1 if end is None else date_pos(dates, end, "right") - 1
    return summarize_equity(dates, equity, start_i, end_i)


def score_train(metrics: dict, spy_metrics: dict) -> float:
    relative_return = metrics["total_return_pct"] - spy_metrics["total_return_pct"]
    drawdown_penalty = max(0.0, abs(metrics["max_drawdown_pct"]) - abs(spy_metrics["max_drawdown_pct"]))
    return metrics["sharpe"] * 100 + relative_return / 4 - drawdown_penalty * 4 + metrics["cagr_pct"]


def pass_absolute_oos(test_metrics: dict) -> tuple[bool, list[str]]:
    reasons = []
    if test_metrics["total_return_pct"] <= 0:
        reasons.append("test return was not positive")
    if test_metrics["max_drawdown_pct"] <= -35.0:
        reasons.append("test drawdown breached -35%")
    if test_metrics["sharpe"] < 0.50:
        reasons.append("test Sharpe below 0.50")
    return not reasons, reasons


def pass_relative_oos(test_metrics: dict, spy_metrics: dict) -> tuple[bool, list[str]]:
    reasons = []
    if test_metrics["total_return_pct"] <= spy_metrics["total_return_pct"]:
        reasons.append("test return did not beat SPY")
    if test_metrics["max_drawdown_pct"] <= spy_metrics["max_drawdown_pct"]:
        reasons.append("test drawdown was not better than SPY")
    return not reasons, reasons


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="walk_forward_spy_tqqq_cycle_results.json")
    parser.add_argument("--candidate-limit", type=int, default=250)
    args = parser.parse_args()

    base_cfg = BacktestConfig()
    dates, data = load_data(base_cfg)
    candidates = build_candidate_configs(base_cfg, args.candidate_limit)
    spy_prices = data["SPY"]
    spy_equity = base_cfg.initial_cash / spy_prices[0] * spy_prices

    folds = []
    for fold in FOLDS:
        train_spy = slice_metrics(dates, spy_equity, fold["train_start"], fold["train_end"])
        test_spy = slice_metrics(dates, spy_equity, fold["test_start"], fold["test_end"])
        ranked = []
        for cfg in candidates:
            equity, _ = run_fast_allocation(dates, data, cfg)
            train = slice_metrics(dates, equity, fold["train_start"], fold["train_end"])
            ranked.append((score_train(train, train_spy), cfg, train, equity))
        ranked.sort(key=lambda row: row[0], reverse=True)
        best_score, best_cfg, train_metrics, best_equity = ranked[0]
        test_metrics = slice_metrics(dates, best_equity, fold["test_start"], fold["test_end"])
        absolute_passed, absolute_reasons = pass_absolute_oos(test_metrics)
        relative_passed, relative_reasons = pass_relative_oos(test_metrics, test_spy)
        folds.append({
            "fold": fold,
            "absolute_passed": absolute_passed,
            "absolute_reasons": absolute_reasons,
            "relative_spy_passed": relative_passed,
            "relative_spy_reasons": relative_reasons,
            "selected_score": round(float(best_score), 2),
            "selected_overrides": {k: v for k, v in asdict(best_cfg).items() if asdict(base_cfg).get(k) != v},
            "train": train_metrics,
            "train_spy": train_spy,
            "test": test_metrics,
            "test_spy": test_spy,
        })

    default_case = evaluate_case(dates, data, base_cfg)
    report = {
        "description": "Walk-forward parameter selection using only prior data for each validation fold.",
        "candidate_count": len(candidates),
        "base_config": asdict(base_cfg),
        "default_full_sample": default_case["full"],
        "summary": {
            "folds": len(folds),
            "absolute_passed_folds": sum(1 for fold in folds if fold["absolute_passed"]),
            "absolute_failed_folds": sum(1 for fold in folds if not fold["absolute_passed"]),
            "relative_spy_passed_folds": sum(1 for fold in folds if fold["relative_spy_passed"]),
            "relative_spy_failed_folds": sum(1 for fold in folds if not fold["relative_spy_passed"]),
        },
        "folds": folds,
    }
    output = Path(args.output)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("SPY/TQQQ Walk-Forward Validation")
    print("=" * 72)
    print(
        f"candidates={len(candidates)} folds={report['summary']['folds']} "
        f"absolute_passed={report['summary']['absolute_passed_folds']} "
        f"relative_spy_passed={report['summary']['relative_spy_passed_folds']}"
    )
    for fold in folds:
        test = fold["test"]
        status = "PASS" if fold["absolute_passed"] else "FAIL"
        rel_status = "SPY+" if fold["relative_spy_passed"] else "SPY-"
        print(
            f"{status:<4} {rel_status:<4} {fold['fold']['name']:<26} "
            f"test_return={test['total_return_pct']:>7.2f}% "
            f"DD={test['max_drawdown_pct']:>7.2f}% Sharpe={test['sharpe']:>4.2f}"
        )
        reasons = fold["absolute_reasons"] + fold["relative_spy_reasons"]
        if reasons:
            print("     " + "; ".join(reasons))
    print(f"\nWrote {output}")


if __name__ == "__main__":
    main()
