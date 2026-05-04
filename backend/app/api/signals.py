from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_pipeline

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("")
async def list_signals():
    pipeline = get_pipeline()
    return pipeline.last_scan_results
