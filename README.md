# ustqqqspy

`ustqqqspy` is a SPY/TQQQ-focused trading system forked from `dashan-creator/usstock`.
It keeps the original FastAPI + Next.js paper/IBKR trading stack and adds a market-cycle
strategy designed around broad-market ETFs instead of a large single-stock watchlist.

## Core Focus

- Default watchlist: `SPY,TQQQ`
- Benchmark context: `SPY`
- Volatility and fear inputs: `^VIX`, `^VIX3M`, `^VVIX`, `^MOVE`
- Event-risk switches: `FED_EVENT_RISK`, `FOMC_DAYS_TO_EVENT`
- Primary strategy: `spy_tqqq_cycle`

## Strategy Logic

The cycle strategy separates market states into risk-on, transition, risk-off, and panic repair.
It uses TQQQ only when trend, volatility, and event risk are aligned. SPY is used for steadier
trend participation and panic-reversal repair signals.

TQQQ is blocked when volatility is in panic, the VIX curve is stressed, bond volatility is high,
or the system is near a Federal Reserve event. SPY can still participate in confirmed repair
conditions with tighter sizing and ATR-based exits.

This repository does not guarantee profits. The implementation provides deterministic signals,
position sizing hooks, stop-loss/take-profit levels, and tests so the strategy can be backtested
and tuned before any live deployment.

## Important Environment Values

```env
SYMBOLS=SPY,TQQQ
FED_EVENT_RISK=false
FOMC_DAYS_TO_EVENT=
```

Set `FED_EVENT_RISK=true` or `FOMC_DAYS_TO_EVENT=0` around FOMC/rate-decision windows to prevent
new TQQQ entries.

## Development

Backend tests:

```bash
cd backend
pytest
```

SPY/TQQQ stability backtest:

```bash
cd backend
python scripts/backtest_spy_tqqq_cycle.py --mode allocation --output backtest_spy_tqqq_cycle_results.json
```

SPY/TQQQ robustness stress test:

```bash
cd backend
python scripts/stress_test_spy_tqqq_cycle.py --output stress_spy_tqqq_cycle_results.json
```

Latest checked result, using Yahoo daily data from 2011-01-03 to 2026-05-11 with 1 bp fees,
2 bp slippage, and 2% annual cash yield:

| Case | Total Return | CAGR | Max Drawdown | Sharpe |
| --- | ---: | ---: | ---: | ---: |
| SPY/TQQQ allocation | 755.47% | 15.01% | -27.40% | 0.89 |
| Buy-and-hold SPY | 662.73% | 14.15% | -33.72% | 0.86 |
| Buy-and-hold TQQQ | 19968.91% | 41.25% | -81.66% | 0.87 |

The stability gate passes only when the allocation beats buy-and-hold SPY, has lower drawdown
than SPY and TQQQ, Sharpe is at least 0.80, and at least 80% of tested market regimes are profitable.
The report also includes a stricter all-cycle profit gate based on continuous full-run equity slices.
The current default passes that strict gate: the continuous 2022 inflation-bear slice is +6.01%.
This is still a historical backtest and not a future profit guarantee.

Continuous full-run regime slices for the current default:

| Regime | Return | Max Drawdown |
| --- | ---: | ---: |
| 2011-2015 post-GFC bull | 107.01% | -14.57% |
| 2016-2019 late-cycle chop | 59.72% | -27.40% |
| 2020-2021 COVID crash/recovery | 17.81% | -17.62% |
| 2022 inflation bear | 6.01% | -6.55% |
| 2023-present AI/liquidity bull | 100.26% | -17.89% |

The default allocation uses SPY/TQQQ for risk-on participation, UUP/DBC for risk-off exposure,
and BIL/UUP during detected inflation-stress regimes driven by MOVE, trend, and drawdown filters.

Robustness screen: a fast array-based checker perturbs core parameters and execution assumptions.
The latest run passed 12 of 18 cases. Nearby trend, momentum, MOVE, inflation-drawdown, TQQQ-weight,
and zero-cash-yield scenarios mostly held up. Failures concentrated in high execution friction
or delayed execution: 5-10 bp slippage, 5 bp fees, and one-day execution delay. Treat the stress
script as a fast screen; the official performance and gates come from `backtest_spy_tqqq_cycle.py`.

Frontend:

```bash
cd frontend
npm install
npm run dev
```
