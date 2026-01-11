"""
Forecast Explainer: Provide human-readable explanations for ML predictions.

This module generates explanations for why the model made a particular
prediction, including:
1. Top contributing features
2. Signal breakdown by indicator
3. Confidence factors
4. Risk assessment

Usage:
    explainer = ForecastExplainer(model, features_df)
    explanation = explainer.explain_prediction(symbol="AAPL")
    print(explanation.summary)
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureContribution:
    """Contribution of a single feature to the prediction."""

    feature_name: str
    value: float
    importance: float
    direction: str  # 'bullish', 'bearish', 'neutral'
    description: str


@dataclass
class SignalBreakdown:
    """Breakdown of signals by category."""

    category: str  # 'trend', 'momentum', 'volatility', 'volume'
    signal: str  # 'bullish', 'bearish', 'neutral'
    strength: float  # 0-1
    indicators: List[str]
    description: str


@dataclass
class ForecastExplanation:
    """Complete explanation for a forecast."""

    symbol: str
    prediction: str  # 'bullish', 'bearish', 'neutral'
    confidence: float
    price_target: Optional[float]
    summary: str
    top_features: List[FeatureContribution]
    signal_breakdown: List[SignalBreakdown]
    risk_factors: List[str]
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    recommendation: str
    timestamp: str


class ForecastExplainer:
    """
    Generate human-readable explanations for ML forecasts.

    This class analyzes model predictions and feature values to explain
    why the model made a particular prediction in terms that traders
    can understand.
    """

    # Feature category mappings
    TREND_FEATURES = ["sma", "ema", "price_vs_sma", "supertrend", "adx", "plus_di", "minus_di"]
    MOMENTUM_FEATURES = ["rsi", "macd", "macd_signal", "macd_hist", "stochastic", "kdj"]
    VOLATILITY_FEATURES = ["atr", "bb_width", "volatility", "bb_upper", "bb_lower"]
    VOLUME_FEATURES = ["volume", "volume_ratio", "obv", "mfi", "vwap"]

    def __init__(
        self,
        feature_importance: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize the explainer.

        Args:
            feature_importance: Optional dict of feature -> importance score
        """
        self.feature_importance = feature_importance or {}

    def explain_prediction(
        self,
        symbol: str,
        features: Dict[str, float],
        prediction: str,
        confidence: float,
        price_target: Optional[float] = None,
        model_info: Optional[Dict[str, Any]] = None,
    ) -> ForecastExplanation:
        """
        Generate a complete explanation for a prediction.

        Args:
            symbol: Stock ticker
            features: Dictionary of feature name -> value
            prediction: Model prediction ('bullish', 'bearish', 'neutral')
            confidence: Prediction confidence (0-1)
            price_target: Optional price target
            model_info: Optional additional model information

        Returns:
            ForecastExplanation with detailed breakdown
        """
        # Analyze top contributing features
        top_features = self._analyze_top_features(features, prediction)

        # Break down signals by category
        signal_breakdown = self._analyze_signal_breakdown(features)

        # Identify risk factors
        risk_factors = self._identify_risk_factors(features, prediction)

        # Gather supporting and contradicting evidence
        supporting, contradicting = self._gather_evidence(features, prediction, signal_breakdown)

        # Generate summary
        summary = self._generate_summary(
            symbol, prediction, confidence, top_features, signal_breakdown
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(prediction, confidence, risk_factors)

        from datetime import datetime

        return ForecastExplanation(
            symbol=symbol,
            prediction=prediction,
            confidence=confidence,
            price_target=price_target,
            summary=summary,
            top_features=top_features,
            signal_breakdown=signal_breakdown,
            risk_factors=risk_factors,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            recommendation=recommendation,
            timestamp=datetime.now().isoformat(),
        )

    def _analyze_top_features(
        self,
        features: Dict[str, float],
        prediction: str,
    ) -> List[FeatureContribution]:
        """Identify and explain top contributing features."""
        contributions = []

        for name, value in features.items():
            if pd.isna(value):
                continue

            importance = self.feature_importance.get(name, 0.5)
            direction, description = self._interpret_feature(name, value)

            contributions.append(
                FeatureContribution(
                    feature_name=name,
                    value=value,
                    importance=importance,
                    direction=direction,
                    description=description,
                )
            )

        # Sort by importance and return top 5
        contributions.sort(key=lambda x: x.importance, reverse=True)
        return contributions[:5]

    def _interpret_feature(
        self,
        name: str,
        value: float,
    ) -> Tuple[str, str]:
        """Interpret a feature value and generate description."""
        name_lower = name.lower()

        # RSI interpretation
        if "rsi" in name_lower:
            if value > 70:
                return "bearish", f"RSI at {value:.1f} indicates overbought conditions"
            elif value < 30:
                return "bullish", f"RSI at {value:.1f} indicates oversold conditions"
            else:
                return "neutral", f"RSI at {value:.1f} is in neutral territory"

        # MACD interpretation
        if "macd" in name_lower and "signal" not in name_lower:
            if value > 0:
                return "bullish", f"MACD at {value:.2f} shows bullish momentum"
            else:
                return "bearish", f"MACD at {value:.2f} shows bearish momentum"

        # ADX interpretation
        if "adx" in name_lower:
            if value > 25:
                return "neutral", f"ADX at {value:.1f} indicates strong trend"
            else:
                return "neutral", f"ADX at {value:.1f} indicates weak/no trend"

        # Price vs SMA
        if "price_vs_sma" in name_lower:
            if value > 0.02:
                return "bullish", f"Price {value*100:.1f}% above SMA (bullish)"
            elif value < -0.02:
                return "bearish", f"Price {abs(value)*100:.1f}% below SMA (bearish)"
            else:
                return "neutral", "Price near SMA (neutral)"

        # Volatility
        if "volatility" in name_lower or "atr" in name_lower:
            return "neutral", f"Volatility measure at {value:.4f}"

        # Volume ratio
        if "volume_ratio" in name_lower:
            if value > 1.5:
                return "neutral", f"Volume {value:.1f}x average (high activity)"
            elif value < 0.5:
                return "neutral", f"Volume {value:.1f}x average (low activity)"
            else:
                return "neutral", f"Volume at {value:.1f}x average"

        # Default
        return "neutral", f"{name}: {value:.4f}"

    def _analyze_signal_breakdown(
        self,
        features: Dict[str, float],
    ) -> List[SignalBreakdown]:
        """Break down signals by category."""
        breakdowns = []

        # Analyze each category
        for category, feature_patterns in [
            ("trend", self.TREND_FEATURES),
            ("momentum", self.MOMENTUM_FEATURES),
            ("volatility", self.VOLATILITY_FEATURES),
            ("volume", self.VOLUME_FEATURES),
        ]:
            matching_features = []
            bullish_count = 0
            bearish_count = 0

            for name, value in features.items():
                if pd.isna(value):
                    continue

                name_lower = name.lower()
                if any(pattern in name_lower for pattern in feature_patterns):
                    matching_features.append(name)
                    direction, _ = self._interpret_feature(name, value)
                    if direction == "bullish":
                        bullish_count += 1
                    elif direction == "bearish":
                        bearish_count += 1

            if not matching_features:
                continue

            total = bullish_count + bearish_count
            if total == 0:
                signal = "neutral"
                strength = 0.5
            elif bullish_count > bearish_count:
                signal = "bullish"
                strength = bullish_count / len(matching_features)
            elif bearish_count > bullish_count:
                signal = "bearish"
                strength = bearish_count / len(matching_features)
            else:
                signal = "neutral"
                strength = 0.5

            description = self._generate_category_description(
                category, signal, strength, matching_features
            )

            breakdowns.append(
                SignalBreakdown(
                    category=category,
                    signal=signal,
                    strength=strength,
                    indicators=matching_features,
                    description=description,
                )
            )

        return breakdowns

    def _generate_category_description(
        self,
        category: str,
        signal: str,
        strength: float,
        indicators: List[str],
    ) -> str:
        """Generate description for a signal category."""
        strength_word = (
            "strongly" if strength > 0.7 else "moderately" if strength > 0.4 else "weakly"
        )

        if category == "trend":
            if signal == "bullish":
                return f"Trend indicators are {strength_word} bullish"
            elif signal == "bearish":
                return f"Trend indicators are {strength_word} bearish"
            else:
                return "Trend indicators show mixed signals"

        elif category == "momentum":
            if signal == "bullish":
                return f"Momentum is {strength_word} positive"
            elif signal == "bearish":
                return f"Momentum is {strength_word} negative"
            else:
                return "Momentum indicators are neutral"

        elif category == "volatility":
            return f"Volatility analysis based on {len(indicators)} indicators"

        elif category == "volume":
            return f"Volume analysis based on {len(indicators)} indicators"

        return f"{category.title()} analysis complete"

    def _identify_risk_factors(
        self,
        features: Dict[str, float],
        prediction: str,
    ) -> List[str]:
        """Identify potential risk factors."""
        risks = []

        # Check for overbought/oversold conditions
        for name, value in features.items():
            if pd.isna(value):
                continue

            name_lower = name.lower()

            if "rsi" in name_lower:
                if value > 80:
                    risks.append("RSI extremely overbought (>80) - reversal risk")
                elif value < 20:
                    risks.append("RSI extremely oversold (<20) - reversal risk")

            if "adx" in name_lower and value < 20:
                risks.append("Weak trend (ADX < 20) - choppy conditions likely")

            if "volatility" in name_lower or "atr" in name_lower:
                # Would need historical context to determine if high
                pass

        # Check for contradicting signals
        if prediction == "bullish":
            for name, value in features.items():
                if pd.isna(value):
                    continue
                if "rsi" in name.lower() and value > 70:
                    risks.append("Bullish prediction but RSI overbought")
                    break

        elif prediction == "bearish":
            for name, value in features.items():
                if pd.isna(value):
                    continue
                if "rsi" in name.lower() and value < 30:
                    risks.append("Bearish prediction but RSI oversold")
                    break

        if not risks:
            risks.append("No significant risk factors identified")

        return risks

    def _gather_evidence(
        self,
        features: Dict[str, float],
        prediction: str,
        signal_breakdown: List[SignalBreakdown],
    ) -> Tuple[List[str], List[str]]:
        """Gather supporting and contradicting evidence."""
        supporting = []
        contradicting = []

        for breakdown in signal_breakdown:
            if breakdown.signal == prediction:
                supporting.append(f"{breakdown.category.title()}: {breakdown.description}")
            elif breakdown.signal != "neutral" and breakdown.signal != prediction:
                contradicting.append(f"{breakdown.category.title()}: {breakdown.description}")

        if not supporting:
            supporting.append("Limited supporting evidence from indicators")

        if not contradicting:
            contradicting.append("No significant contradicting signals")

        return supporting, contradicting

    def _generate_summary(
        self,
        symbol: str,
        prediction: str,
        confidence: float,
        top_features: List[FeatureContribution],
        signal_breakdown: List[SignalBreakdown],
    ) -> str:
        """Generate a human-readable summary."""
        conf_word = "high" if confidence > 0.7 else "moderate" if confidence > 0.4 else "low"

        # Count agreeing categories
        agreeing = sum(1 for b in signal_breakdown if b.signal == prediction)
        total = len(signal_breakdown)

        summary = (
            f"{symbol} shows a {prediction.upper()} outlook with {conf_word} confidence "
            f"({confidence*100:.0f}%). "
        )

        if agreeing > 0:
            summary += f"{agreeing}/{total} indicator categories support this view. "

        if top_features:
            top = top_features[0]
            summary += f"Key driver: {top.description}."

        return summary

    def _generate_recommendation(
        self,
        prediction: str,
        confidence: float,
        risk_factors: List[str],
    ) -> str:
        """Generate actionable recommendation."""
        has_risks = len(risk_factors) > 1 or (
            len(risk_factors) == 1 and "No significant" not in risk_factors[0]
        )

        if confidence > 0.7 and not has_risks:
            if prediction == "bullish":
                return "Strong buy signal - consider entering long position"
            elif prediction == "bearish":
                return "Strong sell signal - consider short or exit long"
            else:
                return "Hold - wait for clearer signal"

        elif confidence > 0.5:
            if prediction == "bullish":
                return "Moderate buy signal - consider small position with stops"
            elif prediction == "bearish":
                return "Moderate sell signal - tighten stops on longs"
            else:
                return "Neutral - no clear edge, stay on sidelines"

        else:
            return "Low confidence - wait for confirmation before acting"

    def to_dict(self, explanation: ForecastExplanation) -> Dict[str, Any]:
        """Convert explanation to dictionary for JSON serialization."""
        return {
            "symbol": explanation.symbol,
            "prediction": explanation.prediction,
            "confidence": explanation.confidence,
            "price_target": explanation.price_target,
            "summary": explanation.summary,
            "top_features": [
                {
                    "name": f.feature_name,
                    "value": f.value,
                    "importance": f.importance,
                    "direction": f.direction,
                    "description": f.description,
                }
                for f in explanation.top_features
            ],
            "signal_breakdown": [
                {
                    "category": s.category,
                    "signal": s.signal,
                    "strength": s.strength,
                    "indicators": s.indicators,
                    "description": s.description,
                }
                for s in explanation.signal_breakdown
            ],
            "risk_factors": explanation.risk_factors,
            "supporting_evidence": explanation.supporting_evidence,
            "contradicting_evidence": explanation.contradicting_evidence,
            "recommendation": explanation.recommendation,
            "timestamp": explanation.timestamp,
        }
