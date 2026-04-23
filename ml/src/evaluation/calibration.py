"""
Calibration evaluation for quantile forecasts.

Measures whether predicted quantile intervals contain the expected fraction
of actual outcomes (e.g. 10% of actuals should fall below q10).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum sample size for meaningful calibration statistics
MIN_CALIBRATION_SAMPLES = 20

# Expected coverage for each standard quantile key
_EXPECTED_COVERAGE: dict[str, float] = {
    "q10": 0.10,
    "q25": 0.25,
    "q50": 0.50,
    "q75": 0.75,
    "q90": 0.90,
}


def compute_calibration_metrics(
    actuals: list[float],
    predictions: dict[str, list[float]],
) -> Optional[dict[str, float]]:
    """
    Compute calibration metrics for quantile forecasts.

    For each quantile *q*, calibration measures what fraction of *actuals*
    fell **below** the corresponding predicted quantile value.  Perfect
    calibration means that fraction equals the nominal quantile level
    (e.g. 10% of actuals < q10 predictions).

    Parameters
    ----------
    actuals : list[float]
        Observed values (e.g. realised returns or prices), one per forecast.
    predictions : dict[str, list[float]]
        Mapping from quantile key (``"q10"``, ``"q25"``, ``"q50"``,
        ``"q75"``, ``"q90"``) to a list of predicted values aligned with
        *actuals*.

    Returns
    -------
    dict[str, float] | None
        Keys like ``"q10_coverage"``, ``"q25_coverage"``, ...,
        ``"calibration_error"`` (mean absolute deviation from ideal).
        Returns ``None`` if fewer than ``MIN_CALIBRATION_SAMPLES`` are
        provided or inputs are invalid.
    """
    n = len(actuals)
    if n < MIN_CALIBRATION_SAMPLES:
        logger.warning(
            "compute_calibration_metrics: too few samples (%d < %d), returning None",
            n,
            MIN_CALIBRATION_SAMPLES,
        )
        return None

    # Validate that all prediction lists match actuals length
    for key, preds in predictions.items():
        if len(preds) != n:
            logger.warning(
                "compute_calibration_metrics: length mismatch for %s (%d != %d)",
                key,
                len(preds),
                n,
            )
            return None

    results: dict[str, float] = {}
    abs_errors: list[float] = []

    for q_key, expected in _EXPECTED_COVERAGE.items():
        preds = predictions.get(q_key)
        if preds is None:
            continue

        # Fraction of actuals that fell below the predicted quantile value
        below_count = sum(1 for a, p in zip(actuals, preds) if a < p)
        coverage = below_count / n
        results[f"{q_key}_coverage"] = round(coverage, 4)
        abs_errors.append(abs(coverage - expected))

    if not abs_errors:
        logger.warning("compute_calibration_metrics: no valid quantile keys found")
        return None

    results["calibration_error"] = round(sum(abs_errors) / len(abs_errors), 4)
    return results
