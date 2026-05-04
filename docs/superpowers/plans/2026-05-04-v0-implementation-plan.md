# US Stock LLM Quant Trading Bot — V0 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 V0 版本——跑通"行情 → 策略 → LLM 分析 → 风控 → 模拟交易 → Telegram 推送 → 前端 Dashboard"完整管线，只记录信号不下单。

**Architecture:** 单体 Monorepo，FastAPI 后端 + Next.js 前端，PostgreSQL 存储，Redis 缓存，APScheduler 驱动扫描周期，OpenAI 兼容 API 对接 LLM。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), APScheduler, yfinance, python-telegram-bot, Next.js 14, Tailwind, Recharts, PostgreSQL, Redis

**Design Spec:** `docs/superpowers/specs/2026-05-04-usstock-trading-system-design.md`

---

## File Structure

```
backend/
├── pyproject.toml
├── .env.example
├── Dockerfile
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 入口 + lifespan
│   ├── config.py                   # pydantic-settings 配置
│   ├── models/
│   │   ├── __init__.py
│   │   ├── db.py                   # async engine + session
│   │   ├── symbol.py               # Symbol model
│   │   ├── bar.py                  # MarketBar model
│   │   ├── signal.py               # Signal model
│   │   ├── order.py                # Order model
│   │   ├── trade.py                # Trade model
│   │   ├── position.py             # Position model
│   │   ├── llm_report.py           # LLMReport model
│   │   ├── risk_event.py           # RiskEvent model
│   │   └── system_log.py           # SystemLog model
│   ├── market/
│   │   ├── __init__.py
│   │   ├── data_service.py         # yfinance 行情获取
│   │   └── indicators.py           # RSI/VWAP/ATR
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── base.py                 # StrategyBase ABC
│   │   ├── breakout.py             # 趋势突破
│   │   └── mean_reversion.py       # 超跌反弹
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py               # OpenAI 兼容客户端
│   │   ├── news_analyzer.py        # 新闻分析员
│   │   ├── risk_reviewer.py        # 风险审查员
│   │   └── trade_reviewer.py       # 交易复盘员
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── hard_rules.py           # 硬规则
│   │   ├── position_manager.py     # 仓位管理
│   │   └── circuit_breaker.py      # 熔断
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── paper_trader.py         # 模拟交易
│   │   └── order_manager.py        # 订单生命周期
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── scanner.py              # 核心扫描管线
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                 # 共享依赖 (db session)
│   │   ├── market.py
│   │   ├── signals.py
│   │   ├── trades.py
│   │   ├── risk.py
│   │   └── system.py
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── market_scanner.py
│   │   └── daily_report.py
│   └── telegram/
│       ├── __init__.py
│       └── bot.py
├── tests/
│   ├── conftest.py
│   ├── test_indicators.py
│   ├── test_breakout.py
│   ├── test_mean_reversion.py
│   ├── test_hard_rules.py
│   ├── test_paper_trader.py
│   └── test_pipeline.py
frontend/
├── package.json
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── Dockerfile
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                # Dashboard
│   │   ├── watchlist/page.tsx
│   │   ├── trades/page.tsx
│   │   ├── strategy/page.tsx
│   │   └── risk/page.tsx
│   ├── components/
│   │   ├── Navbar.tsx
│   │   ├── StatCard.tsx
│   │   ├── PnlChart.tsx
│   │   ├── PositionsTable.tsx
│   │   ├── SignalsTable.tsx
│   │   └── RiskBadge.tsx
│   └── lib/
│       ├── api.ts
│       └── types.ts
docker-compose.yml
.env.example
CLAUDE.md
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/.env.example`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `CLAUDE.md`

- [ ] **Step 1: Create backend pyproject.toml**

```toml
# backend/pyproject.toml
[project]
name = "usstock"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29.0",
    "pydantic-settings>=2.3.0",
    "yfinance>=0.2.38",
    "pandas>=2.2.0",
    "numpy>=1.26.0",
    "openai>=1.30.0",
    "python-telegram-bot>=21.0",
    "apscheduler>=3.10.0",
    "redis>=5.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.4.0",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create config.py**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/usstock"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "not-needed"
    llm_model: str = "default"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Trading
    symbols: str = "SPY,QQQ,AAPL,MSFT,NVDA,TSLA,META,AMZN,GOOGL,AMD"
    scan_interval_minutes: int = 5
    max_daily_loss_pct: float = 0.01
    max_weekly_loss_pct: float = 0.04
    max_concurrent_positions: int = 2
    max_single_position_pct: float = 0.02
    consecutive_loss_limit: int = 3

    # App
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip() for s in self.symbols.split(",")]


settings = Settings()
```

- [ ] **Step 3: Create .env.example**

```bash
# backend/.env.example (copy to .env and fill in)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/usstock
REDIS_URL=redis://localhost:6379/0
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=your-key-here
LLM_MODEL=default
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
SYMBOLS=SPY,QQQ,AAPL,MSFT,NVDA,TSLA,META,AMZN,GOOGL,AMD
```

- [ ] **Step 4: Create docker-compose.yml**

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: usstock
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
      - redis
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  pgdata:
```

- [ ] **Step 5: Create initial CLAUDE.md**

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

US Stock LLM Quant Trading Bot — 量化交易 + LLM 风险增强 + 自动复盘系统。

## Commands

### Backend
```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload          # 启动开发服务器
pytest                                  # 运行全部测试
pytest tests/test_indicators.py -v     # 运行单个测试文件
pytest -k "test_rsi" -v                # 运行匹配的测试
ruff check .                            # Lint
ruff format .                           # Format
```

### Frontend
```bash
cd frontend
npm install
npm run dev                             # 启动开发服务器
npm run build                           # 构建
npm run lint                            # Lint
```

### Docker
```bash
docker compose up -d                    # 启动所有服务
docker compose down                     # 停止
```

## Architecture

单体 Monorepo。后端 FastAPI + SQLAlchemy async，前端 Next.js 14 App Router。

核心管线：Market Data → Strategy Engine → Hard Risk Check → LLM Analysis → Final Decision → Paper Trader → Notification

模块间依赖单向：`api → strategy → market`，`api → risk → execution`，`llm` 作为旁路被调用。

## Key Decisions

- V0: yfinance 获取行情，模拟交易不接 IBKR
- LLM: OpenAI 兼容 API，超时按保守策略处理
- 风控硬规则写死在代码中，不可被 LLM 或配置覆盖
- 所有 LLM 输出存入 llm_reports 表
```

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/__init__.py backend/app/config.py backend/.env.example .env.example docker-compose.yml CLAUDE.md
git commit -m "feat: project scaffolding with config, docker-compose, and CLAUDE.md"
```

---

## Task 2: Database Models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/db.py`
- Create: `backend/app/models/symbol.py`
- Create: `backend/app/models/bar.py`
- Create: `backend/app/models/signal.py`
- Create: `backend/app/models/order.py`
- Create: `backend/app/models/trade.py`
- Create: `backend/app/models/position.py`
- Create: `backend/app/models/llm_report.py`
- Create: `backend/app/models/risk_event.py`
- Create: `backend/app/models/system_log.py`

- [ ] **Step 1: Create db.py (async engine + session)**

```python
# backend/app/models/db.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 2: Create symbol.py**

```python
# backend/app/models/symbol.py
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    sector: Mapped[str] = mapped_column(String(50), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_position_pct: Mapped[float] = mapped_column(Float, default=2.0)
```

- [ ] **Step 3: Create bar.py**

```python
# backend/app/models/bar.py
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class MarketBar(Base):
    __tablename__ = "market_bars"
    __table_args__ = (UniqueConstraint("symbol_id", "timeframe", "bar_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    timeframe: Mapped[str] = mapped_column(String(5))  # 5m, 15m, 1h, 1D
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 4: Create signal.py**

```python
# backend/app/models/signal.py
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    strategy_name: Mapped[str] = mapped_column(String(50))
    direction: Mapped[str] = mapped_column(String(5))  # long, short
    strength: Mapped[float] = mapped_column(Float)  # 0-1
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/approved/rejected/executed/expired
    llm_report_id: Mapped[int | None] = mapped_column(ForeignKey("llm_reports.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

- [ ] **Step 5: Create order.py**

```python
# backend/app/models/order.py
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    side: Mapped[str] = mapped_column(String(4))  # buy, sell
    order_type: Mapped[str] = mapped_column(String(10), default="market")
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    broker_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    filled_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

- [ ] **Step 6: Create trade.py, position.py, llm_report.py, risk_event.py, system_log.py**

```python
# backend/app/models/trade.py
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    strategy_name: Mapped[str] = mapped_column(String(50))
    side: Mapped[str] = mapped_column(String(4))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_reason: Mapped[str] = mapped_column(Text, default="")
    exit_reason: Mapped[str] = mapped_column(Text, default="")
    llm_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    trade_grade: Mapped[str | None] = mapped_column(String(2), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

```python
# backend/app/models/position.py
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), unique=True)
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[float] = mapped_column(Float)
    avg_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float] = mapped_column(Float)
    strategy_name: Mapped[str] = mapped_column(String(50))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

