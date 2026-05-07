from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import nest_asyncio
from ib_insync import IB, Stock, MarketOrder, LimitOrder

nest_asyncio.apply()

logger = logging.getLogger(__name__)


class IBKRBroker:
    """Interactive Brokers adapter via ib_insync. Connects to TWS/Gateway Paper Trading."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self._connected = False

    async def connect(self) -> bool:
        try:
            await asyncio.to_thread(self.ib.connect, self.host, self.port, clientId=self.client_id)
            self._connected = True
            logger.info("Connected to IBKR at %s:%d (client %d)", self.host, self.port, self.client_id)
            return True
        except Exception as e:
            logger.error("IBKR connection failed: %s", e)
            self._connected = False
            return False

    def disconnect(self):
        if self._connected:
            self.ib.disconnect()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self.ib.isConnected()

    async def get_account_value(self) -> float:
        account = await asyncio.to_thread(self.ib.accountSummary)
        for item in account:
            if item.tag == "NetLiquidation":
                return float(item.value)
        return 0.0

    async def get_positions(self) -> list[dict]:
        positions = await asyncio.to_thread(self.ib.positions)
        result = []
        for pos in positions:
            result.append({
                "ticker": pos.contract.symbol,
                "quantity": pos.position,
                "avg_price": pos.avgCost,
                "market_value": pos.position * pos.avgCost,
            })
        return result

    async def get_open_orders(self) -> list[dict]:
        trades = self.ib.openTrades()
        result = []
        for t in trades:
            result.append({
                "ticker": t.contract.symbol,
                "side": t.order.action.lower(),
                "quantity": t.order.totalQuantity,
                "order_type": t.order.orderType,
                "limit_price": getattr(t.order, "lmtPrice", None),
                "status": t.orderStatus.status,
                "order_id": t.order.orderId,
            })
        return result

    async def place_market_order(self, ticker: str, quantity: int, side: str) -> dict:
        contract = Stock(ticker, "SMART", "USD")
        await asyncio.to_thread(self.ib.qualifyContracts, contract)
        order = MarketOrder(side.upper(), quantity)
        trade = await asyncio.to_thread(self.ib.placeOrder, contract, order)
        logger.info("IBKR %s %s x%d", side.upper(), ticker, quantity)

        # Wait for fill (up to 15s)
        for _ in range(30):
            await asyncio.sleep(0.5)
            status = trade.orderStatus.status
            if status == "Filled":
                filled_price = trade.orderStatus.avgFillPrice
                logger.info("IBKR FILLED %s %s x%d @ %.2f", side.upper(), ticker, quantity, filled_price)
                return {
                    "ticker": ticker, "side": side, "quantity": quantity,
                    "order_type": "market", "status": "filled",
                    "filled_price": float(filled_price) if filled_price else 0,
                    "order_id": trade.order.orderId,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            if status in ("Cancelled", "Inactive"):
                return {
                    "ticker": ticker, "side": side, "quantity": quantity,
                    "order_type": "market", "status": "rejected",
                    "reason": f"IBKR status: {status}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        # Timeout - return submitted status (not treated as filled)
        return {
            "ticker": ticker, "side": side, "quantity": quantity,
            "order_type": "market", "status": trade.orderStatus.status,
            "filled_price": 0,
            "order_id": trade.order.orderId,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def place_limit_order(self, ticker: str, quantity: int, side: str, price: float) -> dict:
        contract = Stock(ticker, "SMART", "USD")
        await asyncio.to_thread(self.ib.qualifyContracts, contract)
        order = LimitOrder(side.upper(), quantity, price)
        trade = await asyncio.to_thread(self.ib.placeOrder, contract, order)
        logger.info("IBKR %s %s x%d @ %.2f", side.upper(), ticker, quantity, price)
        return {
            "ticker": ticker, "side": side, "quantity": quantity,
            "order_type": "limit", "limit_price": price,
            "status": trade.orderStatus.status,
            "order_id": trade.order.orderId,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def cancel_order(self, order_id: int):
        for trade in self.ib.openTrades():
            if trade.order.orderId == order_id:
                await asyncio.to_thread(self.ib.cancelOrder, trade.order)
                logger.info("Cancelled IBKR order %d", order_id)
                return
        logger.warning("Order %d not found", order_id)

    async def get_realtime_price(self, ticker: str) -> float:
        contract = Stock(ticker, "SMART", "USD")
        await asyncio.to_thread(self.ib.qualifyContracts, contract)
        [ticker_data] = await asyncio.to_thread(self.ib.reqTickers, contract)
        return ticker_data.marketPrice()

    async def get_account_summary(self) -> dict:
        account = await asyncio.to_thread(self.ib.accountSummary)
        summary = {}
        for item in account:
            if item.tag in ("NetLiquidation", "TotalCashValue", "UnrealizedPnL", "RealizedPnL", "BuyingPower"):
                summary[item.tag] = float(item.value)
        return summary
