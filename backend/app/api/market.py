from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_market_service
from app.config import settings

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/symbols")
async def list_symbols():
    return [{"ticker": t, "is_active": True} for t in settings.symbol_list]


@router.get("/quote/{ticker}")
async def get_quote(ticker: str):
    svc = get_market_service()
    return svc.get_quote(ticker)


@router.get("/bars/{ticker}")
async def get_bars(ticker: str, interval: str = "15m", period: str = "5d"):
    svc = get_market_service()
    df = svc.get_bars(ticker, interval=interval, period=period)
    if df.empty:
        return []
    return df.reset_index().to_dict(orient="records")