```python
# backend/app/models/llm_report.py
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class LLMReport(Base):
    __tablename__ = "llm_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_type: Mapped[str] = mapped_column(String(30))  # news/risk_review/trade_review
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(10), nullable=True)
    impact_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suggested_action: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

```python
# backend/app/models/risk_event.py
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10))  # warning/critical
    message: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

```python
# backend/app/models/system_log.py
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(10))
    module: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

- [ ] **Step 7: Create models/__init__.py**

```python
# backend/app/models/__init__.py
from app.models.bar import MarketBar
from app.models.db import Base, get_db, init_db
from app.models.llm_report import LLMReport
from app.models.order import Order
from app.models.position import Position
from app.models.risk_event import RiskEvent
from app.models.signal import Signal
from app.models.symbol import Symbol
from app.models.system_log import SystemLog
from app.models.trade import Trade

__all__ = [
    "Base", "get_db", "init_db",
    "Symbol", "MarketBar", "Signal", "Order", "Trade",
    "Position", "LLMReport", "RiskEvent", "SystemLog",
]
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/
git commit -m "feat: SQLAlchemy async models for all database tables"
```

---

## Task 3: Market Data Service & Indicators

**Files:**
- Create: `backend/app/market/__init__.py`
- Create: `backend/app/market/data_service.py`
- Create: `backend/app/market/indicators.py`
- Create: `backend/tests/test_indicators.py`

- [ ] **Step 1: Write indicator tests first**

```python
# backend/tests/test_indicators.py
import numpy as np
import pytest

from app.market.indicators import atr, rsi, vwap


def test_rsi_basic():
    # 14 periods of alternating up/down closes
    closes = np.array([10, 10.5, 10, 10.5, 10, 10.5, 10, 10.5, 10, 10.5, 10, 10.5, 10, 10.5, 10])
    result = rsi(closes, period=14)
    assert isinstance(result, float)
    assert 0 <= result <= 100


def test_rsi_all_up():
    closes = np.array(range(1, 20), dtype=float)
    result = rsi(closes, period=14)
    assert result > 70  # strong uptrend → high RSI


def test_rsi_all_down():
    closes = np.array(range(20, 1, -1), dtype=float)
    result = rsi(closes, period=14)
    assert result < 30  # strong downtrend → low RSI


def test_vwap_basic():
    highs = np.array([105, 106, 107], dtype=float)
    lows = np.array([95, 96, 97], dtype=float)
    closes = np.array([100, 101, 102], dtype=float)
    volumes = np.array([1000, 1500, 2000], dtype=float)
    result = vwap(highs, lows, closes, volumes)
    assert isinstance(result, float)
    # VWAP should be volume-weighted average of typical prices
    tp = (highs + lows + closes) / 3
    expected = np.sum(tp * volumes) / np.sum(volumes)
    assert abs(result - expected) < 0.01


def test_atr_basic():
    highs = np.array([110, 112, 111, 113, 115], dtype=float)
    lows = np.array([100, 101, 102, 103, 104], dtype=float)
    closes = np.array([105, 106, 107, 108, 109], dtype=float)
    result = atr(highs, lows, closes, period=3)
    assert isinstance(result, float)
    assert result > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_indicators.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Implement indicators.py**

```python
# backend/app/market/indicators.py
import numpy as np


def rsi(closes: np.ndarray, period: int = 14) -> float:
    """Relative Strength Index."""
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def vwap(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> float:
    """Volume Weighted Average Price."""
    typical_price = (highs + lows + closes) / 3.0
    cumulative_tp_vol = np.sum(typical_price * volumes)
    cumulative_vol = np.sum(volumes)
    if cumulative_vol == 0:
        return float(closes[-1])
    return float(cumulative_tp_vol / cumulative_vol)


def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Average True Range."""
    if len(closes) < 2:
        return float(highs[-1] - lows[-1])

    prev_closes = closes[:-1]
    tr1 = highs[1:] - lows[1:]
    tr2 = np.abs(highs[1:] - prev_closes)
    tr3 = np.abs(lows[1:] - prev_closes)
    true_range = np.maximum(tr1, np.maximum(tr2, tr3))

    if len(true_range) < period:
        return float(np.mean(true_range))
    return float(np.mean(true_range[-period:]))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_indicators.py -v
```

Expected: 5 passed

- [ ] **Step 5: Implement data_service.py**

```python
# backend/app/market/data_service.py
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from app.market.indicators import atr, rsi, vwap


class MarketDataService:
    """Fetch market data via yfinance (V0)."""

    def get_bars(self, ticker: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
        """Fetch OHLCV bars. Returns DataFrame with columns: open, high, low, close, volume."""
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
        return df[["open", "high", "low", "close", "volume"]]

    def get_quote(self, ticker: str) -> dict:
        """Get latest quote for a ticker."""
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        return {
            "ticker": ticker,
            "price": float(info.get("lastPrice", info.get("last_price", 0))),
            "change_pct": float(info.get("regularMarketChangePercent", 0)),
            "volume": int(info.get("lastVolume", 0)),
            "market_cap": float(info.get("marketCap", 0)),
        }

    def compute_indicators(self, df: pd.DataFrame) -> dict:
        """Compute RSI, VWAP, ATR from a bars DataFrame."""
        if df.empty or len(df) < 2:
            return {"rsi": 50.0, "vwap": 0.0, "atr": 0.0}

        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        volumes = df["volume"].values.astype(float)

        period = min(14, len(closes) - 1)
        return {
            "rsi": rsi(closes, period=period),
            "vwap": vwap(highs, lows, closes, volumes),
            "atr": atr(highs, lows, closes, period=period),
        }

    def get_market_context(self, benchmark: str = "QQQ") -> dict:
        """Get market-level context (QQQ state)."""
        quote = self.get_quote(benchmark)
        return {
            "benchmark": benchmark,
            "price": quote["price"],
            "change_pct": quote["change_pct"],
            "is_bullish": quote["change_pct"] > -0.7,
        }


market_data_service = MarketDataService()
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/market/ backend/tests/test_indicators.py
git commit -m "feat: market data service with yfinance and RSI/VWAP/ATR indicators"
```

---

## Task 4: Strategy Engine

**Files:**
- Create: `backend/app/strategy/__init__.py`
- Create: `backend/app/strategy/base.py`
- Create: `backend/app/strategy/breakout.py`
- Create: `backend/app/strategy/mean_reversion.py`
- Create: `backend/tests/test_breakout.py`
- Create: `backend/tests/test_mean_reversion.py`

- [ ] **Step 1: Write strategy tests**

```python
# backend/tests/test_breakout.py
import numpy as np
import pandas as pd
import pytest

from app.strategy.breakout import BreakoutStrategy


@pytest.fixture
def breakout_data():
    """Create data where price breaks above recent high with volume surge."""
    # 20 bars of consolidation, then breakout
    closes = [100 + i * 0.1 for i in range(20)] + [103, 105]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [1000] * 20 + [2500, 3000]  # volume surge on breakout

    df = pd.DataFrame({
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })
    return df


def test_breakout_generates_signal(breakout_data):
    strategy = BreakoutStrategy()
    indicators = {"rsi": 60.0, "vwap": 101.0, "atr": 1.5}
    market = {"is_bullish": True, "change_pct": 0.5}

    signal = strategy.evaluate("NVDA", breakout_data, indicators, market)

    assert signal is not None
    assert signal["ticker"] == "NVDA"
    assert signal["direction"] == "long"
    assert signal["strategy_name"] == "breakout"
    assert signal["entry_price"] > 0
    assert signal["stop_loss"] < signal["entry_price"]
    assert signal["take_profit"] > signal["entry_price"]


def test_breakout_no_signal_when_market_weak(breakout_data):
    strategy = BreakoutStrategy()
    indicators = {"rsi": 60.0, "vwap": 101.0, "atr": 1.5}
    market = {"is_bullish": False, "change_pct": -1.5}  # QQQ down > 0.7%

    signal = strategy.evaluate("NVDA", breakout_data, indicators, market)
    assert signal is None


def test_breakout_no_signal_low_volume(breakout_data):
    strategy = BreakoutStrategy()
    breakout_data.loc[breakout_data.index[-1], "volume"] = 500  # low volume
    indicators = {"rsi": 60.0, "vwap": 101.0, "atr": 1.5}
    market = {"is_bullish": True, "change_pct": 0.5}

    signal = strategy.evaluate("NVDA", breakout_data, indicators, market)
    assert signal is None
```

