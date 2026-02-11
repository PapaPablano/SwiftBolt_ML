"""
ML Model Performance Monitoring Page.

Author: Cursor Agent
Created: 2025-10-31
Updated: January 28, 2025 - Added enterprise ML monitoring
"""

from __future__ import annotations

# Third-party imports
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Standard library imports
import logging

# Local imports
try:
    # Add parent directory to path for module imports
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from main_production_system.monitoring.ml_model_monitor import MLModelMonitor
except ImportError as e:
    st.error(f"❌ Could not import MLModelMonitor: {e}")
    MLModelMonitor = None

logger = logging.getLogger(__name__)


def render() -> None:
    """Render the ML model monitoring dashboard."""
    st.header("🤖 ML Model Performance Monitoring")
    st.markdown("---")
    
    if MLModelMonitor is None:
        st.error("❌ ML Model Monitoring module not available. Please check installations.")
        return
    
    try:
        # Initialize monitor
        monitor = MLModelMonitor()
        
        if not monitor.baselines:
            st.warning("⚠️ No model baselines established yet. Train and validate a model first.")
            st.info("""
            **To establish a baseline:**
            1. Train a model using the training interface
            2. Run validation to establish performance metrics
            3. Baselines will be automatically saved
            """)
            return
        
        # Model selector
        model_name = st.selectbox(
            "Select Model to Monitor",
            options=list(monitor.baselines.keys()),
            key='model_monitor_selector',
            help="Choose which model's performance to analyze"
        )
        
        if not model_name:
            return
        
        # Get dashboard data
        dashboard_data = monitor.get_monitoring_dashboard_data(model_name)
        
        if dashboard_data.get('status') == 'no_baseline':
            st.error(f"❌ No baseline found for {model_name}")
            return
        
        # === BASELINE METRICS ===
        st.subheader("📊 Baseline Performance Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        baseline = dashboard_data['baseline']
        
        with col1:
            st.metric(
                "Baseline MAE",
                f"{baseline['mae']:.4f}",
                help="Mean Absolute Error at baseline"
            )
        
        with col2:
            st.metric(
                "Baseline RMSE",
                f"{baseline['rmse']:.4f}",
                help="Root Mean Squared Error at baseline"
            )
        
        with col3:
            st.metric(
                "Directional Accuracy",
                f"{baseline['directional_accuracy']:.1%}",
                help="Accuracy of predicting direction (up/down)"
            )
        
        with col4:
            st.metric(
                "Baseline Date",
                baseline['established'],
                help="When baseline was established"
            )
        
        st.markdown("---")
        
        # === RECENT PERFORMANCE TREND ===
        st.subheader("📈 Performance Trend (Last 30 Days)")
        
        recent_perf = dashboard_data['recent_performance']
        
        if not recent_perf:
            st.info("📊 No performance data in the last 30 days.")
            st.caption("Performance data will appear here once you start making predictions with this model.")
        else:
            # Create performance trend chart
            perf_df = pd.DataFrame([
                {
                    'Date': p['timestamp'],
                    'Current MAE': p['metrics']['current_mae'],
                    'Baseline MAE': p['metrics']['baseline_mae'],
                    'MAE Degradation %': p['metrics']['mae_degradation_pct'],
                    'Status': p['status']
                }
                for p in recent_perf
            ])
            
            # Ensure Date is datetime
            perf_df['Date'] = pd.to_datetime(perf_df['Date'])
            
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                subplot_titles=('MAE Over Time', 'MAE Degradation %'),
                vertical_spacing=0.12,
                row_heights=[0.6, 0.4]
            )
            
            # Plot 1: MAE trend
            fig.add_trace(
                go.Scatter(
                    x=perf_df['Date'],
                    y=perf_df['Current MAE'],
                    mode='lines+markers',
                    name='Current MAE',
                    line=dict(color='#00C853', width=2)
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=perf_df['Date'],
                    y=perf_df['Baseline MAE'],
                    mode='lines',
                    name='Baseline MAE',
                    line=dict(color='#FF9800', width=2, dash='dash')
                ),
                row=1, col=1
            )
            
            # Plot 2: Degradation %
            fig.add_trace(
                go.Bar(
                    x=perf_df['Date'],
                    y=perf_df['MAE Degradation %'],
                    name='Degradation %',
                    marker=dict(
                        color=perf_df['MAE Degradation %'],
                        colorscale='RdYlGn_r',
                        showscale=False
                    )
                ),
                row=2, col=1
            )
            
            # Add threshold lines
            fig.add_hline(y=10, line_dash="dot", line_color="orange", row=2, col=1,
                         annotation_text="10% Threshold")
            fig.add_hline(y=20, line_dash="dot", line_color="red", row=2, col=1,
                         annotation_text="20% Critical")
            
            fig.update_layout(
                height=600,
                showlegend=True,
                hovermode='x unified',
                template='plotly_dark'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Status summary
            status_counts = perf_df['Status'].value_counts()
            
            if 'CRITICAL' in status_counts:
                st.error(f"🚨 {status_counts['CRITICAL']} CRITICAL alerts detected - immediate retraining recommended")
            elif 'WARNING' in status_counts:
                st.warning(f"⚠️ {status_counts['WARNING']} WARNING alerts - schedule retraining")
            else:
                st.success("✅ Model performance is HEALTHY")
        
        st.markdown("---")
        
        # === DRIFT DETECTION ===
        st.subheader("🔄 Data Drift Detection")
        st.caption("PSI (Population Stability Index) detects changes in feature distributions")
        
        recent_drift = dashboard_data['recent_drift']
        
        if not recent_drift:
            st.info("📊 No drift detection runs in the last 30 days.")
            st.caption("Drift detection will run automatically when new data is processed.")
        else:
            drift_df = pd.DataFrame(recent_drift)
            drift_df['timestamp'] = pd.to_datetime(drift_df['timestamp'])
            
            # Drift score chart
            fig = go.Figure()
            
            fig.add_trace(
                go.Scatter(
                    x=drift_df['timestamp'],
                    y=drift_df['score'],
                    mode='lines+markers',
                    name='Drift Score',
                    line=dict(color='#2196F3', width=3),
                    marker=dict(size=8)
                )
            )
            
            # Threshold lines
            fig.add_hline(y=0.1, line_dash="dot", line_color="yellow",
                         annotation_text="Moderate Drift (0.1)")
            fig.add_hline(y=0.2, line_dash="dot", line_color="red",
                         annotation_text="Significant Drift (0.2)")
            
            fig.update_layout(
                title="PSI Drift Score Over Time",
                xaxis_title="Date",
                yaxis_title="PSI Score",
                height=400,
                hovermode='x unified',
                template='plotly_dark'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Drift summary
            drift_detected_count = sum(1 for d in recent_drift if d['detected'])
            
            if drift_detected_count > 0:
                st.warning(f"⚠️ Drift detected in {drift_detected_count} checks")
                
                # Show recommendations
                retrain_recs = sum(1 for d in recent_drift if d['recommendation'] == 'retrain')
                if retrain_recs > 0:
                    st.error(f"🔄 {retrain_recs} checks recommend RETRAINING")
            else:
                st.success("✅ No significant drift detected")
        
        st.markdown("---")
        
        # === FEATURE IMPORTANCE ===
        st.subheader("🎯 Top Feature Importance")
        st.caption("Most important features used by the model")
        
        top_features = dashboard_data['top_features']
        
        if top_features:
            feature_df = pd.DataFrame(top_features, columns=['Feature', 'Importance'])
            
            fig = go.Figure(
                go.Bar(
                    x=feature_df['Importance'],
                    y=feature_df['Feature'],
                    orientation='h',
                    marker=dict(
                        color=feature_df['Importance'],
                        colorscale='Viridis',
                        showscale=False
                    )
                )
            )
            
            fig.update_layout(
                title="Top 10 Most Important Features",
                xaxis_title="Importance Score",
                yaxis_title="Feature",
                height=400,
                template='plotly_dark'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Display as table too
            with st.expander("📋 View Full Feature Rankings"):
                st.dataframe(feature_df, use_container_width=True, hide_index=True)
        else:
            st.info("No feature importance data available")
        
        st.markdown("---")
        
        # === INSTRUCTIONS ===
        with st.expander("ℹ️ How to Use ML Monitoring"):
            st.markdown("""
            **Establish a Baseline:**
            1. Train your model with high-quality validation data
            2. Use `MLModelMonitor.establish_baseline()` after training
            3. Baseline metrics are automatically saved
            
            **Monitor Performance:**
            1. Call `check_model_performance()` after predictions
            2. Monitor degradation trends over time
            3. Take action when CRITICAL or WARNING alerts appear
            
            **Detect Drift:**
            1. Compare current features vs reference/baseline features
            2. PSI > 0.2 indicates significant drift
            3. Retrain when drift is detected consistently
            """)
        
    except Exception as e:
        st.error(f"❌ Error loading monitoring data: {e}")
        logger.error(f"[MONITOR] Failed to render monitoring page: {e}", exc_info=True)


