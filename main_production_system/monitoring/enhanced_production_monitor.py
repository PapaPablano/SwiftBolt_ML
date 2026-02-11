#!/usr/bin/env python3
"""
Enhanced Production Monitor with Regime-Specific Validation

This module provides comprehensive production monitoring with:
- Regime-specific model validation
- Advanced directional accuracy tracking
- Performance degradation alerts
- Automated model retraining triggers
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import joblib

# Add the main production system to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.walk_forward_validation import WalkForwardValidator
from core.regime_specific_ensemble import RegimeSpecificEnsemble
from core.advanced_directional_features import AdvancedDirectionalFeatures

logger = logging.getLogger(__name__)


class EnhancedProductionMonitor:
    """
    Enhanced production monitor with regime-specific validation and alerts.
    """
    
    def __init__(self, config_path: str = "config/production_config.json"):
        self.config_path = Path(config_path)
        self.load_config()
        
        # Initialize components
        self.validator = WalkForwardValidator(
            initial_train_size=self.config['validation']['initial_train_size'],
            test_size=self.config['validation']['test_size'],
            step_size=self.config['validation']['step_size'],
            window_type=self.config['validation']['window_type']
        )
        
        self.regime_ensemble = RegimeSpecificEnsemble(
            model_dir=self.config['models']['regime_specific_dir']
        )
        
        self.advanced_features = AdvancedDirectionalFeatures()
        
        # Load models
        self.load_models()
        
        # Performance thresholds
        self.thresholds = self.config['monitoring']['thresholds']
        
        # Alert history
        self.alert_history = []
        
    def load_config(self):
        """Load production configuration."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        else:
            # Default configuration
            self.config = {
                "validation": {
                    "initial_train_size": 200,
                    "test_size": 15,
                    "step_size": 5,
                    "window_type": "expanding"
                },
                "models": {
                    "regime_specific_dir": "models/regime_specific",
                    "directional_model": "xgboost_directional_model.pkl",
                    "advanced_model": "xgboost_advanced_directional_model.pkl"
                },
                "monitoring": {
                    "thresholds": {
                        "directional_accuracy": {
                            "LOW": 52.0,
                            "MEDIUM": 55.0,
                            "HIGH": 58.0
                        },
                        "mae_percentage": {
                            "LOW": 3.0,
                            "MEDIUM": 4.0,
                            "HIGH": 6.0
                        },
                        "degradation_threshold": 5.0
                    },
                    "alert_cooldown_hours": 24,
                    "retrain_threshold": 10.0
                }
            }
    
    def load_models(self):
        """Load all production models."""
        try:
            # Load regime-specific ensemble
            if not self.regime_ensemble.load_models():
                logger.warning("Failed to load regime-specific ensemble")
            
            # Load directional model
            directional_path = Path(self.config['models']['directional_model'])
            if directional_path.exists():
                self.directional_model = joblib.load(directional_path)
                logger.info("✓ Loaded directional XGBoost model")
            else:
                logger.warning(f"Directional model not found: {directional_path}")
                self.directional_model = None
            
            # Load advanced model
            advanced_path = Path(self.config['models']['advanced_model'])
            if advanced_path.exists():
                self.advanced_model = joblib.load(advanced_path)
                logger.info("✓ Loaded advanced directional XGBoost model")
            else:
                logger.warning(f"Advanced model not found: {advanced_path}")
                self.advanced_model = None
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    def create_engineered_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create engineered features for production data."""
        # Create a copy to avoid modifying original
        df = df.copy()
        
        # Basic technical indicators
        df['close_lag_1'] = df['close'].shift(1)
        df['close_lag_2'] = df['close'].shift(2)
        df['close_lag_5'] = df['close'].shift(5)
        df['close_lag_10'] = df['close'].shift(10)
        
        # Returns
        df['close_return_1'] = df['close'].pct_change(1)
        df['close_return_5'] = df['close'].pct_change(5)
        df['close_return_10'] = df['close'].pct_change(10)
        
        # Moving averages
        df['close_ma_5'] = df['close'].rolling(5).mean()
        df['close_ma_10'] = df['close'].rolling(10).mean()
        df['close_ma_20'] = df['close'].rolling(20).mean()
        
        # Standard deviations
        df['close_std_5'] = df['close'].rolling(5).std()
        df['close_std_10'] = df['close'].rolling(10).std()
        df['close_std_20'] = df['close'].rolling(20).std()
        
        # Volume moving averages
        if 'volume' in df.columns:
            df['volume_ma_5'] = df['volume'].rolling(5).mean()
            df['volume_ma_10'] = df['volume'].rolling(10).mean()
            df['volume_ma_20'] = df['volume'].rolling(20).mean()
        else:
            # Create dummy volume columns if not present
            df['volume'] = 1000000
            df['volume_ma_5'] = df['volume'].rolling(5).mean()
            df['volume_ma_10'] = df['volume'].rolling(10).mean()
            df['volume_ma_20'] = df['volume'].rolling(20).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['close_rsi_14'] = 100 - (100 / (1 + rs))
        
        # KDJ
        low_min = df['low'].rolling(window=9).min()
        high_max = df['high'].rolling(window=9).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        df['close_kdj_k'] = rsv.ewm(com=2).mean()
        df['close_kdj_d'] = df['close_kdj_k'].ewm(com=2).mean()
        df['close_kdj_j'] = 3 * df['close_kdj_k'] - 2 * df['close_kdj_d']
        
        # MACD
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        df['close_macd'] = exp1 - exp2
        df['close_macd_signal'] = df['close_macd'].ewm(span=9).mean()
        
        # Bollinger Bands
        bb_middle = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['close_bollinger_upper'] = bb_middle + (bb_std * 2)
        df['close_bollinger_lower'] = bb_middle - (bb_std * 2)
        
        # Target (next period close)
        df['target'] = df['close'].shift(-1)
        
        # Remove columns that are all NaN or mostly NaN
        nan_threshold = 0.5
        nan_ratio = df.isnull().sum() / len(df)
        columns_to_drop = nan_ratio[nan_ratio > nan_threshold].index
        df = df.drop(columns=columns_to_drop)
        
        # Fill NaN values
        df = df.ffill().bfill()
        df = df.dropna()
        
        return df
    
    def create_advanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create advanced directional features for production data."""
        # Create basic features first
        df = self.create_engineered_features(df)
        
        # Add advanced directional features
        advanced_features = self.advanced_features.create_advanced_directional_features(df)
        
        # Combine features
        feature_cols = [col for col in df.columns if col not in ['timestamp', 'target', 'time', 'volatility_regime']]
        combined_features = pd.concat([df[feature_cols], advanced_features], axis=1)
        
        # Convert object columns to numeric or drop them
        for col in combined_features.columns:
            if combined_features[col].dtype == 'object':
                try:
                    combined_features[col] = pd.to_numeric(combined_features[col], errors='coerce')
                except:
                    combined_features = combined_features.drop(columns=[col])
        
        # Fill NaN values
        combined_features = combined_features.ffill().bfill()
        combined_features = combined_features.dropna()
        
        # Ensure all columns are numeric
        combined_features = combined_features.select_dtypes(include=[np.number])
        
        # Add target back
        combined_features['target'] = df['target'].loc[combined_features.index]
        
        return combined_features
    
    def weekly_revalidation(self, ticker: str, data: pd.DataFrame) -> Dict:
        """
        Run weekly revalidation with regime-specific models.
        
        Args:
            ticker: Stock ticker symbol
            data: Recent market data
            
        Returns:
            Dictionary with validation results and alerts
        """
        logger.info(f"Starting weekly revalidation for {ticker}")
        
        results = {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat(),
            'alerts': [],
            'performance': {},
            'recommendations': []
        }
        
        try:
            # Create features
            engineered_data = self.create_engineered_features(data)
            
            if len(engineered_data) < 100:
                logger.warning(f"Insufficient data for {ticker}: {len(engineered_data)} samples")
                results['alerts'].append({
                    'type': 'WARNING',
                    'message': f'Insufficient data for validation: {len(engineered_data)} samples',
                    'timestamp': datetime.now().isoformat()
                })
                return results
            
            # Run validation with regime-specific ensemble
            summary = self.validator.validate_ensemble(
                data=engineered_data,
                ticker=ticker,
                ensemble=self.regime_ensemble,
                save_results=True
            )
            
            # Analyze performance by regime
            regime_performance = {}
            for regime in ['LOW', 'MEDIUM', 'HIGH']:
                regime_windows = [w for w in summary.window_results 
                                if w.get('volatility_regime') == regime]
                
                if len(regime_windows) > 0:
                    regime_performance[regime] = {
                        'windows': len(regime_windows),
                        'mean_mae': np.mean([w['mae'] for w in regime_windows]),
                        'mean_directional_accuracy': np.mean([w['directional_accuracy'] for w in regime_windows]),
                        'std_directional_accuracy': np.std([w['directional_accuracy'] for w in regime_windows])
                    }
            
            results['performance'] = {
                'overall': {
                    'mean_mae': summary.mean_mae,
                    'mean_directional_accuracy': summary.mean_directional_accuracy,
                    'total_windows': summary.total_windows
                },
                'regime_specific': regime_performance
            }
            
            # Check for performance degradation
            self.check_performance_degradation(ticker, regime_performance, results)
            
            # Generate recommendations
            self.generate_recommendations(ticker, regime_performance, results)
            
            logger.info(f"✓ Weekly revalidation completed for {ticker}")
            logger.info(f"  Overall Directional Accuracy: {summary.mean_directional_accuracy:.1f}%")
            logger.info(f"  Regime Distribution: {summary.low_windows} low, {summary.medium_windows} medium, {summary.high_windows} high")
            
        except Exception as e:
            logger.error(f"❌ Weekly revalidation failed for {ticker}: {e}")
            results['alerts'].append({
                'type': 'ERROR',
                'message': f'Validation failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
        
        return results
    
    def check_performance_degradation(self, ticker: str, regime_performance: Dict, results: Dict):
        """Check for performance degradation and generate alerts."""
        thresholds = self.thresholds['directional_accuracy']
        
        for regime, performance in regime_performance.items():
            if regime in thresholds:
                current_acc = performance['mean_directional_accuracy']
                threshold = thresholds[regime]
                
                if current_acc < threshold:
                    degradation = threshold - current_acc
                    
                    alert = {
                        'type': 'PERFORMANCE_DEGRADATION',
                        'severity': 'HIGH' if degradation > 10 else 'MEDIUM',
                        'message': f'{regime} regime directional accuracy {current_acc:.1f}% below threshold {threshold}% (degradation: {degradation:.1f}%)',
                        'ticker': ticker,
                        'regime': regime,
                        'current_accuracy': current_acc,
                        'threshold': threshold,
                        'degradation': degradation,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    results['alerts'].append(alert)
                    
                    # Check if retraining is needed
                    if degradation > self.config['monitoring']['retrain_threshold']:
                        results['recommendations'].append({
                            'type': 'RETRAIN_MODEL',
                            'priority': 'HIGH',
                            'message': f'Consider retraining {regime} regime model - degradation {degradation:.1f}% exceeds retrain threshold',
                            'regime': regime
                        })
    
    def generate_recommendations(self, ticker: str, regime_performance: Dict, results: Dict):
        """Generate recommendations based on performance analysis."""
        # Check for regime-specific issues
        for regime, performance in regime_performance.items():
            windows = performance['windows']
            accuracy = performance['mean_directional_accuracy']
            
            if windows < 5:
                results['recommendations'].append({
                    'type': 'INSUFFICIENT_DATA',
                    'priority': 'MEDIUM',
                    'message': f'Insufficient {regime} regime data ({windows} windows) - consider extending validation period',
                    'regime': regime
                })
            
            if accuracy < 45:
                results['recommendations'].append({
                    'type': 'POOR_PERFORMANCE',
                    'priority': 'HIGH',
                    'message': f'{regime} regime showing poor performance ({accuracy:.1f}%) - investigate model parameters',
                    'regime': regime
                })
        
        # Overall recommendations
        overall_acc = results['performance']['overall']['mean_directional_accuracy']
        if overall_acc < 50:
            results['recommendations'].append({
                'type': 'OVERALL_PERFORMANCE',
                'priority': 'HIGH',
                'message': f'Overall directional accuracy {overall_acc:.1f}% below 50% - consider model retraining',
                'regime': 'ALL'
            })
    
    def send_alert(self, alert: Dict):
        """Send alert notification (placeholder for actual implementation)."""
        logger.warning(f"ALERT [{alert['type']}]: {alert['message']}")
        
        # In a real implementation, this would send emails, Slack messages, etc.
        # For now, we'll just log and store the alert
        self.alert_history.append(alert)
        
        # Save alert to file
        alert_file = Path('monitoring_reports/alerts.json')
        alert_file.parent.mkdir(exist_ok=True)
        
        if alert_file.exists():
            with open(alert_file, 'r') as f:
                alerts = json.load(f)
        else:
            alerts = []
        
        alerts.append(alert)
        
        with open(alert_file, 'w') as f:
            json.dump(alerts, f, indent=2)
    
    def generate_monitoring_report(self, results: Dict) -> str:
        """Generate a comprehensive monitoring report."""
        report = []
        report.append("=" * 80)
        report.append("ENHANCED PRODUCTION MONITORING REPORT")
        report.append("=" * 80)
        report.append(f"Timestamp: {results['timestamp']}")
        report.append(f"Ticker: {results['ticker']}")
        report.append("")
        
        # Performance Summary
        perf = results['performance']['overall']
        report.append("OVERALL PERFORMANCE:")
        report.append(f"  Mean MAE: {perf['mean_mae']:.3f}")
        report.append(f"  Mean Directional Accuracy: {perf['mean_directional_accuracy']:.1f}%")
        report.append(f"  Total Windows: {perf['total_windows']}")
        report.append("")
        
        # Regime-Specific Performance
        report.append("REGIME-SPECIFIC PERFORMANCE:")
        for regime, perf in results['performance']['regime_specific'].items():
            report.append(f"  {regime} Regime:")
            report.append(f"    Windows: {perf['windows']}")
            report.append(f"    Directional Accuracy: {perf['mean_directional_accuracy']:.1f}% ± {perf['std_directional_accuracy']:.1f}%")
            report.append(f"    MAE: {perf['mean_mae']:.3f}")
        report.append("")
        
        # Alerts
        if results['alerts']:
            report.append("ALERTS:")
            for alert in results['alerts']:
                report.append(f"  [{alert['type']}] {alert['message']}")
        else:
            report.append("ALERTS: None")
        report.append("")
        
        # Recommendations
        if results['recommendations']:
            report.append("RECOMMENDATIONS:")
            for rec in results['recommendations']:
                report.append(f"  [{rec['priority']}] {rec['message']}")
        else:
            report.append("RECOMMENDATIONS: None")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_monitoring_report(self, results: Dict):
        """Save monitoring report to file."""
        report = self.generate_monitoring_report(results)
        
        # Save to monitoring reports directory
        reports_dir = Path('monitoring_reports')
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = reports_dir / f"monitoring_report_{results['ticker']}_{timestamp}.txt"
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        logger.info(f"✓ Monitoring report saved to: {report_file}")
        
        return report_file


def main():
    """Main function for testing the enhanced production monitor."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize monitor
    monitor = EnhancedProductionMonitor()
    
    # Test with sample data (you would load real production data here)
    logger.info("Enhanced Production Monitor initialized")
    logger.info("Ready for production monitoring with regime-specific validation")
    
    # Example usage:
    # results = monitor.weekly_revalidation('CRWD', production_data)
    # monitor.save_monitoring_report(results)


if __name__ == "__main__":
    main()
