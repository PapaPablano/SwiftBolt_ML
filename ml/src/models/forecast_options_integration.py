"""
Forecast-Options Integration: Connect ML Forecasts to Options Ranking
======================================================================

Bridges the ensemble forecasting pipeline with options ranking by:
- Converting forecast labels to trend signals
- Mapping forecast confidence to signal strength
- Integrating uncertainty metrics into risk assessment
- Providing forecast-aware options scoring

Key Features:
- Seamless integration with EnhancedOptionsRanker
- Forecast confidence weighting for options selection
- Uncertainty-based position sizing recommendations
- Multi-horizon forecast aggregation
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ForecastSignal:
    """Container for forecast signal compatible with options ranker."""

    trend: str  # 'bullish', 'bearish', 'neutral'
    signal_strength: float  # 0-10 scale
    supertrend_factor: float  # Volatility multiplier
    supertrend_performance: float  # Recent performance
    confidence: float  # 0-1 ensemble confidence
    agreement: float  # 0-1 model agreement
    uncertainty: float  # Normalized uncertainty
    forecast_return: Optional[float] = None
    forecast_volatility: Optional[float] = None
    horizon: str = "1D"
    n_models: int = 0


class ForecastOptionsIntegration:
    """
    Integrates ML ensemble forecasts with options ranking.

    Converts ensemble forecast output into the format expected by
    EnhancedOptionsRanker and provides additional forecast-aware scoring.
    """

    def __init__(
        self,
        confidence_weight: float = 0.3,
        agreement_weight: float = 0.2,
        min_confidence_for_directional: float = 0.55,
        uncertainty_discount_factor: float = 0.5,
    ) -> None:
        """
        Initialize Forecast-Options Integration.

        Args:
            confidence_weight: Weight for confidence in signal strength
            agreement_weight: Weight for model agreement in signal strength
            min_confidence_for_directional: Min confidence to consider directional
            uncertainty_discount_factor: How much to discount high uncertainty
        """
        self.confidence_weight = confidence_weight
        self.agreement_weight = agreement_weight
        self.min_confidence_for_directional = min_confidence_for_directional
        self.uncertainty_discount_factor = uncertainty_discount_factor

        logger.info(
            "ForecastOptionsIntegration initialized: " "conf_weight=%.2f, agreement_weight=%.2f",
            confidence_weight,
            agreement_weight,
        )

    def convert_forecast_to_signal(
        self,
        forecast: Dict[str, Any],
        ohlc_df: Optional[pd.DataFrame] = None,
    ) -> ForecastSignal:
        """
        Convert ensemble forecast to options-compatible signal.

        Args:
            forecast: Forecast dict from EnsembleManager or MultiModelEnsemble
            ohlc_df: Optional OHLC data for volatility estimation

        Returns:
            ForecastSignal compatible with EnhancedOptionsRanker
        """
        # Extract core forecast info
        label = forecast.get("label", "Neutral")
        confidence = forecast.get("confidence", 0.5)
        agreement = forecast.get("agreement", 0.5)
        probabilities = forecast.get("probabilities", {})

        # Convert label to trend
        trend = self._label_to_trend(label, confidence)

        # Calculate signal strength (0-10 scale)
        signal_strength = self._calculate_signal_strength(confidence, agreement, probabilities)

        # Calculate supertrend-like metrics
        supertrend_factor = self._estimate_supertrend_factor(forecast, ohlc_df)
        supertrend_performance = self._estimate_supertrend_performance(confidence, agreement)

        # Calculate uncertainty
        uncertainty = self._calculate_uncertainty(probabilities)

        return ForecastSignal(
            trend=trend,
            signal_strength=signal_strength,
            supertrend_factor=supertrend_factor,
            supertrend_performance=supertrend_performance,
            confidence=confidence,
            agreement=agreement,
            uncertainty=uncertainty,
            forecast_return=forecast.get("forecast_return"),
            forecast_volatility=forecast.get("forecast_volatility"),
            horizon=forecast.get("horizon", "1D"),
            n_models=forecast.get("n_models", forecast.get("n_models_used", 0)),
        )

    def create_trend_analysis_dict(
        self,
        signal: ForecastSignal,
        earnings_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create trend analysis dict compatible with EnhancedOptionsRanker.

        Args:
            signal: ForecastSignal from convert_forecast_to_signal
            earnings_date: Optional earnings date

        Returns:
            Dict compatible with rank_options_with_trend()
        """
        return {
            "trend": signal.trend,
            "signal_strength": signal.signal_strength,
            "supertrend_factor": signal.supertrend_factor,
            "supertrend_performance": signal.supertrend_performance,
            "earnings_date": earnings_date,
            # Extended metadata
            "forecast_confidence": signal.confidence,
            "forecast_agreement": signal.agreement,
            "forecast_uncertainty": signal.uncertainty,
            "forecast_return": signal.forecast_return,
            "forecast_volatility": signal.forecast_volatility,
            "forecast_horizon": signal.horizon,
            "n_models": signal.n_models,
            "source": "ensemble_forecast",
        }

    def score_option_with_forecast(
        self,
        option: Dict[str, Any],
        signal: ForecastSignal,
        underlying_price: float,
    ) -> float:
        """
        Score a single option contract based on forecast alignment.

        Args:
            option: Option contract dict with strike, side, etc.
            signal: ForecastSignal
            underlying_price: Current underlying price

        Returns:
            Forecast alignment score (0-1)
        """
        side = option.get("side", "call").lower()
        strike = option.get("strike", underlying_price)

        # Base directional alignment
        directional_score = self._score_directional_alignment(signal.trend, side, signal.confidence)

        # Moneyness alignment
        moneyness_score = self._score_moneyness_alignment(
            strike, underlying_price, signal.trend, side
        )

        # Confidence-weighted adjustment
        confidence_factor = 0.5 + 0.5 * signal.confidence

        # Agreement bonus
        agreement_bonus = 0.1 * signal.agreement

        # Uncertainty discount
        uncertainty_discount = 1 - (self.uncertainty_discount_factor * signal.uncertainty)

        # Combined score
        base_score = 0.6 * directional_score + 0.4 * moneyness_score
        adjusted_score = base_score * confidence_factor * uncertainty_discount
        final_score = min(1.0, adjusted_score + agreement_bonus)

        return float(final_score)

    def rank_options_with_forecast(
        self,
        options_df: pd.DataFrame,
        forecast: Dict[str, Any],
        underlying_price: float,
        ohlc_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Rank options using ensemble forecast.

        Args:
            options_df: Options chain DataFrame
            forecast: Forecast from EnsembleManager
            underlying_price: Current underlying price
            ohlc_df: Optional OHLC data

        Returns:
            DataFrame with forecast_score column added
        """
        if options_df.empty:
            logger.warning("Empty options DataFrame")
            return options_df

        # Convert forecast to signal
        signal = self.convert_forecast_to_signal(forecast, ohlc_df)

        df = options_df.copy()

        # Score each option
        scores = []
        for _, row in df.iterrows():
            option = row.to_dict()
            score = self.score_option_with_forecast(option, signal, underlying_price)
            scores.append(score)

        df["forecast_score"] = scores

        # Add forecast metadata
        df["forecast_trend"] = signal.trend
        df["forecast_confidence"] = signal.confidence
        df["forecast_agreement"] = signal.agreement

        # Sort by forecast score
        df = df.sort_values("forecast_score", ascending=False)

        return df

    def get_position_size_recommendation(
        self,
        signal: ForecastSignal,
        base_position_size: float = 1.0,
        max_position_size: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Get position size recommendation based on forecast confidence.

        Args:
            signal: ForecastSignal
            base_position_size: Base position size (1.0 = normal)
            max_position_size: Maximum position size multiplier

        Returns:
            Position sizing recommendation
        """
        # Confidence-based sizing
        confidence_factor = signal.confidence

        # Agreement bonus
        agreement_factor = 0.5 + 0.5 * signal.agreement

        # Uncertainty discount
        uncertainty_factor = 1 - signal.uncertainty

        # Combined factor
        size_factor = confidence_factor * agreement_factor * uncertainty_factor

        # Scale to position size
        recommended_size = base_position_size * (0.5 + size_factor)
        recommended_size = min(max_position_size, recommended_size)

        return {
            "recommended_size": float(recommended_size),
            "size_factor": float(size_factor),
            "confidence_component": float(confidence_factor),
            "agreement_component": float(agreement_factor),
            "uncertainty_component": float(uncertainty_factor),
            "is_high_conviction": (
                signal.confidence > 0.7 and signal.agreement > 0.7 and signal.uncertainty < 0.3
            ),
            "is_low_conviction": (
                signal.confidence < 0.55 or signal.agreement < 0.5 or signal.uncertainty > 0.5
            ),
        }

    def filter_options_by_forecast(
        self,
        options_df: pd.DataFrame,
        signal: ForecastSignal,
        min_forecast_score: float = 0.5,
    ) -> pd.DataFrame:
        """
        Filter options to those aligned with forecast.

        Args:
            options_df: Options DataFrame with forecast_score
            signal: ForecastSignal
            min_forecast_score: Minimum score threshold

        Returns:
            Filtered DataFrame
        """
        if "forecast_score" not in options_df.columns:
            logger.warning("No forecast_score column - returning all options")
            return options_df

        # Filter by score
        filtered = options_df[options_df["forecast_score"] >= min_forecast_score].copy()

        # Further filter by side alignment if directional
        if signal.trend != "neutral" and signal.confidence > 0.6:
            preferred_side = "call" if signal.trend == "bullish" else "put"

            # Keep only preferred side for strong signals
            if signal.confidence > 0.7:
                filtered = filtered[filtered["side"].str.lower() == preferred_side]

        return filtered

    def _label_to_trend(self, label: str, confidence: float) -> str:
        """Convert forecast label to trend string."""
        if confidence < self.min_confidence_for_directional:
            return "neutral"

        label_lower = label.lower()
        if label_lower == "bullish":
            return "bullish"
        elif label_lower == "bearish":
            return "bearish"
        else:
            return "neutral"

    def _calculate_signal_strength(
        self,
        confidence: float,
        agreement: float,
        probabilities: Dict[str, float],
    ) -> float:
        """Calculate signal strength on 0-10 scale."""
        # Base from confidence (0-5)
        base_strength = confidence * 5

        # Agreement bonus (0-2)
        agreement_bonus = agreement * 2

        # Probability spread bonus (0-3)
        # Higher spread = stronger signal
        if probabilities:
            probs = list(probabilities.values())
            if len(probs) >= 2:
                spread = max(probs) - min(probs)
                spread_bonus = spread * 3
            else:
                spread_bonus = 0
        else:
            spread_bonus = 0

        total = base_strength + agreement_bonus + spread_bonus
        return float(min(10.0, max(0.0, total)))

    def _estimate_supertrend_factor(
        self,
        forecast: Dict,
        ohlc_df: Optional[pd.DataFrame],
    ) -> float:
        """Estimate supertrend-like volatility factor."""
        # Use forecast volatility if available
        vol = forecast.get("forecast_volatility")
        if vol and vol > 0:
            # Scale to supertrend factor (typically 2-4)
            return float(2.0 + vol * 10)

        # Estimate from OHLC if available
        if ohlc_df is not None and len(ohlc_df) > 20:
            atr = self._calculate_atr(ohlc_df, 14)
            close = ohlc_df["close"].iloc[-1]
            atr_pct = atr / close if close > 0 else 0.02
            return float(2.0 + atr_pct * 50)

        return 3.0  # Default

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]

        return float(atr) if not pd.isna(atr) else 0.0

    def _estimate_supertrend_performance(
        self,
        confidence: float,
        agreement: float,
    ) -> float:
        """Estimate supertrend-like performance metric."""
        # Higher confidence + agreement = better "performance"
        return float(confidence * agreement)

    def _calculate_uncertainty(
        self,
        probabilities: Dict[str, float],
    ) -> float:
        """Calculate normalized uncertainty from probabilities."""
        if not probabilities:
            return 0.5

        probs = np.array(list(probabilities.values()))
        probs = probs[probs > 0]

        if len(probs) == 0:
            return 0.5

        # Shannon entropy
        entropy = -np.sum(probs * np.log(probs))

        # Normalize (max entropy for 3 classes = log(3))
        max_entropy = np.log(len(probs)) if len(probs) > 1 else 1
        normalized = entropy / max_entropy if max_entropy > 0 else 0

        return float(normalized)

    def _score_directional_alignment(
        self,
        trend: str,
        side: str,
        confidence: float,
    ) -> float:
        """Score alignment between forecast direction and option side."""
        if trend == "neutral":
            return 0.5  # Neutral is ok for either side

        is_aligned = (trend == "bullish" and side == "call") or (
            trend == "bearish" and side == "put"
        )

        if is_aligned:
            return 0.5 + 0.5 * confidence
        else:
            return 0.5 - 0.3 * confidence

    def _score_moneyness_alignment(
        self,
        strike: float,
        underlying: float,
        trend: str,
        side: str,
    ) -> float:
        """Score strike selection based on forecast."""
        if underlying <= 0:
            return 0.5

        moneyness = (strike - underlying) / underlying

        if trend == "bullish":
            if side == "call":
                # Prefer slightly OTM calls for bullish
                if 0 < moneyness < 0.05:
                    return 0.9
                elif -0.02 < moneyness <= 0:
                    return 0.8
                elif 0.05 <= moneyness < 0.1:
                    return 0.7
                else:
                    return 0.5
            else:
                # For puts in bullish, prefer OTM (lower strikes)
                if moneyness < -0.05:
                    return 0.7
                else:
                    return 0.4

        elif trend == "bearish":
            if side == "put":
                # Prefer slightly OTM puts for bearish
                if -0.05 < moneyness < 0:
                    return 0.9
                elif 0 <= moneyness < 0.02:
                    return 0.8
                elif -0.1 < moneyness <= -0.05:
                    return 0.7
                else:
                    return 0.5
            else:
                # For calls in bearish, prefer OTM (higher strikes)
                if moneyness > 0.05:
                    return 0.7
                else:
                    return 0.4

        else:
            # Neutral - prefer ATM
            if abs(moneyness) < 0.02:
                return 0.8
            elif abs(moneyness) < 0.05:
                return 0.7
            else:
                return 0.5


