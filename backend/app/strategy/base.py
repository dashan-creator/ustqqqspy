from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class StrategyBase(ABC):
    """Base class for all trading strategies."""

    name: str = "base"

    @abstractmethod
    def evaluate(
        self,
        ticker: str,
        bars: pd.DataFrame,
        indicators: dict,
        market: dict,
        news: dict | None = None,
    ) -> dict | None:
        """Return signal dict or None."""
        ...
