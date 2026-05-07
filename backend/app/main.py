from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import market, signals, trades, risk, system, websocket
from app.models.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    from app.config import settings
    from app.pipeline.scanner import scanner_pipeline
    from app.scheduler.market_scanner import create_scheduler
    from app.telegram.bot import set_pipeline, start_telegram

    # IBKR connection (optional)
    if settings.use_ibkr:
        from app.execution.broker import IBKRBroker
        broker = IBKRBroker(host=settings.ibkr_host, port=settings.ibkr_port, client_id=settings.ibkr_client_id)
        connected = await broker.connect()
        if connected:
            scanner_pipeline.ibkr_broker = broker
            logging.info("IBKR Paper Trading connected at %s:%d", settings.ibkr_host, settings.ibkr_port)
        else:
            logging.warning("IBKR connection failed, falling back to paper trader")

    set_pipeline(scanner_pipeline)

    # Sync state with DB on startup
    from app.execution.state_store import sync_with_db
    actions = await sync_with_db(scanner_pipeline.trader)
    for a in actions:
        logging.info("State sync: %s", a)

    # Initialize market data providers
    from app.market.data_service import market_data_service
    from app.market.providers import YFinanceProvider
    providers = [YFinanceProvider()]
    if scanner_pipeline.ibkr_broker:
        from app.market.providers import IBKRProvider
        providers.insert(0, IBKRProvider(scanner_pipeline.ibkr_broker))
    market_data_service.set_providers(providers)

    # Initialize position monitor
    from app.pipeline.position_monitor import init_position_monitor
    init_position_monitor(
        trader=scanner_pipeline.trader,
        order_manager=scanner_pipeline.order_manager,
        ibkr_broker=scanner_pipeline.ibkr_broker,
    )

    scheduler = create_scheduler()
    scheduler.start()

    await start_telegram()

    yield
    if scanner_pipeline.ibkr_broker:
        scanner_pipeline.ibkr_broker.disconnect()
    scheduler.shutdown()


app = FastAPI(title="US Stock Trading Bot", version="0.1.0", lifespan=lifespan)

app.include_router(market.router)
app.include_router(signals.router)
app.include_router(trades.router)
app.include_router(risk.router)
app.include_router(system.router)
app.include_router(websocket.router)


@app.get("/")
async def root():
    return {"name": "US Stock Trading Bot", "version": "0.1.0"}
