# US Stock LLM Quant Trading Bot — Design Spec

> 量化主导，LLM 辅助，风控最终裁决。

## 1. 项目定位

美股中低频自动交易系统（5 分钟 ~ 4 小时级别）。量化策略引擎负责产生交易信号，LLM 负责新闻理解、事件分析、风险过滤和交易复盘，硬风控模块负责最终下单许可。

**不是"AI 自动炒股机器人"，而是"量化交易 + LLM 风险增强 + 自动复盘系统"。**

LLM 的核心目标不是预测涨跌，而是**减少错误交易**——识别隐藏风险、过滤假突破、在大盘不支持时降仓。

## 2. 技术选型

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0 + APScheduler |
| 前端 | React + Next.js (App Router) + Tailwind + Recharts |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis |
| 券商 API | IBKR via ib_insync（V0 阶段先用 yfinance/免费 API） |
| LLM | OpenAI 兼容 API（本地或代理端点） |
| 新闻数据 | yfinance（免费，V0）→ Finnhub / Polygon（V1+）|
| 通知 | Telegram Bot |
| 部署 | Docker Compose |

## 3. 架构方案：单体 Monorepo

```
usstock/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 配置管理 (pydantic-settings)
│   │   ├── market/                  # 行情数据模块
│   │   │   ├── data_service.py      # 行情 API 对接
│   │   │   ├── bar_aggregator.py    # K线聚合
│   │   │   └── indicators.py        # RSI / VWAP / ATR 等指标计算
│   │   ├── strategy/                # 策略引擎
│   │   │   ├── base.py              # 策略基类
│   │   │   ├── breakout.py          # 趋势突破策略
│   │   │   ├── mean_reversion.py    # 超跌反弹策略
│   │   │   └── event_driven.py      # 事件驱动策略
│   │   ├── llm/                     # LLM 分析模块
│   │   │   ├── client.py            # OpenAI 兼容 API 客户端
│   │   │   ├── news_analyzer.py     # 新闻分析员
│   │   │   ├── risk_reviewer.py     # 风险审查员
│   │   │   └── trade_reviewer.py    # 交易复盘员
│   │   ├── risk/                    # 风控模块
│   │   │   ├── hard_rules.py        # 硬规则（不可被 LLM 覆盖）
│   │   │   ├── position_manager.py  # 仓位管理
│   │   │   └── circuit_breaker.py   # 熔断机制
│   │   ├── execution/               # 订单执行
│   │   │   ├── broker.py            # IBKR 对接
│   │   │   ├── paper_trader.py      # 模拟交易引擎
│   │   │   └── order_manager.py     # 订单生命周期管理
│   │   ├── models/                  # SQLAlchemy 数据模型
│   │   │   ├── db.py                # 引擎 & session
│   │   │   ├── signal.py
│   │   │   ├── trade.py
│   │   │   ├── position.py
│   │   │   └── llm_report.py
│   │   ├── api/                     # REST API 路由
│   │   │   ├── market.py
│   │   │   ├── strategy.py
│   │   │   ├── trade.py
│   │   │   └── risk.py
│   │   ├── scheduler/               # 定时任务
│   │   │   ├── market_scanner.py    # 定时扫描行情
│   │   │   └── daily_report.py      # 每日复盘
│   │   └── telegram/                # Telegram Bot
│   │       └── bot.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                     # Next.js App Router
│   │   │   ├── page.tsx             # Dashboard
│   │   │   ├── watchlist/page.tsx   # 股票池
│   │   │   ├── strategy/page.tsx    # 策略管理
│   │   │   ├── trades/page.tsx      # 交易日志
│   │   │   └── risk/page.tsx        # 风控中心
│   │   ├── components/
│   │   └── lib/api.ts               # API 客户端
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

**模块隔离：** 每个模块是 Python package，通过 `__init__.py` 暴露公共接口。模块间依赖单向：`api → strategy → market`，`api → risk → execution`，`llm` 作为旁路服务被 `strategy` 和 `risk` 调用。

## 4. 核心交易管线

```
调度器 (APScheduler, 每 5 分钟)
    │
    ▼
1. Market Data Service       获取实时行情 + K线，计算指标 (RSI/VWAP/ATR)
    │
    ▼
2. Strategy Engine            3 个策略并行扫描，生成候选信号
    │
    ▼
3. Hard Risk Check            仓位/亏损/持仓数/流动性 — 不通过直接拒绝
    │
    ▼
