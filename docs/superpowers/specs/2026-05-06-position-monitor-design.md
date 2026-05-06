# 持仓监控与自动平仓设计

> 完善自动交易闭环：开仓 → 监控 → 平仓 → 复盘

## 1. 目标

补全当前系统的"开环"问题——信号可以开仓但没有自动平仓机制。实现：
- 止损自动执行
- 止盈自动执行
- 移动止盈（trailing stop）
- 平仓后 LLM 复盘

## 2. 架构

```
调度器 (每 5 分钟)
    │
    ├── ScannerPipeline.run_scan()     ← 已有：扫描信号、开仓
    │
    └── PositionMonitor.check_positions()  ← 新增：检查持仓、平仓
            │
            ├── 止损触发? → 平仓
            ├── 止盈触发? → 平仓
            ├── 移动止盈? → 更新追踪 → 可能平仓
            │
            └── 平仓后:
                ├── persist_trade()        ← 已有
                ├── LLM trade_reviewer     ← 已有
                ├── 更新 daily_pnl
                └── 更新 consecutive_losses
```

## 3. PositionMonitor 类

```python
class PositionMonitor:
    def __init__(self, trader, order_manager, ibkr_broker=None):
        self.trader = trader
        self.order_manager = order_manager
        self.ibkr_broker = ibkr_broker
        self.highest_prices: dict[str, float] = {}  # ticker → 最高价追踪

    async def check_positions(self) -> list[dict]:
        """检查所有持仓，执行止损/止盈。返回平仓事件列表。"""
        events = []
        for ticker, pos in list(self.trader.positions.items()):
            current_price = self._get_current_price(ticker)
            if current_price <= 0:
                continue

            # 更新最高价追踪
            self.highest_prices[ticker] = max(
                self.highest_prices.get(ticker, 0), current_price
            )

            # 检查止损
            if self._check_stop_loss(ticker, current_price, pos):
                event = await self._close_position(ticker, current_price, "止损触发")
                events.append(event)
                continue

            # 检查止盈
            if self._check_take_profit(ticker, current_price, pos):
                event = await self._close_position(ticker, current_price, "止盈触发")
                events.append(event)
                continue

            # 检查移动止盈
            if self._check_trailing_stop(ticker, current_price, pos):
                event = await self._close_position(ticker, current_price, "移动止盈触发")
                events.append(event)

        return events
```

## 4. 止损/止盈逻辑

### 4.1 止损

```python
def _check_stop_loss(self, ticker, current_price, pos) -> bool:
    stop = pos.get("stop_loss", 0)
    return stop > 0 and current_price <= stop
```

### 4.2 止盈

```python
def _check_take_profit(self, ticker, current_price, pos) -> bool:
    tp = pos.get("take_profit", 0)
    return tp > 0 and current_price >= tp
```

### 4.3 移动止盈

```python
def _check_trailing_stop(self, ticker, current_price, pos) -> bool:
    """价格从最高点回落 1.5x ATR 则触发"""
    highest = self.highest_prices.get(ticker, 0)
    if highest <= 0:
        return False
    atr = pos.get("atr", current_price * 0.02)
    trailing_stop = highest - 1.5 * atr
    return current_price <= trailing_stop
```

## 5. 平仓流程

```python
async def _close_position(self, ticker, current_price, reason) -> dict:
    pos = self.trader.positions[ticker]
    quantity = pos["quantity"]

    # 执行平仓
    if self.ibkr_broker and self.ibkr_broker.is_connected:
        order = await self.ibkr_broker.place_market_order(ticker, quantity, "sell")
    else:
        order = self.trader.sell(ticker, quantity, current_price, reason)

    # 持久化
    await persist_trade(order)

    # LLM 复盘
    try:
        review = await review_trade(
            ticker=ticker,
            strategy=pos.get("strategy", ""),
            entry_price=pos.get("avg_price", 0),
            exit_price=current_price,
            pnl_pct=((current_price - pos["avg_price"]) / pos["avg_price"]) * 100,
            entry_reason=pos.get("entry_reason", ""),
            exit_reason=reason,
        )
    except Exception:
        review = {}

    # 更新统计
    pnl = (current_price - pos["avg_price"]) * quantity
    self.trader.daily_pnl += pnl
    if pnl < 0:
        self.trader.consecutive_losses += 1
    else:
        self.trader.consecutive_losses = 0

    # 清理追踪
    self.highest_prices.pop(ticker, None)

    return {
        "type": "position_closed",
        "ticker": ticker,
        "exit_price": current_price,
        "pnl": round(pnl, 2),
        "reason": reason,
        "llm_review": review,
    }
```

## 6. 集成到调度器

修改 `scheduler/market_scanner.py`：

```python
from app.pipeline.position_monitor import position_monitor

async def scan_job():
    # ... existing scan logic ...
    events = await scanner_pipeline.run_scan()

    # 新增：检查持仓
    close_events = await position_monitor.check_positions()
    for event in close_events:
        await send_message(f"平仓: {event['ticker']} @ ${event['exit_price']} [{event['reason']}] PnL: ${event['pnl']}")
        events.append(event)
```

## 7. 开仓时记录止损/止盈

修改 scanner.py 开仓逻辑，在 positions dict 中存入止损/止盈：

```python
self.trader.positions[ticker] = {
    "quantity": quantity,
    "avg_price": price,
    "strategy": strategy,
    "stop_loss": signal["stop_loss"],
    "take_profit": signal["take_profit"],
    "entry_reason": signal.get("reason", ""),
}
```

## 8. 前端持仓展示

更新 Dashboard 展示未平仓持仓的实时盈亏：

```tsx
// positions 表格显示
// ticker | 数量 | 入场价 | 当前价 | 未实现盈亏 | 止损 | 止盈
```

## 9. 测试策略

- 止损触发测试：mock current_price < stop_loss → 验证平仓
- 止盈触发测试：mock current_price > take_profit → 验证平仓
- 移动止盈测试：价格先涨后跌 → 验证 trailing stop 触发
- 无触发测试：价格在止损止盈之间 → 验证不平仓
- LLM 复盘测试：平仓后验证 review_trade 被调用
- 统计更新测试：验证 daily_pnl 和 consecutive_losses 正确更新

## 10. 文件清单

| 文件 | 操作 |
|------|------|
| `backend/app/pipeline/position_monitor.py` | 新建 |
| `backend/app/pipeline/scanner.py` | 修改：开仓时存入 stop_loss/take_profit |
| `backend/app/scheduler/market_scanner.py` | 修改：加入持仓检查 |
| `backend/tests/test_position_monitor.py` | 新建 |
| `frontend/src/app/page.tsx` | 修改：持仓表格 |
