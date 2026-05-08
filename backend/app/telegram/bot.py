from __future__ import annotations

import asyncio
import logging
from collections import deque

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_pipeline = None
_message_queue: deque[str] = deque(maxlen=50)
_last_update_id = 0
_poll_task: asyncio.Task | None = None
_running = False


def set_pipeline(pipeline):
    global _pipeline
    _pipeline = pipeline


async def send_message(text: str):
    """Send message to configured Telegram chat. Queue on failure."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": settings.telegram_chat_id, "text": text, "parse_mode": "Markdown"},
            )
            if resp.status_code == 200:
                return
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
    _message_queue.append(text)
    logger.info("Message queued (%d pending)", len(_message_queue))


async def flush_queue():
    """Flush queued messages when connection is available."""
    if not _message_queue:
        return
    sent = 0
    while _message_queue:
        msg = _message_queue[0]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": settings.telegram_chat_id, "text": msg, "parse_mode": "Markdown"},
                )
                if resp.status_code == 200:
                    _message_queue.popleft()
                    sent += 1
                    await asyncio.sleep(0.5)
                    continue
        except Exception:
            break
        break
    if sent > 0:
        logger.info("Flushed %d queued messages", sent)


def _auth(chat_id: str) -> bool:
    return bool(settings.telegram_chat_id) and str(chat_id) == str(settings.telegram_chat_id)


async def _handle_command(text: str, chat_id: str):
    if not _auth(chat_id):
        await _send("未授权")
        return

    cmd = text.strip().lower()

    if cmd == "/start" or cmd == "/help":
        await _send(
            "📊 *USStock 交易系统*\n\n"
            "*/status* - 系统状态\n"
            "*/pnl* - 盈亏统计\n"
            "*/positions* - 当前持仓\n"
            "*/signals* - 最新信号\n"
            "*/risk* - 风控状态\n"
            "*/pause* - 暂停交易\n"
            "*/resume* - 恢复交易\n"
            "*/close TICKER* - 手动平仓\n"
            "*/analyze TICKER* - LLM 分析个股\n"
            "*/balance* - 账户余额\n"
            "*/trades* - 最近交易\n"
        )

    elif cmd == "/status":
        s = await _get_status()
        if s:
            broker = s.get("broker", "paper")
            broker_icon = "🟢" if broker == "ibkr" else "🟡"
            status_icon = "🟢" if not s["circuit_breaker_paused"] else "🔴"
            await _send(
                f"{status_icon} *系统状态*\n\n"
                f"模式: {broker_icon} {broker.upper()}\n"
                f"资金: ${s['cash']:,.2f}\n"
                f"持仓: {len(s['positions'])} 只\n"
                f"当日盈亏: ${s['daily_pnl']:,.2f}\n"
                f"连续亏损: {s['consecutive_losses']} 笔\n"
                f"总盈亏: ${s['stats']['total_pnl']:,.2f}\n"
                f"胜率: {s['stats']['win_rate']:.0%}"
            )

    elif cmd == "/pnl":
        s = await _get_status()
        if s:
            st = s["stats"]
            await _send(
                f"📈 *盈亏统计*\n\n"
                f"总盈亏: ${st['total_pnl']:,.2f}\n"
                f"交易次数: {st['total_trades']}\n"
                f"盈利: {st['wins']} 笔\n"
                f"亏损: {st['losses']} 笔\n"
                f"胜率: {st['win_rate']:.0%}\n"
                f"可用资金: ${s['cash']:,.2f}"
            )

    elif cmd == "/positions":
        s = await _get_status()
        if s and s["positions"]:
            lines = []
            for t, p in s["positions"].items():
                sl = p.get('stop_loss', 0)
                tp = p.get('take_profit', 0)
                lines.append(
                    f"*{t}* | {p['quantity']:.4f} 股\n"
                    f"  入场: ${p.get('avg_price', 0):.2f} | 止损: ${sl:.2f} | 止盈: ${tp:.2f}\n"
                    f"  策略: {p.get('strategy', '?')}"
                )
            await _send("📋 *当前持仓*\n\n" + "\n\n".join(lines))
        else:
            await _send("📋 无持仓")

    elif cmd == "/signals":
        s = await _get_status()
        if s and hasattr(_pipeline, "last_scan_results") and _pipeline.last_scan_results:
            lines = []
            for r in _pipeline.last_scan_results[-5:]:
                t = r.get("type", "?")
                ticker = r.get("ticker", "")
                reason = r.get("reason", r.get("strategy", ""))
                lines.append(f"• `{t}` {ticker} — {reason}")
            await _send("📡 *最新信号*\n\n" + "\n".join(lines))
        else:
            await _send("📡 无最近信号")

    elif cmd == "/risk":
        s = await _get_status()
        if s:
            cb_icon = "🔴" if s["circuit_breaker_paused"] else "🟢"
            await _send(
                f"🛡️ *风控状态*\n\n"
                f"熔断: {cb_icon} {'开启' if s['circuit_breaker_paused'] else '关闭'}\n"
                f"原因: {s['circuit_breaker_reason'] or '无'}\n"
                f"连续亏损: {s['consecutive_losses']} 笔\n"
                f"当日盈亏: ${s['daily_pnl']:,.2f}"
            )

    elif cmd == "/pause":
        if _pipeline:
            _pipeline.circuit_breaker.pause("Telegram 手动暂停")
            await _send("⏸️ 交易已暂停")

    elif cmd == "/resume":
        if _pipeline:
            _pipeline.circuit_breaker.resume()
            await _send("▶️ 交易已恢复")

    elif cmd.startswith("/close "):
        ticker = cmd.split(" ", 1)[1].strip().upper()
        if _pipeline and ticker in _pipeline.trader.positions:
            pos = _pipeline.trader.positions[ticker]
            from app.market.data_service import market_data_service
            quote = await market_data_service.get_quote(ticker)
            price = quote.get("price", pos["avg_price"])
            pnl = (price - pos["avg_price"]) * pos["quantity"]
            _pipeline.trader.sell(ticker, pos["quantity"], price, "Telegram手动平仓")
            _pipeline.trader._save()
            await _send(
                f"✅ *已平仓 {ticker}*\n\n"
                f"入场: ${pos['avg_price']:.2f}\n"
                f"出场: ${price:.2f}\n"
                f"盈亏: ${pnl:+.2f} ({pnl/pos['avg_price']*100:+.2f}%)"
            )
        else:
            await _send(f"❌ 无 {ticker} 持仓")

    elif cmd.startswith("/analyze "):
        ticker = cmd.split(" ", 1)[1].strip().upper()
        await _send(f"🔍 正在分析 {ticker}...")
        try:
            from app.market.data_service import market_data_service
            from app.market.indicators import atr, rsi
            import numpy as np

            quote = await market_data_service.get_quote(ticker)
            bars = await market_data_service.get_bars(ticker, interval="15m", period="5d")
            if bars.empty:
                await _send(f"❌ 无法获取 {ticker} 数据")
                return

            closes = bars["close"].values
            indicators = market_data_service.compute_indicators(bars)

            from app.llm.unified import position_review
            pos_list = [{
                "ticker": ticker,
                "strategy": "分析",
                "quantity": 0,
                "avg_price": quote.get("price", 0),
                "current_price": quote.get("price", 0),
                "pnl_pct": 0,
                "stop_loss": 0,
                "take_profit": 0,
            }]
            report = await position_review(
                positions=pos_list,
                market_state=f"RSI={indicators['rsi']:.0f}, ATR={indicators['atr']:.2f}",
                account_state=f"价格: ${quote.get('price', 0):.2f}",
            )
            await _send(f"📊 *{ticker} 分析*\n\n{report}")
        except Exception as e:
            await _send(f"❌ 分析失败: {e}")

    elif cmd == "/balance":
        if _pipeline:
            s = await _get_status()
            if s:
                ibkr = s.get("ibkr_account", {})
                if ibkr:
                    await _send(
                        f"💰 *IBKR 账户*\n\n"
                        f"净值: ${ibkr.get('NetLiquidation', 0):,.2f}\n"
                        f"现金: ${ibkr.get('TotalCashValue', 0):,.2f}\n"
                        f"购买力: ${ibkr.get('BuyingPower', 0):,.2f}\n"
                        f"未实现盈亏: ${ibkr.get('UnrealizedPnL', 0):,.2f}"
                    )
                else:
                    await _send(f"💰 纸面资金: ${s['cash']:,.2f}")

    elif cmd == "/trades":
        if _pipeline:
            trades = _pipeline.trader.trades[-5:]
            if trades:
                lines = []
                for t in trades:
                    icon = "🟢" if t.get("pnl", 0) >= 0 else "🔴"
                    lines.append(
                        f"{icon} {t.get('ticker', '?')} | {t.get('strategy', '?')} | "
                        f"${t.get('pnl', 0):+.2f} ({t.get('pnl_pct', 0):+.2f}%)"
                    )
                await _send("📝 *最近交易*\n\n" + "\n".join(lines))
            else:
                await _send("📝 暂无交易记录")


async def _send(text: str):
    """Internal send helper."""
    await send_message(text)


async def _get_status() -> dict | None:
    if not _pipeline:
        return None
    try:
        return await _pipeline.get_status()
    except Exception:
        return None


async def _poll_loop():
    """Poll Telegram for commands and flush queued messages."""
    global _last_update_id, _running
    _running = True
    while _running:
        try:
            await flush_queue()

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates",
                    params={"offset": _last_update_id, "timeout": 20},
                )
                data = resp.json()
                for update in data.get("result", []):
                    _last_update_id = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "")
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    if text.startswith("/"):
                        await _handle_command(text, chat_id)
        except Exception as e:
            logger.warning("Telegram poll error: %s", e)
            await asyncio.sleep(5)


async def start_telegram():
    """Start Telegram polling in background."""
    global _poll_task
    if not settings.telegram_bot_token:
        logger.warning("No Telegram token, skipping")
        return
    _poll_task = asyncio.create_task(_poll_loop())
    logger.info("Telegram bot polling started (queue max: 50)")


async def stop_telegram():
    """Gracefully stop Telegram polling."""
    global _running
    _running = False
    if _poll_task and not _poll_task.done():
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
    logger.info("Telegram bot stopped")
