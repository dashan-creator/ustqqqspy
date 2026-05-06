from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.execution.paper_trader import PaperTrader
from app.execution.order_manager import OrderManager
from app.pipeline.position_monitor import PositionMonitor


@pytest.fixture
def setup():
    trader = PaperTrader(initial_cash=100_000)
    om = OrderManager(trader)
    # Open a position with stop_loss and take_profit
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
    with patch.object(monitor, "_get_current_price", return_value=94.0):
        events = await monitor.check_positions()
    assert len(events) == 1
    assert events[0]["type"] == "position_closed"
    assert events[0]["ticker"] == "NVDA"
    assert "止损" in events[0]["reason"]
    assert "NVDA" not in trader.positions


@pytest.mark.asyncio
async def test_take_profit_triggers(setup):
    trader, om, monitor = setup
    with patch.object(monitor, "_get_current_price", return_value=125.0):
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
    # highest=130, atr=130*0.02=2.6, trailing_stop=130-1.5*2.6=126.1, price=124 < 126.1
    with patch.object(monitor, "_get_current_price", return_value=124.0):
        events = await monitor.check_positions()
    assert len(events) == 1
    assert "移动止盈" in events[0]["reason"]


@pytest.mark.asyncio
async def test_consecutive_losses_increments(setup):
    trader, om, monitor = setup
    # Stop loss triggers at loss
    with patch.object(monitor, "_get_current_price", return_value=90.0):
        await monitor.check_positions()
    assert trader.consecutive_losses == 1


@pytest.mark.asyncio
async def test_consecutive_losses_resets_on_win(setup):
    trader, om, monitor = setup
    trader.consecutive_losses = 2
    with patch.object(monitor, "_get_current_price", return_value=125.0):
        await monitor.check_positions()
    assert trader.consecutive_losses == 0
