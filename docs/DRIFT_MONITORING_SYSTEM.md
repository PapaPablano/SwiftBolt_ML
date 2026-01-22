# Part 5: Drift Monitoring & Performance Tracking

## Overview

Drift monitoring detects when your trained ensemble's real-world performance degrades. This triggers automatic alerts and can trigger emergency retraining.

---

## Module: Drift Monitor (`ml/src/training/drift_monitor.py`)

```python
"""Monitor for performance degradation (drift)."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.data.supabase_db import db

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Daily performance snapshot."""
    date: str
    symbol: str
    timeframe: str
    accuracy: float
    n_predictions: int
    drift_detected: bool
    baseline_accuracy: float
    drift_margin: float  # accuracy - baseline
    
    def to_dict(self) -> Dict:
        return {
            "date": self.date,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "accuracy": self.accuracy,
            "n_predictions": self.n_predictions,
            "drift_detected": self.drift_detected,
            "baseline_accuracy": self.baseline_accuracy,
            "drift_margin": self.drift_margin,
        }


class DriftMonitor:
    """Monitor for performance degradation (drift)."""
    
    # Configuration
    DRIFT_THRESHOLD = 0.15  # Alert if accuracy < baseline - 15%
    MIN_SAMPLES = 5         # Need at least 5 predictions to evaluate
    SEVERE_DRIFT = 0.25     # Emergency alert if accuracy < baseline - 25%
    
    def __init__(self):
        self.baseline_accuracies = {}  # {(symbol, timeframe): 0.60}
        self.daily_metrics = []        # List of PerformanceMetrics
        self.prediction_log = {}       # {(symbol, timeframe, date): [(pred, actual), ...]}
    
    def set_baseline(
        self,
        symbol: str,
        timeframe: str,
        accuracy: float,
    ) -> None:
        """
        Set baseline accuracy from validation set.
        
        This is typically the validation accuracy from the training job.
        
        Args:
            symbol: Stock ticker
            timeframe: Timeframe identifier
            accuracy: Baseline accuracy from validation set
        """
        self.baseline_accuracies[(symbol, timeframe)] = accuracy
        logger.info(
            f"Baseline for {symbol}/{timeframe}: {accuracy:.1%}"
        )
    
    def record_prediction(
        self,
        symbol: str,
        timeframe: str,
        prediction: str,  # "BULLISH", "BEARISH", "NEUTRAL"
        actual: str,
        confidence: float,
    ) -> None:
        """
        Record a single prediction for drift tracking.
        
        Args:
            symbol: Stock ticker
            timeframe: Timeframe
            prediction: Model's prediction
            actual: Actual direction (from next bar close)
            confidence: Model's confidence score
        """
        today = datetime.utcnow().date().isoformat()
        key = (symbol, timeframe, today)
        
        if key not in self.prediction_log:
            self.prediction_log[key] = []
        
        self.prediction_log[key].append({
            "prediction": prediction,
            "actual": actual,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def compute_daily_metrics(
        self,
        symbol: str,
        timeframe: str,
        date: str,
    ) -> Optional[PerformanceMetrics]:
        """
        Compute accuracy metrics for a specific day.
        
        Args:
            symbol: Stock ticker
            timeframe: Timeframe
            date: Date (YYYY-MM-DD format)
        
        Returns:
            PerformanceMetrics with accuracy and drift status
        """
        key = (symbol, timeframe, date)
        preds_for_day = self.prediction_log.get(key, [])
        
        if len(preds_for_day) < self.MIN_SAMPLES:
            logger.warning(
                f"Only {len(preds_for_day)} predictions for {symbol}/{timeframe}/{date}, "
                f"need {self.MIN_SAMPLES} for drift check"
            )
            return None
        
        # Calculate accuracy
        predictions = np.array([p["prediction"] for p in preds_for_day])
        actuals = np.array([p["actual"] for p in preds_for_day])
        
        accuracy = float(np.mean(predictions == actuals))
        
        # Get baseline
        baseline = self.baseline_accuracies.get((symbol, timeframe), 0.55)
        
        # Calculate drift margin
        drift_margin = accuracy - baseline
        drift_detected = drift_margin < -self.DRIFT_THRESHOLD
        severe_drift = drift_margin < -self.SEVERE_DRIFT
        
        metrics = PerformanceMetrics(
            date=date,
            symbol=symbol,
            timeframe=timeframe,
            accuracy=accuracy,
            n_predictions=len(preds_for_day),
            drift_detected=drift_detected,
            baseline_accuracy=baseline,
            drift_margin=drift_margin,
        )
        
        self.daily_metrics.append(metrics)
        
        # Log results
        status = "⚠️ DRIFT" if drift_detected else "✅"
        emergency = " 🚨 EMERGENCY" if severe_drift else ""
        
        logger.info(
            f"{status} {symbol}/{timeframe}/{date}: {accuracy:.1%} accuracy "
            f"(baseline: {baseline:.1%}, margin: {drift_margin:+.1%}){emergency}"
        )
        
        return metrics
    
    def get_drift_status(
        self,
        symbol: str,
        timeframe: str,
        lookback_days: int = 7,
    ) -> Dict:
        """
        Get drift status over lookback window.
        
        Args:
            symbol: Stock ticker
            timeframe: Timeframe
            lookback_days: Days to look back (default 7)
        
        Returns:
            {
                "symbol": "AAPL",
                "timeframe": "d1",
                "lookback_days": 7,
                "overall_accuracy": 0.52,
                "baseline": 0.59,
                "drift_detected": True,
                "daily_accuracies": [0.50, 0.55, 0.48, ...],
                "trend": "declining",
                "recommendation": "retrain_now",
            }
        """
        today = datetime.utcnow().date()
        
        # Find metrics for lookback window
        relevant_metrics = [
            m for m in self.daily_metrics
            if m.symbol == symbol
            and m.timeframe == timeframe
            and (today - datetime.fromisoformat(m.date).date()).days < lookback_days
        ]
        
        if not relevant_metrics:
            logger.warning(f"No drift metrics for {symbol}/{timeframe}")
            return {"error": "No metrics available"}
        
        accuracies = [m.accuracy for m in relevant_metrics]
        baseline = self.baseline_accuracies.get((symbol, timeframe), 0.55)
        overall_accuracy = np.mean(accuracies)
        
        # Detect trend
        if len(accuracies) >= 3:
            first_half = np.mean(accuracies[: len(accuracies) // 2])
            second_half = np.mean(accuracies[len(accuracies) // 2 :])
            trend = "declining" if second_half < first_half else "improving"
        else:
            trend = "insufficient_data"
        
        # Recommendation
        drift_detected = any(m.drift_detected for m in relevant_metrics)
        severe_drift = any(
            m.drift_margin < -self.SEVERE_DRIFT for m in relevant_metrics
        )
        
        if severe_drift:
            recommendation = "retrain_now"
        elif drift_detected and trend == "declining":
            recommendation = "schedule_retrain"
        elif drift_detected:
            recommendation = "monitor_closely"
        else:
            recommendation = "operating_normally"
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "lookback_days": lookback_days,
            "overall_accuracy": float(overall_accuracy),
            "baseline": float(baseline),
            "drift_detected": drift_detected,
            "severe_drift": severe_drift,
            "daily_accuracies": [float(a) for a in accuracies],
            "trend": trend,
            "recommendation": recommendation,
            "n_days_monitored": len(relevant_metrics),
        }
    
    def store_metrics_to_db(
        self,
        symbol: str,
        timeframe: str,
        metrics: PerformanceMetrics,
    ) -> bool:
        """
        Store performance metrics to database for tracking.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            symbol_id = db.get_symbol_id(symbol)
            
            db.client.table("drift_monitoring").insert({
                "symbol_id": symbol_id,
                "timeframe": timeframe,
                "date": metrics.date,
                "accuracy": metrics.accuracy,
                "n_predictions": metrics.n_predictions,
                "baseline_accuracy": metrics.baseline_accuracy,
                "drift_margin": metrics.drift_margin,
                "drift_detected": metrics.drift_detected,
            }).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")
            return False


# Module-level convenience functions

_monitor = DriftMonitor()  # Global instance


def record_prediction(
    symbol: str,
    timeframe: str,
    prediction: str,
    actual: str,
    confidence: float,
) -> None:
    """Record prediction in global monitor."""
    _monitor.record_prediction(symbol, timeframe, prediction, actual, confidence)


def check_drift(
    symbol: str,
    timeframe: str,
    lookback_days: int = 7,
) -> Dict:
    """Check drift status for symbol/timeframe."""
    return _monitor.get_drift_status(symbol, timeframe, lookback_days)


def set_baselines_from_training(
    training_results: Dict,
) -> None:
    """
    Set all baselines from training job results.
    
    Args:
        training_results: Result from ensemble_training_job
    """
    for symbol, timeframes in training_results.get("trained", {}).items():
        for timeframe, result in timeframes.items():
            accuracy = result.get("validation_accuracy")
            if accuracy:
                _monitor.set_baseline(symbol, timeframe, accuracy)
```

