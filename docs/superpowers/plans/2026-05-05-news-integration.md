# 新闻数据源集成实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入 Finnhub 和 Polygon 新闻数据源，通过统一接口为 LLM 风险审查员提供实时个股新闻。

**Architecture:** 双适配器模式（Finnhub + Polygon）+ 统一 NewsService 接口 + 内存缓存去重。适配器并行调用，任一失败自动降级。

**Tech Stack:** httpx (async), dataclass, ABC, pytest + unittest.mock

**Design Spec:** `docs/superpowers/specs/2026-05-05-news-integration-design.md`

---

## File Structure

```
backend/app/news/
├── __init__.py              # exports NewsService, news_service singleton
├── models.py                # NewsItem dataclass
├── cache.py                 # NewsCache 内存缓存
├── service.py               # NewsService 统一接口
├── adapters/
│   ├── __init__.py          # exports all adapters
│   ├── base.py              # NewsAdapter ABC
│   ├── finnhub.py           # FinnhubAdapter
│   └── polygon.py           # PolygonAdapter
backend/tests/
├── test_news_models.py
├── test_news_cache.py
├── test_finnhub_adapter.py
├── test_polygon_adapter.py
├── test_news_service.py
```

Modified:
- `backend/app/config.py` — add FINNHUB_API_KEY, POLYGON_API_KEY, NEWS_CACHE_TTL_SECONDS
- `backend/app/pipeline/scanner.py:92-99` — replace hardcoded news_summary with real news
- `.env.example` — add news config vars

---

### Task 1: NewsItem 数据模型

**Files:**
- Create: `backend/app/news/models.py`
- Create: `backend/app/news/__init__.py`
- Test: `backend/tests/test_news_models.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_news_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.news'"

- [ ] **Step 3: Create news package and implement NewsItem**

```python
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
```

```python
# backend/app/news/__init__.py
from app.news.models import NewsItem

__all__ = ["NewsItem"]
```

```python
# backend/app/news/adapters/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_news_models.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/news/ backend/tests/test_news_models.py
git commit -m "feat: NewsItem data model for news integration"
```

---

### Task 2: NewsCache 内存缓存

**Files:**
- Create: `backend/app/news/cache.py`
- Test: `backend/tests/test_news_cache.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_news_cache.py -v`
Expected: FAIL with "cannot import name 'NewsCache'"

- [ ] **Step 3: Implement NewsCache**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_news_cache.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/news/cache.py backend/tests/test_news_cache.py
git commit -m "feat: NewsCache with TTL-based memory cache"
```

---

### Task 3: NewsAdapter 基类 + Finnhub 适配器

**Files:**
- Create: `backend/app/news/adapters/base.py`
- Create: `backend/app/news/adapters/finnhub.py`
- Test: `backend/tests/test_finnhub_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_finnhub_adapter.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

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
    import httpx
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
        items = await adapter.fetch_ticker_news("NVDA")
    assert items == []


@pytest.mark.asyncio
async def test_fetch_handles_http_error(adapter):
    import httpx
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AsyncMock()
        mock_get.return_value.raise_for_status = lambda: (_ for _ in ()).throw(httpx.HTTPStatusError("429", request=None, response=None))
        items = await adapter.fetch_ticker_news("NVDA")
    assert items == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_finnhub_adapter.py -v`
Expected: FAIL with "cannot import name 'FinnhubAdapter'"

- [ ] **Step 3: Implement base adapter and Finnhub adapter**

```python
# backend/app/news/adapters/base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from app.news.models import NewsItem


class NewsAdapter(ABC):
    @abstractmethod
    async def fetch_ticker_news(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        """Fetch news for a ticker. Returns empty list on error."""
        ...
```

```python
# backend/app/news/adapters/finnhub.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.news.adapters.base import NewsAdapter
from app.news.models import NewsItem

logger = logging.getLogger(__name__)


class FinnhubAdapter(NewsAdapter):
    BASE_URL = "https://finnhub.io/api/v1/company-news"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch_ticker_news(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = datetime.now(timezone.utc).replace(day=datetime.now(timezone.utc).day - 1).strftime("%Y-%m-%d")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    self.BASE_URL,
                    params={"symbol": ticker, "from": yesterday, "to": today, "token": self.api_key},
                )
                resp.raise_for_status()
                data = resp.json()

            items = []
            for entry in data[:limit]:
                ts = entry.get("datetime", 0)
                items.append(NewsItem(
                    ticker=ticker,
                    headline=entry.get("headline", ""),
                    summary=entry.get("summary", ""),
                    source="finnhub",
                    url=entry.get("url", ""),
                    published_at=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
                ))
            return items
        except Exception as e:
            logger.warning("Finnhub fetch failed for %s: %s", ticker, e)
            return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_finnhub_adapter.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/news/adapters/ backend/tests/test_finnhub_adapter.py
git commit -m "feat: NewsAdapter base class and Finnhub adapter"
```

---

### Task 4: Polygon 适配器

**Files:**
- Create: `backend/app/news/adapters/polygon.py`
- Test: `backend/tests/test_polygon_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_polygon_adapter.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
    import httpx
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
        items = await adapter.fetch_ticker_news("NVDA")
    assert items == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_polygon_adapter.py -v`
Expected: FAIL with "cannot import name 'PolygonAdapter'"

- [ ] **Step 3: Implement Polygon adapter**

```python
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
                pub = entry.get("publisher", {})
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_polygon_adapter.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/news/adapters/polygon.py backend/tests/test_polygon_adapter.py
git commit -m "feat: Polygon news adapter"
```

---

### Task 5: NewsService 统一接口

