# ML System Improvement Plan

> **Generated**: 2026-01-01
> **Updated**: 2026-01-01 (incorporated feedback)
> **Status**: Ready for Implementation
> **Estimated Impact**: 15-25% accuracy improvement across forecasts

---

## Executive Summary

This document outlines actionable improvements to the SwiftBolt ML forecasting system, organized by priority. Each item includes specific file changes, implementation steps, and expected impact.

### Key Changes from Review
- ✅ **ADX already uses Wilder's smoothing** - No fix needed (verified in `technical_indicators_corrected.py`)
- 🔄 **High confidence threshold**: Increased from 252 → **504 bars** (2 years)
- 🔄 **Feature scaling**: Changed from StandardScaler → **RobustScaler** (outlier resistant)
- 🔄 **Reordered phases**: Forecast Validator moved to Week 1 (foundational)
- 🔄 **Parallelized execution**: Compress timeline from 3 weeks → 2 weeks
- ➕ **Added**: IV curve smoothness check for options

---

## Phase 1: High Priority (Model Reliability)

### 1.1 Increase Minimum Training Data Threshold

**Problem**: Current `min_bars_for_training = 20` is statistically unreliable for model training. With 40+ features and 3-class classification, 20 samples leads to severe overfitting.

**Files to Modify**:
- [settings.py](../ml/config/settings.py)
- [forecast_job.py](../ml/src/forecast_job.py)

**Implementation**:

```python
# ml/config/settings.py - Line 38
# BEFORE:
min_bars_for_training: int = 20

# AFTER:
min_bars_for_training: int = 100  # Minimum for statistical significance
min_bars_for_high_confidence: int = 504  # 2 years for high-quality forecasts (market cycle)
```

**Rationale for 504 bars (2 years)**:
- Market cycles average ~2 years (bull/bear phases)
- 1 year (252 bars) may only capture half a cycle
- 2 years provides exposure to both up/down regimes

```python
# ml/src/forecast_job.py - Add confidence penalty for low data
def process_symbol(symbol: str) -> None:
    df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=252)

    # NEW: Calculate data quality multiplier
    data_quality_multiplier = min(1.0, len(df) / 252)  # 1.0 at 252+ bars

    # Apply to final confidence
    forecast["confidence"] *= data_quality_multiplier
```

**Expected Impact**: 5-10% accuracy improvement, reduced overfit forecasts

---

### 1.2 Implement Confidence Calibration Validation

**Problem**: Confidence scores are not validated against actual outcomes. A forecast with 80% confidence may only hit 50% of the time.

**Files to Create**:
- `ml/src/monitoring/confidence_calibrator.py`

**Files to Modify**:
- [forecast_job.py](../ml/src/forecast_job.py)
- [forecast_quality.py](../ml/src/monitoring/forecast_quality.py)

**Implementation**:

```python
# NEW FILE: ml/src/monitoring/confidence_calibrator.py
"""Confidence calibration for forecast validation."""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

@dataclass
class CalibrationResult:
    """Calibration analysis result."""
    bucket: str  # e.g., "70-80%"
    predicted_confidence: float  # Average confidence in bucket
    actual_accuracy: float  # Actual hit rate
    n_samples: int
    is_calibrated: bool  # Within 10% of predicted
    adjustment_factor: float  # Multiply confidence by this

class ConfidenceCalibrator:
    """
    Validates and adjusts confidence scores based on historical accuracy.

    Usage:
        calibrator = ConfidenceCalibrator()
        calibrator.fit(historical_forecasts, actual_outcomes)
        adjusted_confidence = calibrator.calibrate(raw_confidence)
    """

    BUCKETS = [(0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]

    def __init__(self):
        self.calibration_map: Dict[Tuple[float, float], float] = {}
        self.is_fitted = False

    def fit(
        self,
        forecasts: pd.DataFrame,
        min_samples_per_bucket: int = 30
    ) -> List[CalibrationResult]:
        """
        Fit calibration model on historical forecasts.

        Args:
            forecasts: DataFrame with 'confidence', 'predicted_label', 'actual_label'
            min_samples_per_bucket: Minimum samples to compute adjustment

        Returns:
            List of CalibrationResult for each bucket
        """
        results = []

        for low, high in self.BUCKETS:
            bucket_mask = (forecasts['confidence'] >= low) & (forecasts['confidence'] < high)
            bucket_data = forecasts[bucket_mask]

            if len(bucket_data) < min_samples_per_bucket:
                # Not enough data, use 1.0 (no adjustment)
                self.calibration_map[(low, high)] = 1.0
                continue

            # Calculate actual accuracy
            correct = (bucket_data['predicted_label'] == bucket_data['actual_label']).sum()
            actual_accuracy = correct / len(bucket_data)
            predicted_confidence = bucket_data['confidence'].mean()

            # Calculate adjustment factor
            # If predicted 75% but actual 60%, factor = 60/75 = 0.8
            adjustment = actual_accuracy / predicted_confidence if predicted_confidence > 0 else 1.0
            adjustment = np.clip(adjustment, 0.5, 1.5)  # Limit extreme adjustments

            self.calibration_map[(low, high)] = adjustment

            results.append(CalibrationResult(
                bucket=f"{int(low*100)}-{int(high*100)}%",
                predicted_confidence=predicted_confidence,
                actual_accuracy=actual_accuracy,
                n_samples=len(bucket_data),
                is_calibrated=abs(actual_accuracy - predicted_confidence) < 0.10,
                adjustment_factor=adjustment
            ))

        self.is_fitted = True
        return results

    def calibrate(self, confidence: float) -> float:
        """
        Apply calibration adjustment to raw confidence.

        Args:
            confidence: Raw confidence score (0-1)

        Returns:
            Calibrated confidence score
        """
        if not self.is_fitted:
            return confidence

        for (low, high), adjustment in self.calibration_map.items():
            if low <= confidence < high:
                return np.clip(confidence * adjustment, 0.40, 0.95)

        return confidence

    def get_calibration_report(self) -> str:
        """Generate human-readable calibration report."""
        if not self.is_fitted:
            return "Calibrator not fitted. Call fit() with historical data."

        lines = ["Confidence Calibration Report", "=" * 40]
        for (low, high), adjustment in self.calibration_map.items():
            status = "OK" if 0.9 <= adjustment <= 1.1 else "ADJUST"
            lines.append(f"{int(low*100)}-{int(high*100)}%: x{adjustment:.2f} [{status}]")

        return "\n".join(lines)
```

