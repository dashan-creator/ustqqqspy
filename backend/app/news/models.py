# backend/app/news/models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsItem:
    ticker: str
    headline: str
    summary: str
    source: str
    url: str
    published_at: datetime

    @property
    def dedup_key(self) -> str:
        return f"{self.ticker}:{self.headline}"
