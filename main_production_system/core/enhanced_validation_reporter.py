#!/usr/bin/env python3
"""
Enhanced Validation Reporter
Generates comprehensive reports and visualizations for walk-forward validation results.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union
import warnings

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    from matplotlib.patches import Rectangle
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class EnhancedValidationReporter:
    """
    Enhanced validation reporter with comprehensive visualizations and reports.
    
    Generates:
    - Executive summary reports
    - Performance trend charts
    - Regime analysis visualizations
    - SuperTrend AI performance charts
    - KDJ feature analysis
    - Validation quality metrics
    - Interactive dashboards
    """
    
    def __init__(self, output_path: Path = Path('validation_results/reports')):
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Set up plotting style
        if PLOTTING_AVAILABLE:
            plt.style.use('seaborn-v0_8')
            sns.set_palette("husl")
    
    def generate_comprehensive_report(
        self, 
        summary: Any, 
        window_results: List[Dict], 
        ticker: str,
        save_plots: bool = True
    ) -> Dict[str, Any]:
        """
        Generate comprehensive validation report with all visualizations.
        
        Args:
            summary: EnhancedValidationSummary object
            window_results: List of window result dictionaries
            ticker: Ticker symbol
            save_plots: Whether to save plots to disk
        
        Returns:
            Dictionary containing all report components
        """
        logger.info(f"Generating comprehensive report for {ticker}")
        
        report = {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat(),
            'executive_summary': self._generate_executive_summary(summary),
            'performance_analysis': self._generate_performance_analysis(summary, window_results),
            'regime_analysis': self._generate_regime_analysis(summary, window_results),
            'supertrend_analysis': self._generate_supertrend_analysis(summary, window_results),
            'kdj_analysis': self._generate_kdj_analysis(summary, window_results),
            'validation_quality': self._generate_validation_quality_analysis(summary, window_results),
            'recommendations': self._generate_detailed_recommendations(summary, window_results),
            'plots': {}
        }
        
        if save_plots and PLOTTING_AVAILABLE:
            try:
                # Generate all plots
                report['plots'] = {
                    'performance_trends': self._create_performance_trends_plot(summary, window_results, ticker),
                    'regime_analysis': self._create_regime_analysis_plot(summary, window_results, ticker),
                    'supertrend_performance': self._create_supertrend_performance_plot(summary, window_results, ticker),
                    'kdj_analysis': self._create_kdj_analysis_plot(summary, window_results, ticker),
                    'validation_quality': self._create_validation_quality_plot(summary, window_results, ticker),
                    'correlation_heatmap': self._create_correlation_heatmap(summary, window_results, ticker),
                    'interactive_dashboard': self._create_interactive_dashboard(summary, window_results, ticker)
                }
            except Exception as e:
                logger.warning(f"Failed to generate plots: {e}")
                report['plots'] = {}
        
        # Save report
        self._save_comprehensive_report(report, ticker)
        
        return report
    
    def _generate_executive_summary(self, summary: Any) -> Dict[str, Any]:
        """Generate executive summary of validation results."""
        # Calculate overall performance score
        performance_score = self._calculate_performance_score(summary)
        
        # Determine deployment readiness
        deployment_ready = (
            summary.performance_targets_met.get('mae_target', False) and
            summary.performance_targets_met.get('directional_accuracy_target', False) and
            summary.residual_diagnostics_pass_rate > 0.8
        )
        
        # Identify key strengths and weaknesses
        strengths = []
        weaknesses = []
        
        if summary.mean_directional_accuracy > 65:
            strengths.append("High directional accuracy")
        if summary.mean_r_squared > 0.6:
            strengths.append("Strong explanatory power (R²)")
        if summary.mean_supertrend_accuracy > 60:
            strengths.append("Effective SuperTrend AI integration")
        if summary.residual_diagnostics_pass_rate > 0.9:
            strengths.append("Excellent model diagnostics")
        
        if summary.mean_mae > 15:
            weaknesses.append("High prediction error")
        if summary.mean_directional_accuracy < 55:
            weaknesses.append("Low directional accuracy")
        if summary.residual_diagnostics_pass_rate < 0.7:
            weaknesses.append("Poor model diagnostics")
        if summary.benchmark_comparison_avg_rank > 3:
            weaknesses.append("Below benchmark performance")
        
        return {
            'performance_score': performance_score,
            'deployment_ready': deployment_ready,
            'total_windows': summary.total_windows,
            'overall_assessment': self._get_overall_assessment(performance_score),
            'key_strengths': strengths,
            'key_weaknesses': weaknesses,
            'critical_metrics': {
                'mae': summary.mean_mae,
                'directional_accuracy': summary.mean_directional_accuracy,
                'r_squared': summary.mean_r_squared,
                'supertrend_accuracy': summary.mean_supertrend_accuracy
            }
        }
    
    def _calculate_performance_score(self, summary: Any) -> float:
        """Calculate overall performance score (0-100)."""
        scores = []
        
        # MAE score (inverted - lower is better)
        mae_score = max(0, 100 - (summary.mean_mae / 20) * 100)
        scores.append(mae_score)
        
        # Directional accuracy score
        dir_acc_score = min(100, summary.mean_directional_accuracy)
        scores.append(dir_acc_score)
        
        # R-squared score
        r2_score = max(0, summary.mean_r_squared * 100)
        scores.append(r2_score)
        
        # SuperTrend AI score
        st_score = min(100, summary.mean_supertrend_accuracy)
        scores.append(st_score)
        
        # Validation quality score
        val_score = (
            summary.residual_diagnostics_pass_rate * 40 +
            (1 / summary.benchmark_comparison_avg_rank) * 30 +
            summary.purged_cv_validation_pass_rate * 30
        )
        scores.append(val_score)
        
        return np.mean(scores)
    
    def _get_overall_assessment(self, performance_score: float) -> str:
        """Get overall assessment based on performance score."""
        if performance_score >= 80:
            return "EXCELLENT"
        elif performance_score >= 70:
            return "GOOD"
        elif performance_score >= 60:
            return "FAIR"
        elif performance_score >= 50:
            return "POOR"
        else:
            return "UNACCEPTABLE"
    
    def _generate_performance_analysis(self, summary: Any, window_results: List[Dict]) -> Dict[str, Any]:
        """Generate detailed performance analysis."""
        df = pd.DataFrame(window_results)
        
        # Calculate performance trends
        performance_trends = {
            'mae_trend': self._calculate_trend(df['mae']),
            'directional_accuracy_trend': self._calculate_trend(df['directional_accuracy']),
            'r_squared_trend': self._calculate_trend(df['r_squared']),
            'supertrend_accuracy_trend': self._calculate_trend(df['supertrend_accuracy'])
        }
        
        # Calculate stability metrics
        stability_metrics = {
            'mae_coefficient_of_variation': df['mae'].std() / df['mae'].mean() if df['mae'].mean() > 0 else 0,
            'directional_accuracy_std': df['directional_accuracy'].std(),
            'r_squared_std': df['r_squared'].std(),
            'performance_consistency': 1 - (df['mae'].std() / df['mae'].mean()) if df['mae'].mean() > 0 else 0
        }
        
        # Calculate regime-specific performance
        regime_performance = {}
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            regime_data = df[df['volatility_regime'] == regime]
            if len(regime_data) > 0:
                regime_performance[regime] = {
                    'mae': regime_data['mae'].mean(),
                    'directional_accuracy': regime_data['directional_accuracy'].mean(),
                    'r_squared': regime_data['r_squared'].mean(),
                    'window_count': len(regime_data)
                }
        
        return {
            'trends': performance_trends,
            'stability': stability_metrics,
            'regime_performance': regime_performance,
            'best_window': {
                'window': summary.best_window['window'],
                'mae': summary.best_window['mae'],
                'directional_accuracy': summary.best_window['directional_accuracy'],
                'regime': summary.best_window['volatility_regime']
            },
            'worst_window': {
                'window': summary.worst_window['window'],
                'mae': summary.worst_window['mae'],
                'directional_accuracy': summary.worst_window['directional_accuracy'],
                'regime': summary.worst_window['volatility_regime']
            }
        }
    
    def _calculate_trend(self, series: pd.Series) -> str:
        """Calculate trend direction for a series."""
        if len(series) < 2:
            return "INSUFFICIENT_DATA"
        
        # Simple linear trend
        x = np.arange(len(series))
        slope = np.polyfit(x, series, 1)[0]
        
        if slope > 0.01:
            return "IMPROVING"
        elif slope < -0.01:
            return "DEGRADING"
        else:
            return "STABLE"
    
    def _generate_regime_analysis(self, summary: Any, window_results: List[Dict]) -> Dict[str, Any]:
        """Generate volatility regime analysis."""
        df = pd.DataFrame(window_results)
        
        regime_stats = {}
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            regime_data = df[df['volatility_regime'] == regime]
            if len(regime_data) > 0:
                regime_stats[regime] = {
                    'window_count': len(regime_data),
                    'percentage': len(regime_data) / len(df) * 100,
                    'avg_mae': regime_data['mae'].mean(),
                    'avg_directional_accuracy': regime_data['directional_accuracy'].mean(),
                    'avg_r_squared': regime_data['r_squared'].mean(),
                    'avg_supertrend_accuracy': regime_data['supertrend_accuracy'].mean(),
                    'volatility_ratio_range': [
                        regime_data['volatility_ratio'].min(),
                        regime_data['volatility_ratio'].max()
                    ]
                }
        
        # Regime transition analysis
        regime_transitions = []
        for i in range(1, len(df)):
            prev_regime = df.iloc[i-1]['volatility_regime']
            curr_regime = df.iloc[i]['volatility_regime']
            if prev_regime != curr_regime:
                regime_transitions.append({
                    'window': i + 1,
                    'from_regime': prev_regime,
                    'to_regime': curr_regime
                })
        
        return {
            'regime_distribution': regime_stats,
            'regime_transitions': regime_transitions,
            'dominant_regime': max(regime_stats.keys(), key=lambda k: regime_stats[k]['window_count']),
            'regime_stability': len(regime_transitions) / len(df) if len(df) > 0 else 0
        }
    
    def _generate_supertrend_analysis(self, summary: Any, window_results: List[Dict]) -> Dict[str, Any]:
        """Generate SuperTrend AI analysis."""
        df = pd.DataFrame(window_results)
        
        # SuperTrend performance analysis
        supertrend_stats = {
            'avg_accuracy': df['supertrend_accuracy'].mean(),
            'accuracy_std': df['supertrend_accuracy'].std(),
            'avg_factor': df['supertrend_factor'].mean(),
            'factor_std': df['supertrend_factor'].std(),
            'avg_performance': df['supertrend_performance'].mean(),
            'performance_std': df['supertrend_performance'].std()
        }
        
        # Factor distribution analysis
        factor_distribution = {
            'min_factor': df['supertrend_factor'].min(),
            'max_factor': df['supertrend_factor'].max(),
            'median_factor': df['supertrend_factor'].median(),
            'factor_quartiles': df['supertrend_factor'].quantile([0.25, 0.5, 0.75]).to_dict()
        }
        
        # Performance vs factor correlation
        factor_performance_corr = df['supertrend_factor'].corr(df['supertrend_accuracy'])
        
        # Best performing factors
        best_performance_windows = df.nlargest(3, 'supertrend_accuracy')
        best_factors = best_performance_windows['supertrend_factor'].tolist()
        
        return {
            'performance_stats': supertrend_stats,
            'factor_distribution': factor_distribution,
            'factor_performance_correlation': factor_performance_corr,
            'best_performing_factors': best_factors,
            'factor_effectiveness': 'HIGH' if factor_performance_corr > 0.3 else 'MEDIUM' if factor_performance_corr > 0.1 else 'LOW'
        }
    
    def _generate_kdj_analysis(self, summary: Any, window_results: List[Dict]) -> Dict[str, Any]:
        """Generate KDJ feature analysis."""
        df = pd.DataFrame(window_results)
        
        # KDJ feature statistics
        kdj_stats = {
            'avg_importance': df['kdj_importance'].mean(),
            'importance_std': df['kdj_importance'].std(),
            'total_crossover_signals': df['kdj_crossover_signals'].sum(),
            'avg_signals_per_window': df['kdj_crossover_signals'].mean(),
            'signal_frequency': df['kdj_crossover_signals'].sum() / len(df) if len(df) > 0 else 0
        }
        
        # Signal effectiveness analysis
        signal_effectiveness = []
        for _, row in df.iterrows():
            if row['kdj_crossover_signals'] > 0:
                # Higher signals with better performance suggests effectiveness
                effectiveness = row['directional_accuracy'] / max(1, row['kdj_crossover_signals'])
                signal_effectiveness.append(effectiveness)
        
        avg_signal_effectiveness = np.mean(signal_effectiveness) if signal_effectiveness else 0
        
        # Feature importance trend
        importance_trend = self._calculate_trend(df['kdj_importance'])
        
        return {
            'feature_stats': kdj_stats,
            'signal_effectiveness': avg_signal_effectiveness,
            'importance_trend': importance_trend,
            'feature_contribution': 'HIGH' if kdj_stats['avg_importance'] > 0.15 else 'MEDIUM' if kdj_stats['avg_importance'] > 0.05 else 'LOW',
            'signal_quality': 'HIGH' if avg_signal_effectiveness > 20 else 'MEDIUM' if avg_signal_effectiveness > 10 else 'LOW'
        }
    
    def _generate_validation_quality_analysis(self, summary: Any, window_results: List[Dict]) -> Dict[str, Any]:
        """Generate validation quality analysis."""
        df = pd.DataFrame(window_results)
        
        # Validation quality metrics
        quality_metrics = {
            'residual_diagnostics_pass_rate': summary.residual_diagnostics_pass_rate,
            'benchmark_comparison_avg_rank': summary.benchmark_comparison_avg_rank,
            'purged_cv_pass_rate': summary.purged_cv_validation_pass_rate,
            'overall_quality_score': (
                summary.residual_diagnostics_pass_rate * 0.4 +
                (1 / summary.benchmark_comparison_avg_rank) * 0.4 +
                summary.purged_cv_validation_pass_rate * 0.2
            )
        }
        
        # Quality trends
        quality_trends = {
            'residual_diagnostics_trend': self._calculate_trend(df['residual_diagnostics_passed'].astype(float)),
            'benchmark_rank_trend': self._calculate_trend(df['benchmark_comparison_rank']),
            'purged_cv_trend': self._calculate_trend(df['purged_cv_validation_passed'].astype(float))
        }
        
        # Quality issues
        quality_issues = []
        if summary.residual_diagnostics_pass_rate < 0.8:
            quality_issues.append("High residual diagnostic failure rate")
        if summary.benchmark_comparison_avg_rank > 3:
            quality_issues.append("Below benchmark performance")
        if summary.purged_cv_validation_pass_rate < 0.9:
            quality_issues.append("Purged CV validation issues")
        
        return {
            'metrics': quality_metrics,
            'trends': quality_trends,
            'issues': quality_issues,
            'overall_quality': 'HIGH' if quality_metrics['overall_quality_score'] > 0.8 else 'MEDIUM' if quality_metrics['overall_quality_score'] > 0.6 else 'LOW'
        }
    
    def _generate_detailed_recommendations(self, summary: Any, window_results: List[Dict]) -> List[Dict[str, Any]]:
        """Generate detailed recommendations with priorities."""
        recommendations = []
        
        # Performance-based recommendations
        if summary.mean_mae > 15:
            recommendations.append({
                'category': 'PERFORMANCE',
                'priority': 'HIGH',
                'title': 'Reduce Prediction Error',
                'description': f'Current MAE of {summary.mean_mae:.2f} exceeds target of 12.0',
                'actions': [
                    'Retrain model with more recent data',
                    'Increase training window size',
                    'Add more relevant features',
                    'Consider ensemble methods'
                ]
            })
        
        if summary.mean_directional_accuracy < 55:
            recommendations.append({
                'category': 'PERFORMANCE',
                'priority': 'HIGH',
                'title': 'Improve Directional Accuracy',
                'description': f'Current accuracy of {summary.mean_directional_accuracy:.1f}% is below target of 65%',
                'actions': [
                    'Add technical indicators for trend detection',
                    'Implement regime-specific models',
                    'Use ensemble voting methods',
                    'Optimize SuperTrend AI parameters'
                ]
            })
        
        # SuperTrend AI recommendations
        if summary.mean_supertrend_accuracy < 60:
            recommendations.append({
                'category': 'SUPERTREND_AI',
                'priority': 'MEDIUM',
                'title': 'Optimize SuperTrend AI',
                'description': f'SuperTrend accuracy of {summary.mean_supertrend_accuracy:.1f}% can be improved',
                'actions': [
                    'Adjust factor range and step size',
                    'Optimize K-means clustering parameters',
                    'Consider different performance metrics',
                    'Implement adaptive factor selection'
                ]
            })
        
        # KDJ feature recommendations
        if summary.mean_kdj_importance < 0.1:
            recommendations.append({
                'category': 'FEATURES',
                'priority': 'MEDIUM',
                'title': 'Optimize KDJ Features',
                'description': f'KDJ importance of {summary.mean_kdj_importance:.3f} is low',
                'actions': [
                    'Adjust KDJ calculation parameters',
                    'Add KDJ divergence signals',
                    'Combine with other oscillators',
                    'Consider removing if consistently low importance'
                ]
            })
        
        # Validation quality recommendations
        if summary.residual_diagnostics_pass_rate < 0.8:
            recommendations.append({
                'category': 'VALIDATION',
                'priority': 'HIGH',
                'title': 'Fix Residual Diagnostics',
                'description': f'Diagnostic pass rate of {summary.residual_diagnostics_pass_rate:.1%} is low',
                'actions': [
                    'Review model specification',
                    'Check for autocorrelation in residuals',
                    'Consider different error distributions',
                    'Implement robust estimation methods'
                ]
            })
        
        # General recommendations
        if summary.performance_targets_met.get('mae_target', False) and summary.performance_targets_met.get('directional_accuracy_target', False):
            recommendations.append({
                'category': 'DEPLOYMENT',
                'priority': 'LOW',
                'title': 'Ready for Production',
                'description': 'Model meets performance targets and is ready for deployment',
                'actions': [
                    'Deploy to production environment',
                    'Set up monitoring and alerting',
                    'Schedule regular retraining',
                    'Document model performance'
                ]
            })
        
        return recommendations
    
    def _create_performance_trends_plot(self, summary: Any, window_results: List[Dict], ticker: str) -> str:
        """Create performance trends visualization."""
        if not PLOTTING_AVAILABLE:
            return ""
        
        df = pd.DataFrame(window_results)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Performance Trends - {ticker}', fontsize=16, fontweight='bold')
        
        # MAE trend
        axes[0, 0].plot(df['window'], df['mae'], 'o-', linewidth=2, markersize=4, color='red')
        axes[0, 0].axhline(summary.mean_mae, color='red', linestyle='--', alpha=0.7, label='Mean')
        axes[0, 0].fill_between(df['window'], 
                               summary.mean_mae - summary.std_mae,
                               summary.mean_mae + summary.std_mae,
                               alpha=0.2, color='red')
        axes[0, 0].set_title('Mean Absolute Error')
        axes[0, 0].set_xlabel('Validation Window')
        axes[0, 0].set_ylabel('MAE')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Directional accuracy trend
        axes[0, 1].plot(df['window'], df['directional_accuracy'], 'o-', linewidth=2, markersize=4, color='green')
        axes[0, 1].axhline(summary.mean_directional_accuracy, color='green', linestyle='--', alpha=0.7, label='Mean')
        axes[0, 1].axhline(50, color='gray', linestyle=':', alpha=0.7, label='Random')
        axes[0, 1].set_title('Directional Accuracy')
        axes[0, 1].set_xlabel('Validation Window')
        axes[0, 1].set_ylabel('Accuracy (%)')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # R-squared trend
        axes[1, 0].plot(df['window'], df['r_squared'], 'o-', linewidth=2, markersize=4, color='blue')
        axes[1, 0].axhline(summary.mean_r_squared, color='blue', linestyle='--', alpha=0.7, label='Mean')
        axes[1, 0].set_title('R-squared')
        axes[1, 0].set_xlabel('Validation Window')
        axes[1, 0].set_ylabel('R²')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # SuperTrend accuracy trend
        axes[1, 1].plot(df['window'], df['supertrend_accuracy'], 'o-', linewidth=2, markersize=4, color='orange')
        axes[1, 1].axhline(summary.mean_supertrend_accuracy, color='orange', linestyle='--', alpha=0.7, label='Mean')
        axes[1, 1].set_title('SuperTrend AI Accuracy')
        axes[1, 1].set_xlabel('Validation Window')
        axes[1, 1].set_ylabel('Accuracy (%)')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_path / f"{ticker}_performance_trends.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(plot_path)
    
    def _create_regime_analysis_plot(self, summary: Any, window_results: List[Dict], ticker: str) -> str:
        """Create volatility regime analysis visualization."""
        if not PLOTTING_AVAILABLE:
            return ""
        
        df = pd.DataFrame(window_results)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Volatility Regime Analysis - {ticker}', fontsize=16, fontweight='bold')
        
        # Regime distribution pie chart
        regime_counts = df['volatility_regime'].value_counts()
        colors = ['lightgreen', 'orange', 'red']
        axes[0, 0].pie(regime_counts.values, labels=regime_counts.index, autopct='%1.1f%%', colors=colors)
        axes[0, 0].set_title('Regime Distribution')
        
        # MAE by regime
        regime_data = []
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            regime_mae = df[df['volatility_regime'] == regime]['mae']
            if len(regime_mae) > 0:
                regime_data.append(regime_mae)
        
        axes[0, 1].boxplot(regime_data, labels=['LOW', 'MEDIUM', 'HIGH'])
        axes[0, 1].set_title('MAE by Volatility Regime')
        axes[0, 1].set_ylabel('MAE')
        axes[0, 1].grid(True, alpha=0.3)
        
        # Volatility ratio over time
        colors_map = {'LOW': 'green', 'MEDIUM': 'orange', 'HIGH': 'red'}
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            regime_data = df[df['volatility_regime'] == regime]
            if len(regime_data) > 0:
                axes[1, 0].scatter(regime_data['window'], regime_data['volatility_ratio'], 
                                 c=colors_map[regime], label=regime, alpha=0.7)
        axes[1, 0].set_title('Volatility Ratio Over Time')
        axes[1, 0].set_xlabel('Validation Window')
        axes[1, 0].set_ylabel('Volatility Ratio')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # Performance by regime
        regime_performance = []
        regime_labels = []
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            regime_data = df[df['volatility_regime'] == regime]
            if len(regime_data) > 0:
                regime_performance.append(regime_data['directional_accuracy'].mean())
                regime_labels.append(f'{regime}\n(n={len(regime_data)})')
        
        bars = axes[1, 1].bar(regime_labels, regime_performance, color=colors)
        axes[1, 1].set_title('Directional Accuracy by Regime')
        axes[1, 1].set_ylabel('Accuracy (%)')
        axes[1, 1].grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bar, value in zip(bars, regime_performance):
            axes[1, 1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                           f'{value:.1f}%', ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_path / f"{ticker}_regime_analysis.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(plot_path)
    
    def _create_supertrend_performance_plot(self, summary: Any, window_results: List[Dict], ticker: str) -> str:
        """Create SuperTrend AI performance visualization."""
        if not PLOTTING_AVAILABLE:
            return ""
        
        df = pd.DataFrame(window_results)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'SuperTrend AI Performance - {ticker}', fontsize=16, fontweight='bold')
        
        # SuperTrend accuracy trend
        axes[0, 0].plot(df['window'], df['supertrend_accuracy'], 'o-', linewidth=2, markersize=4, color='purple')
        axes[0, 0].axhline(summary.mean_supertrend_accuracy, color='purple', linestyle='--', alpha=0.7, label='Mean')
        axes[0, 0].set_title('SuperTrend AI Accuracy Over Time')
        axes[0, 0].set_xlabel('Validation Window')
        axes[0, 0].set_ylabel('Accuracy (%)')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Factor distribution
        axes[0, 1].hist(df['supertrend_factor'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        axes[0, 1].axvline(summary.mean_supertrend_factor, color='red', linestyle='--', label='Mean Factor')
        axes[0, 1].set_title('SuperTrend Factor Distribution')
        axes[0, 1].set_xlabel('Factor Value')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Factor vs Performance scatter
        scatter = axes[1, 0].scatter(df['supertrend_factor'], df['supertrend_accuracy'], 
                                   c=df['window'], cmap='viridis', alpha=0.7)
        axes[1, 0].set_title('Factor vs Performance')
        axes[1, 0].set_xlabel('SuperTrend Factor')
        axes[1, 0].set_ylabel('Accuracy (%)')
        plt.colorbar(scatter, ax=axes[1, 0], label='Window')
        axes[1, 0].grid(True, alpha=0.3)
        
        # Performance distribution
        axes[1, 1].hist(df['supertrend_performance'], bins=20, alpha=0.7, color='lightcoral', edgecolor='black')
        axes[1, 1].axvline(summary.mean_supertrend_performance, color='red', linestyle='--', label='Mean Performance')
        axes[1, 1].set_title('SuperTrend Performance Distribution')
        axes[1, 1].set_xlabel('Performance Value')
        axes[1, 1].set_ylabel('Frequency')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_path / f"{ticker}_supertrend_performance.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(plot_path)
    
    def _create_kdj_analysis_plot(self, summary: Any, window_results: List[Dict], ticker: str) -> str:
        """Create KDJ feature analysis visualization."""
        if not PLOTTING_AVAILABLE:
            return ""
        
        df = pd.DataFrame(window_results)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'KDJ Feature Analysis - {ticker}', fontsize=16, fontweight='bold')
        
        # KDJ importance trend
        axes[0, 0].plot(df['window'], df['kdj_importance'], 'o-', linewidth=2, markersize=4, color='darkgreen')
        axes[0, 0].axhline(summary.mean_kdj_importance, color='darkgreen', linestyle='--', alpha=0.7, label='Mean')
        axes[0, 0].set_title('KDJ Feature Importance Over Time')
        axes[0, 0].set_xlabel('Validation Window')
        axes[0, 0].set_ylabel('Importance')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Crossover signals over time
        axes[0, 1].bar(df['window'], df['kdj_crossover_signals'], alpha=0.7, color='lightblue', edgecolor='navy')
        axes[0, 1].axhline(df['kdj_crossover_signals'].mean(), color='red', linestyle='--', alpha=0.7, label='Mean')
        axes[0, 1].set_title('KDJ Crossover Signals Over Time')
        axes[0, 1].set_xlabel('Validation Window')
        axes[0, 1].set_ylabel('Number of Signals')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # KDJ importance vs performance
        scatter = axes[1, 0].scatter(df['kdj_importance'], df['directional_accuracy'], 
                                   c=df['window'], cmap='plasma', alpha=0.7)
        axes[1, 0].set_title('KDJ Importance vs Directional Accuracy')
        axes[1, 0].set_xlabel('KDJ Importance')
        axes[1, 0].set_ylabel('Directional Accuracy (%)')
        plt.colorbar(scatter, ax=axes[1, 0], label='Window')
        axes[1, 0].grid(True, alpha=0.3)
        
        # Signal effectiveness
        signal_effectiveness = []
        for _, row in df.iterrows():
            if row['kdj_crossover_signals'] > 0:
                effectiveness = row['directional_accuracy'] / row['kdj_crossover_signals']
                signal_effectiveness.append(effectiveness)
        
        if signal_effectiveness:
            axes[1, 1].hist(signal_effectiveness, bins=15, alpha=0.7, color='gold', edgecolor='black')
            axes[1, 1].axvline(np.mean(signal_effectiveness), color='red', linestyle='--', label='Mean')
            axes[1, 1].set_title('Signal Effectiveness Distribution')
            axes[1, 1].set_xlabel('Effectiveness (Accuracy/Signals)')
            axes[1, 1].set_ylabel('Frequency')
            axes[1, 1].legend()
        else:
            axes[1, 1].text(0.5, 0.5, 'No crossover signals detected', ha='center', va='center', transform=axes[1, 1].transAxes)
            axes[1, 1].set_title('Signal Effectiveness Distribution')
        
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_path / f"{ticker}_kdj_analysis.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(plot_path)
    
    def _create_validation_quality_plot(self, summary: Any, window_results: List[Dict], ticker: str) -> str:
        """Create validation quality visualization."""
        if not PLOTTING_AVAILABLE:
            return ""
        
        df = pd.DataFrame(window_results)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Validation Quality Analysis - {ticker}', fontsize=16, fontweight='bold')
        
        # Residual diagnostics pass rate over time
        axes[0, 0].plot(df['window'], df['residual_diagnostics_passed'].astype(float), 'o-', linewidth=2, markersize=4, color='blue')
        axes[0, 0].axhline(summary.residual_diagnostics_pass_rate, color='blue', linestyle='--', alpha=0.7, label='Mean')
        axes[0, 0].set_title('Residual Diagnostics Pass Rate')
        axes[0, 0].set_xlabel('Validation Window')
        axes[0, 0].set_ylabel('Pass Rate')
        axes[0, 0].set_ylim(0, 1)
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Benchmark comparison rank over time
        axes[0, 1].plot(df['window'], df['benchmark_comparison_rank'], 'o-', linewidth=2, markersize=4, color='green')
        axes[0, 1].axhline(summary.benchmark_comparison_avg_rank, color='green', linestyle='--', alpha=0.7, label='Mean')
        axes[0, 1].set_title('Benchmark Comparison Rank')
        axes[0, 1].set_xlabel('Validation Window')
        axes[0, 1].set_ylabel('Rank (lower is better)')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Purged CV pass rate over time
        axes[1, 0].plot(df['window'], df['purged_cv_validation_passed'].astype(float), 'o-', linewidth=2, markersize=4, color='red')
        axes[1, 0].axhline(summary.purged_cv_validation_pass_rate, color='red', linestyle='--', alpha=0.7, label='Mean')
        axes[1, 0].set_title('Purged CV Validation Pass Rate')
        axes[1, 0].set_xlabel('Validation Window')
        axes[1, 0].set_ylabel('Pass Rate')
        axes[1, 0].set_ylim(0, 1)
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # Overall quality score
        quality_scores = (
            df['residual_diagnostics_passed'].astype(float) * 0.4 +
            (1 / df['benchmark_comparison_rank']) * 0.4 +
            df['purged_cv_validation_passed'].astype(float) * 0.2
        )
        
        axes[1, 1].plot(df['window'], quality_scores, 'o-', linewidth=2, markersize=4, color='purple')
        axes[1, 1].axhline(quality_scores.mean(), color='purple', linestyle='--', alpha=0.7, label='Mean')
        axes[1, 1].axhline(0.8, color='green', linestyle=':', alpha=0.7, label='High Quality Threshold')
        axes[1, 1].axhline(0.6, color='orange', linestyle=':', alpha=0.7, label='Medium Quality Threshold')
        axes[1, 1].set_title('Overall Quality Score')
        axes[1, 1].set_xlabel('Validation Window')
        axes[1, 1].set_ylabel('Quality Score')
        axes[1, 1].set_ylim(0, 1)
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_path / f"{ticker}_validation_quality.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(plot_path)
    
    def _create_correlation_heatmap(self, summary: Any, window_results: List[Dict], ticker: str) -> str:
        """Create correlation heatmap of all metrics."""
        if not PLOTTING_AVAILABLE:
            return ""
        
        df = pd.DataFrame(window_results)
        
        # Select numeric columns for correlation
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        correlation_matrix = df[numeric_cols].corr()
        
        plt.figure(figsize=(12, 10))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0, 
                   square=True, fmt='.2f', cbar_kws={'shrink': 0.8})
        plt.title(f'Metrics Correlation Heatmap - {ticker}', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_path / f"{ticker}_correlation_heatmap.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(plot_path)
    
    def _create_interactive_dashboard(self, summary: Any, window_results: List[Dict], ticker: str) -> str:
        """Create interactive Plotly dashboard."""
        if not PLOTTING_AVAILABLE:
            return ""
        
        df = pd.DataFrame(window_results)
        
        # Create subplots
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=('MAE Trend', 'Directional Accuracy', 'R-squared Trend', 'SuperTrend Accuracy', 
                          'Volatility Regime', 'Validation Quality'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # MAE trend
        fig.add_trace(
            go.Scatter(x=df['window'], y=df['mae'], mode='lines+markers', name='MAE', line=dict(color='red')),
            row=1, col=1
        )
        
        # Directional accuracy
        fig.add_trace(
            go.Scatter(x=df['window'], y=df['directional_accuracy'], mode='lines+markers', name='Dir Acc', line=dict(color='green')),
            row=1, col=2
        )
        
        # R-squared
        fig.add_trace(
            go.Scatter(x=df['window'], y=df['r_squared'], mode='lines+markers', name='R²', line=dict(color='blue')),
            row=2, col=1
        )
        
        # SuperTrend accuracy
        fig.add_trace(
            go.Scatter(x=df['window'], y=df['supertrend_accuracy'], mode='lines+markers', name='ST Acc', line=dict(color='orange')),
            row=2, col=2
        )
        
        # Volatility regime
        regime_colors = {'LOW': 'green', 'MEDIUM': 'orange', 'HIGH': 'red'}
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            regime_data = df[df['volatility_regime'] == regime]
            if len(regime_data) > 0:
                fig.add_trace(
                    go.Scatter(x=regime_data['window'], y=regime_data['mae'], 
                             mode='markers', name=f'{regime} Volatility', 
                             marker=dict(color=regime_colors[regime], size=8)),
                    row=3, col=1
                )
        
        # Validation quality
        quality_scores = (
            df['residual_diagnostics_passed'].astype(float) * 0.4 +
            (1 / df['benchmark_comparison_rank']) * 0.4 +
            df['purged_cv_validation_passed'].astype(float) * 0.2
        )
        fig.add_trace(
            go.Scatter(x=df['window'], y=quality_scores, mode='lines+markers', name='Quality Score', line=dict(color='purple')),
            row=3, col=2
        )
        
        # Update layout
        fig.update_layout(
            title=f'Interactive Validation Dashboard - {ticker}',
            height=800,
            showlegend=True
        )
        
        # Save interactive dashboard
        dashboard_path = self.output_path / f"{ticker}_interactive_dashboard.html"
        fig.write_html(str(dashboard_path))
        
        return str(dashboard_path)
    
    def _save_comprehensive_report(self, report: Dict[str, Any], ticker: str):
        """Save comprehensive report to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON report
        json_path = self.output_path / f"{ticker}_{timestamp}_comprehensive_report.json"
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"✓ Saved comprehensive report: {json_path}")
        
        # Save text summary
        text_path = self.output_path / f"{ticker}_{timestamp}_executive_summary.txt"
        with open(text_path, 'w') as f:
            f.write("ENHANCED VALIDATION REPORT\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Ticker: {ticker}\n")
            f.write(f"Generated: {report['timestamp']}\n\n")
            
            # Executive summary
            exec_sum = report['executive_summary']
            f.write("EXECUTIVE SUMMARY\n")
            f.write("-" * 20 + "\n")
            f.write(f"Performance Score: {exec_sum['performance_score']:.1f}/100\n")
            f.write(f"Deployment Ready: {'YES' if exec_sum['deployment_ready'] else 'NO'}\n")
            f.write(f"Overall Assessment: {exec_sum['overall_assessment']}\n")
            f.write(f"Total Windows: {exec_sum['total_windows']}\n\n")
            
            f.write("Key Strengths:\n")
            for strength in exec_sum['key_strengths']:
                f.write(f"  • {strength}\n")
            
            f.write("\nKey Weaknesses:\n")
            for weakness in exec_sum['key_weaknesses']:
                f.write(f"  • {weakness}\n")
            
            f.write("\nCritical Metrics:\n")
            for metric, value in exec_sum['critical_metrics'].items():
                f.write(f"  • {metric}: {value:.3f}\n")
            
            # Recommendations
            f.write("\n\nRECOMMENDATIONS\n")
            f.write("-" * 20 + "\n")
            for i, rec in enumerate(report['recommendations'], 1):
                f.write(f"{i}. [{rec['priority']}] {rec['title']}\n")
                f.write(f"   {rec['description']}\n")
                f.write("   Actions:\n")
                for action in rec['actions']:
                    f.write(f"     • {action}\n")
                f.write("\n")
        
        logger.info(f"✓ Saved executive summary: {text_path}")


# Example usage
if __name__ == "__main__":
    # This would be used with actual validation results
    reporter = EnhancedValidationReporter()
    print("Enhanced Validation Reporter initialized")
    print("Use with EnhancedValidationSummary and window results")
