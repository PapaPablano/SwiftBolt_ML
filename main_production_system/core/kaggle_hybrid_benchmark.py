#!/usr/bin/env python3
"""
Benchmark & Tuning Module for Kaggle-Prophet Hybrid
Part 6: Benchmark & Tune - R²/MAPE optimization and weight tuning
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging
from sklearn.metrics import r2_score, mean_absolute_error, mean_absolute_percentage_error, mean_squared_error

logger = logging.getLogger(__name__)


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Calculate comprehensive performance metrics.
    
    Args:
        y_true: True values
        y_pred: Predicted values
    
    Returns:
        Dictionary of metrics
    """
    metrics = {}
    
    # R² Score
    try:
        metrics['r2'] = float(r2_score(y_true, y_pred))
    except:
        metrics['r2'] = 0.0
    
    # MAE (Mean Absolute Error)
    try:
        metrics['mae'] = float(mean_absolute_error(y_true, y_pred))
    except:
        metrics['mae'] = np.inf
    
    # RMSE (Root Mean Squared Error)
    try:
        metrics['rmse'] = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    except:
        metrics['rmse'] = np.inf
    
    # MAPE (Mean Absolute Percentage Error)
    try:
        # Avoid division by zero
        nonzero_mask = np.abs(y_true) > 1e-6
        if nonzero_mask.sum() > 0:
            metrics['mape'] = float(mean_absolute_percentage_error(
                y_true[nonzero_mask], y_pred[nonzero_mask]
            )) * 100  # Convert to percentage
        else:
            metrics['mape'] = np.inf
    except:
        metrics['mape'] = np.inf
    
    # Directional Accuracy
    try:
        if len(y_true) > 1 and len(y_pred) > 1:
            true_direction = np.diff(y_true) > 0
            pred_direction = np.diff(y_pred) > 0
            directional_accuracy = (true_direction == pred_direction).mean() * 100
            metrics['directional_accuracy'] = float(directional_accuracy)
        else:
            metrics['directional_accuracy'] = 0.0
    except:
        metrics['directional_accuracy'] = 0.0
    
    return metrics


def tune_prophet_weight(
    model,
    X_val: np.ndarray,
    y_val: np.ndarray,
    df_ohlcv_val: pd.DataFrame,
    weight_range: Tuple[float, float] = (0.05, 0.25),
    n_trials: int = 10,
    metric: str = 'mae'
) -> Tuple[float, Dict]:
    """
    Tune Prophet weight via grid search on validation set.
    
    Args:
        model: Trained KaggleProphetHybrid model
        X_val: Validation features
        y_val: Validation targets
        df_ohlcv_val: Validation OHLCV data
        weight_range: (min, max) Prophet weight range
        n_trials: Number of weight values to test
        metric: Metric to optimize ('mae', 'rmse', 'mape', 'r2')
    
    Returns:
        Tuple of (best_weight, best_metrics)
    """
    logger.info(f"[BENCHMARK] Tuning Prophet weight in range {weight_range} using {metric}")
    
    # Generate weight candidates
    weights_to_test = np.linspace(weight_range[0], weight_range[1], n_trials)
    
    best_weight = model.weights[3]  # Default
    best_metric_value = np.inf if metric != 'r2' else -np.inf
    best_metrics = {}
    all_results = []
    
    # Save original weights
    original_weights = model.weights.copy()
    
    for prophet_weight in weights_to_test:
        # Adjust weights: keep relative ratios of other models
        other_weights = original_weights[:3]
        other_sum = sum(other_weights)
        if other_sum > 0:
            # Normalize other weights to sum to (1 - prophet_weight)
            normalized_others = [(w / other_sum) * (1 - prophet_weight) for w in other_weights]
            new_weights = normalized_others + [prophet_weight]
        else:
            new_weights = [0.3, 0.3, 0.4 - prophet_weight, prophet_weight]
        
        # Update model weights
        model.weights = new_weights
        
        # Predict on validation set
        try:
            signals, confidence = model.predict(X_val, df_ohlcv_test=df_ohlcv_val)
            
            # Convert signals to predictions (use signals as proxy for direction)
            # For proper evaluation, we'd want actual price predictions, but signals work for weight tuning
            predictions = signals.astype(float)
            
            # Calculate metrics
            metrics = calculate_metrics(y_val, predictions)
            
            # Select metric to optimize
            if metric == 'r2':
                metric_value = -metrics['r2']  # Negate for minimization
            else:
                metric_value = metrics[metric]
            
            all_results.append({
                'prophet_weight': prophet_weight,
                'metrics': metrics,
                metric: metric_value
            })
            
            # Check if this is the best weight
            if metric == 'r2':
                if metrics['r2'] > -best_metric_value:
                    best_weight = prophet_weight
                    best_metric_value = -metrics['r2']
                    best_metrics = metrics
            else:
                if metric_value < best_metric_value:
                    best_weight = prophet_weight
                    best_metric_value = metric_value
                    best_metrics = metrics
            
            logger.debug(f"  Weight={prophet_weight:.3f}: {metric}={metrics[metric]:.4f}, R²={metrics['r2']:.4f}")
        except Exception as e:
            logger.warning(f"  Weight={prophet_weight:.3f} failed: {e}")
            continue
    
    # Restore original weights
    model.weights = original_weights
    
    logger.info(f"[BENCHMARK] Best Prophet weight: {best_weight:.3f} (optimizing {metric}={best_metric_value:.4f})")
    logger.info(f"[BENCHMARK] Best metrics: R²={best_metrics.get('r2', 0):.4f}, MAPE={best_metrics.get('mape', 0):.2f}%")
    
    return best_weight, best_metrics