---

## Daily Drift Checking Job

### Job: `ml/src/training/drift_check_job.py`

```python
"""Daily drift monitoring job.

Run every morning after market hours to:
1. Fetch yesterday's forecasts
2. Fetch actual results
3. Calculate accuracy
4. Alert if drift detected
5. Log trends
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings
from src.data.supabase_db import db
from src.training.drift_monitor import DriftMonitor

logger = logging.getLogger(__name__)


def fetch_yesterday_forecasts(
    symbol: str,
    timeframe: str,
) -> List[Dict]:
    """
    Fetch forecasts from yesterday for symbol/timeframe.
    
    Returns:
        List of forecast records with predictions
    """
    yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
    
    try:
        result = db.client.table("forecast_results").select(
            "id, forecast_direction, confidence, forecast_time"
        ).eq(
            "symbol", symbol
        ).eq(
            "timeframe", timeframe
        ).gte(
            "forecast_time", f"{yesterday}T00:00:00"
        ).lt(
            "forecast_time", f"{yesterday}T23:59:59"
        ).execute()
        
        return result.data or []
        
    except Exception as e:
        logger.error(f"Failed to fetch yesterday's forecasts: {e}")
        return []


def fetch_actual_results(
    symbol: str,
    timeframe: str,
) -> Dict[str, str]:
    """
    Fetch actual market directions for yesterday.
    
    Returns:
        {forecast_time: actual_direction}
    """
    yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
    
    try:
        result = db.client.table("ohlc_data").select(
            "timestamp, close"
        ).eq(
            "symbol", symbol
        ).eq(
            "timeframe", timeframe
        ).gte(
            "timestamp", f"{yesterday}T00:00:00"
        ).lt(
            "timestamp", f"{yesterday}T23:59:59"
        ).order(
            "timestamp"
        ).execute()
        
        closes = [float(row["close"]) for row in result.data]
        
        # Calculate directions (comparing close at time + 1 to close at time)
        actual_directions = {}
        for i in range(len(closes) - 1):
            next_close = closes[i + 1]
            curr_close = closes[i]
            ret = (next_close - curr_close) / curr_close
            
            if ret > 0.002:
                direction = "BULLISH"
            elif ret < -0.002:
                direction = "BEARISH"
            else:
                direction = "NEUTRAL"
            
            actual_directions[i] = direction
        
        return actual_directions
        
    except Exception as e:
        logger.error(f"Failed to fetch actual results: {e}")
        return {}


def run_daily_drift_check(
    symbols: List[str] = None,
) -> Dict:
    """
    Run drift check for all symbols/timeframes.
    
    Args:
        symbols: List of symbols to check (default: all in settings)
    
    Returns:
        Summary of drift checks
    """
    if symbols is None:
        symbols = settings.symbols_to_process
    
    logger.info("=" * 60)
    logger.info("DAILY DRIFT CHECK")
    logger.info(f"Date: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    monitor = DriftMonitor()
    
    # Load baselines from database
    logger.info("Loading baselines from database...")
    # TODO: Query training_runs table for latest baselines
    # For now, use defaults
    for symbol in symbols:
        for timeframe in ["m15", "h1", "h4", "d1", "w1"]:
            monitor.set_baseline(symbol, timeframe, 0.55)  # Default baseline
    
    results = {
        "check_time": datetime.utcnow().isoformat(),
        "symbols": symbols,
        "checks": [],
        "alerts": [],
    }
    
    for symbol in symbols:
        for timeframe in ["m15", "h1", "h4", "d1"]:
            logger.info(f"\nChecking {symbol}/{timeframe}...")
            
            # Fetch yesterday's forecasts and actuals
            forecasts = fetch_yesterday_forecasts(symbol, timeframe)
            actuals = fetch_actual_results(symbol, timeframe)
            
            if not forecasts:
                logger.warning(f"No forecasts found for {symbol}/{timeframe}")
                continue
            
            # Record in monitor
            for i, forecast in enumerate(forecasts):
                actual = actuals.get(i, "NEUTRAL")
                monitor.record_prediction(
                    symbol=symbol,
                    timeframe=timeframe,
                    prediction=forecast["forecast_direction"],
                    actual=actual,
                    confidence=forecast["confidence"],
                )
            
            # Compute metrics
            today = datetime.utcnow().date().isoformat()
            metrics = monitor.compute_daily_metrics(symbol, timeframe, today)
            
            if metrics:
                results["checks"].append(metrics.to_dict())
                
                # Store to database
                monitor.store_metrics_to_db(symbol, timeframe, metrics)
                
                # Check for alerts
                if metrics.drift_detected:
                    alert = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "type": "drift_detected",
                        "accuracy": metrics.accuracy,
                        "baseline": metrics.baseline_accuracy,
                        "margin": metrics.drift_margin,
                    }
                    results["alerts"].append(alert)
                    logger.warning(f"🚨 DRIFT ALERT: {symbol}/{timeframe}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("DRIFT CHECK SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Checks performed: {len(results['checks'])}")
    logger.info(f"Alerts triggered: {len(results['alerts'])}")
    
    for alert in results["alerts"]:
        logger.warning(
            f"  {alert['symbol']}/{alert['timeframe']}: "
            f"{alert['accuracy']:.1%} vs {alert['baseline']:.1%} "
            f"({alert['margin']:+.1%})"
        )
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Daily drift monitoring check"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=settings.symbols_to_process,
        help="Symbols to check",
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    results = run_daily_drift_check(symbols=args.symbols)
    
    # Exit with error if alerts triggered
    if results["alerts"]:
        sys.exit(1)
```

