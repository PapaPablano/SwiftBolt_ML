"""Configuration settings for SwiftBolt ML pipeline."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(
            str(Path(__file__).resolve().parents[1] / ".env"),
            str(Path(__file__).resolve().parents[2] / ".env"),
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase Connection
    supabase_url: str
    supabase_key: str | None = None  # Service role key (maps to SUPABASE_KEY env var)
    supabase_service_role_key: str | None = None  # Alias for supabase_key
    database_url: str | None = None  # Direct Postgres connection string (optional for backfill)

    def model_post_init(self, __context) -> None:
        """Set service_role_key alias after init."""
        if self.supabase_key is None and self.supabase_service_role_key is not None:
            object.__setattr__(self, 'supabase_key', self.supabase_service_role_key)
        if self.supabase_service_role_key is None and self.supabase_key is not None:
            object.__setattr__(self, 'supabase_service_role_key', self.supabase_key)

    # ML Configuration
    forecast_horizons: list[str] = [
        "1D",
        "1W",
        "1M",
        "2M",
        "3M",
        "4M",
        "5M",
        "6M",
    ]
    min_bars_for_training: int = 100  # Minimum for statistical significance
    min_bars_for_high_confidence: int = 504  # 2 years for high-quality forecasts (market cycle)
    max_training_bars: int = 780  # ~3 years of daily data for long horizons
    use_ensemble_forecaster: bool = True  # Use ensemble (RF+XGBoost) vs RF-only
    confidence_threshold: float = 0.6
    enable_feature_selection: bool = True
    max_feature_count: int = 40
    feature_selection_cv_splits: int = 5

    # Intraday Weight Calibration Configuration
    intraday_horizons: list[str] = ["15m", "1h"]
    intraday_calibration_min_samples: int = 50  # ~2 days of 15min data
    intraday_lookback_hours: int = 72  # 3 days of historical data for calibration
    intraday_weight_update_frequency_hours: int = 4
    intraday_min_bars: int = 100  # Minimum bars for intraday forecasting
    enable_intraday_calibration: bool = True
    intraday_symbols: list[str] = ["AAPL", "NVDA", "AMD", "PLTR", "CRWD", "AMZN", "MU"]

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
