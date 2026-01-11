"""
Forecast Validator - Measure and improve forecast edge.

Tracks:
- Directional Accuracy: Did we predict the correct direction?
- Target Precision: How close was target to actual?
- Band Efficiency: Did bands contain actual price movement?
- Confidence Calibration: Does confidence = actual accuracy?

Edge = (Dir_Acc × 0.35) + (Target_Acc × 0.35) + (Band_Eff × 0.20) + (Conf_Cal × 0.10)
Target: Overall Edge > 55% (vs 50% coin flip)

Option B Framework (Primary Metric):
- FULL_HIT: Direction correct AND price within band ± tolerance
- DIRECTIONAL_HIT: Direction correct AND price within 2x tolerance
- DIRECTIONAL_ONLY: Direction correct but price beyond 2x tolerance
- MISS: Direction incorrect

Tolerance by horizon:
- 1-3 days: ±1% of mid-price
- 4-10 days: ±2% of mid-price
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np


class ForecastOutcome(Enum):
    """Four-tier outcome classification for Option B framework."""

    FULL_HIT = "FULL_HIT"  # Direction ✓ + Price within band ± tolerance
    DIRECTIONAL_HIT = "DIRECTIONAL_HIT"  # Direction ✓ + Price within 2x tolerance
    DIRECTIONAL_ONLY = "DIRECTIONAL_ONLY"  # Direction ✓ + Price beyond 2x tolerance
    MISS = "MISS"  # Direction ✗


@dataclass
class ForecastEvaluation:
    """Result of evaluating a single forecast against actual outcome."""

    outcome: ForecastOutcome
    direction_correct: bool
    within_band: bool
    within_tolerance: bool
    within_2x_tolerance: bool
    mape: float  # Mean Absolute Percentage Error
    bias: float  # forecast - actual (positive = over-forecast)
    coverage: int  # 1 if within band, 0 otherwise
    horizon_days: int
    tolerance_pct: float

    def to_dict(self) -> Dict:
        return {
            "outcome": self.outcome.value,
            "direction_correct": self.direction_correct,
            "within_band": self.within_band,
            "within_tolerance": self.within_tolerance,
            "within_2x_tolerance": self.within_2x_tolerance,
            "mape": round(self.mape, 4),
            "bias": round(self.bias, 4),
            "coverage": self.coverage,
            "horizon_days": self.horizon_days,
            "tolerance_pct": self.tolerance_pct,
        }


@dataclass
class ForecastAccuracySummary:
    """Aggregated accuracy metrics following Option B framework."""

    total_forecasts: int
    directional_accuracy: float  # % direction correct
    full_hit_rate: float  # % FULL_HIT
    directional_hit_rate: float  # % DIRECTIONAL_HIT
    directional_only_rate: float  # % DIRECTIONAL_ONLY
    miss_rate: float  # % MISS
    mape: float  # Mean MAPE across all forecasts
    bias: float  # Mean bias (systematic over/under)
    empirical_coverage: float  # % within predicted bands
    outcome_counts: Dict[str, int]
    by_horizon: Dict[int, Dict]  # Breakdown by horizon

    def to_dict(self) -> Dict:
        return {
            "total_forecasts": self.total_forecasts,
            "primary_metrics": {
                "directional_accuracy": f"{self.directional_accuracy:.1%}",
                "full_hit_rate": f"{self.full_hit_rate:.1%}",
            },
            "outcome_distribution": {
                "full_hit": f"{self.full_hit_rate:.1%}",
                "directional_hit": f"{self.directional_hit_rate:.1%}",
                "directional_only": f"{self.directional_only_rate:.1%}",
                "miss": f"{self.miss_rate:.1%}",
            },
            "diagnostic_metrics": {
                "mape": f"{self.mape:.2f}%",
                "bias": f"{self.bias:+.4f}",
                "empirical_coverage": f"{self.empirical_coverage:.1%}",
            },
            "outcome_counts": self.outcome_counts,
            "by_horizon": self.by_horizon,
        }

    def get_status(self) -> str:
        """Return health status based on metrics."""
        if self.directional_accuracy >= 0.54 and self.full_hit_rate >= 0.42:
            return "OPTIMAL"
        elif self.directional_accuracy >= 0.52 and self.full_hit_rate >= 0.35:
            return "ACCEPTABLE"
        elif self.directional_accuracy >= 0.50:
            return "MARGINAL"
        else:
            return "DEGRADED"


def get_tolerance_for_horizon(horizon_days: int) -> float:
    """
    Get tolerance percentage based on forecast horizon.

    Args:
        horizon_days: Number of days in forecast horizon

    Returns:
        Tolerance as decimal (0.01 = 1%, 0.02 = 2%)
    """
    if horizon_days <= 3:
        return 0.01  # ±1% for 1-3 day horizons
    else:
        return 0.02  # ±2% for 4-10 day horizons


def evaluate_single_forecast(
    forecast_low: float,
    forecast_mid: float,
    forecast_high: float,
    horizon_days: int,
    actual_close: float,
    prior_close: float,
) -> ForecastEvaluation:
    """
    Evaluate a single forecast against actual outcome using Option B framework.

    Args:
        forecast_low: Lower band estimate
        forecast_mid: Mid-point/target estimate
        forecast_high: Upper band estimate
        horizon_days: Forecast horizon (1-10 days)
        actual_close: Realized close price at horizon
        prior_close: Previous day's close (for direction calculation)

    Returns:
        ForecastEvaluation with outcome classification and metrics
    """
    # Step 1: Direction evaluation
    direction_forecast_up = forecast_mid > prior_close
    direction_actual_up = actual_close > prior_close
    direction_correct = direction_forecast_up == direction_actual_up

    # Step 2: Tolerance calculation
    tolerance = get_tolerance_for_horizon(horizon_days)

    # Band with tolerance
    band_low_with_tol = forecast_mid * (1 - tolerance)
    band_high_with_tol = forecast_mid * (1 + tolerance)

    # 2x tolerance for directional hit
    band_low_2x = forecast_mid * (1 - 2 * tolerance)
    band_high_2x = forecast_mid * (1 + 2 * tolerance)

    # Step 3: Band evaluation
    within_original_band = forecast_low <= actual_close <= forecast_high
    within_tolerance = band_low_with_tol <= actual_close <= band_high_with_tol
    within_2x_tolerance = band_low_2x <= actual_close <= band_high_2x

    # Step 4: Outcome classification
    if direction_correct and within_tolerance:
        outcome = ForecastOutcome.FULL_HIT
    elif direction_correct and within_2x_tolerance:
        outcome = ForecastOutcome.DIRECTIONAL_HIT
    elif direction_correct:
        outcome = ForecastOutcome.DIRECTIONAL_ONLY
    else:
        outcome = ForecastOutcome.MISS

    # Step 5: Calculate auxiliary metrics
    mape = abs(actual_close - forecast_mid) / actual_close * 100 if actual_close != 0 else 0
    bias = forecast_mid - actual_close
    coverage = 1 if within_original_band else 0

    return ForecastEvaluation(
        outcome=outcome,
        direction_correct=direction_correct,
        within_band=within_original_band,
        within_tolerance=within_tolerance,
        within_2x_tolerance=within_2x_tolerance,
        mape=mape,
        bias=bias,
        coverage=coverage,
        horizon_days=horizon_days,
        tolerance_pct=tolerance * 100,
    )


def summarize_forecast_accuracy(
    evaluations: List[ForecastEvaluation], filter_horizon: Optional[int] = None
) -> ForecastAccuracySummary:
    """
    Aggregate individual forecast evaluations into portfolio metrics.

    Args:
        evaluations: List of ForecastEvaluation objects
        filter_horizon: Optional horizon to filter by (None = all)

    Returns:
        ForecastAccuracySummary with aggregated metrics
    """
    if filter_horizon is not None:
        evaluations = [e for e in evaluations if e.horizon_days == filter_horizon]

    if not evaluations:
        return ForecastAccuracySummary(
            total_forecasts=0,
            directional_accuracy=0.0,
            full_hit_rate=0.0,
            directional_hit_rate=0.0,
            directional_only_rate=0.0,
            miss_rate=0.0,
            mape=0.0,
            bias=0.0,
            empirical_coverage=0.0,
            outcome_counts={},
            by_horizon={},
        )

    n = len(evaluations)

    # Count outcomes
    outcome_counts = {
        ForecastOutcome.FULL_HIT.value: 0,
        ForecastOutcome.DIRECTIONAL_HIT.value: 0,
        ForecastOutcome.DIRECTIONAL_ONLY.value: 0,
        ForecastOutcome.MISS.value: 0,
    }
    for e in evaluations:
        outcome_counts[e.outcome.value] += 1

    # Primary metrics
    directional_accuracy = sum(1 for e in evaluations if e.direction_correct) / n
    full_hit_rate = outcome_counts[ForecastOutcome.FULL_HIT.value] / n
    directional_hit_rate = outcome_counts[ForecastOutcome.DIRECTIONAL_HIT.value] / n
    directional_only_rate = outcome_counts[ForecastOutcome.DIRECTIONAL_ONLY.value] / n
    miss_rate = outcome_counts[ForecastOutcome.MISS.value] / n

    # Diagnostic metrics
    mape = np.mean([e.mape for e in evaluations])
    bias = np.mean([e.bias for e in evaluations])
    empirical_coverage = np.mean([e.coverage for e in evaluations])

    # Breakdown by horizon
    horizons = set(e.horizon_days for e in evaluations)
    by_horizon = {}
    for h in sorted(horizons):
        h_evals = [e for e in evaluations if e.horizon_days == h]
        h_n = len(h_evals)
        if h_n > 0:
            by_horizon[h] = {
                "count": h_n,
                "directional_accuracy": sum(1 for e in h_evals if e.direction_correct) / h_n,
                "full_hit_rate": sum(1 for e in h_evals if e.outcome == ForecastOutcome.FULL_HIT)
                / h_n,
                "mape": np.mean([e.mape for e in h_evals]),
                "tolerance": get_tolerance_for_horizon(h) * 100,
            }

    return ForecastAccuracySummary(
        total_forecasts=n,
        directional_accuracy=directional_accuracy,
        full_hit_rate=full_hit_rate,
        directional_hit_rate=directional_hit_rate,
        directional_only_rate=directional_only_rate,
        miss_rate=miss_rate,
        mape=mape,
        bias=bias,
        empirical_coverage=empirical_coverage,
        outcome_counts=outcome_counts,
        by_horizon=by_horizon,
    )


def evaluate_forecast_batch(forecasts: List[Dict]) -> ForecastAccuracySummary:
    """
    Convenience function to evaluate a batch of forecasts.

    Args:
        forecasts: List of dicts with:
            - forecast_low: float
            - forecast_mid: float (or forecast_target)
            - forecast_high: float
            - horizon_days: int (default 1)
            - actual_close: float
            - prior_close: float (or actual_open as fallback)

    Returns:
        ForecastAccuracySummary with aggregated metrics
    """
    evaluations = []

    for f in forecasts:
        forecast_low = f.get("forecast_low", f.get("lower_band", 0))
        forecast_mid = f.get("forecast_mid", f.get("forecast_target", 0))
        forecast_high = f.get("forecast_high", f.get("upper_band", 0))
        horizon_days = f.get("horizon_days", 1)
        actual_close = f.get("actual_close", 0)
        prior_close = f.get("prior_close", f.get("actual_open", 0))

        if forecast_mid == 0 or actual_close == 0 or prior_close == 0:
            continue

        eval_result = evaluate_single_forecast(
            forecast_low=forecast_low,
            forecast_mid=forecast_mid,
            forecast_high=forecast_high,
            horizon_days=horizon_days,
            actual_close=actual_close,
            prior_close=prior_close,
        )
        evaluations.append(eval_result)

    return summarize_forecast_accuracy(evaluations)


@dataclass
class DirectionalAccuracyResult:
    """Result of directional accuracy calculation."""

    overall_accuracy: float
    total_forecasts: int
    correct_directions: int
    accuracy_by_confidence: Dict[str, float]
    expected_edge: str

    def to_dict(self) -> Dict:
        return {
            "overall_accuracy": self.overall_accuracy,
            "total_forecasts": self.total_forecasts,
            "correct_directions": self.correct_directions,
            "accuracy_by_confidence": self.accuracy_by_confidence,
            "expected_edge": self.expected_edge,
            "weight_in_edge": "35%",
        }


@dataclass
class TargetPrecisionResult:
    """Result of target precision calculation."""

    mean_error_pct: float
    median_error_pct: float
    std_error_pct: float
    within_2pct: float
    quality_rating: str

    def to_dict(self) -> Dict:
        return {
            "mean_error_pct": self.mean_error_pct,
            "median_error_pct": self.median_error_pct,
            "std_error_pct": self.std_error_pct,
            "within_2pct": self.within_2pct,
            "quality_rating": self.quality_rating,
            "weight_in_edge": "35%",
        }


@dataclass
class BandEfficiencyResult:
    """Result of band efficiency calculation."""

    containment_rate: float
    avg_band_width_pct: float
    avg_actual_range_pct: float
    efficiency: float
    rating: str

    def to_dict(self) -> Dict:
        return {
            "containment_rate": self.containment_rate,
            "avg_band_width_pct": self.avg_band_width_pct,
            "avg_actual_range_pct": self.avg_actual_range_pct,
            "efficiency": self.efficiency,
            "rating": self.rating,
            "weight_in_edge": "20%",
        }


@dataclass
class ConfidenceCalibrationResult:
    """Result of confidence calibration calculation."""

    calibration_scores: Dict[str, Dict]
    mean_error: float
    quality: str

    def to_dict(self) -> Dict:
        return {
            "calibration_scores": self.calibration_scores,
            "mean_error": self.mean_error,
            "quality": self.quality,
            "weight_in_edge": "10%",
        }


@dataclass
class ValidationReport:
    """Complete validation report."""

    summary: Dict
    directional_accuracy: DirectionalAccuracyResult
    target_precision: TargetPrecisionResult
    band_efficiency: BandEfficiencyResult
    confidence_calibration: ConfidenceCalibrationResult
    recommendations: List[Dict]

    def to_dict(self) -> Dict:
        return {
            "summary": self.summary,
            "directional_accuracy": self.directional_accuracy.to_dict(),
            "target_precision": self.target_precision.to_dict(),
            "band_efficiency": self.band_efficiency.to_dict(),
            "confidence_calibration": self.confidence_calibration.to_dict(),
            "recommendations": self.recommendations,
        }


class DirectionalAccuracy:
    """Measure: did we predict the correct direction?"""

    def calculate(self, forecasts: List[Dict]) -> DirectionalAccuracyResult:
        """
        Calculate directional accuracy.

        Args:
            forecasts: List of dicts with:
                - forecast_direction: "BULLISH" or "BEARISH"
                - forecast_confidence: 0-1
                - actual_open: float
                - actual_close: float
        """
        if not forecasts:
            return DirectionalAccuracyResult(
                overall_accuracy=0.0,
                total_forecasts=0,
                correct_directions=0,
                accuracy_by_confidence={},
                expected_edge="+0.0%",
            )

        correct = 0
        total = 0
        confidence_buckets: Dict[float, Dict] = {}

        for forecast in forecasts:
            actual_close = forecast.get("actual_close", 0)
            actual_open = forecast.get("actual_open", 0)
            forecast_direction = forecast.get("forecast_direction", "").upper()
            forecast_confidence = forecast.get("forecast_confidence", 0.5)

            if actual_close == 0 or actual_open == 0:
                continue

            actual_direction = "BULLISH" if actual_close > actual_open else "BEARISH"
            is_correct = forecast_direction == actual_direction

            correct += int(is_correct)
            total += 1

            # Track by confidence bucket (round to 0.1)
            conf_bucket = round(forecast_confidence, 1)
            if conf_bucket not in confidence_buckets:
                confidence_buckets[conf_bucket] = {"correct": 0, "total": 0}

            confidence_buckets[conf_bucket]["correct"] += int(is_correct)
            confidence_buckets[conf_bucket]["total"] += 1

        overall_accuracy = correct / total if total > 0 else 0

        # Accuracy by confidence level
        accuracy_by_confidence = {
            f"{conf:.0%}": bucket["correct"] / bucket["total"]
            for conf, bucket in sorted(confidence_buckets.items())
            if bucket["total"] >= 3  # Minimum sample size
        }

        edge_pct = (overall_accuracy - 0.5) * 100

        return DirectionalAccuracyResult(
            overall_accuracy=round(overall_accuracy, 3),
            total_forecasts=total,
            correct_directions=correct,
            accuracy_by_confidence=accuracy_by_confidence,
            expected_edge=f"+{edge_pct:.1f}%" if edge_pct >= 0 else f"{edge_pct:.1f}%",
        )


class TargetPrecision:
    """Measure: how close was target to actual close?"""

    def calculate(self, forecasts: List[Dict]) -> TargetPrecisionResult:
        """
        Calculate target precision.

        Args:
            forecasts: List of dicts with:
                - forecast_target: predicted close level
                - actual_close: actual close price
        """
        if not forecasts:
            return TargetPrecisionResult(
                mean_error_pct=0.0,
                median_error_pct=0.0,
                std_error_pct=0.0,
                within_2pct=0.0,
                quality_rating="N/A",
            )

        error_pct = []

        for forecast in forecasts:
            target = forecast.get("forecast_target", 0)
            actual = forecast.get("actual_close", 0)

            if target == 0 or actual == 0:
                continue

            error = abs(target - actual)
            pct_error = (error / actual) * 100
            error_pct.append(pct_error)

        if not error_pct:
            return TargetPrecisionResult(
                mean_error_pct=0.0,
                median_error_pct=0.0,
                std_error_pct=0.0,
                within_2pct=0.0,
                quality_rating="N/A",
            )

        mean_error = np.mean(error_pct)
        median_error = np.median(error_pct)
        std_error = np.std(error_pct)

        within_2pct = sum(1 for e in error_pct if e <= 2.0) / len(error_pct)

        if mean_error < 1.5:
            quality = "Excellent"
        elif mean_error < 2.5:
            quality = "Good"
        elif mean_error < 4.0:
            quality = "Fair"
        else:
            quality = "Needs Improvement"

        return TargetPrecisionResult(
            mean_error_pct=round(mean_error, 2),
            median_error_pct=round(median_error, 2),
            std_error_pct=round(std_error, 2),
            within_2pct=round(within_2pct, 3),
            quality_rating=quality,
        )


class BandEfficiency:
    """Measure: did bands contain actual price movement?"""

    def calculate(self, forecasts: List[Dict]) -> BandEfficiencyResult:
        """
        Calculate band efficiency.

        Args:
            forecasts: List of dicts with:
                - upper_band: upper band level
                - lower_band: lower band level
                - actual_high: actual high price
                - actual_low: actual low price
                - actual_close: actual close price
        """
        if not forecasts:
            return BandEfficiencyResult(
                containment_rate=0.0,
                avg_band_width_pct=0.0,
                avg_actual_range_pct=0.0,
                efficiency=0.0,
                rating="N/A",
            )

        contained = 0
        total = 0
        band_widths = []
        price_ranges = []
        prices = []

        for forecast in forecasts:
            upper = forecast.get("upper_band", 0)
            lower = forecast.get("lower_band", 0)
            high = forecast.get("actual_high", 0)
            low = forecast.get("actual_low", 0)
            close = forecast.get("actual_close", 0)

            if upper == 0 or lower == 0 or high == 0 or low == 0:
                continue

            # Check if high and low both within bands
            is_contained = (high <= upper) and (low >= lower)
            contained += int(is_contained)
            total += 1

            band_widths.append(upper - lower)
            price_ranges.append(high - low)
            prices.append(close)

        if total == 0:
            return BandEfficiencyResult(
                containment_rate=0.0,
                avg_band_width_pct=0.0,
                avg_actual_range_pct=0.0,
                efficiency=0.0,
                rating="N/A",
            )

        containment_rate = contained / total
        avg_price = np.mean(prices) if prices else 1
        avg_band_width_pct = (np.mean(band_widths) / avg_price) * 100 if band_widths else 0
        avg_actual_range_pct = (np.mean(price_ranges) / avg_price) * 100 if price_ranges else 1

        # Efficiency = containment × (band tightness)
        # Narrow efficient bands = good, wide loose bands = bad
        band_ratio = avg_band_width_pct / (avg_actual_range_pct + 0.01)
        efficiency = containment_rate / (1 + max(0, band_ratio - 1))

        if containment_rate > 0.85:
            rating = "Excellent"
        elif containment_rate > 0.75:
            rating = "Good"
        elif containment_rate > 0.60:
            rating = "Fair"
        else:
            rating = "Needs Improvement"

        return BandEfficiencyResult(
            containment_rate=round(containment_rate, 3),
            avg_band_width_pct=round(avg_band_width_pct, 2),
            avg_actual_range_pct=round(avg_actual_range_pct, 2),
            efficiency=round(efficiency, 3),
            rating=rating,
        )


class ConfidenceCalibration:
    """Measure: does forecast confidence = actual accuracy?"""

    def calculate(self, forecasts: List[Dict]) -> ConfidenceCalibrationResult:
        """
        Calculate confidence calibration.

        If I say 70% confidence, I should be right 70% of the time.

        Args:
            forecasts: List of dicts with:
                - forecast_direction: "BULLISH" or "BEARISH"
                - forecast_confidence: 0-1
                - actual_open: float
                - actual_close: float
        """
        if not forecasts:
            return ConfidenceCalibrationResult(calibration_scores={}, mean_error=0.0, quality="N/A")

        buckets: Dict[float, Dict] = {}

        for forecast in forecasts:
            conf = forecast.get("forecast_confidence", 0.5)
            actual_close = forecast.get("actual_close", 0)
            actual_open = forecast.get("actual_open", 0)
            forecast_direction = forecast.get("forecast_direction", "").upper()

            if actual_close == 0 or actual_open == 0:
                continue

            actual_direction = "BULLISH" if actual_close > actual_open else "BEARISH"
            is_correct = forecast_direction == actual_direction

            # Round to nearest 0.05
            bucket_key = round(conf * 20) / 20
            if bucket_key not in buckets:
                buckets[bucket_key] = {"correct": 0, "total": 0}

            buckets[bucket_key]["correct"] += int(is_correct)
            buckets[bucket_key]["total"] += 1

        calibration_scores = {}
        calibration_errors = []

        for conf_level, data in sorted(buckets.items()):
            if data["total"] >= 3:  # Minimum samples
                actual_accuracy = data["correct"] / data["total"]
                expected_accuracy = conf_level
                error = abs(actual_accuracy - expected_accuracy)

                calibration_errors.append(error)
                calibration_scores[f"{conf_level:.0%}"] = {
                    "expected": round(expected_accuracy, 2),
                    "actual": round(actual_accuracy, 2),
                    "error": round(error, 2),
                    "samples": data["total"],
                }

        mean_error = np.mean(calibration_errors) if calibration_errors else 0

        if mean_error < 0.05:
            quality = "Perfect"
        elif mean_error < 0.10:
            quality = "Good"
        elif mean_error < 0.15:
            quality = "Fair"
        else:
            quality = "Needs Improvement"

        return ConfidenceCalibrationResult(
            calibration_scores=calibration_scores, mean_error=round(mean_error, 3), quality=quality
        )


class ForecastValidator:
    """All-in-one validation and edge calculation."""

    def __init__(self):
        self.dir_accuracy = DirectionalAccuracy()
        self.target_precision = TargetPrecision()
        self.band_efficiency = BandEfficiency()
        self.conf_calibration = ConfidenceCalibration()

    def generate_report(self, forecasts: List[Dict]) -> ValidationReport:
        """
        Generate comprehensive validation report.

        Args:
            forecasts: Full list with all fields from forecast + actual outcomes:
                - symbol: str
                - forecast_date: str
                - forecast_direction: "BULLISH" or "BEARISH"
                - forecast_confidence: 0-1
                - forecast_target: float
                - upper_band: float
                - lower_band: float
                - actual_open: float
                - actual_close: float
                - actual_high: float
                - actual_low: float

        Returns:
            ValidationReport with all metrics and recommendations
        """
        dir_acc = self.dir_accuracy.calculate(forecasts)
        target_prec = self.target_precision.calculate(forecasts)
        band_eff = self.band_efficiency.calculate(forecasts)
        conf_cal = self.conf_calibration.calculate(forecasts)

        # Calculate integrated edge score
        # Dir: aim for >55%, scale 0-1
        dir_score = dir_acc.overall_accuracy - 0.5  # 0 = 50%, 0.1 = 60%

        # Target: aim for <2.5%, invert
        target_score = max(0, 1 - target_prec.mean_error_pct / 5)  # 5% = 0, 0% = 1

        # Band: containment rate
        band_score = band_eff.containment_rate

        # Calibration: invert error
        cal_score = 1 - conf_cal.mean_error

        edge_score = dir_score * 0.35 + target_score * 0.35 + band_score * 0.20 + cal_score * 0.10

        # Normalize to 0.5 baseline
        edge_score = 0.5 + edge_score

        if edge_score > 0.55:
            rating = "Exceeds Target"
        elif edge_score > 0.52:
            rating = "On Target"
        elif edge_score > 0.50:
            rating = "Close"
        else:
            rating = "Needs Improvement"

        # Date range
        dates = [f.get("forecast_date", "") for f in forecasts if f.get("forecast_date")]
        date_range = f"{min(dates)} to {max(dates)}" if dates else "N/A"

        summary = {
            "total_forecasts": len(forecasts),
            "date_range": date_range,
            "edge_score": f"{edge_score*100:.1f}%",
            "target": ">55%",
            "rating": rating,
        }

        recommendations = self._generate_recommendations(dir_acc, target_prec, band_eff, conf_cal)

        return ValidationReport(
            summary=summary,
            directional_accuracy=dir_acc,
            target_precision=target_prec,
            band_efficiency=band_eff,
            confidence_calibration=conf_cal,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        dir_acc: DirectionalAccuracyResult,
        target_prec: TargetPrecisionResult,
        band_eff: BandEfficiencyResult,
        conf_cal: ConfidenceCalibrationResult,
    ) -> List[Dict]:
        """Generate improvement recommendations based on weak areas."""
        recommendations = []

        # Direction accuracy
        if dir_acc.overall_accuracy < 0.53:
            recommendations.append(
                {
                    "issue": f"Directional accuracy {dir_acc.overall_accuracy:.1%} below 53%",
                    "action": "Increase SuperTrend weight or retrain ensemble with more features",
                    "priority": "HIGH",
                }
            )
        elif dir_acc.overall_accuracy < 0.55:
            recommendations.append(
                {
                    "issue": f"Directional accuracy {dir_acc.overall_accuracy:.1%} slightly below target",
                    "action": "Review conflicting signal handling; consider adding momentum features",
                    "priority": "MEDIUM",
                }
            )

        # Target precision
        if target_prec.mean_error_pct > 3.5:
            recommendations.append(
                {
                    "issue": f"Target precision {target_prec.mean_error_pct:.1f}% off (goal: <2.5%)",
                    "action": "Increase polynomial forecast weight; refine ATR-based move calculation",
                    "priority": "HIGH",
                }
            )
        elif target_prec.mean_error_pct > 2.5:
            recommendations.append(
                {
                    "issue": f"Target precision {target_prec.mean_error_pct:.1f}% moderately off",
                    "action": "Consider time-of-day adjustments; refine S/R constraint weights",
                    "priority": "MEDIUM",
                }
            )

        # Band containment
        if band_eff.containment_rate < 0.70:
            recommendations.append(
                {
                    "issue": f"Bands contain only {band_eff.containment_rate:.0%} of moves (goal: >85%)",
                    "action": "Widen bands via volatility_expansion parameter; improve S/R detection",
                    "priority": "HIGH",
                }
            )
        elif band_eff.containment_rate < 0.80:
            recommendations.append(
                {
                    "issue": f"Bands contain {band_eff.containment_rate:.0%} of moves (goal: >85%)",
                    "action": "Slightly widen bands; review ATR multiplier",
                    "priority": "MEDIUM",
                }
            )

        # Confidence calibration
        if conf_cal.mean_error > 0.15:
            recommendations.append(
                {
                    "issue": f"Confidence calibration error {conf_cal.mean_error:.0%}",
                    "action": "Adjust confidence boost/penalty multipliers; recalibrate monthly",
                    "priority": "HIGH",
                }
            )
        elif conf_cal.mean_error > 0.10:
            recommendations.append(
                {
                    "issue": f"Confidence calibration slightly off ({conf_cal.mean_error:.0%})",
                    "action": "Fine-tune confidence calculation weights",
                    "priority": "MEDIUM",
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "issue": "No major issues detected",
                    "action": "Continue monitoring; recalibrate monthly",
                    "priority": "ROUTINE",
                }
            )

        return recommendations

    def calculate_edge(self, forecasts: List[Dict]) -> float:
        """
        Quick edge calculation without full report.

        Returns:
            Edge score as float (0.5 = no edge, >0.55 = good edge)
        """
        report = self.generate_report(forecasts)
        edge_str = report.summary["edge_score"]
        return float(edge_str.rstrip("%")) / 100


def validate_forecasts(forecasts: List[Dict]) -> ValidationReport:
    """Convenience function to validate a list of forecasts."""
    validator = ForecastValidator()
    return validator.generate_report(forecasts)


def calculate_edge(forecasts: List[Dict]) -> float:
    """Convenience function to calculate edge score."""
    validator = ForecastValidator()
    return validator.calculate_edge(forecasts)
