"""
CLI script to get forecast quality metrics for a symbol.
Called by FastAPI endpoint.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
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
        
        # Get latest forecast for the symbol/horizon
        symbol_id = db.get_symbol_id(symbol)
        if not symbol_id:
            return {
                "error": f"Symbol {symbol} not found",
                "symbol": symbol,
                "horizon": horizon,
            }
        
        # Get latest forecast from database
        # This is a simplified version - in production, you'd query the forecasts table
        # For now, we'll return a structure that can be enhanced later
        
        # Get forecast data (this would come from the forecasts table)
        # For MVP, we'll create a mock structure that can be replaced with actual DB query
        forecast_data = {
            "symbol": symbol,
            "horizon": horizon,
            "timeframe": timeframe,
            "confidence": 0.75,  # Would come from DB
            "model_agreement": 0.85,  # Would come from DB
            "created_at": datetime.now(),  # Would come from DB
            "conflicting_signals": 0,  # Would come from DB
        }
        
        # Compute quality metrics
        quality_score = ForecastQualityMonitor.compute_quality_score(forecast_data)
        issues = ForecastQualityMonitor.check_quality_issues(forecast_data)
        
        return {
            "symbol": symbol,
            "horizon": horizon,
            "timeframe": timeframe,
            "qualityScore": quality_score,
            "confidence": forecast_data["confidence"],
            "modelAgreement": forecast_data["model_agreement"],
            "issues": issues,
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