```python
# backend/tests/test_mean_reversion.py
import pandas as pd
import pytest

from app.strategy.mean_reversion import MeanReversionStrategy


@pytest.fixture
def oversold_data():
    """Create data with sharp drop and low RSI."""
    closes = [100] * 10 + [97, 94, 91]  # sharp 9% drop
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    volumes = [1000] * 13

    df = pd.DataFrame({
        "open": closes, "high": highs, "low": lows, "close": closes, "volume": volumes,
    })
    return df


def test_mean_reversion_generates_signal(oversold_data):
    strategy = MeanReversionStrategy()
    indicators = {"rsi": 22.0, "vwap": 98.0, "atr": 2.0}
    market = {"is_bullish": True, "change_pct": 0.2}
    news = {"sentiment": "neutral", "has_major_negative": False}

    signal = strategy.evaluate("AAPL", oversold_data, indicators, market, news)

    assert signal is not None
    assert signal["direction"] == "long"
    assert signal["strategy_name"] == "mean_reversion"


def test_mean_reversion_no_signal_with_negative_news(oversold_data):
    strategy = MeanReversionStrategy()
    indicators = {"rsi": 22.0, "vwap": 98.0, "atr": 2.0}
    market = {"is_bullish": True, "change_pct": 0.2}
    news = {"sentiment": "negative", "has_major_negative": True}

    signal = strategy.evaluate("AAPL", oversold_data, indicators, market, news)
    assert signal is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_breakout.py tests/test_mean_reversion.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Implement strategy base class**

```python
# backend/app/strategy/base.py
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class StrategyBase(ABC):
    """Base class for all trading strategies."""

    name: str = "base"

    @abstractmethod
    def evaluate(
        self,
        ticker: str,
        bars: pd.DataFrame,
        indicators: dict,
        market: dict,
        news: dict | None = None,
    ) -> dict | None:
        """
        Evaluate if a trading signal exists.

        Returns signal dict or None:
        {
            "ticker": str,
            "strategy_name": str,
            "direction": "long" | "short",
            "strength": float (0-1),
            "entry_price": float,
            "stop_loss": float,
            "take_profit": float,
            "reason": str,
        }
        """
        ...
```

- [ ] **Step 4: Implement breakout strategy**

```python
# backend/app/strategy/breakout.py
import pandas as pd
import numpy as np

from app.strategy.base import StrategyBase


class BreakoutStrategy(StrategyBase):
    """Trend breakout: price breaks above N-bar high with volume surge."""

    name = "breakout"
    lookback = 20
    volume_ratio = 1.8
    max_market_drop = -0.7

    def evaluate(
        self,
        ticker: str,
        bars: pd.DataFrame,
        indicators: dict,
        market: dict,
        news: dict | None = None,
    ) -> dict | None:
        if len(bars) < self.lookback + 1:
            return None

        # Market must not be in strong decline
        if market.get("change_pct", 0) < self.max_market_drop:
            return None

        closes = bars["close"].values
        highs = bars["high"].values
        volumes = bars["volume"].values

        current_price = closes[-1]
        current_high = highs[-1]

        # Recent N-bar high (excluding current bar)
        recent_high = np.max(highs[-(self.lookback + 1):-1])

        # Breakout condition: current close above recent high
        if current_price <= recent_high:
            return None

        # Volume condition: current volume > N-bar average * ratio
        avg_volume = np.mean(volumes[-(self.lookback + 1):-1])
        if avg_volume == 0 or volumes[-1] < avg_volume * self.volume_ratio:
            return None

        # Price must be above VWAP
        vwap = indicators.get("vwap", 0)
        if vwap > 0 and current_price < vwap:
            return None

        atr_val = indicators.get("atr", current_price * 0.02)
        if atr_val <= 0:
            atr_val = current_price * 0.02

        entry_price = current_price
        stop_loss = entry_price - 1.5 * atr_val
        take_profit = entry_price + 3.0 * atr_val

        # Strength based on volume surge magnitude
        vol_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        strength = min(1.0, vol_ratio / 3.0)

        return {
            "ticker": ticker,
            "strategy_name": self.name,
            "direction": "long",
            "strength": round(strength, 2),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "reason": f"Breakout above {self.lookback}-bar high {recent_high:.2f}, volume {vol_ratio:.1f}x avg",
        }
```

- [ ] **Step 5: Implement mean reversion strategy**

```python
# backend/app/strategy/mean_reversion.py
import numpy as np
import pandas as pd

from app.strategy.base import StrategyBase


class MeanReversionStrategy(StrategyBase):
    """Oversold bounce: RSI < 25, price far below VWAP, no major negative news."""

    name = "mean_reversion"
    rsi_threshold = 25
    vwap_deviation_pct = 0.02  # price must be >2% below VWAP

    def evaluate(
        self,
        ticker: str,
        bars: pd.DataFrame,
        indicators: dict,
        market: dict,
        news: dict | None = None,
    ) -> dict | None:
        if len(bars) < 5:
            return None

        # Reject if major negative news
        if news and news.get("has_major_negative", False):
            return None

        rsi_val = indicators.get("rsi", 50)
        vwap_val = indicators.get("vwap", 0)
        atr_val = indicators.get("atr", 0)
        closes = bars["close"].values
        current_price = closes[-1]

        # RSI must be oversold
        if rsi_val >= self.rsi_threshold:
            return None

        # Price must be meaningfully below VWAP
        if vwap_val <= 0:
            return None
        deviation = (vwap_val - current_price) / vwap_val
        if deviation < self.vwap_deviation_pct:
            return None

        if atr_val <= 0:
            atr_val = current_price * 0.02

        entry_price = current_price
        stop_loss = entry_price - 1.5 * atr_val
        take_profit = vwap_val  # target: revert to VWAP

        strength = min(1.0, (self.rsi_threshold - rsi_val) / self.rsi_threshold)

        return {
            "ticker": ticker,
            "strategy_name": self.name,
            "direction": "long",
            "strength": round(strength, 2),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "reason": f"Oversold bounce: RSI={rsi_val:.0f}, {deviation*100:.1f}% below VWAP",
        }
```

- [ ] **Step 6: Create strategy __init__.py**

```python
# backend/app/strategy/__init__.py
from app.strategy.base import StrategyBase
from app.strategy.breakout import BreakoutStrategy
from app.strategy.mean_reversion import MeanReversionStrategy

STRATEGIES: list[StrategyBase] = [BreakoutStrategy(), MeanReversionStrategy()]

__all__ = ["StrategyBase", "BreakoutStrategy", "MeanReversionStrategy", "STRATEGIES"]
```

- [ ] **Step 7: Run tests**

```bash
cd backend && pytest tests/test_breakout.py tests/test_mean_reversion.py -v
```

Expected: 5 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/strategy/ backend/tests/test_breakout.py backend/tests/test_mean_reversion.py
git commit -m "feat: strategy engine with breakout and mean reversion strategies"
```

---

## Task 5: LLM Module

**Files:**
- Create: `backend/app/llm/__init__.py`
- Create: `backend/app/llm/client.py`
- Create: `backend/app/llm/news_analyzer.py`
- Create: `backend/app/llm/risk_reviewer.py`
- Create: `backend/app/llm/trade_reviewer.py`

- [ ] **Step 1: Create LLM client**

```python
# backend/app/llm/client.py
import json
import time
import logging
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)


async def chat(system_prompt: str, user_prompt: str, timeout: float = 30.0) -> dict:
    """Call LLM and parse JSON response. Returns parsed dict or error dict."""
    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            timeout=timeout,
        )
        content = response.choices[0].message.content
        latency_ms = int((time.monotonic() - start) * 1000)

        # Try parsing as JSON
        try:
            result = json.loads(content)
            result["_latency_ms"] = latency_ms
            result["_model"] = settings.llm_model
            return result
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            if "```" in content:
                json_str = content.split("```")[1].strip()
                if json_str.startswith("json"):
                    json_str = json_str[4:].strip()
                result = json.loads(json_str)
                result["_latency_ms"] = latency_ms
                result["_model"] = settings.llm_model
                return result
            logger.warning("LLM returned non-JSON: %s", content[:200])
            return {"error": "invalid_json", "raw": content[:500], "_latency_ms": latency_ms}

    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error("LLM call failed: %s", e)
        return {"error": str(e), "_latency_ms": latency_ms}
```

- [ ] **Step 2: Create news_analyzer.py**

```python
# backend/app/llm/news_analyzer.py
from app.llm.client import chat