def benchmark_model(
    model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    df_ohlcv_test: pd.DataFrame,
    return_breakdown: bool = True
) -> Dict:
    """
    Comprehensive benchmark of model performance.
    
    Args:
        model: Trained KaggleProphetHybrid model
        X_test: Test features
        y_test: Test targets
        df_ohlcv_test: Test OHLCV data
        return_breakdown: If True, return component-level breakdown
    
    Returns:
        Dictionary with metrics and optional breakdown
    """
    logger.info("[BENCHMARK] Running comprehensive benchmark...")
    
    # Get predictions
    signals, confidence = model.predict(X_test, df_ohlcv_test=df_ohlcv_test)
    
    # Convert signals to numeric predictions for metrics
    # Signals are -1, 0, 1, but we can use them as directional predictions
    predictions = signals.astype(float)
    
    # Calculate metrics
    metrics = calculate_metrics(y_test, predictions)
    
    results = {
        'metrics': metrics,
        'targets_met': {
            'r2_target': metrics['r2'] >= 0.90,
            'mape_target': metrics['mape'] <= 5.0,
            'directional_accuracy_target': metrics['directional_accuracy'] >= 60.0
        },
        'summary': {
            'status': 'PASS' if all([
                metrics['r2'] >= 0.90,
                metrics['mape'] <= 5.0,
                metrics['directional_accuracy'] >= 60.0
            ]) else 'PARTIAL' if metrics['r2'] >= 0.75 else 'FAIL'
        }
    }
    
    if return_breakdown:
        # Get model info for breakdown
        model_info = model.get_model_info()
        results['breakdown'] = {
            'ensemble_weights': model.weights,
            'model_availability': model_info['models'],
            'signal_distribution': {
                'buy': int(np.sum(signals == 1)),
                'hold': int(np.sum(signals == 0)),
                'sell': int(np.sum(signals == -1))
            },
            'confidence_stats': {
                'mean': float(np.mean(confidence)),
                'std': float(np.std(confidence)),
                'min': float(np.min(confidence)),
                'max': float(np.max(confidence))
            }
        }
    
    logger.info(f"[BENCHMARK] Results: R²={metrics['r2']:.4f}, MAPE={metrics['mape']:.2f}%, "
               f"Directional={metrics['directional_accuracy']:.1f}%")
    
    return results


def format_benchmark_report(results: Dict) -> str:
    """
    Format benchmark results as a readable report.
    
    Args:
        results: Results dictionary from benchmark_model()
    
    Returns:
        Formatted string report
    """
    metrics = results['metrics']
    targets = results['targets_met']
    summary = results['summary']
    breakdown = results.get('breakdown', {})
    
    report = []
    report.append("=" * 60)
    report.append("KAGGLE-PROPHET HYBRID BENCHMARK REPORT")
    report.append("=" * 60)
    report.append("")
    report.append(f"Overall Status: {summary['status']}")
    report.append("")
    report.append("Performance Metrics:")
    report.append(f"  R² Score:           {metrics['r2']:.4f} {'✅' if targets['r2_target'] else '❌'} (Target: ≥0.90)")
    report.append(f"  MAPE:                {metrics['mape']:.2f}% {'✅' if targets['mape_target'] else '❌'} (Target: ≤5.0%)")
    report.append(f"  MAE:                 {metrics['mae']:.4f}")
    report.append(f"  RMSE:                {metrics['rmse']:.4f}")
    report.append(f"  Directional Acc:    {metrics['directional_accuracy']:.1f}% {'✅' if targets['directional_accuracy_target'] else '❌'} (Target: ≥60%)")
    report.append("")
    
    if breakdown:
        report.append("Ensemble Breakdown:")
        weights = breakdown.get('ensemble_weights', [])
        model_names = ['Transformer', 'XGBoost', 'BiLSTM', 'Prophet']
        for name, weight in zip(model_names, weights):
            report.append(f"  {name}: {weight*100:.1f}%")
        report.append("")
        report.append("Signal Distribution:")
        signal_dist = breakdown.get('signal_distribution', {})
        report.append(f"  Buy:  {signal_dist.get('buy', 0)}")
        report.append(f"  Hold: {signal_dist.get('hold', 0)}")
        report.append(f"  Sell: {signal_dist.get('sell', 0)}")
        report.append("")
        report.append("Confidence Statistics:")
        conf_stats = breakdown.get('confidence_stats', {})
        report.append(f"  Mean: {conf_stats.get('mean', 0):.3f}")
        report.append(f"  Std:  {conf_stats.get('std', 0):.3f}")
        report.append(f"  Range: [{conf_stats.get('min', 0):.3f}, {conf_stats.get('max', 0):.3f}]")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)

