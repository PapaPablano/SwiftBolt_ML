#!/usr/bin/env python3
"""
Shadow Mode Deployment System for ML Analysis Platform.
Runs production system alongside existing strategy to validate
predictions without executing actual trades.
"""

import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import sqlite3

from .multi_asset_production import MultiAssetProductionSystem
from .regime_specific_ensemble import RegimeSpecificEnsemble

class ShadowModeDeployment:
    """
    Shadow mode deployment for validating predictions without trading.
    """
    
    def __init__(self, db_path: str = "shadow_mode.db"):
        """
        Initialize shadow mode deployment.
        
        Args:
            db_path: Path to SQLite database for logging
        """
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        
        # Initialize production system
        self.production_system = MultiAssetProductionSystem()
        self.ensemble = RegimeSpecificEnsemble()
        
        # Initialize database
        self._init_database()
        
        # Shadow mode configuration
        self.config = {
            'enabled': True,
            'start_date': datetime.now(),
            'evaluation_period_days': 14,
            'min_confidence_threshold': 0.52,
            'max_daily_predictions': 100,
            'evaluation_metrics': [
                'directional_accuracy',
                'mae',
                'rmse',
                'sharpe_ratio',
                'max_drawdown'
            ]
        }
        
        self.logger.info("Shadow Mode Deployment initialized")
    
    def _init_database(self):
        """Initialize SQLite database for shadow mode logging."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shadow_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ticker TEXT NOT NULL,
                regime TEXT NOT NULL,
                prediction REAL NOT NULL,
                confidence REAL NOT NULL,
                actual_return REAL,
                actual_direction INTEGER,
                prediction_direction INTEGER,
                correct_direction INTEGER,
                error REAL,
                executed BOOLEAN DEFAULT FALSE,
                metadata TEXT
            )
        ''')
        
        # Create evaluation results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_date TEXT NOT NULL,
                ticker TEXT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                sample_size INTEGER,
                period_days INTEGER
            )
        ''')
        
        # Create system status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_predictions INTEGER,
                avg_confidence REAL,
                directional_accuracy REAL,
                system_health TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def shadow_predict(self, ticker: str, features: pd.DataFrame, 
                      current_regime: str) -> Dict[str, Any]:
        """
        Make prediction in shadow mode (no actual trading).
        
        Args:
            ticker: Stock ticker symbol
            features: Feature matrix
            current_regime: Current market regime
            
        Returns:
            Dictionary with prediction and metadata
        """
        if not self.config['enabled']:
            return {'error': 'Shadow mode disabled'}
        
        try:
            # Make prediction using production system
            prediction = self.production_system.route_prediction(
                ticker, current_regime, features
            )
            
            # Add shadow mode metadata
            prediction.update({
                'shadow_mode': True,
                'executed': False,
                'timestamp': datetime.now().isoformat()
            })
            
            # Log prediction
            self._log_prediction(ticker, current_regime, prediction)
            
            return prediction
            
        except Exception as e:
            self.logger.error(f"Shadow prediction failed for {ticker}: {e}")
            return {
                'error': str(e),
                'shadow_mode': True,
                'executed': False
            }
    
    def _log_prediction(self, ticker: str, regime: str, prediction: Dict[str, Any]):
        """Log prediction to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO shadow_predictions 
            (timestamp, ticker, regime, prediction, confidence, prediction_direction, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            prediction['timestamp'],
            ticker,
            regime,
            prediction['prediction'],
            prediction['confidence'],
            1 if prediction['prediction'] > 0 else 0,
            json.dumps(prediction)
        ))
        
        conn.commit()
        conn.close()
    
    def update_actual_outcome(self, ticker: str, timestamp: str, 
                            actual_return: float, actual_price: float):
        """
        Update prediction with actual outcome.
        
        Args:
            ticker: Stock ticker symbol
            timestamp: Prediction timestamp
            actual_return: Actual return achieved
            actual_price: Actual price
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate actual direction
        actual_direction = 1 if actual_return > 0 else 0
        
        # Update prediction record
        cursor.execute('''
            UPDATE shadow_predictions 
            SET actual_return = ?, actual_direction = ?, 
                correct_direction = (prediction_direction = ?),
                error = ABS(prediction - ?)
            WHERE ticker = ? AND timestamp = ?
        ''', (actual_return, actual_direction, actual_direction, 
              actual_price, ticker, timestamp))
        
        conn.commit()
        conn.close()
    
    def evaluate_shadow_period(self, days: Optional[int] = None) -> Dict[str, Any]:
        """
        Evaluate shadow mode performance over specified period.
        
        Args:
            days: Number of days to evaluate (default: config period)
            
        Returns:
            Dictionary with evaluation results
        """
        if days is None:
            days = self.config['evaluation_period_days']
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get predictions from evaluation period
        start_date = datetime.now() - timedelta(days=days)
        start_timestamp = start_date.isoformat()
        
        cursor.execute('''
            SELECT * FROM shadow_predictions 
            WHERE timestamp >= ? AND actual_return IS NOT NULL
            ORDER BY timestamp
        ''', (start_timestamp,))
        
        predictions = cursor.fetchall()
        conn.close()
        
        if not predictions:
            return {'error': 'No completed predictions in evaluation period'}
        
        # Calculate metrics
        results = self._calculate_evaluation_metrics(predictions)
        
        # Log evaluation results
        self._log_evaluation_results(results, days)
        
        return results
    
    def _calculate_evaluation_metrics(self, predictions: List[Tuple]) -> Dict[str, Any]:
        """Calculate evaluation metrics from predictions."""
        if not predictions:
            return {}
        
        # Extract data
        actual_returns = [p[6] for p in predictions if p[6] is not None]
        prediction_directions = [p[8] for p in predictions if p[8] is not None]
        actual_directions = [p[7] for p in predictions if p[7] is not None]
        errors = [p[11] for p in predictions if p[11] is not None]
        confidences = [p[5] for p in predictions if p[5] is not None]
        
        # Calculate metrics
        metrics = {}
        
        # Directional accuracy
        if actual_directions and prediction_directions:
            correct = sum(1 for a, p in zip(actual_directions, prediction_directions) if a == p)
            metrics['directional_accuracy'] = correct / len(actual_directions) * 100
        
        # Error metrics
        if errors:
            metrics['mae'] = np.mean(errors)
            metrics['rmse'] = np.sqrt(np.mean([e**2 for e in errors]))
            metrics['max_error'] = max(errors)
        
        # Return metrics
        if actual_returns:
            metrics['mean_return'] = np.mean(actual_returns)
            metrics['std_return'] = np.std(actual_returns)
            metrics['sharpe_ratio'] = metrics['mean_return'] / metrics['std_return'] if metrics['std_return'] > 0 else 0
            metrics['max_drawdown'] = self._calculate_max_drawdown(actual_returns)
        
        # Confidence metrics
        if confidences:
            metrics['avg_confidence'] = np.mean(confidences)
            metrics['confidence_std'] = np.std(confidences)
        
        # Sample size
        metrics['sample_size'] = len(predictions)
        metrics['evaluation_period'] = f"{len(predictions)} predictions"
        
        # Overall assessment
        if metrics.get('directional_accuracy', 0) > 52:
            metrics['assessment'] = '✅ Shadow mode successful, proceed to live trading'
        elif metrics.get('directional_accuracy', 0) > 48:
            metrics['assessment'] = '⚠️ Shadow mode promising, continue optimization'
        else:
            metrics['assessment'] = '❌ Shadow mode below threshold, needs improvement'
        
        return metrics
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown from returns."""
        if not returns:
            return 0
        
        cumulative = np.cumprod([1 + r for r in returns])
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return abs(min(drawdown)) * 100
    
    def _log_evaluation_results(self, results: Dict[str, Any], days: int):
        """Log evaluation results to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        evaluation_date = datetime.now().isoformat()
        
        for metric_name, metric_value in results.items():
            if isinstance(metric_value, (int, float)) and not np.isnan(metric_value):
                cursor.execute('''
                    INSERT INTO evaluation_results 
                    (evaluation_date, metric_name, metric_value, sample_size, period_days)
                    VALUES (?, ?, ?, ?, ?)
                ''', (evaluation_date, metric_name, metric_value, 
                      results.get('sample_size', 0), days))
        
        conn.commit()
        conn.close()
    
    def get_shadow_results(self, ticker: Optional[str] = None) -> Dict[str, Any]:
        """Get shadow mode results for analysis."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if ticker:
            cursor.execute('''
                SELECT * FROM shadow_predictions 
                WHERE ticker = ? AND actual_return IS NOT NULL
                ORDER BY timestamp DESC
            ''', (ticker,))
        else:
            cursor.execute('''
                SELECT * FROM shadow_predictions 
                WHERE actual_return IS NOT NULL
                ORDER BY timestamp DESC
            ''')
        
        predictions = cursor.fetchall()
        conn.close()
        
        if not predictions:
            return {'error': 'No completed predictions found'}
        
        return self._calculate_evaluation_metrics(predictions)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get recent predictions
        recent_date = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute('''
            SELECT COUNT(*), AVG(confidence), 
                   SUM(CASE WHEN correct_direction = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
            FROM shadow_predictions 
            WHERE timestamp >= ?
        ''', (recent_date,))
        
        stats = cursor.fetchone()
        conn.close()
        
        total_predictions, avg_confidence, directional_accuracy = stats
        
        # Determine system health
        if directional_accuracy and directional_accuracy > 55:
            health = "Excellent"
        elif directional_accuracy and directional_accuracy > 52:
            health = "Good"
        elif directional_accuracy and directional_accuracy > 48:
            health = "Fair"
        else:
            health = "Poor"
        
        return {
            'total_predictions': total_predictions or 0,
            'avg_confidence': avg_confidence or 0,
            'directional_accuracy': directional_accuracy or 0,
            'system_health': health,
            'shadow_mode_active': self.config['enabled'],
            'evaluation_period_days': self.config['evaluation_period_days']
        }
    
    def generate_shadow_report(self, output_path: str):
        """Generate comprehensive shadow mode report."""
        # Get evaluation results
        results = self.evaluate_shadow_period()
        health = self.get_system_health()
        
        # Generate report
        report = {
            'report_timestamp': datetime.now().isoformat(),
            'evaluation_period_days': self.config['evaluation_period_days'],
            'system_health': health,
            'performance_metrics': results,
            'recommendations': self._generate_recommendations(results)
        }
        
        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.logger.info(f"Shadow mode report saved to {output_path}")
        return report
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on shadow mode results."""
        recommendations = []
        
        directional_accuracy = results.get('directional_accuracy', 0)
        sample_size = results.get('sample_size', 0)
        
        if sample_size < 50:
            recommendations.append("Increase sample size - need at least 50 predictions for reliable evaluation")
        
        if directional_accuracy > 55:
            recommendations.append("✅ Excellent performance - ready for live trading")
            recommendations.append("Consider increasing position sizes gradually")
        elif directional_accuracy > 52:
            recommendations.append("✅ Good performance - proceed to limited live trading")
            recommendations.append("Start with LOW regime only, small position sizes")
        elif directional_accuracy > 48:
            recommendations.append("⚠️ Promising performance - continue optimization")
            recommendations.append("Focus on improving MEDIUM regime predictions")
        else:
            recommendations.append("❌ Performance below threshold - needs improvement")
            recommendations.append("Review feature engineering and model selection")
            recommendations.append("Consider ensemble methods or additional data")
        
        # Specific recommendations based on metrics
        if results.get('mae', 0) > 10:
            recommendations.append("High MAE - consider improving point predictions")
        
        if results.get('sharpe_ratio', 0) < 0.5:
            recommendations.append("Low Sharpe ratio - consider risk management improvements")
        
        if results.get('max_drawdown', 0) > 20:
            recommendations.append("High drawdown - implement better risk controls")
        
        return recommendations

# Example usage
if __name__ == "__main__":
    # Initialize shadow mode
    shadow = ShadowModeDeployment()
    
    # Example shadow prediction
    features = pd.DataFrame({
        'close': [100.0],
        'volume': [1000000],
        'rsi': [50.0],
        'macd': [0.1]
    })
    
    # Make shadow prediction
    prediction = shadow.shadow_predict('CRWD', features, 'LOW')
    print(f"Shadow prediction: {prediction}")
    
    # Simulate actual outcome (in practice, this would come from market data)
    actual_return = 0.02  # 2% return
    actual_price = 102.0
    
    # Update with actual outcome
    shadow.update_actual_outcome('CRWD', prediction['timestamp'], actual_return, actual_price)
    
    # Evaluate shadow period
    results = shadow.evaluate_shadow_period()
    print(f"Shadow evaluation results: {results}")
    
    # Get system health
    health = shadow.get_system_health()
    print(f"System health: {health}")
    
    # Generate report
    report = shadow.generate_shadow_report('shadow_mode_report.json')
    print(f"Shadow report generated: {report['recommendations']}")
