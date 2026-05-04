# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

US Stock LLM Quant Trading Bot — 量化交易 + LLM 风险增强 + 自动复盘系统。

## Commands

### Backend
```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest
pytest tests/test_indicators.py -v
pytest -k "test_rsi" -v
ruff check .
ruff format .
```

### Frontend
```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
```

### Docker
```bash
docker compose up -d
docker compose down
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
