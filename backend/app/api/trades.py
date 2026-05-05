from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_pipeline
from app.api.security import require_admin

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("")
async def list_trades(_admin: None = Depends(require_admin)):
    pipeline = get_pipeline()
    return pipeline.trader.trades


@router.get("/stats")
async def trade_stats():
    pipeline = get_pipeline()
    return pipeline.trader.get_stats()
