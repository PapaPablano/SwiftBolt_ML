"""
Support/Resistance Level Hold Probability Predictor.

Uses Logistic Regression to predict P(level holds) based on:
- RSI at level formation
- Volume at pivot points
- Candle body size at touches
- Historical touch count
- Recency of formation

Phase 2 of the Advanced S/R Integration Strategy.
"""

import logging
from typing import Any, Dict, List, Tuple

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class SRProbabilityPredictor:
    """
    Predicts probability that S/R levels will hold.

    Uses logistic regression trained on historical level outcomes to predict
    whether a detected support or resistance level will hold or break.

    Features used:
    - rsi_at_formation: RSI value when level was formed
    - volume_at_pivot: Volume ratio at pivot vs average
    - body_size_pct: Candle body size as % of range
    - touch_count: How many times level was tested
    - recency_score: How recent the level is (0-100)
    - distance_from_price_pct: Current distance from price
    - level_age_days: Age of level in bars

    Usage:
        predictor = SRProbabilityPredictor()

        # Train on historical data
        X, y = predictor.generate_training_data(df, levels_with_outcomes)
        predictor.train(X, y)

        # Predict probability for new level
        prob = predictor.predict_probability(df, level_price, level_idx)
    """

    def __init__(self, lookback_period: int = 100):
        """
        Initialize the predictor.

        Args:
            lookback_period: Number of bars to analyze for training
        """
        self.lookback_period = lookback_period
        self.model = LogisticRegression(random_state=42, max_iter=1000)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = [
            "rsi_at_formation",
            "volume_at_pivot",
            "body_size_pct",
            "touch_count",
            "recency_score",
            "distance_from_price_pct",
            "level_age_days",
        ]

    def extract_level_features(
        self,
        df: pd.DataFrame,
        level: float,
        level_idx: int,
        current_idx: int,
    ) -> Dict[str, float]:
        """
        Extract features for a single S/R level.

        Args:
            df: OHLC DataFrame with indicators
            level: Price level to analyze
            level_idx: Index where level was formed
            current_idx: Current bar index

        Returns:
            Dict of feature values
        """
        # Ensure indices are valid
        level_idx = max(0, min(level_idx, len(df) - 1))
        current_idx = max(0, min(current_idx, len(df) - 1))

        # RSI at formation
        rsi_at_formation = 50.0
        if "rsi_14" in df.columns:
            rsi_val = df["rsi_14"].iloc[level_idx]
            if pd.notna(rsi_val):
                rsi_at_formation = float(rsi_val)

        # Volume at pivot (relative to average)
        volume_at_pivot = 1.0
        if "volume" in df.columns:
            start_idx = max(0, level_idx - 20)
            avg_volume = df["volume"].iloc[start_idx:level_idx].mean()
            pivot_volume = df["volume"].iloc[level_idx]
            if avg_volume > 0 and pd.notna(pivot_volume):
                volume_at_pivot = float(pivot_volume / avg_volume)

        # Body size at formation (relative to range)
        body_size_pct = 50.0
        open_price = df["open"].iloc[level_idx]
        close_price = df["close"].iloc[level_idx]
        high = df["high"].iloc[level_idx]
        low = df["low"].iloc[level_idx]
        range_size = high - low if high > low else 0.01
        if range_size > 0:
            body_size_pct = abs(close_price - open_price) / range_size * 100

        # Touch count (how many times price approached this level)
        tolerance = level * 0.01  # 1% tolerance
        touches_df = df.iloc[level_idx:current_idx]
        if len(touches_df) > 0:
            touches = touches_df[
                (touches_df["low"] <= level + tolerance) & (touches_df["high"] >= level - tolerance)
            ]
            touch_count = len(touches)
        else:
            touch_count = 0

        # Recency score (how recent is the level)
        bars_since_formation = current_idx - level_idx
        recency_score = max(0, 100 - bars_since_formation)

        # Distance from current price
        current_price = df["close"].iloc[current_idx]
        distance_from_price_pct = abs(level - current_price) / current_price * 100

        # Level age in bars
        level_age_days = float(bars_since_formation)

        return {
            "rsi_at_formation": rsi_at_formation,
            "volume_at_pivot": volume_at_pivot,
            "body_size_pct": body_size_pct,
            "touch_count": float(touch_count),
            "recency_score": recency_score,
            "distance_from_price_pct": distance_from_price_pct,
            "level_age_days": level_age_days,
        }

    def generate_training_data(
        self,
        df: pd.DataFrame,
        levels: List[Dict[str, Any]],
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Generate training data from historical level outcomes.

        Args:
            df: OHLC DataFrame with indicators
            levels: List of historical levels with outcomes
                    Each dict should have: price, index, held (bool)

        Returns:
            Tuple of (features_df, labels_series)
        """
        X_list = []
        y_list = []

        for level_info in levels:
            level_price = level_info.get("price")
            level_idx = level_info.get("index")
            did_hold = level_info.get("held")

            if level_price is None or level_idx is None or did_hold is None:
                continue

            # Extract features at different points after formation
            # This creates multiple training samples per level
            for check_idx in range(level_idx + 5, min(level_idx + 50, len(df))):
                features = self.extract_level_features(df, level_price, level_idx, check_idx)
                X_list.append(features)
                y_list.append(1 if did_hold else 0)

        if not X_list:
            logger.warning("No training data generated for S/R probability model")
            return pd.DataFrame(), pd.Series(dtype=float)

        X = pd.DataFrame(X_list)
        y = pd.Series(y_list)

        logger.info(f"Generated {len(X)} training samples for S/R probability model")
        return X, y

    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """
        Train the logistic regression model.

        Args:
            X: Feature DataFrame
            y: Label series (1=held, 0=broken)

        Returns:
            Training metrics dict
        """
        if len(X) < 50:
            logger.warning(f"Insufficient training data: {len(X)} samples (need 50+)")
            return {"error": "Insufficient data", "n_samples": len(X)}

        try:
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            self.is_trained = True

            train_accuracy = self.model.score(X_scaled, y)

            # Get feature importances (coefficients)
            coefficients = dict(zip(self.feature_names, self.model.coef_[0]))

            logger.info(
                f"S/R probability model trained: "
                f"accuracy={train_accuracy:.3f}, samples={len(X)}"
            )

            return {
                "n_samples": len(X),
                "accuracy": train_accuracy,
                "coefficients": coefficients,
            }

        except Exception as e:
            logger.error(f"Failed to train S/R probability model: {e}")
            return {"error": str(e)}

    def predict_probability(
        self,
        df: pd.DataFrame,
        level: float,
        level_idx: int,
    ) -> float:
        """
        Predict probability that a level will hold.

        Args:
            df: OHLC DataFrame with indicators
            level: Price level to predict
            level_idx: Index where level was formed

        Returns:
            Probability (0-1) that level will hold
        """
        if not self.is_trained:
            logger.debug("S/R probability model not trained, returning default 0.5")
            return 0.5

        current_idx = len(df) - 1
        features = self.extract_level_features(df, level, level_idx, current_idx)

        try:
            X = pd.DataFrame([features])
            X_scaled = self.scaler.transform(X)
            probability = self.model.predict_proba(X_scaled)[0][1]
            return float(probability)
        except Exception as e:
            logger.warning(f"Failed to predict S/R probability: {e}")
            return 0.5

    def add_probability_features(
        self,
        df: pd.DataFrame,
        sr_levels: Dict[str, Any],
    ) -> pd.DataFrame:
        """
        Add hold probability features to DataFrame.

        Args:
            df: OHLC DataFrame
            sr_levels: S/R levels from detector (includes zigzag swings)

        Returns:
            DataFrame with probability features added
        """
        df = df.copy()

        # Get zigzag swings for level formation indices
        methods = sr_levels.get("methods", {})
        zigzag_data = methods.get("zigzag", {})
        swings = zigzag_data.get("swings", [])

        nearest_support = sr_levels.get("nearest_support")
        nearest_resistance = sr_levels.get("nearest_resistance")

        # Default probabilities
        support_prob = 0.5
        resistance_prob = 0.5

        # Find support level formation index and predict
        if nearest_support and swings and self.is_trained:
            support_swings = [s for s in swings if s.get("type") == "low"]
            if support_swings:
                # Find closest swing to nearest support
                closest_swing = min(
                    support_swings,
                    key=lambda s: abs(s.get("price", 0) - nearest_support),
                )
                swing_price = closest_swing.get("price", 0)
                # Only use if swing is close to the support level (within 2%)
                if abs(swing_price - nearest_support) / nearest_support < 0.02:
                    support_prob = self.predict_probability(
                        df, nearest_support, closest_swing.get("index", 0)
                    )

        # Find resistance level formation index and predict
        if nearest_resistance and swings and self.is_trained:
            resistance_swings = [s for s in swings if s.get("type") == "high"]
            if resistance_swings:
                closest_swing = min(
                    resistance_swings,
                    key=lambda s: abs(s.get("price", 0) - nearest_resistance),
                )
                swing_price = closest_swing.get("price", 0)
                if abs(swing_price - nearest_resistance) / nearest_resistance < 0.02:
                    resistance_prob = self.predict_probability(
                        df, nearest_resistance, closest_swing.get("index", 0)
                    )

        # Add features (broadcast to all rows)
        df["support_hold_probability"] = support_prob
        df["resistance_hold_probability"] = resistance_prob

        logger.info(
            f"Added S/R probability features: "
            f"support_prob={support_prob:.3f}, resistance_prob={resistance_prob:.3f}"
        )

        return df


def create_historical_level_outcomes(
    df: pd.DataFrame,
    swings: List[Dict[str, Any]],
    forward_bars: int = 20,
) -> List[Dict[str, Any]]:
    """
    Create training labels by checking if levels held in subsequent bars.

    A level is considered to have "held" if:
    - For support (low): price never closed significantly below it
    - For resistance (high): price never closed significantly above it

    Args:
        df: OHLC DataFrame
        swings: ZigZag swing points from SupportResistanceDetector
        forward_bars: Number of bars to check for level hold

    Returns:
        List of levels with held/broken outcome
    """
    levels_with_outcomes = []

    for swing in swings:
        level_price = swing.get("price")
        level_idx = swing.get("index")
        level_type = swing.get("type")

        if level_price is None or level_idx is None or level_type is None:
            continue

        # Get future bars after level formation
        end_idx = min(level_idx + forward_bars, len(df))
        if end_idx <= level_idx:
            continue

        future_bars = df.iloc[level_idx:end_idx]

        # Determine if level held
        # Use 1% tolerance for "breaking" the level
        tolerance = level_price * 0.01

        if level_type == "low":  # Support level
            # Level held if low never went significantly below it
            min_low = future_bars["low"].min()
            held = min_low >= level_price - tolerance
        else:  # Resistance level
            # Level held if high never went significantly above it
            max_high = future_bars["high"].max()
            held = max_high <= level_price + tolerance

        levels_with_outcomes.append(
            {
                "price": level_price,
                "index": level_idx,
                "type": level_type,
                "held": held,
            }
        )

    logger.info(
        f"Created {len(levels_with_outcomes)} level outcomes "
        f"({sum(1 for level in levels_with_outcomes if level['held'])} held, "
        f"{sum(1 for level in levels_with_outcomes if not level['held'])} broken)"
    )

    return levels_with_outcomes
