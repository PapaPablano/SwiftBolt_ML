#!/usr/bin/env python3
"""
Blind Walk-Forward Validation on Held-Out Data

Tests the production ensemble pipeline on data that was NEVER used for training,
tuning, or feature selection. This is the gold standard for model validation.

Usage:
    python scripts/blind_walk_forward_validation.py --symbols AAPL,MSFT,SPY \
        --holdout-start 2025-10-15 --holdout-end 2026-02-03 \
        --horizons 1D,5D,10D,20D

The script:
1. Holds out data from holdout_start to holdout_end
2. For each day in holdout period:
   - Trains ensemble on ALL data BEFORE that day
   - Makes predictions for 1D/5D/10D/20D horizons
   - Records predictions
3. Calculates accuracy metrics by comparing to actual outcomes
4. Generates validation report
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings
from src.data.supabase_db import db
from src.features.adaptive_thresholds import AdaptiveThresholds
from src.models.baseline_forecaster import BaselineForecaster
from src.models.tabpfn_forecaster import TabPFNForecaster, is_tabpfn_available

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


class BlindWalkForwardValidator:
    """Validates model on held-out future data using expanding window."""
    
    def __init__(
        self,
        symbols: List[str],
        holdout_start: str,
        holdout_end: str,
        horizons: List[str],
        model_type: str = 'baseline',
    ):
        """
        Initialize validator.
        
        Args:
            symbols: List of symbols to test (e.g., ['AAPL', 'MSFT', 'SPY'])
            holdout_start: Start date of holdout period (e.g., '2025-10-15')
            holdout_end: End date of holdout period (e.g., '2026-02-03')
            horizons: List of horizons to test (e.g., ['1D', '5D', '10D', '20D'])
            model_type: 'baseline' or 'tabpfn'
        """
        self.symbols = symbols
        self.holdout_start = pd.Timestamp(holdout_start)
        self.holdout_end = pd.Timestamp(holdout_end)
        self.horizons = horizons
        self.model_type = model_type
        
        # Convert horizons to days
        self.horizon_days = {
            '1D': 1,
            '5D': 5,
            '10D': 10,
            '20D': 20,
        }
        
        logger.info(f"Initialized BlindWalkForwardValidator:")
        logger.info(f"  Symbols: {symbols}")
        logger.info(f"  Holdout: {holdout_start} to {holdout_end}")
        logger.info(f"  Horizons: {horizons}")
        logger.info(f"  Model: {model_type}")
    
    def load_data(self, symbol: str) -> pd.DataFrame:
        """Load all available OHLC data for symbol."""
        logger.info(f"Loading data for {symbol}...")
        df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=1000)
        if df is None or len(df) == 0:
            raise ValueError(f"No data found for {symbol}")
        
        df['ts'] = pd.to_datetime(df['ts'])
        df = df.sort_values('ts').reset_index(drop=True)
        logger.info(f"  Loaded {len(df)} bars from {df['ts'].min()} to {df['ts'].max()}")
        return df
    
    def get_training_data_for_date(self, df: pd.DataFrame, test_date: pd.Timestamp) -> pd.DataFrame:
        """
        Get all data BEFORE test_date for training.
        
        This ensures no look-ahead bias - we only use data that would have been
        available at prediction time.
        """
        train_df = df[df['ts'] < test_date].copy()
        return train_df
    
    def get_actual_return(self, df: pd.DataFrame, test_date: pd.Timestamp, horizon_days: int) -> float:
        """
        Get actual return from test_date to test_date + horizon_days.
        
        Returns:
            Actual return (0.05 = 5% gain, -0.03 = 3% loss)
            Returns None if target date not in data
        """
        target_date = test_date + pd.Timedelta(days=horizon_days)
        
        # Find closest dates
        test_row = df[df['ts'] >= test_date].head(1)
        target_row = df[df['ts'] >= target_date].head(1)
        
        if len(test_row) == 0 or len(target_row) == 0:
            return None
        
        test_price = test_row['close'].iloc[0]
        target_price = target_row['close'].iloc[0]
        
        return (target_price - test_price) / test_price
    
    def train_and_predict(
        self,
        full_df: pd.DataFrame,
        train_df: pd.DataFrame,
        test_date: pd.Timestamp,
        horizon_days: int,
    ) -> Dict:
        """
        Train model on train_df (data before test_date) and make prediction FOR test_date.
        
        Prediction must use data up to and including test_date so we predict the return
        from test_date to test_date+horizon_days, matching how actual_return is computed.
        """
        # Choose model
        if self.model_type == 'tabpfn' and is_tabpfn_available():
            model = TabPFNForecaster()
        else:
            model = BaselineForecaster()
        
        # Prepare training data (only data before test_date)
        try:
            X, y = model.prepare_training_data(train_df, horizon_days=horizon_days)
        except Exception as e:
            logger.warning(f"Failed to prepare training  {e}")
            return {'error': str(e)}
        
        # Train
        min_samples = 100
        if len(X) < min_samples:
            return {'error': f'Insufficient training  {len(X)} < {min_samples}'}
        
        try:
            model.train(X, y, min_samples=min_samples)
        except Exception as e:
            logger.warning(f"Training failed: {e}")
            return {'error': str(e)}
        
        # Predict FOR test_date: use data up to and including test_date so the model
        # predicts return from test_date -> test_date+horizon_days (same as actual_return).
        df_up_to_test = full_df[full_df['ts'] <= test_date].copy()
        if len(df_up_to_test) == 0:
            return {'error': 'No data up to test_date'}
        try:
            result = model.predict(df_up_to_test, horizon_days=horizon_days)
            
            return {
                'label': result.get('label', 'neutral'),
                'confidence': result.get('confidence', 0.0),
                'probabilities': result.get('probabilities', {}),
            }
        except Exception as e:
            logger.warning(f"Prediction failed: {e}")
            return {'error': str(e)}
    
    def validate_symbol(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Run blind walk-forward validation for one symbol.
        
        Returns:
            DataFrame with predictions and actuals for all test dates and horizons
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Validating {symbol}")
        logger.info(f"{'='*60}")
        
        # Load all data
        df = self.load_data(symbol)
        
        # Get trading days in holdout period
        holdout_df = df[(df['ts'] >= self.holdout_start) & (df['ts'] <= self.holdout_end)]
        test_dates = holdout_df['ts'].tolist()
        
        logger.info(f"Testing on {len(test_dates)} trading days in holdout period")
        
        results = []
        
        # For each test date
        for test_date in tqdm(test_dates, desc=f"{symbol} walk-forward"):
            # Get training data (all data BEFORE test_date)
            train_df = self.get_training_data_for_date(df, test_date)
            
            logger.debug(f"Test date: {test_date.date()}, Training samples: {len(train_df)}")
            
            # Test each horizon
            for horizon_str in self.horizons:
                horizon_days = self.horizon_days[horizon_str]
                
                # Train and predict (pass full df so we can predict FOR test_date, not last row of train_df)
                pred = self.train_and_predict(df, train_df, test_date, horizon_days)
                
                if 'error' in pred:
                    logger.debug(f"  {horizon_str}: Error - {pred['error']}")
                    continue
                
                # Get actual outcome
                actual_return = self.get_actual_return(df, test_date, horizon_days)
                
                if actual_return is None:
                    logger.debug(f"  {horizon_str}: No actual data available")
                    continue
                
                # Convert actual return to label using SAME adaptive thresholds as training
                # This is critical - validation must use same thresholds as training!
                bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds_horizon(
                    train_df, horizon_days=horizon_days
                )
                
                logger.debug(
                    f"  {horizon_str}: actual_return={actual_return:.4f}, "
                    f"thresholds=[{bearish_thresh:.4f}, {bullish_thresh:.4f}]"
                )
                
                if actual_return > bullish_thresh:
                    actual_label = 'bullish'
                elif actual_return < bearish_thresh:
                    actual_label = 'bearish'
                else:
                    actual_label = 'neutral'
                
                # Record result
                results.append({
                    'symbol': symbol,
                    'test_date': test_date,
                    'horizon': horizon_str,
                    'horizon_days': horizon_days,
                    'train_samples': len(train_df),
                    'predicted_label': pred['label'],
                    'predicted_confidence': pred['confidence'],
                    'actual_label': actual_label,
                    'actual_return': actual_return,
                    'bearish_threshold': bearish_thresh,
                    'bullish_threshold': bullish_thresh,
                    'correct': pred['label'] == actual_label,
                })
        
        results_df = pd.DataFrame(results)
        
        if len(results_df) > 0:
            logger.info(f"\n{symbol} Results:")
            logger.info(f"  Total predictions: {len(results_df)}")
            logger.info(f"  Accuracy: {results_df['correct'].mean():.1%}")
            
            # Per-horizon accuracy
            for horizon in self.horizons:
                horizon_df = results_df[results_df['horizon'] == horizon]
                if len(horizon_df) > 0:
                    logger.info(f"  {horizon} accuracy: {horizon_df['correct'].mean():.1%} (n={len(horizon_df)})")
        
        return results_df
    
    def run_validation(self) -> pd.DataFrame:
        """
        Run validation for all symbols.
        
        Returns:
            Combined DataFrame with all results
        """
        all_results = []
        
        for symbol in self.symbols:
            try:
                symbol_results = self.validate_symbol(symbol)
                all_results.append(symbol_results)
            except Exception as e:
                logger.error(f"Failed to validate {symbol}: {e}")
        
        if not all_results:
            raise ValueError("No validation results generated")
        
        combined_df = pd.concat(all_results, ignore_index=True)
        return combined_df
    
    def generate_report(self, results_df: pd.DataFrame) -> Dict:
        """
        Generate validation report with metrics.
        
        Returns:
            Dict with summary statistics
        """
        if len(results_df) == 0 or 'correct' not in results_df.columns:
            report = {
                'validation_date': datetime.now().isoformat(),
                'holdout_period': {
                    'start': self.holdout_start.isoformat(),
                    'end': self.holdout_end.isoformat(),
                },
                'symbols': self.symbols,
                'horizons': self.horizons,
                'model_type': self.model_type,
                'total_predictions': 0,
                'overall_accuracy': 0.0,
                'note': 'No successful predictions (all failed or no data)',
            }
            return report

        report = {
            'validation_date': datetime.now().isoformat(),
            'holdout_period': {
                'start': self.holdout_start.isoformat(),
                'end': self.holdout_end.isoformat(),
            },
            'symbols': self.symbols,
            'horizons': self.horizons,
            'model_type': self.model_type,
            'total_predictions': len(results_df),
            'overall_accuracy': float(results_df['correct'].mean()),
        }
        
        # Per-symbol accuracy
        report['by_symbol'] = {}
        for symbol in self.symbols:
            symbol_df = results_df[results_df['symbol'] == symbol]
            if len(symbol_df) > 0:
                report['by_symbol'][symbol] = {
                    'accuracy': float(symbol_df['correct'].mean()),
                    'n_predictions': len(symbol_df),
                }
        
        # Per-horizon accuracy
        report['by_horizon'] = {}
        for horizon in self.horizons:
            horizon_df = results_df[results_df['horizon'] == horizon]
            if len(horizon_df) > 0:
                report['by_horizon'][horizon] = {
                    'accuracy': float(horizon_df['correct'].mean()),
                    'n_predictions': len(horizon_df),
                }
        
        # Confidence calibration
        if 'predicted_confidence' in results_df.columns:
            high_conf = results_df[results_df['predicted_confidence'] >= 0.7]
            med_conf = results_df[(results_df['predicted_confidence'] >= 0.5) & 
                                 (results_df['predicted_confidence'] < 0.7)]
            low_conf = results_df[results_df['predicted_confidence'] < 0.5]
            
            report['confidence_calibration'] = {
                'high (>=0.7)': {
                    'accuracy': float(high_conf['correct'].mean()) if len(high_conf) > 0 else None,
                    'n': len(high_conf),
                },
                'medium (0.5-0.7)': {
                    'accuracy': float(med_conf['correct'].mean()) if len(med_conf) > 0 else None,
                    'n': len(med_conf),
                },
                'low (<0.5)': {
                    'accuracy': float(low_conf['correct'].mean()) if len(low_conf) > 0 else None,
                    'n': len(low_conf),
                },
            }
        
        return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Blind walk-forward validation on held-out data'
    )
    parser.add_argument(
        '--symbols',
        default='AAPL,MSFT,SPY',
        help='Comma-separated list of symbols to test (default: AAPL,MSFT,SPY)'
    )
    parser.add_argument(
        '--holdout-start',
        default='2025-10-15',
        help='Start date of holdout period (default: 2025-10-15)'
    )
    parser.add_argument(
        '--holdout-end',
        default='2026-02-03',
        help='End date of holdout period (default: 2026-02-03)'
    )
    parser.add_argument(
        '--horizons',
        default='1D,5D,10D,20D',
        help='Comma-separated horizons to test (default: 1D,5D,10D,20D)'
    )
    parser.add_argument(
        '--model-type',
        choices=['baseline', 'tabpfn'],
        default='baseline',
        help='Model type to test (default: baseline)'
    )
    parser.add_argument(
        '--output-dir',
        default='validation_results',
        help='Output directory for results (default: validation_results)'
    )
    
    args = parser.parse_args()
    
    # Parse arguments
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    horizons = [h.strip().upper() for h in args.horizons.split(',')]
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize validator
    validator = BlindWalkForwardValidator(
        symbols=symbols,
        holdout_start=args.holdout_start,
        holdout_end=args.holdout_end,
        horizons=horizons,
        model_type=args.model_type,
    )
    
    # Run validation
    logger.info("\n" + "="*80)
    logger.info("STARTING BLIND WALK-FORWARD VALIDATION")
    logger.info("="*80)
    
    results_df = validator.run_validation()
    
    # Generate report
    report = validator.generate_report(results_df)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    results_file = output_dir / f'validation_results_{timestamp}.csv'
    results_df.to_csv(results_file, index=False)
    logger.info(f"\n✓ Results saved to: {results_file}")
    
    report_file = output_dir / f'validation_report_{timestamp}.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    logger.info(f"✓ Report saved to: {report_file}")
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("VALIDATION SUMMARY")
    logger.info("="*80)
    logger.info(f"Overall Accuracy: {report['overall_accuracy']:.1%}")
    logger.info(f"Total Predictions: {report['total_predictions']}")
    logger.info(f"\nPer-Symbol Accuracy:")
    for symbol, metrics in report['by_symbol'].items():
        logger.info(f"  {symbol}: {metrics['accuracy']:.1%} (n={metrics['n_predictions']})")
    logger.info(f"\nPer-Horizon Accuracy:")
    for horizon, metrics in report['by_horizon'].items():
        logger.info(f"  {horizon}: {metrics['accuracy']:.1%} (n={metrics['n_predictions']})")
    
    if 'confidence_calibration' in report:
        logger.info(f"\nConfidence Calibration:")
        for bucket, metrics in report['confidence_calibration'].items():
            if metrics['n'] > 0:
                logger.info(f"  {bucket}: {metrics['accuracy']:.1%} (n={metrics['n']})")
    
    logger.info("\n" + "="*80)
    
    # Close database
    db.close()


if __name__ == '__main__':
    main()
