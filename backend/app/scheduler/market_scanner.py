from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.pipeline.scanner import scanner_pipeline
from app.pipeline.position_monitor import position_monitor
from app.telegram.bot import send_message

logger = logging.getLogger(__name__)


async def scan_job():
    now = datetime.now(timezone.utc)
    hour = now.hour

    if hour < 13 or hour > 20:
        return

    logger.info("Running scan...")
    events = await scanner_pipeline.run_scan()

    # Check open positions for stop-loss / take-profit
    if position_monitor:
        close_events = await position_monitor.check_positions()
        for event in close_events:
            msg = (
                f"CLOSED: {event['ticker']} @ ${event['exit_price']:.2f}\n"
                f"Reason: {event['reason']}\n"
                f"PnL: ${event['pnl']:.2f} ({event['pnl_pct']:.2f}%)"
            )
            await send_message(msg)
        events.extend(close_events)

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


async def daily_report_job():
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


async def position_review_job():
    """每30分钟让 LLM 审视所有持仓，结果推送到 Telegram。"""
    from app.market.data_service import market_data_service
    from app.llm.unified import position_review

    positions = scanner_pipeline.trader.positions
    if not positions:
        return

    now = datetime.now(timezone.utc)
    if now.hour < 13 or now.hour > 20:
        return

    # 构建持仓数据
    pos_list = []
    news_lines = []
    for ticker, pos in positions.items():
        quote = await market_data_service.get_quote(ticker)
        current_price = quote.get("price", pos["avg_price"])
        pnl_pct = ((current_price - pos["avg_price"]) / pos["avg_price"]) * 100 if pos["avg_price"] > 0 else 0
        pos_list.append({
            "ticker": ticker,
            "strategy": pos.get("strategy", ""),
            "quantity": pos.get("quantity", 0),
            "avg_price": pos.get("avg_price", 0),
            "current_price": current_price,
            "pnl_pct": round(pnl_pct, 2),
            "stop_loss": pos.get("stop_loss", 0),
            "take_profit": pos.get("take_profit", 0),
        })

    market = await market_data_service.get_market_context("QQQ")
    market_state = f"QQQ {market['change_pct']:+.2f}%, {'看涨' if market['is_bullish'] else '看跌'}"

    stats = scanner_pipeline.trader.get_stats()
    account_state = f"资金: ${scanner_pipeline.trader.cash:,.2f}\n总盈亏: ${stats['total_pnl']:,.2f}\n胜率: {stats['win_rate']:.0%}"

    try:
        report = await position_review(
            positions=pos_list,
            market_state=market_state,
            account_state=account_state,
        )
        await send_message(report)
        logger.info("Position review sent to Telegram")
    except Exception as e:
        logger.warning("Position review failed: %s", e)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scan_job, "interval", minutes=settings.scan_interval_minutes, id="market_scan")
    scheduler.add_job(position_review_job, "interval", minutes=30, id="position_review")
    scheduler.add_job(daily_report_job, "cron", hour=20, minute=5, id="daily_report")
    return scheduler
