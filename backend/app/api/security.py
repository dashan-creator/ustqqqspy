from __future__ import annotations

from fastapi import Depends, HTTPException, Header

from app.config import settings


async def require_admin(x_api_key: str = Header(default="")) -> None:
    """Require admin API key for write operations. Read-only endpoints skip this."""
    if not settings.admin_api_key:
        return  # No key configured → allow all (V0 default)
    if x_api_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