---

## Monitoring Dashboard Queries

### Query: Daily Accuracy Trending

```sql
SELECT 
    date,
    symbol,
    timeframe,
    accuracy,
    baseline_accuracy,
    (accuracy - baseline_accuracy) as drift_margin,
    drift_detected,
    n_predictions
FROM drift_monitoring
WHERE symbol = 'AAPL'
  AND timeframe = 'd1'
  AND date >= NOW() - INTERVAL '30 days'
ORDER BY date DESC
LIMIT 30;
```

### Query: Drift Alerts by Symbol

```sql
SELECT 
    DATE_TRUNC('day', date) as alert_date,
    symbol,
    timeframe,
    COUNT(*) as alert_count,
    AVG(accuracy) as avg_accuracy,
    AVG(baseline_accuracy) as avg_baseline
FROM drift_monitoring
WHERE drift_detected = TRUE
  AND date >= NOW() - INTERVAL '7 days'
GROUP BY alert_date, symbol, timeframe
ORDER BY alert_date DESC;
```

### Query: Baseline Accuracy Needed for Retrain

```sql
SELECT 
    symbol,
    timeframe,
    MAX(run_date) as last_training,
    AVG(m.accuracy) as recent_accuracy,
    tr.ensemble_validation_accuracy as training_baseline
FROM drift_monitoring m
JOIN training_runs tr ON tr.symbol_id = (SELECT id FROM symbols WHERE ticker = m.symbol)
  AND tr.timeframe = m.timeframe
WHERE m.date >= NOW() - INTERVAL '7 days'
  AND m.drift_detected = TRUE
GROUP BY symbol, timeframe, training_baseline
HAVING AVG(m.accuracy) < (training_baseline - 0.15)
ORDER BY recent_accuracy ASC;
```

