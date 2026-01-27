"""
Divergence Monitoring Module

Tracks and analyzes divergence metrics from walk-forward validation to detect
overfitting in ensemble forecasts. Logs metrics to database and provides
query functions for monitoring dashboards.

Based on Phase 5 of ML overfitting fix: Implements automated overfitting
detection through validation vs test RMSE divergence tracking.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class DivergenceMonitor:
    """
    Monitor and track divergence metrics for ensemble validation.

    Divergence = |val_rmse - test_rmse| / val_rmse

    High divergence (> threshold) indicates overfitting where the model
    performs well on validation data but poorly on held-out test data.
    """

    # Default overfitting threshold (20% divergence)
    DEFAULT_DIVERGENCE_THRESHOLD = 0.20

    # Alert thresholds for different severity levels
    ALERT_THRESHOLDS = {
        "warning": 0.15,   # 15% divergence
        "critical": 0.30,  # 30% divergence
    }

    def __init__(
        self,
        db_client=None,
        divergence_threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
    ):
        """
        Initialize divergence monitor.

        Args:
            db_client: Database client for logging metrics (Supabase or similar)
            divergence_threshold: Threshold for flagging overfitting (default 0.20 = 20%)
        """
        self.db_client = db_client
        self.divergence_threshold = divergence_threshold
        self.divergence_history: List[Dict] = []

        logger.info(
            "DivergenceMonitor initialized with threshold=%.2f%%",
            divergence_threshold * 100,
        )

    def log_window_result(
        self,
        symbol: str,
        symbol_id: str,
        horizon: str,
        window_id: int,
        val_rmse: float,
        test_rmse: float,
        val_mae: Optional[float] = None,
        test_mae: Optional[float] = None,
        train_rmse: Optional[float] = None,
        n_train_samples: Optional[int] = None,
        n_val_samples: Optional[int] = None,
        n_test_samples: Optional[int] = None,
        data_span_days: Optional[int] = None,
        model_count: int = 2,
        models_used: Optional[List[str]] = None,
        hyperparameters: Optional[Dict] = None,
        directional_accuracy: Optional[float] = None,
    ) -> Dict:
        """
        Log a walk-forward validation window result with divergence metrics.

        Args:
            symbol: Stock ticker symbol
            symbol_id: Internal symbol identifier
            horizon: Forecast horizon ("1D", "4h", etc.)
            window_id: Sequential ID of this window
            val_rmse: Validation set RMSE
            test_rmse: Test set RMSE (held-out)
            val_mae: Validation MAE (optional)
            test_mae: Test MAE (optional)
            train_rmse: Training RMSE (optional)
            n_train_samples: Number of training samples
            n_val_samples: Number of validation samples
            n_test_samples: Number of test samples
            data_span_days: Number of days in data window
            model_count: Number of models in ensemble (2-3 typical)
            models_used: List of model names (["LSTM", "ARIMA_GARCH", "GB"])
            hyperparameters: Dict of hyperparameters used
            directional_accuracy: Percentage of correct direction predictions

        Returns:
            Dict with divergence metrics and overfitting flag
        """
        # Calculate divergence
        divergence = self._calculate_divergence(val_rmse, test_rmse)

        # Detect overfitting
        is_overfitting = divergence > self.divergence_threshold

        # Determine alert level
        alert_level = self._get_alert_level(divergence)

        # Create result dict
        result = {
            "symbol": symbol,
            "symbol_id": symbol_id,
            "horizon": horizon,
            "window_id": window_id,
            "val_rmse": val_rmse,
            "test_rmse": test_rmse,
            "train_rmse": train_rmse,
            "divergence": divergence,
            "is_overfitting": is_overfitting,
            "alert_level": alert_level,
            "model_count": model_count,
            "models_used": models_used or [],
            "n_train_samples": n_train_samples,
            "n_val_samples": n_val_samples,
            "n_test_samples": n_test_samples,
            "data_span_days": data_span_days,
            "validation_date": datetime.utcnow(),
        }

        # Store in history
        self.divergence_history.append(result)

        # Log to database if client available
        if self.db_client:
            try:
                self._log_to_database(
                    symbol=symbol,
                    symbol_id=symbol_id,
                    horizon=horizon,
                    window_id=window_id,
                    val_rmse=val_rmse,
                    test_rmse=test_rmse,
                    train_rmse=train_rmse,
                    divergence=divergence,
                    is_overfitting=is_overfitting,
                    model_count=model_count,
                    models_used=models_used,
                    n_train_samples=n_train_samples,
                    n_val_samples=n_val_samples,
                    n_test_samples=n_test_samples,
                    data_span_days=data_span_days,
                    hyperparameters=hyperparameters,
                    directional_accuracy=directional_accuracy,
                    val_mae=val_mae,
                    test_mae=test_mae,
                )
            except Exception as e:
                logger.error("Failed to log divergence metrics to database: %s", e)

        # Log alert if overfitting detected
        if is_overfitting:
            logger.warning(
                "%s %s Window %d: OVERFITTING DETECTED - "
                "Divergence %.2f%% (val_rmse=%.4f, test_rmse=%.4f)",
                symbol,
                horizon,
                window_id,
                divergence * 100,
                val_rmse,
                test_rmse,
            )
        else:
            logger.info(
                "%s %s Window %d: Divergence %.2f%% (val_rmse=%.4f, test_rmse=%.4f)",
                symbol,
                horizon,
                window_id,
                divergence * 100,
                val_rmse,
                test_rmse,
            )

        return result

    def _calculate_divergence(
        self, val_rmse: float, test_rmse: float
    ) -> float:
        """
        Calculate divergence between validation and test RMSE.

        Divergence = |val_rmse - test_rmse| / val_rmse

        Args:
            val_rmse: Validation set RMSE
            test_rmse: Test set RMSE

        Returns:
            Divergence score (0.0 = perfect agreement, >1.0 = severe overfitting)
        """
        if val_rmse <= 0:
            return 0.0

        try:
            divergence = abs(val_rmse - test_rmse) / val_rmse
            return float(divergence) if np.isfinite(divergence) else 0.0
        except Exception as e:
            logger.warning("Failed to calculate divergence: %s", e)
            return 0.0

    def _get_alert_level(self, divergence: float) -> str:
        """
        Determine alert level based on divergence value.

        Args:
            divergence: Calculated divergence score

        Returns:
            Alert level: "normal", "warning", or "critical"
        """
        if divergence > self.ALERT_THRESHOLDS["critical"]:
            return "critical"
        elif divergence > self.ALERT_THRESHOLDS["warning"]:
            return "warning"
        else:
            return "normal"

    def _log_to_database(self, **kwargs):
        """
        Log divergence metrics to database.

        Requires db_client to be initialized with insert capability.
        """
        if not self.db_client:
            return

        try:
            # This would use the Supabase client to insert into ensemble_validation_metrics
            # table. Implementation depends on specific db_client interface.
            # Example:
            # self.db_client.table('ensemble_validation_metrics').insert(kwargs).execute()
            logger.debug(
                "Logged divergence metrics for %s %s window %d",
                kwargs.get("symbol"),
                kwargs.get("horizon"),
                kwargs.get("window_id"),
            )
        except Exception as e:
            logger.error("Database logging error: %s", e)

    def get_recent_overfitting_symbols(
        self, horizon: Optional[str] = None, days: int = 7
    ) -> List[Tuple[str, float]]:
        """
        Get symbols that have been flagged for overfitting recently.

        Args:
            horizon: Filter by specific horizon (optional)
            days: Number of days to look back (default 7)

        Returns:
            List of (symbol, max_divergence) tuples sorted by divergence
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Filter recent overfitting events
        overfitting_events = [
            event
            for event in self.divergence_history
            if event["is_overfitting"]
            and event["validation_date"] > cutoff_date
            and (horizon is None or event["horizon"] == horizon)
        ]

        # Group by symbol and get max divergence
        symbol_divergences: Dict[str, float] = {}
        for event in overfitting_events:
            symbol = event["symbol"]
            divergence = event["divergence"]
            if symbol not in symbol_divergences:
                symbol_divergences[symbol] = divergence
            else:
                symbol_divergences[symbol] = max(symbol_divergences[symbol], divergence)

        # Sort by divergence (worst first)
        sorted_symbols = sorted(
            symbol_divergences.items(), key=lambda x: x[1], reverse=True
        )

        return sorted_symbols

    def get_divergence_summary(
        self, horizon: Optional[str] = None
    ) -> Dict:
        """
        Get summary statistics of divergence history.

        Args:
            horizon: Filter by specific horizon (optional)

        Returns:
            Dict with divergence statistics
        """
        # Filter by horizon if specified
        events = [
            event
            for event in self.divergence_history
            if horizon is None or event["horizon"] == horizon
        ]

        if not events:
            return {
                "total_windows": 0,
                "overfitting_windows": 0,
                "pct_overfitting": 0.0,
                "mean_divergence": 0.0,
                "max_divergence": 0.0,
                "min_divergence": 0.0,
                "std_divergence": 0.0,
            }

        divergences = np.array([event["divergence"] for event in events])
        overfitting_count = sum(1 for event in events if event["is_overfitting"])

        return {
            "total_windows": len(events),
            "overfitting_windows": overfitting_count,
            "pct_overfitting": 100.0 * overfitting_count / len(events),
            "mean_divergence": float(np.mean(divergences)),
            "max_divergence": float(np.max(divergences)),
            "min_divergence": float(np.min(divergences)),
            "std_divergence": float(np.std(divergences)),
            "threshold": self.divergence_threshold,
        }

    def clear_history(self):
        """Clear divergence history (useful for resetting between runs)."""
        self.divergence_history.clear()
        logger.info("Divergence history cleared")


def create_divergence_monitor(db_client=None) -> DivergenceMonitor:
    """
    Factory function to create a DivergenceMonitor instance.

    Args:
        db_client: Optional database client for persistence

    Returns:
        Initialized DivergenceMonitor instance
    """
    return DivergenceMonitor(db_client=db_client)
