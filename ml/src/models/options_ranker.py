"""ML-based options contract ranking model."""

import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class OptionsRanker:
    """
    Ranks option contracts based on ML-derived favorability scores.

    Scoring considers:
    - Moneyness (distance from strike to underlying price)
    - Implied volatility relative to historical volatility
    - Open interest and volume (liquidity)
    - Greeks (delta, gamma, theta, vega)
    - Time to expiration
    - Underlying price trend and momentum
    """

    def __init__(self):
        """Initialize the options ranker."""
        self.weights = {
            "moneyness": 0.25,
            "iv_rank": 0.20,
            "liquidity": 0.15,
            "delta_score": 0.15,
            "theta_decay": 0.10,
            "momentum": 0.15,
        }

    def rank_options(
        self,
        options_df: pd.DataFrame,
        underlying_price: float,
        underlying_trend: str = "neutral",  # bullish, neutral, bearish
        historical_vol: float = 0.30,  # 30% default HV
    ) -> pd.DataFrame:
        """
        Score and rank options contracts.

        Args:
            options_df: DataFrame with columns: strike, side, expiration, delta,
                       gamma, theta, vega, impliedVolatility, volume, openInterest,
                       bid, ask, last
            underlying_price: Current price of underlying asset
            underlying_trend: ML-derived trend (bullish/neutral/bearish)
            historical_vol: Historical volatility of underlying

        Returns:
            DataFrame with added 'ml_score' column, sorted by score descending
        """
        if options_df.empty:
            logger.warning("No options data to rank")
            return options_df

        df = options_df.copy()

        # Calculate component scores
        df["moneyness_score"] = self._score_moneyness(
            df["strike"], df["side"], underlying_price, underlying_trend
        )
        df["iv_rank_score"] = self._score_iv_rank(df["impliedVolatility"], historical_vol)
        df["liquidity_score"] = self._score_liquidity(df["volume"], df["openInterest"])
        df["delta_score"] = self._score_delta(df["delta"], df["side"], underlying_trend)
        df["theta_decay_score"] = self._score_theta(df["theta"], df["side"], df["expiration"])
        df["momentum_score"] = self._score_momentum(underlying_trend, df["side"])

        # Weighted composite score
        df["ml_score"] = 0.0
        for component, weight in self.weights.items():
            score_col = f"{component}_score"
            if score_col in df.columns:
                df["ml_score"] += df[score_col] * weight

        # Normalize to 0-1 range
        if df["ml_score"].max() > 0:
            df["ml_score"] = df["ml_score"] / df["ml_score"].max()

        # Clamp to ensure 0-1 range
        df["ml_score"] = df["ml_score"].clip(0, 1)

        # Sort by score
        df = df.sort_values("ml_score", ascending=False).reset_index(drop=True)

        logger.info(f"Ranked {len(df)} options contracts")
        logger.info(f"Score range: {df['ml_score'].min():.3f} - {df['ml_score'].max():.3f}")

        return df

    def _score_moneyness(
        self,
        strikes: pd.Series,
        sides: pd.Series,
        underlying_price: float,
        trend: str,
    ) -> pd.Series:
        """
        Score options based on moneyness and trend alignment.

        Higher scores for:
        - Calls: ATM/slightly OTM on bullish trend
        - Puts: ATM/slightly OTM on bearish trend
        """
        # Calculate moneyness percentage
        moneyness = (strikes - underlying_price) / underlying_price

        scores = pd.Series(0.0, index=strikes.index)

        for idx in strikes.index:
            m = moneyness.loc[idx]
            side = sides.loc[idx]

            if side == "call":
                # Calls: favor slightly OTM to ATM
                if trend == "bullish":
                    if -0.02 <= m <= 0.05:  # ATM to 5% OTM
                        scores.loc[idx] = 1.0
                    elif -0.05 <= m < -0.02 or 0.05 < m <= 0.10:  # Nearby
                        scores.loc[idx] = 0.7
                    else:
                        scores.loc[idx] = max(0, 1.0 - abs(m) * 5)
                else:
                    scores.loc[idx] = max(0, 0.5 - abs(m) * 3)

            else:  # put
                # Puts: favor slightly OTM to ATM
                if trend == "bearish":
                    if -0.05 <= m <= 0.02:  # 5% OTM to ATM
                        scores.loc[idx] = 1.0
                    elif -0.10 <= m < -0.05 or 0.02 < m <= 0.05:  # Nearby
                        scores.loc[idx] = 0.7
                    else:
                        scores.loc[idx] = max(0, 1.0 - abs(m) * 5)
                else:
                    scores.loc[idx] = max(0, 0.5 - abs(m) * 3)

        return scores

    def _score_iv_rank(
        self,
        implied_vols: pd.Series,
        historical_vol: float,
    ) -> pd.Series:
        """
        Score based on IV relative to HV.

        Higher scores when IV < HV (cheaper options relative to realized vol).
        """
        if historical_vol == 0:
            return pd.Series(0.5, index=implied_vols.index)

        iv_ratio = implied_vols / historical_vol

        # Score: higher when IV is lower than HV (buying opportunity)
        # But not too low (illiquid or problematic)
        scores = pd.Series(0.0, index=implied_vols.index)

        for idx in iv_ratio.index:
            ratio = iv_ratio.loc[idx]
            if ratio < 0.7:  # IV much lower than HV
                scores.loc[idx] = 0.4  # Suspiciously low
            elif 0.7 <= ratio < 0.9:  # IV moderately lower
                scores.loc[idx] = 1.0  # Good buy
            elif 0.9 <= ratio <= 1.1:  # Fair value
                scores.loc[idx] = 0.7
            elif 1.1 < ratio <= 1.5:  # IV elevated
                scores.loc[idx] = 0.4
            else:  # IV very high
                scores.loc[idx] = 0.2  # Expensive

        return scores

    def _score_liquidity(
        self,
        volumes: pd.Series,
        open_interests: pd.Series,
    ) -> pd.Series:
        """
        Score based on volume and open interest.

        Higher scores for more liquid contracts.
        """
        # Normalize volume and OI
        max_vol = volumes.max() if volumes.max() > 0 else 1
        max_oi = open_interests.max() if open_interests.max() > 0 else 1

        vol_norm = volumes / max_vol
        oi_norm = open_interests / max_oi

        # Composite: 60% OI (stability), 40% volume (activity)
        scores = (0.6 * oi_norm + 0.4 * vol_norm).clip(0, 1)

        # Penalty for very low liquidity
        min_threshold = 0.1
        scores = scores.apply(lambda x: 0 if x < min_threshold else x)

        return scores

    def _score_delta(
        self,
        deltas: pd.Series,
        sides: pd.Series,
        trend: str,
    ) -> pd.Series:
        """
        Score based on delta alignment with trend.

        Higher deltas (more directional exposure) are better when trend is strong.
        """
        scores = pd.Series(0.5, index=deltas.index)

        for idx in deltas.index:
            delta = abs(deltas.loc[idx])
            side = sides.loc[idx]

            # For strong trends, prefer higher delta (more exposure)
            if trend == "bullish" and side == "call":
                scores.loc[idx] = min(1.0, delta + 0.3)
            elif trend == "bearish" and side == "put":
                scores.loc[idx] = min(1.0, delta + 0.3)
            else:
                # Neutral or counter-trend: moderate deltas
                scores.loc[idx] = 0.5 + (0.5 - abs(delta - 0.5))

        return scores

    def _score_theta(
        self,
        thetas: pd.Series,
        sides: pd.Series,
        expirations: pd.Series,
    ) -> pd.Series:
        """
        Score based on theta decay relative to time remaining.

        Higher scores for favorable theta (less decay for buyers).
        """
        scores = pd.Series(0.5, index=thetas.index)

        for idx in thetas.index:
            theta = thetas.loc[idx]
            expiration = pd.to_datetime(expirations.loc[idx], unit="s")
            days_to_expiry = (expiration - datetime.now()).days

            # Buyers (long options): prefer lower theta decay
            # Normalize theta (usually negative for buyers)
            theta_per_day = abs(theta)

            if days_to_expiry > 45:
                # More time: theta less critical
                scores.loc[idx] = 0.7
            elif days_to_expiry > 21:
                # Moderate time: theta matters
                scores.loc[idx] = max(0.3, 1.0 - theta_per_day * 10)
            else:
                # Near expiry: theta critical
                scores.loc[idx] = max(0.1, 1.0 - theta_per_day * 20)

        return scores

    def _score_momentum(
        self,
        trend: str,
        sides: pd.Series,
    ) -> pd.Series:
        """
        Score based on trend/momentum alignment.

        Higher scores when option side aligns with underlying momentum.
        """
        scores = pd.Series(0.5, index=sides.index)

        for idx in sides.index:
            side = sides.loc[idx]

            if trend == "bullish" and side == "call":
                scores.loc[idx] = 1.0
            elif trend == "bearish" and side == "put":
                scores.loc[idx] = 1.0
            elif trend == "neutral":
                scores.loc[idx] = 0.5
            else:
                # Counter-trend
                scores.loc[idx] = 0.2

        return scores
