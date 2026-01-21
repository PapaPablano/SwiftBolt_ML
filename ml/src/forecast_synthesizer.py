"""
Forecast Synthesizer - 3-Layer Directional Forecast Generation.

Combines:
- Layer 1: SuperTrend AI (momentum + trend confirmation)
- Layer 2: S/R Indicators (Pivot Levels, Polynomial, Logistic)
- Layer 3: Ensemble ML (RF + GB consensus)

Into precise directional forecasts with dynamic confidence bands.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.forecast_weights import ForecastWeights, get_default_weights


@dataclass
class ForecastResult:
    """Result of a forecast synthesis."""

    target: float
    upper_band: float
    lower_band: float
    confidence: float
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    layers_agreeing: int
    reasoning: str
    key_drivers: List[str]

    # Component breakdown
    supertrend_component: float
    polynomial_component: float
    ml_component: float
    sr_constraint_range: str

    # Metadata
    symbol: Optional[str] = None
    horizon: str = "1D"

    def to_dict(self) -> Dict:
        return {
            "target": self.target,
            "upper_band": self.upper_band,
            "lower_band": self.lower_band,
            "confidence": self.confidence,
            "direction": self.direction,
            "layers_agreeing": self.layers_agreeing,
            "reasoning": self.reasoning,
            "key_drivers": self.key_drivers,
            "supertrend_component": self.supertrend_component,
            "polynomial_component": self.polynomial_component,
            "ml_component": self.ml_component,
            "sr_constraint_range": self.sr_constraint_range,
            "symbol": self.symbol,
            "horizon": self.horizon,
        }


class ForecastSynthesizer:
    """
    Synthesizes 3-layer forecasts into precise directional targets.

    Usage:
        synthesizer = ForecastSynthesizer()
        result = synthesizer.generate_1d_forecast(
            current_price=100.0,
            df=df_with_indicators,
            supertrend_info=st_output,
            sr_response=sr_api_response,
            ensemble_result=ml_output,
            symbol="AAPL"
        )
    """

    def __init__(self, weights: Optional[ForecastWeights] = None):
        self.weights = weights or get_default_weights()

    def generate_forecast(
        self,
        current_price: float,
        df: pd.DataFrame,
        supertrend_info: Dict,
        sr_response: Dict,
        ensemble_result: Dict,
        horizon_days: float = 1.0,
        symbol: Optional[str] = None,
        timeframe: str = "d1",
    ) -> ForecastResult:
        """
        Generate forecast for any horizon length.

        Args:
            current_price: Latest close price
            df: DataFrame with OHLCV and indicators (including 'atr')
            supertrend_info: Output from SuperTrendAI.calculate()
            sr_response: Output from S/R indicator API/detector
            ensemble_result: Output from EnsembleForecaster.predict()
            horizon_days: Number of days to forecast (e.g., 0.167 for 4h, 30 for 30d)
            symbol: Optional stock ticker for logging
            timeframe: Source timeframe (e.g., "m15", "h1", "d1")

        Returns:
            ForecastResult with target, bands, confidence
        """
        # Scale ATR-based moves by horizon length
        horizon_scale = np.sqrt(horizon_days)  # Volatility scales with sqrt(time)
        
        result = self._generate_base_forecast(
            current_price=current_price,
            df=df,
            supertrend_info=supertrend_info,
            sr_response=sr_response,
            ensemble_result=ensemble_result,
            horizon_scale=horizon_scale,
            symbol=symbol,
        )
        
        # Update horizon metadata
        result.horizon = self._format_horizon(horizon_days)
        result.symbol = symbol
        
        return result

    def generate_1d_forecast(
        self,
        current_price: float,
        df: pd.DataFrame,
        supertrend_info: Dict,
        sr_response: Dict,
        ensemble_result: Dict,
        symbol: Optional[str] = None,
    ) -> ForecastResult:
        """
        Generate precise 1D forecast by synthesizing 3 layers.

        Args:
            current_price: Latest close price
            df: DataFrame with OHLCV and indicators (including 'atr')
            supertrend_info: Output from SuperTrendAI.calculate()
            sr_response: Output from S/R indicator API/detector
            ensemble_result: Output from EnsembleForecaster.predict()
            symbol: Optional stock ticker for logging

        Returns:
            ForecastResult with target, bands, confidence
        """
        # ===== LAYER 1: SuperTrend Bias =====
        trend_direction = supertrend_info.get("current_trend", "NEUTRAL")
        signal_strength = supertrend_info.get("signal_strength", 5) / 10.0  # Normalize to 0-1
        performance_idx = supertrend_info.get("performance_index", 0.5)

        # Get ATR from dataframe or supertrend info
        if "atr" in df.columns and len(df) > 0:
            atr = df["atr"].iloc[-1]
        else:
            atr = supertrend_info.get("atr", current_price * 0.02)  # Default 2%

        if atr is None or (isinstance(atr, float) and np.isnan(atr)):
            atr = supertrend_info.get("atr")

        if atr is None or (isinstance(atr, float) and np.isnan(atr)):
            if all(c in df.columns for c in ["high", "low", "close"]) and len(df) > 1:
                high = df["high"].astype(float)
                low = df["low"].astype(float)
                close = df["close"].astype(float)
                prev_close = close.shift(1)
                tr = pd.concat(
                    [
                        (high - low).abs(),
                        (high - prev_close).abs(),
                        (low - prev_close).abs(),
                    ],
                    axis=1,
                ).max(axis=1)
                atr = float(tr.tail(14).mean())

        if atr is None or (isinstance(atr, float) and np.isnan(atr)):
            atr = current_price * 0.02

        atr = float(atr)

        # SuperTrend suggests target move = atr × strength × performance
        st_target_move = atr * signal_strength * (0.5 + 0.5 * performance_idx)

        if trend_direction == "BULLISH":
            st_target = current_price + st_target_move
            st_bias = 1
        elif trend_direction == "BEARISH":
            st_target = current_price - st_target_move
            st_bias = -1
        else:
            st_target = current_price
            st_bias = 0

        # ===== LAYER 2: S/R Constraints =====
        support_weighted = self._calculate_sr_weighted(
            sr_response, is_support=True, current_price=current_price
        )
        resistance_weighted = self._calculate_sr_weighted(
            sr_response, is_support=False, current_price=current_price
        )

        # Extract polynomial momentum
        polynomial = sr_response.get("polynomial", {})
        poly_support_trend = polynomial.get("supportTrend", "flat")
        poly_resistance_trend = polynomial.get("resistanceTrend", "flat")
        poly_is_expanding = polynomial.get("isDiverging", False)
        poly_is_converging = polynomial.get("isConverging", False)

        # Get polynomial forecasts
        poly_forecast_support = polynomial.get("forecastSupport", [current_price])
        poly_forecast_resistance = polynomial.get("forecastResistance", [current_price])
        poly_target_support = poly_forecast_support[0] if poly_forecast_support else current_price
        poly_target_resistance = (
            poly_forecast_resistance[0] if poly_forecast_resistance else current_price
        )

        # Get logistic probabilities
        logistic = sr_response.get("logistic", {})
        logistic_resistance_levels = logistic.get("resistanceLevels", [])
        logistic_support_levels = logistic.get("supportLevels", [])

        logistic_resistance_prob = (
            logistic_resistance_levels[0].get("probability", 0.5)
            if logistic_resistance_levels
            else 0.5
        )
        logistic_support_prob = (
            logistic_support_levels[0].get("probability", 0.5) if logistic_support_levels else 0.5
        )

        # ===== LAYER 3: Ensemble Direction =====
        ml_label = ensemble_result.get("label", "Neutral")
        ml_confidence = ensemble_result.get("confidence", 0.5)
        ml_agreement = ensemble_result.get("agreement", False)

        if ml_label.lower() == "bullish":
            ml_bias = 1
        elif ml_label.lower() == "bearish":
            ml_bias = -1
        else:
            ml_bias = 0

        # ===== SYNTHESIZE FORECAST =====

        # 1. Count agreeing layers
        agreeing_layers = 0
        if st_bias == 1:
            agreeing_layers += 1
        if ml_bias == 1:
            agreeing_layers += 1
        # For S/R, check if there's room in the direction
        if st_bias == 1 and resistance_weighted > current_price * 1.01:
            agreeing_layers += 1
        elif st_bias == -1 and support_weighted < current_price * 0.99:
            agreeing_layers += 1

        # Determine overall direction
        if st_bias == 1 and ml_bias >= 0:
            direction = "BULLISH"
        elif st_bias == -1 and ml_bias <= 0:
            direction = "BEARISH"
        elif ml_bias == 1 and st_bias >= 0:
            direction = "BULLISH"
        elif ml_bias == -1 and st_bias <= 0:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        # 2. Calculate primary target
        if direction == "BULLISH":
            primary_target, upper_band, lower_band = self._calculate_bullish_target(
                current_price=current_price,
                st_target=st_target,
                atr=atr,
                poly_target=poly_target_resistance,
                poly_slope=poly_resistance_trend,
                resistance_weighted=resistance_weighted,
                support_weighted=support_weighted,
                logistic_resistance_prob=logistic_resistance_prob,
                poly_is_expanding=poly_is_expanding,
            )
            poly_component = poly_target_resistance

        elif direction == "BEARISH":
            primary_target, upper_band, lower_band = self._calculate_bearish_target(
                current_price=current_price,
                st_target=st_target,
                atr=atr,
                poly_target=poly_target_support,
                poly_slope=poly_support_trend,
                resistance_weighted=resistance_weighted,
                support_weighted=support_weighted,
                logistic_support_prob=logistic_support_prob,
                poly_is_expanding=poly_is_expanding,
            )
            poly_component = poly_target_support

        else:  # NEUTRAL
            primary_target = current_price
            upper_band = resistance_weighted
            lower_band = support_weighted
            poly_component = current_price

        # 3. Calculate confidence
        confidence = self._calculate_confidence(
            trend_strength=signal_strength,
            ml_confidence=ml_confidence,
            ml_agreement=ml_agreement,
            st_bias=st_bias,
            ml_bias=ml_bias,
            logistic_resistance_prob=logistic_resistance_prob,
            logistic_support_prob=logistic_support_prob,
            poly_is_expanding=poly_is_expanding,
            poly_is_converging=poly_is_converging,
            direction=direction,
        )

        # 4. Build reasoning
        drivers, reasoning = self._build_reasoning(
            direction=direction,
            signal_strength=signal_strength * 10,
            ml_confidence=ml_confidence,
            ml_agreement=ml_agreement,
            poly_is_expanding=poly_is_expanding,
            logistic_resistance_prob=logistic_resistance_prob,
            logistic_support_prob=logistic_support_prob,
            st_bias=st_bias,
        )

        # 5. Validate bands
        lower_band, upper_band = self._validate_bands(
            current_price=current_price,
            target=primary_target,
            lower_band=lower_band,
            upper_band=upper_band,
            atr=atr,
        )

        return ForecastResult(
            target=round(primary_target, 2),
            upper_band=round(upper_band, 2),
            lower_band=round(lower_band, 2),
            confidence=round(confidence, 2),
            direction=direction,
            layers_agreeing=agreeing_layers,
            reasoning=reasoning,
            key_drivers=drivers,
            supertrend_component=round(st_target, 2),
            polynomial_component=round(poly_component, 2),
            ml_component=(
                round(current_price * (1 + 0.02 * ml_bias), 2)
                if ml_bias != 0
                else round(current_price, 2)
            ),
            sr_constraint_range=f"{round(lower_band, 2)} - {round(upper_band, 2)}",
            symbol=symbol,
            horizon="1D",
        )

    def generate_1w_forecast(
        self,
        daily_forecast: ForecastResult,
        timeframe_forecasts: Dict[str, ForecastResult],
        current_price: float,
        symbol: Optional[str] = None,
    ) -> ForecastResult:
        """
        Generate 1W forecast using multi-timeframe alignment.

        Args:
            daily_forecast: 1D forecast result (used as anchor)
            timeframe_forecasts: Dict of forecasts for each timeframe ("1h", "4h", "1d", "1w")
            current_price: Latest close price
            symbol: Optional ticker

        Returns:
            ForecastResult for 1W horizon
        """
        # Count timeframe alignment
        timeframes = ["1h", "4h", "1d", "1w"]
        agreeing_frames = 0
        total_frames = 0

        primary_direction = daily_forecast.direction

        for tf in timeframes:
            if tf in timeframe_forecasts:
                tf_forecast = timeframe_forecasts[tf]
                if tf_forecast.direction == primary_direction:
                    agreeing_frames += 1
                total_frames += 1

        alignment_score = agreeing_frames / total_frames if total_frames > 0 else 0.0

        # 1W target: 40% daily continuation, 35% 1W level, 25% structure
        if "1w" in timeframe_forecasts:
            forecast_1w_level = timeframe_forecasts["1w"]
        else:
            forecast_1w_level = daily_forecast

        target_1w = (
            daily_forecast.target * 0.40
            + forecast_1w_level.target * 0.35
            + (
                daily_forecast.upper_band
                if primary_direction == "BULLISH"
                else daily_forecast.lower_band
            )
            * 0.25
        )

        # Confidence boost from alignment (require 60%+ agreement)
        alignment_bonus = 0.15 if alignment_score >= 0.6 else (alignment_score * 0.15)
        confidence_1w = min(0.95, daily_forecast.confidence * 0.8 + alignment_bonus)

        # Bands from 1W structure
        upper_band = forecast_1w_level.upper_band
        lower_band = forecast_1w_level.lower_band

        reasoning = (
            f"{daily_forecast.reasoning} | "
            f"Multi-frame alignment: {alignment_score*100:.0f}% ({agreeing_frames}/{total_frames} TFs)"
        )

        return ForecastResult(
            target=round(target_1w, 2),
            upper_band=round(upper_band, 2),
            lower_band=round(lower_band, 2),
            confidence=round(confidence_1w, 2),
            direction=primary_direction,
            layers_agreeing=daily_forecast.layers_agreeing,
            reasoning=reasoning,
            key_drivers=daily_forecast.key_drivers + [f"TF Alignment: {alignment_score*100:.0f}%"],
            supertrend_component=daily_forecast.supertrend_component,
            polynomial_component=daily_forecast.polynomial_component,
            ml_component=daily_forecast.ml_component,
            sr_constraint_range=f"{round(lower_band, 2)} - {round(upper_band, 2)}",
            symbol=symbol,
            horizon="1W",
        )

    def _calculate_sr_weighted(
        self, sr_response: Dict, is_support: bool, current_price: float
    ) -> float:
        """Calculate weighted S/R level from all 3 indicators."""
        weights = self.weights.sr_weights

        # Get pivot level (use 100-bar as strongest structure)
        pivot_levels = sr_response.get("pivotLevels", {})
        if is_support:
            pivot_100 = pivot_levels.get("period100", {}).get("low")
            pivot_50 = pivot_levels.get("period50", {}).get("low")
            pivot_25 = pivot_levels.get("period25", {}).get("low")
            # Use highest valid pivot below price
            pivots = [p for p in [pivot_100, pivot_50, pivot_25] if p and p < current_price]
            pivot = max(pivots) if pivots else current_price * 0.95
        else:
            pivot_100 = pivot_levels.get("period100", {}).get("high")
            pivot_50 = pivot_levels.get("period50", {}).get("high")
            pivot_25 = pivot_levels.get("period25", {}).get("high")
            # Use lowest valid pivot above price
            pivots = [p for p in [pivot_100, pivot_50, pivot_25] if p and p > current_price]
            pivot = min(pivots) if pivots else current_price * 1.05

        # Get polynomial level
        polynomial = sr_response.get("polynomial", {})
        if is_support:
            poly = polynomial.get("support", pivot)
        else:
            poly = polynomial.get("resistance", pivot)

        if poly is None:
            poly = pivot

        # Get logistic level (highest probability)
        logistic = sr_response.get("logistic", {})
        if is_support:
            logistic_levels = logistic.get("supportLevels", [])
        else:
            logistic_levels = logistic.get("resistanceLevels", [])

        if logistic_levels:
            # Sort by probability, take highest
            logistic_level = max(logistic_levels, key=lambda x: x.get("probability", 0))
            logistic_val = logistic_level.get("level", poly)
        else:
            logistic_val = poly

        # Weighted combination
        weighted = (
            pivot * weights["pivot_levels"]
            + poly * weights["polynomial"]
            + logistic_val * weights["logistic"]
        )

        return weighted

    def _calculate_bullish_target(
        self,
        current_price: float,
        st_target: float,
        atr: float,
        poly_target: float,
        poly_slope: str,
        resistance_weighted: float,
        support_weighted: float,
        logistic_resistance_prob: float,
        poly_is_expanding: bool,
    ) -> Tuple[float, float, float]:
        """Calculate bullish target and bands."""
        tw = self.weights.target_weights

        # Base from SuperTrend momentum
        primary_target = st_target * tw["supertrend_move"]

        # Add polynomial extrapolation
        primary_target += poly_target * tw["polynomial_forecast"]

        # Polynomial momentum bonus
        if poly_slope == "rising":
            primary_target += atr * 0.3  # Room to expand upside

        # Resistance constraint
        resistance_cap = resistance_weighted * 0.95  # Stay 5% below full resistance

        # Apply logistic probability constraint
        if logistic_resistance_prob > 0.70:
            # Strong resistance - pull target down
            primary_target = primary_target * 0.7 + resistance_cap * 0.3
        elif logistic_resistance_prob < 0.40:
            # Weak resistance - allow full move
            primary_target = min(primary_target, resistance_cap)
        else:
            # Moderate - blend
            primary_target = primary_target * 0.65 + resistance_cap * 0.35

        # Ensure target is above current price for bullish
        if primary_target < current_price:
            primary_target = current_price + atr * 0.5

        # Bands
        upper_band = resistance_cap
        lower_band = support_weighted

        return primary_target, upper_band, lower_band

    def _calculate_bearish_target(
        self,
        current_price: float,
        st_target: float,
        atr: float,
        poly_target: float,
        poly_slope: str,
        resistance_weighted: float,
        support_weighted: float,
        logistic_support_prob: float,
        poly_is_expanding: bool,
    ) -> Tuple[float, float, float]:
        """Calculate bearish target and bands."""
        tw = self.weights.target_weights

        # Base from SuperTrend momentum
        primary_target = st_target * tw["supertrend_move"]

        # Add polynomial extrapolation
        primary_target += poly_target * tw["polynomial_forecast"]

        # Polynomial momentum bonus
        if poly_slope == "falling":
            primary_target -= atr * 0.3  # Room to fall

        # Support constraint
        support_cap = support_weighted * 1.05  # Stay 5% above full support

        # Apply logistic probability constraint
        if logistic_support_prob > 0.70:
            # Strong support - pull target up
            primary_target = primary_target * 0.7 + support_cap * 0.3
        elif logistic_support_prob < 0.40:
            # Weak support - allow full move
            primary_target = max(primary_target, support_cap)
        else:
            # Moderate - blend
            primary_target = primary_target * 0.65 + support_cap * 0.35

        # Ensure target is below current price for bearish
        if primary_target > current_price:
            primary_target = current_price - atr * 0.5

        # Bands
        upper_band = resistance_weighted
        lower_band = support_cap

        return primary_target, upper_band, lower_band

    def _calculate_confidence(
        self,
        trend_strength: float,
        ml_confidence: float,
        ml_agreement: bool,
        st_bias: int,
        ml_bias: int,
        logistic_resistance_prob: float,
        logistic_support_prob: float,
        poly_is_expanding: bool,
        poly_is_converging: bool,
        direction: str,
    ) -> float:
        """Calculate forecast confidence based on layer agreement."""
        confidence = 0.50  # Start neutral

        boosts = self.weights.confidence_boosts
        penalties = self.weights.confidence_penalties

        # Boost from strong SuperTrend
        if trend_strength >= 0.7:
            confidence += boosts["strong_trend"]
        elif trend_strength >= 0.5:
            confidence += boosts["strong_trend"] * 0.5

        # Boost from high ensemble confidence
        if ml_confidence >= 0.70:
            confidence += boosts["high_ensemble_conf"]
        elif ml_confidence >= 0.55:
            confidence += boosts["high_ensemble_conf"] * 0.5

        # Boost from RF/GB agreement
        if ml_agreement:
            confidence += boosts["strong_agreement"]

        # Boost from multi-layer agreement
        if st_bias == ml_bias and st_bias != 0:
            confidence += boosts["all_layers_agree"] * 0.5

        # Boost from expanding S/R (room to move)
        if poly_is_expanding:
            confidence += boosts["expanding_sr"]

        # Penalty from weak trend
        if trend_strength < 0.3:
            confidence += penalties["weak_trend_strength"]

        # Penalty from weak ensemble
        if ml_confidence < 0.55:
            confidence += penalties["weak_ensemble_conf"]

        # Penalty from conflicting signals
        if st_bias != 0 and ml_bias != 0 and st_bias != ml_bias:
            confidence += penalties["conflicting_signals"]

        # Penalty from strong opposing level
        if direction == "BULLISH" and logistic_resistance_prob > 0.80:
            confidence += penalties["strong_resistance"]
        elif direction == "BEARISH" and logistic_support_prob > 0.80:
            confidence += penalties["strong_support"]

        # Penalty from converging S/R (squeeze = limited move)
        if poly_is_converging:
            confidence += penalties["converging_sr"]

        # Clip to 0.40-0.95 range
        return max(0.40, min(0.95, confidence))

    def _build_reasoning(
        self,
        direction: str,
        signal_strength: float,
        ml_confidence: float,
        ml_agreement: bool,
        poly_is_expanding: bool,
        logistic_resistance_prob: float,
        logistic_support_prob: float,
        st_bias: int,
    ) -> Tuple[List[str], str]:
        """Build reasoning string and key drivers list."""
        drivers = []

        if signal_strength >= 6:
            drivers.append(f"Strong SuperTrend signal ({signal_strength:.0f}/10)")
        elif signal_strength >= 4:
            drivers.append(f"Moderate SuperTrend signal ({signal_strength:.0f}/10)")

        if ml_confidence >= 0.70:
            drivers.append(f"High ML consensus ({ml_confidence*100:.0f}%)")
        elif ml_confidence >= 0.55:
            drivers.append(f"Moderate ML consensus ({ml_confidence*100:.0f}%)")

        if ml_agreement:
            drivers.append("RF and GB models agree")

        if poly_is_expanding:
            drivers.append("S/R levels expanding (room for move)")

        if direction == "BULLISH" and logistic_resistance_prob < 0.5:
            drivers.append("Weak resistance ahead")
        elif direction == "BEARISH" and logistic_support_prob < 0.5:
            drivers.append("Weak support below")

        if direction == "BULLISH" and logistic_resistance_prob > 0.7:
            drivers.append(f"Strong resistance ({logistic_resistance_prob*100:.0f}% prob)")
        elif direction == "BEARISH" and logistic_support_prob > 0.7:
            drivers.append(f"Strong support ({logistic_support_prob*100:.0f}% prob)")

        reasoning = (
            f"{direction} forecast: {', '.join(drivers)}"
            if drivers
            else f"{direction} signal with low conviction"
        )

        return drivers, reasoning

    def _validate_bands(
        self, current_price: float, target: float, lower_band: float, upper_band: float, atr: float
    ) -> Tuple[float, float]:
        """Validate and adjust bands to ensure they make sense."""
        bp = self.weights.band_params

        # Ensure bands don't cross
        if lower_band > upper_band:
            lower_band, upper_band = upper_band, lower_band

        # Ensure minimum band width
        min_width = current_price * (bp["min_band_pct"] / 100)
        if (upper_band - lower_band) < min_width:
            mid = (upper_band + lower_band) / 2
            lower_band = mid - min_width / 2
            upper_band = mid + min_width / 2

        # Ensure maximum band width
        max_width = current_price * (bp["max_band_pct"] / 100)
        if (upper_band - lower_band) > max_width:
            mid = (upper_band + lower_band) / 2
            lower_band = mid - max_width / 2
            upper_band = mid + max_width / 2

        # Ensure target is within bands
        if target > upper_band:
            target = (upper_band + current_price) / 2
        elif target < lower_band:
            target = (lower_band + current_price) / 2

        # Ensure bands contain current price
        if lower_band > current_price:
            lower_band = current_price - atr
        if upper_band < current_price:
            upper_band = current_price + atr

        return lower_band, upper_band

    def _generate_base_forecast(
        self,
        current_price: float,
        df: pd.DataFrame,
        supertrend_info: Dict,
        sr_response: Dict,
        ensemble_result: Dict,
        horizon_scale: float,
        symbol: Optional[str] = None,
    ) -> ForecastResult:
        """
        Generate base forecast with horizon scaling applied.
        
        This is the core forecast logic extracted from generate_1d_forecast
        with horizon_scale applied to ATR-based moves.
        """
        # ===== LAYER 1: SuperTrend Bias =====
        trend_direction = supertrend_info.get("current_trend", "NEUTRAL")
        signal_strength = supertrend_info.get("signal_strength", 5) / 10.0
        performance_idx = supertrend_info.get("performance_index", 0.5)

        # Get ATR
        if "atr" in df.columns and len(df) > 0:
            atr = df["atr"].iloc[-1]
        else:
            atr = supertrend_info.get("atr", current_price * 0.02)

        if atr is None or (isinstance(atr, float) and np.isnan(atr)):
            atr = supertrend_info.get("atr")

        if atr is None or (isinstance(atr, float) and np.isnan(atr)):
            if all(c in df.columns for c in ["high", "low", "close"]) and len(df) > 1:
                high = df["high"].astype(float)
                low = df["low"].astype(float)
                close = df["close"].astype(float)
                prev_close = close.shift(1)
                tr = pd.concat(
                    [
                        (high - low).abs(),
                        (high - prev_close).abs(),
                        (low - prev_close).abs(),
                    ],
                    axis=1,
                ).max(axis=1)
                atr = float(tr.tail(14).mean())

        if atr is None or (isinstance(atr, float) and np.isnan(atr)):
            atr = current_price * 0.02

        atr = float(atr)

        # Apply horizon scaling to ATR-based moves
        scaled_atr = atr * horizon_scale
        st_target_move = scaled_atr * signal_strength * (0.5 + 0.5 * performance_idx)

        if trend_direction == "BULLISH":
            st_target = current_price + st_target_move
            st_bias = 1
        elif trend_direction == "BEARISH":
            st_target = current_price - st_target_move
            st_bias = -1
        else:
            st_target = current_price
            st_bias = 0

        # ===== LAYER 2: S/R Constraints =====
        support_weighted = self._calculate_sr_weighted(
            sr_response, is_support=True, current_price=current_price
        )
        resistance_weighted = self._calculate_sr_weighted(
            sr_response, is_support=False, current_price=current_price
        )

        polynomial = sr_response.get("polynomial", {})
        poly_support_trend = polynomial.get("supportTrend", "flat")
        poly_resistance_trend = polynomial.get("resistanceTrend", "flat")
        poly_is_expanding = polynomial.get("isDiverging", False)
        poly_is_converging = polynomial.get("isConverging", False)

        poly_forecast_support = polynomial.get("forecastSupport", [current_price])
        poly_forecast_resistance = polynomial.get("forecastResistance", [current_price])
        poly_target_support = poly_forecast_support[0] if poly_forecast_support else current_price
        poly_target_resistance = (
            poly_forecast_resistance[0] if poly_forecast_resistance else current_price
        )

        logistic = sr_response.get("logistic", {})
        logistic_resistance_levels = logistic.get("resistanceLevels", [])
        logistic_support_levels = logistic.get("supportLevels", [])

        logistic_resistance_prob = (
            logistic_resistance_levels[0].get("probability", 0.5)
            if logistic_resistance_levels
            else 0.5
        )
        logistic_support_prob = (
            logistic_support_levels[0].get("probability", 0.5) if logistic_support_levels else 0.5
        )

        # ===== LAYER 3: Ensemble Direction =====
        ml_label = ensemble_result.get("label", "Neutral")
        ml_confidence = ensemble_result.get("confidence", 0.5)
        ml_agreement = ensemble_result.get("agreement", False)

        if ml_label.lower() == "bullish":
            ml_bias = 1
        elif ml_label.lower() == "bearish":
            ml_bias = -1
        else:
            ml_bias = 0

        # ===== SYNTHESIZE FORECAST =====
        agreeing_layers = 0
        if st_bias == 1:
            agreeing_layers += 1
        if ml_bias == 1:
            agreeing_layers += 1
        if st_bias == 1 and resistance_weighted > current_price * 1.01:
            agreeing_layers += 1
        elif st_bias == -1 and support_weighted < current_price * 0.99:
            agreeing_layers += 1

        # Determine overall direction
        if st_bias == 1 and ml_bias >= 0:
            direction = "BULLISH"
        elif st_bias == -1 and ml_bias <= 0:
            direction = "BEARISH"
        elif ml_bias == 1 and st_bias >= 0:
            direction = "BULLISH"
        elif ml_bias == -1 and st_bias <= 0:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        # Calculate primary target
        if direction == "BULLISH":
            primary_target, upper_band, lower_band = self._calculate_bullish_target(
                current_price=current_price,
                st_target=st_target,
                atr=scaled_atr,
                poly_target=poly_target_resistance,
                poly_slope=poly_resistance_trend,
                resistance_weighted=resistance_weighted,
                support_weighted=support_weighted,
                logistic_resistance_prob=logistic_resistance_prob,
                poly_is_expanding=poly_is_expanding,
            )
            poly_component = poly_target_resistance

        elif direction == "BEARISH":
            primary_target, upper_band, lower_band = self._calculate_bearish_target(
                current_price=current_price,
                st_target=st_target,
                atr=scaled_atr,
                poly_target=poly_target_support,
                poly_slope=poly_support_trend,
                resistance_weighted=resistance_weighted,
                support_weighted=support_weighted,
                logistic_support_prob=logistic_support_prob,
                poly_is_expanding=poly_is_expanding,
            )
            poly_component = poly_target_support

        else:  # NEUTRAL
            primary_target = current_price
            upper_band = resistance_weighted
            lower_band = support_weighted
            poly_component = current_price

        # Calculate confidence
        confidence = self._calculate_confidence(
            trend_strength=signal_strength,
            ml_confidence=ml_confidence,
            ml_agreement=ml_agreement,
            st_bias=st_bias,
            ml_bias=ml_bias,
            logistic_resistance_prob=logistic_resistance_prob,
            logistic_support_prob=logistic_support_prob,
            poly_is_expanding=poly_is_expanding,
            poly_is_converging=poly_is_converging,
            direction=direction,
        )

        # Build reasoning
        drivers, reasoning = self._build_reasoning(
            direction=direction,
            signal_strength=signal_strength * 10,
            ml_confidence=ml_confidence,
            ml_agreement=ml_agreement,
            poly_is_expanding=poly_is_expanding,
            logistic_resistance_prob=logistic_resistance_prob,
            logistic_support_prob=logistic_support_prob,
            st_bias=st_bias,
        )

        # Validate bands
        lower_band, upper_band = self._validate_bands(
            current_price=current_price,
            target=primary_target,
            lower_band=lower_band,
            upper_band=upper_band,
            atr=scaled_atr,
        )

        return ForecastResult(
            target=round(primary_target, 2),
            upper_band=round(upper_band, 2),
            lower_band=round(lower_band, 2),
            confidence=round(confidence, 2),
            direction=direction,
            layers_agreeing=agreeing_layers,
            reasoning=reasoning,
            key_drivers=drivers,
            supertrend_component=round(st_target, 2),
            polynomial_component=round(poly_component, 2),
            ml_component=(
                round(current_price * (1 + 0.02 * ml_bias), 2)
                if ml_bias != 0
                else round(current_price, 2)
            ),
            sr_constraint_range=f"{round(lower_band, 2)} - {round(upper_band, 2)}",
            symbol=symbol,
            horizon="1D",
        )

    def _format_horizon(self, horizon_days: float) -> str:
        """Format horizon_days into readable string (e.g., 0.167 -> '4h', 30 -> '30d')."""
        if horizon_days < 1:
            hours = int(horizon_days * 24)
            return f"{hours}h"
        elif horizon_days == 7:
            return "1w"
        elif horizon_days == 30:
            return "1M"
        elif horizon_days == 60:
            return "2M"
        elif horizon_days == 90:
            return "3M"
        elif horizon_days == 120:
            return "4M"
        elif horizon_days == 180:
            return "6M"
        elif horizon_days == 360:
            return "1Y"
        else:
            return f"{int(horizon_days)}d"


# Convenience function
def synthesize_forecast(
    current_price: float,
    df: pd.DataFrame,
    supertrend_info: Dict,
    sr_response: Dict,
    ensemble_result: Dict,
    symbol: Optional[str] = None,
    weights: Optional[ForecastWeights] = None,
) -> ForecastResult:
    """
    Convenience function to synthesize a 1D forecast.

    Args:
        current_price: Latest close price
        df: DataFrame with OHLCV and indicators
        supertrend_info: SuperTrend AI output
        sr_response: S/R indicator output
        ensemble_result: Ensemble ML output
        symbol: Optional ticker
        weights: Optional custom weights

    Returns:
        ForecastResult
    """
    synthesizer = ForecastSynthesizer(weights=weights)
    return synthesizer.generate_1d_forecast(
        current_price=current_price,
        df=df,
        supertrend_info=supertrend_info,
        sr_response=sr_response,
        ensemble_result=ensemble_result,
        symbol=symbol,
    )
