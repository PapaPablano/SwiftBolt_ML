"""
Validation Service

Connects real-time metrics from database to UnifiedValidator,
producing reconciled confidence scores with drift detection.

Usage:
    ```python
    service = ValidationService()
    result = await service.get_live_validation("AAPL", "BULLISH")
    print(f"Unified Confidence: {result.unified_confidence:.1%}")
    print(f"Drift Severity: {result.drift_severity}")
    ```
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.data.supabase_db import SupabaseDatabase
from src.validation import UnifiedValidator, ValidationScores, UnifiedPrediction

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Routes real-time metrics to UnifiedValidator.
    
    Fetches component scores from database and produces unified predictions.
    """

    def __init__(self, db: Optional[SupabaseDatabase] = None):
        """
        Initialize validation service.
        
        Args:
            db: Optional database connection. Creates new if not provided.
        """
        self.validator = UnifiedValidator()
        self.db = db or SupabaseDatabase()
        logger.info("ValidationService initialized")

    async def get_live_validation(
        self, symbol: str, direction: str
    ) -> UnifiedPrediction:
        """
        Get reconciled validation for a symbol.
        
        Fetches component scores from:
        1. Backtesting score from ml_model_metrics (3-month window)
        2. Walk-forward score from rolling_evaluation (quarterly rolling)
        3. Live score from live_predictions (last 30 predictions)
        4. Multi-TF scores from indicator_values (current M15, H1, H4, D1, W1)
        
        Args:
            symbol: Trading symbol (e.g., "AAPL")
            direction: Prediction direction ("BULLISH", "BEARISH", "NEUTRAL")
        
        Returns:
            UnifiedPrediction with reconciled confidence and drift analysis
        
        Raises:
            ValueError: If symbol not found or insufficient data
        """
        try:
            logger.debug(f"Fetching validation for {symbol} ({direction})")
            
            # Fetch component scores in parallel for efficiency
            backtest_score = await self._get_backtesting_score(symbol)
            walkforward_score = await self._get_walkforward_score(symbol)
            live_score = await self._get_live_score(symbol)
            multi_tf_scores = await self._get_multi_tf_scores(symbol)
            
            logger.debug(
                f"Scores fetched - BT: {backtest_score:.1%}, "
                f"WF: {walkforward_score:.1%}, Live: {live_score:.1%}"
            )
            
            # Create scores object
            scores = ValidationScores(
                backtesting_score=backtest_score,
                walkforward_score=walkforward_score,
                live_score=live_score,
                multi_tf_scores=multi_tf_scores,
                timestamp=datetime.now(),
            )
            
            # Validate using UnifiedValidator
            result = self.validator.validate(symbol, direction, scores)
            
            # Store result for dashboard retrieval
            await self._store_validation_result(symbol, result)
            
            logger.info(
                f"Validation complete for {symbol}: "
                f"confidence={result.unified_confidence:.1%}, "
                f"drift={result.drift_detected}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Validation failed for {symbol}: {e}", exc_info=True)
            raise

    async def _get_backtesting_score(self, symbol: str) -> float:
        """
        Fetch 3-month historical accuracy from backtesting.
        
        Queries model_validation_stats for symbol with:
        - Time window: 90 days (3 months)
        - Metric: accuracy
        - Validation type: backtest
        - Aggregation: mean of all runs in window
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Accuracy score 0-1. Defaults to 0.55 if no data.
        """
        try:
            three_months_ago = datetime.now() - timedelta(days=90)
            
            # First get symbol_id
            symbol_result = (
                self.db.client.table("symbols")
                .select("id")
                .eq("ticker", symbol)
                .execute()
            )
            
            if not symbol_result.data:
                logger.warning(f"Symbol {symbol} not found in database")
                return 0.55
            
            symbol_id = symbol_result.data[0]["id"]
            
            # Query model_validation_stats
            result = (
                self.db.client.table("model_validation_stats")
                .select("accuracy")
                .eq("symbol_id", symbol_id)
                .eq("validation_type", "backtest")
                .gte("created_at", three_months_ago.isoformat())
                .execute()
            )
            
            if not result.data:
                logger.warning(f"No backtesting metrics for {symbol}")
                return 0.55  # Conservative default
            
            # Calculate mean accuracy
            accuracies = [row["accuracy"] for row in result.data if row["accuracy"] is not None]
            if not accuracies:
                return 0.55
            
            score = float(sum(accuracies) / len(accuracies))
            logger.debug(f"{symbol} backtesting score: {score:.1%}")
            return score
            
        except Exception as e:
            logger.warning(f"Error fetching backtesting score for {symbol}: {e}")
            return 0.55

    async def _get_walkforward_score(self, symbol: str) -> float:
        """
        Fetch quarterly rolling accuracy from walk-forward validation.
        
        Queries model_validation_stats for symbol with:
        - Time window: 13 weeks (quarterly rolling)
        - Validation type: walkforward
        - Metric: mean accuracy across rolling windows
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Walk-forward accuracy score 0-1. Defaults to 0.60 if no data.
        """
        try:
            thirteen_weeks_ago = datetime.now() - timedelta(weeks=13)
            
            # First get symbol_id
            symbol_result = (
                self.db.client.table("symbols")
                .select("id")
                .eq("ticker", symbol)
                .execute()
            )
            
            if not symbol_result.data:
                logger.warning(f"Symbol {symbol} not found in database")
                return 0.60
            
            symbol_id = symbol_result.data[0]["id"]
            
            # Query model_validation_stats
            result = (
                self.db.client.table("model_validation_stats")
                .select("accuracy")
                .eq("symbol_id", symbol_id)
                .eq("validation_type", "walkforward")
                .gte("created_at", thirteen_weeks_ago.isoformat())
                .execute()
            )
            
            if not result.data:
                logger.warning(f"No walk-forward metrics for {symbol}")
                return 0.60  # Conservative default
            
            # Calculate mean accuracy across rolling windows
            accuracies = [row["accuracy"] for row in result.data if row["accuracy"] is not None]
            if not accuracies:
                return 0.60
            
            score = float(sum(accuracies) / len(accuracies))
            logger.debug(f"{symbol} walk-forward score: {score:.1%}")
            return score
            
        except Exception as e:
            logger.warning(f"Error fetching walk-forward score for {symbol}: {e}")
            return 0.60

    async def _get_live_score(self, symbol: str) -> float:
        """
        Fetch current accuracy from live predictions.
        
        Calculates mean accuracy score across all timeframes from last 30 predictions:
        1. Query live_predictions for symbol (last 30 per timeframe)
        2. Use accuracy_score field directly
        3. Return mean accuracy across timeframes
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Live prediction accuracy 0-1. Defaults to 0.50 if insufficient data.
        """
        try:
            # First get symbol_id
            symbol_result = (
                self.db.client.table("symbols")
                .select("id")
                .eq("ticker", symbol)
                .execute()
            )
            
            if not symbol_result.data:
                logger.warning(f"Symbol {symbol} not found in database")
                return 0.50
            
            symbol_id = symbol_result.data[0]["id"]
            
            # Fetch recent live predictions (across all timeframes)
            result = (
                self.db.client.table("live_predictions")
                .select("accuracy_score, timeframe")
                .eq("symbol_id", symbol_id)
                .order("prediction_time", desc=True)
                .limit(50)  # Get more to account for multiple timeframes
                .execute()
            )
            
            if not result.data or len(result.data) < 5:
                logger.warning(f"Insufficient live data for {symbol} (got {len(result.data or [])} predictions)")
                return 0.50  # Conservative default
            
            # Calculate mean accuracy across predictions
            accuracy_scores = [
                float(row["accuracy_score"]) 
                for row in result.data 
                if row.get("accuracy_score") is not None
            ]
            
            if not accuracy_scores:
                return 0.50
            
            accuracy = sum(accuracy_scores) / len(accuracy_scores)
            
            logger.debug(
                f"{symbol} live score: {accuracy:.1%} (mean of {len(accuracy_scores)} predictions)"
            )
            return accuracy
            
        except Exception as e:
            logger.warning(f"Error fetching live score for {symbol}: {e}")
            return 0.50

    async def _get_multi_tf_scores(self, symbol: str) -> Dict[str, float]:
        """
        Fetch current multi-timeframe prediction scores.
        
        Gets raw prediction scores for symbol across timeframes:
        - M15: 15-minute
        - H1: 1-hour
        - H4: 4-hour
        - D1: 1-day
        - W1: 1-week
        
        Scores range from -1 (bearish) to +1 (bullish).
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Dict mapping timeframe to raw score. Example:
            {"M15": -0.48, "H1": -0.40, "H4": -0.35, "D1": 0.60, "W1": 0.70}
        """
        try:
            timeframes = ["M15", "H1", "H4", "D1", "W1"]
            multi_tf_scores = {}
            
            for tf in timeframes:
                try:
                    # Query most recent indicator value for this timeframe
                    result = (
                        self.db.client.table("indicator_values")
                        .select("prediction_score")
                        .eq("symbol", symbol)
                        .eq("timeframe", tf)
                        .order("calculated_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                    
                    if result.data:
                        score = result.data[0].get("prediction_score", 0.0)
                        multi_tf_scores[tf] = score
                        logger.debug(f"{symbol} {tf} score: {score:.2f}")
                    else:
                        # No data for this timeframe, use neutral
                        multi_tf_scores[tf] = 0.0
                        logger.debug(f"{symbol} {tf}: no data (using 0.0)")
                        
                except Exception as e:
                    logger.warning(f"Error fetching {tf} score for {symbol}: {e}")
                    multi_tf_scores[tf] = 0.0  # Neutral default
            
            logger.debug(f"{symbol} multi-TF scores: {multi_tf_scores}")
            return multi_tf_scores
            
        except Exception as e:
            logger.warning(f"Error fetching multi-TF scores for {symbol}: {e}")
            return {tf: 0.0 for tf in ["M15", "H1", "H4", "D1", "W1"]}

    async def _store_validation_result(
        self, symbol: str, result: UnifiedPrediction
    ) -> None:
        """
        Store unified validation result in database.
        
        Inserts into validation_results table for dashboard retrieval
        and historical tracking.
        
        Args:
            symbol: Trading symbol
            result: UnifiedPrediction object
        """
        try:
            # Get symbol_id
            symbol_result = (
                self.db.client.table("symbols")
                .select("id")
                .eq("ticker", symbol)
                .execute()
            )
            
            if not symbol_result.data:
                logger.warning(f"Symbol {symbol} not found, skipping validation storage")
                return
            
            symbol_id = symbol_result.data[0]["id"]
            
            # Convert result to storable format
            data = {
                "symbol_id": symbol_id,
                "symbol": symbol,
                "direction": result.direction,
                "unified_confidence": float(result.unified_confidence),
                "backtesting_score": float(result.backtesting_score),
                "walkforward_score": float(result.walkforward_score),
                "live_score": float(result.live_score),
                "drift_detected": result.drift_detected,
                "drift_magnitude": float(result.drift_magnitude),
                "drift_severity": result.drift_severity,
                "drift_explanation": result.drift_explanation,
                "timeframe_conflict": result.timeframe_conflict,
                "consensus_direction": result.consensus_direction,
                "conflict_explanation": result.conflict_explanation,
                "recommendation": result.recommendation,
                "retraining_trigger": result.retraining_trigger,
                "retraining_reason": result.retraining_reason or "",
                "created_at": datetime.now().isoformat(),
            }
            
            # Insert into database
            self.db.client.table("validation_results").insert(data).execute()
            
            logger.debug(f"Stored validation result for {symbol}")
            
        except Exception as e:
            logger.error(f"Error storing validation result for {symbol}: {e}")
            # Don't raise - validation already computed successfully


async def get_live_validation(
    symbol: str, direction: str, db: Optional[SupabaseDatabase] = None
) -> UnifiedPrediction:
    """
    Convenience function to get unified validation.
    
    Args:
        symbol: Trading symbol
        direction: Prediction direction ("BULLISH", "BEARISH", "NEUTRAL")
        db: Optional database connection
    
    Returns:
        UnifiedPrediction with reconciled confidence
    """
    service = ValidationService(db)
    return await service.get_live_validation(symbol, direction)


if __name__ == "__main__":
    import asyncio
    
    # Example usage
    async def main():
        service = ValidationService()
        
        # Get validation for AAPL bullish signal
        result = await service.get_live_validation("AAPL", "BULLISH")
        
        print(f"\nValidation Result for AAPL (BULLISH)")
        print(f"Unified Confidence: {result.unified_confidence:.1%}")
        print(f"Drift Detected: {result.drift_detected}")
        print(f"Drift Severity: {result.drift_severity}")
        print(f"Recommendation: {result.recommendation}")
        print(f"Retraining Trigger: {result.retraining_trigger}")
    
    asyncio.run(main())