SYSTEM_PROMPT = """你是一个美股新闻分析员。分析给定的新闻和市场数据，输出 JSON。
输出格式（严格JSON）:
{
    "event_type": "guidance_raise|earnings_beat|upgrade|downgrade|product_launch|regulatory|other",
    "sentiment": "positive|negative|neutral",
    "impact_score": 1-5,
    "risk_flags": ["..."],
    "trade_permission": "watch_only|trade_ok|avoid",
    "summary": "一句话中文总结"
}"""


async def analyze_news(ticker: str, headline: str, price_change: str, market_state: str) -> dict:
    user_prompt = f"""股票: {ticker}
新闻: {headline}
价格变动: {price_change}
大盘: {market_state}"""

    return await chat(SYSTEM_PROMPT, user_prompt, timeout=15.0)
```

- [ ] **Step 3: Create risk_reviewer.py**

```python
# backend/app/llm/risk_reviewer.py
from app.llm.client import chat

SYSTEM_PROMPT = """你是一个美股交易风险审查员。评估交易信号的风险。
LLM 只能建议降仓或拒绝，不能建议加仓突破上限。
输出格式（严格JSON）:
{
    "risk_score": 1-10,
    "action": "approve|reduce_size|reject",
    "suggested_position_pct": 0-2,
    "reason": "中文说明",
    "risk_flags": ["..."]
}"""


async def review_risk(
    ticker: str,
    strategy: str,
    entry_price: float,
    stop_loss: float,
    position_pct: float,
    market_state: str,
    news_summary: str,
) -> dict:
    user_prompt = f"""交易信号:
- 股票: {ticker}
- 策略: {strategy}
- 入场价: {entry_price}
- 止损: {stop_loss}
- 仓位: {position_pct}%
- 大盘: {market_state}
- 新闻: {news_summary}"""

    return await chat(SYSTEM_PROMPT, user_prompt, timeout=30.0)
```

- [ ] **Step 4: Create trade_reviewer.py**

```python
# backend/app/llm/trade_reviewer.py
from app.llm.client import chat

SYSTEM_PROMPT = """你是一个交易复盘员。分析已完成的交易，给出评级和改进建议。
输出格式（严格JSON）:
{
    "trade_grade": "A|B|C|D|F",
    "what_worked": "中文",
    "what_failed": "中文",
    "mistake": "中文",
    "suggestion": "中文"
}"""


async def review_trade(
    ticker: str,
    strategy: str,
    entry_price: float,
    exit_price: float,
    pnl_pct: float,
    entry_reason: str,
    exit_reason: str,
) -> dict:
    user_prompt = f"""交易记录:
- 股票: {ticker}
- 策略: {strategy}
- 入场价: {entry_price}
- 出场价: {exit_price}
- 盈亏: {pnl_pct:.2f}%
- 入场理由: {entry_reason}
- 出场理由: {exit_reason}"""

    return await chat(SYSTEM_PROMPT, user_prompt, timeout=30.0)
```

- [ ] **Step 5: Create llm __init__.py**

```python
# backend/app/llm/__init__.py
from app.llm.news_analyzer import analyze_news
from app.llm.risk_reviewer import review_risk
from app.llm.trade_reviewer import review_trade

__all__ = ["analyze_news", "review_risk", "review_trade"]
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm/
git commit -m "feat: LLM module with news analyzer, risk reviewer, and trade reviewer"
```

---

## Task 6: Risk Engine

**Files:**
- Create: `backend/app/risk/__init__.py`
- Create: `backend/app/risk/hard_rules.py`
- Create: `backend/app/risk/position_manager.py`
- Create: `backend/app/risk/circuit_breaker.py`
- Create: `backend/tests/test_hard_rules.py`

- [ ] **Step 1: Write hard rules tests**

```python
# backend/tests/test_hard_rules.py
import pytest

from app.risk.hard_rules import HardRiskChecker, RiskCheckResult


@pytest.fixture
def checker():
    return HardRiskChecker(
        max_daily_loss_pct=0.01,
        max_weekly_loss_pct=0.04,
        max_concurrent_positions=2,
        max_single_position_pct=0.02,
        consecutive_loss_limit=3,
    )


def test_approve_normal_trade(checker):
    result = checker.check(
        position_pct=2.0,
        current_positions=0,
        daily_pnl_pct=0.0,
        weekly_pnl_pct=0.0,
        consecutive_losses=0,
        daily_volume_usd=10_000_000,
        spread_pct=0.001,
    )
    assert result.approved is True


def test_reject_position_too_large(checker):
    result = checker.check(
        position_pct=5.0,  # > 2%
        current_positions=0,
        daily_pnl_pct=0.0,
        weekly_pnl_pct=0.0,
        consecutive_losses=0,
        daily_volume_usd=10_000_000,
        spread_pct=0.001,
    )
    assert result.approved is False
    assert "position" in result.reason.lower() or "仓位" in result.reason


def test_reject_too_many_positions(checker):
    result = checker.check(
        position_pct=2.0,
        current_positions=2,  # already at max
        daily_pnl_pct=0.0,
        weekly_pnl_pct=0.0,
        consecutive_losses=0,
        daily_volume_usd=10_000_000,
        spread_pct=0.001,
    )
    assert result.approved is False


def test_reject_daily_loss_limit(checker):
    result = checker.check(
        position_pct=2.0,
        current_positions=0,
        daily_pnl_pct=-0.012,  # > 1% loss
        weekly_pnl_pct=-0.02,
        consecutive_losses=0,
        daily_volume_usd=10_000_000,
        spread_pct=0.001,
    )
    assert result.approved is False


def test_reject_consecutive_losses(checker):
    result = checker.check(
        position_pct=2.0,
        current_positions=0,
        daily_pnl_pct=-0.005,
        weekly_pnl_pct=-0.02,
        consecutive_losses=3,  # hit limit
        daily_volume_usd=10_000_000,
        spread_pct=0.001,
    )
    assert result.approved is False


def test_reject_low_volume(checker):
    result = checker.check(
        position_pct=2.0,
        current_positions=0,
        daily_pnl_pct=0.0,
        weekly_pnl_pct=0.0,
        consecutive_losses=0,
        daily_volume_usd=1_000_000,  # < 5M
        spread_pct=0.001,
    )
    assert result.approved is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_hard_rules.py -v
```

- [ ] **Step 3: Implement hard_rules.py**

```python
# backend/app/risk/hard_rules.py
from dataclasses import dataclass


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str = ""
    suggested_position_pct: float | None = None


