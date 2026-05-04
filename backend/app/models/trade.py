from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    strategy_name: Mapped[str] = mapped_column(String(50))
    side: Mapped[str] = mapped_column(String(4))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_reason: Mapped[str] = mapped_column(Text, default="")
    exit_reason: Mapped[str] = mapped_column(Text, default="")
    llm_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    trade_grade: Mapped[str | None] = mapped_column(String(2), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
