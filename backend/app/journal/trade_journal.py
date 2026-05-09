from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Obsidian vault path - trades/ subdirectory
JOURNAL_DIR = Path(os.getenv("TRADE_JOURNAL_DIR", "/home/du/project/usstock/trades"))


def _format_grade(grade: str) -> str:
    grades = {"A": "A 优秀", "B": "B 良好", "C": "C 一般", "D": "D 较差", "F": "F 失败"}
    return grades.get(grade, grade)


def _pnl_emoji(pnl: float) -> str:
    if pnl > 0:
        return "盈利"
    elif pnl < 0:
        return "亏损"
    return "持平"


async def write_trade_note(trade: dict, llm_review: dict | None = None):
    """Write a trade note in Obsidian markdown format.

    trade dict expects:
        ticker, strategy, entry_price, exit_price, quantity,
        pnl, pnl_pct, reason, timestamp
    """
    try:
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

        ticker = trade.get("ticker", "UNKNOWN")
        strategy = trade.get("strategy", "unknown")
        pnl = trade.get("pnl", 0)
        pnl_pct = trade.get("pnl_pct", 0)
        ts = trade.get("timestamp", datetime.now(timezone.utc).isoformat())

        # Filename: 2026-05-07_143022_NVDA_breakout.md (unique per trade)
        now = datetime.now(timezone.utc)
        filename = f"{now.strftime('%Y-%m-%d_%H%M%S')}_{ticker}_{strategy}.md"
        filepath = JOURNAL_DIR / filename

        # Obsidian frontmatter
        outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"
        tags = f"[trades, {ticker.lower()}, {strategy}, {outcome}]"

        content = f"""---
ticker: {ticker}
strategy: {strategy}
pnl: {pnl}
pnl_pct: {pnl_pct}
outcome: {outcome}
date: {date_str}
tags: {tags}
---

# {ticker} {strategy} {'盈利' if pnl > 0 else '亏损' if pnl < 0 else '持平'}

## 交易详情

| 项目 | 值 |
|------|-----|
| 股票 | {ticker} |
| 策略 | {strategy} |
| 入场价 | ${trade.get('entry_price', 0):.2f} |
| 出场价 | ${trade.get('exit_price', 0):.2f} |
| 数量 | {trade.get('quantity', 0)} |
| 盈亏 | ${pnl:.2f} ({pnl_pct:+.2f}%) |
| 出场原因 | {trade.get('reason', '—')} |
| 时间 | {ts} |

## 入场逻辑

{trade.get('entry_reason', trade.get('reason', '—'))}

## 出场逻辑

{trade.get('reason', '—')}

"""
        # LLM 复盘
        if llm_review and not llm_review.get("error"):
            content += f"""## LLM 复盘

- **评级**: {_format_grade(llm_review.get('trade_grade', '—'))}
- **成功之处**: {llm_review.get('what_worked', '—')}
- **失败之处**: {llm_review.get('what_failed', '—')}
- **错误**: {llm_review.get('mistake', '—')}
- **改进建议**: {llm_review.get('suggestion', '—')}

"""
        else:
            content += "## LLM 复盘\n\n*LLM 未生成复盘*\n\n"

        content += f"""## 经验总结

*待手动填写*

## 关联标签

#{ticker.lower()} #{strategy} #{outcome} #trades
"""

        filepath.write_text(content, encoding="utf-8")
        logger.info("Trade note saved: %s", filepath)
        return str(filepath)

    except Exception as e:
        logger.error("Failed to write trade note: %s", e)
        return None