**Integration into forecast_job.py**:

```python
# Add to forecast_job.py after quality monitoring
from src.monitoring.confidence_calibrator import ConfidenceCalibrator

# Load historical forecasts for calibration (run periodically, not every forecast)
def load_calibration_data(symbol_id: str, lookback_days: int = 90):
    """Load historical forecasts with outcomes for calibration."""
    return db.fetch_forecast_outcomes(symbol_id, lookback_days)

# Apply calibration to confidence
calibrator = ConfidenceCalibrator()
historical = load_calibration_data(symbol_id)
if len(historical) >= 100:
    calibrator.fit(historical)
    forecast["confidence"] = calibrator.calibrate(forecast["confidence"])
```

**Expected Impact**: More reliable confidence scores, better decision-making

---

### 1.3 Fix Feature Scaling Consistency (Use RobustScaler)

**Problem**: `StandardScaler` used in `BaselineForecaster` but not consistently applied across all features. Tree models can handle unscaled features, but ensemble combination benefits from normalization.

**Key Change**: Use **RobustScaler** instead of StandardScaler for outlier resistance.

**Files to Modify**:
- [baseline_forecaster.py](../ml/src/models/baseline_forecaster.py)
- [ensemble_forecaster.py](../ml/src/models/ensemble_forecaster.py)

**Implementation**:

```python
# ml/src/models/ensemble_forecaster.py - Use RobustScaler
from sklearn.preprocessing import RobustScaler

class EnsembleForecaster:
    def __init__(self, ...):
        # CHANGE: Use RobustScaler instead of StandardScaler
        # RobustScaler uses median/IQR, not mean/std
        # Better for OHLC data with gaps and outliers
        self.scaler = RobustScaler()

    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Train ensemble with robust feature scaling."""

        # NEW: Apply RobustScaler to all numeric features
        X_scaled = pd.DataFrame(
            self.scaler.fit_transform(X),
            columns=X.columns,
            index=X.index
        )

        # Validate feature ranges after scaling
        feature_stats = X_scaled.describe()
        for col in X_scaled.columns:
            col_range = feature_stats.loc['max', col] - feature_stats.loc['min', col]
            if col_range > 10:  # After RobustScaler, range should be ~1-2
                logger.warning(
                    f"Feature '{col}' still has large range after scaling ({col_range:.2f}). "
                    "May contain extreme outliers."
                )

        # Continue with training on X_scaled...
```

**Why RobustScaler over StandardScaler**:
| Aspect | StandardScaler | RobustScaler |
|--------|----------------|--------------|
| Center | Mean | Median |
| Scale | Std Dev | IQR (Q3-Q1) |
| Outlier Sensitivity | High | Low |
| Best For | Normal distribution | Data with outliers |

**Expected Impact**: 2-5% accuracy improvement from consistent scaling + outlier handling

---

### 1.4 Scale Backtest Windows by Horizon

**Problem**: Fixed 252/21/5 walk-forward parameters don't suit all horizons. 1D forecasts backtested on 21-day windows (3 weeks) is too long; 6M forecasts on same window is too short.

