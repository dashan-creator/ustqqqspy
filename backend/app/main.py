from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import market, signals, trades, risk, system
from app.models.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    from app.pipeline.scanner import scanner_pipeline
    from app.scheduler.market_scanner import create_scheduler
    from app.telegram.bot import create_bot, set_pipeline

    set_pipeline(scanner_pipeline)

    scheduler = create_scheduler()
    scheduler.start()

    tg_app = None
    try:
        tg_app = create_bot()
        if tg_app:
            await tg_app.initialize()
            await tg_app.start()
            await tg_app.updater.start_polling()
    except Exception as e:
        logging.warning("Telegram bot failed to start: %s", e)
        tg_app = None

    yield

    try:
        if tg_app:
            await tg_app.updater.stop()
            await tg_app.stop()
    except Exception:
        pass
    scheduler.shutdown()


app = FastAPI(title="US Stock Trading Bot", version="0.1.0", lifespan=lifespan)

app.include_router(market.router)
app.include_router(signals.router)
app.include_router(trades.router)
app.include_router(risk.router)
app.include_router(system.router)


@app.get("/")
async def root():
    return {"name": "US Stock Trading Bot", "version": "0.1.0"}
