from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_pipeline

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("")
async def list_trades():
    pipeline = get_pipeline()
    return pipeline.trader.trades


@router.get("/stats")
async def trade_stats():
    pipeline = get_pipeline()
    return pipeline.trader.get_stats()
