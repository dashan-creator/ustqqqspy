from __future__ import annotations

from fastapi import Depends, HTTPException, Header

from app.config import settings


async def require_admin(x_api_key: str = Header(default="")) -> None:
    if not settings.admin_api_key:
        raise HTTPException(status_code=500, detail="Admin API key not configured")
    if x_api_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