**Files to Modify**:
- [walk_forward_tester.py](../ml/src/backtesting/walk_forward_tester.py)

**Implementation**:

```python
# ml/src/backtesting/walk_forward_tester.py

class WalkForwardBacktester:
    """Walk-forward backtester with horizon-aware windows."""

    # NEW: Horizon-specific window configuration
    HORIZON_WINDOWS = {
        "1D": {"train": 126, "test": 10, "step": 2},   # 6mo train, 2wk test
        "1W": {"train": 252, "test": 25, "step": 5},   # 1yr train, 5wk test
        "1M": {"train": 504, "test": 60, "step": 20},  # 2yr train, 3mo test
        "2M": {"train": 504, "test": 90, "step": 30},  # 2yr train, 4.5mo test
        "3M": {"train": 756, "test": 120, "step": 40}, # 3yr train, 6mo test
        "6M": {"train": 756, "test": 180, "step": 60}, # 3yr train, 9mo test
    }

    def __init__(
        self,
        train_window: int = 252,
        test_window: int = 21,
        step_size: int = 5,
        horizon: str = None,  # NEW: Optional horizon for auto-config
    ) -> None:
        if horizon and horizon in self.HORIZON_WINDOWS:
            config = self.HORIZON_WINDOWS[horizon]
            self.train_window = config["train"]
            self.test_window = config["test"]
            self.step_size = config["step"]
            logger.info(f"Using horizon-optimized windows for {horizon}: {config}")
        else:
            self.train_window = train_window
            self.test_window = test_window
            self.step_size = step_size
```

**Update forecast_job.py**:

```python
# forecast_job.py - Use horizon-aware backtester
backtester = WalkForwardBacktester(horizon=horizon)  # Auto-configure
```

**Expected Impact**: 5-10% improvement in backtest reliability, better horizon-specific metrics

---

## Phase 2: Medium Priority (Robustness)

### 2.1 Add Data Validation Pipeline

**Problem**: No validation of OHLC data quality. Outliers, gaps, or invalid values can corrupt features.

**Files to Create**:
- `ml/src/data/data_validator.py`

**Implementation**:

```python
# NEW FILE: ml/src/data/data_validator.py
"""OHLC data validation and cleaning pipeline."""

import logging
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    issues: List[str]
    rows_flagged: int
    rows_removed: int

class OHLCValidator:
    """
    Validates OHLC data for common issues.

    Checks:
    1. OHLC relationship: High >= max(Open, Close), Low <= min(Open, Close)
    2. Volume positivity: Volume >= 0
    3. Price positivity: All prices > 0
    4. Gap detection: Flags gaps > 3 ATR from previous close
    5. Outlier detection: Z-score > 4 on returns
    """

    MAX_GAP_ATRS = 3.0
    OUTLIER_ZSCORE = 4.0

    def validate(
        self,
        df: pd.DataFrame,
        fix_issues: bool = True
    ) -> Tuple[pd.DataFrame, ValidationResult]:
        """
        Validate and optionally fix OHLC data.

        Args:
            df: DataFrame with open, high, low, close, volume columns
            fix_issues: If True, remove/fix invalid rows

        Returns:
            Tuple of (cleaned DataFrame, ValidationResult)
        """
        issues = []
        original_len = len(df)
        flagged_rows = set()

        # 1. Check OHLC relationships
        invalid_high = df['high'] < df[['open', 'close']].max(axis=1)
        invalid_low = df['low'] > df[['open', 'close']].min(axis=1)

        if invalid_high.any():
            issues.append(f"High < max(Open,Close) in {invalid_high.sum()} rows")
            flagged_rows.update(df[invalid_high].index.tolist())

        if invalid_low.any():
            issues.append(f"Low > min(Open,Close) in {invalid_low.sum()} rows")
            flagged_rows.update(df[invalid_low].index.tolist())

        # 2. Check volume
        negative_volume = df['volume'] < 0
        if negative_volume.any():
            issues.append(f"Negative volume in {negative_volume.sum()} rows")
            flagged_rows.update(df[negative_volume].index.tolist())

        # 3. Check price positivity
        for col in ['open', 'high', 'low', 'close']:
            non_positive = df[col] <= 0
            if non_positive.any():
                issues.append(f"Non-positive {col} in {non_positive.sum()} rows")
                flagged_rows.update(df[non_positive].index.tolist())

        # 4. Gap detection (skip first row)
        if len(df) > 1:
            atr = self._calculate_atr(df, period=14)
            gaps = (df['open'].iloc[1:] - df['close'].iloc[:-1].values).abs()
            atr_aligned = atr.iloc[1:]

            large_gaps = gaps > (atr_aligned * self.MAX_GAP_ATRS)
            if large_gaps.any():
                gap_indices = df.index[1:][large_gaps]
                issues.append(f"Large gaps (>{self.MAX_GAP_ATRS} ATR) in {len(gap_indices)} rows")
                # Don't remove gaps, just flag

        # 5. Outlier detection on returns
        returns = df['close'].pct_change()
        zscore = (returns - returns.mean()) / returns.std()
        outliers = zscore.abs() > self.OUTLIER_ZSCORE
        if outliers.any():
            issues.append(f"Return outliers (z>{self.OUTLIER_ZSCORE}) in {outliers.sum()} rows")
            flagged_rows.update(df[outliers].index.tolist())

        # Apply fixes if requested
        rows_removed = 0
        if fix_issues and flagged_rows:
            # Remove flagged rows (except gaps which are just flagged)
            removable = flagged_rows - set(df.index[1:][large_gaps] if 'large_gaps' in dir() else [])
            df = df.drop(index=list(removable), errors='ignore')
            rows_removed = original_len - len(df)
            logger.info(f"Removed {rows_removed} invalid rows from data")

        return df, ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            rows_flagged=len(flagged_rows),
            rows_removed=rows_removed
        )

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)

        tr = pd.concat([
            high - low,
            (high - close).abs(),
            (low - close).abs()
        ], axis=1).max(axis=1)

        return tr.rolling(window=period).mean()
```

