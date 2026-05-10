from __future__ import annotations

import logging

from app.llm.client import chat

logger = logging.getLogger(__name__)


# === 开仓时：合并新闻分析 + 风险审查 ===

PRE_TRADE_PROMPT = """你是一个美股交易分析助手。根据以下信息，一次性完成两个任务：
1. 分析新闻事件（类型、情感、影响）
2. 评估交易风险并给出决策

输出严格JSON格式：
{
    "event_type": "guidance_raise|earnings_beat|upgrade|downgrade|product_launch|regulatory|other|none",
    "sentiment": "positive|negative|neutral",
    "impact_score": 1-5,
    "risk_score": 1-10,
    "action": "approve|reduce_size|reject",
    "suggested_position_pct": 0-2,
    "reason": "中文说明，包括新闻分析和风险评估",
    "risk_flags": ["..."]
}"""


async def pre_trade_analysis(
    ticker: str,
    strategy: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    position_pct: float,
    market_state: str,
    rsi: float,
    atr: float,
    volume_ratio: float,
    news_headlines: str,
    current_positions: str,
    account_state: str,
    last_trade_review: str = "",
) -> dict:
    """开仓前一次调用：新闻分析 + 风险审查。"""
    user_prompt = f"""交易信号:
- 股票: {ticker}
- 策略: {strategy}
- 入场价: {entry_price}
- 止损: {stop_loss}
- 止盈: {take_profit}
- 仓位: {position_pct}%

市场指标:
- RSI: {rsi:.1f}
- ATR: {atr:.2f}
- 成交量比: {volume_ratio:.1f}x
- 大盘: {market_state}

新闻:
{news_headlines if news_headlines else "无相关新闻"}

当前持仓:
{current_positions if current_positions else "无持仓"}

账户状态:
{account_state}"""

    if last_trade_review:
        user_prompt += f"\n\n上次交易复盘（参考）:\n{last_trade_review}"

    return await chat(PRE_TRADE_PROMPT, user_prompt, timeout=30.0)


# === 平仓时：交易复盘 ===

POST_TRADE_PROMPT = """你是一个交易复盘专家。分析已完成的交易，给出评级和改进建议。
输出严格JSON格式：
{
    "trade_grade": "A|B|C|D|F",
    "what_worked": "中文",
    "what_failed": "中文",
    "mistake": "中文",
    "suggestion": "中文",
    "key_lesson": "一句话核心教训"
}"""


async def post_trade_review(
    ticker: str,
    strategy: str,
    entry_price: float,
    exit_price: float,
    pnl_pct: float,
    entry_reason: str,
    exit_reason: str,
    hold_duration: str = "",
) -> dict:
    """平仓后一次调用：交易复盘。"""
    user_prompt = f"""交易记录:
- 股票: {ticker}
- 策略: {strategy}
- 入场价: {entry_price}
- 出场价: {exit_price}
- 盈亏: {pnl_pct:+.2f}%
- 入场理由: {entry_reason}
- 出场理由: {exit_reason}
- 持仓时长: {hold_duration}"""

    return await chat(POST_TRADE_PROMPT, user_prompt, timeout=30.0)


# === 持仓分析：定期审视所有持仓 ===

POSITION_REVIEW_PROMPT = """你是一个美股持仓分析师。分析当前所有持仓，结合大盘和个股情况给出操作建议。

要求：
1. 逐个分析每只持仓的状态
2. 结合大盘趋势判断风险
3. 给出明确操作建议

输出格式（中文，简洁直接）：

📊 持仓分析报告

【大盘】
- 趋势判断和风险提示

【逐个持仓】
每个持仓格式：
{股票} | {策略} | 盈亏 {百分比}
→ 建议：持有/减仓/止盈/止损
→ 原因：一句话

【总评】
- 整体风险等级：低/中/高
- 建议操作：持有/减仓/暂停新仓

保持简洁，每只股票不超过2行。"""


async def position_review(
    positions: list[dict],
    market_state: str,
    account_state: str,
    news_summary: str = "",
) -> str:
    """分析所有持仓，返回中文报告（直接发 Telegram）。"""
    if not positions:
        return "📊 当前无持仓"

    pos_text = ""
    for p in positions:
        pnl_pct = p.get("pnl_pct", 0)
        pos_text += (
            f"\n{p['ticker']} | {p['strategy']} | "
            f"数量: {p['quantity']} | 入场: ${p['avg_price']:.2f} | "
            f"当前: ${p.get('current_price', p['avg_price']):.2f} | "
            f"盈亏: {pnl_pct:+.1f}% | "
            f"止损: ${p.get('stop_loss', 0):.2f} | 止盈: ${p.get('take_profit', 0):.2f}"
        )

    user_prompt = f"""当前持仓:
{pos_text}

大盘:
{market_state}

账户:
{account_state}

新闻:
{news_summary if news_summary else "无重大新闻"}"""

    result = await chat(
        POSITION_REVIEW_PROMPT,
        user_prompt,
        timeout=15.0,
        max_tokens=1200,
        json_mode=False,
    )

    if isinstance(result, dict):
        return result.get("content", "") or result.get("reason", str(result))
    return str(result)
