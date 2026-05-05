# backend/app/news/adapters/polygon.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.news.adapters.base import NewsAdapter
from app.news.models import NewsItem

logger = logging.getLogger(__name__)


class PolygonAdapter(NewsAdapter):
    BASE_URL = "https://api.polygon.io/v2/reference/news"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch_ticker_news(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    self.BASE_URL,
                    params={"ticker": ticker, "limit": limit, "apiKey": self.api_key},
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            items = []
            for entry in results[:limit]:
                ts_str = entry.get("published_utc", "")
                try:
                    published_at = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    published_at = datetime.now(timezone.utc)

                items.append(NewsItem(
                    ticker=ticker,
                    headline=entry.get("title", ""),
                    summary=entry.get("description", ""),
                    source="polygon",
                    url=entry.get("article_url", ""),
                    published_at=published_at,
                ))
            return items
        except Exception as e:
            logger.warning("Polygon fetch failed for %s: %s", ticker, e)
            return []
