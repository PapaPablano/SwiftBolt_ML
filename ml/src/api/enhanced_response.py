"""
Enhanced Prediction Response Builder.

Combines all ML components into a unified API response:
1. Base prediction (direction, confidence, price target)
2. Multi-timeframe consensus (signal aggregation)
3. Forecast explanation (why the model predicted this)
4. Data quality report (health of underlying data)

Usage:
    from src.api.enhanced_response import build_enhanced_response
    
    response = build_enhanced_response(
        symbol="AAPL",
        features_df=features_df,
        prediction="bullish",
        confidence=0.78,
        price_target=150.25,
        model=trained_model
    )
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from ..features.multi_timeframe import MultiTimeframeFeatures
from ..features.nan_reporter import NaNReporter
from ..models.forecast_explainer import ForecastExplainer

logger = logging.getLogger(__name__)


def build_enhanced_response(
    symbol: str,
    features_df: pd.DataFrame,
    prediction: str,
    confidence: float,
    price_target: Optional[float] = None,
    feature_importance: Optional[Dict[str, float]] = None,
    timeframes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build an enhanced prediction response with all ML insights.
    
    Args:
        symbol: Stock ticker symbol
        features_df: DataFrame with multi-timeframe features
        prediction: Base prediction ('bullish', 'bearish', 'neutral')
        confidence: Prediction confidence (0-1)
        price_target: Optional price target
        feature_importance: Optional dict of feature -> importance
        timeframes: List of timeframes used
        
    Returns:
        Enhanced response dictionary ready for JSON serialization
    """
    response = {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "prediction": prediction,
        "confidence": round(confidence, 3),
        "price_target": price_target,
    }
    
    # 1. Multi-timeframe consensus
    try:
        mtf_data = _build_multi_timeframe_section(
            features_df, timeframes or ["m15", "h1", "d1", "w1"]
        )
        response["multi_timeframe"] = mtf_data
    except Exception as e:
        logger.warning(f"Failed to build multi-timeframe section: {e}")
        response["multi_timeframe"] = {"error": str(e)}
    
    # 2. Forecast explanation
    try:
        explanation_data = _build_explanation_section(
            symbol, features_df, prediction, confidence,
            price_target, feature_importance
        )
        response["explanation"] = explanation_data
    except Exception as e:
        logger.warning(f"Failed to build explanation section: {e}")
        response["explanation"] = {"error": str(e)}
    
    # 3. Data quality report
    try:
        quality_data = _build_data_quality_section(features_df)
        response["data_quality"] = quality_data
    except Exception as e:
        logger.warning(f"Failed to build data quality section: {e}")
        response["data_quality"] = {"error": str(e)}
    
    logger.info(f"Built enhanced response for {symbol}: {prediction} @ {confidence:.1%}")
    
    return response


def _build_multi_timeframe_section(
    features_df: pd.DataFrame,
    timeframes: List[str],
) -> Dict[str, Any]:
    """Build the multi-timeframe consensus section."""
    mtf = MultiTimeframeFeatures(timeframes=timeframes)
    
    # Get the latest row's aggregated signals
    signals_df = mtf.aggregate_signals(features_df)
    
    if signals_df.empty:
        return {
            "signal": "neutral",
            "consensus_confidence": 0.0,
            "bullish_count": 0,
            "bearish_count": 0,
            "dominant_tf": None,
            "timeframe_breakdown": [],
        }
    
    # Get the most recent signal
    latest = signals_df.iloc[-1]
    
    # Build timeframe breakdown
    tf_breakdown = []
    for tf in timeframes:
        # Check for RSI as proxy for signal
        rsi_col = f"rsi_14_{tf}"
        if rsi_col in features_df.columns:
            rsi_val = features_df[rsi_col].iloc[-1]
            if pd.notna(rsi_val):
                if rsi_val > 60:
                    tf_signal = "bullish"
                elif rsi_val < 40:
                    tf_signal = "bearish"
                else:
                    tf_signal = "neutral"
                
                tf_breakdown.append({
                    "timeframe": tf,
                    "signal": tf_signal,
                    "rsi": round(rsi_val, 1),
                })
    
    return {
        "signal": latest.get("signal", "neutral"),
        "consensus_confidence": round(float(latest.get("confidence", 0)), 3),
        "bullish_count": int(latest.get("bullish_count", 0)),
        "bearish_count": int(latest.get("bearish_count", 0)),
        "dominant_tf": latest.get("dominant_tf"),
        "signal_value": round(float(latest.get("signal_value", 0)), 3),
        "timeframe_breakdown": tf_breakdown,
    }


