"""
Forecast Validator - Measure and improve forecast edge.

Tracks:
- Directional Accuracy: Did we predict the correct direction?
- Target Precision: How close was target to actual?
- Band Efficiency: Did bands contain actual price movement?
- Confidence Calibration: Does confidence = actual accuracy?

Edge = (Dir_Acc × 0.35) + (Target_Acc × 0.35) + (Band_Eff × 0.20) + (Conf_Cal × 0.10)
Target: Overall Edge > 55% (vs 50% coin flip)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime


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
            "weight_in_edge": "35%"
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
            "weight_in_edge": "35%"
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
            "weight_in_edge": "20%"
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
            "weight_in_edge": "10%"
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
            "recommendations": self.recommendations
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
                expected_edge="+0.0%"
            )

        correct = 0
        total = 0
        confidence_buckets: Dict[float, Dict] = {}

        for forecast in forecasts:
            actual_close = forecast.get('actual_close', 0)
            actual_open = forecast.get('actual_open', 0)
            forecast_direction = forecast.get('forecast_direction', '').upper()
            forecast_confidence = forecast.get('forecast_confidence', 0.5)

            if actual_close == 0 or actual_open == 0:
                continue

            actual_direction = "BULLISH" if actual_close > actual_open else "BEARISH"
            is_correct = forecast_direction == actual_direction

            correct += int(is_correct)
            total += 1

            # Track by confidence bucket (round to 0.1)
            conf_bucket = round(forecast_confidence, 1)
            if conf_bucket not in confidence_buckets:
                confidence_buckets[conf_bucket] = {'correct': 0, 'total': 0}

            confidence_buckets[conf_bucket]['correct'] += int(is_correct)
            confidence_buckets[conf_bucket]['total'] += 1

        overall_accuracy = correct / total if total > 0 else 0

        # Accuracy by confidence level
        accuracy_by_confidence = {
            f"{conf:.0%}": bucket['correct'] / bucket['total']
            for conf, bucket in sorted(confidence_buckets.items())
            if bucket['total'] >= 3  # Minimum sample size
        }

        edge_pct = (overall_accuracy - 0.5) * 100

        return DirectionalAccuracyResult(
            overall_accuracy=round(overall_accuracy, 3),
            total_forecasts=total,
            correct_directions=correct,
            accuracy_by_confidence=accuracy_by_confidence,
            expected_edge=f"+{edge_pct:.1f}%" if edge_pct >= 0 else f"{edge_pct:.1f}%"
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
                quality_rating="N/A"
            )

        error_pct = []

        for forecast in forecasts:
            target = forecast.get('forecast_target', 0)
            actual = forecast.get('actual_close', 0)

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
                quality_rating="N/A"
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
            quality_rating=quality
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
                rating="N/A"
            )

        contained = 0
        total = 0
        band_widths = []
        price_ranges = []
        prices = []

        for forecast in forecasts:
            upper = forecast.get('upper_band', 0)
            lower = forecast.get('lower_band', 0)
            high = forecast.get('actual_high', 0)
            low = forecast.get('actual_low', 0)
            close = forecast.get('actual_close', 0)

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
                rating="N/A"
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
            rating=rating
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
            return ConfidenceCalibrationResult(
                calibration_scores={},
                mean_error=0.0,
                quality="N/A"
            )

        buckets: Dict[float, Dict] = {}

        for forecast in forecasts:
            conf = forecast.get('forecast_confidence', 0.5)
            actual_close = forecast.get('actual_close', 0)
            actual_open = forecast.get('actual_open', 0)
            forecast_direction = forecast.get('forecast_direction', '').upper()

            if actual_close == 0 or actual_open == 0:
                continue

            actual_direction = "BULLISH" if actual_close > actual_open else "BEARISH"
            is_correct = forecast_direction == actual_direction

            # Round to nearest 0.05
            bucket_key = round(conf * 20) / 20
            if bucket_key not in buckets:
                buckets[bucket_key] = {'correct': 0, 'total': 0}

            buckets[bucket_key]['correct'] += int(is_correct)
            buckets[bucket_key]['total'] += 1

        calibration_scores = {}
        calibration_errors = []

        for conf_level, data in sorted(buckets.items()):
            if data['total'] >= 3:  # Minimum samples
                actual_accuracy = data['correct'] / data['total']
                expected_accuracy = conf_level
                error = abs(actual_accuracy - expected_accuracy)

                calibration_errors.append(error)
                calibration_scores[f"{conf_level:.0%}"] = {
                    "expected": round(expected_accuracy, 2),
                    "actual": round(actual_accuracy, 2),
                    "error": round(error, 2),
                    "samples": data['total']
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
            calibration_scores=calibration_scores,
            mean_error=round(mean_error, 3),
            quality=quality
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

        edge_score = (
            dir_score * 0.35 +
            target_score * 0.35 +
            band_score * 0.20 +
            cal_score * 0.10
        )

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
        dates = [f.get('forecast_date', '') for f in forecasts if f.get('forecast_date')]
        date_range = f"{min(dates)} to {max(dates)}" if dates else "N/A"

        summary = {
            "total_forecasts": len(forecasts),
            "date_range": date_range,
            "edge_score": f"{edge_score*100:.1f}%",
            "target": ">55%",
            "rating": rating
        }

        recommendations = self._generate_recommendations(dir_acc, target_prec, band_eff, conf_cal)

        return ValidationReport(
            summary=summary,
            directional_accuracy=dir_acc,
            target_precision=target_prec,
            band_efficiency=band_eff,
            confidence_calibration=conf_cal,
            recommendations=recommendations
        )

    def _generate_recommendations(
        self,
        dir_acc: DirectionalAccuracyResult,
        target_prec: TargetPrecisionResult,
        band_eff: BandEfficiencyResult,
        conf_cal: ConfidenceCalibrationResult
    ) -> List[Dict]:
        """Generate improvement recommendations based on weak areas."""
        recommendations = []

        # Direction accuracy
        if dir_acc.overall_accuracy < 0.53:
            recommendations.append({
                "issue": f"Directional accuracy {dir_acc.overall_accuracy:.1%} below 53%",
                "action": "Increase SuperTrend weight or retrain ensemble with more features",
                "priority": "HIGH"
            })
        elif dir_acc.overall_accuracy < 0.55:
            recommendations.append({
                "issue": f"Directional accuracy {dir_acc.overall_accuracy:.1%} slightly below target",
                "action": "Review conflicting signal handling; consider adding momentum features",
                "priority": "MEDIUM"
            })

        # Target precision
        if target_prec.mean_error_pct > 3.5:
            recommendations.append({
                "issue": f"Target precision {target_prec.mean_error_pct:.1f}% off (goal: <2.5%)",
                "action": "Increase polynomial forecast weight; refine ATR-based move calculation",
                "priority": "HIGH"
            })
        elif target_prec.mean_error_pct > 2.5:
            recommendations.append({
                "issue": f"Target precision {target_prec.mean_error_pct:.1f}% moderately off",
                "action": "Consider time-of-day adjustments; refine S/R constraint weights",
                "priority": "MEDIUM"
            })

        # Band containment
        if band_eff.containment_rate < 0.70:
            recommendations.append({
                "issue": f"Bands contain only {band_eff.containment_rate:.0%} of moves (goal: >85%)",
                "action": "Widen bands via volatility_expansion parameter; improve S/R detection",
                "priority": "HIGH"
            })
        elif band_eff.containment_rate < 0.80:
            recommendations.append({
                "issue": f"Bands contain {band_eff.containment_rate:.0%} of moves (goal: >85%)",
                "action": "Slightly widen bands; review ATR multiplier",
                "priority": "MEDIUM"
            })

        # Confidence calibration
        if conf_cal.mean_error > 0.15:
            recommendations.append({
                "issue": f"Confidence calibration error {conf_cal.mean_error:.0%}",
                "action": "Adjust confidence boost/penalty multipliers; recalibrate monthly",
                "priority": "HIGH"
            })
        elif conf_cal.mean_error > 0.10:
            recommendations.append({
                "issue": f"Confidence calibration slightly off ({conf_cal.mean_error:.0%})",
                "action": "Fine-tune confidence calculation weights",
                "priority": "MEDIUM"
            })

        if not recommendations:
            recommendations.append({
                "issue": "No major issues detected",
                "action": "Continue monitoring; recalibrate monthly",
                "priority": "ROUTINE"
            })

        return recommendations

    def calculate_edge(self, forecasts: List[Dict]) -> float:
        """
        Quick edge calculation without full report.

        Returns:
            Edge score as float (0.5 = no edge, >0.55 = good edge)
        """
        report = self.generate_report(forecasts)
        edge_str = report.summary['edge_score']
        return float(edge_str.rstrip('%')) / 100


def validate_forecasts(forecasts: List[Dict]) -> ValidationReport:
    """Convenience function to validate a list of forecasts."""
    validator = ForecastValidator()
    return validator.generate_report(forecasts)


def calculate_edge(forecasts: List[Dict]) -> float:
    """Convenience function to calculate edge score."""
    validator = ForecastValidator()
    return validator.calculate_edge(forecasts)
