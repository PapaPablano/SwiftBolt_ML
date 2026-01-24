"""
Validation API Endpoints

Exposes unified validation metrics through REST API.
Used by dashboard to fetch reconciled confidence scores.

Endpoints:
    GET /api/validation/unified/{symbol}/{direction}
    GET /api/validation/history/{symbol}
    GET /api/validation/drift-alerts
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.services.validation_service import ValidationService
from src.validation import UnifiedPrediction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/validation", tags=["validation"])
validation_service = ValidationService()


class ValidationResponse(dict):
    """
    Standardized API response for validation results.
    
    Example:
    {
        "symbol": "AAPL",
        "direction": "BULLISH",
        "unified_confidence": 0.581,
        "status": "CAUTION",
        "components": {
            "backtesting_score": 0.988,
            "walkforward_score": 0.780,
            "live_score": 0.400
        },
        "drift": {
            "detected": true,
            "magnitude": 0.580,
            "severity": "severe",
            "explanation": "Live score (40.0%) is 58.0% lower than backtesting (98.8%)..."
        },
        "multi_tf": {
            "consensus": "BULLISH",
            "conflict": true,
            "explanation": "Weak consensus (26.4% margin)...",
            "breakdown": {"M15": -0.48, "H1": -0.40, "D1": 0.60, "W1": 0.70}
        },
        "recommendation": "Moderate confidence - trade with normal risk",
        "retraining": {
            "trigger": false,
            "reason": "Model within acceptable drift range",
            "next_date": "2026-02-20T10:40:00"
        },
        "timestamp": "2026-01-21T10:40:00"
    }
    """

    @staticmethod
    def from_prediction(prediction: UnifiedPrediction) -> Dict:
        """
        Convert UnifiedPrediction to API response format.
        
        Args:
            prediction: UnifiedPrediction object
        
        Returns:
            Dictionary with structured validation response
        """
        # Determine status emoji and text
        if prediction.unified_confidence >= 0.75:
            status = "HIGH_CONFIDENCE"
        elif prediction.unified_confidence >= 0.60:
            status = "MODERATE_CONFIDENCE"
        elif prediction.unified_confidence >= 0.45:
            status = "LOW_CONFIDENCE"
        elif prediction.unified_confidence >= 0.30:
            status = "VERY_LOW_CONFIDENCE"
        else:
            status = "INSUFFICIENT_CONFIDENCE"
        
        return {
            "symbol": prediction.symbol,
            "direction": prediction.direction,
            "unified_confidence": round(prediction.unified_confidence, 4),
            "status": status,
            "components": {
                "backtesting_score": round(prediction.backtesting_score, 4),
                "walkforward_score": round(prediction.walkforward_score, 4),
                "live_score": round(prediction.live_score, 4),
            },
            "drift": {
                "detected": prediction.drift_detected,
                "magnitude": round(prediction.drift_magnitude, 4),
                "severity": prediction.drift_severity,
                "explanation": prediction.drift_explanation,
            },
            "multi_tf": {
                "consensus": prediction.consensus_direction,
                "conflict": prediction.timeframe_conflict,
                "explanation": prediction.conflict_explanation,
                "breakdown": prediction.multi_tf_consensus,
            },
            "recommendation": prediction.recommendation,
            "adjustments": prediction.adjustments,
            "retraining": {
                "trigger": prediction.retraining_trigger,
                "reason": prediction.retraining_reason,
                "next_date": (
                    prediction.next_retraining_date.isoformat()
                    if prediction.next_retraining_date
                    else None
                ),
            },
            "timestamp": prediction.timestamp.isoformat(),
        }


@router.get("/unified/{symbol}/{direction}")
async def get_unified_validation(
    symbol: str,
    direction: str,
) -> Dict:
    """
    Get reconciled validation for a symbol and direction.
    
    Combines backtesting, walk-forward, and live metrics into a single
    unified confidence score with drift detection and multi-TF reconciliation.
    
    Args:
        symbol: Trading symbol (e.g., "AAPL")
        direction: Prediction direction ("BULLISH", "BEARISH", "NEUTRAL")
    
    Returns:
        Standardized validation response with unified confidence,
        component breakdown, drift analysis, and recommendation.
    
    Raises:
        HTTPException: If validation fails or symbol not found
    
    Example:
        GET /api/validation/unified/AAPL/BULLISH
        
        Response:
        {
            "symbol": "AAPL",
            "direction": "BULLISH",
            "unified_confidence": 0.581,
            "status": "MODERATE_CONFIDENCE",
            "components": {...},
            "drift": {...},
            "multi_tf": {...},
            "recommendation": "Moderate confidence - trade with normal risk",
            ...
        }
    """
    try:
        # Validate direction
        if direction not in ["BULLISH", "BEARISH", "NEUTRAL"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid direction: {direction}. Must be BULLISH, BEARISH, or NEUTRAL.",
            )
        
        logger.info(f"Fetching unified validation: {symbol} {direction}")
        
        # Get unified validation
        result = await validation_service.get_live_validation(symbol, direction)
        
        # Convert to API response format
        response = ValidationResponse.from_prediction(result)
        
        logger.info(
            f"Validation retrieved: {symbol} confidence={response['unified_confidence']:.1%}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute validation: {str(e)}",
        )


@router.get("/history/{symbol}")
async def get_validation_history(
    symbol: str,
    days: int = Query(7, ge=1, le=90, description="Number of days of history to retrieve"),
    limit: int = Query(100, ge=1, le=500, description="Max number of results"),
) -> Dict:
    """
    Get validation history for a symbol.
    
    Retrieves historical validation results from database,
    showing confidence trends, drift evolution, and retraining events.
    
    Args:
        symbol: Trading symbol
        days: Number of days of history (1-90, default 7)
        limit: Maximum results to return (1-500, default 100)
    
    Returns:
        Dictionary with validation history:
        {
            "symbol": "AAPL",
            "history": [
                {"timestamp": "2026-01-21T10:40:00", "confidence": 0.581, "drift_severity": "severe", ...},
                ...
            ],
            "trend": {
                "avg_confidence": 0.62,
                "drift_trend": "increasing",
                "retraining_events": 1
            }
        }
    
    Example:
        GET /api/validation/history/AAPL?days=7&limit=50
    """
    try:
        logger.info(f"Fetching validation history: {symbol} (last {days} days)")
        
        # Query validation history from database
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        result = (
            validation_service.db.client.table("validation_results")
            .select("*")
            .eq("symbol", symbol)
            .gte("created_at", cutoff_date)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        
        if not result.
            raise HTTPException(
                status_code=404,
                detail=f"No validation history found for {symbol} in last {days} days",
            )
        
        # Format history records
        history = []
        drift_magnitudes = []
        retrain_count = 0
        
        for record in result.
            history.append(
                {
                    "timestamp": record.get("created_at"),
                    "unified_confidence": record.get("unified_confidence"),
                    "drift_detected": record.get("drift_detected"),
                    "drift_magnitude": record.get("drift_magnitude"),
                    "drift_severity": record.get("drift_severity"),
                    "retraining_trigger": record.get("retraining_trigger"),
                    "recommendation": record.get("recommendation"),
                }
            )
            
            if record.get("drift_magnitude"):
                drift_magnitudes.append(record["drift_magnitude"])
            
            if record.get("retraining_trigger"):
                retrain_count += 1
        
        # Calculate trend statistics
        confidences = [h["unified_confidence"] for h in history]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Determine drift trend
        if len(drift_magnitudes) >= 2:
            recent_drift = drift_magnitudes[0]
            old_drift = drift_magnitudes[-1]
            if recent_drift > old_drift * 1.1:  # 10% increase
                drift_trend = "increasing"
            elif recent_drift < old_drift * 0.9:  # 10% decrease
                drift_trend = "decreasing"
            else:
                drift_trend = "stable"
        else:
            drift_trend = "unknown"
        
        logger.info(
            f"History retrieved: {symbol} ({len(history)} records, "
            f"avg_conf={avg_confidence:.1%}, drift_trend={drift_trend})"
        )
        
        return {
            "symbol": symbol,
            "period_days": days,
            "record_count": len(history),
            "history": history,
            "trend": {
                "avg_confidence": round(avg_confidence, 4),
                "min_confidence": round(min(confidences), 4) if confidences else 0,
                "max_confidence": round(max(confidences), 4) if confidences else 0,
                "drift_trend": drift_trend,
                "retraining_events": retrain_count,
            },
        }
        
    except Exception as e:
        logger.error(f"Error fetching history for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve history: {str(e)}",
        )


@router.get("/drift-alerts")
async def get_drift_alerts(
    min_severity: str = Query(
        "moderate",
        regex="^(minor|moderate|severe|critical)$",
        description="Minimum drift severity to retrieve",
    ),
    limit: int = Query(50, ge=1, le=500, description="Max alerts to return"),
) -> Dict:
    """
    Get recent drift alerts across all symbols.
    
    Returns symbols with detected drift above severity threshold,
    sorted by magnitude (highest first).
    
    Args:
        min_severity: Minimum severity level (minor, moderate, severe, critical)
        limit: Maximum alerts to return
    
    Returns:
        Dictionary with drift alerts:
        {
            "alerts": [
                {
                    "symbol": "AAPL",
                    "drift_magnitude": 0.58,
                    "drift_severity": "severe",
                    "timestamp": "2026-01-21T10:40:00",
                    "recommendation": "Investigate model degradation"
                },
                ...
            ],
            "total_alerts": 3,
            "queried_at": "2026-01-21T10:40:00"
        }
    
    Example:
        GET /api/validation/drift-alerts?min_severity=severe&limit=20
    """
    try:
        # Map severity to numeric threshold for comparison
        severity_order = ["minor", "moderate", "severe", "critical"]
        min_severity_idx = severity_order.index(min_severity)
        
        logger.info(f"Fetching drift alerts (min_severity={min_severity})")
        
        # Query recent validation results with drift detected
        result = (
            validation_service.db.client.table("validation_results")
            .select("*")
            .eq("drift_detected", True)
            .order("drift_magnitude", desc=True)
            .limit(limit * 2)  # Get more to filter by severity
            .execute()
        )
        
        # Filter by severity and format response
        alerts = []
        for record in result.
            severity_idx = severity_order.index(record.get("drift_severity", "minor"))
            
            if severity_idx >= min_severity_idx:
                alerts.append(
                    {
                        "symbol": record.get("symbol"),
                        "direction": record.get("direction"),
                        "drift_magnitude": record.get("drift_magnitude"),
                        "drift_severity": record.get("drift_severity"),
                        "unified_confidence": record.get("unified_confidence"),
                        "timestamp": record.get("created_at"),
                        "retraining_trigger": record.get("retraining_trigger"),
                    }
                )
            
            if len(alerts) >= limit:
                break
        
        logger.info(f"Found {len(alerts)} drift alerts")
        
        return {
            "alerts": alerts,
            "total_alerts": len(alerts),
            "min_severity_filter": min_severity,
            "queried_at": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error fetching drift alerts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve drift alerts: {str(e)}",
        )


if __name__ == "__main__":
    # Test endpoints locally
    import asyncio
    import json
    
    async def test():
        print("\n=== Testing Validation API ===")
        
        # Test unified validation endpoint
        print("\n1. Testing /api/validation/unified/AAPL/BULLISH")
        try:
            result = await get_unified_validation("AAPL", "BULLISH")
            print(json.dumps(result, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
        
        # Test history endpoint
        print("\n2. Testing /api/validation/history/AAPL")
        try:
            result = await get_validation_history("AAPL", days=7, limit=10)
            print(json.dumps(result, indent=2, default=str)[:500] + "...")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test drift alerts endpoint
        print("\n3. Testing /api/validation/drift-alerts")
        try:
            result = await get_drift_alerts(min_severity="moderate", limit=10)
            print(json.dumps(result, indent=2, default=str)[:500] + "...")
        except Exception as e:
            print(f"Error: {e}")
    
    asyncio.run(test())
