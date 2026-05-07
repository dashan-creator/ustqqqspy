from __future__ import annotations

import asyncio
import logging
from collections import deque

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_pipeline = None
_message_queue: deque[str] = deque(maxlen=50)  # 最多积存50条
_last_update_id = 0


def set_pipeline(pipeline):
    global _pipeline
    _pipeline = pipeline


async def send_message(text: str):
    """发送消息，失败时加入队列等待重试。"""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": settings.telegram_chat_id, "text": text},
            )
            if resp.status_code == 200:
                logger.debug("Telegram sent: %s", text[:50])
                return
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
    # 发送失败，加入队列
    _message_queue.append(text)
    logger.info("Message queued (%d pending)", len(_message_queue))


async def flush_queue():
    """尝试发送积存的消息。"""
    if not _message_queue:
        return
    sent = 0
    while _message_queue:
        msg = _message_queue[0]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": settings.telegram_chat_id, "text": msg},
                )
                if resp.status_code == 200:
                    _message_queue.popleft()
                    sent += 1
                    await asyncio.sleep(0.5)  # 避免限流
                    continue
        except Exception:
            break
        break
    if sent > 0:
        logger.info("Flushed %d queued messages", sent)


async def _handle_command(text: str, chat_id: str):
    if str(chat_id) != str(settings.telegram_chat_id):
        return

    cmd = text.strip().lower()
    if cmd == "/status" and _pipeline:
        s = await _pipeline.get_status()
        msg = (
            f"系统: {'运行中' if not s['circuit_breaker_paused'] else '已暂停'}\n"
            f"资金: ${s['cash']:,.2f}\n"
            f"持仓: {len(s['positions'])}\n"
            f"盈亏: ${s.get('daily_pnl', 0):,.2f}"
        )
        await send_message(msg)
    elif cmd == "/pnl" and _pipeline:
        stats = _pipeline.trader.get_stats()
        msg = (
            f"总盈亏: ${stats['total_pnl']:,.2f}\n"
            f"交易: {stats['total_trades']} (胜{stats['wins']} 负{stats['losses']})\n"
            f"胜率: {stats['win_rate']:.0%}"
        )
        await send_message(msg)
    elif cmd == "/positions" and _pipeline:
        positions = _pipeline.trader.positions
        if not positions:
            await send_message("无持仓")
        else:
            lines = [f"{t}: {p['quantity']}股 @ ${p['avg_price']:.2f} [{p['strategy']}]" for t, p in positions.items()]
            await send_message("\n".join(lines))
    elif cmd == "/pause" and _pipeline:
        _pipeline.circuit_breaker.pause("Telegram手动暂停")
        await send_message("交易已暂停")
    elif cmd == "/resume" and _pipeline:
        _pipeline.circuit_breaker.resume()
        await send_message("交易已恢复")
    elif cmd == "/risk" and _pipeline:
        s = await _pipeline.get_status()
        msg = f"熔断: {'开启' if s['circuit_breaker_paused'] else '关闭'}\n连续亏损: {s.get('consecutive_losses', 0)}笔"
        await send_message(msg)
    elif cmd == "/signals" and _pipeline:
        results = _pipeline.last_scan_results
        if not results:
            await send_message("无最近信号")
        else:
            lines = [f"{r.get('type')}: {r.get('ticker', 'N/A')}" for r in results[-5:]]
            await send_message("\n".join(lines))
    elif cmd == "/help":
        await send_message(
            "/status 系统状态\n/pnl 盈亏\n/positions 持仓\n"
            "/pause 暂停\n/resume 恢复\n/risk 风控\n/signals 信号"
        )


async def _poll_loop():
    """轮询 Telegram 命令 + 定时刷队列。"""
    global _last_update_id
    while True:
        try:
            # 先刷积存消息
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
    """启动 Telegram 轮询（后台任务）。"""
    if not settings.telegram_bot_token:
        logger.warning("No Telegram token, skipping")
        return
    asyncio.create_task(_poll_loop())
    logger.info("Telegram bot polling started (queue max: 50)")
