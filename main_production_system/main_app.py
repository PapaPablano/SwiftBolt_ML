#!/usr/bin/env python3
"""
Main Production Application
Runs the complete KDJ-Enhanced ML Analysis Platform.
"""

import sys
import logging
from pathlib import Path
import argparse
from typing import Dict, Any

# Add main system to path
sys.path.append(str(Path(__file__).parent))

from core.hybrid_ensemble import HybridEnsemble
from core.data_processor import DataProcessor
from core.kdj_feature_engineer import KDJFeatureEngineer
from core.xgboost_trainer import XGBoostTrainer
from monitoring.production_monitor import ProductionMonitor
from dashboard.main_dashboard import MainDashboard

class MLAnalysisPlatform:
    """Main production application for ML Analysis Platform."""
    
    def __init__(self, config: Dict[str, Any] = None):
        default_config = self._get_default_config()
        if config:
            # Merge provided config with defaults
            self.config = {**default_config, **config}
        else:
            self.config = default_config
        self.setup_logging()
        
        # Initialize components
        self.ensemble = HybridEnsemble(self.config.get('ensemble', {}))
        monitoring_config = self.config.get('monitoring', {})
        # Ensure monitoring config has all required keys
        if 'monitoring_window' not in monitoring_config:
            monitoring_config['monitoring_window'] = 100
        if 'alert_cooldown' not in monitoring_config:
            monitoring_config['alert_cooldown'] = 300
        if 'drift_detection_window' not in monitoring_config:
            monitoring_config['drift_detection_window'] = 20
        if 'alert_thresholds' not in monitoring_config:
            monitoring_config['alert_thresholds'] = {
                'mae_degradation': 15.0,
                'rmse_degradation': 15.0,
                'accuracy_drop': 50.0,
                'ensemble_improvement': 5.0,
                'drift_threshold': 0.05,
                'latency_threshold': 100.0
            }
        self.monitor = ProductionMonitor(monitoring_config)
        
        self.logger = logging.getLogger(__name__)
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for the platform."""
        return {
            'ensemble': {
                'ensemble_weights': {'xgboost': 0.6, 'arima_garch': 0.4},
                'confidence_threshold': 0.7
            },
            'monitoring': {
                'alert_thresholds': {
                    'mae_degradation': 15.0,
                    'accuracy_drop': 50.0
                }
            },
            'models': {
                'xgboost_path': 'xgboost_tuned_model.pkl',
                'arima_module': None
            },
            'data': {
                'default_data_path': 'CRWD_engineered.csv'
            }
        }
    
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('ml_platform.log')
            ]
        )
    
    def initialize_system(self) -> bool:
        """Initialize the complete system."""
        try:
            self.logger.info("🚀 Initializing ML Analysis Platform...")
            
            # Load models
            xgboost_path = Path(self.config['models']['xgboost_path'])
            if xgboost_path.exists():
                self.ensemble.load_models(xgboost_path)
                self.logger.info("✅ Models loaded successfully")
            else:
                self.logger.warning(f"⚠️ XGBoost model not found: {xgboost_path}")
                return False
            
            # Initialize monitoring
            self.logger.info("✅ Monitoring system initialized")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ System initialization failed: {e}")
            return False
    
    def run_dashboard(self):
        """Run the Streamlit dashboard."""
        self.logger.info("🌐 Starting dashboard...")
        dashboard = MainDashboard()
        dashboard.run()
    
    def run_training(self, data_path: str):
        """Run model training pipeline."""
        self.logger.info(f"🎯 Starting training on {data_path}")
        
        try:
            # Train ensemble
            results = self.ensemble.train_ensemble(data_path)
            
            # Log results
            self.logger.info("✅ Training completed successfully")
            self.logger.info(f"📊 XGBoost MAE: {results['xgboost_results'].get('val_mae', 'N/A')}")
            self.logger.info(f"📊 Ensemble MAE: {results['ensemble_results'].get('ensemble_mae', 'N/A')}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Training failed: {e}")
            return None
    
    def run_batch_predictions(self, input_file: str, output_file: str = None):
        """Run batch predictions on input file."""
        self.logger.info(f"🔮 Running batch predictions on {input_file}")
        
        try:
            # Load data
            data_processor = DataProcessor()
            df = data_processor.load_data(input_file)
            
            # Generate predictions
            prediction = self.ensemble.predict(df)
            
            # Save results
            if output_file:
                results = {
                    'timestamp': prediction.timestamp,
                    'ensemble_forecast': float(prediction.ensemble_forecast),
                    'xgboost_forecast': float(prediction.xgboost_forecast),
                    'arima_forecast': float(prediction.arima_forecast) if prediction.arima_forecast is not None else None,
                    'confidence_score': float(prediction.confidence_score),
                    'directional_signal': prediction.directional_signal
                }
                
                import json
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2)
                    
                self.logger.info(f"✅ Results saved to {output_file}")
            
            return prediction
            
        except Exception as e:
            self.logger.error(f"❌ Batch prediction failed: {e}")
            return None
    
    def run_monitoring_check(self):
        """Run monitoring health check."""
        self.logger.info("🔍 Running monitoring check...")
        
        # Generate mock metrics for demo
        from monitoring.production_monitor import PerformanceMetrics
        import random
        from datetime import datetime
        
        mock_metrics = PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            mae=random.uniform(10, 15),
            rmse=random.uniform(12, 18),
            mape=random.uniform(2, 5),
            directional_accuracy=random.uniform(55, 70),
            ensemble_improvement=random.uniform(5, 15),
            prediction_latency_ms=random.uniform(30, 80),
            drift_score=random.uniform(0.1, 0.8)
        )
        
        # Record metrics
        self.monitor.record_metrics(mock_metrics)
        
        # Generate report
        report = self.monitor.generate_monitoring_report()
        
        self.logger.info("✅ Monitoring check completed")
        print(report)
        
        return report
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        try:
            ensemble_status = self.ensemble.get_model_status()
            health = self.monitor.get_model_health()
            
            return {
                'platform_status': 'OPERATIONAL',
                'ensemble_status': ensemble_status,
                'monitoring_health': health,
                'config': self.config
            }
            
        except Exception as e:
            return {
                'platform_status': 'ERROR',
                'error': str(e)
            }

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ML Analysis Platform - KDJ Enhanced")
    parser.add_argument('--mode', choices=['dashboard', 'train', 'predict', 'monitor', 'status'], 
                       default='dashboard', help='Operation mode')
    parser.add_argument('--data', type=str, help='Data file path')
    parser.add_argument('--output', type=str, help='Output file path')
    parser.add_argument('--config', type=str, help='Configuration file path')
    
    args = parser.parse_args()
    
    # Load configuration if provided
    config = None
    if args.config:
        import json
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Initialize platform
    platform = MLAnalysisPlatform(config)
    
    # Execute based on mode
    if args.mode == 'dashboard':
        print("🌐 Starting dashboard...")
        print("📍 Navigate to: http://localhost:8501")
        platform.run_dashboard()
        
    elif args.mode == 'train':
        if not args.data:
            print("❌ Data file required for training mode")
            return
        
        if platform.initialize_system():
            results = platform.run_training(args.data)
            if results:
                print("✅ Training completed successfully")
            else:
                print("❌ Training failed")
        
    elif args.mode == 'predict':
        if not args.data:
            print("❌ Data file required for prediction mode")
            return
            
        if platform.initialize_system():
            prediction = platform.run_batch_predictions(args.data, args.output)
            if prediction:
                print(f"✅ Prediction: ${prediction.ensemble_forecast:.2f}")
                print(f"📊 Confidence: {prediction.confidence_score:.1%}")
                print(f"📈 Signal: {prediction.directional_signal}")
            else:
                print("❌ Prediction failed")
        
    elif args.mode == 'monitor':
        platform.run_monitoring_check()
        
    elif args.mode == 'status':
        status = platform.get_system_status()
        import json
        print(json.dumps(status, indent=2))

if __name__ == "__main__":
    main()