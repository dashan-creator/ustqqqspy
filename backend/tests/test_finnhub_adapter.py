# backend/tests/test_finnhub_adapter.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx

import pytest

from app.news.adapters.finnhub import FinnhubAdapter


@pytest.fixture
def adapter():
    return FinnhubAdapter(api_key="test-key")


@pytest.mark.asyncio
async def test_fetch_ticker_news(adapter):
    mock_response = [
        {
            "headline": "Nvidia beats earnings",
            "summary": "Revenue up 50%",
            "url": "https://example.com/1",
            "datetime": 1714900000,
            "source": "Reuters",
        },
        {
            "headline": "AI chip demand surges",
            "summary": "Data center revenue record",
            "url": "https://example.com/2",
            "datetime": 1714903600,
            "source": "Bloomberg",
        },
    ]

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response,
        )
        mock_get.return_value.raise_for_status = lambda: None
        items = await adapter.fetch_ticker_news("NVDA")

    assert len(items) == 2
    assert items[0].ticker == "NVDA"
    assert items[0].headline == "Nvidia beats earnings"
    assert items[0].source == "finnhub"
    assert items[0].published_at.tzinfo is not None


@pytest.mark.asyncio
async def test_fetch_empty_response(adapter):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: [],
        )
        mock_get.return_value.raise_for_status = lambda: None
        items = await adapter.fetch_ticker_news("INVALID")

    assert items == []


@pytest.mark.asyncio
async def test_fetch_handles_timeout(adapter):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
        items = await adapter.fetch_ticker_news("NVDA")
    assert items == []


@pytest.mark.asyncio
async def test_fetch_handles_http_error(adapter):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AsyncMock()
        mock_get.return_value.raise_for_status = lambda: (_ for _ in ()).throw(httpx.HTTPStatusError("429", request=None, response=None))
        items = await adapter.fetch_ticker_news("NVDA")
    assert items == []
