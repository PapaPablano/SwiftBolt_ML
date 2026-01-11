"""
Enhanced Options Ranker with ML-derived trend analysis.

Integrates SuperTrend AI and multi-indicator signals for
improved options contract ranking.

Phase 6 implementation from technicals_and_ml_improvement.md

Phase 7 (P0 Modules):
- Probability of Profit (PoP) + Risk/Reward scoring
- Earnings IV expansion/crush detection
- Extrinsic/Intrinsic value analysis
- Put-Call Ratio sentiment analysis
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from .options_ranker import OptionsRanker
from .pop_calculator import ProbabilityOfProfitCalculator
from .earnings_analyzer import EarningsIVAnalyzer
from .extrinsic_calculator import ExtrinsicIntrinsicCalculator
from .pcr_analyzer import PutCallRatioAnalyzer
from ..features.technical_indicators import add_all_technical_features
from ..strategies.supertrend_ai import SuperTrendAI
from ..strategies.multi_indicator_signals import MultiIndicatorSignalGenerator

logger = logging.getLogger(__name__)


class EnhancedOptionsRanker(OptionsRanker):
    """
    Enhanced options ranker with ML-derived trend analysis.

    Extends base OptionsRanker with:
    - SuperTrend AI signal integration
    - Multi-indicator composite signals
    - Trend strength weighting
    - Volatility regime detection

    Phase 7 P0 Modules (captures additional 5-8% alpha):
    - Probability of Profit (PoP) + Risk/Reward
    - Earnings IV expansion/crush detection
    - Extrinsic/Intrinsic value analysis
    - Put-Call Ratio sentiment (contrarian signals)
    """

    def __init__(self):
        """Initialize enhanced ranker with P0 module calculators."""
        super().__init__()

        # Initialize P0 module calculators
        self.pop_calc = ProbabilityOfProfitCalculator()
        self.earnings_analyzer = EarningsIVAnalyzer()
        self.extrinsic_calc = ExtrinsicIntrinsicCalculator()
        self.pcr_analyzer = PutCallRatioAnalyzer()

        # Optimized weights: 61.4% base + 38.6% P0 modules
        # Reduced redundant scores (moneyness/delta captured by PoP, IV by Earnings)
        # Boosted high-predictive signals (SuperTrend, Trend Strength)
        self.weights = {
            # Base scores (61.4% total)
            "moneyness": 0.085,
            "iv_rank": 0.066,
            "liquidity": 0.104,
            "delta_score": 0.047,
            "theta_decay": 0.066,
            "momentum": 0.057,
            "trend_strength": 0.085,
            "supertrend": 0.104,
            # P0 module scores (38.6% total)
            "pop_rr": 0.113,
            "earnings_iv": 0.094,
            "extrinsic": 0.094,
            "pcr": 0.075,
        }

    def rank_options_with_trend(
        self,
        options_df: pd.DataFrame,
        underlying_price: float,
        trend_analysis: dict,
        historical_vol: float = 0.30,
    ) -> pd.DataFrame:
        """
        Rank options using comprehensive trend analysis.

        Args:
            options_df: Options chain DataFrame
            underlying_price: Current underlying price
            trend_analysis: Dict from MultiIndicatorSignalGenerator
                Expected keys:
                - trend: 'bullish', 'bearish', 'neutral'
                - signal_strength: 0-10
                - supertrend_factor: float
                - supertrend_performance: float
                - indicator_signals: dict of individual signals
            historical_vol: Historical volatility

        Returns:
            Ranked options DataFrame with ml_score
        """
        if options_df.empty:
            logger.warning("No options data to rank")
            return options_df

        df = options_df.copy()

        # Extract trend info
        trend = trend_analysis.get("trend", "neutral")
        signal_strength = trend_analysis.get("signal_strength", 5.0)
        supertrend_factor = trend_analysis.get("supertrend_factor", 3.0)
        supertrend_perf = trend_analysis.get("supertrend_performance", 0.0)

        # Calculate base scores
        df["moneyness_score"] = self._score_moneyness(
            df["strike"], df["side"], underlying_price, trend
        )
        df["iv_rank_score"] = self._score_iv_rank(df["impliedVolatility"], historical_vol)
        df["liquidity_score"] = self._score_liquidity(df["volume"], df["openInterest"])
        df["delta_score"] = self._score_delta(df["delta"], df["side"], trend)
        df["theta_decay_score"] = self._score_theta(df["theta"], df["side"], df["expiration"])
        df["momentum_score"] = self._score_momentum(trend, df["side"])

        # Enhanced scores
        df["trend_strength_score"] = self._score_trend_strength(signal_strength, df["side"], trend)
        df["supertrend_score"] = self._score_supertrend(
            supertrend_factor, supertrend_perf, df["side"], trend
        )

        # P0 Module scores (Phase 7)
        earnings_date = trend_analysis.get("earnings_date")
        df["pop_rr_score"] = self._score_pop_and_rr(df, underlying_price)
        df["earnings_iv_score"] = self._score_earnings_iv(df, historical_vol, earnings_date)
        df["extrinsic_score"] = self._score_extrinsic_richness(df, underlying_price, historical_vol)
        df["pcr_score"] = self._score_pcr_sentiment(df)

        # Weighted composite score
        df["ml_score"] = 0.0
        for component, weight in self.weights.items():
            score_col = f"{component}_score"
            if score_col in df.columns:
                df["ml_score"] += df[score_col] * weight

        # Normalize to 0-1 range
        if df["ml_score"].max() > 0:
            df["ml_score"] = df["ml_score"] / df["ml_score"].max()

        df["ml_score"] = df["ml_score"].clip(0, 1)

        # Add trend metadata
        df["trend"] = trend
        df["trend_strength"] = signal_strength
        df["supertrend_factor"] = supertrend_factor

        # Sort by score
        df = df.sort_values("ml_score", ascending=False)
        df = df.reset_index(drop=True)

        logger.info(f"Enhanced ranking: {len(df)} contracts")
        logger.info(f"Trend: {trend}, Strength: {signal_strength:.1f}/10")
        logger.info(f"Score range: {df['ml_score'].min():.3f} - " f"{df['ml_score'].max():.3f}")

        return df

    def _score_trend_strength(
        self,
        signal_strength: float,
        sides: pd.Series,
        trend: str,
    ) -> pd.Series:
        """
        Score based on trend strength alignment.

        Strong trends favor directional options.
        Weak trends favor neutral strategies.
        """
        # Normalize strength to 0-1
        strength_norm = signal_strength / 10.0

        scores = pd.Series(0.5, index=sides.index)

        for idx in sides.index:
            side = sides.loc[idx]

            if trend == "bullish" and side == "call":
                # Strong bullish = high score for calls
                scores.loc[idx] = 0.5 + (strength_norm * 0.5)
            elif trend == "bearish" and side == "put":
                # Strong bearish = high score for puts
                scores.loc[idx] = 0.5 + (strength_norm * 0.5)
            elif trend == "neutral":
                # Neutral trend = moderate scores for both
                scores.loc[idx] = 0.5
            else:
                # Counter-trend: penalize based on strength
                scores.loc[idx] = max(0.1, 0.5 - (strength_norm * 0.4))

        return scores

    def _score_supertrend(
        self,
        factor: float,
        performance: float,
        sides: pd.Series,
        trend: str,
    ) -> pd.Series:
        """
        Score based on SuperTrend AI signals.

        Higher performance index = more reliable signal.
        Optimal factor (2.5-3.5) = balanced signal.
        """
        scores = pd.Series(0.5, index=sides.index)

        # Performance bonus (0-1 range)
        perf_bonus = min(1.0, max(0.0, performance))

        # Factor quality (optimal around 3.0)
        factor_quality = 1.0 - abs(factor - 3.0) / 3.0
        factor_quality = max(0.3, factor_quality)

        for idx in sides.index:
            side = sides.loc[idx]

            base_score = 0.5

            # Trend alignment
            if trend == "bullish" and side == "call":
                base_score = 0.7
            elif trend == "bearish" and side == "put":
                base_score = 0.7
            elif trend == "neutral":
                base_score = 0.5
            else:
                base_score = 0.3

            # Apply performance and factor quality
            final_score = base_score * (0.5 + 0.25 * perf_bonus)
            final_score *= 0.5 + 0.5 * factor_quality

            scores.loc[idx] = min(1.0, final_score)

        return scores

    # =========================================================================
    # P0 MODULE SCORING METHODS (Phase 7)
    # =========================================================================

    def _score_pop_and_rr(
        self,
        options_df: pd.DataFrame,
        underlying_price: float,
    ) -> pd.Series:
        """
        Score options based on Probability of Profit and Risk/Reward ratio.

        High PoP + favorable R/R = high score.
        """
        scores = []
        for idx, row in options_df.iterrows():
            try:
                pop_data = self.pop_calc.calculate_pop(
                    underlying_price=underlying_price,
                    strike=row["strike"],
                    side=row["side"],
                    bid=row.get("bid", 0),
                    ask=row.get("ask", 0),
                    delta=row.get("delta", 0.5),
                )
                rr_data = self.pop_calc.calculate_risk_reward_ratio(
                    strike=row["strike"],
                    underlying_price=underlying_price,
                    bid=row.get("bid", 0),
                    ask=row.get("ask", 0),
                    side=row["side"],
                )
                score = self.pop_calc.score_pop_and_rr(pop_data, rr_data)
                scores.append(score)
            except Exception as e:
                logger.debug(f"PoP scoring error for {idx}: {e}")
                scores.append(0.5)

        return pd.Series(scores, index=options_df.index)

    def _score_earnings_iv(
        self,
        options_df: pd.DataFrame,
        historical_vol: float,
        earnings_date: str = None,
    ) -> pd.Series:
        """
        Score options based on earnings IV expansion/crush opportunity.

        Detects IV regime and scores based on strategy alignment.
        """
        scores = []

        # Default earnings date if not provided (45 days out)
        if earnings_date is None:
            from datetime import timedelta

            earnings_date = (datetime.today() + timedelta(days=45)).strftime("%Y-%m-%d")

        for idx, row in options_df.iterrows():
            try:
                # Calculate days to earnings and expiry
                earnings_dt = datetime.strptime(earnings_date, "%Y-%m-%d")
                days_to_earnings = (earnings_dt - datetime.today()).days

                # Handle expiration - could be string or timestamp
                exp = row.get("expiration")
                if isinstance(exp, str):
                    exp_dt = datetime.strptime(exp, "%Y-%m-%d")
                else:
                    exp_dt = datetime.fromtimestamp(exp)
                days_to_expiry = (exp_dt - datetime.today()).days

                earnings_data = self.earnings_analyzer.calculate_earnings_impact_on_iv(
                    current_iv=row.get("impliedVolatility", 0.30),
                    historical_iv=historical_vol,
                    days_to_earnings=days_to_earnings,
                    days_to_expiry=max(1, days_to_expiry),
                )
                score = self.earnings_analyzer.score_earnings_strategy(
                    earnings_data,
                    side=row["side"],
                    expiration=str(exp),
                    underlying_price=row.get("underlyingPrice", 0),
                    strike=row["strike"],
                    strategy_type="auto",
                )
                scores.append(score)
            except Exception as e:
                logger.debug(f"Earnings IV scoring error for {idx}: {e}")
                scores.append(0.7)

        return pd.Series(scores, index=options_df.index)

    def _score_extrinsic_richness(
        self,
        options_df: pd.DataFrame,
        underlying_price: float,
        historical_vol: float,
    ) -> pd.Series:
        """
        Score options based on extrinsic/intrinsic value decomposition.

        Identifies time value rich vs intrinsic rich options.
        """
        scores = []

        for idx, row in options_df.iterrows():
            try:
                # Calculate days to expiry
                exp = row.get("expiration")
                if isinstance(exp, str):
                    exp_dt = datetime.strptime(exp, "%Y-%m-%d")
                else:
                    exp_dt = datetime.fromtimestamp(exp)
                days_to_expiry = max(1, (exp_dt - datetime.today()).days)

                ext_data = self.extrinsic_calc.calculate_extrinsic_intrinsic_ratio(
                    strike=row["strike"],
                    underlying_price=underlying_price,
                    side=row["side"],
                    bid=row.get("bid", 0),
                    ask=row.get("ask", 0),
                    days_to_expiry=days_to_expiry,
                )
                score = self.extrinsic_calc.score_extrinsic_richness(
                    ext_data,
                    implied_vol=row.get("impliedVolatility", 0.30),
                    historical_vol=historical_vol,
                    strategy_type="auto",
                )
                scores.append(score)
            except Exception as e:
                logger.debug(f"Extrinsic scoring error for {idx}: {e}")
                scores.append(0.7)

        return pd.Series(scores, index=options_df.index)

    def _score_pcr_sentiment(
        self,
        options_df: pd.DataFrame,
    ) -> pd.Series:
        """
        Score options based on Put-Call Ratio sentiment analysis.

        Uses contrarian signals: high PCR = bullish for calls.
        """
        try:
            pcr_data = self.pcr_analyzer.analyze_put_call_ratio(options_df)
        except Exception as e:
            logger.debug(f"PCR analysis error: {e}")
            return pd.Series(0.7, index=options_df.index)

        scores = []
        for idx, row in options_df.iterrows():
            try:
                score = self.pcr_analyzer.score_pcr_opportunity(
                    pcr_data, side=row["side"], use_contrarian=True
                )
                scores.append(score)
            except Exception as e:
                logger.debug(f"PCR scoring error for {idx}: {e}")
                scores.append(0.7)

        return pd.Series(scores, index=options_df.index)

    def get_top_recommendations(
        self,
        ranked_df: pd.DataFrame,
        n_calls: int = 3,
        n_puts: int = 3,
    ) -> dict:
        """
        Get top recommended options for each side.

        Returns:
            Dict with 'calls' and 'puts' DataFrames
        """
        calls = ranked_df[ranked_df["side"] == "call"].head(n_calls)
        puts = ranked_df[ranked_df["side"] == "put"].head(n_puts)

        return {
            "calls": calls,
            "puts": puts,
            "top_call": calls.iloc[0] if len(calls) > 0 else None,
            "top_put": puts.iloc[0] if len(puts) > 0 else None,
        }

    def generate_ranking_summary(
        self,
        ranked_df: pd.DataFrame,
        trend_analysis: dict,
    ) -> str:
        """Generate human-readable ranking summary."""
        trend = trend_analysis.get("trend", "neutral")
        strength = trend_analysis.get("signal_strength", 5.0)

        recs = self.get_top_recommendations(ranked_df)

        lines = [
            "=" * 50,
            "OPTIONS RANKING SUMMARY",
            "=" * 50,
            f"Trend: {trend.upper()} (Strength: {strength:.1f}/10)",
            f"Total contracts analyzed: {len(ranked_df)}",
            "",
        ]

        if recs["top_call"] is not None:
            tc = recs["top_call"]
            lines.extend(
                [
                    "📈 TOP CALL:",
                    f"   Strike: ${tc['strike']:.2f}",
                    f"   Expiry: {tc['expiration']}",
                    f"   Score: {tc['ml_score']:.3f}",
                    f"   Delta: {tc['delta']:.3f}",
                    "",
                ]
            )

        if recs["top_put"] is not None:
            tp = recs["top_put"]
            lines.extend(
                [
                    "📉 TOP PUT:",
                    f"   Strike: ${tp['strike']:.2f}",
                    f"   Expiry: {tp['expiration']}",
                    f"   Score: {tp['ml_score']:.3f}",
                    f"   Delta: {tp['delta']:.3f}",
                ]
            )

        return "\n".join(lines)

    def rank_options_with_indicators(
        self,
        options_df: pd.DataFrame,
        underlying_df: pd.DataFrame,
        underlying_price: float,
        historical_vol: float = 0.30,
    ) -> pd.DataFrame:
        """
        Rank options using full technical indicator analysis.

        This is the main entry point for Phase 6 integration. It:
        1. Computes all technical indicators on the underlying OHLC data
        2. Runs SuperTrend AI to get adaptive trend signals
        3. Generates multi-indicator composite signals
        4. Ranks options based on comprehensive trend analysis

        Args:
            options_df: Options chain DataFrame with columns:
                strike, side, expiration, delta, gamma, theta, vega,
                impliedVolatility, volume, openInterest, bid, ask
            underlying_df: OHLC DataFrame with columns:
                ts, open, high, low, close, volume
            underlying_price: Current underlying price
            historical_vol: Historical volatility (annualized)

        Returns:
            Ranked options DataFrame with ml_score and trend metadata
        """
        if options_df.empty:
            logger.warning("No options data to rank")
            return options_df

        if underlying_df.empty or len(underlying_df) < 50:
            logger.warning(
                f"Insufficient OHLC data ({len(underlying_df)} bars), "
                "falling back to basic ranking"
            )
            return self.rank_options(options_df, underlying_price, "neutral", historical_vol)

        # Step 1: Add all technical indicators to OHLC data
        logger.info("Computing technical indicators...")
        df_with_indicators = add_all_technical_features(underlying_df)

        # Step 2: Run SuperTrend AI
        supertrend_info: Dict[str, Any] = {}
        try:
            supertrend = SuperTrendAI(df_with_indicators)
            df_with_indicators, supertrend_info = supertrend.calculate()
            logger.info(
                f"SuperTrend: factor={supertrend_info.get('target_factor', 0):.2f}, "
                f"perf={supertrend_info.get('performance_index', 0):.3f}"
            )
        except Exception as e:
            logger.warning(f"SuperTrend AI failed: {e}, using defaults")
            supertrend_info = {
                "target_factor": 3.0,
                "performance_index": 0.5,
                "signal_strength": 5,
            }

        # Step 3: Generate multi-indicator signals
        signal_generator = MultiIndicatorSignalGenerator()
        trend_analysis = signal_generator.get_trend_analysis(df_with_indicators)

        # Step 4: Combine SuperTrend info with trend analysis
        combined_analysis = {
            "trend": trend_analysis.get("trend", "neutral"),
            "signal_strength": supertrend_info.get("signal_strength", 5),
            "supertrend_factor": supertrend_info.get("target_factor", 3.0),
            "supertrend_performance": supertrend_info.get("performance_index", 0.5),
            "composite_signal": trend_analysis.get("composite_signal", 0.0),
            "confidence": trend_analysis.get("confidence", 0.5),
            "adx": trend_analysis.get("adx", 20.0),
            "rsi": trend_analysis.get("rsi", 50.0),
            "supertrend_signal": trend_analysis.get("supertrend_signal", 0),
        }

        logger.info(
            f"Trend analysis: {combined_analysis['trend']} "
            f"(confidence={combined_analysis['confidence']:.2f}, "
            f"ADX={combined_analysis['adx']:.1f})"
        )

        # Step 5: Rank options with enhanced trend analysis
        return self.rank_options_with_trend(
            options_df,
            underlying_price,
            combined_analysis,
            historical_vol,
        )

    def analyze_underlying(
        self,
        underlying_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Analyze underlying price data and return trend analysis.

        Useful for getting trend info without ranking options.

        Args:
            underlying_df: OHLC DataFrame

        Returns:
            Dict with trend analysis including:
            - trend: 'bullish', 'bearish', 'neutral'
            - signal_strength: 0-10
            - supertrend_factor: optimal ATR multiplier
            - supertrend_performance: 0-1 performance index
            - confidence: 0-1 confidence score
            - indicators: dict of individual indicator values
        """
        if underlying_df.empty or len(underlying_df) < 50:
            return {
                "trend": "neutral",
                "signal_strength": 5,
                "supertrend_factor": 3.0,
                "supertrend_performance": 0.5,
                "confidence": 0.0,
                "indicators": {},
            }

        # Add technical indicators
        df_with_indicators = add_all_technical_features(underlying_df)

        # Run SuperTrend AI
        supertrend_info: Dict[str, Any] = {}
        try:
            supertrend = SuperTrendAI(df_with_indicators)
            df_with_indicators, supertrend_info = supertrend.calculate()
        except Exception as e:
            logger.warning(f"SuperTrend AI failed: {e}")
            supertrend_info = {
                "target_factor": 3.0,
                "performance_index": 0.5,
                "signal_strength": 5,
            }

        # Generate multi-indicator signals
        signal_generator = MultiIndicatorSignalGenerator()
        trend_analysis = signal_generator.get_trend_analysis(df_with_indicators)

        # Get latest indicator values
        latest = df_with_indicators.iloc[-1]
        indicators = {
            "rsi_14": float(latest.get("rsi_14", 50)),
            "macd_hist": float(latest.get("macd_hist", 0)),
            "adx": float(latest.get("adx", 20)),
            "plus_di": float(latest.get("plus_di", 50)),
            "minus_di": float(latest.get("minus_di", 50)),
            "kdj_j": float(latest.get("kdj_j", 50)),
            "mfi": float(latest.get("mfi", 50)),
            "stoch_k": float(latest.get("stoch_k", 50)),
            "supertrend_trend": int(latest.get("supertrend_trend", 0)),
        }

        return {
            "trend": trend_analysis.get("trend", "neutral"),
            "signal_strength": supertrend_info.get("signal_strength", 5),
            "supertrend_factor": supertrend_info.get("target_factor", 3.0),
            "supertrend_performance": supertrend_info.get("performance_index", 0.5),
            "confidence": trend_analysis.get("confidence", 0.5),
            "composite_signal": trend_analysis.get("composite_signal", 0.0),
            "indicators": indicators,
        }
