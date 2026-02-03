"""
Regime features for market context.

Adds features that describe the broader market environment
(SPY trend, VIX volatility, correlation to SPY, sector strength).
"""

import logging
from typing import Any, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

REGIME_FEATURES = [
    "spy_above_200ma",
    "spy_trend_strength",
    "spy_trend_regime",
    "vix",
    "vix_regime",
    "vix_percentile",
    "vix_change_5d",
    "correlation_to_spy_30d",
    "correlation_regime",
    "beta_to_spy",
    "sector_relative_strength",
    "sector_outperforming",
]


def _load_ohlcv(symbol: str, limit: int) -> pd.DataFrame | None:
    """Load OHLCV from Supabase. Returns None if symbol not found or error."""
    try:
        from src.data.supabase_db import SupabaseDatabase

        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=limit)
        if df is not None and len(df) > 0:
            return df
    except Exception as e:
        logger.debug("Could not load %s: %s", symbol, e)
    return None


def _stock_dates(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Return normalized date index from df (ts column or index)."""
    if "ts" in df.columns:
        return pd.to_datetime(df["ts"], utc=False).dt.tz_localize(None).dt.normalize()
    return pd.to_datetime(df.index).normalize()


def load_market_data(df: pd.DataFrame, limit: int = 800) -> Dict[str, pd.DataFrame | None]:
    """
    Load SPY, VIX, QQQ aligned to stock date range.
    Returns dict with keys 'spy', 'vix', 'qqq' (DataFrames or None).
    """
    stock_dates = _stock_dates(df)
    if len(stock_dates) == 0:
        return {"spy": None, "vix": None, "qqq": None}

    market_data: Dict[str, pd.DataFrame | None] = {}
    for sym in ["SPY", "VIX", "QQQ"]:
        market_data[sym.lower()] = _load_ohlcv(sym, limit=limit)
        if market_data[sym.lower()] is not None:
            logger.info("Loaded %s: %s bars", sym, len(market_data[sym.lower()]))
    return market_data


def add_market_trend_regime(df: pd.DataFrame, spy_df: pd.DataFrame | None) -> pd.DataFrame:
    """Add SPY trend regime features (above 200 MA, trend strength, regime 0/1/2)."""
    stock_dates = _stock_dates(df)
    if spy_df is None or len(spy_df) < 50:
        logger.warning("Insufficient SPY data for trend regime, using defaults")
        df["spy_above_200ma"] = 1
        df["spy_trend_strength"] = 0.0
        df["spy_trend_regime"] = 2
        return df

    spy_idx = pd.to_datetime(spy_df["ts"], utc=False).dt.tz_localize(None).dt.normalize()
    spy_close = spy_df.set_index(spy_idx)["close"]
    spy_sma200 = spy_close.rolling(200, min_periods=50).mean()
    spy_dist = (spy_close / spy_sma200 - 1).reindex(stock_dates, method="ffill")

    df["spy_above_200ma"] = (spy_dist > 0).astype(int).fillna(1).values
    df["spy_trend_strength"] = spy_dist.fillna(0.0).values

    conditions = [spy_dist < -0.05, spy_dist > 0.05]
    choices = [0, 2]  # 0=bear, 2=bull
    df["spy_trend_regime"] = np.select(conditions, choices, default=1).astype(int)
    return df


def add_volatility_regime(df: pd.DataFrame, vix_df: pd.DataFrame | None) -> pd.DataFrame:
    """Add VIX-based volatility regime features."""
    stock_dates = _stock_dates(df)
    if vix_df is None or len(vix_df) == 0:
        logger.warning("No VIX data, using defaults")
        df["vix"] = 15.0
        df["vix_regime"] = 1
        df["vix_percentile"] = 50.0
        df["vix_change_5d"] = 0.0
        return df

    vix_idx = pd.to_datetime(vix_df["ts"], utc=False).dt.tz_localize(None).dt.normalize()
    vix_close = vix_df.set_index(vix_idx)["close"].reindex(stock_dates, method="ffill")
    df["vix"] = vix_close.fillna(15.0).values

    conditions = [df["vix"] < 15, df["vix"] < 25]
    choices = [0, 1]
    df["vix_regime"] = np.select(conditions, choices, default=2).astype(int)

    vix_series = pd.Series(df["vix"].copy(), index=stock_dates)
    df["vix_percentile"] = (
        vix_series.rolling(252, min_periods=60)
        .apply(lambda x: (x.rank(pct=True).iloc[-1] * 100) if len(x) > 0 else 50.0, raw=False)
        .fillna(50.0)
        .values
    )
    df["vix_change_5d"] = vix_series.pct_change(5).fillna(0.0).values
    return df


def add_correlation_regime(
    df: pd.DataFrame, spy_df: pd.DataFrame | None, window: int = 30
) -> pd.DataFrame:
    """Add correlation and beta to SPY."""
    stock_dates = _stock_dates(df)
    if spy_df is None or len(spy_df) < window:
        df["correlation_to_spy_30d"] = 0.5
        df["correlation_regime"] = 1
        df["beta_to_spy"] = 1.0
        return df

    spy_idx = pd.to_datetime(spy_df["ts"], utc=False).dt.tz_localize(None).dt.normalize()
    spy_ret = spy_df.set_index(spy_idx)["close"].pct_change()
    stock_ret = pd.Series(df["close"].values).pct_change()
    stock_ret.index = stock_dates
    spy_aligned = spy_ret.reindex(stock_dates, method="ffill")
    corr = stock_ret.rolling(window).corr(spy_aligned).fillna(0.5)
    df["correlation_to_spy_30d"] = corr.values

    conditions = [df["correlation_to_spy_30d"] < 0.3, df["correlation_to_spy_30d"] < 0.7]
    choices = [0, 1]
    df["correlation_regime"] = np.select(conditions, choices, default=2).astype(int)

    stock_std = stock_ret.rolling(window).std()
    spy_std = spy_aligned.rolling(window).std()
    beta = (corr * (stock_std / spy_std)).fillna(1.0)
    df["beta_to_spy"] = beta.values
    return df


def add_sector_regime(
    df: pd.DataFrame,
    sector_etf_df: pd.DataFrame | None,
    spy_df: pd.DataFrame | None,
    window: int = 20,
) -> pd.DataFrame:
    """Add sector relative strength vs SPY."""
    stock_dates = _stock_dates(df)
    if sector_etf_df is None or spy_df is None or len(sector_etf_df) < window:
        df["sector_relative_strength"] = 0.0
        df["sector_outperforming"] = 1
        return df

    spy_idx = pd.to_datetime(spy_df["ts"], utc=False).dt.tz_localize(None).dt.normalize()
    sector_idx = pd.to_datetime(sector_etf_df["ts"], utc=False).dt.tz_localize(None).dt.normalize()
    spy_ret = spy_df.set_index(spy_idx)["close"].pct_change().rolling(window).sum()
    sector_ret = sector_etf_df.set_index(sector_idx)["close"].pct_change().rolling(window).sum()
    rel = (
        sector_ret.reindex(stock_dates, method="ffill")
        - spy_ret.reindex(stock_dates, method="ffill")
    ).fillna(0.0)
    df["sector_relative_strength"] = rel.values
    df["sector_outperforming"] = (df["sector_relative_strength"] > 0).astype(int)
    return df


def add_regime_defaults(df: pd.DataFrame) -> pd.DataFrame:
    """Add regime columns with default values so feature set is fixed when regime not loaded."""
    n = len(df)
    df["spy_above_200ma"] = 1
    df["spy_trend_strength"] = 0.0
    df["spy_trend_regime"] = 2
    df["vix"] = 15.0
    df["vix_regime"] = 1
    df["vix_percentile"] = 50.0
    df["vix_change_5d"] = 0.0
    df["correlation_to_spy_30d"] = 0.5
    df["correlation_regime"] = 1
    df["beta_to_spy"] = 1.0
    df["sector_relative_strength"] = 0.0
    df["sector_outperforming"] = 1
    return df


def add_all_regime_features(df: pd.DataFrame, symbol: str = "TSLA") -> pd.DataFrame:
    """
    Add all regime features to a stock OHLCV DataFrame.
    Expects df with columns: ts, open, high, low, close, volume.
    """
    logger.info("Adding regime features for %s", symbol)
    limit = 800
    market = load_market_data(df, limit=limit)

    df = add_market_trend_regime(df, market.get("spy"))
    df = add_volatility_regime(df, market.get("vix"))
    df = add_correlation_regime(df, market.get("spy"))
    sector_map: Dict[str, str] = {
        "TSLA": "qqq",
        "NVDA": "qqq",
        "AAPL": "qqq",
        "MSFT": "qqq",
        "META": "qqq",
        "GOOG": "qqq",
        "GOOGL": "qqq",
        "AMD": "qqq",
    }
    sector_key = sector_map.get(symbol.upper(), "qqq")
    sector_etf = market.get(sector_key)
    df = add_sector_regime(df, sector_etf, market.get("spy"))

    n_regime = sum(1 for c in REGIME_FEATURES if c in df.columns)
    logger.info("Regime features added: %s", n_regime)
    return df