**Integration into forecast_job.py**:

```python
from src.data.data_validator import OHLCValidator

def process_symbol(symbol: str) -> None:
    df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=252)

    # NEW: Validate data
    validator = OHLCValidator()
    df, validation = validator.validate(df, fix_issues=True)

    if not validation.is_valid:
        logger.warning(f"Data issues for {symbol}: {validation.issues}")

    if len(df) < settings.min_bars_for_training:
        logger.warning(f"Insufficient data after validation for {symbol}")
        return
```

**Expected Impact**: Cleaner data, fewer corrupt forecasts

---

### 2.2 Temporal Smoothing for Options Ranking

**Problem**: Momentum score (40% weight) swings daily, causing high ranking churn and poor trade execution.

**IMPORTANT CLARIFICATION**: We smooth the **final ranking scores**, NOT the underlying Greeks (delta, gamma, theta, vega). Greeks should remain raw market signals.

| What to Smooth | Why |
|----------------|-----|
| ✅ `momentum_score` | Reduces noise in output rankings |
| ✅ `composite_rank` | Stabilizes final rankings |
| ❌ `delta`, `gamma`, etc. | Loses market signal precision |

**Files to Modify**:
- [options_momentum_ranker.py](../ml/src/models/options_momentum_ranker.py)

**Implementation**:

```python
# ml/src/models/options_momentum_ranker.py

class OptionsMomentumRanker:
    # NEW: Add smoothing parameters
    MOMENTUM_SMOOTHING_WINDOW = 3  # 3-day EMA for momentum stability

    def rank_options(
        self,
        options_df: pd.DataFrame,
        iv_stats: Optional[IVStatistics] = None,
        options_history: Optional[pd.DataFrame] = None,
        underlying_trend: str = "neutral",
        previous_rankings: Optional[pd.DataFrame] = None,  # NEW
    ) -> pd.DataFrame:
        """Rank options with optional temporal smoothing."""

        # ... existing ranking logic ...

        # NEW: Apply temporal smoothing if history available
        if previous_rankings is not None and not previous_rankings.empty:
            df = self._apply_temporal_smoothing(df, previous_rankings)

        return df

    def _apply_temporal_smoothing(
        self,
        current: pd.DataFrame,
        previous: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Apply EMA smoothing to momentum scores to reduce churn.

        Formula: smoothed = alpha * current + (1 - alpha) * previous
        Where alpha = 2 / (window + 1) for EMA
        """
        alpha = 2 / (self.MOMENTUM_SMOOTHING_WINDOW + 1)  # ~0.5 for 3-day

        # Match contracts between current and previous
        for idx, row in current.iterrows():
            contract_id = row.get('contract_symbol', f"{row['strike']}_{row['side']}")

            # Find previous momentum score
            prev_match = previous[
                previous.get('contract_symbol', previous['strike'].astype(str) + '_' + previous['side']) == contract_id
            ]

            if len(prev_match) > 0:
                prev_momentum = prev_match.iloc[0].get('momentum_score', row['momentum_score'])

                # EMA smoothing
                smoothed = alpha * row['momentum_score'] + (1 - alpha) * prev_momentum
                current.at[idx, 'momentum_score'] = smoothed

                # Recalculate composite with smoothed momentum
                current.at[idx, 'composite_rank'] = (
                    smoothed * self.MOMENTUM_WEIGHT +
                    row['value_score'] * self.VALUE_WEIGHT +
                    row['greeks_score'] * self.GREEKS_WEIGHT
                )

        return current
```

**Expected Impact**: 30% reduction in daily ranking churn

