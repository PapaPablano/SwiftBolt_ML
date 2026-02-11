#!/usr/bin/env python3
"""
Production Monitor - Main Production System
Real-time monitoring for the KDJ-Enhanced Hybrid Ensemble.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union
import logging
from pathlib import Path
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import deque
import time

@dataclass
class PerformanceMetrics:
    """Structure for performance metrics."""
    timestamp: str
    mae: float
    rmse: float
    mape: float
    directional_accuracy: float
    ensemble_improvement: float
    prediction_latency_ms: float
    drift_score: float

@dataclass
class AlertEvent:
    """Structure for alert events."""
    timestamp: str
    alert_type: str
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    message: str
    metric_value: float
    threshold: float
    
class ProductionMonitor:
    """
    Production monitoring system for hybrid ensemble.
    Tracks performance, detects drift, and manages alerts.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {
            'alert_thresholds': {
                'mae_degradation': 15.0,  # % increase
                'rmse_degradation': 15.0,
                'accuracy_drop': 50.0,    # % minimum
                'ensemble_improvement': 5.0,  # % minimum
                'drift_threshold': 0.05,  # p-value
                'latency_threshold': 100.0  # ms
            },
            'monitoring_window': 100,  # Keep last N metrics
            'alert_cooldown': 300,     # 5 minutes between same alerts
            'drift_detection_window': 20
        }
        
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.metrics_history = deque(maxlen=self.config['monitoring_window'])
        self.alerts_history = deque(maxlen=1000)
        self.alert_cooldowns = {}
        
        # Baseline performance (to be set)
        self.baseline_metrics = None
        
    def record_metrics(self, metrics: PerformanceMetrics):
        """Record new performance metrics and check for alerts."""
        self.metrics_history.append(metrics)
        
        # Check for alerts
        alerts = self._check_alerts(metrics)
        
        for alert in alerts:
            self.alerts_history.append(alert)
            self._log_alert(alert)
        
        # Update baseline if needed
        self._update_baseline()
        
        self.logger.info(f"Recorded metrics: MAE={metrics.mae:.3f}, Accuracy={metrics.directional_accuracy:.1f}%")
        
    def _check_alerts(self, metrics: PerformanceMetrics) -> List[AlertEvent]:
        """Check metrics against thresholds and generate alerts."""
        alerts = []
        current_time = datetime.now().isoformat()
        thresholds = self.config['alert_thresholds']
        
        # MAE degradation alert
        if self.baseline_metrics and metrics.mae > 0:
            mae_increase = (metrics.mae - self.baseline_metrics.mae) / self.baseline_metrics.mae * 100
            if mae_increase > thresholds['mae_degradation']:
                if self._can_alert('mae_degradation'):
                    alerts.append(AlertEvent(
                        timestamp=current_time,
                        alert_type='mae_degradation',
                        severity='HIGH',
                        message=f"MAE degraded by {mae_increase:.1f}%",
                        metric_value=mae_increase,
                        threshold=thresholds['mae_degradation']
                    ))
        
        # RMSE degradation alert
        if self.baseline_metrics and metrics.rmse > 0:
            rmse_increase = (metrics.rmse - self.baseline_metrics.rmse) / self.baseline_metrics.rmse * 100
            if rmse_increase > thresholds['rmse_degradation']:
                if self._can_alert('rmse_degradation'):
                    alerts.append(AlertEvent(
                        timestamp=current_time,
                        alert_type='rmse_degradation',
                        severity='HIGH',
                        message=f"RMSE degraded by {rmse_increase:.1f}%",
                        metric_value=rmse_increase,
                        threshold=thresholds['rmse_degradation']
                    ))
        
        # Directional accuracy drop
        if metrics.directional_accuracy < thresholds['accuracy_drop']:
            if self._can_alert('accuracy_drop'):
                alerts.append(AlertEvent(
                    timestamp=current_time,
                    alert_type='accuracy_drop',
                    severity='CRITICAL',
                    message=f"Directional accuracy dropped to {metrics.directional_accuracy:.1f}%",
                    metric_value=metrics.directional_accuracy,
                    threshold=thresholds['accuracy_drop']
                ))
        
        # Ensemble improvement check
        if metrics.ensemble_improvement < thresholds['ensemble_improvement']:
            if self._can_alert('ensemble_improvement'):
                alerts.append(AlertEvent(
                    timestamp=current_time,
                    alert_type='ensemble_improvement',
                    severity='MEDIUM',
                    message=f"Ensemble improvement only {metrics.ensemble_improvement:.1f}%",
                    metric_value=metrics.ensemble_improvement,
                    threshold=thresholds['ensemble_improvement']
                ))
        
        # Drift detection
        if metrics.drift_score < thresholds['drift_threshold']:
            if self._can_alert('drift_detection'):
                alerts.append(AlertEvent(
                    timestamp=current_time,
                    alert_type='drift_detection',
                    severity='HIGH',
                    message=f"Data drift detected (p-value: {metrics.drift_score:.4f})",
                    metric_value=metrics.drift_score,
                    threshold=thresholds['drift_threshold']
                ))
        
        # Latency alert
        if metrics.prediction_latency_ms > thresholds['latency_threshold']:
            if self._can_alert('latency_threshold'):
                alerts.append(AlertEvent(
                    timestamp=current_time,
                    alert_type='latency_threshold',
                    severity='MEDIUM',
                    message=f"High prediction latency: {metrics.prediction_latency_ms:.1f}ms",
                    metric_value=metrics.prediction_latency_ms,
                    threshold=thresholds['latency_threshold']
                ))
        
        return alerts
    
    def _can_alert(self, alert_type: str) -> bool:
        """Check if we can send an alert (respects cooldown)."""
        cooldown = self.config['alert_cooldown']
        last_alert_time = self.alert_cooldowns.get(alert_type, 0)
        current_time = time.time()
        
        if current_time - last_alert_time > cooldown:
            self.alert_cooldowns[alert_type] = current_time
            return True
        return False
    
    def _log_alert(self, alert: AlertEvent):
        """Log alert event."""
        severity_emojis = {
            'LOW': '🟡',
            'MEDIUM': '🟠', 
            'HIGH': '🔴',
            'CRITICAL': '🚨'
        }
        
        emoji = severity_emojis.get(alert.severity, '⚠️')
        self.logger.warning(f"{emoji} ALERT [{alert.severity}] {alert.alert_type}: {alert.message}")
    
    def _update_baseline(self):
        """Update baseline metrics using recent performance."""
        if len(self.metrics_history) < 10:
            return
            
        # Use median of recent metrics as baseline
        recent_metrics = list(self.metrics_history)[-10:]
        
        self.baseline_metrics = PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            mae=np.median([m.mae for m in recent_metrics]),
            rmse=np.median([m.rmse for m in recent_metrics]),
            mape=np.median([m.mape for m in recent_metrics]),
            directional_accuracy=np.median([m.directional_accuracy for m in recent_metrics]),
            ensemble_improvement=np.median([m.ensemble_improvement for m in recent_metrics]),
            prediction_latency_ms=np.median([m.prediction_latency_ms for m in recent_metrics]),
            drift_score=np.median([m.drift_score for m in recent_metrics])
        )
    
    def get_model_health(self) -> Dict[str, Any]:
        """Get overall model health assessment."""
        if not self.metrics_history:
            return {'status': 'NO_DATA', 'message': 'No metrics available'}
        
        latest_metrics = self.metrics_history[-1]
        recent_alerts = [a for a in self.alerts_history if self._is_recent_alert(a)]
        
        # Count critical issues
        critical_alerts = [a for a in recent_alerts if a.severity in ['HIGH', 'CRITICAL']]
        
        # Determine health status
        if len(critical_alerts) > 0:
            status = 'DEGRADED'
            message = f"{len(critical_alerts)} critical issues detected"
        elif len(recent_alerts) > 3:
            status = 'DEGRADED'
            message = f"{len(recent_alerts)} alerts in recent period"
        elif latest_metrics.directional_accuracy > 60:
            status = 'HEALTHY'
            message = "All systems operating normally"
        else:
            status = 'MONITORING'
            message = "Performance below optimal but stable"
        
        # Calculate trend
        trend = self._calculate_performance_trend()
        
        return {
            'status': status,
            'message': message,
            'latest_metrics': asdict(latest_metrics),
            'recent_alerts': len(recent_alerts),
            'critical_alerts': len(critical_alerts),
            'performance_trend': trend,
            'days_until_retraining': self._estimate_retraining_schedule()
        }
    
    def _is_recent_alert(self, alert: AlertEvent, hours: int = 24) -> bool:
        """Check if alert is recent."""
        alert_time = datetime.fromisoformat(alert.timestamp)
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return alert_time > cutoff_time
    
    def _calculate_performance_trend(self) -> str:
        """Calculate performance trend over recent metrics."""
        if len(self.metrics_history) < 5:
            return 'INSUFFICIENT_DATA'
        
        recent_metrics = list(self.metrics_history)[-5:]
        
        # Calculate trend in key metrics
        mae_values = [m.mae for m in recent_metrics]
        accuracy_values = [m.directional_accuracy for m in recent_metrics]
        
        mae_trend = np.polyfit(range(len(mae_values)), mae_values, 1)[0]
        accuracy_trend = np.polyfit(range(len(accuracy_values)), accuracy_values, 1)[0]
        
        # Determine overall trend
        if mae_trend > 0.1 or accuracy_trend < -1.0:
            return 'DEGRADING'
        elif mae_trend < -0.1 and accuracy_trend > 1.0:
            return 'IMPROVING'
        else:
            return 'STABLE'
    
    def _estimate_retraining_schedule(self) -> int:
        """Estimate days until retraining needed."""
        if not self.metrics_history or len(self.metrics_history) < 3:
            return 30  # Default
        
        trend = self._calculate_performance_trend()
        
        if trend == 'DEGRADING':
            return 7  # Urgent retraining
        elif trend == 'STABLE':
            return 30  # Regular schedule
        else:
            return 60  # Extended schedule
    
    def generate_monitoring_report(self, save_path: Optional[Path] = None) -> str:
        """Generate comprehensive monitoring report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not self.metrics_history:
            report = "No monitoring data available."
        else:
            health = self.get_model_health()
            latest_metrics = self.metrics_history[-1]
            recent_alerts = [a for a in self.alerts_history if self._is_recent_alert(a)]
            
            report = f"""
