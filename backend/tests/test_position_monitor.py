from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.execution.paper_trader import PaperTrader
from app.execution.order_manager import OrderManager
from app.pipeline.position_monitor import PositionMonitor


@pytest.fixture
def setup():
    # Mock load_state to avoid DB/file access during init
    with patch("app.execution.state_store.load_state", return_value=None):
        trader = PaperTrader(initial_cash=100_000, restore=False)
        om = OrderManager(trader)
        trader.buy("NVDA", 10, 100.0, "breakout", "test entry")
        trader.positions["NVDA"]["stop_loss"] = 95.0
        trader.positions["NVDA"]["take_profit"] = 120.0
        trader.positions["NVDA"]["entry_reason"] = "test"
        monitor = PositionMonitor(trader, om)
    return trader, om, monitor


@pytest.mark.asyncio
async def test_no_close_when_price_in_range(setup):
    trader, om, monitor = setup
    with patch.object(monitor, "_get_current_price", return_value=105.0):
        events = await monitor.check_positions()
    assert events == []
    assert "NVDA" in trader.positions


@pytest.mark.asyncio
async def test_stop_loss_triggers(setup):
    trader, om, monitor = setup
    with patch.object(monitor, "_get_current_price", return_value=94.0), \
         patch("app.pipeline.position_monitor.persist_trade", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.persist_order", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.post_trade_review", new_callable=AsyncMock, return_value={}), \
         patch("app.pipeline.position_monitor.write_trade_note", new_callable=AsyncMock):
        events = await monitor.check_positions()
    assert len(events) == 1
    assert events[0]["type"] == "position_closed"
    assert events[0]["ticker"] == "NVDA"
    assert "止损" in events[0]["reason"]
    assert "NVDA" not in trader.positions


@pytest.mark.asyncio
async def test_take_profit_triggers(setup):
    trader, om, monitor = setup
    with patch.object(monitor, "_get_current_price", return_value=125.0), \
         patch("app.pipeline.position_monitor.persist_trade", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.persist_order", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.post_trade_review", new_callable=AsyncMock, return_value={}), \
         patch("app.pipeline.position_monitor.write_trade_note", new_callable=AsyncMock):
        events = await monitor.check_positions()
    assert len(events) == 1
    assert "止盈" in events[0]["reason"]
    assert events[0]["pnl"] > 0
    assert "NVDA" not in trader.positions


@pytest.mark.asyncio
async def test_trailing_stop(setup):
    trader, om, monitor = setup
    # Set take_profit very high so it won't trigger
    trader.positions["NVDA"]["take_profit"] = 999.0

    # Price goes up to 130
    with patch.object(monitor, "_get_current_price", return_value=130.0):
        events = await monitor.check_positions()
    assert events == []
    assert monitor.highest_prices["NVDA"] == 130.0

    # Price drops significantly
    with patch.object(monitor, "_get_current_price", return_value=124.0), \
         patch("app.pipeline.position_monitor.persist_trade", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.persist_order", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.post_trade_review", new_callable=AsyncMock, return_value={}), \
         patch("app.pipeline.position_monitor.write_trade_note", new_callable=AsyncMock):
        events = await monitor.check_positions()
    assert len(events) == 1
    assert "移动止盈" in events[0]["reason"]


@pytest.mark.asyncio
async def test_consecutive_losses_increments(setup):
    trader, om, monitor = setup
    with patch.object(monitor, "_get_current_price", return_value=90.0), \
         patch("app.pipeline.position_monitor.persist_trade", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.persist_order", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.post_trade_review", new_callable=AsyncMock, return_value={}), \
         patch("app.pipeline.position_monitor.write_trade_note", new_callable=AsyncMock):
        await monitor.check_positions()
    assert trader.consecutive_losses == 1


@pytest.mark.asyncio
async def test_consecutive_losses_resets_on_win(setup):
    trader, om, monitor = setup
    trader.consecutive_losses = 2
    with patch.object(monitor, "_get_current_price", return_value=125.0), \
         patch("app.pipeline.position_monitor.persist_trade", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.persist_order", new_callable=AsyncMock), \
         patch("app.pipeline.position_monitor.post_trade_review", new_callable=AsyncMock, return_value={}), \
         patch("app.pipeline.position_monitor.write_trade_note", new_callable=AsyncMock):
        await monitor.check_positions()
    assert trader.consecutive_losses == 0