---

### 2.3 Integrate ForecastValidator into Pipeline

**Problem**: `ForecastQualityMonitor` exists but doesn't measure target precision, band efficiency, or edge.

**Files to Create**:
- `ml/src/monitoring/forecast_validator.py`

**Implementation**:

```python
# NEW FILE: ml/src/monitoring/forecast_validator.py
"""Forecast accuracy and edge validation."""

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

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

class ForecastValidator:
    """
    Validates forecast accuracy against realized outcomes.

    Usage:
        validator = ForecastValidator()
        metrics = validator.validate(historical_forecasts, actual_prices)
    """

    def validate(
        self,
        forecasts: pd.DataFrame,
        actuals: pd.DataFrame,
        atr_column: str = 'atr'
    ) -> ValidationMetrics:
        """
        Validate forecasts against actual outcomes.

        Args:
            forecasts: DataFrame with columns:
                - symbol, horizon, label, confidence
                - target, upper_band, lower_band
                - forecast_date
            actuals: DataFrame with columns:
                - symbol, date, close, atr

        Returns:
            ValidationMetrics with accuracy analysis
        """
        matched = self._match_forecasts_to_actuals(forecasts, actuals)

        if len(matched) == 0:
            return self._empty_metrics()

        # Direction accuracy
        direction_correct = matched['predicted_direction'] == matched['actual_direction']
        direction_accuracy = direction_correct.mean()

        # Target precision
        target_error = (matched['target'] - matched['actual_close']).abs() / matched['actual_close']
        avg_target_error = target_error.mean()

        if atr_column in matched.columns:
            target_within_1atr = (target_error <= matched[atr_column]).mean()
        else:
            target_within_1atr = np.nan

        # Band efficiency
        within_bands = (
            (matched['actual_close'] >= matched['lower_band']) &
            (matched['actual_close'] <= matched['upper_band'])
        )
        band_capture_rate = within_bands.mean()

        predicted_range = matched['upper_band'] - matched['lower_band']
        actual_range = matched['actual_high'] - matched['actual_low']

        band_too_wide = predicted_range > (actual_range * 2)
        band_too_narrow = ~within_bands

        # Edge calculation
        returns_following = matched['actual_return']
        wins = returns_following > 0
        losses = returns_following < 0

        win_rate = wins.mean()
        avg_win = returns_following[wins].mean() if wins.any() else 0
        avg_loss = returns_following[losses].abs().mean() if losses.any() else 0

        expected_edge = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        realized_edge = returns_following.mean()

        return ValidationMetrics(
            direction_accuracy=direction_accuracy,
            avg_target_error_pct=avg_target_error * 100,
            target_within_1atr=target_within_1atr,
            band_capture_rate=band_capture_rate,
            band_too_wide_rate=band_too_wide.mean(),
            band_too_narrow_rate=band_too_narrow.mean(),
            expected_edge=expected_edge * 100,
            realized_edge=realized_edge * 100,
            edge_gap=(expected_edge - realized_edge) * 100,
            n_samples=len(matched)
        )

    def _match_forecasts_to_actuals(
        self,
        forecasts: pd.DataFrame,
        actuals: pd.DataFrame
    ) -> pd.DataFrame:
        """Match each forecast to its outcome."""
        matched_rows = []

        for _, forecast in forecasts.iterrows():
            symbol = forecast['symbol']
            horizon_days = self._parse_horizon(forecast['horizon'])
            forecast_date = pd.to_datetime(forecast['forecast_date'])
            outcome_date = forecast_date + pd.Timedelta(days=horizon_days)

            # Find actual price at outcome date
            symbol_actuals = actuals[actuals['symbol'] == symbol]
            outcome = symbol_actuals[
                symbol_actuals['date'] >= outcome_date
            ].head(1)

            if len(outcome) == 0:
                continue

            actual_close = outcome.iloc[0]['close']
            entry_price = forecast.get('entry_price', forecast.get('current_price', actual_close))

            matched_rows.append({
                **forecast.to_dict(),
                'actual_close': actual_close,
                'actual_high': outcome.iloc[0].get('high', actual_close),
                'actual_low': outcome.iloc[0].get('low', actual_close),
                'actual_return': (actual_close - entry_price) / entry_price,
                'predicted_direction': forecast['label'].lower(),
                'actual_direction': 'bullish' if actual_close > entry_price else 'bearish',
            })

        return pd.DataFrame(matched_rows)

    def _parse_horizon(self, horizon: str) -> int:
        """Parse horizon string to days."""
        mapping = {'1D': 1, '1W': 5, '1M': 20, '2M': 40, '3M': 60, '6M': 120}
        return mapping.get(horizon, 1)

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
            n_samples=0
        )
```

**Expected Impact**: Measurable forecast quality, identify weak areas

---

