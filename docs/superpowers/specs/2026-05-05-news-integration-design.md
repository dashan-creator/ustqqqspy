# 新闻数据源集成设计

> 双适配器 + 统一接口 + 缓存去重，为 LLM 分析员提供实时个股新闻输入。

## 1. 目标

接入 Finnhub 和 Polygon 两个新闻数据源，通过统一接口为现有交易管线的 LLM 风险审查员提供实时个股新闻摘要，替换当前硬编码的占位文本。

## 2. 技术选型

| 组件 | 技术 |
|------|------|
| 主数据源 | Finnhub API（免费 60 calls/min） |
| 备数据源 | Polygon.io API（免费额度有限） |
| HTTP 客户端 | httpx (async) |
| 缓存 | 内存 dict + TTL（V0），Redis（V1+） |
| 去重 | headline + ticker + 时间窗口 |

## 3. 模块结构

```
backend/app/news/
├── __init__.py
├── service.py          # NewsService 统一接口
├── cache.py            # NewsCache 内存缓存
├── models.py           # NewsItem dataclass
├── adapters/
│   ├── __init__.py
│   ├── base.py         # NewsAdapter ABC
│   ├── finnhub.py      # Finnhub 适配器
│   └── polygon.py      # Polygon 适配器
backend/tests/
├── test_news_service.py
├── test_finnhub_adapter.py
├── test_polygon_adapter.py
```

## 4. 数据模型

```python
@dataclass
class NewsItem:
    ticker: str
    headline: str
    summary: str
    source: str              # "finnhub" / "polygon"
    url: str
    published_at: datetime
```

## 5. 统一接口

```python
class NewsAdapter(ABC):
    async def fetch_ticker_news(self, ticker: str, limit: int = 10) -> list[NewsItem]

class NewsService:
    adapters: list[NewsAdapter]
    cache: NewsCache

    async def get_ticker_news(self, ticker: str) -> list[NewsItem]:
        # 1. 查缓存
        # 2. 并行调用所有 adapter
        # 3. 合并去重 (headline + ticker)
        # 4. 写缓存，返回
```

## 6. 适配器实现

### Finnhub 适配器

- API: `https://finnhub.io/api/v1/company-news?symbol={ticker}&from={date}&to={date}`
- 免费额度: 60 calls/min
- 返回字段映射: `headline`, `summary`, `source`, `url`, `datetime`

### Polygon 适配器

- API: `https://api.polygon.io/v2/reference/news?ticker={ticker}`
- 免费额度: 5 calls/min
- 返回字段映射: `title`, `description`, `publisher`, `article_url`, `published_utc`

## 7. 缓存设计

```python
class NewsCache:
    _store: dict[str, CacheEntry]  # key = ticker
    ttl_seconds: int = 300

    def get(self, ticker: str) -> list[NewsItem] | None
    def set(self, ticker: str, news: list[NewsItem])
```

- TTL 默认 5 分钟
- 同一 ticker 在 TTL 内直接返回缓存
- V0 用内存 dict，V1+ 可换 Redis

## 8. 接入交易管线

改动文件: `backend/app/pipeline/scanner.py`

在 `_scan_symbol` 方法中，LLM 审查前插入新闻获取：

```python
# 现有: llm_result = await review_risk(..., news_summary="V0: no news service yet")
# 改为:
news_items = await news_service.get_ticker_news(ticker)
news_summary = "; ".join(n.headline for n in news_items[:5]) or "无相关新闻"
llm_result = await review_risk(..., news_summary=news_summary)
```

同时调用 `news_analyzer.py` 分析新闻，结果存入 `llm_reports` 表。

## 9. 配置

环境变量（`.env`）：

```bash
FINNHUB_API_KEY=         # 可选，有则启用 Finnhub
POLYGON_API_KEY=         # 可选，有则启用 Polygon
NEWS_CACHE_TTL_SECONDS=300
```

两个 key 都为空时，新闻模块完全跳过，LLM 用空新闻继续审查（降级模式）。

## 10. 容错

- 单个 adapter 超时 (10s) 或报错 → 跳过该源，用另一个
- 两个都失败 → 日志记录，返回空列表
- 缓存命中 → 直接返回，不调 API
- API 限流 → adapter 内部 catch httpx 异常，返回空列表

## 11. 测试策略

- 单元测试：mock httpx 响应，验证去重、缓存、合并逻辑
- 不依赖真实 API key
- 测试用例：
  - Finnhub 返回正常数据 → NewsItem 列表正确
  - Polygon 返回正常数据 → NewsItem 列表正确
  - 两个 adapter 并行调用 → 结果合并去重
  - 缓存命中 → 不调 API
  - 单个 adapter 超时 → 降级到另一个
  - 两个都失败 → 返回空列表