4. Context Collection         收集新闻/事件/大盘状态
    │
    ▼
5. LLM Risk Analysis          风险评分 + approve/reduce/reject
    │
    ▼
6. Final Decision             Risk Engine 结合 LLM 建议 + 硬规则裁决
    │
    ▼
7. Execution                  V0: 模拟记录 / V1: Paper / V2: IBKR Live
    │
    ▼
8. Position Monitor           止损/止盈/移动止盈，平仓后 LLM 自动复盘
    │
    ▼
9. Notification               Telegram 推送 + WebSocket → 前端
```

**容错设计：**
- 每个步骤异步独立，失败不阻塞下一轮扫描
- LLM 调用 30 秒超时，超时按 "保守" 处理（降仓或跳过）
- 主周期为 15 分钟 K 线

## 5. 交易策略

### 5.1 趋势突破策略

**入场：**
- 价格突破最近 N 根 K 线高点
- 成交量 > 过去 20 根均量的 1.8 倍
- 价格 > VWAP
- QQQ 当日跌幅不超过 -0.7%

**出场：** 固定止损（入场价 - 1.5×ATR）/ 移动止盈（最高价回落 1×ATR）/ 跌破 VWAP / 3 根连续缩量 K 线

**适用场景：** 财报后趋势、分析师上调评级、大盘强势时龙头股突破

### 5.2 超跌反弹策略

**入场：**
- RSI < 25
- 价格偏离 VWAP 过远
- 跌幅明显大于同板块
- 无重大基本面利空

**出场：** 回到 VWAP 止盈 / 继续破位止损 / 反弹失败快速退出

**适用场景：** 非理性杀跌、大盘恐慌后回补、蓝筹技术性反弹

### 5.3 事件驱动策略

**流程：** 新闻出现 → LLM 分类 → 价格确认 → 风控确认 → 下单

不直接根据新闻交易，必须等待技术确认。

## 6. LLM 模块

### 6.1 客户端配置

```python
client = AsyncOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
)
model = os.getenv("LLM_MODEL", "default")
```

### 6.2 三个 LLM 角色（V0）

| 角色 | 触发时机 | 输出 | 超时 |
|------|---------|------|------|
| 新闻分析员 | 新闻到达 | 事件类型、情感、影响分、风险标记 | 15s |
| 风险审查员 | 下单前 | 风险分、approve/reduce/reject、建议仓位 | 30s |
| 交易复盘员 | 平仓后 | 评级、错误分析、改进建议 | 30s |

### 6.3 容错

- 超时 → `reduce_size`（保守降仓）
- 返回格式异常 → 正则提取，失败则跳过 LLM
- API 报错 → 记录日志，降级为纯规则风控
- 所有输出存入 `llm_reports` 表

### 6.4 LLM 权限

**可以：** 总结新闻、判断事件类型、标记风险、建议降仓、建议观望、生成复盘
**不可以：** 直接下单、提高最大仓位、关闭止损、关闭熔断、绕过风控、修改账户级参数

## 7. 风控规则

### 7.1 账户级（硬规则，不可覆盖）

```python
MAX_DAILY_LOSS_PCT = 0.01          # 单日最大亏损 1%
MAX_WEEKLY_LOSS_PCT = 0.04         # 单周最大亏损 4%
MAX_CONCURRENT_POSITIONS = 2       # 最多 2 个持仓 (V0)
MAX_SINGLE_POSITION_PCT = 0.02     # 单票最大 2%
CONSECUTIVE_LOSS_LIMIT = 3         # 连亏 3 笔暂停
```

### 7.2 交易级

```python
MAX_SPREAD_PCT = 0.005             # 点差 > 0.5% 禁止
MIN_VOLUME_USD = 5_000_000         # 日成交额 < 500 万禁止
BLOCK_BEFORE_EARNINGS_HOURS = 24   # 财报前 24h 降仓
OPENING_BLACKOUT_MINUTES = 5       # 开盘 5 分钟内不交易
```

### 7.3 熔断机制

- 当日亏损达上限 → 强制停机
- 连续亏损 3 笔 → 暂停交易，推送 Telegram 告警
- LLM 服务不可用 → 降级为纯规则风控
- API 数据延迟 > 60s → 暂停自动下单

## 8. 数据库设计

### symbols
```sql
id SERIAL PRIMARY KEY,
ticker VARCHAR(10) UNIQUE,
name VARCHAR(100),
sector VARCHAR(50),
is_active BOOLEAN DEFAULT true,
max_position_pct FLOAT DEFAULT 2,
created_at TIMESTAMPTZ
```

### market_bars
```sql
id, symbol_id FK, timeframe VARCHAR(5),
open, high, low, close, volume BIGINT, vwap,
bar_time TIMESTAMPTZ,
UNIQUE(symbol_id, timeframe, bar_time)
```

### signals
```sql
id, symbol_id FK, strategy_name, direction, strength,
entry_price, stop_loss, take_profit, reason,
status (pending/approved/rejected/executed/expired),
llm_report_id FK, created_at
```

### orders
```sql
id, signal_id FK, symbol_id FK, side, order_type,
quantity, price, status, broker_order_id,
filled_price, filled_at, created_at
```

### trades
```sql
id, symbol_id FK, strategy_name, side,
entry_price, exit_price, quantity,
pnl, pnl_pct, entry_reason, exit_reason,
llm_review TEXT, trade_grade (A/B/C/D/F),
opened_at, closed_at
```

### positions
```sql
id, symbol_id FK UNIQUE, side, quantity,
avg_price, current_price, unrealized_pnl,
stop_loss, take_profit, strategy_name,
opened_at, updated_at
```

### llm_reports
```sql
id, symbol_id FK, report_type (news/risk_review/trade_review),
source_text, summary, sentiment, impact_score (1-5),
risk_score (1-10), risk_flags JSONB,
suggested_action, model_used, latency_ms, created_at
```

### risk_events
```sql
id, event_type, severity (warning/critical),
message, action_taken, created_at
```

### system_logs
```sql
id, level, module, message, metadata JSONB, created_at
```

## 9. API 接口

```
GET  /api/market/symbols              # 股票池
GET  /api/market/quote/{ticker}       # 实时报价
GET  /api/market/bars/{ticker}        # K线数据
GET  /api/signals                     # 信号列表
GET  /api/signals/{id}                # 信号详情
GET  /api/trades                      # 交易记录
GET  /api/trades/{id}                 # 交易详情
GET  /api/trades/stats                # 统计
GET  /api/positions                   # 当前持仓
POST /api/positions/{ticker}/close    # 手动平仓
GET  /api/risk/status                 # 风控状态
GET  /api/risk/events                 # 风控事件
POST /api/system/pause                # 暂停
POST /api/system/resume               # 恢复
GET  /api/system/status               # 系统状态
WS   /ws/market                       # 实时行情
WS   /ws/signals                      # 实时信号
```

## 10. 前端页面

1. **Dashboard** — 账户净值、今日 PnL、持仓概览、风控状态、系统状态
2. **Watchlist** — 股票池、实时价格、信号状态、LLM 评分、风险标签
3. **Trades** — 交易日志、详情含 LLM 复盘
4. **Strategy** — 策略开关、参数、胜率/盈亏比/最大回撤
5. **Risk** — 亏损额度、剩余可交易额度、风险暴露、风控事件日志

## 11. Telegram 指令

```
/status    系统状态
/pnl       今日盈亏
/positions 当前持仓
/watch {ticker}  股票详情 + LLM 分析
/pause     暂停自动交易
/resume    恢复自动交易
/close {ticker}  手动平仓
/risk      风控状态
/signals   当前候选信号
```

默认模式：小仓位自动执行，高风险交易需确认，超限仓位必须手动确认。

## 12. 初期标的池

```
SPY  QQQ  AAPL  MSFT  NVDA  TSLA
META  AMZN  GOOGL  AMD  NFLX  AVGO
SMH  XLK
```

选择标准：高流动性、低滑点、新闻密集、适合 LLM 分析、走势有延续性。

## 13. 里程碑

| 版本 | 目标 | 交易方式 | 持续时间 |
|------|------|---------|---------|
| V0 | 跑通管线，验证信号质量 | 只记录信号，不下单 | 1-2 周 |
| V1 | 模拟交易，统计胜率 | Paper Trading | 2-4 周 |
| V2 | 小资金实盘 | IBKR Live，严格风控 | 持续 |
| V3 | 策略扩展 | 更多标的/策略/期权 | 远期 |

### V0 交付物

- 行情数据获取（yfinance → IBKR）
- 趋势突破 + 超跌反弹策略引擎
- LLM 风险分析（OpenAI 兼容 API）
- 硬风控模块
- 模拟交易记录
- Telegram 推送
- 前端 Dashboard（基础版）
