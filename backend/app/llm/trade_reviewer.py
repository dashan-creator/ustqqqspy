from __future__ import annotations

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
    user_prompt = (
        f"交易记录:\n- 股票: {ticker}\n- 策略: {strategy}\n"
        f"- 入场价: {entry_price}\n- 出场价: {exit_price}\n"
        f"- 盈亏: {pnl_pct:.2f}%\n- 入场理由: {entry_reason}\n"
        f"- 出场理由: {exit_reason}"
    )
    return await chat(SYSTEM_PROMPT, user_prompt, timeout=30.0)
