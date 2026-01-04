"""Intraday weight calibration engine.

Learns optimal layer weights from rapid intraday feedback loops,
then applies those weights to daily/weekly/monthly forecasts.
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402


logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    """Result of weight calibration for a symbol."""

    symbol: str
    symbol_id: str
    supertrend_weight: float
    sr_weight: float
    ensemble_weight: float
    validation_mae: float
    direction_accuracy: float
    sample_count: int
    horizon: str


class IntradayWeightCalibrator:
    """
    Learns optimal layer weights from intraday forecast evaluations.

    Uses walk-forward validation to avoid overfitting and
    grid search to find optimal weight combinations.
    """

    # Weight grid for optimization
    WEIGHT_GRID = {
        "supertrend": [0.15, 0.20, 0.25, 0.30, 0.35, 0.40],
        "sr": [0.15, 0.20, 0.25, 0.30, 0.35],
        "ensemble": [0.25, 0.30, 0.35, 0.40, 0.45, 0.50],
    }

    def __init__(
        self,
        min_samples: int | None = None,
        lookback_hours: int | None = None,
    ):
        """
        Initialize calibrator.

        Args:
            min_samples: Minimum evaluation samples required for calibration
            lookback_hours: Hours of historical data to use
        """
        self.min_samples = min_samples or settings.intraday_calibration_min_samples
        self.lookback_hours = lookback_hours or settings.intraday_lookback_hours

    def _fetch_evaluation_data(
        self,
        symbol_id: str,
        horizon: str | None = None,
    ) -> pd.DataFrame:
        """
        Fetch evaluation data for calibration.

        Args:
            symbol_id: Symbol UUID
            horizon: Optional filter for '15m' or '1h'

        Returns:
            DataFrame with evaluation records
        """
        evals = db.get_intraday_evaluations_for_calibration(
            symbol_id=symbol_id,
            lookback_hours=self.lookback_hours,
        )

        if not evals:
            return pd.DataFrame()

        df = pd.DataFrame(evals)

        # Filter by horizon if specified
        if horizon and "horizon" in df.columns:
            df = df[df["horizon"] == horizon]

        return df

    def _compute_weighted_prediction(
        self,
        row: pd.Series,
        w_st: float,
        w_sr: float,
        w_ens: float,
    ) -> float:
        """
        Compute weighted price prediction from components.

        Args:
            row: DataFrame row with component values
            w_st: SuperTrend weight
            w_sr: S/R weight
            w_ens: Ensemble weight

        Returns:
            Weighted prediction
        """
        # Normalize weights to sum to 1
        total = w_st + w_sr + w_ens
        w_st_norm = w_st / total
        w_sr_norm = w_sr / total
        w_ens_norm = w_ens / total

        st_comp = float(row.get("supertrend_component", 0) or 0)
        sr_comp = float(row.get("sr_component", 0) or 0)
        ens_comp = float(row.get("ensemble_component", 0) or 0)

        return w_st_norm * st_comp + w_sr_norm * sr_comp + w_ens_norm * ens_comp

    def _evaluate_weights(
        self,
        df: pd.DataFrame,
        w_st: float,
        w_sr: float,
        w_ens: float,
    ) -> tuple[float, float]:
        """
        Evaluate weight combination on data.

        Args:
            df: Evaluation data
            w_st, w_sr, w_ens: Layer weights

        Returns:
            Tuple of (MAE, direction_accuracy)
        """
        if len(df) == 0:
            return float("inf"), 0.0

        errors = []
        direction_correct = 0

        for _, row in df.iterrows():
            # Get actual realized price
            realized = float(row.get("realized_price", 0) or 0)
            if realized == 0:
                continue

            # Compute weighted prediction
            pred = self._compute_weighted_prediction(row, w_st, w_sr, w_ens)
            if pred == 0:
                continue

            # Calculate error
            error = abs(pred - realized) / realized
            errors.append(error)

            # Check direction (relative to some baseline)
            # Use original predicted price as reference
            orig_pred = float(row.get("predicted_price", 0) or 0)
            if orig_pred > 0:
                pred_direction = "up" if pred > orig_pred * 0.998 else "down"
                actual_direction = "up" if realized > orig_pred * 0.998 else "down"
                if pred_direction == actual_direction:
                    direction_correct += 1

        if not errors:
            return float("inf"), 0.0

        mae = np.mean(errors)
        direction_acc = direction_correct / len(errors) if errors else 0.0

        return mae, direction_acc

    def _walk_forward_validate(
        self,
        df: pd.DataFrame,
        w_st: float,
        w_sr: float,
        w_ens: float,
        n_splits: int = 3,
    ) -> tuple[float, float]:
        """
        Walk-forward cross-validation for weight evaluation.

        Args:
            df: Evaluation data (sorted by time)
            w_st, w_sr, w_ens: Layer weights
            n_splits: Number of validation folds

        Returns:
            Tuple of (avg_MAE, avg_direction_accuracy)
        """
        if len(df) < n_splits * 2:
            # Not enough data for CV, use full dataset
            return self._evaluate_weights(df, w_st, w_sr, w_ens)

        # Sort by evaluation time
        df = df.sort_values("evaluated_at").reset_index(drop=True)

        # Walk-forward splits
        fold_size = len(df) // (n_splits + 1)
        maes = []
        accs = []

        for i in range(n_splits):
            train_end = fold_size * (i + 1)
            val_start = train_end
            val_end = min(val_start + fold_size, len(df))

            # We don't actually "train" on training data for grid search,
            # but this simulates walk-forward by only evaluating on future data
            val_df = df.iloc[val_start:val_end]

            if len(val_df) < 5:
                continue

            mae, acc = self._evaluate_weights(val_df, w_st, w_sr, w_ens)
            if mae != float("inf"):
                maes.append(mae)
                accs.append(acc)

        if not maes:
            return float("inf"), 0.0

        return np.mean(maes), np.mean(accs)

    def _grid_search_weights(
        self,
        df: pd.DataFrame,
    ) -> tuple[float, float, float, float, float]:
        """
        Grid search for optimal weight combination.

        Args:
            df: Evaluation data

        Returns:
            Tuple of (best_st, best_sr, best_ens, best_mae, best_acc)
        """
        best_mae = float("inf")
        best_acc = 0.0
        best_weights = (0.33, 0.33, 0.34)

        for w_st in self.WEIGHT_GRID["supertrend"]:
            for w_sr in self.WEIGHT_GRID["sr"]:
                for w_ens in self.WEIGHT_GRID["ensemble"]:
                    mae, acc = self._walk_forward_validate(df, w_st, w_sr, w_ens)

                    # Optimize for lowest MAE with tie-breaking by accuracy
                    if mae < best_mae or (mae == best_mae and acc > best_acc):
                        best_mae = mae
                        best_acc = acc
                        best_weights = (w_st, w_sr, w_ens)

        return (*best_weights, best_mae, best_acc)

    def _scipy_optimize_weights(
        self,
        df: pd.DataFrame,
        initial_guess: tuple[float, float, float] = (0.33, 0.33, 0.34),
    ) -> tuple[float, float, float, float, float]:
        """
        Use scipy optimization for fine-tuning weights.

        Args:
            df: Evaluation data
            initial_guess: Starting weights

        Returns:
            Tuple of (best_st, best_sr, best_ens, best_mae, best_acc)
        """

        def objective(weights):
            w_st, w_sr, w_ens = weights
            mae, _ = self._walk_forward_validate(df, w_st, w_sr, w_ens)
            return mae

        # Constraints: weights must be positive and sum doesn't matter (normalized)
        bounds = [(0.1, 0.6), (0.1, 0.5), (0.2, 0.6)]

        result = minimize(
            objective,
            initial_guess,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 100},
        )

        if result.success:
            w_st, w_sr, w_ens = result.x
            mae, acc = self._walk_forward_validate(df, w_st, w_sr, w_ens)
            return w_st, w_sr, w_ens, mae, acc

        # Fall back to grid search result
        return (*initial_guess, float("inf"), 0.0)

    def calibrate_symbol(
        self,
        symbol: str,
        horizon: str | None = None,
        use_scipy: bool = True,
    ) -> CalibrationResult | None:
        """
        Calibrate weights for a single symbol.

        Args:
            symbol: Stock ticker
            horizon: Optional filter ('15m' or '1h')
            use_scipy: Use scipy optimization after grid search

        Returns:
            CalibrationResult or None if insufficient data
        """
        logger.info("Calibrating weights for %s (horizon=%s)", symbol, horizon or "all")

        # Get symbol ID
        symbol_id = db.get_symbol_id(symbol)
        if not symbol_id:
            logger.warning("Symbol not found: %s", symbol)
            return None

        # Fetch evaluation data
        df = self._fetch_evaluation_data(symbol_id, horizon)

        if len(df) < self.min_samples:
            logger.warning(
                "Insufficient samples for %s: %d (need %d)",
                symbol,
                len(df),
                self.min_samples,
            )
            return None

        logger.info("Found %d evaluation samples for %s", len(df), symbol)

        # Grid search for initial weights
        w_st, w_sr, w_ens, mae, acc = self._grid_search_weights(df)
        logger.info(
            "Grid search result: ST=%.2f SR=%.2f ENS=%.2f MAE=%.4f Acc=%.2f%%",
            w_st,
            w_sr,
            w_ens,
            mae,
            acc * 100,
        )

        # Optionally refine with scipy
        if use_scipy and mae != float("inf"):
            w_st_opt, w_sr_opt, w_ens_opt, mae_opt, acc_opt = self._scipy_optimize_weights(
                df, (w_st, w_sr, w_ens)
            )

            if mae_opt < mae:
                w_st, w_sr, w_ens, mae, acc = w_st_opt, w_sr_opt, w_ens_opt, mae_opt, acc_opt
                logger.info(
                    "Scipy refined: ST=%.2f SR=%.2f ENS=%.2f MAE=%.4f Acc=%.2f%%",
                    w_st,
                    w_sr,
                    w_ens,
                    mae,
                    acc * 100,
                )

        return CalibrationResult(
            symbol=symbol,
            symbol_id=symbol_id,
            supertrend_weight=w_st,
            sr_weight=w_sr,
            ensemble_weight=w_ens,
            validation_mae=mae,
            direction_accuracy=acc,
            sample_count=len(df),
            horizon=horizon or "all",
        )

    def calibrate_and_save(
        self,
        symbol: str,
        horizon: str | None = None,
    ) -> bool:
        """
        Calibrate weights and save to database.

        Saves calibrated weights for all configured forecast horizons so they
        can be used by the daily forecast job.

        Args:
            symbol: Stock ticker
            horizon: Optional filter for calibration data

        Returns:
            True if calibration succeeded
        """
        result = self.calibrate_symbol(symbol, horizon)

        if result is None:
            return False

        # Normalize weights to sum to 1
        total = result.supertrend_weight + result.sr_weight + result.ensemble_weight
        st_norm = result.supertrend_weight / total
        sr_norm = result.sr_weight / total
        ens_norm = result.ensemble_weight / total

        # Save calibrated weights for all forecast horizons
        # Intraday weights are applied to 1D, 1W, 1M, etc.
        forecast_horizons = settings.forecast_horizons
        success_count = 0

        for target_horizon in forecast_horizons:
            success = db.update_symbol_weights_from_intraday(
                symbol_id=result.symbol_id,
                horizon=target_horizon,
                supertrend_weight=st_norm,
                sr_weight=sr_norm,
                ensemble_weight=ens_norm,
                sample_count=result.sample_count,
                accuracy=result.direction_accuracy,
            )
            if success:
                success_count += 1

        if success_count > 0:
            logger.info(
                "Saved calibrated weights for %s to %d horizons: "
                "ST=%.2f%% SR=%.2f%% ENS=%.2f%% (n=%d, acc=%.1f%%)",
                symbol,
                success_count,
                st_norm * 100,
                sr_norm * 100,
                ens_norm * 100,
                result.sample_count,
                result.direction_accuracy * 100,
            )

        return success_count > 0


def run_calibration_job(symbols: list[str] | None = None) -> tuple[int, int]:
    """
    Run calibration for all configured symbols.

    Args:
        symbols: Optional list of symbols (default: from settings)

    Returns:
        Tuple of (success_count, fail_count)
    """
    if symbols is None:
        symbols = settings.intraday_symbols

    calibrator = IntradayWeightCalibrator()
    success_count = 0
    fail_count = 0

    for symbol in symbols:
        try:
            if calibrator.calibrate_and_save(symbol):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logger.error("Error calibrating %s: %s", symbol, e, exc_info=True)
            fail_count += 1

    return success_count, fail_count


def main() -> None:
    """Main entry point for weight calibration job."""
    parser = argparse.ArgumentParser(description="Calibrate layer weights from intraday data")
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Single symbol to calibrate (default: all intraday symbols)",
    )
    parser.add_argument(
        "--horizon",
        type=str,
        choices=["15m", "1h"],
        default=None,
        help="Filter by horizon (default: use all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate weights but don't save to database",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Intraday Weight Calibration Job")
    logger.info("=" * 60)

    if args.symbol:
        symbols = [args.symbol.upper()]
    else:
        symbols = settings.intraday_symbols

    calibrator = IntradayWeightCalibrator()

    for symbol in symbols:
        result = calibrator.calibrate_symbol(symbol, args.horizon)

        if result is None:
            logger.info("%s: Insufficient data for calibration", symbol)
            continue

        logger.info(
            "%s: ST=%.2f SR=%.2f ENS=%.2f (MAE=%.4f, Acc=%.1f%%, n=%d)",
            symbol,
            result.supertrend_weight,
            result.sr_weight,
            result.ensemble_weight,
            result.validation_mae,
            result.direction_accuracy * 100,
            result.sample_count,
        )

        if not args.dry_run:
            calibrator.calibrate_and_save(symbol, args.horizon)

    logger.info("=" * 60)
    logger.info("Calibration Job Complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
