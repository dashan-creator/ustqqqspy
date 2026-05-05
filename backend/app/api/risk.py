from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_pipeline
from app.api.security import require_admin

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/status")
async def risk_status(_admin: None = Depends(require_admin)):
    pipeline = get_pipeline()
    return await pipeline.get_status()
