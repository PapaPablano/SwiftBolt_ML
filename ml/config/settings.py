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
    supabase_service_role_key: str | None = None  # Alias for supabase_key
    database_url: str | None = None  # Direct Postgres connection string (optional for backfill)

    def model_post_init(self, __context) -> None:
        """Set service_role_key alias after init."""
        if self.supabase_service_role_key is None:
            object.__setattr__(self, 'supabase_service_role_key', self.supabase_key)

    # ML Configuration
    forecast_horizons: list[str] = ["1D", "1W"]
    min_bars_for_training: int = 20  # Lowered to allow forecasts with limited data
    use_ensemble_forecaster: bool = True  # Use ensemble (RF+XGBoost) vs RF-only
    confidence_threshold: float = 0.6

    # Job Configuration
    symbols_to_process: list[str] = ["AAPL", "SPY", "TSLA", "NVDA", "MSFT"]
    batch_size: int = 10

    # Tradier API (Options Data)
    tradier_api_key: str | None = None
    tradier_base_url: str = "https://api.tradier.com/v1"  # Production
    # tradier_base_url: str = "https://sandbox.tradier.com/v1"  # Sandbox

    # Logging
    log_level: str = "INFO"


# Singleton settings instance
settings = Settings()  # type: ignore
