# backend/app/news/cache.py
from __future__ import annotations

import time
from dataclasses import dataclass

from app.news.models import NewsItem


@dataclass
class _CacheEntry:
    items: list[NewsItem]
    expires_at: float


class NewsCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, _CacheEntry] = {}

    def get(self, ticker: str) -> list[NewsItem] | None:
        entry = self._store.get(ticker)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[ticker]
            return None
        return entry.items

    def set(self, ticker: str, news: list[NewsItem]) -> None:
        self._store[ticker] = _CacheEntry(
            items=news,
            expires_at=time.monotonic() + self.ttl_seconds,
        )
