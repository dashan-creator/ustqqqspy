from __future__ import annotations

import yfinance as yf
import numpy as np
import pandas as pd

from app.market.indicators import atr, rsi, vwap


class MarketDataService:
    """Fetch market data via yfinance (V0)."""

    def get_bars(self, ticker: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
        """Fetch OHLCV bars."""
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        return df[["open", "high", "low", "close", "volume"]]

    def get_quote(self, ticker: str) -> dict:
        """Get latest quote."""
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
        return {
            "ticker": ticker,
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
        }

    def compute_indicators(self, df: pd.DataFrame) -> dict:
        """Compute RSI, VWAP, ATR."""
        if df.empty or len(df) < 2:
            return {"rsi": 50.0, "vwap": 0.0, "atr": 0.0}

        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        volumes = df["volume"].values.astype(float)

        period = min(14, len(closes) - 1)
        return {
            "rsi": rsi(closes, period=period),
            "vwap": vwap(highs, lows, closes, volumes),
            "atr": atr(highs, lows, closes, period=period),
        }

    def get_market_context(self, benchmark: str = "QQQ") -> dict:
        """Get market-level context."""
        quote = self.get_quote(benchmark)
        return {
            "benchmark": benchmark,
            "price": quote["price"],
            "change_pct": quote["change_pct"],
            "is_bullish": quote["change_pct"] > -0.7,
        }


market_data_service = MarketDataService()
