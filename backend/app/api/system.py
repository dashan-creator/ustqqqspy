from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_pipeline
from app.api.security import require_admin

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status(_admin: None = Depends(require_admin)):
    pipeline = get_pipeline()
    return {
        "status": "paused" if pipeline.circuit_breaker.is_paused else "running",
        "positions": len(pipeline.trader.positions),
        "cash": pipeline.trader.cash,
    }


@router.post("/pause")
async def pause_trading(reason: str = "Manual pause", _admin: None = Depends(require_admin)):
    pipeline = get_pipeline()
    pipeline.circuit_breaker.pause(reason)
    return {"status": "paused", "reason": reason}


@router.post("/resume")
async def resume_trading(_admin: None = Depends(require_admin)):
    pipeline = get_pipeline()
    pipeline.circuit_breaker.resume()
    return {"status": "running"}


@router.get("/stats")
async def system_stats(_admin: None = Depends(require_admin)):
    pipeline = get_pipeline()
    return pipeline.trader.get_stats()
