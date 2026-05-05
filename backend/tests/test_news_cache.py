# backend/tests/test_news_cache.py
from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import patch

from app.news.cache import NewsCache
from app.news.models import NewsItem


def _make_item(ticker: str, headline: str) -> NewsItem:
    return NewsItem(
        ticker=ticker, headline=headline, summary="",
        source="test", url="", published_at=datetime.now(timezone.utc),
    )


def test_cache_miss():
    cache = NewsCache(ttl_seconds=300)
    assert cache.get("NVDA") is None


def test_cache_hit():
    cache = NewsCache(ttl_seconds=300)
    items = [_make_item("NVDA", "headline 1")]
    cache.set("NVDA", items)
    result = cache.get("NVDA")
    assert result is not None
    assert len(result) == 1
    assert result[0].headline == "headline 1"


def test_cache_expiry():
    cache = NewsCache(ttl_seconds=1)
    items = [_make_item("NVDA", "headline 1")]
    cache.set("NVDA", items)
    with patch("time.monotonic", return_value=time.monotonic() + 2):
        assert cache.get("NVDA") is None


def test_cache_different_tickers():
    cache = NewsCache(ttl_seconds=300)
    cache.set("NVDA", [_make_item("NVDA", "n1")])
    cache.set("AAPL", [_make_item("AAPL", "n2")])
    assert len(cache.get("NVDA")) == 1
    assert len(cache.get("AAPL")) == 1
    assert cache.get("TSLA") is None
