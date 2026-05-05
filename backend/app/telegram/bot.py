from __future__ import annotations

import logging

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import settings

logger = logging.getLogger(__name__)

_pipeline = None


def _authorized(update: Update) -> bool:
    return bool(settings.telegram_chat_id) and str(update.effective_chat.id) == str(settings.telegram_chat_id)


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
    if not _authorized(update):
        await update.message.reply_text('Forbidden')
        return
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
    if not _authorized(update):
        await update.message.reply_text('Forbidden')
        return
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
    if not _authorized(update):
        await update.message.reply_text('Forbidden')
        return
    if not _pipeline:
        return
    _pipeline.circuit_breaker.pause("Manual pause via Telegram")
    await update.message.reply_text("Trading PAUSED")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        await update.message.reply_text('Forbidden')
        return
    if not _pipeline:
        return
    _pipeline.circuit_breaker.resume()
    await update.message.reply_text("Trading RESUMED")


async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        await update.message.reply_text('Forbidden')
        return
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
    if not _authorized(update):
        await update.message.reply_text('Forbidden')
        return
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
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured, skipping message")
        return
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