class HardRiskChecker:
    """Hard risk rules. Cannot be overridden by LLM or config."""

    def __init__(
        self,
        max_daily_loss_pct: float = 0.01,
        max_weekly_loss_pct: float = 0.04,
        max_concurrent_positions: int = 2,
        max_single_position_pct: float = 0.02,
        consecutive_loss_limit: int = 3,
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_weekly_loss_pct = max_weekly_loss_pct
        self.max_concurrent_positions = max_concurrent_positions
        self.max_single_position_pct = max_single_position_pct
        self.consecutive_loss_limit = consecutive_loss_limit
        self.min_volume_usd = 5_000_000
        self.max_spread_pct = 0.005

    def check(
        self,
        position_pct: float,
        current_positions: int,
        daily_pnl_pct: float,
        weekly_pnl_pct: float,
        consecutive_losses: int,
        daily_volume_usd: float,
        spread_pct: float = 0.0,
    ) -> RiskCheckResult:
        # Position size
        if position_pct > self.max_single_position_pct:
            return RiskCheckResult(
                False,
                f"仓位 {position_pct}% 超过上限 {self.max_single_position_pct}%",
                self.max_single_position_pct,
            )

        # Concurrent positions
        if current_positions >= self.max_concurrent_positions:
            return RiskCheckResult(False, f"持仓数 {current_positions} 已达上限 {self.max_concurrent_positions}")

        # Daily loss
        if daily_pnl_pct <= -self.max_daily_loss_pct:
            return RiskCheckResult(False, f"当日亏损 {daily_pnl_pct*100:.2f}% 达到上限 {self.max_daily_loss_pct*100}%")

        # Weekly loss
        if weekly_pnl_pct <= -self.max_weekly_loss_pct:
            return RiskCheckResult(False, f"本周亏损 {weekly_pnl_pct*100:.2f}% 达到上限 {self.max_weekly_loss_pct*100}%")

        # Consecutive losses
        if consecutive_losses >= self.consecutive_loss_limit:
            return RiskCheckResult(False, f"连续亏损 {consecutive_losses} 笔，达到上限 {self.consecutive_loss_limit}")

        # Volume
        if daily_volume_usd < self.min_volume_usd:
            return RiskCheckResult(False, f"日成交额 ${daily_volume_usd:,.0f} 低于最低要求 ${self.min_volume_usd:,.0f}")

        # Spread
        if spread_pct > self.max_spread_pct:
            return RiskCheckResult(False, f"点差 {spread_pct*100:.2f}% 超过上限 {self.max_spread_pct*100}%")

        return RiskCheckResult(True, "风控通过")
```

- [ ] **Step 4: Implement circuit_breaker.py**

```python
# backend/app/risk/circuit_breaker.py
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Trading circuit breaker — force pause when risk limits are hit."""

    def __init__(self):
        self._paused = False
        self._pause_reason = ""
        self._paused_at: datetime | None = None

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def pause_reason(self) -> str:
        return self._pause_reason

    def pause(self, reason: str):
        self._paused = True
        self._pause_reason = reason
        self._paused_at = datetime.now(timezone.utc)
        logger.warning("CIRCUIT BREAKER TRIGGERED: %s", reason)

    def resume(self):
        logger.info("Circuit breaker resumed")
        self._paused = False
        self._pause_reason = ""
        self._paused_at = None

    def check_trading_allowed(self) -> tuple[bool, str]:
        if self._paused:
            return False, f"交易已暂停: {self._pause_reason}"
        return True, ""
```

- [ ] **Step 5: Implement position_manager.py**

```python
# backend/app/risk/position_manager.py
import logging

logger = logging.getLogger(__name__)


class PositionManager:
    """Track and manage position sizing."""

    def __init__(self, max_position_pct: float = 2.0, account_value: float = 100_000.0):
        self.max_position_pct = max_position_pct
        self.account_value = account_value

    def calculate_quantity(self, price: float, position_pct: float) -> float:
        """Calculate number of shares for a given position percentage."""
        capped_pct = min(position_pct, self.max_position_pct)
        position_value = self.account_value * (capped_pct / 100.0)
        return int(position_value / price)

    def check_stop_loss(self, current_price: float, stop_loss: float) -> bool:
        """Check if stop loss is triggered."""
        return current_price <= stop_loss

    def check_take_profit(self, current_price: float, take_profit: float) -> bool:
        """Check if take profit is triggered."""
        return current_price >= take_profit

    def trailing_stop(self, current_price: float, highest_price: float, atr: float) -> float:
        """Calculate trailing stop price (highest - 1x ATR)."""
        return highest_price - atr
```

- [ ] **Step 6: Create risk __init__.py**

```python
# backend/app/risk/__init__.py
from app.risk.circuit_breaker import CircuitBreaker
from app.risk.hard_rules import HardRiskChecker, RiskCheckResult
from app.risk.position_manager import PositionManager

__all__ = ["HardRiskChecker", "RiskCheckResult", "CircuitBreaker", "PositionManager"]
```

- [ ] **Step 7: Run tests**

```bash
cd backend && pytest tests/test_hard_rules.py -v
```

Expected: 6 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/risk/ backend/tests/test_hard_rules.py
git commit -m "feat: risk engine with hard rules, position manager, and circuit breaker"
```

---

## Task 7: Execution Engine (Paper Trader)

**Files:**
- Create: `backend/app/execution/__init__.py`
- Create: `backend/app/execution/paper_trader.py`
- Create: `backend/app/execution/order_manager.py`
- Create: `backend/tests/test_paper_trader.py`

- [ ] **Step 1: Write paper trader tests**

```python
# backend/tests/test_paper_trader.py
import pytest

from app.execution.paper_trader import PaperTrader


@pytest.fixture
def trader():
    return PaperTrader(initial_cash=100_000)


def test_buy_order(trader):
    order = trader.buy("NVDA", quantity=10, price=800.0, strategy="breakout", reason="test")
    assert order["side"] == "buy"
    assert order["filled_price"] == 800.0
    assert order["status"] == "filled"
    assert "NVDA" in trader.positions
    assert trader.cash < 100_000


def test_sell_order(trader):
    trader.buy("NVDA", quantity=10, price=800.0, strategy="breakout", reason="test")
    order = trader.sell("NVDA", quantity=10, price=820.0, reason="take profit")
    assert order["side"] == "sell"
    assert order["status"] == "filled"
    assert "NVDA" not in trader.positions
    assert trader.cash > 100_000  # profit


def test_pnl_calculation(trader):
    trader.buy("AAPL", quantity=100, price=180.0, strategy="breakout", reason="test")
    trader.sell("AAPL", quantity=100, price=185.0, reason="take profit")
    assert len(trader.trades) == 1
    assert trader.trades[0]["pnl"] == 500.0  # (185-180) * 100
    assert trader.trades[0]["pnl_pct"] == pytest.approx(2.78, rel=0.01)


def test_unrealized_pnl(trader):
    trader.buy("AAPL", quantity=100, price=180.0, strategy="breakout", reason="test")
    pnl = trader.get_unrealized_pnl("AAPL", current_price=190.0)
    assert pnl == 1000.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_paper_trader.py -v
```

- [ ] **Step 3: Implement paper_trader.py**

```python
# backend/app/execution/paper_trader.py
from datetime import datetime, timezone


class PaperTrader:
    """Simulated trading engine for V0/V1."""

    def __init__(self, initial_cash: float = 100_000.0):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: dict[str, dict] = {}  # ticker -> {qty, avg_price, strategy}
        self.trades: list[dict] = []
        self.orders: list[dict] = []

    def buy(self, ticker: str, quantity: int, price: float, strategy: str, reason: str) -> dict:
        cost = quantity * price
        self.cash -= cost

        if ticker in self.positions:
            pos = self.positions[ticker]
            total_qty = pos["quantity"] + quantity
            pos["avg_price"] = (pos["avg_price"] * pos["quantity"] + price * quantity) / total_qty
            pos["quantity"] = total_qty
        else:
            self.positions[ticker] = {"quantity": quantity, "avg_price": price, "strategy": strategy}

        order = {
            "ticker": ticker,
            "side": "buy",
            "quantity": quantity,
            "filled_price": price,
            "status": "filled",
            "strategy": strategy,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.orders.append(order)
        return order

    def sell(self, ticker: str, quantity: int, price: float, reason: str) -> dict:
        if ticker not in self.positions:
            return {"ticker": ticker, "side": "sell", "status": "rejected", "reason": "no position"}

        pos = self.positions[ticker]
        sell_qty = min(quantity, pos["quantity"])
        revenue = sell_qty * price
        self.cash += revenue

        pnl = (price - pos["avg_price"]) * sell_qty
        pnl_pct = ((price - pos["avg_price"]) / pos["avg_price"]) * 100

        trade = {
            "ticker": ticker,
            "side": "sell",
            "quantity": sell_qty,
            "entry_price": pos["avg_price"],
            "exit_price": price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "strategy": pos["strategy"],
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.trades.append(trade)

        pos["quantity"] -= sell_qty
        if pos["quantity"] <= 0:
            del self.positions[ticker]

        order = {
            "ticker": ticker,
            "side": "sell",
            "quantity": sell_qty,
            "filled_price": price,
            "status": "filled",
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.orders.append(order)
        return order

    def get_unrealized_pnl(self, ticker: str, current_price: float) -> float:
        if ticker not in self.positions:
            return 0.0
        pos = self.positions[ticker]
        return round((current_price - pos["avg_price"]) * pos["quantity"], 2)

    def get_portfolio_value(self, prices: dict[str, float]) -> float:
        positions_value = sum(
            prices.get(ticker, pos["avg_price"]) * pos["quantity"]
            for ticker, pos in self.positions.items()
        )
        return self.cash + positions_value

    def get_total_pnl(self) -> float:
        return sum(t["pnl"] for t in self.trades)

    def get_stats(self) -> dict:
        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]
        total = len(self.trades)
        return {
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / total if total > 0 else 0,
            "total_pnl": round(self.get_total_pnl(), 2),
            "cash": round(self.cash, 2),
        }
```

- [ ] **Step 4: Implement order_manager.py**

```python
# backend/app/execution/order_manager.py
import logging
from app.execution.paper_trader import PaperTrader

logger = logging.getLogger(__name__)


class OrderManager:
    """Manage order lifecycle. V0: paper trading only."""

    def __init__(self, trader: PaperTrader):
        self.trader = trader

    def execute_signal(self, signal: dict, quantity: int) -> dict:
        """Execute a signal by creating a paper trade."""
        ticker = signal["ticker"]
        price = signal["entry_price"]
        strategy = signal["strategy_name"]
        reason = signal.get("reason", "")

        order = self.trader.buy(ticker, quantity, price, strategy, reason)
        logger.info("Paper BUY %s x%d @ %.2f [%s]", ticker, quantity, price, strategy)
        return order

    def close_position(self, ticker: str, price: float, reason: str) -> dict:
        """Close an existing position."""
        if ticker not in self.trader.positions:
            return {"status": "rejected", "reason": "no position"}
        pos = self.trader.positions[ticker]
        order = self.trader.sell(ticker, pos["quantity"], price, reason)
        logger.info("Paper SELL %s @ %.2f [%s]", ticker, price, reason)
        return order

    def check_exits(self, prices: dict[str, float], stop_losses: dict[str, float]) -> list[dict]:
        """Check all positions for stop loss triggers."""
        exits = []
        for ticker, pos in list(self.trader.positions.items()):
            current_price = prices.get(ticker, 0)
            stop = stop_losses.get(ticker, 0)
            if stop > 0 and current_price <= stop:
                order = self.close_position(ticker, current_price, f"Stop loss triggered at {stop}")
                exits.append(order)
        return exits
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/test_paper_trader.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/execution/ backend/tests/test_paper_trader.py
git commit -m "feat: paper trading engine and order manager"
```

---

## Task 8: Trading Pipeline

**Files:**
- Create: `backend/app/pipeline/__init__.py`
- Create: `backend/app/pipeline/scanner.py`

- [ ] **Step 1: Implement scanner.py**

```python
# backend/app/pipeline/scanner.py
import logging
from datetime import datetime, timezone

from app.config import settings
from app.market.data_service import market_data_service
from app.strategy import STRATEGIES
from app.llm import review_risk
from app.risk import CircuitBreaker, HardRiskChecker, PositionManager
from app.execution.paper_trader import PaperTrader
from app.execution.order_manager import OrderManager

logger = logging.getLogger(__name__)


class ScannerPipeline:
    """Core scanning pipeline — runs every N minutes."""

    def __init__(self):
        self.risk_checker = HardRiskChecker(
            max_daily_loss_pct=settings.max_daily_loss_pct,
            max_weekly_loss_pct=settings.max_weekly_loss_pct,
            max_concurrent_positions=settings.max_concurrent_positions,
            max_single_position_pct=settings.max_single_position_pct,
            consecutive_loss_limit=settings.consecutive_loss_limit,
        )
        self.circuit_breaker = CircuitBreaker()
        self.position_manager = PositionManager()
        self.trader = PaperTrader()
        self.order_manager = OrderManager(self.trader)
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.consecutive_losses = 0
        self.last_scan_results: list[dict] = []

    async def run_scan(self) -> list[dict]:
        """Execute one full scan cycle. Returns list of events."""
        events = []

        # Check circuit breaker
        allowed, reason = self.circuit_breaker.check_trading_allowed()
        if not allowed:
            logger.warning("Scan skipped: %s", reason)
            events.append({"type": "skipped", "reason": reason})
            return events

        # Get market context
        market = market_data_service.get_market_context("QQQ")

        # Scan each symbol
        for ticker in settings.symbol_list:
            try:
                result = await self._scan_symbol(ticker, market)
                if result:
                    events.append(result)
            except Exception as e:
                logger.error("Error scanning %s: %s", ticker, e)
                events.append({"type": "error", "ticker": ticker, "error": str(e)})

        self.last_scan_results = events
        return events

    async def _scan_symbol(self, ticker: str, market: dict) -> dict | None:
        # 1. Get market data
        bars = market_data_service.get_bars(ticker, interval="15m", period="5d")
        if bars.empty:
            return None

        indicators = market_data_service.compute_indicators(bars)

        # 2. Run strategies
        for strategy in STRATEGIES:
            signal = strategy.evaluate(ticker, bars, indicators, market)
            if signal is None:
                continue

            # 3. Hard risk check
            risk_result = self.risk_checker.check(
                position_pct=settings.max_single_position_pct * 100,
                current_positions=len(self.trader.positions),
                daily_pnl_pct=self.daily_pnl / self.trader.initial_cash,
                weekly_pnl_pct=self.weekly_pnl / self.trader.initial_cash,
                consecutive_losses=self.consecutive_losses,
                daily_volume_usd=bars["volume"].iloc[-1] * bars["close"].iloc[-1],
            )

            if not risk_result.approved:
                return {"type": "signal_rejected", "ticker": ticker, "strategy": signal["strategy_name"], "reason": risk_result.reason, "timestamp": datetime.now(timezone.utc).isoformat()}

            # 4. LLM risk review
            llm_result = await review_risk(
                ticker=ticker,
                strategy=signal["strategy_name"],
                entry_price=signal["entry_price"],
                stop_loss=signal["stop_loss"],
                position_pct=settings.max_single_position_pct * 100,
                market_state=f"QQQ {market['change_pct']:+.2f}%",
                news_summary="V0: no news service yet",
            )

            llm_action = llm_result.get("action", "approve")
            if llm_action == "reject":
                return {"type": "signal_rejected", "ticker": ticker, "strategy": signal["strategy_name"], "reason": f"LLM rejected: {llm_result.get('reason', 'unknown')}", "timestamp": datetime.now(timezone.utc).isoformat()}

            # 5. Execute (paper)
            quantity = self.position_manager.calculate_quantity(signal["entry_price"], settings.max_single_position_pct * 100)
            if quantity <= 0:
                continue

            order = self.order_manager.execute_signal(signal, quantity)

            return {
                "type": "signal_executed",
                "ticker": ticker,
                "strategy": signal["strategy_name"],
                "direction": signal["direction"],
                "entry_price": signal["entry_price"],
                "stop_loss": signal["stop_loss"],
                "take_profit": signal["take_profit"],
                "quantity": quantity,
                "llm_action": llm_action,
                "llm_risk_score": llm_result.get("risk_score"),
                "reason": signal["reason"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return None

    def get_status(self) -> dict:
        return {
            "circuit_breaker_paused": self.circuit_breaker.is_paused,
            "circuit_breaker_reason": self.circuit_breaker.pause_reason,
            "positions": dict(self.trader.positions),
            "cash": self.trader.cash,
            "stats": self.trader.get_stats(),
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
        }


# Singleton
scanner_pipeline = ScannerPipeline()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/pipeline/
git commit -m "feat: trading pipeline connecting market data, strategies, risk, and execution"
```

---

## Task 9: FastAPI Routes

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/market.py`
- Create: `backend/app/api/signals.py`
- Create: `backend/app/api/trades.py`
- Create: `backend/app/api/risk.py`
- Create: `backend/app/api/system.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create deps.py**

```python
# backend/app/api/deps.py
from app.pipeline.scanner import scanner_pipeline
from app.market.data_service import market_data_service


def get_pipeline():
    return scanner_pipeline


def get_market_service():
    return market_data_service
```

- [ ] **Step 2: Create API routes**

```python
# backend/app/api/market.py
from fastapi import APIRouter

from app.api.deps import get_market_service
from app.config import settings

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/symbols")
async def list_symbols():
    return [{"ticker": t, "is_active": True} for t in settings.symbol_list]


@router.get("/quote/{ticker}")
async def get_quote(ticker: str):
    svc = get_market_service()
    return svc.get_quote(ticker)


@router.get("/bars/{ticker}")
async def get_bars(ticker: str, interval: str = "15m", period: str = "5d"):
    svc = get_market_service()
    df = svc.get_bars(ticker, interval=interval, period=period)
    if df.empty:
        return []
    return df.reset_index().to_dict(orient="records")
```

```python
# backend/app/api/signals.py
from fastapi import APIRouter

from app.api.deps import get_pipeline

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("")
async def list_signals():
    pipeline = get_pipeline()
    return pipeline.last_scan_results
```

```python
# backend/app/api/trades.py
from fastapi import APIRouter

from app.api.deps import get_pipeline

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("")
async def list_trades():
    pipeline = get_pipeline()
    return pipeline.trader.trades


@router.get("/stats")
async def trade_stats():
    pipeline = get_pipeline()
    return pipeline.trader.get_stats()
```

```python
# backend/app/api/risk.py
from fastapi import APIRouter

from app.api.deps import get_pipeline

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/status")
async def risk_status():
    pipeline = get_pipeline()
    return pipeline.get_status()
```

```python
# backend/app/api/system.py
from fastapi import APIRouter

from app.api.deps import get_pipeline

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status():
    pipeline = get_pipeline()
    return {
        "status": "paused" if pipeline.circuit_breaker.is_paused else "running",
        "positions": len(pipeline.trader.positions),
        "cash": pipeline.trader.cash,
    }


@router.post("/pause")
async def pause_trading(reason: str = "Manual pause"):
    pipeline = get_pipeline()
    pipeline.circuit_breaker.pause(reason)
    return {"status": "paused", "reason": reason}


@router.post("/resume")
async def resume_trading():
    pipeline = get_pipeline()
    pipeline.circuit_breaker.resume()
    return {"status": "running"}
```

- [ ] **Step 3: Create main.py**

```python
# backend/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import market, signals, trades, risk, system
from app.models.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="US Stock Trading Bot", version="0.1.0", lifespan=lifespan)

app.include_router(market.router)
app.include_router(signals.router)
app.include_router(trades.router)
app.include_router(risk.router)
app.include_router(system.router)


@app.get("/")
async def root():
    return {"name": "US Stock Trading Bot", "version": "0.1.0"}
```

- [ ] **Step 4: Create api/__init__.py**

```python
# backend/app/api/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/ backend/app/main.py
git commit -m "feat: FastAPI routes for market, signals, trades, risk, and system"
```

---

## Task 10: Telegram Bot

**Files:**
- Create: `backend/app/telegram/__init__.py`
- Create: `backend/app/telegram/bot.py`

- [ ] **Step 1: Implement Telegram bot**

```python
# backend/app/telegram/bot.py
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import settings

logger = logging.getLogger(__name__)

# These will be set by main.py after pipeline is initialized
_pipeline = None


def set_pipeline(pipeline):
    global _pipeline
    _pipeline = pipeline


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _pipeline:
        await update.message.reply_text("Pipeline not initialized")
        return
    s = _pipeline.get_status()
    msg = (
        f"System: {'PAUSED' if s['circuit_breaker_paused'] else 'RUNNING'}\n"
        f"Cash: ${s['cash']:,.2f}\n"
        f"Positions: {len(s['positions'])}\n"
        f"Daily PnL: ${s['daily_pnl']:,.2f}\n"
        f"Total PnL: ${s['stats']['total_pnl']:,.2f}\n"
        f"Win Rate: {s['stats']['win_rate']:.0%}"
    )
    await update.message.reply_text(msg)


async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _pipeline:
        return
    stats = _pipeline.trader.get_stats()
    msg = (
        f"Total PnL: ${stats['total_pnl']:,.2f}\n"
        f"Trades: {stats['total_trades']}\n"
        f"Wins: {stats['wins']}\n"
        f"Losses: {stats['losses']}\n"
        f"Win Rate: {stats['win_rate']:.0%}"
    )
    await update.message.reply_text(msg)


async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _pipeline:
        return
    positions = _pipeline.trader.positions
    if not positions:
        await update.message.reply_text("No open positions")
        return
    lines = []
    for ticker, pos in positions.items():
        lines.append(f"{ticker}: {pos['quantity']} shares @ ${pos['avg_price']:.2f} [{pos['strategy']}]")
    await update.message.reply_text("\n".join(lines))


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _pipeline:
        return
    _pipeline.circuit_breaker.pause("Manual pause via Telegram")
    await update.message.reply_text("Trading PAUSED")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _pipeline:
        return
    _pipeline.circuit_breaker.resume()
    await update.message.reply_text("Trading RESUMED")


async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _pipeline:
        return
    s = _pipeline.get_status()
    msg = (
        f"Circuit Breaker: {'ON' if s['circuit_breaker_paused'] else 'OFF'}\n"
        f"Reason: {s['circuit_breaker_reason'] or 'None'}\n"
        f"Consecutive Losses: {s['consecutive_losses']}\n"
        f"Daily PnL: ${s['daily_pnl']:,.2f}"
    )
    await update.message.reply_text(msg)


async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _pipeline:
        return
    results = _pipeline.last_scan_results
    if not results:
        await update.message.reply_text("No recent signals")
        return
    lines = []
    for r in results[-10:]:
        lines.append(f"{r.get('type')}: {r.get('ticker', 'N/A')} - {r.get('reason', r.get('strategy', ''))}")
    await update.message.reply_text("\n".join(lines))


async def send_message(text: str):
    """Send a message to the configured chat."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured, skipping message")
        return
    import httpx
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": settings.telegram_chat_id, "text": text})


