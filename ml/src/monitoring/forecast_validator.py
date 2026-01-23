"""
Forecast Validator: Accuracy and Edge Validation
================================================

Validates forecast accuracy against realized outcomes, measuring:
- Direction accuracy
- Target precision
- Band efficiency
- Edge metrics (expected vs realized)

Usage:
    validator = ForecastValidator()
    metrics = validator.validate(historical_forecasts, actual_prices)
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ValidationMetrics:
    """Forecast validation metrics."""

    # Direction accuracy
    direction_accuracy: float  # % of correct direction predictions

    # Target precision
    avg_target_error_pct: float  # Average |target - actual| / actual
    target_within_1atr: float  # % of targets within 1 ATR of actual

    # Band efficiency
    band_capture_rate: float  # % of actual moves within predicted bands
    band_too_wide_rate: float  # % where bands > 2x actual range
    band_too_narrow_rate: float  # % where actual exceeded bands

    # Edge metrics
    expected_edge: float  # (win_rate * avg_win) - (loss_rate * avg_loss)
    realized_edge: float  # Actual PnL following forecasts
    edge_gap: float  # expected - realized (should be near 0 if calibrated)

    # Sample size
    n_samples: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "direction_accuracy": round(self.direction_accuracy * 100, 1),
            "avg_target_error_pct": round(self.avg_target_error_pct, 2),
            "target_within_1atr": (
                round(self.target_within_1atr * 100, 1)
                if not np.isnan(self.target_within_1atr)
                else None
            ),
            "band_capture_rate": round(self.band_capture_rate * 100, 1),
            "band_too_wide_rate": round(self.band_too_wide_rate * 100, 1),
            "band_too_narrow_rate": round(self.band_too_narrow_rate * 100, 1),
            "expected_edge": round(self.expected_edge, 3),
            "realized_edge": round(self.realized_edge, 3),
            "edge_gap": round(self.edge_gap, 3),
            "n_samples": self.n_samples,
        }

    def is_well_calibrated(self) -> bool:
        """Check if forecasts are well-calibrated (edge gap < 5%)."""
        return abs(self.edge_gap) < 0.05

    def get_quality_grade(self) -> str:
        """Get overall quality grade (A-F)."""
        score = 0

        # Direction accuracy (40% weight)
        if self.direction_accuracy >= 0.65:
            score += 40
        elif self.direction_accuracy >= 0.55:
            score += 30
        elif self.direction_accuracy >= 0.50:
            score += 20
        else:
            score += 10

        # Band capture rate (30% weight)
        if self.band_capture_rate >= 0.80:
            score += 30
        elif self.band_capture_rate >= 0.70:
            score += 22
        elif self.band_capture_rate >= 0.60:
            score += 15
        else:
            score += 5

        # Edge calibration (30% weight)
        if abs(self.edge_gap) < 0.02:
            score += 30
        elif abs(self.edge_gap) < 0.05:
            score += 22
        elif abs(self.edge_gap) < 0.10:
            score += 15
        else:
            score += 5

        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"


class ForecastValidator:
    """
    Validates forecast accuracy against realized outcomes.

    Usage:
        validator = ForecastValidator()
        metrics = validator.validate(historical_forecasts, actual_prices)
    """

    # Horizon mapping: horizon string -> trading days
    HORIZON_DAYS = {
        "1D": 1,
        "1W": 5,
        "1M": 20,
        "2M": 40,
        "3M": 60,
        "6M": 120,
    }

    def validate(
        self,
        forecasts: pd.DataFrame,
        actuals: pd.DataFrame,
        atr_column: str = "atr",
    ) -> ValidationMetrics:
        """
        Validate forecasts against actual outcomes.

        Args:
            forecasts: DataFrame with columns:
                - symbol, horizon, label (or overall_label), confidence
                - target (or predicted_value), upper_band (or upper), lower_band (or lower)
                - forecast_date (or created_at, run_at)
                - entry_price or current_price (optional)
            actuals: DataFrame with columns:
                - symbol, date (or ts), close
                - high, low (optional, for band analysis)
                - atr (optional, for target precision)

        Returns:
            ValidationMetrics with accuracy analysis
        """
        matched = self._match_forecasts_to_actuals(forecasts, actuals, atr_column)

        if len(matched) == 0:
            logger.warning("No matched forecasts found for validation")
            return self._empty_metrics()

        logger.info(f"Validating {len(matched)} matched forecasts")

        # Direction accuracy
        if (
            "direction_correct" in matched.columns
            and matched["direction_correct"].notna().any()
        ):
            direction_correct = matched["direction_correct"].fillna(False)
        else:
            direction_correct = (
                matched["predicted_direction"] == matched["actual_direction"]
            )
        direction_accuracy = direction_correct.mean()

        # Target precision
        target_error = (matched["target"] - matched["actual_close"]).abs() / matched["actual_close"]
        avg_target_error = target_error.mean()

        if atr_column in matched.columns and matched[atr_column].notna().any():
            # Calculate error in ATR units
            atr_error = (matched["target"] - matched["actual_close"]).abs() / matched[atr_column]
            target_within_1atr = (atr_error <= 1.0).mean()
        else:
            target_within_1atr = np.nan

        # Band efficiency
        within_bands = (matched["actual_close"] >= matched["lower_band"]) & (
            matched["actual_close"] <= matched["upper_band"]
        )
        band_capture_rate = within_bands.mean()

        predicted_range = matched["upper_band"] - matched["lower_band"]

        # Use actual high/low if available, otherwise use close
        if "actual_high" in matched.columns and "actual_low" in matched.columns:
            actual_range = matched["actual_high"] - matched["actual_low"]
        else:
            actual_range = matched["actual_close"] * 0.02  # Assume 2% range

        # Avoid division by zero
        valid_range_mask = actual_range > 0
        band_ratio = pd.Series(index=matched.index, dtype=float)
        band_ratio[valid_range_mask] = (
            predicted_range[valid_range_mask] / actual_range[valid_range_mask]
        )

        band_too_wide = (band_ratio > 2.0) & valid_range_mask
        band_too_narrow = ~within_bands

        # Edge calculation
        returns_following = matched["actual_return"]

        # For edge, use signed returns aligned with prediction
        aligned_returns = returns_following.copy()
        bearish_mask = matched["predicted_direction"] == "bearish"
        aligned_returns[bearish_mask] = -aligned_returns[bearish_mask]

        wins = aligned_returns > 0
        losses = aligned_returns < 0

        win_rate = wins.mean() if len(wins) > 0 else 0
        avg_win = aligned_returns[wins].mean() if wins.any() else 0
        avg_loss = aligned_returns[losses].abs().mean() if losses.any() else 0

        expected_edge = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        realized_edge = aligned_returns.mean()

        metrics = ValidationMetrics(
            direction_accuracy=direction_accuracy,
            avg_target_error_pct=avg_target_error * 100,
            target_within_1atr=target_within_1atr if not np.isnan(target_within_1atr) else 0.0,
            band_capture_rate=band_capture_rate,
            band_too_wide_rate=band_too_wide.mean(),
            band_too_narrow_rate=band_too_narrow.mean(),
            expected_edge=expected_edge,
            realized_edge=realized_edge,
            edge_gap=expected_edge - realized_edge,
            n_samples=len(matched),
        )

        logger.info(
            f"Validation complete: direction={metrics.direction_accuracy:.1%}, "
            f"band_capture={metrics.band_capture_rate:.1%}, "
            f"edge_gap={metrics.edge_gap:.3f}, grade={metrics.get_quality_grade()}"
        )

        return metrics

    def _match_forecasts_to_actuals(
        self,
        forecasts: pd.DataFrame,
        actuals: pd.DataFrame,
        atr_column: str = "atr",
    ) -> pd.DataFrame:
        """Match each forecast to its outcome."""
        matched_rows = []

        # Normalize column names for forecasts
        forecasts = forecasts.copy()
        if "overall_label" in forecasts.columns and "label" not in forecasts.columns:
            forecasts["label"] = forecasts["overall_label"]
        if "predicted_value" in forecasts.columns and "target" not in forecasts.columns:
            forecasts["target"] = forecasts["predicted_value"]
        if "upper" in forecasts.columns and "upper_band" not in forecasts.columns:
            forecasts["upper_band"] = forecasts["upper"]
        if "lower" in forecasts.columns and "lower_band" not in forecasts.columns:
            forecasts["lower_band"] = forecasts["lower"]

        # Find forecast date column
        date_col = None
        for col in ["forecast_date", "created_at", "run_at"]:
            if col in forecasts.columns:
                date_col = col
                break

        if date_col is None:
            logger.warning("No date column found in forecasts")
            return pd.DataFrame()

        # Normalize actuals date column
        actuals = actuals.copy()
        if "ts" in actuals.columns and "date" not in actuals.columns:
            actuals["date"] = pd.to_datetime(
                actuals["ts"], unit="s" if actuals["ts"].dtype == np.int64 else None
            )

        for _, forecast in forecasts.iterrows():
            symbol = forecast.get("symbol") or forecast.get("ticker")
            if symbol is None:
                continue

            horizon = forecast.get("horizon", "1D")
            horizon_days = self._parse_horizon(horizon)

            try:
                # Handle ISO8601 format with timezone info
                forecast_date = pd.to_datetime(forecast[date_col], format='ISO8601', errors='coerce')
                if pd.isna(forecast_date):
                    # Fallback to mixed format if ISO8601 fails
                    forecast_date = pd.to_datetime(forecast[date_col], format='mixed', errors='coerce')
                if pd.isna(forecast_date):
                    continue
            except Exception:
                continue

            outcome_date = forecast_date + pd.Timedelta(days=horizon_days)

            # Find actual price at outcome date
            symbol_actuals = (
                actuals[actuals["symbol"] == symbol] if "symbol" in actuals.columns else actuals
            )

            if "date" in symbol_actuals.columns:
                # Use ISO8601 format to handle various timestamp formats
                try:
                    actuals_dates = pd.to_datetime(symbol_actuals["date"], format='ISO8601', errors='coerce')
                except Exception:
                    # Fallback to mixed format if ISO8601 fails
                    actuals_dates = pd.to_datetime(symbol_actuals["date"], format='mixed', errors='coerce')
                
                outcome = symbol_actuals[
                    actuals_dates >= outcome_date
                ].head(1)
            else:
                continue

            if len(outcome) == 0:
                continue

            actual_close = outcome.iloc[0]["close"]
            realized_label = outcome.iloc[0].get("realized_label")
            direction_correct = outcome.iloc[0].get("direction_correct")

            # Get entry price
            entry_price = forecast.get("entry_price") or forecast.get("current_price")
            if entry_price is None:
                # Try to get from actuals at forecast date
                entry_match = symbol_actuals[
                    pd.to_datetime(symbol_actuals["date"]) <= forecast_date
                ].tail(1)
                if len(entry_match) > 0:
                    entry_price = entry_match.iloc[0]["close"]
                else:
                    entry_price = actual_close

            # Get target and bands
            target = forecast.get("target")
            if target is None:
                # Try to extract from points JSON if available
                points = forecast.get("points")
                if isinstance(points, list) and len(points) > 0:
                    target = points[0].get("value", entry_price)
                else:
                    target = entry_price

            upper_band = forecast.get("upper_band", target * 1.02)
            lower_band = forecast.get("lower_band", target * 0.98)

            # Calculate actual return
            actual_return = (actual_close - entry_price) / entry_price if entry_price > 0 else 0

            # Determine directions
            predicted_label = str(forecast.get("label", "neutral")).lower()
            actual_direction = (
                str(realized_label).lower()
                if realized_label is not None
                else (
                    "bullish"
                    if actual_return > 0.005
                    else ("bearish" if actual_return < -0.005 else "neutral")
                )
            )

            row = {
                "symbol": symbol,
                "horizon": horizon,
                "forecast_date": forecast_date,
                "target": target,
                "upper_band": upper_band,
                "lower_band": lower_band,
                "entry_price": entry_price,
                "actual_close": actual_close,
                "actual_return": actual_return,
                "predicted_direction": predicted_label,
                "actual_direction": actual_direction,
                "direction_correct": direction_correct,
                "confidence": forecast.get("confidence", 0.5),
            }

            # Add optional fields
            if "high" in outcome.columns:
                row["actual_high"] = outcome.iloc[0]["high"]
            if "low" in outcome.columns:
                row["actual_low"] = outcome.iloc[0]["low"]
            if atr_column in outcome.columns:
                row[atr_column] = outcome.iloc[0][atr_column]

            matched_rows.append(row)

        return pd.DataFrame(matched_rows)

    def _parse_horizon(self, horizon: str) -> int:
        """Parse horizon string to trading days."""
        return self.HORIZON_DAYS.get(horizon, 1)

    def _empty_metrics(self) -> ValidationMetrics:
        """Return empty metrics when no data."""
        return ValidationMetrics(
            direction_accuracy=0.0,
            avg_target_error_pct=0.0,
            target_within_1atr=0.0,
            band_capture_rate=0.0,
            band_too_wide_rate=0.0,
            band_too_narrow_rate=0.0,
            expected_edge=0.0,
            realized_edge=0.0,
            edge_gap=0.0,
            n_samples=0,
        )

    def validate_by_horizon(
        self,
        forecasts: pd.DataFrame,
        actuals: pd.DataFrame,
    ) -> dict[str, ValidationMetrics]:
        """
        Validate forecasts grouped by horizon.

        Returns:
            Dict mapping horizon to ValidationMetrics
        """
        results = {}

        for horizon in forecasts["horizon"].unique():
            horizon_forecasts = forecasts[forecasts["horizon"] == horizon]
            metrics = self.validate(horizon_forecasts, actuals)
            results[horizon] = metrics

        return results

    def validate_by_symbol(
        self,
        forecasts: pd.DataFrame,
        actuals: pd.DataFrame,
    ) -> dict[str, ValidationMetrics]:
        """
        Validate forecasts grouped by symbol.

        Returns:
            Dict mapping symbol to ValidationMetrics
        """
        results = {}

        symbol_col = "symbol" if "symbol" in forecasts.columns else "ticker"
        for symbol in forecasts[symbol_col].unique():
            symbol_forecasts = forecasts[forecasts[symbol_col] == symbol]
            metrics = self.validate(symbol_forecasts, actuals)
            results[symbol] = metrics

        return results

    def generate_report(self, metrics: ValidationMetrics) -> str:
        """Generate human-readable validation report."""
        lines = [
            "=" * 50,
            "FORECAST VALIDATION REPORT",
            "=" * 50,
            f"Samples: {metrics.n_samples}",
            f"Quality Grade: {metrics.get_quality_grade()}",
            "",
            "DIRECTION ACCURACY",
            "-" * 30,
            f"  Accuracy: {metrics.direction_accuracy:.1%}",
            "",
            "TARGET PRECISION",
            "-" * 30,
            f"  Avg Error: {metrics.avg_target_error_pct:.2f}%",
            (
                f"  Within 1 ATR: {metrics.target_within_1atr:.1%}"
                if metrics.target_within_1atr > 0
                else "  Within 1 ATR: N/A"
            ),
            "",
            "BAND EFFICIENCY",
            "-" * 30,
            f"  Capture Rate: {metrics.band_capture_rate:.1%}",
            f"  Too Wide: {metrics.band_too_wide_rate:.1%}",
            f"  Too Narrow: {metrics.band_too_narrow_rate:.1%}",
            "",
            "EDGE ANALYSIS",
            "-" * 30,
            f"  Expected Edge: {metrics.expected_edge:.3f}",
            f"  Realized Edge: {metrics.realized_edge:.3f}",
            f"  Edge Gap: {metrics.edge_gap:.3f}"
            + (" (WELL CALIBRATED)" if metrics.is_well_calibrated() else " (NEEDS CALIBRATION)"),
            "=" * 50,
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    print("ForecastValidator imported successfully")

    # Create sample data for testing
    sample_forecasts = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "MSFT"],
            "horizon": ["1D", "1D", "1D"],
            "label": ["bullish", "bearish", "neutral"],
            "confidence": [0.75, 0.65, 0.55],
            "target": [150.0, 148.0, 300.0],
            "upper_band": [152.0, 150.0, 305.0],
            "lower_band": [148.0, 146.0, 295.0],
            "forecast_date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01"]),
            "current_price": [149.0, 149.5, 298.0],
        }
    )

    sample_actuals = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "MSFT"],
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-02"]),
            "close": [151.0, 147.0, 299.0],
            "high": [152.0, 150.0, 302.0],
            "low": [149.0, 146.0, 297.0],
        }
    )

    validator = ForecastValidator()
    metrics = validator.validate(sample_forecasts, sample_actuals)
    print(validator.generate_report(metrics))
