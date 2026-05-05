# backend/tests/test_polygon_adapter.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx

import pytest

from app.news.adapters.polygon import PolygonAdapter


@pytest.fixture
def adapter():
    return PolygonAdapter(api_key="test-key")


@pytest.mark.asyncio
async def test_fetch_ticker_news(adapter):
    mock_response = {
        "results": [
            {
                "title": "Nvidia Reports Record Revenue",
                "description": "Q1 earnings beat expectations",
                "article_url": "https://example.com/3",
                "published_utc": "2026-05-05T12:00:00Z",
                "publisher": {"name": "MarketWatch"},
            },
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response,
        )
        mock_get.return_value.raise_for_status = lambda: None
        items = await adapter.fetch_ticker_news("NVDA")

    assert len(items) == 1
    assert items[0].ticker == "NVDA"
    assert items[0].headline == "Nvidia Reports Record Revenue"
    assert items[0].source == "polygon"


@pytest.mark.asyncio
async def test_fetch_empty_results(adapter):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"results": []},
        )
        mock_get.return_value.raise_for_status = lambda: None
        items = await adapter.fetch_ticker_news("INVALID")

    assert items == []


@pytest.mark.asyncio
async def test_fetch_handles_timeout(adapter):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
        items = await adapter.fetch_ticker_news("NVDA")
    assert items == []