def create_bot() -> Application | None:
    if not settings.telegram_bot_token:
        logger.warning("No Telegram bot token, skipping bot setup")
        return None

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("pnl", cmd_pnl))
    app.add_handler(CommandHandler("positions", cmd_positions))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("signals", cmd_signals))
    return app
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/telegram/
git commit -m "feat: Telegram bot with /status /pnl /positions /pause /resume /risk /signals"
```

---

## Task 11: Scheduler

**Files:**
- Create: `backend/app/scheduler/__init__.py`
- Create: `backend/app/scheduler/market_scanner.py`
- Create: `backend/app/scheduler/daily_report.py`
- Modify: `backend/app/main.py` (add scheduler startup)

- [ ] **Step 1: Implement market_scanner.py**

```python
# backend/app/scheduler/market_scanner.py
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.pipeline.scanner import scanner_pipeline
from app.telegram.bot import send_message

logger = logging.getLogger(__name__)


async def scan_job():
    """Scheduled scan job — runs every N minutes during market hours."""
    now = datetime.now(timezone.utc)
    hour = now.hour

    # Only run during US market hours (roughly 13:30-20:00 UTC)
    if hour < 13 or hour > 20:
        return

    logger.info("Running scan...")
    events = await scanner_pipeline.run_scan()

    for event in events:
        if event.get("type") == "signal_executed":
            msg = (
                f"SIGNAL: {event['ticker']} {event['direction'].upper()}\n"
                f"Strategy: {event['strategy']}\n"
                f"Price: ${event['entry_price']:.2f}\n"
                f"Stop: ${event['stop_loss']:.2f}\n"
                f"Qty: {event['quantity']}\n"
                f"LLM: {event.get('llm_action', 'N/A')} (risk={event.get('llm_risk_score', '?')})"
            )
            await send_message(msg)
        elif event.get("type") == "signal_rejected":
            msg = f"REJECTED: {event['ticker']} [{event['strategy']}] — {event['reason']}"
            await send_message(msg)

    logger.info("Scan complete: %d events", len(events))


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scan_job, "interval", minutes=settings.scan_interval_minutes, id="market_scan")
    return scheduler