---

## Alert Escalation

### Normal Operation
```
Accuracy > (Baseline - 5%)  → ✅ OK - Continue monitoring
```

### Warning Zone
```
(Baseline - 15%) < Accuracy < (Baseline - 5%)  → ⚠️ MONITOR - Log trending
```

### Drift Alert
```
(Baseline - 15%) > Accuracy  → 🚨 DRIFT - Schedule retrain this week
```

### Emergency (Severe Drift)
```
(Baseline - 25%) > Accuracy  → 🚆 EMERGENCY - Retrain NOW, disable live trading
```

---

## Integration with Slack Alerts

### Add to drift_check_job.py

```python
import os
from slack_sdk import WebClient

def send_slack_alert(results: Dict):
    """Send drift alerts to Slack."""
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        return
    
    client = WebClient(token=slack_token)
    
    for alert in results["alerts"]:
        symbol = alert["symbol"]
        timeframe = alert["timeframe"]
        accuracy = alert["accuracy"]
        baseline = alert["baseline"]
        
        message = (
            f"🚨 DRIFT DETECTED: {symbol}/{timeframe}\n"
            f"Current Accuracy: {accuracy:.1%}\n"
            f"Baseline: {baseline:.1%}\n"
            f"Action: Schedule retrain"
        )
        
        client.chat_postMessage(
            channel="#ml-alerts",
            text=message,
        )
```

---

## Next Steps

1. ✅ Review drift monitoring concept
2. → Implement `drift_monitor.py` in `ml/src/training/`
3. → Implement `drift_check_job.py` for daily monitoring
4. → Add GitHub Actions workflow for daily checks
5. → See `TRAINING_IMPLEMENTATION_CHECKLIST.md` for schedule
