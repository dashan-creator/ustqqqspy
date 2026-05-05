# backend/tests/test_news_service.py
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.news.models import NewsItem
from app.news.service import NewsService


def _make_item(ticker: str, headline: str, source: str = "test") -> NewsItem:
    return NewsItem(
        ticker=ticker, headline=headline, summary="",
        source=source, url="", published_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_get_news_from_single_adapter():
    adapter = AsyncMock()
    adapter.fetch_ticker_news.return_value = [_make_item("NVDA", "news 1", "finnhub")]
    svc = NewsService(adapters=[adapter], cache_ttl=300)
    items = await svc.get_ticker_news("NVDA")
    assert len(items) == 1
    assert items[0].headline == "news 1"
    adapter.fetch_ticker_news.assert_awaited_once_with("NVDA")


@pytest.mark.asyncio
async def test_get_news_merges_and_deduplicates():
    adapter1 = AsyncMock()
    adapter1.fetch_ticker_news.return_value = [
        _make_item("NVDA", "same headline", "finnhub"),
        _make_item("NVDA", "unique 1", "finnhub"),
    ]
    adapter2 = AsyncMock()
    adapter2.fetch_ticker_news.return_value = [
        _make_item("NVDA", "same headline", "polygon"),
        _make_item("NVDA", "unique 2", "polygon"),
    ]
    svc = NewsService(adapters=[adapter1, adapter2], cache_ttl=300)
    items = await svc.get_ticker_news("NVDA")
    headlines = [i.headline for i in items]
    assert headlines.count("same headline") == 1
    assert "unique 1" in headlines
    assert "unique 2" in headlines


@pytest.mark.asyncio
async def test_get_news_uses_cache():
    adapter = AsyncMock()
    adapter.fetch_ticker_news.return_value = [_make_item("NVDA", "cached", "finnhub")]
    svc = NewsService(adapters=[adapter], cache_ttl=300)
    items1 = await svc.get_ticker_news("NVDA")
    items2 = await svc.get_ticker_news("NVDA")
    assert len(items1) == 1
    assert len(items2) == 1
    adapter.fetch_ticker_news.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_news_adapter_failure_returns_other():
    failing = AsyncMock()
    failing.fetch_ticker_news.side_effect = Exception("timeout")
    working = AsyncMock()
    working.fetch_ticker_news.return_value = [_make_item("NVDA", "ok", "polygon")]
    svc = NewsService(adapters=[failing, working], cache_ttl=300)
    items = await svc.get_ticker_news("NVDA")
    assert len(items) == 1
    assert items[0].source == "polygon"


@pytest.mark.asyncio
async def test_get_news_all_fail_returns_empty():
    failing1 = AsyncMock()
    failing1.fetch_ticker_news.side_effect = Exception("timeout")
    failing2 = AsyncMock()
    failing2.fetch_ticker_news.side_effect = Exception("429")
    svc = NewsService(adapters=[failing1, failing2], cache_ttl=300)
    items = await svc.get_ticker_news("NVDA")
    assert items == []


@pytest.mark.asyncio
async def test_get_news_no_adapters_returns_empty():
    svc = NewsService(adapters=[], cache_ttl=300)
    items = await svc.get_ticker_news("NVDA")
    assert items == []