def _build_explanation_section(
    symbol: str,
    features_df: pd.DataFrame,
    prediction: str,
    confidence: float,
    price_target: Optional[float],
    feature_importance: Optional[Dict[str, float]],
) -> Dict[str, Any]:
    """Build the forecast explanation section."""
    explainer = ForecastExplainer(feature_importance=feature_importance)
    
    # Get latest feature values as dict
    if features_df.empty:
        return {"error": "No features available"}
    
    latest_row = features_df.iloc[-1]
    features_dict = {
        col: float(val) if pd.notna(val) else None
        for col, val in latest_row.items()
        if col not in ["ts", "timestamp"]
    }
    
    # Generate explanation
    explanation = explainer.explain_prediction(
        symbol=symbol,
        features=features_dict,
        prediction=prediction,
        confidence=confidence,
        price_target=price_target,
    )
    
    # Convert to dict format
    return {
        "summary": explanation.summary,
        "top_features": [
            {
                "name": f.feature_name,
                "value": round(f.value, 4) if f.value else None,
                "direction": f.direction,
                "description": f.description,
            }
            for f in explanation.top_features
        ],
        "signal_breakdown": [
            {
                "category": s.category,
                "signal": s.signal,
                "strength": round(s.strength, 2),
                "description": s.description,
            }
            for s in explanation.signal_breakdown
        ],
        "risk_factors": explanation.risk_factors,
        "supporting_evidence": explanation.supporting_evidence,
        "contradicting_evidence": explanation.contradicting_evidence,
        "recommendation": explanation.recommendation,
    }


def _build_data_quality_section(features_df: pd.DataFrame) -> Dict[str, Any]:
    """Build the data quality section."""
    reporter = NaNReporter()
    report = reporter.scan_dataframe(features_df)
    
    # Calculate health score (inverse of NaN percentage)
    health_score = max(0, 1 - (report.overall_nan_percentage / 100))
    
    # Get problematic columns
    problematic = reporter.get_problematic_columns(threshold_pct=10.0)
    
    # Build column-level summary
    column_issues = []
    for col_name, col_report in report.column_reports.items():
        if col_report.nan_count > 0:
            column_issues.append({
                "column": col_name,
                "nan_count": col_report.nan_count,
                "nan_pct": round(col_report.nan_percentage, 1),
                "severity": col_report.severity,
            })
    
    # Sort by severity
    column_issues.sort(key=lambda x: x["nan_pct"], reverse=True)
    
    # Generate warnings
    warnings = []
    if health_score < 0.95:
        warnings.append(f"Data quality below 95% ({health_score:.1%})")
    if problematic:
        warnings.append(f"{len(problematic)} columns have >10% missing data")
    if report.total_nans > 100:
        warnings.append(f"High NaN count: {report.total_nans}")
    
    return {
        "health_score": round(health_score, 3),
        "total_rows": report.total_rows,
        "total_columns": report.total_columns,
        "total_nans": report.total_nans,
        "columns_with_issues": report.columns_with_nans,
        "severity": report.severity,
        "column_issues": column_issues[:10],  # Top 10 worst columns
        "warnings": warnings,
        "is_clean": report.is_clean,
    }


def build_minimal_response(
    symbol: str,
    prediction: str,
    confidence: float,
    price_target: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Build a minimal response without the enhanced sections.
    
    Use this for faster responses when full analysis isn't needed.
    """
    return {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "prediction": prediction,
        "confidence": round(confidence, 3),
        "price_target": price_target,
    }
