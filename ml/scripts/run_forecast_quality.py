"""
CLI script to get forecast quality metrics for a symbol.
Called by FastAPI endpoint.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent
sys.path.insert(0, str(ml_dir))

from src.data.supabase_db import SupabaseDatabase
from src.monitoring.forecast_quality import ForecastQualityMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_forecast_quality(
    symbol: str,
    horizon: str = "1D",
    timeframe: str = "d1",
) -> dict:
    """
    Get forecast quality metrics for a symbol.
    
    Args:
        symbol: Stock ticker symbol
        horizon: Forecast horizon (1D, 1W, etc.)
        timeframe: Timeframe (d1, h1, etc.)
        
    Returns:
        Dictionary with quality metrics
    """
    try:
        db = SupabaseDatabase()
        
        # Get symbol ID
        symbol_id = db.get_symbol_id(symbol)
        if not symbol_id:
            return {
                "error": f"Symbol {symbol} not found",
                "symbol": symbol,
                "horizon": horizon,
            }
        
        # Query the ml_forecasts table for the specific symbol, horizon, and timeframe
        # First try with timeframe filter, then fallback to just horizon if no results
        try:
            logger.info(f"Querying forecast for {symbol} horizon={horizon} timeframe={timeframe}")
            response = (
                db.client.table("ml_forecasts")
                .select("confidence, model_agreement, run_at, quality_score, quality_issues, synthesis_data, model_predictions, timeframe, horizon")
                .eq("symbol_id", symbol_id)
                .eq("horizon", horizon)
                .eq("timeframe", timeframe)
                .order("run_at", desc=True)
                .limit(1)
                .execute()
            )
            
            # If no results with timeframe filter, try without timeframe filter (for legacy forecasts)
            if not response.data or len(response.data) == 0:
                logger.info(f"No forecast found for {symbol} horizon={horizon} timeframe={timeframe}, trying without timeframe filter")
                response = (
                    db.client.table("ml_forecasts")
                    .select("confidence, model_agreement, run_at, quality_score, quality_issues, synthesis_data, model_predictions, timeframe, horizon")
                    .eq("symbol_id", symbol_id)
                    .eq("horizon", horizon)
                    .order("run_at", desc=True)
                    .limit(1)
                    .execute()
                )
            
            if not response.data or len(response.data) == 0:
                # No forecast found for this horizon at all - return default/empty quality
                logger.warning(f"No forecast found for {symbol} horizon={horizon} (tried with and without timeframe filter)")
                return {
                    "symbol": symbol,
                    "horizon": horizon,
                    "timeframe": timeframe,
                    "qualityScore": 0.5,  # Default neutral score
                    "confidence": 0.5,
                    "modelAgreement": 0.5,
                    "issues": [
                        {
                            "level": "warning",
                            "type": "no_forecast",
                            "message": f"No forecast found for {horizon} horizon",
                            "action": "run_forecast",
                        }
                    ],
                    "timestamp": datetime.now().isoformat(),
                }
            
            forecast_row = response.data[0]
            
            found_timeframe = forecast_row.get('timeframe', 'N/A')
            found_horizon = forecast_row.get('horizon', 'N/A')
            logger.info(f"Found forecast for {symbol}: requested_horizon={horizon}, found_horizon={found_horizon}, timeframe={found_timeframe}")
            
            # Verify we got the right horizon (sanity check)
            if found_horizon != horizon:
                logger.warning(f"Horizon mismatch! Requested {horizon} but got {found_horizon}")
            
            # Extract forecast data
            confidence = forecast_row.get("confidence", 0.5)
            model_agreement = forecast_row.get("model_agreement")
            if model_agreement is None:
                model_agreement = 0.75  # Default if null
            run_at_str = forecast_row.get("run_at")
            
            logger.info(f"Forecast data for {horizon}: confidence={confidence}, model_agreement={model_agreement}, run_at={run_at_str}")
            
            # Parse run_at to datetime (timezone-naive, as ForecastQualityMonitor uses datetime.now() which is naive)
            if run_at_str:
                if isinstance(run_at_str, str):
                    # Handle ISO format strings - convert to timezone-naive
                    if run_at_str.endswith("Z"):
                        # UTC timezone, convert to naive
                        created_at = datetime.fromisoformat(run_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    elif "+" in run_at_str:
                        # Has timezone info, convert to naive UTC
                        dt = datetime.fromisoformat(run_at_str)
                        if dt.tzinfo:
                            # Convert to UTC then remove timezone
                            created_at = dt.astimezone(timezone.utc).replace(tzinfo=None)
                        else:
                            created_at = dt
                    else:
                        # No timezone, parse as-is
                        created_at = datetime.fromisoformat(run_at_str)
                elif isinstance(run_at_str, datetime):
                    # If timezone-aware, convert to naive
                    if run_at_str.tzinfo:
                        created_at = run_at_str.astimezone(timezone.utc).replace(tzinfo=None)
                    else:
                        created_at = run_at_str
                else:
                    created_at = datetime.now()
            else:
                created_at = datetime.now()
            
            # Check for conflicting signals from synthesis_data or model_predictions
            synthesis_data = forecast_row.get("synthesis_data") or {}
            model_predictions = forecast_row.get("model_predictions") or {}
            conflicting_signals = 0
            
            # Count conflicting signals from model predictions
            if isinstance(model_predictions, dict):
                labels = [v.get("label", "").lower() for v in model_predictions.values() if isinstance(v, dict)]
                unique_labels = set(labels)
                if len(unique_labels) > 1:
                    conflicting_signals = len(unique_labels) - 1
            
            # Build forecast data dict for quality monitor
            forecast_data = {
                "symbol": symbol,
                "horizon": horizon,
                "timeframe": timeframe,
                "confidence": confidence,
                "model_agreement": model_agreement,
                "created_at": created_at,
                "conflicting_signals": conflicting_signals,
            }
            
            # Compute quality metrics using the actual forecast data
            quality_score = ForecastQualityMonitor.compute_quality_score(forecast_data)
            issues = ForecastQualityMonitor.check_quality_issues(forecast_data)
            
            # If there's a stored quality_score, use it (it may have been computed with more context)
            stored_quality_score = forecast_row.get("quality_score")
            if stored_quality_score is not None:
                quality_score = stored_quality_score
            
            # Merge any stored quality_issues
            stored_issues = forecast_row.get("quality_issues")
            if stored_issues and isinstance(stored_issues, list):
                # Combine stored issues with computed issues (avoid duplicates)
                existing_types = {issue.get("type") for issue in issues}
                for stored_issue in stored_issues:
                    if isinstance(stored_issue, dict) and stored_issue.get("type") not in existing_types:
                        issues.append(stored_issue)
            
            return {
                "symbol": symbol,
                "horizon": horizon,
                "timeframe": timeframe,
                "qualityScore": quality_score,
                "confidence": confidence,
                "modelAgreement": model_agreement,
                "issues": issues,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as db_error:
            logger.error(f"Error querying forecast from database: {db_error}", exc_info=True)
            # Fallback to default values if DB query fails
            return {
                "symbol": symbol,
                "horizon": horizon,
                "timeframe": timeframe,
                "qualityScore": 0.5,
                "confidence": 0.5,
                "modelAgreement": 0.5,
                "issues": [
                    {
                        "level": "warning",
                        "type": "database_error",
                        "message": f"Could not fetch forecast: {str(db_error)}",
                        "action": "retry",
                    }
                ],
                "timestamp": datetime.now().isoformat(),
            }
        
    except Exception as e:
        logger.error(f"Error getting forecast quality: {e}", exc_info=True)
        return {
            "error": str(e),
            "symbol": symbol,
            "horizon": horizon,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get forecast quality metrics")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol")
    parser.add_argument("--horizon", default="1D", help="Forecast horizon (1D, 1W, etc.)")
    parser.add_argument("--timeframe", default="d1", help="Timeframe (d1, h1, etc.)")
    
    args = parser.parse_args()
    
    result = get_forecast_quality(
        symbol=args.symbol,
        horizon=args.horizon,
        timeframe=args.timeframe,
    )
    
    print(json.dumps(result, indent=2))
