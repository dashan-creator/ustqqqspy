from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from app.market.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)


class YFinanceProvider(MarketDataProvider):
    """Yahoo Finance market data provider via yfinance."""

    name = "yfinance"

    async def get_bars(self, ticker: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            if df.empty:
                return pd.DataFrame()
            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low",
                "Close": "close", "Volume": "volume",
            })
            return df[["open", "high", "low", "close", "volume"]]
        except Exception as e:
            logger.warning("YFinance get_bars failed for %s: %s", ticker, e)
            return pd.DataFrame()

    async def get_quote(self, ticker: str) -> dict:
        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info
            try:
                price = float(getattr(info, "last_price", 0) or 0)
            except (TypeError, ValueError):
                price = 0.0
            try:
                change_pct = float(getattr(info, "regular_market_change_percent", 0) or 0)
            except (TypeError, ValueError):
                change_pct = 0.0
            try:
                volume = int(getattr(info, "last_volume", 0) or 0)
            except (TypeError, ValueError):
                volume = 0
            return {"ticker": ticker, "price": price, "change_pct": change_pct, "volume": volume}
        except Exception as e:
            logger.warning("YFinance get_quote failed for %s: %s", ticker, e)
            return {"ticker": ticker, "price": 0, "change_pct": 0, "volume": 0}