```

- [ ] **Step 2: Implement daily_report.py**

```python
# backend/app/scheduler/daily_report.py
import logging
from datetime import datetime, timezone

from app.pipeline.scanner import scanner_pipeline
from app.telegram.bot import send_message

logger = logging.getLogger(__name__)


async def daily_report_job():
    """Generate and send daily trading report."""
    stats = scanner_pipeline.trader.get_stats()
    positions = scanner_pipeline.trader.positions

    msg = (
        f"Daily Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
        f"Cash: ${scanner_pipeline.trader.cash:,.2f}\n"
        f"Total PnL: ${stats['total_pnl']:,.2f}\n"
        f"Trades: {stats['total_trades']} (W:{stats['wins']} L:{stats['losses']})\n"
        f"Win Rate: {stats['win_rate']:.0%}\n"
        f"Open Positions: {len(positions)}"
    )

    for ticker, pos in positions.items():
        msg += f"\n  {ticker}: {pos['quantity']} @ ${pos['avg_price']:.2f}"

    await send_message(msg)
    logger.info("Daily report sent")
```

- [ ] **Step 3: Update main.py to start scheduler and Telegram bot**

```python
# backend/app/main.py — add to lifespan:
from app.scheduler.market_scanner import create_scheduler
from app.telegram.bot import create_bot, set_pipeline
from app.pipeline.scanner import scanner_pipeline

# In lifespan, after init_db():
set_pipeline(scanner_pipeline)
scheduler = create_scheduler()
scheduler.start()
tg_app = create_bot()
if tg_app:
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

# On shutdown:
if tg_app:
    await tg_app.updater.stop()
    await tg_app.stop()
scheduler.shutdown()
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/scheduler/ backend/app/main.py
git commit -m "feat: APScheduler for market scanning and daily reports"
```

---

## Task 12: Frontend Next.js App

**Files:**
- Create: `frontend/` (entire Next.js project)
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/watchlist/page.tsx`
- Create: `frontend/src/app/trades/page.tsx`
- Create: `frontend/src/app/strategy/page.tsx`
- Create: `frontend/src/app/risk/page.tsx`
- Create: `frontend/src/components/Navbar.tsx`
- Create: `frontend/src/components/StatCard.tsx`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/types.ts`

- [ ] **Step 1: Initialize Next.js project**

```bash
cd frontend && npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --no-import-alias
```

- [ ] **Step 2: Create types.ts**

```typescript
// frontend/src/lib/types.ts
export interface Quote {
  ticker: string;
  price: number;
  change_pct: number;
  volume: number;
}

