from __future__ import annotations

import logging

import pandas as pd

from app.market.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)


class IBKRProvider(MarketDataProvider):
    """IBKR market data provider using ib_insync."""

    name = "ibkr"

    def __init__(self, broker):
        self.broker = broker

    async def get_bars(self, ticker: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
        if not self.broker or not self.broker.is_connected:
            return pd.DataFrame()
        try:
            from ib_insync import Stock
            contract = Stock(ticker, "SMART", "USD")
            import asyncio
            await asyncio.to_thread(self.broker.ib.qualifyContracts, contract)

            # Map interval strings
            bar_size_map = {"1m": "1 min", "5m": "5 mins", "15m": "15 mins", "1h": "1 hour", "1D": "1 day"}
            bar_size = bar_size_map.get(interval, "15 mins")

            duration_map = {"1d": "1 D", "5d": "5 D", "1mo": "1 M", "3mo": "3 M"}
            duration = duration_map.get(period, "5 D")

            bars = await asyncio.to_thread(
                self.broker.ib.reqHistoricalData,
                contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
            )

            if not bars:
                return pd.DataFrame()

            df = pd.DataFrame([{
                "open": bar.open, "high": bar.high,
                "low": bar.low, "close": bar.close,
                "volume": int(bar.volume),
            } for bar in bars])
            return df
        except Exception as e:
            logger.warning("IBKR get_bars failed for %s: %s", ticker, e)
            return pd.DataFrame()

    async def get_quote(self, ticker: str) -> dict:
        if not self.broker or not self.broker.is_connected:
            return {"ticker": ticker, "price": 0, "change_pct": 0, "volume": 0}
        try:
            # Use historical bars for quote (works without real-time subscription)
            bars = await self.get_bars(ticker, interval="1D", period="2d")
            if not bars.empty and len(bars) > 0:
                last = bars.iloc[-1]
                price = float(last["close"])
                # Calculate change from previous day
                change_pct = 0.0
                if len(bars) > 1:
                    prev_close = float(bars.iloc[-2]["close"])
                    if prev_close > 0:
                        change_pct = ((price - prev_close) / prev_close) * 100
                return {"ticker": ticker, "price": price, "change_pct": round(change_pct, 2), "volume": int(last.get("volume", 0))}
            return {"ticker": ticker, "price": 0, "change_pct": 0, "volume": 0}
        except Exception as e:
            logger.warning("IBKR get_quote failed for %s: %s", ticker, e)
            return {"ticker": ticker, "price": 0, "change_pct": 0, "volume": 0}
