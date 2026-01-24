"""Configuration settings for SwiftBolt ML pipeline."""

from pathlib import Path

from pydantic import field_validator
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
    # Service role key (maps to SUPABASE_KEY env var)
    supabase_key: str | None = None
    # Alias for supabase_key
    supabase_service_role_key: str | None = None
    # Direct Postgres connection string (optional for backfill)
    database_url: str | None = None

    @field_validator(
        "supabase_url",
        "supabase_key",
        "supabase_service_role_key",
        "database_url",
        "tradier_api_key",
        "alpaca_api_key",
        "alpaca_api_secret",
        mode="before",
    )
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        """Strip whitespace and newlines from string fields to prevent HTTP header errors."""
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip()
        return v

    def model_post_init(self, __context) -> None:
        """Set service_role_key alias after init."""
        key_missing = self.supabase_key is None
        service_key = self.supabase_service_role_key
        if key_missing and service_key is not None:
            object.__setattr__(self, "supabase_key", service_key)

        service_missing = self.supabase_service_role_key is None
        if service_missing and self.supabase_key is not None:
            object.__setattr__(
                self,
                "supabase_service_role_key",
                self.supabase_key,
            )

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
    # Minimum for statistical significance
    min_bars_for_training: int = 100
    # 2 years for high-quality forecasts (market cycle)
    min_bars_for_high_confidence: int = 504
    # ~3 years of daily data for long horizons
    max_training_bars: int = 780
    # Use ensemble (RF+XGBoost) vs RF-only
    use_ensemble_forecaster: bool = True
    confidence_threshold: float = 0.6
    enable_feature_selection: bool = True
    max_feature_count: int = 40
    feature_selection_cv_splits: int = 5

    # Intraday Weight Calibration Configuration
    intraday_horizons: list[str] = ["15m", "1h"]
    # ~2 days of 15-minute data
    intraday_calibration_min_samples: int = 50
    # 14 days of historical data for calibration
    intraday_lookback_hours: int = 336
    intraday_weight_update_frequency_hours: int = 4
    # Minimum bars for intraday forecasting
    intraday_min_bars: int = 100
    enable_intraday_calibration: bool = True
    intraday_symbols: list[str] = [
        "AAPL",
        "NVDA",
        "AMD",
        "PLTR",
        "CRWD",
        "AMZN",
        "MU",
    ]

    # Job Configuration
    symbols_to_process: list[str] = [
        "AAPL",
        "SPY",
        "TSLA",
        "NVDA",
        "MSFT",
    ]
    batch_size: int = 10

    # Tradier API (Options Data)
    tradier_api_key: str | None = None
    # Production endpoint
    tradier_base_url: str = "https://api.tradier.com/v1"
    # Sandbox endpoint
    # tradier_base_url: str = "https://sandbox.tradier.com/v1"

    # Alpaca API (Market Data)
    alpaca_api_key: str | None = None
    alpaca_api_secret: str | None = None
    alpaca_base_url: str = "https://data.alpaca.markets/v2"

    # Underlying History Configuration
    underlying_history_lookback_days: int = 7
    underlying_history_timeframes: list[str] = ["d1"]

    # Logging
    log_level: str = "INFO"


# Multi-Horizon Forecasting Configuration
# Each timeframe generates multiple horizon forecasts for cascading coverage
TIMEFRAME_HORIZONS = {
    "m15": {
        "horizons": ["4h", "1d", "1w"],  # 4 hours, 1 day, 1 week
        "horizon_days": [0.167, 1, 7],  # In days (4h = 0.167 days)
        "training_bars": 950,  # Historical bars used
    },
    "h1": {
        "horizons": ["5d", "15d", "30d"],  # 5 days, 15 days, 30 days
        "horizon_days": [5, 15, 30],
        "training_bars": 950,
    },
    "h4": {
        "horizons": ["30d", "45d", "90d"],  # 30 days, 45 days, 90 days
        "horizon_days": [30, 45, 90],
        "training_bars": 616,
    },
    "d1": {
        "horizons": ["30d", "60d", "120d"],  # 30 days, 60 days, 120 days
        "horizon_days": [30, 60, 120],
        "training_bars": 500,
    },
    "w1": {
        "horizons": ["90d", "180d", "360d"],  # 90 days, 180 days, 360 days
        "horizon_days": [90, 180, 360],
        "training_bars": 104,
    },
}

# Singleton settings instance
settings = Settings()  # type: ignore