### 2.4 Add IV Freshness Check for Options

**Problem**: IV calculations may use stale data in slow markets.

**Files to Modify**:
- [options_momentum_ranker.py](../ml/src/models/options_momentum_ranker.py)

**Implementation**:

```python
# ml/src/models/options_momentum_ranker.py

class IVStatistics:
    # ... existing code ...

    # NEW: Add freshness tracking
    last_updated: datetime = None
    max_age_hours: int = 4

    @property
    def is_stale(self) -> bool:
        """Check if IV data is stale (> max_age_hours old)."""
        if self.last_updated is None:
            return True
        age = datetime.now() - self.last_updated
        return age.total_seconds() > (self.max_age_hours * 3600)

    @property
    def staleness_penalty(self) -> float:
        """Calculate confidence penalty for stale data (0-0.2)."""
        if not self.is_stale:
            return 0.0

        age_hours = (datetime.now() - self.last_updated).total_seconds() / 3600
        # Linear penalty: 0 at max_age, 0.2 at 2x max_age
        excess_hours = age_hours - self.max_age_hours
        return min(0.2, excess_hours / self.max_age_hours * 0.2)

# In rank_options method:
def rank_options(self, ...):
    # Apply staleness penalty to value scores
    if iv_stats and iv_stats.is_stale:
        staleness_penalty = iv_stats.staleness_penalty
        logger.warning(f"IV data is stale ({iv_stats.last_updated}), applying {staleness_penalty:.1%} penalty")
        df["value_score"] *= (1 - staleness_penalty)
```

**Additional Check: IV Curve Smoothness**

IV shouldn't jump dramatically between adjacent strikes. Add this validation:

```python
# ml/src/models/options_momentum_ranker.py

class IVStatistics:
    # ... existing code ...

    def is_iv_curve_reasonable(self, iv_by_strike: dict) -> bool:
        """
        Check if IV curve is smooth (no >5% jumps between adjacent strikes).

        Large IV jumps between strikes indicate bad data or illiquidity.

        Args:
            iv_by_strike: Dict mapping strike price to IV

        Returns:
            True if IV curve is smooth, False if suspicious jumps exist
        """
        if len(iv_by_strike) < 2:
            return True

        strikes = sorted(iv_by_strike.keys())
        for i in range(1, len(strikes)):
            iv_current = iv_by_strike[strikes[i]]
            iv_prev = iv_by_strike[strikes[i-1]]

            if iv_prev > 0:
                iv_jump_pct = abs(iv_current - iv_prev) / iv_prev * 100
                if iv_jump_pct > 5.0:  # >5% jump is suspicious
                    logger.warning(
                        f"Suspicious IV jump: {strikes[i-1]} ({iv_prev:.2%}) -> "
                        f"{strikes[i]} ({iv_current:.2%}) = {iv_jump_pct:.1f}% jump"
                    )
                    return False

        return True

    @property
    def data_quality_score(self) -> float:
        """
        Combined data quality score (0-1).

        Factors:
        - Freshness (0.5 weight)
        - IV curve smoothness (0.5 weight)
        """
        freshness_score = 1.0 - self.staleness_penalty
        # Assume curve is reasonable if not checked
        curve_score = 1.0 if getattr(self, '_iv_curve_ok', True) else 0.7

        return freshness_score * 0.5 + curve_score * 0.5
```

**Expected Impact**: More reliable options rankings during low-activity periods

---

## Phase 3: Enhancements

### 3.1 Reduce S/R Indicator Redundancy

**Problem**: Three S/R indicators (Pivot, Polynomial, Logistic) may be highly correlated, over-weighting structural analysis.

**Files to Create**:
- `ml/src/features/sr_correlation_analyzer.py`

**Files to Modify**:
- [forecast_weights.py](../ml/src/forecast_weights.py)

**Implementation**:

