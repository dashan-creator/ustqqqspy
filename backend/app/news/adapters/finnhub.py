# backend/app/news/adapters/finnhub.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.news.adapters.base import NewsAdapter
from app.news.models import NewsItem

logger = logging.getLogger(__name__)


class FinnhubAdapter(NewsAdapter):
    BASE_URL = "https://finnhub.io/api/v1/company-news"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch_ticker_news(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = datetime.now(timezone.utc).replace(day=datetime.now(timezone.utc).day - 1).strftime("%Y-%m-%d")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    self.BASE_URL,
                    params={"symbol": ticker, "from": yesterday, "to": today, "token": self.api_key},
                )
                resp.raise_for_status()
                data = resp.json()

            items = []
            for entry in data[:limit]:
                ts = entry.get("datetime", 0)
                items.append(NewsItem(
                    ticker=ticker,
                    headline=entry.get("headline", ""),
                    summary=entry.get("summary", ""),
                    source="finnhub",
                    url=entry.get("url", ""),
                    published_at=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
                ))
            return items
        except Exception as e:
            logger.warning("Finnhub fetch failed for %s: %s", ticker, e)
            return []
