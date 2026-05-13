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

SPY/TQQQ walk-forward validation:

```bash
cd backend
python scripts/walk_forward_spy_tqqq_cycle.py --output walk_forward_spy_tqqq_cycle_results.json
```

Latest checked result, using Yahoo daily data from 2011-01-03 to 2026-05-11 with 1 bp fees,
2 bp slippage, and 2% annual cash yield:

| Case | Total Return | CAGR | Max Drawdown | Sharpe |
| --- | ---: | ---: | ---: | ---: |
| SPY/TQQQ allocation | 806.41% | 15.44% | -25.88% | 0.90 |
| Buy-and-hold SPY | 662.73% | 14.15% | -33.72% | 0.86 |
| Buy-and-hold TQQQ | 19968.91% | 41.25% | -81.66% | 0.87 |

The stability gate passes only when the allocation beats buy-and-hold SPY, has lower drawdown
than SPY and TQQQ, Sharpe is at least 0.80, and at least 80% of tested market regimes are profitable.
The report also includes a stricter all-cycle profit gate based on continuous full-run equity slices.
The current default passes that strict gate: the continuous 2022 inflation-bear slice is +8.21%.
This is still a historical backtest and not a future profit guarantee.

Continuous full-run regime slices for the current default:

| Regime | Return | Max Drawdown |
| --- | ---: | ---: |
| 2011-2015 post-GFC bull | 99.57% | -15.88% |
| 2016-2019 late-cycle chop | 76.55% | -25.88% |
| 2020-2021 COVID crash/recovery | 17.81% | -17.62% |
| 2022 inflation bear | 8.21% | -6.55% |
| 2023-present AI/liquidity bull | 95.08% | -19.95% |

Default allocation policy:

| State | Trigger | Allocation intent | Default target |
| --- | --- | --- | --- |
| Risk-on attack | SPY trend is above the 100/200-day filters, TQQQ 210-day momentum is positive, and VIX is controlled | Use TQQQ for upside capture with SPY as ballast | 65% SPY / 35% TQQQ |
| Repair | Long trend is intact, panic is absent, momentum is recovering, and VIX is no higher than 24 | Rebuild exposure without full leverage | 80% SPY / 20% TQQQ |
| Normal defense | Trend is not strong enough for attack, but inflation/panic filters are not active | Stay defensive inside equities | 60% SPY |
| Risk-off | Trend, VIX/VVIX, VIX curve, or drawdown filters show broad stress | Leave equity beta and use defensive diversifiers | 40% UUP / 25% DBC |
| Inflation stress | MOVE is elevated, SPY is below the 200-day filter, and drawdown exceeds the inflation threshold | Defend against rate/inflation shocks | 50% BIL / 25% UUP |

In short: TQQQ is the attack sleeve, SPY is the normal equity defense sleeve, and BIL/UUP plus
UUP/DBC are reserved for regimes where SPY itself has not historically been defensive enough.

Allocation state exposure in the latest full backtest:

| State | Days | Share of Days |
| --- | ---: | ---: |
| Risk-on attack | 2314 | 59.93% |
| Risk-off | 784 | 20.31% |
| Normal defense | 324 | 8.39% |
| Warmup | 210 | 5.44% |
| Repair | 156 | 4.04% |
| Inflation stress | 73 | 1.89% |

Average full-sample target weights were SPY 47.2%, TQQQ 21.8%, UUP 8.6%, DBC 5.1%, and BIL 0.9%,
with 386 allocation-state changes.

Robustness screen: a fast array-based checker perturbs core parameters and execution assumptions.
The latest run passed 16 of 18 cases. Nearby trend, momentum, MOVE, inflation-drawdown, TQQQ-weight,
zero-cash-yield, 5 bp slippage, and 5 bp fee scenarios held up. Failures concentrated in severe
execution friction or delayed execution: 10 bp slippage and one-day execution delay. Treat the stress
script as a fast screen; the official performance and gates come from `backtest_spy_tqqq_cycle.py`.

Walk-forward validation is more conservative. A 250-candidate parameter family is selected using only
prior data for each fold and then tested on the next unseen window. The selector is regularized toward
lower drawdown, higher Sharpe, and the default inflation-defense discipline. The latest run passed 4 of
4 absolute out-of-sample stability folds, including +8.21% in the 2022 inflation-bear fold, but only 1
of 4 relative-to-SPY folds. The full-sample all-cycle pass is therefore a strong historical result, while
future superiority versus SPY remains unproven in every validation window.

Frontend:

```bash
cd frontend
npm install
npm run dev
```
