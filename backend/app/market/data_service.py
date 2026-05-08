from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

from app.market.indicators import atr, rsi, vwap
from app.market.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)


class MarketDataService:
    """Multi-source market data service with automatic failover."""

    def __init__(self):
        self.providers: list[MarketDataProvider] = []
        self._cache: dict[str, tuple[float, pd.DataFrame]] = {}
        self._quote_cache: dict[str, tuple[float, dict]] = {}
        self._cache_ttl = 60  # seconds

    def set_providers(self, providers: list[MarketDataProvider]):
        self.providers = providers
        logger.info("Market data providers: %s", [p.name for p in providers])

    async def get_bars(self, ticker: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
        cache_key = f"{ticker}:{interval}:{period}"
        cached = self._cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < self._cache_ttl:
            return cached[1]

        for provider in self.providers:
            try:
                df = await provider.get_bars(ticker, interval, period)
                if not df.empty and len(df) > 1:
                    self._cache[cache_key] = (time.monotonic(), df)
                    return df
            except Exception as e:
                logger.warning("Provider %s failed for %s: %s", provider.name, ticker, e)

        # Return cached data if available (even expired)
        if cached:
            logger.warning("All providers failed for %s, using stale cache", ticker)
            return cached[1]

        logger.error("No data available for %s from any provider", ticker)
        return pd.DataFrame()

    async def get_quote(self, ticker: str) -> dict:
        cached = self._quote_cache.get(ticker)
        if cached and time.monotonic() - cached[0] < self._cache_ttl:
            return cached[1]

        best_quote: dict = {}
        for provider in self.providers:
            try:
                quote = await provider.get_quote(ticker)
                if quote.get("price", 0) > 0:
                    if not best_quote:
                        best_quote = quote
                    else:
                        # Merge: keep best change_pct if primary has 0
                        if best_quote.get("change_pct", 0) == 0 and quote.get("change_pct", 0) != 0:
                            best_quote["change_pct"] = quote["change_pct"]
            except Exception as e:
                logger.warning("Provider %s quote failed for %s: %s", provider.name, ticker, e)

        if best_quote:
            self._quote_cache[ticker] = (time.monotonic(), best_quote)
            return best_quote

        if cached:
            return cached[1]

        return {"ticker": ticker, "price": 0, "change_pct": 0, "volume": 0}

    def compute_indicators(self, df: pd.DataFrame) -> dict:
        if df.empty or len(df) < 2:
            return {"rsi": 50.0, "vwap": 0.0, "atr": 0.0}

        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        volumes = df["volume"].values.astype(float)

        period = min(14, len(closes) - 1)
        avg_vol = np.mean(volumes[-period:]) if len(volumes) >= period else np.mean(volumes)
        current_vol = float(volumes[-1]) if len(volumes) > 0 else 0
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

        return {
            "rsi": rsi(closes, period=period),
            "vwap": vwap(highs, lows, closes, volumes),
            "atr": atr(highs, lows, closes, period=period),
            "volume_ratio": round(vol_ratio, 2),
        }

    async def get_market_context(self, benchmark: str = "QQQ") -> dict:
        quote = await self.get_quote(benchmark)
        return {
            "benchmark": benchmark,
            "price": quote["price"],
            "change_pct": quote["change_pct"],
            "is_bullish": quote["change_pct"] > -0.7,
        }


market_data_service = MarketDataService()
