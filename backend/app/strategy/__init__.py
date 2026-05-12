from app.strategy.base import StrategyBase
from app.strategy.breakout import BreakoutStrategy
from app.strategy.mean_reversion import MeanReversionStrategy
from app.strategy.spy_tqqq_cycle import SpyTqqqCycleStrategy

STRATEGIES: list[StrategyBase] = [SpyTqqqCycleStrategy(), BreakoutStrategy(), MeanReversionStrategy()]

__all__ = [
    "StrategyBase",
    "BreakoutStrategy",
    "MeanReversionStrategy",
    "SpyTqqqCycleStrategy",
    "STRATEGIES",
]
