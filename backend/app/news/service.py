# backend/app/news/service.py
from __future__ import annotations

import asyncio
import logging

from app.news.adapters.base import NewsAdapter
from app.news.cache import NewsCache
from app.news.models import NewsItem

logger = logging.getLogger(__name__)


class NewsService:
    def __init__(self, adapters: list[NewsAdapter], cache_ttl: int = 300):
        self.adapters = adapters
        self.cache = NewsCache(ttl_seconds=cache_ttl)

    async def get_ticker_news(self, ticker: str) -> list[NewsItem]:
        if not self.adapters:
            return []

        cached = self.cache.get(ticker)
        if cached is not None:
            return cached

        tasks = [adapter.fetch_ticker_news(ticker) for adapter in self.adapters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: list[NewsItem] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("News adapter failed: %s", result)
                continue
            all_items.extend(result)

        # Deduplicate by headline
        seen: set[str] = set()
        unique: list[NewsItem] = []
        for item in all_items:
            if item.dedup_key not in seen:
                seen.add(item.dedup_key)
                unique.append(item)

        self.cache.set(ticker, unique)
        return unique
