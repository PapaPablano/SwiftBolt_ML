"""
ML Model Monitoring Dashboard Tab.

Displays model health, drift detection, and performance metrics.

Author: Cursor Agent
Created: 2025-01-28
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

# Import monitoring system
try:
    from main_production_system.monitoring.ml_model_monitor import MLModelMonitor
    MONITOR_AVAILABLE = True
except ImportError:
    MONITOR_AVAILABLE = False

logger = logging.getLogger(__name__)


def render_model_monitoring_tab():
    """Render the ML Model Monitoring dashboard tab."""
    st.header("🔍 ML Model Monitoring Dashboard")
    st.markdown("Track model performance, detect drift, and monitor health metrics")
    
    if not MONITOR_AVAILABLE:
        st.error("❌ ML Model Monitor not available. Please check installation.")
        return
    
    # Initialize monitor
    monitor = MLModelMonitor()
    
    # Model selection
    models_with_baselines = list(monitor.baselines.keys())
    
    if not models_with_baselines:
        st.warning("⚠️ No model baselines established yet.")
        st.info("""
        To establish a baseline:
        1. Train your model
        2. Generate predictions on validation set
        3. Call `monitor.establish_baseline()` with model name, predictions, and actuals
        """)
        return
    
    selected_model = st.selectbox(
        "Select Model to Monitor",
        models_with_baselines,
        key="monitoring_model_select"
    )
    
    if not selected_model:
        return
    
    # Get dashboard data
    dashboard_data = monitor.get_monitoring_dashboard_data(selected_model)
    
    if dashboard_data.get('status') == 'no_baseline':
        st.warning(f"No baseline found for {selected_model}")
        return
    
    baseline = dashboard_data['baseline']
    recent_perf = dashboard_data['recent_performance']
    recent_drift = dashboard_data['recent_drift']
    
    # === BASELINE METRICS SECTION ===
    st.subheader("📊 Baseline Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Baseline Established",
            baseline['established']
        )
    
    with col2:
        st.metric(
            "Baseline MAE",
            f"${baseline['mae']:.2f}"
        )
    
    with col3:
        st.metric(
            "Baseline RMSE",
            f"${baseline['rmse']:.2f}"
        )
    
    with col4:
        st.metric(
            "Baseline Directional Accuracy",
            f"{baseline['directional_accuracy']:.1%}"
        )
    
    st.markdown("---")
    
    # === RECENT PERFORMANCE SECTION ===
    st.subheader("📈 Recent Performance Trends")
    
    if recent_perf:
        # Extract metrics for plotting
        timestamps = [p['timestamp'] for p in recent_perf]
        mae_values = [p['metrics']['current_mae'] for p in recent_perf]
        mae_degradation = [p['metrics']['mae_degradation_pct'] for p in recent_perf]
        acc_values = [p['metrics']['current_dir_acc'] for p in recent_perf]
        statuses = [p['status'] for p in recent_perf]
        
        # Create subplot figure
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('MAE Over Time', 'MAE Degradation %', 'Directional Accuracy', 'Model Status'),
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )
        
        # MAE Over Time
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=mae_values,
                mode='lines+markers',
                name='Current MAE',
                line=dict(color='#3b82f6', width=2)
            ),
            row=1, col=1
        )
        
        # Baseline MAE line
        fig.add_hline(
            y=baseline['mae'],
            line_dash="dash",
            line_color="gray",
            annotation_text="Baseline MAE",
            row=1, col=1
        )
        
        # MAE Degradation
        color_map = {'HEALTHY': 'green', 'WARNING': 'orange', 'CRITICAL': 'red'}
        colors = [color_map.get(status, 'gray') for status in statuses]
        
        fig.add_trace(
            go.Bar(
                x=timestamps,
                y=mae_degradation,
                name='MAE Degradation %',
                marker_color=colors
            ),
            row=1, col=2
        )
        
        # Directional Accuracy
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=acc_values,
                mode='lines+markers',
                name='Directional Accuracy',
                line=dict(color='#10b981', width=2)
            ),
            row=2, col=1
        )
        
        # Baseline accuracy line
        fig.add_hline(
            y=baseline['directional_accuracy'],
            line_dash="dash",
            line_color="gray",
            annotation_text="Baseline Accuracy",
            row=2, col=1
        )
        
        # Status timeline
        status_numeric = [1 if s == 'HEALTHY' else (2 if s == 'WARNING' else 3) for s in statuses]
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=status_numeric,
                mode='lines+markers',
                name='Status',
                line=dict(width=3),
                marker=dict(size=10, color=colors)
            ),
            row=2, col=2
        )
        
        fig.update_yaxes(title_text="MAE ($)", row=1, col=1)
        fig.update_yaxes(title_text="Degradation %", row=1, col=2)
        fig.update_yaxes(title_text="Accuracy", row=2, col=1)
        fig.update_yaxes(title_text="Status", tickvals=[1, 2, 3], ticktext=['Healthy', 'Warning', 'Critical'], row=2, col=2)
        
        fig.update_layout(height=700, showlegend=False, title_text=f"{selected_model} Performance Monitoring")
        st.plotly_chart(fig, use_container_width=True)
        
        # Performance summary table
        st.subheader("📋 Recent Performance Summary")
        perf_df = pd.DataFrame(recent_perf)
        
        if 'timestamp' in perf_df.columns:
            perf_df['timestamp'] = pd.to_datetime(perf_df['timestamp'])
            perf_df = perf_df.sort_values('timestamp', ascending=False)
        
        display_cols = ['timestamp', 'status', 'recommendation']
        if 'metrics' in perf_df.columns:
            # Expand metrics
            perf_df['MAE'] = perf_df['metrics'].apply(lambda x: x.get('current_mae', 0))
            perf_df['MAE Degradation %'] = perf_df['metrics'].apply(lambda x: x.get('mae_degradation_pct', 0))
            perf_df['Directional Accuracy'] = perf_df['metrics'].apply(lambda x: x.get('current_dir_acc', 0))
            display_cols = ['timestamp', 'status', 'MAE', 'MAE Degradation %', 'Directional Accuracy', 'recommendation']
        
        st.dataframe(
            perf_df[display_cols].head(10),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No recent performance data available. Run predictions to track performance.")
    
    st.markdown("---")
    
    # === DRIFT DETECTION SECTION ===
    st.subheader("🔄 Drift Detection History")
    
    if recent_drift:
        drift_df = pd.DataFrame(recent_drift)
        drift_df['timestamp'] = pd.to_datetime(drift_df['timestamp'])
        drift_df = drift_df.sort_values('timestamp', ascending=False)
        
        # Drift score chart
        fig_drift = go.Figure()
        
        fig_drift.add_trace(
            go.Scatter(
                x=drift_df['timestamp'],
                y=drift_df['score'],
                mode='lines+markers',
                name='Drift Score',
                line=dict(color='#ef5350', width=2),
                marker=dict(size=8)
            )
        )
        
        # Threshold lines
        fig_drift.add_hline(y=0.1, line_dash="dash", line_color="orange", annotation_text="Moderate Drift (0.1)")
        fig_drift.add_hline(y=0.2, line_dash="dash", line_color="red", annotation_text="Significant Drift (0.2)")
        
        fig_drift.update_layout(
            title="Drift Score Over Time",
            xaxis_title="Date",
            yaxis_title="Drift Score (PSI)",
            height=400
        )
        
        st.plotly_chart(fig_drift, use_container_width=True)
        
        # Drift summary table
        st.dataframe(
            drift_df[['timestamp', 'detected', 'score', 'recommendation']].head(10),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No drift detection history available.")
    
    st.markdown("---")
    
    # === TOP FEATURES SECTION ===
    st.subheader("🔧 Top Features (Baseline)")
    
    if dashboard_data.get('top_features'):
        top_features = dashboard_data['top_features']
        
        feature_names = [f[0] for f in top_features]
        feature_importance = [f[1] for f in top_features]
        
        fig_features = go.Figure()
        fig_features.add_trace(
            go.Bar(
                x=feature_importance,
                y=feature_names,
                orientation='h',
                marker_color='#6366f1'
            )
        )
        
        fig_features.update_layout(
            title="Feature Importance (Baseline)",
            xaxis_title="Importance",
            yaxis_title="Feature",
            height=400
        )
        
        st.plotly_chart(fig_features, use_container_width=True)
    else:
        st.info("No feature importance data available.")
    
    st.markdown("---")
    
    # === ALERTS & RECOMMENDATIONS ===
    st.subheader("⚠️ Alerts & Recommendations")
    
    if recent_perf:
        latest_perf = recent_perf[-1]
        status = latest_perf.get('status', 'UNKNOWN')
        recommendation = latest_perf.get('recommendation', 'N/A')
        
        if status == 'CRITICAL':
            st.error(f"🚨 **CRITICAL**: {recommendation.replace('_', ' ')}")
            st.warning("Immediate action required. Consider retraining the model.")
        elif status == 'WARNING':
            st.warning(f"⚠️ **WARNING**: {recommendation.replace('_', ' ')}")
            st.info("Schedule model retraining in the near future.")
        else:
            st.success(f"✅ **HEALTHY**: Model performance is within acceptable limits.")
            st.info("Continue monitoring. No action required at this time.")
    else:
        st.info("No alerts available. Establish a baseline and run predictions to generate alerts.")


if __name__ == "__main__":
    st.set_page_config(page_title="Model Monitoring", layout="wide")
    render_model_monitoring_tab()

