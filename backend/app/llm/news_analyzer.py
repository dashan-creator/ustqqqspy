from __future__ import annotations

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
    user_prompt = f"股票: {ticker}\n新闻: {headline}\n价格变动: {price_change}\n大盘: {market_state}"
    return await chat(SYSTEM_PROMPT, user_prompt, timeout=15.0)
