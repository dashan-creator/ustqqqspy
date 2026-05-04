from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    sector: Mapped[str] = mapped_column(String(50), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_position_pct: Mapped[float] = mapped_column(Float, default=2.0)
