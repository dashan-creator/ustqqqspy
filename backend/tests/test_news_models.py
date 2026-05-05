# backend/tests/test_news_models.py
from __future__ import annotations

from datetime import datetime, timezone

from app.news.models import NewsItem


def test_news_item_creation():
    item = NewsItem(
        ticker="NVDA",
        headline="Nvidia beats earnings",
        summary="Revenue up 50%",
        source="finnhub",
        url="https://example.com/1",
        published_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )
    assert item.ticker == "NVDA"
    assert item.source == "finnhub"
    assert item.published_at.tzinfo is not None


def test_news_item_dedup_key():
    item = NewsItem(
        ticker="NVDA",
        headline="Nvidia beats earnings",
        summary="Revenue up 50%",
        source="finnhub",
        url="https://example.com/1",
        published_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )
    key = item.dedup_key
    assert "NVDA" in key
    assert "Nvidia beats earnings" in key