export interface Signal {
  type: string;
  ticker?: string;
  strategy?: string;
  direction?: string;
  entry_price?: number;
  stop_loss?: number;
  take_profit?: number;
  quantity?: number;
  reason?: string;
  timestamp?: string;
}

export interface Trade {
  ticker: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  strategy: string;
  reason: string;
  timestamp: string;
}

export interface TradeStats {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  cash: number;
}

export interface Position {
  quantity: number;
  avg_price: number;
  strategy: string;
}

export interface SystemStatus {
  status: string;
  positions: number;
  cash: number;
}
```

- [ ] **Step 3: Create api.ts**

```typescript
// frontend/src/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  getSymbols: () => fetchJson<{ ticker: string; is_active: boolean }[]>("/api/market/symbols"),
  getQuote: (ticker: string) => fetchJson<any>(`/api/market/quote/${ticker}`),
  getSignals: () => fetchJson<any[]>("/api/signals"),
  getTrades: () => fetchJson<any[]>("/api/trades"),
  getTradeStats: () => fetchJson<any>("/api/trades/stats"),
  getRiskStatus: () => fetchJson<any>("/api/risk/status"),
  getSystemStatus: () => fetchJson<any>("/api/system/status"),
  pause: () => fetch(`${API_BASE}/api/system/pause`, { method: "POST" }),
  resume: () => fetch(`${API_BASE}/api/system/resume`, { method: "POST" }),
};
```

- [ ] **Step 4: Create Navbar component**

```tsx
// frontend/src/components/Navbar.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/trades", label: "Trades" },
  { href: "/strategy", label: "Strategy" },
  { href: "/risk", label: "Risk" },
];

export function Navbar() {
  const pathname = usePathname();
  return (
    <nav className="bg-gray-900 text-white p-4 flex gap-6">
      <span className="font-bold text-lg">USStock</span>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`hover:text-blue-400 ${pathname === l.href ? "text-blue-400 font-semibold" : ""}`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
```

- [ ] **Step 5: Create StatCard component**

```tsx
// frontend/src/components/StatCard.tsx
export function StatCard({ title, value, subtitle }: { title: string; value: string; subtitle?: string }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-sm text-gray-500">{title}</p>
      <p className="text-2xl font-bold">{value}</p>
      {subtitle && <p className="text-sm text-gray-400">{subtitle}</p>}
    </div>
  );
}
```

- [ ] **Step 6: Create layout.tsx**

```tsx
// frontend/src/app/layout.tsx
import type { Metadata } from "next";
import { Navbar } from "@/components/Navbar";
import "./globals.css";

export const metadata: Metadata = { title: "USStock Trading Bot" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">
        <Navbar />
        <main className="max-w-7xl mx-auto p-6">{children}</main>
      </body>
    </html>
  );
}
```

- [ ] **Step 7: Create Dashboard page**

```tsx
// frontend/src/app/page.tsx
"use client";
import { useEffect, useState } from "react";
import { StatCard } from "@/components/StatCard";
import { api } from "@/lib/api";

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    api.getSystemStatus().then(setStatus).catch(() => {});
    api.getTradeStats().then(setStats).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="System" value={status?.status || "..."} />
        <StatCard title="Cash" value={`$${(status?.cash || 0).toLocaleString()}`} />
        <StatCard title="Positions" value={String(status?.positions || 0)} />
        <StatCard title="Total PnL" value={`$${(stats?.total_pnl || 0).toLocaleString()}`} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="Total Trades" value={String(stats?.total_trades || 0)} />
        <StatCard title="Win Rate" value={`${((stats?.win_rate || 0) * 100).toFixed(0)}%`} />
        <StatCard title="Wins" value={String(stats?.wins || 0)} />
        <StatCard title="Losses" value={String(stats?.losses || 0)} />
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Create Watchlist, Trades, Strategy, Risk pages**

```tsx
// frontend/src/app/watchlist/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Watchlist() {
  const [symbols, setSymbols] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);

  useEffect(() => {
    api.getSymbols().then(setSymbols).catch(() => {});
    api.getSignals().then(setSignals).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Watchlist</h1>
      <table className="w-full bg-white rounded shadow">
        <thead>
          <tr className="border-b">
            <th className="p-3 text-left">Ticker</th>
            <th className="p-3 text-left">Status</th>
            <th className="p-3 text-left">Recent Signal</th>
          </tr>
        </thead>
        <tbody>
          {symbols.map((s) => {
            const sig = signals.find((sig) => sig.ticker === s.ticker);
            return (
              <tr key={s.ticker} className="border-b hover:bg-gray-50">
                <td className="p-3 font-mono font-bold">{s.ticker}</td>
                <td className="p-3">{s.is_active ? "Active" : "Inactive"}</td>
                <td className="p-3">{sig ? `${sig.type}: ${sig.reason || sig.strategy || ""}` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

```tsx
// frontend/src/app/trades/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Trades() {
  const [trades, setTrades] = useState<any[]>([]);

  useEffect(() => { api.getTrades().then(setTrades).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Trade Log</h1>
      <table className="w-full bg-white rounded shadow">
        <thead>
          <tr className="border-b">
            <th className="p-3 text-left">Ticker</th>
            <th className="p-3 text-left">Strategy</th>
            <th className="p-3 text-right">Entry</th>
            <th className="p-3 text-right">Exit</th>
            <th className="p-3 text-right">PnL</th>
            <th className="p-3 text-left">Reason</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={i} className="border-b hover:bg-gray-50">
              <td className="p-3 font-mono font-bold">{t.ticker}</td>
              <td className="p-3">{t.strategy}</td>
              <td className="p-3 text-right">${t.entry_price}</td>
              <td className="p-3 text-right">${t.exit_price}</td>
              <td className={`p-3 text-right font-bold ${t.pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                ${t.pnl} ({t.pnl_pct}%)
              </td>
              <td className="p-3 text-sm text-gray-500">{t.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

```tsx
// frontend/src/app/strategy/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";

export default function Strategy() {
  const [stats, setStats] = useState<any>(null);

  useEffect(() => { api.getTradeStats().then(setStats).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Strategy</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="Breakout" value="Active" subtitle="N-bar high + volume" />
        <StatCard title="Mean Reversion" value="Active" subtitle="RSI < 25 + VWAP deviation" />
      </div>
      <h2 className="text-xl font-bold mt-6 mb-4">Performance</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="Win Rate" value={`${((stats?.win_rate || 0) * 100).toFixed(0)}%`} />
        <StatCard title="Total PnL" value={`$${(stats?.total_pnl || 0).toLocaleString()}`} />
        <StatCard title="Total Trades" value={String(stats?.total_trades || 0)} />
        <StatCard title="Cash" value={`$${(stats?.cash || 0).toLocaleString()}`} />
      </div>
    </div>
  );
}
```

```tsx
// frontend/src/app/risk/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";

export default function Risk() {
  const [risk, setRisk] = useState<any>(null);

  useEffect(() => { api.getRiskStatus().then(setRisk).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Risk Center</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="Circuit Breaker" value={risk?.circuit_breaker_paused ? "ON" : "OFF"} />
        <StatCard title="Daily PnL" value={`$${(risk?.daily_pnl || 0).toLocaleString()}`} />
        <StatCard title="Consecutive Losses" value={String(risk?.consecutive_losses || 0)} />
        <StatCard title="Cash" value={`$${(risk?.cash || 0).toLocaleString()}`} />
      </div>
      {risk?.circuit_breaker_reason && (
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700">
          <strong>Pause Reason:</strong> {risk.circuit_breaker_reason}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat: Next.js frontend with Dashboard, Watchlist, Trades, Strategy, Risk pages"
```

---

## Task 13: Integration & Docker

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Modify: `backend/app/main.py` (finalize)

- [ ] **Step 1: Create backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create frontend Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json .
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["npm", "start"]
```

- [ ] **Step 3: Run backend tests**

```bash
cd backend && pytest -v
```

Expected: All tests pass

- [ ] **Step 4: Verify backend starts**

```bash
cd backend && uvicorn app.main:app --port 8000 &
curl http://localhost:8000/
# Expected: {"name":"US Stock Trading Bot","version":"0.1.0"}
curl http://localhost:8000/api/market/symbols
# Expected: list of symbols
```

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile
git commit -m "feat: Dockerfiles for backend and frontend"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** Market data (Task 3), Strategies (Task 4), LLM (Task 5), Risk (Task 6), Execution (Task 7), Pipeline (Task 8), API (Task 9), Telegram (Task 10), Scheduler (Task 11), Frontend (Task 12) — all V0 deliverables covered.
- [ ] **Placeholder scan:** No TBD/TODO found. All code is complete.
- [ ] **Type consistency:** All model names (Signal, Trade, Position, etc.) consistent across tasks. Method signatures match usage.
