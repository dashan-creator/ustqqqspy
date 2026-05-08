from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.pipeline.scanner import scanner_pipeline
from app.telegram.bot import send_message


def _get_position_monitor():
    from app.pipeline.position_monitor import position_monitor
    return position_monitor

logger = logging.getLogger(__name__)


async def scan_job():
    now = datetime.now(timezone.utc)
    hour = now.hour

    if hour < 13 or hour > 20:
        return

    # Reset daily/weekly PnL at appropriate boundaries
    if not hasattr(scanner_pipeline.trader, "_last_reset_date"):
        scanner_pipeline.trader._last_reset_date = now.date()
        scanner_pipeline.trader._last_reset_week = now.isocalendar()[1]

    if scanner_pipeline.trader._last_reset_date != now.date():
        scanner_pipeline.trader.daily_pnl = 0.0
        scanner_pipeline.trader._last_reset_date = now.date()

    current_week = now.isocalendar()[1]
    if scanner_pipeline.trader._last_reset_week != current_week:
        scanner_pipeline.trader.weekly_pnl = 0.0
        scanner_pipeline.trader._last_reset_week = current_week

    logger.info("Running scan...")
    events = await scanner_pipeline.run_scan()

    # Check open positions for stop-loss / take-profit
    position_monitor = _get_position_monitor()
    if position_monitor:
        close_events = await position_monitor.check_positions()
        for event in close_events:
            etype = event.get("type", "")
            if etype == "position_closed":
                msg = (
                    f"CLOSED: {event.get('ticker', '?')} @ ${event.get('exit_price', 0):.2f}\n"
                    f"Reason: {event.get('reason', '')}\n"
                    f"PnL: ${event.get('pnl', 0):.2f} ({event.get('pnl_pct', 0):.2f}%)"
                )
                await send_message(msg)
            elif etype == "position_close_failed":
                await send_message(f"CLOSE FAILED: {event.get('ticker', '?')} — {event.get('reason', '')}")
        events.extend(close_events)

        # LLM 持仓分析（有持仓时）
        stats = scanner_pipeline.trader.get_stats()
        account_state = f"资金: ${scanner_pipeline.trader.cash:,.2f}\n总盈亏: ${stats['total_pnl']:,.2f}\n胜率: {stats['win_rate']:.0%}"
        review = await position_monitor.review_positions(account_state=account_state)
        if review:
            await send_message(review)

    # Send scanner events (excluding position_closed which was already sent above)
    for event in events:
        etype = event.get("type", "")
        if etype == "position_closed" or etype == "position_close_failed":
            continue  # Already handled above
        if etype == "signal_executed":
            msg = (
                f"SIGNAL: {event['ticker']} {event.get('direction', '').upper()}\n"
                f"Strategy: {event.get('strategy', '')}\n"
                f"Price: ${event.get('entry_price', 0):.2f}\n"
                f"Stop: ${event.get('stop_loss', 0):.2f}\n"
                f"Qty: {event.get('quantity', 0)}\n"
                f"LLM: {event.get('llm_action', 'N/A')} (risk={event.get('llm_risk_score', '?')})"
            )
            await send_message(msg)
        elif etype == "signal_rejected":
            await send_message(f"REJECTED: {event.get('ticker', '?')} [{event.get('strategy', '')}] — {event.get('reason', '')}")
        elif etype == "signal_pending":
            await send_message(f"PENDING: {event.get('ticker', '?')} — {event.get('reason', '')}")

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


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scan_job, "interval", minutes=settings.scan_interval_minutes, id="market_scan")
    scheduler.add_job(daily_report_job, "cron", hour=20, minute=5, id="daily_report")
    return scheduler
