from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./usstock.db"
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    # LLM
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "not-needed"
    llm_model: str = "default"
    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # IBKR
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 1
    ibkr_username: str = ""
    ibkr_password: str = ""
    use_ibkr: bool = False  # True = IBKR Paper Trading, False = in-memory paper trader
    # News
    finnhub_api_key: str = ""
    polygon_api_key: str = ""
    news_cache_ttl_seconds: int = 300
    # Trading
    symbols: str = "SPY,QQQ,AAPL,MSFT,NVDA,TSLA,META,AMZN,GOOGL,AMD"
    scan_interval_minutes: int = 15
    max_daily_loss_pct: float = 0.01
    max_weekly_loss_pct: float = 0.04
    max_concurrent_positions: int = 2
    max_single_position_pct: float = 2.0
    consecutive_loss_limit: int = 3
    initial_cash: float = 100_000.0
    # App
    admin_api_key: str = ""
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip() for s in self.symbols.split(",")]


settings = Settings()
