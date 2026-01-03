"""
Ranking Calibrator - Maps raw composite scores to calibrated probabilities.

Implements Perplexity's recommendation:
"Add a post-processing stage: map raw score → predicted return percentile
(or probability of positive return) using isotonic regression or quantile mapping.
Then rank by the calibrated output."

This brings forecast confidence calibration concepts into options ranking.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

logger = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    """Result of calibration fitting."""
    n_samples: int
    n_bins: int
    mean_raw_score: float
    mean_forward_return: float
    calibration_error: float  # Mean absolute calibration error
    is_monotonic: bool
    fit_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __str__(self) -> str:
        mono = "✅" if self.is_monotonic else "⚠️"
        return (
            f"Calibration: n={self.n_samples}, bins={self.n_bins}, "
            f"MAE={self.calibration_error:.4f}, {mono} monotonic"
        )


class IsotonicCalibrator:
    """
    Isotonic regression calibrator for ranking scores.
    
    Maps raw composite_rank (0-100) to:
    1. Predicted return percentile (0-100)
    2. Probability of positive return (0-1)
    
    Isotonic regression ensures monotonicity: higher scores → higher expected returns.
    """
    
    def __init__(
        self,
        n_bins: int = 20,
        min_samples_per_bin: int = 30,
        clip_extremes: bool = True,
    ):
        """
        Initialize calibrator.
        
        Args:
            n_bins: Number of bins for calibration curve
            min_samples_per_bin: Minimum samples required per bin
            clip_extremes: Clip extreme predictions to [0.05, 0.95]
        """
        self.n_bins = n_bins
        self.min_samples_per_bin = min_samples_per_bin
        self.clip_extremes = clip_extremes
        
        # Fitted calibration curves
        self._return_percentile_curve: Optional[interp1d] = None
        self._positive_prob_curve: Optional[interp1d] = None
        self._bin_centers: Optional[np.ndarray] = None
        self._bin_return_percentiles: Optional[np.ndarray] = None
        self._bin_positive_probs: Optional[np.ndarray] = None
        self._is_fitted = False
        self._fit_result: Optional[CalibrationResult] = None
    
    def fit(
        self,
        scores: np.ndarray,
        forward_returns: np.ndarray,
    ) -> CalibrationResult:
        """
        Fit isotonic calibration from historical scores and returns.
        
        Args:
            scores: Raw composite_rank values (0-100)
            forward_returns: Actual forward returns (e.g., 1-day, 3-day)
            
        Returns:
            CalibrationResult with fit statistics
        """
        scores = np.asarray(scores).flatten()
        forward_returns = np.asarray(forward_returns).flatten()
        
        # Remove NaN/Inf
        valid_mask = np.isfinite(scores) & np.isfinite(forward_returns)
        scores = scores[valid_mask]
        forward_returns = forward_returns[valid_mask]
        
        n_samples = len(scores)
        if n_samples < self.n_bins * self.min_samples_per_bin:
            logger.warning(
                f"Insufficient samples ({n_samples}) for {self.n_bins} bins. "
                f"Reducing bins."
            )
            self.n_bins = max(5, n_samples // self.min_samples_per_bin)
        
        # Create score bins
        bin_edges = np.percentile(scores, np.linspace(0, 100, self.n_bins + 1))
        bin_edges = np.unique(bin_edges)  # Remove duplicates
        actual_bins = len(bin_edges) - 1
        
        if actual_bins < 3:
            logger.error("Cannot fit calibration with fewer than 3 bins")
            self._is_fitted = False
            return CalibrationResult(
                n_samples=n_samples,
                n_bins=actual_bins,
                mean_raw_score=float(np.mean(scores)),
                mean_forward_return=float(np.mean(forward_returns)),
                calibration_error=1.0,
                is_monotonic=False,
            )
        
        # Assign each sample to a bin
        bin_indices = np.digitize(scores, bin_edges[1:-1])
        
        # Calculate bin statistics
        bin_centers = []
        bin_return_means = []
        bin_positive_probs = []
        
        for i in range(actual_bins):
            mask = bin_indices == i
            if mask.sum() >= self.min_samples_per_bin:
                bin_scores = scores[mask]
                bin_returns = forward_returns[mask]
                
                bin_centers.append(np.mean(bin_scores))
                bin_return_means.append(np.mean(bin_returns))
                bin_positive_probs.append(np.mean(bin_returns > 0))
        
        if len(bin_centers) < 3:
            logger.error("Insufficient valid bins after filtering")
            self._is_fitted = False
            return CalibrationResult(
                n_samples=n_samples,
                n_bins=len(bin_centers),
                mean_raw_score=float(np.mean(scores)),
                mean_forward_return=float(np.mean(forward_returns)),
                calibration_error=1.0,
                is_monotonic=False,
            )
        
        bin_centers = np.array(bin_centers)
        bin_return_means = np.array(bin_return_means)
        bin_positive_probs = np.array(bin_positive_probs)
        
        # Apply isotonic regression (Pool Adjacent Violators Algorithm)
        bin_return_means = self._isotonic_regression(bin_return_means)
        bin_positive_probs = self._isotonic_regression(bin_positive_probs)
        
        # Convert returns to percentiles
        bin_return_percentiles = self._returns_to_percentiles(
            bin_return_means, forward_returns
        )
        
        # Check monotonicity
        is_monotonic = (
            np.all(np.diff(bin_return_percentiles) >= 0) and
            np.all(np.diff(bin_positive_probs) >= 0)
        )
        
        # Build interpolation curves
        self._bin_centers = bin_centers
        self._bin_return_percentiles = bin_return_percentiles
        self._bin_positive_probs = bin_positive_probs
        
        # Extend to full 0-100 range
        extended_centers = np.concatenate([[0], bin_centers, [100]])
        extended_percentiles = np.concatenate([
            [bin_return_percentiles[0]],
            bin_return_percentiles,
            [bin_return_percentiles[-1]]
        ])
        extended_probs = np.concatenate([
            [bin_positive_probs[0]],
            bin_positive_probs,
            [bin_positive_probs[-1]]
        ])
        
        self._return_percentile_curve = interp1d(
            extended_centers, extended_percentiles,
            kind='linear', bounds_error=False,
            fill_value=(extended_percentiles[0], extended_percentiles[-1])
        )
        self._positive_prob_curve = interp1d(
            extended_centers, extended_probs,
            kind='linear', bounds_error=False,
            fill_value=(extended_probs[0], extended_probs[-1])
        )
        
        self._is_fitted = True
        
        # Calculate calibration error
        predicted_probs = self.predict_positive_prob(scores)
        actual_positive = (forward_returns > 0).astype(float)
        calibration_error = np.mean(np.abs(predicted_probs - actual_positive))
        
        self._fit_result = CalibrationResult(
            n_samples=n_samples,
            n_bins=len(bin_centers),
            mean_raw_score=float(np.mean(scores)),
            mean_forward_return=float(np.mean(forward_returns)),
            calibration_error=float(calibration_error),
            is_monotonic=is_monotonic,
        )
        
        logger.info(f"Calibration fitted: {self._fit_result}")
        
        return self._fit_result
    
    def _isotonic_regression(self, y: np.ndarray) -> np.ndarray:
        """
        Apply Pool Adjacent Violators Algorithm for isotonic regression.
        
        Ensures monotonically increasing output.
        """
        n = len(y)
        result = y.copy()
        
        # Forward pass: merge violating pairs
        i = 0
        while i < n - 1:
            if result[i] > result[i + 1]:
                # Merge blocks
                j = i + 1
                while j < n and result[i] > result[j]:
                    j += 1
                # Average the block
                block_mean = np.mean(result[i:j])
                result[i:j] = block_mean
                # Go back to check previous blocks
                i = max(0, i - 1)
            else:
                i += 1
        
        return result
    
    def _returns_to_percentiles(
        self,
        bin_returns: np.ndarray,
        all_returns: np.ndarray,
    ) -> np.ndarray:
        """Convert mean returns to percentiles within the return distribution."""
        percentiles = np.zeros_like(bin_returns)
        for i, ret in enumerate(bin_returns):
            percentiles[i] = np.mean(all_returns <= ret) * 100
        return percentiles
    
    def predict_return_percentile(self, scores: np.ndarray) -> np.ndarray:
        """
        Predict return percentile for given scores.
        
        Args:
            scores: Raw composite_rank values (0-100)
            
        Returns:
            Predicted return percentiles (0-100)
        """
        if not self._is_fitted:
            logger.warning("Calibrator not fitted, returning raw scores")
            return np.asarray(scores)
        
        scores = np.asarray(scores).flatten()
        percentiles = self._return_percentile_curve(scores)
        
        if self.clip_extremes:
            percentiles = np.clip(percentiles, 5, 95)
        
        return percentiles
    
    def predict_positive_prob(self, scores: np.ndarray) -> np.ndarray:
        """
        Predict probability of positive return for given scores.
        
        Args:
            scores: Raw composite_rank values (0-100)
            
        Returns:
            Predicted probabilities (0-1)
        """
        if not self._is_fitted:
            logger.warning("Calibrator not fitted, returning 0.5")
            return np.full_like(scores, 0.5, dtype=float)
        
        scores = np.asarray(scores).flatten()
        probs = self._positive_prob_curve(scores)
        
        if self.clip_extremes:
            probs = np.clip(probs, 0.05, 0.95)
        
        return probs
    
    def calibrate_rankings(
        self,
        df: pd.DataFrame,
        score_col: str = "composite_rank",
    ) -> pd.DataFrame:
        """
        Add calibrated scores to a rankings DataFrame.
        
        Args:
            df: DataFrame with raw scores
            score_col: Column name for raw scores
            
        Returns:
            DataFrame with added calibrated columns:
            - calibrated_return_pct: Predicted return percentile
            - calibrated_positive_prob: Probability of positive return
            - calibrated_rank: Final rank based on calibrated scores
        """
        if not self._is_fitted:
            logger.warning("Calibrator not fitted, skipping calibration")
            df["calibrated_return_pct"] = df[score_col]
            df["calibrated_positive_prob"] = 0.5
            df["calibrated_rank"] = df[score_col]
            return df
        
        df = df.copy()
        scores = df[score_col].values
        
        df["calibrated_return_pct"] = self.predict_return_percentile(scores)
        df["calibrated_positive_prob"] = self.predict_positive_prob(scores)
        
        # Calibrated rank combines both signals
        # Weight: 60% return percentile, 40% positive probability
        df["calibrated_rank"] = (
            df["calibrated_return_pct"] * 0.6 +
            df["calibrated_positive_prob"] * 100 * 0.4
        )
        
        return df
    
    def get_calibration_curve(self) -> Dict[str, Any]:
        """Get the fitted calibration curve data for visualization."""
        if not self._is_fitted:
            return {}
        
        return {
            "bin_centers": self._bin_centers.tolist(),
            "return_percentiles": self._bin_return_percentiles.tolist(),
            "positive_probs": self._bin_positive_probs.tolist(),
            "fit_result": {
                "n_samples": self._fit_result.n_samples,
                "n_bins": self._fit_result.n_bins,
                "calibration_error": self._fit_result.calibration_error,
                "is_monotonic": self._fit_result.is_monotonic,
            }
        }
    
    def save(self, path: str) -> None:
        """Save calibrator state to file."""
        import json
        
        state = {
            "n_bins": self.n_bins,
            "min_samples_per_bin": self.min_samples_per_bin,
            "clip_extremes": self.clip_extremes,
            "is_fitted": self._is_fitted,
        }
        
        if self._is_fitted:
            state["bin_centers"] = self._bin_centers.tolist()
            state["bin_return_percentiles"] = self._bin_return_percentiles.tolist()
            state["bin_positive_probs"] = self._bin_positive_probs.tolist()
            state["fit_result"] = {
                "n_samples": self._fit_result.n_samples,
                "n_bins": self._fit_result.n_bins,
                "mean_raw_score": self._fit_result.mean_raw_score,
                "mean_forward_return": self._fit_result.mean_forward_return,
                "calibration_error": self._fit_result.calibration_error,
                "is_monotonic": self._fit_result.is_monotonic,
                "fit_timestamp": self._fit_result.fit_timestamp.isoformat(),
            }
        
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Calibrator saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> "IsotonicCalibrator":
        """Load calibrator state from file."""
        import json
        
        with open(path, 'r') as f:
            state = json.load(f)
        
        calibrator = cls(
            n_bins=state["n_bins"],
            min_samples_per_bin=state["min_samples_per_bin"],
            clip_extremes=state["clip_extremes"],
        )
        
        if state.get("is_fitted"):
            calibrator._bin_centers = np.array(state["bin_centers"])
            calibrator._bin_return_percentiles = np.array(state["bin_return_percentiles"])
            calibrator._bin_positive_probs = np.array(state["bin_positive_probs"])
            
            # Rebuild interpolation curves
            extended_centers = np.concatenate([
                [0], calibrator._bin_centers, [100]
            ])
            extended_percentiles = np.concatenate([
                [calibrator._bin_return_percentiles[0]],
                calibrator._bin_return_percentiles,
                [calibrator._bin_return_percentiles[-1]]
            ])
            extended_probs = np.concatenate([
                [calibrator._bin_positive_probs[0]],
                calibrator._bin_positive_probs,
                [calibrator._bin_positive_probs[-1]]
            ])
            
            calibrator._return_percentile_curve = interp1d(
                extended_centers, extended_percentiles,
                kind='linear', bounds_error=False,
                fill_value=(extended_percentiles[0], extended_percentiles[-1])
            )
            calibrator._positive_prob_curve = interp1d(
                extended_centers, extended_probs,
                kind='linear', bounds_error=False,
                fill_value=(extended_probs[0], extended_probs[-1])
            )
            
            fit_result = state["fit_result"]
            calibrator._fit_result = CalibrationResult(
                n_samples=fit_result["n_samples"],
                n_bins=fit_result["n_bins"],
                mean_raw_score=fit_result["mean_raw_score"],
                mean_forward_return=fit_result["mean_forward_return"],
                calibration_error=fit_result["calibration_error"],
                is_monotonic=fit_result["is_monotonic"],
                fit_timestamp=datetime.fromisoformat(fit_result["fit_timestamp"]),
            )
            calibrator._is_fitted = True
        
        logger.info(f"Calibrator loaded from {path}")
        return calibrator


class QuantileCalibrator:
    """
    Alternative calibrator using quantile mapping.
    
    Maps raw scores to empirical quantiles of forward returns.
    Simpler than isotonic regression but less smooth.
    """
    
    def __init__(self, n_quantiles: int = 100):
        """
        Initialize quantile calibrator.
        
        Args:
            n_quantiles: Number of quantiles for mapping
        """
        self.n_quantiles = n_quantiles
        self._score_quantiles: Optional[np.ndarray] = None
        self._return_quantiles: Optional[np.ndarray] = None
        self._is_fitted = False
    
    def fit(
        self,
        scores: np.ndarray,
        forward_returns: np.ndarray,
    ) -> None:
        """Fit quantile mapping from scores to returns."""
        scores = np.asarray(scores).flatten()
        forward_returns = np.asarray(forward_returns).flatten()
        
        valid_mask = np.isfinite(scores) & np.isfinite(forward_returns)
        scores = scores[valid_mask]
        forward_returns = forward_returns[valid_mask]
        
        # Compute quantiles
        quantile_points = np.linspace(0, 100, self.n_quantiles + 1)
        self._score_quantiles = np.percentile(scores, quantile_points)
        self._return_quantiles = np.percentile(forward_returns, quantile_points)
        
        self._is_fitted = True
        logger.info(f"Quantile calibrator fitted with {len(scores)} samples")
    
    def predict_return_quantile(self, scores: np.ndarray) -> np.ndarray:
        """Map scores to return quantiles."""
        if not self._is_fitted:
            return np.asarray(scores)
        
        scores = np.asarray(scores).flatten()
        
        # Find which quantile each score falls into
        quantile_indices = np.searchsorted(self._score_quantiles, scores)
        quantile_indices = np.clip(quantile_indices, 0, self.n_quantiles)
        
        # Return the corresponding return quantile
        return quantile_indices / self.n_quantiles * 100
