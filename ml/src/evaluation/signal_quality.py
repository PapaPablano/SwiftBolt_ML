"""
Signal quality score computation for ML forecasts.

Combines accuracy, confidence interval width, and regime alignment
into a single 0-100 integer score with a calibration label.
"""

import logging

logger = logging.getLogger(__name__)


def compute_signal_quality(
    accuracy: float,
    confidence_width: float | None = None,
    regime_aligned: bool | None = None,
) -> tuple[int, str, float]:
    """
    Compute a signal quality score from evaluation metrics.

    Args:
        accuracy: Walk-forward accuracy in [0, 1] (e.g. 0.55 = 55%).
        confidence_width: Width of ensemble confidence interval as a fraction
            of price (e.g. 0.04 = 4%). None defaults to component score of 50.
        regime_aligned: True if forecast direction matches detected trend,
            False if opposing, None if regime unavailable (defaults to 50).

    Returns:
        Tuple of (score 0-100, calibration_label, accuracy_pct 0-100).
    """
    # --- accuracy component: normalize [0.45, 0.65] -> [0, 100] ---
    accuracy_pct = round(accuracy * 100, 2)
    acc_clamped = max(0.45, min(0.65, accuracy))
    accuracy_component = (acc_clamped - 0.45) / (0.65 - 0.45) * 100.0

    # --- confidence component: inverse of width, normalized ---
    if confidence_width is not None and confidence_width > 0:
        # Typical CI width range [0.02, 0.20]; narrower is better
        width_clamped = max(0.02, min(0.20, confidence_width))
        confidence_component = (1.0 - (width_clamped - 0.02) / (0.20 - 0.02)) * 100.0
    else:
        confidence_component = 50.0

    # --- regime component ---
    if regime_aligned is True:
        regime_component = 100.0
    elif regime_aligned is False:
        regime_component = 0.0
    else:
        regime_component = 50.0

    # --- weighted composite ---
    quality = round(0.5 * accuracy_component + 0.3 * confidence_component + 0.2 * regime_component)
    quality = max(0, min(100, quality))

    # --- calibration label ---
    if quality >= 70:
        label = "well-calibrated"
    elif quality >= 40:
        label = "moderate"
    else:
        label = "uncalibrated"

    logger.debug(
        "signal_quality=%d label=%s acc=%.2f ci_w=%s regime=%s",
        quality,
        label,
        accuracy,
        confidence_width,
        regime_aligned,
    )

    return quality, label, accuracy_pct
