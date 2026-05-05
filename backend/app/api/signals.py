from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_pipeline
from app.api.security import require_admin

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("")
async def list_signals(_admin: None = Depends(require_admin)):
    pipeline = get_pipeline()
    return pipeline.last_scan_results
