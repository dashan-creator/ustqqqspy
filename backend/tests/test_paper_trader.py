from __future__ import annotations

import pytest

from app.execution.paper_trader import PaperTrader


@pytest.fixture
def trader():
    return PaperTrader(initial_cash=100_000)


def test_buy_order(trader):
    order = trader.buy("NVDA", quantity=10, price=800.0, strategy="breakout", reason="test")
    assert order["side"] == "buy"
    assert order["filled_price"] == 800.0
    assert order["status"] == "filled"
    assert "NVDA" in trader.positions
    assert trader.cash < 100_000


def test_sell_order(trader):
    trader.buy("NVDA", quantity=10, price=800.0, strategy="breakout", reason="test")
    order = trader.sell("NVDA", quantity=10, price=820.0, reason="take profit")
    assert order["side"] == "sell"
    assert order["status"] == "filled"
    assert "NVDA" not in trader.positions
    assert trader.cash > 100_000


def test_pnl_calculation(trader):
    trader.buy("AAPL", quantity=100, price=180.0, strategy="breakout", reason="test")
    trader.sell("AAPL", quantity=100, price=185.0, reason="take profit")
    assert len(trader.trades) == 1
    assert trader.trades[0]["pnl"] == 500.0
    assert trader.trades[0]["pnl_pct"] == pytest.approx(2.78, rel=0.01)


def test_unrealized_pnl(trader):
    trader.buy("AAPL", quantity=100, price=180.0, strategy="breakout", reason="test")
    pnl = trader.get_unrealized_pnl("AAPL", current_price=190.0)
    assert pnl == 1000.0
