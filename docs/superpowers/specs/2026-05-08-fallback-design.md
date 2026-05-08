# 网络异常兜底方案设计

> 核心原则：不确定时不开仓，状态不清时暂停交易，恢复后自动同步。

## 1. 异常场景分类

| 场景 | 影响 | 严重度 |
|------|------|--------|
| 行情数据源全部失败 | 无法判断价格，策略失效 | Critical |
| IBKR 连接断开 | 无法下单/平仓 | Critical |
| 完全断网 | 所有外部服务不可用 | Critical |
| LLM 服务不可用 | 无法做风险审查 | High |
| 新闻 API 不可用 | 无法获取事件信息 | Medium |
| Telegram 不可用 | 无法推送通知 | Low |

## 2. 兜底策略

### 2.1 行情数据失败

**检测：** `get_bars()` 和 `get_quote()` 返回空或 0 价格

**兜底：**
- 停止新开仓（策略无法评估）
- 已有持仓继续监控（用最后已知价格 + 缓存）
- 通知用户 "行情数据异常，暂停开新仓"
- 每次扫描重试，恢复后自动继续

```python
# scanner.py
bars = await market_data_service.get_bars(ticker)
if bars.empty:
    logger.warning("No market data for %s, skipping (keep monitoring positions)", ticker)
    continue  # 跳过该 ticker，不产生信号
```

### 2.2 IBKR 连接断开

**检测：** `broker.is_connected` 为 False 或下单超时

**兜底：**
- 停止新开仓
- 已有持仓用纸面模式继续监控止损/止盈
- 自动重连脚本每 60 秒尝试重连
- 重连后同步 IBKR 实际持仓状态
- 通知用户 "IBKR 断开，切换为监控模式"

```python
# position_monitor.py
if not self.ibkr_broker or not self.ibkr_broker.is_connected:
    # 用最后已知价格继续监控止损
    # 如果触发止损，记录到日志但不执行（因为无法下单）
    logger.warning("IBKR disconnected, monitoring only (no execution)")
```

### 2.3 LLM 服务不可用

**检测：** LLM 调用超时或返回错误

**兜底（已实现）：**
- SmartGate 正常条件跳过 LLM
- LLM 失败时按 `reduce_size` 处理（保守降仓）
- 用历史数据和规则逻辑做二次验证
- 不阻塞交易流程

### 2.4 完全断网

**检测：** 所有外部连接失败（行情 + IBKR + LLM + Telegram）

**兜底：**
- 立即停止所有交易活动
- 保存当前状态到磁盘
- 通知用户（如果 Telegram 可用）
- 重连脚本持续尝试
- 恢复后自动同步 IBKR 持仓和市场状态

### 2.5 钱包/账户异常

**检测：** IBKR 返回余额异常、资金不足、账户锁定

**兜底：**
- 资金不足：停止开新仓，继续监控已有持仓
- 账户锁定：停止所有操作，告警用户
- 余额与本地不一致：以 IBKR 为准，同步本地状态

## 3. 实现方案

### 3.1 健康检查模块

新增 `app/monitor/health_check.py`，每分钟检查所有外部依赖状态：

```python
class HealthStatus:
    market_data: bool     # 行情可用
    ibkr_connected: bool  # IBKR 连接
    llm_available: bool   # LLM 可用
    news_available: bool  # 新闻可用
    telegram_available: bool  # Telegram 可用
    network_up: bool      # 网络连通

    @property
    def can_trade(self) -> bool:
        return self.market_data and self.ibkr_connected and self.network_up

    @property
    def can_scan(self) -> bool:
        return self.market_data and self.network_up
```

### 3.2 状态恢复模块

新增 `app/monitor/recovery.py`，断线重连后自动同步：

```python
async def sync_after_reconnect(trader, broker):
    """IBKR 重连后同步实际持仓状态。"""
    ibkr_positions = await broker.get_positions()
    ibkr_account = await broker.get_account_summary()

    # 以 IBKR 为准同步本地状态
    trader.cash = ibkr_account.get("TotalCashValue", trader.cash)

    # 对比本地和 IBKR 持仓
    for ibkr_pos in ibkr_positions:
        ticker = ibkr_pos["ticker"]
        if ticker in trader.positions:
            # 更新数量和价格
            trader.positions[ticker]["quantity"] = ibkr_pos["quantity"]
            trader.positions[ticker]["avg_price"] = ibkr_pos["avg_price"]
        else:
            # IBKR 有但本地没有 → 添加并设置默认止损
            trader.positions[ticker] = {
                "quantity": ibkr_pos["quantity"],
                "avg_price": ibkr_pos["avg_price"],
                "strategy": "unknown",
                "stop_loss": ibkr_pos["avg_price"] * 0.97,  # 默认 3% 止损
                "take_profit": ibkr_pos["avg_price"] * 1.06,  # 默认 6% 止盈
            }

    # 本地有但 IBKR 没有 → 清除
    for ticker in list(trader.positions.keys()):
        if ticker not in [p["ticker"] for p in ibkr_positions]:
            logger.warning("Position %s exists locally but not in IBKR, removing", ticker)
            del trader.positions[ticker]

    trader._save()
```

### 3.3 扫描管线集成

```python
# scanner.py - 扫描前检查健康状态
health = await health_checker.check()

if not health.can_scan:
    logger.warning("System unhealthy: market=%s ibkr=%s network=%s",
                   health.market_data, health.ibkr_connected, health.network_up)
    return [{"type": "scan_skipped", "reason": "system unhealthy"}]

if not health.can_trade:
    # 只监控已有持仓，不开新仓
    logger.warning("Cannot trade (IBKR down), monitoring positions only")
    # ... 只执行 position_monitor.check_positions()
    return events
```

### 3.4 重连后自动恢复

```python
# ibkr_reconnect.py - 重连成功后
if reconnected:
    await sync_after_reconnect(trader, broker)
    await send_message("IBKR 重连成功，持仓已同步")
```

## 4. 优先级

1. **P0**：健康检查模块（先检测再行动）
2. **P1**：扫描管线集成（异常时停止开仓）
3. **P2**：状态恢复模块（重连后同步）
4. **P3**：完整断网处理（所有服务停止）

## 5. 测试策略

- Mock 所有外部服务失败，验证系统停止开仓
- Mock IBKR 断线，验证持仓继续监控
- Mock 重连成功，验证状态同步
- Mock 完全断网，验证状态保存
