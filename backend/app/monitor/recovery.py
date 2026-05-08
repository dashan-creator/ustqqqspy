from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.market.data_service import market_data_service

logger = logging.getLogger(__name__)

# 断线期间价格变动超过此比例，直接清仓
EMERGENCY_CLOSE_PCT = 0.05  # 5%


async def sync_after_reconnect(trader, broker, position_monitor=None) -> list[str]:
    """IBKR 重连后同步持仓状态，立即设止损，异常仓位清仓。"""
    actions = []

    if not broker or not broker.is_connected:
        actions.append("IBKR not connected, skip sync")
        return actions

    # 1. 同步账户资金
    try:
        account = await broker.get_account_summary()
        ibkr_cash = account.get("TotalCashValue", trader.cash)
        trader.cash = ibkr_cash
        actions.append(f"Synced cash: ${ibkr_cash:,.2f}")
    except Exception as e:
        actions.append(f"Failed to sync cash: {e}")

    # 2. 获取 IBKR 实际持仓
    try:
        ibkr_positions = await broker.get_positions()
    except Exception as e:
        actions.append(f"Failed to get IBKR positions: {e}")
        return actions

    ibkr_tickers = {p["ticker"] for p in ibkr_positions}

    # 3. 本地有但 IBKR 没有的 → 清除（断线期间被平仓了）
    for ticker in list(trader.positions.keys()):
        if ticker not in ibkr_tickers:
            logger.warning("Position %s exists locally but not in IBKR, removing", ticker)
            del trader.positions[ticker]
            actions.append(f"Removed stale local position: {ticker}")

    # 4. 处理 IBKR 实际持仓
    for ibkr_pos in ibkr_positions:
        ticker = ibkr_pos["ticker"]
        quantity = ibkr_pos["quantity"]
        avg_price = ibkr_pos["avg_price"]

        # 获取当前价格
        try:
            quote = await market_data_service.get_quote(ticker)
            current_price = quote.get("price", 0)
        except Exception:
            current_price = 0

        if current_price <= 0:
            actions.append(f"{ticker}: no current price, keep position as-is")
            continue

        # 计算断线期间盈亏
        pnl_pct = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0

        # 5. 异常仓位：亏损超过阈值，直接清仓
        if pnl_pct < -(EMERGENCY_CLOSE_PCT * 100):
            logger.warning("EMERGENCY CLOSE %s: %.2f%% loss exceeds threshold", ticker, pnl_pct)
            try:
                await broker.place_market_order(ticker, quantity, "sell")
                if ticker in trader.positions:
                    del trader.positions[ticker]
                actions.append(f"EMERGENCY CLOSED {ticker}: {pnl_pct:+.1f}% loss (>{EMERGENCY_CLOSE_PCT*100}%)")
            except Exception as e:
                actions.append(f"Emergency close failed for {ticker}: {e}")
            continue

        # 6. 同步或创建本地持仓
        if ticker not in trader.positions:
            # IBKR 有但本地没有 → 创建并设止损
            from app.market.indicators import atr as calc_atr
            bars = await market_data_service.get_bars(ticker, interval="15m", period="5d")
            atr_val = 0
            if not bars.empty and len(bars) > 1:
                import numpy as np
                highs = bars["high"].values
                lows = bars["low"].values
                closes = bars["close"].values
                atr_val = calc_atr(highs, lows, closes, period=min(14, len(closes) - 1))

            if atr_val <= 0:
                atr_val = current_price * 0.02

            stop_loss = current_price - 1.5 * atr_val
            take_profit = current_price + 3.0 * atr_val

            trader.positions[ticker] = {
                "quantity": quantity,
                "avg_price": avg_price,
                "strategy": "reconnected",
                "stop_loss": round(stop_loss, 2),
                "take_profit": round(take_profit, 2),
                "atr": round(atr_val, 2),
                "entry_reason": "Position from IBKR, auto-set stop on reconnect",
            }
            actions.append(f"Synced {ticker}: {quantity} @ ${avg_price:.2f}, stop=${stop_loss:.2f}")
        else:
            # 更新数量（可能断线期间有部分成交）
            trader.positions[ticker]["quantity"] = quantity
            trader.positions[ticker]["avg_price"] = avg_price
            actions.append(f"Updated {ticker}: qty={quantity}, avg=${avg_price:.2f}")

    # 7. 保存状态
    trader._save()
    actions.append("State saved after reconnect sync")

    return actions
