# backend/app/news/adapters/base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from app.news.models import NewsItem


class NewsAdapter(ABC):
    @abstractmethod
    async def fetch_ticker_news(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        """Fetch news for a ticker. Returns empty list on error."""
        ...
