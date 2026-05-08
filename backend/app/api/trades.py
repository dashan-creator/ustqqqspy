from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_pipeline
from app.api.security import require_admin
from app.models.db import async_session
from app.models.trade import Trade
from app.models.symbol import Symbol

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("")
async def list_trades(_admin: None = Depends(require_admin)):
    pipeline = get_pipeline()
    # Merge in-memory trades with DB trades
    db_trades = []
    try:
        async with async_session() as session:
            result = await session.execute(
                select(Trade, Symbol.ticker)
                .join(Symbol, Trade.symbol_id == Symbol.id, isouter=True)
                .order_by(Trade.closed_at.desc())
                .limit(100)
            )
            for t, ticker in result.all():
                db_trades.append({
                    "id": t.id,
                    "ticker": ticker or f"symbol_{t.symbol_id}",
                    "strategy": t.strategy_name,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "reason": t.exit_reason,
                    "timestamp": t.closed_at.isoformat() if t.closed_at else "",
                })
    except Exception:
        pass
    memory_trades = pipeline.trader.trades
    return db_trades + memory_trades


@router.get("/stats")
async def trade_stats():
    pipeline = get_pipeline()
    return pipeline.trader.get_stats()


@router.get("/stats/{strategy}")
async def strategy_stats(strategy: str):
    pipeline = get_pipeline()
    strategy_trades = [t for t in pipeline.trader.trades if t.get("strategy") == strategy]
    if not strategy_trades:
        return {"strategy": strategy, "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "avg_win": 0, "avg_loss": 0, "profit_factor": 0, "max_drawdown": 0, "total_pnl": 0}

    wins = [t for t in strategy_trades if t["pnl"] > 0]
    losses = [t for t in strategy_trades if t["pnl"] <= 0]
    total = len(strategy_trades)
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    # Max drawdown
    cumulative = 0
    peak = 0
    max_dd = 0
    for t in strategy_trades:
        cumulative += t["pnl"]
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)

    return {
        "strategy": strategy,
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / total, 2) if total > 0 else 0,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_dd, 2),
        "total_pnl": round(sum(t["pnl"] for t in strategy_trades), 2),
    }