**Files:**
- Create: `backend/app/news/service.py`
- Modify: `backend/app/news/__init__.py`
- Test: `backend/tests/test_news_service.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_news_service.py -v`
Expected: FAIL with "cannot import name 'NewsService'"

- [ ] **Step 3: Implement NewsService**

```python
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
```

- [ ] **Step 4: Update `__init__.py` exports**

```python
# backend/app/news/__init__.py
from app.news.models import NewsItem
from app.news.service import NewsService

__all__ = ["NewsItem", "NewsService"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/test_news_service.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/news/service.py backend/app/news/__init__.py backend/tests/test_news_service.py
git commit -m "feat: NewsService with parallel adapters and dedup cache"
```

---

### Task 6: 配置集成

**Files:**
- Modify: `backend/app/config.py:20-22`
- Modify: `.env.example`

- [ ] **Step 1: Add news config to Settings**

在 `backend/app/config.py` 的 `telegram_chat_id` 后添加：

```python
    # News
    finnhub_api_key: str = ""
    polygon_api_key: str = ""
    news_cache_ttl_seconds: int = 300
```

- [ ] **Step 2: Update .env.example**

在 `.env.example` 末尾添加：

```
# News (optional — leave empty to disable)
FINNHUB_API_KEY=
POLYGON_API_KEY=
NEWS_CACHE_TTL_SECONDS=300
```

- [ ] **Step 3: Verify config loads**

Run: `cd /home/du/project/usstock/backend && python3 -c "from app.config import settings; print('finnhub_key:', bool(settings.finnhub_api_key), 'polygon_key:', bool(settings.polygon_api_key))"`
Expected: `finnhub_key: False polygon_key: False`

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py .env.example
git commit -m "feat: add news API key config and .env.example"
```

---

### Task 7: 接入交易管线

**Files:**
- Modify: `backend/app/pipeline/scanner.py:1,9,92-99`

- [ ] **Step 1: Add news service import and init**

在 `scanner.py` 顶部 import 区添加：

```python
from app.news import NewsService
from app.news.adapters.finnhub import FinnhubAdapter
from app.news.adapters.polygon import PolygonAdapter
from app.llm import analyze_news
```

在 `ScannerPipeline.__init__` 中（`self.ibkr_broker = None` 之前）添加：

```python
        # Initialize news service with available adapters
        news_adapters = []
        if settings.finnhub_api_key:
            news_adapters.append(FinnhubAdapter(api_key=settings.finnhub_api_key))
        if settings.polygon_api_key:
            news_adapters.append(PolygonAdapter(api_key=settings.polygon_api_key))
        self.news_service = NewsService(adapters=news_adapters, cache_ttl=settings.news_cache_ttl_seconds)
```

- [ ] **Step 2: Replace hardcoded news_summary**

将 `scanner.py:92-99` 中的：

```python
            llm_result = await review_risk(
                ticker=ticker,
                strategy=signal["strategy_name"],
                entry_price=signal["entry_price"],
                stop_loss=signal["stop_loss"],
                position_pct=settings.max_single_position_pct,
                market_state=f"QQQ {market['change_pct']:+.2f}%",
                news_summary="V0: no news service yet",
            )
```

替换为：

```python
            # Fetch news for this ticker
            news_items = await self.news_service.get_ticker_news(ticker)
            news_summary = "; ".join(n.headline for n in news_items[:5]) or "无相关新闻"

            # Analyze news with LLM (best-effort)
            if news_items:
                try:
                    await analyze_news(
                        ticker=ticker,
                        headline=news_items[0].headline,
                        price_change=f"{market['change_pct']:+.2f}%",
                        market_state=f"QQQ {market['change_pct']:+.2f}%",
                    )
                except Exception:
                    logger.warning("News analysis failed for %s", ticker)

            llm_result = await review_risk(
                ticker=ticker,
                strategy=signal["strategy_name"],
                entry_price=signal["entry_price"],
                stop_loss=signal["stop_loss"],
                position_pct=settings.max_single_position_pct,
                market_state=f"QQQ {market['change_pct']:+.2f}%",
                news_summary=news_summary,
            )
```

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/ -v`
Expected: all existing tests pass (news service degrades gracefully when no API keys configured)

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipeline/scanner.py
git commit -m "feat: integrate news service into trading pipeline"
```

---

### Task 8: 端到端验证

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

Run: `cd /home/du/project/usstock/backend && /home/du/.local/bin/pytest tests/ -v`
Expected: All tests pass (22 existing + new news tests)

- [ ] **Step 2: Verify backend starts**

Run: `cd /home/du/project/usstock/backend && PYTHONPATH=/home/du/project/usstock/backend timeout 5 python3 -c "from app.main import app; print('OK', len(app.routes))" 2>&1 || true`
Expected: `OK <N>` (N > 0)

- [ ] **Step 3: Verify news service degrades without API keys**

Run: `cd /home/du/project/usstock/backend && python3 -c "
import asyncio
from app.news import NewsService
async def test():
    svc = NewsService(adapters=[], cache_ttl=300)
    items = await svc.get_ticker_news('NVDA')
    print('items:', items)
asyncio.run(test())
"`
Expected: `items: []`

- [ ] **Step 4: Push to GitHub**

```bash
git push
```

---

## Self-Review

- [x] **Spec coverage:** All spec sections (models, cache, adapters, service, config, pipeline integration, testing) covered by tasks 1-8.
- [x] **Placeholder scan:** No TBD/TODO. All code is complete.
- [x] **Type consistency:** `NewsItem.dedup_key`, `NewsAdapter.fetch_ticker_news`, `NewsService.get_ticker_news`, `NewsCache.get/set` — signatures consistent across all tasks.
