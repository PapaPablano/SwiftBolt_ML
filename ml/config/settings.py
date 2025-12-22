"""Configuration settings for SwiftBolt ML pipeline."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase Connection
    supabase_url: str
    supabase_key: str  # Service role key (maps to SUPABASE_KEY env var)
    database_url: str | None = None  # Direct Postgres connection string (optional for backfill)

    # ML Configuration
    forecast_horizons: list[str] = ["1D", "1W"]
    min_bars_for_training: int = 50  # Lowered from 100 to allow forecasts with less data
    confidence_threshold: float = 0.6

    # Job Configuration
    symbols_to_process: list[str] = ["AAPL", "SPY", "TSLA", "NVDA", "MSFT"]
    batch_size: int = 10

    # Logging
    log_level: str = "INFO"


# Singleton settings instance
settings = Settings()  # type: ignore
