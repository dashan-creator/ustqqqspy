from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class LLMReport(Base):
    __tablename__ = "llm_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_type: Mapped[str] = mapped_column(String(30))
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(10), nullable=True)
    impact_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suggested_action: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
