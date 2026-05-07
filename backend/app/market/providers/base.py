from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    """Base class for market data providers."""

    name: str = "base"

    @abstractmethod
    async def get_bars(self, ticker: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
        """Fetch OHLCV bars. Returns empty DataFrame on failure."""
        ...

    @abstractmethod
    async def get_quote(self, ticker: str) -> dict:
        """Get latest quote. Returns {ticker, price, change_pct, volume}."""
        ...
