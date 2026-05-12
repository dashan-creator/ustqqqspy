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

Frontend:

```bash
cd frontend
npm install
npm run dev
```