ML ANALYSIS PLATFORM - MONITORING REPORT
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{"="*60}

MODEL HEALTH STATUS: {health['status']} {"✅" if health['status'] == "HEALTHY" else "⚠️" if health['status'] == "MONITORING" else "🔴"}
Message: {health['message']}
Performance Trend: {health['performance_trend']}
Days Until Retraining: {health['days_until_retraining']}

LATEST METRICS (as of {latest_metrics.timestamp})
{"="*40}
MAE:                    {latest_metrics.mae:.4f}
RMSE:                   {latest_metrics.rmse:.4f}
MAPE:                   {latest_metrics.mape:.2f}%
Directional Accuracy:   {latest_metrics.directional_accuracy:.1f}%
Ensemble Improvement:   {latest_metrics.ensemble_improvement:.1f}%
Prediction Latency:     {latest_metrics.prediction_latency_ms:.1f}ms
Drift Score:            {latest_metrics.drift_score:.4f}

RECENT ALERTS (Last 24 hours)
{"="*30}
Total Alerts: {len(recent_alerts)}
Critical: {len([a for a in recent_alerts if a.severity in ['HIGH', 'CRITICAL']])}
"""
            
            if recent_alerts:
                report += "\nAlert Details:\n"
                for alert in recent_alerts[-5:]:  # Last 5 alerts
                    report += f"  [{alert.severity}] {alert.alert_type}: {alert.message}\n"
            else:
                report += "No recent alerts ✅\n"
            
            # Performance history
            if len(self.metrics_history) > 1:
                report += f"\nPERFORMANCE HISTORY (Last {min(len(self.metrics_history), 10)} readings)\n"
                report += "="*50 + "\n"
                
                recent_history = list(self.metrics_history)[-10:]
                for i, metrics in enumerate(recent_history):
                    report += f"{i+1:2d}. MAE: {metrics.mae:.3f}, Accuracy: {metrics.directional_accuracy:.1f}%, Latency: {metrics.prediction_latency_ms:.1f}ms\n"
            
            # Recommendations
            report += f"\nRECOMMENDATIONS\n"
            report += "="*20 + "\n"
            
            if health['status'] == 'DEGRADED':
                report += "🔴 MODEL RETRAINING RECOMMENDED\n"
                report += "🔴 INVESTIGATE ALERT CAUSES\n"
            elif health['status'] == 'MONITORING':
                report += "🟡 MONITOR CLOSELY\n"
                report += "🟡 CONSIDER PARAMETER TUNING\n"
            else:
                report += "✅ CONTINUE CURRENT OPERATIONS\n"
                
        # Save report if path provided
        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'w') as f:
                f.write(report)
                
            self.logger.info(f"Monitoring report saved to {save_path}")
        
        return report
    
    def export_metrics_for_dashboard(self) -> Dict[str, Any]:
        """Export metrics in format suitable for dashboard display."""
        if not self.metrics_history:
            return {'status': 'no_data'}
        
        # Convert to lists for JSON serialization
        metrics_list = [asdict(m) for m in self.metrics_history]
        alerts_list = [asdict(a) for a in self.alerts_history if self._is_recent_alert(a)]
        
        return {
            'status': 'success',
            'health': self.get_model_health(),
            'metrics_history': metrics_list,
            'recent_alerts': alerts_list,
            'baseline_metrics': asdict(self.baseline_metrics) if self.baseline_metrics else None,
            'config': self.config
        }
    
    def load_metrics_history(self, file_path: Path):
        """Load metrics history from CSV file."""
        try:
            df = pd.read_csv(file_path)
            self.metrics_history.clear()
            
            for _, row in df.iterrows():
                metrics = PerformanceMetrics(
                    timestamp=row['timestamp'],
                    mae=row['mae'],
                    rmse=row['rmse'],
                    mape=row['mape'],
                    directional_accuracy=row['directional_accuracy'],
                    ensemble_improvement=row['ensemble_improvement'],
                    prediction_latency_ms=row['prediction_latency_ms'],
                    drift_score=row['drift_score']
                )
                self.metrics_history.append(metrics)
                
            self.logger.info(f"Loaded {len(self.metrics_history)} metrics from {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error loading metrics history: {e}")
    
    def save_metrics_history(self, file_path: Path):
        """Save metrics history to CSV file."""
        if not self.metrics_history:
            return
            
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        df = pd.DataFrame([asdict(m) for m in self.metrics_history])
        df.to_csv(file_path, index=False)
        
        self.logger.info(f"Saved {len(self.metrics_history)} metrics to {file_path}")
    
    def load_alerts_log(self, file_path: Path):
        """Load alerts history from JSON file."""
        try:
            with open(file_path, 'r') as f:
                alerts_data = json.load(f)
                
            self.alerts_history.clear()
            
            for alert_data in alerts_data:
                alert = AlertEvent(**alert_data)
                self.alerts_history.append(alert)
                
            self.logger.info(f"Loaded {len(self.alerts_history)} alerts from {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error loading alerts log: {e}")
    
    def save_alerts_log(self, file_path: Path):
        """Save alerts history to JSON file."""
        if not self.alerts_history:
            return
            
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        alerts_data = [asdict(a) for a in self.alerts_history]
        
        with open(file_path, 'w') as f:
            json.dump(alerts_data, f, indent=2)
            
        self.logger.info(f"Saved {len(self.alerts_history)} alerts to {file_path}")
    
    def update_alert_thresholds(self, new_thresholds: Dict[str, float]):
        """Update alert thresholds."""
        self.config['alert_thresholds'].update(new_thresholds)
        self.logger.info(f"Updated alert thresholds: {new_thresholds}")
    
    def reset_monitoring_state(self):
        """Reset monitoring state (for testing or redeployment)."""
        self.metrics_history.clear()
        self.alerts_history.clear()
        self.alert_cooldowns.clear()
        self.baseline_metrics = None
        self.logger.info("Monitoring state reset")
    
    def run_walk_forward_validation(
        self,
        data: pd.DataFrame,
        ticker: str = 'UNKNOWN',
        ensemble: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Run walk-forward validation and check for performance degradation.
        
        Args:
            data: DataFrame with OHLC data
            ticker: Ticker symbol
            ensemble: HybridEnsemble instance (optional)
        
        Returns:
            Validation summary dict or None if validation fails
        """
        try:
            from ..core.walk_forward_validation import WalkForwardValidator
            
            # Initialize validator
            validator_config = self.config.get('walk_forward_validation', {})
            validator = WalkForwardValidator(
                initial_train_size=validator_config.get('initial_train_size', 200),
                test_size=validator_config.get('test_size', 15),
                step_size=validator_config.get('step_size', 5),
                window_type=validator_config.get('window_type', 'expanding'),
                storage_path=Path(validator_config.get('storage_path', 'validation_results'))
            )
            
            # Run validation
            summary = validator.validate_ensemble(data, ticker=ticker, ensemble=ensemble, save_results=True)
            
            # Check for performance degradation
            alert_threshold = validator_config.get('alert_threshold_mae_increase', 15.0)
            
            if self.baseline_metrics and summary.mean_mae > 0:
                mae_increase_pct = (summary.mean_mae - self.baseline_metrics.mae) / self.baseline_metrics.mae * 100
                
                if mae_increase_pct > alert_threshold:
                    from .production_monitor import AlertEvent
                    
                    alert = AlertEvent(
                        timestamp=summary.timestamp,
                        alert_type='walk_forward_degradation',
                        severity='HIGH',
                        message=f"Walk-forward validation shows {mae_increase_pct:.1f}% MAE increase",
                        metric_value=mae_increase_pct,
                        threshold=alert_threshold
                    )
                    
                    if self._can_alert('walk_forward_degradation'):
                        self.alerts_history.append(alert)
                        self._log_alert(alert)
                        self.logger.warning(
                            f"🚨 Walk-forward validation alert: {mae_increase_pct:.1f}% MAE increase"
                        )
            
            self.logger.info(
                f"Walk-forward validation complete: MAE={summary.mean_mae:.2f}, "
                f"Dir Acc={summary.mean_directional_accuracy:.1f}%"
            )
            
            return {
                'ticker': summary.ticker,
                'timestamp': summary.timestamp,
                'total_windows': summary.total_windows,
                'mean_mae': summary.mean_mae,
                'mean_rmse': summary.mean_rmse,
                'mean_directional_accuracy': summary.mean_directional_accuracy,
                'stable_windows': summary.stable_windows,
                'volatile_windows': summary.volatile_windows
            }
            
        except Exception as e:
            self.logger.error(f"Walk-forward validation failed: {e}")
            return None
    
    def schedule_weekly_validation(self, data: pd.DataFrame, ticker: str, ensemble: Optional[Any] = None):
        """
        Schedule weekly walk-forward validation (call on Mondays).
        
        Example usage:
            if datetime.now().weekday() == 0:  # Monday
                monitor.schedule_weekly_validation(data, 'CRWD', ensemble)
        """
        from datetime import datetime
        
        if datetime.now().weekday() == 0:  # Monday
            self.logger.info("\n=== Running Weekly Walk-Forward Validation ===")
            results = self.run_walk_forward_validation(data, ticker=ticker, ensemble=ensemble)
            
            if results:
                self.logger.info(
                    f"✓ Weekly validation complete: "
                    f"MAE={results['mean_mae']:.2f}, "
                    f"Dir Acc={results['mean_directional_accuracy']:.1f}%"
                )
            else:
                self.logger.warning("✗ Weekly validation failed")
        else:
            self.logger.debug("Not Monday - skipping weekly validation")