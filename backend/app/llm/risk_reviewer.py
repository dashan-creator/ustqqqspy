from __future__ import annotations

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
    user_prompt = (
        f"交易信号:\n- 股票: {ticker}\n- 策略: {strategy}\n"
        f"- 入场价: {entry_price}\n- 止损: {stop_loss}\n"
        f"- 仓位: {position_pct}%\n- 大盘: {market_state}\n"
        f"- 新闻: {news_summary}"
    )
    return await chat(SYSTEM_PROMPT, user_prompt, timeout=30.0)
