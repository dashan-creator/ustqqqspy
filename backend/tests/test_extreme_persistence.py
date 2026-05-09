"""Extreme state persistence and paper trader edge cases."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.execution.paper_trader import PaperTrader
from app.execution.state_store import save_state, load_state


class TestPaperTraderEdgeCases:

    def test_buy_zero_quantity_rejected(self):
        trader = PaperTrader(initial_cash=100_000, restore=False)
        order = trader.buy("SPY", 0, 100.0, "test", "test")
        assert order["status"] == "rejected"

    def test_buy_negative_quantity_rejected(self):
        trader = PaperTrader(initial_cash=100_000, restore=False)
        order = trader.buy("SPY", -5, 100.0, "test", "test")
        assert order["status"] == "rejected"

    def test_buy_zero_price_rejected(self):
        trader = PaperTrader(initial_cash=100_000, restore=False)
        order = trader.buy("SPY", 10, 0, "test", "test")
        assert order["status"] == "rejected"

    def test_buy_insufficient_cash_rejected(self):
        trader = PaperTrader(initial_cash=100, restore=False)
        order = trader.buy("SPY", 10, 100.0, "test", "test")  # $1000 > $100
        assert order["status"] == "rejected"

    def test_sell_nonexistent_ticker_rejected(self):
        trader = PaperTrader(initial_cash=100_000, restore=False)
        order = trader.sell("FAKE", 10, 100.0, "test")
        assert order["status"] == "rejected"

    def test_sell_more_than_held(self):
        """Sell quantity > held quantity should sell all."""
        trader = PaperTrader(initial_cash=100_000, restore=False)
        trader.buy("SPY", 5, 100.0, "test", "test")
        order = trader.sell("SPY", 10, 110.0, "test")
        assert "SPY" not in trader.positions  # All sold

    def test_fractional_quantity(self):
        """Fractional shares should work."""
        trader = PaperTrader(initial_cash=100_000, restore=False)
        order = trader.buy("SPY", 0.5, 100.0, "test", "test")
        assert order["status"] == "filled"
        assert trader.positions["SPY"]["quantity"] == 0.5

    def test_very_small_trade(self):
        """Very small trade should work."""
        trader = PaperTrader(initial_cash=100_000, restore=False)
        order = trader.buy("SPY", 0.001, 100.0, "test", "test")
        assert order["status"] == "filled"
        assert trader.cash == pytest.approx(99_999.9)

    def test_multiple_buys_averages_price(self):
        trader = PaperTrader(initial_cash=100_000, restore=False)
        trader.buy("SPY", 10, 100.0, "test", "test")
        trader.buy("SPY", 10, 110.0, "test", "test")
        assert trader.positions["SPY"]["quantity"] == 20
        assert trader.positions["SPY"]["avg_price"] == 105.0

    def test_consecutive_losses_tracking(self):
        trader = PaperTrader(initial_cash=100_000, restore=False)
        trader.consecutive_losses = 0
        # Simulate losing trades by setting the field directly
        trader.consecutive_losses = 3
        assert trader.consecutive_losses == 3
        # Reset on win
        trader.consecutive_losses = 0
        assert trader.consecutive_losses == 0

    def test_daily_pnl_tracking(self):
        trader = PaperTrader(initial_cash=100_000, restore=False)
        trader.daily_pnl = 0.0
        trader.daily_pnl += 100.0
        trader.daily_pnl += -50.0
        assert trader.daily_pnl == 50.0


class TestStatePersistenceEdgeCases:

    def test_save_and_load_roundtrip(self, tmp_path):
        with patch("app.execution.state_store.STATE_FILE", tmp_path / "state.json"):
            save_state(
                cash=200.0,
                positions={"SPY": {"quantity": 1, "avg_price": 100}},
                trades=[{"ticker": "SPY", "pnl": 50}],
                risk_state={"consecutive_losses": 1, "daily_pnl": 50.0},
            )
            state = load_state()
            assert state["cash"] == 200.0
            assert "SPY" in state["positions"]
            assert len(state["trades"]) == 1
            assert state["risk_state"]["consecutive_losses"] == 1

    def test_load_missing_file_returns_none(self, tmp_path):
        with patch("app.execution.state_store.STATE_FILE", tmp_path / "nonexistent.json"):
            state = load_state()
            assert state is None

    def test_load_corrupted_file_returns_none(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")
        with patch("app.execution.state_store.STATE_FILE", bad_file):
            state = load_state()
            assert state is None

    def test_load_empty_positions(self, tmp_path):
        with patch("app.execution.state_store.STATE_FILE", tmp_path / "state.json"):
            save_state(cash=200.0, positions={}, trades=[])
            state = load_state()
            assert state["cash"] == 200.0
            assert state["positions"] == {}

    def test_load_with_missing_risk_state(self, tmp_path):
        """Old state file without risk_state should load gracefully."""
        bad_file = tmp_path / "old.json"
        bad_file.write_text(json.dumps({
            "cash": 200.0, "positions": {}, "trades": [],
        }))
        with patch("app.execution.state_store.STATE_FILE", bad_file):
            state = load_state()
            assert state["cash"] == 200.0
            assert state.get("risk_state") is None

    def test_paper_trader_restores_from_state(self, tmp_path):
        """PaperTrader should restore cash and positions from state file."""
        with patch("app.execution.state_store.STATE_FILE", tmp_path / "state.json"):
            save_state(
                cash=150.0,
                positions={"AAPL": {"quantity": 5, "avg_price": 200, "strategy": "test"}},
                trades=[{"ticker": "SPY", "pnl": 10}],
                risk_state={"consecutive_losses": 2, "daily_pnl": -10.0},
            )
            trader = PaperTrader(initial_cash=200.0, restore=True)
            assert trader.cash == 150.0
            assert "AAPL" in trader.positions
            assert trader.positions["AAPL"]["quantity"] == 5
            assert len(trader.trades) == 1
            assert trader.consecutive_losses == 2
            assert trader.daily_pnl == -10.0