```python
# NEW FILE: ml/src/features/sr_correlation_analyzer.py
"""Analyze correlation between S/R indicators to reduce redundancy."""

import numpy as np
import pandas as pd
from scipy import stats

class SRCorrelationAnalyzer:
    """
    Measures correlation between S/R indicators to optimize weights.

    If two indicators are highly correlated (r > 0.8), their combined
    weight should be reduced to avoid over-weighting that signal.
    """

    def analyze(
        self,
        pivot_levels: pd.Series,
        polynomial_levels: pd.Series,
        logistic_levels: pd.Series
    ) -> dict:
        """
        Compute pairwise correlations and suggest weight adjustments.

        Returns:
            Dict with correlations and suggested weight multipliers
        """
        correlations = {
            'pivot_poly': stats.pearsonr(pivot_levels, polynomial_levels)[0],
            'pivot_logistic': stats.pearsonr(pivot_levels, logistic_levels)[0],
            'poly_logistic': stats.pearsonr(polynomial_levels, logistic_levels)[0],
        }

        # Calculate redundancy penalties
        # High correlation (>0.8) means we should reduce combined weight
        penalties = {}
        for pair, corr in correlations.items():
            if abs(corr) > 0.8:
                penalties[pair] = 0.7  # 30% reduction for highly correlated
            elif abs(corr) > 0.6:
                penalties[pair] = 0.85  # 15% reduction
            else:
                penalties[pair] = 1.0  # No reduction

        # Suggest adjusted weights (default: 0.30, 0.35, 0.35)
        base_weights = {'pivot': 0.30, 'polynomial': 0.35, 'logistic': 0.35}

        # Apply average penalty to each indicator based on its correlations
        pivot_penalty = (penalties['pivot_poly'] + penalties['pivot_logistic']) / 2
        poly_penalty = (penalties['pivot_poly'] + penalties['poly_logistic']) / 2
        logistic_penalty = (penalties['pivot_logistic'] + penalties['poly_logistic']) / 2

        adjusted = {
            'pivot': base_weights['pivot'] * pivot_penalty,
            'polynomial': base_weights['polynomial'] * poly_penalty,
            'logistic': base_weights['logistic'] * logistic_penalty,
        }

        # Normalize to sum to 1
        total = sum(adjusted.values())
        adjusted = {k: v / total for k, v in adjusted.items()}

        return {
            'correlations': correlations,
            'penalties': penalties,
            'adjusted_weights': adjusted,
        }
```

**Expected Impact**: 3-5% improvement from reduced redundant signals

---

### 3.2 Event-Driven Forecast Refresh

**Problem**: Forecasts run on fixed schedule; major price moves can make forecasts stale.

**Files to Create**:
- `ml/src/monitoring/price_monitor.py`

**Implementation**:

```python
# NEW FILE: ml/src/monitoring/price_monitor.py
"""Monitor prices and trigger forecast refresh on significant moves."""

import logging
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RefreshTrigger:
    """Trigger for forecast refresh."""
    symbol: str
    reason: str
    price_move_pct: float
    atr_move: float
    triggered_at: datetime

class PriceMonitor:
    """
    Monitors price movements and triggers forecast refresh.

    Triggers refresh when:
    1. Price moves > 2 ATR from last forecast
    2. Price breaks key S/R level
    3. Trend reversal detected (SuperTrend flip)
    """

    MOVE_THRESHOLD_ATR = 2.0  # Trigger on 2+ ATR move
    MOVE_THRESHOLD_PCT = 5.0  # Or 5%+ move

    def __init__(self, db_client):
        self.db = db_client
        self.last_prices = {}
        self.last_atrs = {}

    def check_for_triggers(
        self,
        symbols: List[str]
    ) -> List[RefreshTrigger]:
        """
        Check all symbols for refresh triggers.

        Args:
            symbols: List of symbols to check

        Returns:
            List of RefreshTrigger for symbols needing refresh
        """
        triggers = []

        for symbol in symbols:
            trigger = self._check_symbol(symbol)
            if trigger:
                triggers.append(trigger)
                logger.info(f"Refresh triggered for {symbol}: {trigger.reason}")

        return triggers

    def _check_symbol(self, symbol: str) -> Optional[RefreshTrigger]:
        """Check single symbol for refresh trigger."""
        # Get last forecast
        forecast = self.db.get_latest_forecast(symbol)
        if not forecast:
            return None

        forecast_price = forecast.get('current_price', 0)
        forecast_atr = forecast.get('atr', forecast_price * 0.02)

        # Get current price
        current = self.db.get_current_price(symbol)
        if not current:
            return None

        current_price = current['close']

        # Calculate move
        move_pct = abs(current_price - forecast_price) / forecast_price * 100
        move_atr = abs(current_price - forecast_price) / forecast_atr

        # Check thresholds
        if move_atr >= self.MOVE_THRESHOLD_ATR:
            return RefreshTrigger(
                symbol=symbol,
                reason=f"Price moved {move_atr:.1f} ATR since last forecast",
                price_move_pct=move_pct,
                atr_move=move_atr,
                triggered_at=datetime.now()
            )

        if move_pct >= self.MOVE_THRESHOLD_PCT:
            return RefreshTrigger(
                symbol=symbol,
                reason=f"Price moved {move_pct:.1f}% since last forecast",
                price_move_pct=move_pct,
                atr_move=move_atr,
                triggered_at=datetime.now()
            )

        return None
```

**Expected Impact**: Fresher forecasts during volatile periods

---

### 3.3 Add Model Change Audit Trail

**Problem**: No tracking of how models change over time.

**Database Migration**:

