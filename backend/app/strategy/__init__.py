from app.strategy.base import StrategyBase
from app.strategy.breakout import BreakoutStrategy
from app.strategy.mean_reversion import MeanReversionStrategy

STRATEGIES: list[StrategyBase] = [BreakoutStrategy(), MeanReversionStrategy()]

__all__ = ["StrategyBase", "BreakoutStrategy", "MeanReversionStrategy", "STRATEGIES"]
