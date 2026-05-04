from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_pipeline

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/status")
async def risk_status():
    pipeline = get_pipeline()
    return pipeline.get_status()