def create_integration_from_manager(
    manager: Any,  # EnsembleManager
) -> Tuple[ForecastOptionsIntegration, ForecastSignal]:
    """
    Convenience function to create integration from EnsembleManager.

    Args:
        manager: Trained EnsembleManager instance

    Returns:
        Tuple of (ForecastOptionsIntegration, latest ForecastSignal)
    """
    integration = ForecastOptionsIntegration()

    if manager.forecast_history:
        latest = manager.forecast_history[-1]
        forecast_dict = {
            "label": latest.label,
            "confidence": latest.confidence,
            "probabilities": latest.probabilities,
            "agreement": latest.agreement,
            "forecast_return": latest.forecast_return,
            "forecast_volatility": latest.forecast_volatility,
            "n_models": latest.n_models,
        }
        signal = integration.convert_forecast_to_signal(forecast_dict)
    else:
        # Default neutral signal
        signal = ForecastSignal(
            trend="neutral",
            signal_strength=5.0,
            supertrend_factor=3.0,
            supertrend_performance=0.5,
            confidence=0.5,
            agreement=0.5,
            uncertainty=0.5,
        )

    return integration, signal


if __name__ == "__main__":
    # Quick test
    print("Testing ForecastOptionsIntegration...")

    # Create sample forecast
    forecast = {
        "label": "Bullish",
        "confidence": 0.75,
        "agreement": 0.8,
        "probabilities": {
            "bullish": 0.75,
            "neutral": 0.15,
            "bearish": 0.10,
        },
        "forecast_return": 0.02,
        "forecast_volatility": 0.018,
        "n_models": 4,
        "horizon": "1D",
    }

    # Initialize integration
    integration = ForecastOptionsIntegration()

    # Convert to signal
    signal = integration.convert_forecast_to_signal(forecast)
    print("\nForecast Signal:")
    print(f"  Trend: {signal.trend}")
    print(f"  Signal Strength: {signal.signal_strength:.2f}")
    print(f"  SuperTrend Factor: {signal.supertrend_factor:.2f}")
    print(f"  Confidence: {signal.confidence:.2f}")
    print(f"  Agreement: {signal.agreement:.2f}")
    print(f"  Uncertainty: {signal.uncertainty:.3f}")

    # Create trend analysis dict
    trend_dict = integration.create_trend_analysis_dict(signal)
    print("\nTrend Analysis Dict:")
    for k, v in trend_dict.items():
        print(f"  {k}: {v}")

    # Create sample options
    options_df = pd.DataFrame(
        {
            "strike": [95, 100, 105, 110, 95, 100, 105],
            "side": ["call", "call", "call", "call", "put", "put", "put"],
            "expiration": ["2024-01-19"] * 7,
            "bid": [5.5, 2.5, 0.8, 0.2, 0.3, 1.0, 3.5],
            "ask": [5.7, 2.7, 1.0, 0.3, 0.4, 1.2, 3.7],
        }
    )

    # Rank options
    ranked = integration.rank_options_with_forecast(options_df, forecast, underlying_price=100)
    print("\nRanked Options:")
    print(ranked[["strike", "side", "forecast_score"]].to_string())

    # Position size recommendation
    sizing = integration.get_position_size_recommendation(signal)
    print("\nPosition Sizing:")
    print(f"  Recommended Size: {sizing['recommended_size']:.2f}x")
    print(f"  High Conviction: {sizing['is_high_conviction']}")

    print("\n\nSUCCESS: ForecastOptionsIntegration working!")
