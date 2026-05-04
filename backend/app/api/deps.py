from __future__ import annotations

from app.pipeline.scanner import scanner_pipeline
from app.market.data_service import market_data_service


def get_pipeline():
    return scanner_pipeline


def get_market_service():
    return market_data_service