```sql
-- migration: 20260101_add_ml_audit_trail.sql

CREATE TABLE ml_model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID REFERENCES symbols(id),
    model_type VARCHAR(50) NOT NULL,  -- 'ensemble', 'supertrend', 'sr'
    version_hash VARCHAR(64),  -- Hash of model parameters
    parameters JSONB,
    training_stats JSONB,
    performance_metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ml_forecast_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_id UUID REFERENCES ml_forecasts(id),
    field_name VARCHAR(50),
    old_value JSONB,
    new_value JSONB,
    change_reason VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_model_versions_symbol ON ml_model_versions(symbol_id);
CREATE INDEX idx_forecast_changes_forecast ON ml_forecast_changes(forecast_id);
```

**Expected Impact**: Better debugging, model improvement tracking

---

## Implementation Roadmap (Parallelized - 2 Weeks)

### Week 1: Foundation (Parallel Tracks)

**Track A: Model Reliability** (Primary developer)
| Order | Item | File(s) | Est. Time |
|-------|------|---------|-----------|
| A1 | 1.1 - Min training data (100 bars, 504 high conf) | settings.py | 15 min |
| A2 | 1.2 - Confidence calibrator | NEW: confidence_calibrator.py | 2 hrs |
| A3 | 2.3 - Forecast validator ⬆️ MOVED UP | NEW: forecast_validator.py | 2 hrs |

**Track B: Data Robustness** (Can run in parallel)
| Order | Item | File(s) | Est. Time |
|-------|------|---------|-----------|
| B1 | 1.3 - RobustScaler (not StandardScaler) | ensemble_forecaster.py | 30 min |
| B2 | 1.4 - Horizon-aware backtest windows | walk_forward_tester.py | 1 hr |
| B3 | 2.1 - OHLC data validation pipeline | NEW: data_validator.py | 1.5 hrs |

**Week 1 Checkpoint**:
- [ ] All 6 items complete
- [ ] Unit tests for new files
- [ ] Baseline backtest run for comparison

### Week 2: Integration & Enhancements

**Track A: Options Improvements**
| Order | Item | File(s) | Est. Time |
|-------|------|---------|-----------|
| A4 | 2.2 - Temporal smoothing (scores only) | options_momentum_ranker.py | 1 hr |
| A5 | 2.4 - IV freshness + curve smoothness | options_momentum_ranker.py | 1 hr |

**Track B: System Enhancements**
| Order | Item | File(s) | Est. Time |
|-------|------|---------|-----------|
| B4 | 3.1 - S/R correlation analyzer | NEW: sr_correlation_analyzer.py | 1.5 hrs |
| B5 | 3.2 - Event-driven forecast refresh | NEW: price_monitor.py | 2 hrs |
| B6 | 3.3 - Model audit trail | DB migration | 1 hr |

**Week 2 Checkpoint**:
- [ ] All items complete
- [ ] Integration tests pass
- [ ] A/B comparison backtest vs baseline

### Quick Wins (Implement Immediately)
These can be done in <30 minutes each:
1. [ ] Update `min_bars_for_training` from 20 → 100 in settings.py
2. [ ] Add `min_bars_for_high_confidence = 504` in settings.py
3. [ ] Import RobustScaler in ensemble_forecaster.py

---

## Validation Criteria

Each improvement should be validated by:

1. **Unit Tests**: Add tests for new classes/functions
2. **Backtest Comparison**: Run backtests before/after to measure improvement
3. **A/B Testing**: For production, run new logic on subset of symbols
4. **Metrics Tracking**: Log key metrics to database for trend analysis

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing forecasts | Implement behind feature flags |
| Performance degradation | Add timing instrumentation |
| Data quality issues | Validate on sample before full rollout |
| Confidence calibration instability | Require minimum 100 samples before applying |

---

## Success Metrics

| Metric | Current (Est.) | Week 1 Target | Week 2 Target |
|--------|----------------|---------------|---------------|
| Direction Accuracy | 55-60% | 62% | **65%+** |
| Confidence Calibration Gap | Unknown | Measured | **< 5%** |
| Band Capture Rate | Unknown | Measured | **> 75%** |
| Options Ranking Churn | High | -15% | **-30%** |
| Forecast Staleness | Fixed schedule | - | **Event-driven** |
| Data Validation | None | Implemented | **< 1% bad data** |

### Measurement Approach

1. **Direction Accuracy**: Run backtest on last 6 months of data, compare predicted vs actual direction
2. **Confidence Calibration**: Bucket forecasts by confidence, measure actual hit rate per bucket
3. **Band Capture Rate**: % of actual prices within predicted upper/lower bands
4. **Ranking Churn**: Count how many contracts change top-10 position day-over-day
5. **Data Validation**: % of rows flagged by OHLCValidator

### Baseline Run (Before Starting)

Before implementing changes, run this baseline measurement:

```bash
# From ml/ directory
python -m src.backtesting.run_baseline_benchmark
```

This creates a snapshot to compare against after improvements.
