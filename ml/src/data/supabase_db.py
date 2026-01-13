"""Supabase-based database access layer for SwiftBolt ML pipeline."""

import logging
from typing import Any

import pandas as pd
from supabase import Client, create_client

from config.settings import settings

logger = logging.getLogger(__name__)


class SupabaseDatabase:
    """Supabase database client manager."""

    def __init__(self) -> None:
        """Initialize Supabase client."""
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key,
        )
        logger.info("Supabase client initialized")

    def fetch_ohlc_bars(
        self,
        symbol: str,
        timeframe: str = "d1",
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLC bars for a symbol from the database.

        Args:
            symbol: Stock ticker symbol
            timeframe: Timeframe (d1, h1, etc.)
            limit: Maximum number of bars to fetch (most recent)

        Returns:
            DataFrame with columns: ts, open, high, low, close, volume
        """
        try:
            # Get symbol_id
            symbol_response = (
                self.client.table("symbols")
                .select("id")
                .eq("ticker", symbol.upper())
                .single()
                .execute()
            )
            symbol_id = symbol_response.data["id"]

            # Fetch OHLC bars
            query = (
                self.client.table("ohlc_bars_v2")
                .select("ts, open, high, low, close, volume")
                .eq("symbol_id", symbol_id)
                .eq("timeframe", timeframe)
                .order("ts", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()

            # Convert to DataFrame
            df = pd.DataFrame(response.data)

            if df.empty:
                logger.warning(
                    "No OHLC bars found for %s (%s)",
                    symbol,
                    timeframe,
                )
                return df

            # Convert timestamp to datetime and sort ascending
            df["ts"] = pd.to_datetime(df["ts"])
            df = df.sort_values("ts").reset_index(drop=True)

            logger.info(
                "Fetched %s bars for %s (%s)",
                len(df),
                symbol,
                timeframe,
            )
            return df

        except Exception as e:
            logger.error(
                "Error fetching OHLC bars for %s: %s",
                symbol,
                e,
            )
            raise

    def get_last_close_at_or_before(
        self,
        symbol: str,
        target_ts,
        timeframe: str = "d1",
    ) -> tuple[pd.Timestamp, float] | None:
        try:
            symbol_id = self.get_symbol_id(symbol)
            ts_iso = pd.to_datetime(target_ts).isoformat()
            response = (
                self.client.table("ohlc_bars_v2")
                .select("ts, close")
                .eq("symbol_id", symbol_id)
                .eq("timeframe", timeframe)
                .lte("ts", ts_iso)
                .order("ts", desc=True)
                .limit(1)
                .execute()
            )

            if not response.data:
                return None

            row = response.data[0]
            return (pd.to_datetime(row["ts"]), float(row["close"]))
        except Exception as e:
            logger.warning(
                "Error fetching last close for %s (%s): %s",
                symbol,
                timeframe,
                e,
            )
            return None

    def fetch_recent_forecast_evaluations(
        self,
        symbol: str,
        horizon: str = "1D",
        limit: int = 60,
    ) -> pd.DataFrame:
        try:
            response = (
                self.client.table("forecast_evaluations")
                .select(
                    "evaluation_date, predicted_value, realized_price, "
                    "price_error, price_error_pct"
                )
                .eq("symbol", symbol.upper())
                .eq("horizon", horizon)
                .order("evaluation_date", desc=True)
                .limit(limit)
                .execute()
            )

            df = pd.DataFrame(response.data or [])
            if df.empty:
                return df

            df["evaluation_date"] = pd.to_datetime(df["evaluation_date"])
            df = df.sort_values("evaluation_date").reset_index(drop=True)
            return df
        except Exception as e:
            logger.warning(
                "Error fetching forecast evaluations for %s (%s): %s",
                symbol,
                horizon,
                e,
            )
            return pd.DataFrame()

    def fetch_symbol_model_weights(
        self,
        symbol_id: str,
        horizon: str,
    ) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("symbol_model_weights")
                .select("rf_weight, gb_weight, synth_weights, " "diagnostics, last_updated")
                .eq("symbol_id", symbol_id)
                .eq("horizon", horizon)
                .order("last_updated", desc=True)
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return dict(response.data[0])
        except Exception as e:
            logger.warning(
                "Could not fetch symbol model weights for %s (%s): %s",
                symbol_id,
                horizon,
                e,
            )
            return None

    def upsert_symbol_model_weights(
        self,
        symbol_id: str,
        horizon: str,
        rf_weight: float | None = None,
        gb_weight: float | None = None,
        synth_weights: dict[str, Any] | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        try:
            payload: dict[str, Any] = {
                "symbol_id": symbol_id,
                "horizon": horizon,
                "last_updated": pd.Timestamp.utcnow().isoformat(),
            }
            if rf_weight is not None:
                payload["rf_weight"] = float(rf_weight)
            if gb_weight is not None:
                payload["gb_weight"] = float(gb_weight)
            if synth_weights is not None:
                payload["synth_weights"] = synth_weights
            if diagnostics is not None:
                payload["diagnostics"] = diagnostics

            self.client.table("symbol_model_weights").upsert(
                payload,
                on_conflict="symbol_id,horizon",
            ).execute()
        except Exception as e:
            logger.warning(
                "Could not upsert symbol model weights for %s (%s): %s",
                symbol_id,
                horizon,
                e,
            )

    def get_nth_future_close_after(
        self,
        symbol: str,
        after_ts,
        n: int = 1,
        timeframe: str = "d1",
    ) -> tuple[pd.Timestamp, float] | None:
        if n <= 0:
            return None

        try:
            symbol_id = self.get_symbol_id(symbol)
            ts_iso = pd.to_datetime(after_ts).isoformat()
            response = (
                self.client.table("ohlc_bars_v2")
                .select("ts, close")
                .eq("symbol_id", symbol_id)
                .eq("timeframe", timeframe)
                .gt("ts", ts_iso)
                .order("ts", desc=False)
                .limit(n)
                .execute()
            )

            if not response.data or len(response.data) < n:
                return None

            row = response.data[n - 1]
            return (pd.to_datetime(row["ts"]), float(row["close"]))
        except Exception as e:
            logger.warning(
                "Error fetching future close for %s (%s): %s",
                symbol,
                timeframe,
                e,
            )
            return None

    def get_symbol_id(self, symbol: str) -> str:
        """
        Get the UUID for a symbol ticker.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Symbol UUID
        """
        try:
            response = (
                self.client.table("symbols")
                .select("id")
                .eq("ticker", symbol.upper())
                .single()
                .execute()
            )
            return response.data["id"]
        except Exception as e:
            logger.error(
                "Error fetching symbol_id for %s: %s",
                symbol,
                e,
            )
            raise

    def upsert_forecast(
        self,
        symbol_id: str,
        horizon: str,
        overall_label: str,
        confidence: float,
        points: list[dict[str, Any]],
        supertrend_data: dict[str, Any] | None = None,
        backtest_metrics: dict[str, Any] | None = None,
        quality_score: float | None = None,
        quality_issues: list[dict[str, Any]] | None = None,
        model_agreement: float | None = None,
        training_stats: dict[str, Any] | None = None,
        sr_levels: dict[str, Any] | None = None,
        sr_density: int | None = None,
        synthesis_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Insert or update a forecast in the ml_forecasts table.

        Args:
            symbol_id: UUID of the symbol
            horizon: Forecast horizon (e.g., '1D', '1W')
            overall_label: Overall trend label (Bullish/Neutral/Bearish)
            confidence: Model confidence score (0-1)
            points: List of forecast points
            supertrend_data: Optional SuperTrend AI data dict
            backtest_metrics: Optional backtest performance metrics
            quality_score: Optional quality score
            quality_issues: Optional list of quality issues
            model_agreement: Optional model agreement score
            training_stats: Optional training statistics
            sr_levels: Optional support/resistance levels dict
            sr_density: Optional S/R density count
            synthesis_data: Optional 3-layer forecast synthesis data
        """
        try:
            # Build forecast data for upsert keyed by (symbol_id, horizon)
            forecast_data = {
                "symbol_id": symbol_id,
                "horizon": horizon,
                "overall_label": overall_label,
                "confidence": confidence,
                "points": points,
            }

            # Add SuperTrend AI data if available
            if supertrend_data:
                forecast_data.update(
                    {
                        "supertrend_factor": supertrend_data.get("supertrend_factor"),
                        "supertrend_performance": supertrend_data.get("supertrend_performance"),
                        "supertrend_signal": supertrend_data.get("supertrend_signal"),
                        "trend_label": supertrend_data.get("trend_label"),
                        "trend_confidence": supertrend_data.get("trend_confidence"),
                        "stop_level": supertrend_data.get("stop_level"),
                        "trend_duration_bars": supertrend_data.get("trend_duration_bars"),
                    }
                )

            if backtest_metrics:
                forecast_data["backtest_metrics"] = backtest_metrics
            if quality_score is not None:
                forecast_data["quality_score"] = quality_score
            if quality_issues is not None:
                forecast_data["quality_issues"] = quality_issues
            if model_agreement is not None:
                forecast_data["model_agreement"] = model_agreement
            if training_stats is not None:
                forecast_data["training_stats"] = training_stats
            if sr_levels is not None:
                forecast_data["sr_levels"] = sr_levels
            if sr_density is not None:
                forecast_data["sr_density"] = sr_density
            if synthesis_data is not None:
                forecast_data["synthesis_data"] = synthesis_data

            # Upsert (insert or update on conflict) - no delete
            self.client.table("ml_forecasts").upsert(
                forecast_data,
                on_conflict="symbol_id,horizon",
            ).execute()

            logger.info(
                "Saved forecast: %s - %s (confidence: %.2f%%)",
                horizon,
                overall_label,
                confidence * 100,
            )

        except Exception as e:
            logger.error(
                "Error upserting forecast: %s",
                e,
            )
            raise

    def upsert_supertrend_signals(
        self,
        symbol: str,
        signals: list[dict[str, Any]],
    ) -> None:
        """
        Insert SuperTrend signals into the supertrend_signals table.

        Args:
            symbol: Stock ticker symbol
            signals: List of signal dictionaries from SuperTrendAI
        """
        if not signals:
            return

        try:
            for signal in signals:
                signal_data = {
                    "symbol": symbol.upper(),
                    "signal_date": signal["date"],
                    "signal_type": signal["type"],
                    "entry_price": signal["price"],
                    "stop_level": signal["stop_level"],
                    "target_price": signal.get("target_price"),
                    "confidence": signal.get("confidence"),
                    "atr_at_signal": signal.get("atr_at_signal"),
                    "risk_amount": signal.get("risk_amount"),
                    "reward_amount": signal.get("reward_amount"),
                    "outcome": "OPEN",
                }

                # Upsert (insert or update on conflict)
                self.client.table("supertrend_signals").upsert(
                    signal_data,
                    on_conflict="symbol,signal_date,signal_type",
                ).execute()

            logger.info(
                "Saved %s SuperTrend signals for %s",
                len(signals),
                symbol,
            )

        except Exception as e:
            logger.warning(
                "Error upserting SuperTrend signals for %s: %s",
                symbol,
                e,
            )

    def upsert_option_rank(
        self,
        underlying_symbol_id: str,
        contract_symbol: str,
        expiry: str,
        strike: float,
        side: str,
        ml_score: float,
        implied_vol: float,
        delta: float,
        gamma: float,
        theta: float,
        vega: float,
        rho: float,
        bid: float,
        ask: float,
        mark: float,
        last_price: float,
        volume: int,
        open_interest: int,
        run_at: str,
    ) -> None:
        """
        Insert or update an option rank in the options_ranks table.

        Args:
            underlying_symbol_id: UUID of the underlying symbol
            contract_symbol: Options contract symbol
            expiry: Expiration date (YYYY-MM-DD)
            strike: Strike price
            side: "call" or "put"
            ml_score: ML ranking score (0-1)
            implied_vol: Implied volatility
            delta: Option delta
            gamma: Option gamma
            theta: Option theta
            vega: Option vega
            rho: Option rho
            bid: Bid price
            ask: Ask price
            mark: Mark price
            last_price: Last traded price
            volume: Volume
            open_interest: Open interest
            run_at: Timestamp when ranking was generated
        """
        try:
            rank_data = {
                "underlying_symbol_id": underlying_symbol_id,
                "contract_symbol": contract_symbol,
                "expiry": expiry,
                "strike": strike,
                "side": side,
                "ml_score": ml_score,
                "implied_vol": implied_vol,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "rho": rho,
                "bid": bid,
                "ask": ask,
                "mark": mark,
                "last_price": last_price,
                "volume": volume,
                "open_interest": open_interest,
                "run_at": run_at,
            }

            # Delete existing rank for this contract if it exists
            self.client.table("options_ranks").delete().eq(
                "contract_symbol", contract_symbol
            ).execute()

            # Insert new rank
            self.client.table("options_ranks").insert(rank_data).execute()

            logger.debug(
                "Saved rank for %s (score: %.3f)",
                contract_symbol,
                ml_score,
            )

        except Exception as e:
            logger.error(
                "Error upserting option rank for %s: %s",
                contract_symbol,
                e,
            )
            raise

    def upsert_option_rank_extended(
        self,
        underlying_symbol_id: str,
        contract_symbol: str,
        expiry: str,
        strike: float,
        side: str,
        ml_score: float,
        implied_vol: float,
        delta: float,
        gamma: float,
        theta: float,
        vega: float,
        rho: float,
        bid: float,
        ask: float,
        mark: float,
        last_price: float,
        volume: int,
        open_interest: int,
        run_at: str,
        # Momentum Framework columns
        composite_rank: float = 0.0,
        momentum_score: float = 0.0,
        value_score: float = 0.0,
        greeks_score: float = 0.0,
        iv_rank: float = 0.0,
        spread_pct: float = 0.0,
        vol_oi_ratio: float = 0.0,
        liquidity_confidence: float = 1.0,
        ranking_mode: str | None = None,
        relative_value_score: float | None = None,
        entry_difficulty_score: float | None = None,
        ranking_stability_score: float | None = None,
        signal_discount: bool = False,
        signal_runner: bool = False,
        signal_greeks: bool = False,
        signal_buy: bool = False,
        signals: str = "",
    ) -> None:
        """
        Insert or update an option rank with momentum framework scores.

        Extends upsert_option_rank with additional columns for:
        - Composite rank (0-100)
        - Momentum, Value, Greeks component scores
        - IV Rank and spread metrics
        - Trading signals (DISCOUNT, RUNNER, GREEKS, BUY)
        """
        try:
            rank_data = {
                "underlying_symbol_id": underlying_symbol_id,
                "contract_symbol": contract_symbol,
                "expiry": expiry,
                "strike": strike,
                "side": side,
                "ml_score": ml_score,
                "implied_vol": implied_vol,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "rho": rho,
                "bid": bid,
                "ask": ask,
                "mark": mark,
                "last_price": last_price,
                "volume": volume,
                "open_interest": open_interest,
                "run_at": run_at,
                # Momentum Framework scores
                "composite_rank": composite_rank,
                "momentum_score": momentum_score,
                "value_score": value_score,
                "greeks_score": greeks_score,
                "iv_rank": iv_rank,
                "spread_pct": spread_pct,
                "vol_oi_ratio": vol_oi_ratio,
                "liquidity_confidence": liquidity_confidence,
                "ranking_mode": ranking_mode,
                "relative_value_score": relative_value_score,
                "entry_difficulty_score": entry_difficulty_score,
                "ranking_stability_score": ranking_stability_score,
                # Signals
                "signal_discount": signal_discount,
                "signal_runner": signal_runner,
                "signal_greeks": signal_greeks,
                "signal_buy": signal_buy,
                "signals": signals,
            }

            # Delete existing rank for this contract if it exists
            delete_query = (
                self.client.table("options_ranks").delete().eq("contract_symbol", contract_symbol)
            )
            if ranking_mode is not None:
                delete_query = delete_query.eq("ranking_mode", ranking_mode)
            delete_query.execute()

            # Insert new rank
            self.client.table("options_ranks").insert(rank_data).execute()

            logger.debug(
                "Saved extended rank for %s (composite: %.1f, signals: %s)",
                contract_symbol,
                composite_rank,
                signals,
            )

        except Exception as e:
            logger.error(
                "Error upserting extended option rank for %s: %s",
                contract_symbol,
                e,
            )
            raise

    def insert_options_snapshots(
        self,
        symbol_id: str,
        snapshots_df: pd.DataFrame,
    ) -> int:
        """Insert options snapshots into the database.

        Args:
            symbol_id: UUID of the underlying symbol
            snapshots_df: DataFrame with snapshot data

        Returns:
            Number of records inserted
        """
        if snapshots_df.empty:
            return 0

        inserted = 0
        records = []

        def _safe_float(v: Any) -> float | None:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            if pd.isna(v):
                return None
            try:
                return float(v)
            except Exception:
                return None

        def _safe_int(v: Any) -> int:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return 0
            if pd.isna(v):
                return 0
            try:
                return int(v)
            except Exception:
                return 0

        for _, row in snapshots_df.iterrows():
            record = {
                "underlying_symbol_id": symbol_id,
                "contract_symbol": str(row.get("contract_symbol", "")),
                "option_type": str(row.get("option_type", "call")),
                "strike": float(row.get("strike", 0) or 0),
                "expiration": str(row.get("expiration", "")),
                "bid": _safe_float(row.get("bid", 0)),
                "ask": _safe_float(row.get("ask", 0)),
                "last": _safe_float(row.get("last", 0)),
                "underlying_price": _safe_float(row.get("underlying_price", 0)),
                "volume": _safe_int(row.get("volume", 0)),
                "open_interest": _safe_int(row.get("open_interest", 0)),
                "delta": _safe_float(row.get("delta", 0)),
                "gamma": _safe_float(row.get("gamma", 0)),
                "theta": _safe_float(row.get("theta", 0)),
                "vega": _safe_float(row.get("vega", 0)),
                "rho": _safe_float(row.get("rho", 0)),
                "iv": _safe_float(row.get("iv", 0)),
                "snapshot_time": str(row.get("snapshot_time", "")),
            }
            records.append(record)

        try:
            # Use upsert with on_conflict to handle duplicates
            self.client.table("options_snapshots").upsert(
                records,
                on_conflict="contract_symbol,snapshot_time",
            ).execute()
            inserted = len(records)
            logger.info(
                "Inserted %s options snapshots",
                inserted,
            )
        except Exception as e:
            logger.error(
                "Error inserting options snapshots: %s",
                e,
            )
            raise

        return inserted

    def get_options_history(
        self,
        symbol: str,
        days_back: int = 30,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Get historical options snapshots for a symbol.

        Queries options_price_history first (preferred for momentum),
        then falls back to options_snapshots if no data found.

        Args:
            symbol: Stock ticker symbol
            days_back: Number of days of history to retrieve
            limit: Maximum records per contract (None = all)

        Returns:
            DataFrame with historical options data
        """
        try:
            symbol_id = self.get_symbol_id(symbol)
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_back)
            cutoff_date = cutoff.isoformat()

            # Try options_price_history first (multi-day snapshots)
            query = (
                self.client.table("options_price_history")
                .select("*")
                .eq("underlying_symbol_id", symbol_id)
                .gte("snapshot_at", cutoff_date)
                .order("snapshot_at", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()

            if response.data and len(response.data) > 0:
                df = pd.DataFrame(response.data)
                df["snapshot_time"] = pd.to_datetime(df["snapshot_at"])
                # Normalize column names for ranker compatibility
                if "side" in df.columns and "option_type" not in df.columns:
                    df["option_type"] = df["side"]
                if "last_price" in df.columns and "last" not in df.columns:
                    df["last"] = df["last_price"]
                logger.info(
                    "Fetched %s from price_history for %s",
                    len(df),
                    symbol,
                )
                return df

            # Fallback to options_snapshots
            query = (
                self.client.table("options_snapshots")
                .select("*")
                .eq("underlying_symbol_id", symbol_id)
                .gte("snapshot_time", cutoff_date)
                .order("snapshot_time", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()

            if not response.data:
                return pd.DataFrame()

            df = pd.DataFrame(response.data)
            df["snapshot_time"] = pd.to_datetime(df["snapshot_time"])

            logger.info(
                "Fetched %s from options_snapshots for %s",
                len(df),
                symbol,
            )
            return df

        except Exception as e:
            logger.error(
                "Error fetching options history for %s: %s",
                symbol,
                e,
            )
            return pd.DataFrame()

    def get_snapshot_count(
        self,
        symbol: str,
        days_back: int = 30,
    ) -> int:
        """Get count of unique snapshot days for a symbol.

        Args:
            symbol: Stock ticker symbol
            days_back: Number of days to check

        Returns:
            Number of unique snapshot days
        """
        try:
            symbol_id = self.get_symbol_id(symbol)

            cutoff = (pd.Timestamp.now() - pd.Timedelta(days=days_back)).isoformat()

            response = (
                self.client.table("options_snapshots")
                .select("snapshot_time")
                .eq("underlying_symbol_id", symbol_id)
                .gte(
                    "snapshot_time",
                    cutoff,
                )
                .execute()
            )

            if not response.data:
                return 0

            # Count unique days
            df = pd.DataFrame(response.data)
            df["date"] = pd.to_datetime(df["snapshot_time"]).dt.date
            unique_days = df["date"].nunique()

            return unique_days

        except Exception as e:
            logger.warning(
                "Error getting snapshot count for %s: %s",
                symbol,
                e,
            )
            return 0

    def get_latest_options_snapshot(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """Get the most recent options snapshot for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            DataFrame with latest snapshot data
        """
        try:
            symbol_id = self.get_symbol_id(symbol)

            # Get the most recent snapshot time
            time_response = (
                self.client.table("options_snapshots")
                .select("snapshot_time")
                .eq("underlying_symbol_id", symbol_id)
                .order("snapshot_time", desc=True)
                .limit(1)
                .execute()
            )

            if not time_response.data:
                return pd.DataFrame()

            latest_time = time_response.data[0]["snapshot_time"]

            # Get all records at that time
            response = (
                self.client.table("options_snapshots")
                .select("*")
                .eq("underlying_symbol_id", symbol_id)
                .eq("snapshot_time", latest_time)
                .execute()
            )

            if not response.data:
                return pd.DataFrame()

            df = pd.DataFrame(response.data)
            df["snapshot_time"] = pd.to_datetime(df["snapshot_time"])

            logger.info(
                "Fetched latest snapshot for %s: %s contracts",
                symbol,
                len(df),
            )
            return df

        except Exception as e:
            logger.error(
                "Error fetching latest snapshot for %s: %s",
                symbol,
                e,
            )
            return pd.DataFrame()

    def fetch_historical_forecasts_for_calibration(
        self,
        lookback_days: int = 90,
        min_samples: int = 100,
    ) -> pd.DataFrame | None:
        """
        Fetch historical forecasts with their outcomes for confidence
        calibration.

        Joins ml_forecasts with forecast_evaluations to get:
        - confidence: The predicted confidence
        - predicted_label: The predicted direction (bullish/neutral/bearish)
        - actual_label: The actual direction based on price movement

        Args:
            lookback_days: Number of days to look back
            min_samples: Minimum samples required

        Returns:
            DataFrame with confidence, predicted_label, actual_label columns
            or None if insufficient data
        """
        try:
            # Query forecast evaluations which have both predicted and actual
            response = (
                self.client.table("forecast_evaluations")
                .select(
                    "forecast_id, predicted_label, actual_label, " "ml_forecasts!inner(confidence)"
                )
                .gte(
                    "evaluation_date",
                    (pd.Timestamp.now() - pd.Timedelta(days=lookback_days)).isoformat(),
                )
                .limit(1000)
                .execute()
            )

            if not response.data or len(response.data) < min_samples:
                sample_count = len(response.data) if response.data else 0
                logger.info(
                    "Insufficient calibration data: %s samples (need %s)",
                    sample_count,
                    min_samples,
                )
                return None

            # Flatten the nested structure
            data = []
            for row in response.data:
                forecast_data = row.get("ml_forecasts", {})
                data.append(
                    {
                        "confidence": forecast_data.get("confidence", 0.5),
                        "predicted_label": row.get(
                            "predicted_label",
                            "neutral",
                        ),
                        "actual_label": row.get("actual_label", "neutral"),
                    }
                )

            df = pd.DataFrame(data)
            logger.info(
                "Fetched %s forecasts for calibration",
                len(df),
            )
            return df

        except Exception as e:
            logger.warning(
                "Could not fetch calibration data: %s",
                e,
            )
            return None

    # ========================================================================
    # INTRADAY CALIBRATION METHODS
    # ========================================================================

    def upsert_intraday_forecast(
        self,
        symbol_id: str,
        symbol: str,
        horizon: str,
        timeframe: str,
        overall_label: str,
        confidence: float,
        points: list[dict] | None,
        target_price: float,
        current_price: float,
        supertrend_component: float,
        sr_component: float,
        ensemble_component: float,
        supertrend_direction: str,
        ensemble_label: str,
        layers_agreeing: int,
        expires_at: str,
    ) -> str | None:
        """
        Insert an intraday forecast for weight calibration.

        Args:
            symbol_id: UUID of the symbol
            symbol: Stock ticker
            horizon: '15m' or '1h'
            timeframe: 'm15' or 'h1'
            overall_label: Predicted direction
            confidence: Prediction confidence
            target_price: Predicted target price
            current_price: Current price at forecast time
            supertrend_component: SuperTrend component value
            sr_component: S/R component value
            ensemble_component: Ensemble ML component value
            supertrend_direction: SuperTrend direction
            ensemble_label: Ensemble predicted label
            layers_agreeing: Number of agreeing layers
            expires_at: When forecast expires (ISO string)

        Returns:
            Forecast UUID if successful, None otherwise
        """
        try:
            forecast_data = {
                "symbol_id": symbol_id,
                "symbol": symbol.upper(),
                "horizon": horizon,
                "timeframe": timeframe,
                "overall_label": overall_label,
                "confidence": confidence,
                "target_price": target_price,
                "current_price": current_price,
                "supertrend_component": supertrend_component,
                "sr_component": sr_component,
                "ensemble_component": ensemble_component,
                "supertrend_direction": supertrend_direction,
                "ensemble_label": ensemble_label,
                "layers_agreeing": layers_agreeing,
                "expires_at": expires_at,
            }

            if points is not None:
                forecast_data["points"] = points

            response = self.client.table("ml_forecasts_intraday").insert(forecast_data).execute()

            if response.data:
                forecast_id = response.data[0]["id"]
                logger.debug(
                    "Saved intraday %s forecast for %s: %s",
                    horizon,
                    symbol,
                    overall_label,
                )
                return forecast_id
            return None

        except Exception as e:
            logger.error(
                "Error upserting intraday forecast for %s: %s",
                symbol,
                e,
            )
            return None

    def insert_intraday_forecast_path(
        self,
        symbol_id: str,
        symbol: str,
        timeframe: str,
        horizon: str,
        steps: int,
        interval_sec: int,
        overall_label: str,
        confidence: float,
        model_type: str,
        points: list[dict],
        expires_at: str,
    ) -> str | None:
        try:
            payload = {
                "symbol_id": symbol_id,
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "horizon": horizon,
                "steps": int(steps),
                "interval_sec": int(interval_sec),
                "overall_label": overall_label,
                "confidence": float(confidence),
                "model_type": model_type,
                "points": points,
                "expires_at": expires_at,
            }

            response = self.client.table("ml_forecast_paths_intraday").insert(payload).execute()

            if response.data:
                return response.data[0]["id"]
            return None
        except Exception as exc:
            logger.error(
                "Error inserting intraday forecast path for %s %s: %s",
                symbol,
                timeframe,
                exc,
            )
            return None

    def get_pending_intraday_evaluations(
        self,
        horizon: str | None = None,
    ) -> list[dict]:
        """
        Get intraday forecasts that have expired and need evaluation.

        Args:
            horizon: Optional filter for '15m' or '1h'

        Returns:
            List of forecast dicts awaiting evaluation
        """
        try:
            response = self.client.rpc(
                "get_pending_intraday_evaluations",
                {"p_horizon": horizon},
            ).execute()

            return response.data or []

        except Exception as e:
            logger.error("Error fetching pending intraday evaluations: %s", e)
            return []

    def save_intraday_evaluation(
        self,
        forecast_id: str,
        symbol_id: str,
        symbol: str,
        horizon: str,
        predicted_label: str,
        predicted_price: float,
        predicted_confidence: float,
        realized_price: float,
        realized_return: float,
        realized_label: str,
        direction_correct: bool,
        price_error: float,
        price_error_pct: float,
        supertrend_direction_correct: bool,
        sr_containment: bool,
        ensemble_direction_correct: bool,
        forecast_created_at: str,
        option_b_outcome: str | None = None,
        option_b_direction_correct: bool | None = None,
        option_b_within_tolerance: bool | None = None,
        option_b_mape: float | None = None,
        option_b_bias: float | None = None,
    ) -> bool:
        """
        Save an intraday forecast evaluation result.

        Returns:
            True if successful, False otherwise
        """
        try:
            eval_data = {
                "forecast_id": forecast_id,
                "symbol_id": symbol_id,
                "symbol": symbol.upper(),
                "horizon": horizon,
                "predicted_label": predicted_label,
                "predicted_price": predicted_price,
                "predicted_confidence": predicted_confidence,
                "realized_price": realized_price,
                "realized_return": realized_return,
                "realized_label": realized_label,
                "direction_correct": direction_correct,
                "price_error": price_error,
                "price_error_pct": price_error_pct,
                "supertrend_direction_correct": supertrend_direction_correct,
                "sr_containment": sr_containment,
                "ensemble_direction_correct": ensemble_direction_correct,
                "forecast_created_at": forecast_created_at,
            }

            # Add Option B fields if provided
            if option_b_outcome is not None:
                eval_data["option_b_outcome"] = option_b_outcome
            if option_b_direction_correct is not None:
                eval_data["option_b_direction_correct"] = option_b_direction_correct
            if option_b_within_tolerance is not None:
                eval_data["option_b_within_tolerance"] = option_b_within_tolerance
            if option_b_mape is not None:
                eval_data["option_b_mape"] = option_b_mape
            if option_b_bias is not None:
                eval_data["option_b_bias"] = option_b_bias

            self.client.table("ml_forecast_evaluations_intraday").insert(eval_data).execute()

            logger.debug(
                "Saved intraday evaluation for %s %s: correct=%s",
                symbol,
                horizon,
                direction_correct,
            )
            return True

        except Exception as e:
            logger.error(
                "Error saving intraday evaluation for %s: %s",
                symbol,
                e,
            )
            return False

    def get_intraday_calibration_stats(
        self,
        symbol_id: str,
        lookback_hours: int = 72,
    ) -> dict | None:
        """
        Get aggregated stats for intraday calibration.

        Args:
            symbol_id: UUID of the symbol
            lookback_hours: Hours of history to consider

        Returns:
            Dict with per-horizon accuracy stats
        """
        try:
            response = self.client.rpc(
                "get_intraday_calibration_data",
                {
                    "p_symbol_id": symbol_id,
                    "p_lookback_hours": lookback_hours,
                },
            ).execute()

            if not response.data:
                return None

            return {row["horizon"]: row for row in response.data}

        except Exception as e:
            logger.error(
                "Error fetching intraday calibration stats: %s",
                e,
            )
            return None

    def get_intraday_evaluations_for_calibration(
        self,
        symbol_id: str,
        lookback_hours: int = 72,
    ) -> pd.DataFrame:
        """
        Get raw intraday evaluation data for weight optimization.

        Args:
            symbol_id: UUID of the symbol
            lookback_hours: Hours of history to fetch

        Returns:
            DataFrame with evaluation data and component values
        """
        try:
            response = self.client.rpc(
                "get_intraday_evaluations_for_calibration",
                {
                    "p_symbol_id": symbol_id,
                    "p_lookback_hours": lookback_hours,
                },
            ).execute()

            if not response.data:
                return pd.DataFrame()

            df = pd.DataFrame(response.data)
            df["evaluated_at"] = pd.to_datetime(df["evaluated_at"])
            return df

        except Exception as e:
            logger.error(
                "Error fetching intraday evaluations for calibration: %s",
                e,
            )
            return pd.DataFrame()

    def update_symbol_weights_from_intraday(
        self,
        symbol_id: str,
        horizon: str,
        supertrend_weight: float,
        sr_weight: float,
        ensemble_weight: float,
        sample_count: int,
        accuracy: float,
    ) -> bool:
        """
        Update symbol model weights with intraday-calibrated values.

        Args:
            symbol_id: UUID of the symbol
            horizon: Forecast horizon
            supertrend_weight: Calibrated SuperTrend weight
            sr_weight: Calibrated S/R weight
            ensemble_weight: Calibrated ensemble weight
            sample_count: Number of samples used for calibration
            accuracy: Achieved accuracy with these weights

        Returns:
            True if successful
        """
        try:
            weight_data = {
                "symbol_id": symbol_id,
                "horizon": horizon,
                "synth_weights": {
                    "layer_weights": {
                        "supertrend_component": supertrend_weight,
                        "sr_component": sr_weight,
                        "ensemble_component": ensemble_weight,
                    }
                },
                "calibration_source": "intraday",
                "intraday_sample_count": sample_count,
                "intraday_accuracy": accuracy,
                "last_updated": pd.Timestamp.now().isoformat(),
            }

            # Upsert - update if exists, insert if new
            self.client.table("symbol_model_weights").upsert(
                weight_data,
                on_conflict="symbol_id,horizon",
            ).execute()

            logger.info(
                "Updated symbol weights for %s %s from intraday: "
                "ST=%.2f, SR=%.2f, ML=%.2f (n=%d, acc=%.1f%%)",
                symbol_id,
                horizon,
                supertrend_weight,
                sr_weight,
                ensemble_weight,
                sample_count,
                accuracy * 100,
            )
            return True

        except Exception as e:
            logger.error(
                "Error updating symbol weights from intraday: %s",
                e,
            )
            return False

    def get_calibrated_weights(
        self,
        symbol_id: str,
        horizon: str,
        min_samples: int = 50,
    ) -> dict | None:
        """
        Get intraday-calibrated weights for a symbol if available.

        Args:
            symbol_id: UUID of the symbol
            horizon: Forecast horizon
            min_samples: Minimum samples required to use calibrated weights

        Returns:
            Dict with layer weights or None if not enough data
        """
        try:
            response = (
                self.client.table("symbol_model_weights")
                .select("synth_weights, calibration_source, intraday_sample_count")
                .eq("symbol_id", symbol_id)
                .eq("horizon", horizon)
                .single()
                .execute()
            )

            if not response.data:
                return None

            data = response.data
            source = data.get("calibration_source")
            sample_count = data.get("intraday_sample_count", 0)

            # Only use intraday weights if sufficient samples
            if source == "intraday" and sample_count >= min_samples:
                synth_weights = data.get("synth_weights", {})
                return synth_weights.get("layer_weights")

            return None

        except Exception as e:
            logger.debug(
                "No calibrated weights for %s %s: %s",
                symbol_id,
                horizon,
                e,
            )
            return None

    def execute_rpc(
        self,
        function_name: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict] | None:
        """
        Execute a Supabase RPC function.

        Args:
            function_name: Name of the RPC function to call
            params: Optional parameters to pass to the function

        Returns:
            List of result rows, or None if error
        """
        try:
            response = self.client.rpc(
                function_name,
                params or {},
            ).execute()
            return response.data
        except Exception as e:
            logger.error(
                "Error executing RPC function %s: %s",
                function_name,
                e,
            )
            return None

    def close(self) -> None:
        """Close the Supabase client (no-op for REST API)."""
        logger.info("Supabase client closed")


# Global instance
db = SupabaseDatabase()
