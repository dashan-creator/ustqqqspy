from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class MarketBar(Base):
    __tablename__ = "market_bars"
    __table_args__ = (UniqueConstraint("symbol_id", "timeframe", "bar_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    timeframe: Mapped[str] = mapped_column(String(5))
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
