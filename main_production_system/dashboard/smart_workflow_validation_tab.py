#!/usr/bin/env python3
"""
Smart Workflow Dashboard - Enhanced Validation Tab
Provides a streamlined 3-tab interface for walk-forward validation with all new enhancements.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# Import enhanced validation components
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.enhanced_walk_forward_validation import EnhancedWalkForwardValidator, EnhancedValidationSummary
    from core.enhanced_validation_reporter import EnhancedValidationReporter
    ENHANCED_VALIDATION_AVAILABLE = True
except ImportError:
    ENHANCED_VALIDATION_AVAILABLE = False

logger = logging.getLogger(__name__)


def render_smart_workflow_validation_tab():
    """
    Render the Smart Workflow Validation Tab.
    
    This follows the Smart Workflow Dashboard mode with 3 streamlined tabs:
    1. Data Configuration
    2. Review & Edit (optional)
    3. Process & Results
    """
    
    st.title("🎯 Enhanced Walk-Forward Validation")
    st.markdown("**Smart Workflow Dashboard Mode** - Comprehensive validation with all new enhancements")
    
    # Initialize session state
    if 'validation_data' not in st.session_state:
        st.session_state.validation_data = None
    if 'validation_results' not in st.session_state:
        st.session_state.validation_results = None
    if 'validation_progress' not in st.session_state:
        st.session_state.validation_progress = 0
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📊 Data Configuration", "🔍 Review & Edit", "⚡ Process & Results"])
    
    with tab1:
        render_data_configuration_tab()
    
    with tab2:
        render_review_edit_tab()
    
    with tab3:
        render_process_results_tab()


def render_data_configuration_tab():
    """Render the Data Configuration tab."""
    st.header("📊 Data Configuration")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Data Source")
        
        # Data source selection
        data_source = st.selectbox(
            "Select Data Source",
            ["Upload CSV", "Use Sample Data", "Load from File"],
            help="Choose how to load your OHLC data for validation"
        )
        
        if data_source == "Upload CSV":
            uploaded_file = st.file_uploader(
                "Upload OHLC Data (CSV)",
                type=['csv'],
                help="Upload a CSV file with columns: timestamp, open, high, low, close, volume"
            )
            
            if uploaded_file is not None:
                try:
                    data = pd.read_csv(uploaded_file)
                    st.session_state.validation_data = data
                    st.success(f"✅ Data loaded successfully! {len(data)} rows, {len(data.columns)} columns")
                    
                    # Show data preview
                    with st.expander("📋 Data Preview", expanded=True):
                        st.dataframe(data.head(10), use_container_width=True)
                        
                        # Data quality check
                        st.subheader("🔍 Data Quality Check")
                        quality_metrics = check_data_quality(data)
                        display_data_quality(quality_metrics)
                        
                except Exception as e:
                    st.error(f"❌ Error loading data: {e}")
        
        elif data_source == "Use Sample Data":
            if st.button("Generate Sample Data", type="primary"):
                data = generate_sample_data()
                st.session_state.validation_data = data
                st.success(f"✅ Sample data generated! {len(data)} rows")
                
                with st.expander("📋 Sample Data Preview", expanded=True):
                    st.dataframe(data.head(10), use_container_width=True)
        
        elif data_source == "Load from File":
            file_path = st.text_input(
                "File Path",
                value="CRWD_daily.csv",
                help="Enter the path to your data file"
            )
            
            if st.button("Load File", type="primary"):
                try:
                    data = pd.read_csv(file_path)
                    st.session_state.validation_data = data
                    st.success(f"✅ Data loaded from {file_path}! {len(data)} rows")
                except Exception as e:
                    st.error(f"❌ Error loading file: {e}")
    
    with col2:
        st.subheader("Validation Settings")
        
        # Basic settings
        ticker = st.text_input("Ticker Symbol", value="CRWD", help="Symbol for tracking results")
        
        # Advanced settings
        with st.expander("⚙️ Advanced Settings", expanded=False):
            initial_train_size = st.number_input(
                "Initial Training Size", 
                min_value=50, 
                max_value=1000, 
                value=200,
                help="Size of initial training window"
            )
            
            test_size = st.number_input(
                "Test Window Size", 
                min_value=5, 
                max_value=50, 
                value=15,
                help="Size of each test window"
            )
            
            step_size = st.number_input(
                "Step Size", 
                min_value=1, 
                max_value=20, 
                value=5,
                help="How many periods to step forward each iteration"
            )
            
            window_type = st.selectbox(
                "Window Type",
                ["expanding", "rolling"],
                help="Expanding: growing training set, Rolling: fixed size"
            )
        
        # Enhanced features
        with st.expander("🚀 Enhanced Features", expanded=True):
            enable_enhanced_validation = st.checkbox(
                "Enhanced Validation", 
                value=True,
                help="Enable purged CV, residual diagnostics, benchmark comparison"
            )
            
            enable_supertrend_ai = st.checkbox(
                "SuperTrend AI", 
                value=True,
                help="Enable SuperTrend AI multi-factor analysis"
            )
            
            enable_kdj_features = st.checkbox(
                "KDJ Features", 
                value=True,
                help="Enable KDJ-enhanced features"
            )
        
        # Store settings in session state
        st.session_state.validation_settings = {
            'ticker': ticker,
            'initial_train_size': initial_train_size,
            'test_size': test_size,
            'step_size': step_size,
            'window_type': window_type,
            'enable_enhanced_validation': enable_enhanced_validation,
            'enable_supertrend_ai': enable_supertrend_ai,
            'enable_kdj_features': enable_kdj_features
        }
        
        # Progress indicator
        progress = 0
        if st.session_state.validation_data is not None:
            progress += 50
        if 'validation_settings' in st.session_state:
            progress += 50
        
        st.session_state.validation_progress = progress
        
        # Progress bar
        st.progress(progress / 100)
        st.caption(f"Configuration Progress: {progress}%")
        
        if progress == 100:
            st.success("✅ Configuration Complete! Ready for validation.")
        else:
            st.info("ℹ️ Complete data configuration to proceed.")


def render_review_edit_tab():
    """Render the Review & Edit tab."""
    st.header("🔍 Review & Edit")
    
    if st.session_state.validation_data is None:
        st.warning("⚠️ Please configure data in Tab 1 first.")
        return
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📊 Data Overview")
        
        data = st.session_state.validation_data
        
        # Basic statistics
        st.metric("Total Rows", len(data))
        st.metric("Total Columns", len(data.columns))
        
        if 'close' in data.columns:
            st.metric("Price Range", f"${data['close'].min():.2f} - ${data['close'].max():.2f}")
            st.metric("Average Price", f"${data['close'].mean():.2f}")
        
        # Data quality summary
        quality_metrics = check_data_quality(data)
        
        st.subheader("🔍 Data Quality")
        col_quality_1, col_quality_2 = st.columns(2)
        
        with col_quality_1:
            st.metric("Missing Values", quality_metrics['missing_values'])
            st.metric("Duplicates", quality_metrics['duplicates'])
        
        with col_quality_2:
            st.metric("Completeness", f"{quality_metrics['completeness']:.1%}")
            st.metric("Quality Score", f"{quality_metrics['quality_score']:.1f}/10")
        
        # Data preview
        with st.expander("📋 Full Data Preview", expanded=False):
            st.dataframe(data, use_container_width=True)
    
    with col2:
        st.subheader("⚙️ Validation Configuration")
        
        if 'validation_settings' not in st.session_state:
            st.warning("⚠️ Please configure validation settings in Tab 1 first.")
            return
        
        settings = st.session_state.validation_settings
        
        # Display current settings
        st.json(settings)
        
        # Allow editing
        st.subheader("✏️ Edit Settings")
        
        new_ticker = st.text_input("Ticker Symbol", value=settings['ticker'])
        new_initial_train_size = st.number_input(
            "Initial Training Size", 
            min_value=50, 
            max_value=1000, 
            value=settings['initial_train_size']
        )
        new_test_size = st.number_input(
            "Test Window Size", 
            min_value=5, 
            max_value=50, 
            value=settings['test_size']
        )
        new_step_size = st.number_input(
            "Step Size", 
            min_value=1, 
            max_value=20, 
            value=settings['step_size']
        )
        new_window_type = st.selectbox(
            "Window Type",
            ["expanding", "rolling"],
            index=0 if settings['window_type'] == 'expanding' else 1
        )
        
        # Update settings if changed
        if st.button("Update Settings", type="primary"):
            st.session_state.validation_settings.update({
                'ticker': new_ticker,
                'initial_train_size': new_initial_train_size,
                'test_size': new_test_size,
                'step_size': new_step_size,
                'window_type': new_window_type
            })
            st.success("✅ Settings updated!")
            st.rerun()
        
        # Validation preview
        st.subheader("📈 Validation Preview")
        
        if len(data) >= settings['initial_train_size'] + settings['test_size']:
            max_windows = (len(data) - settings['initial_train_size'] - settings['test_size']) // settings['step_size'] + 1
            st.metric("Estimated Windows", max_windows)
            st.metric("Training Data Points", settings['initial_train_size'])
            st.metric("Test Data Points per Window", settings['test_size'])
        else:
            st.error("❌ Insufficient data for validation")
    
    # Optional: Data preprocessing
    with st.expander("🔧 Data Preprocessing (Optional)", expanded=False):
        st.info("Advanced data preprocessing options will be available here.")
        
        # Placeholder for future preprocessing options
        if st.button("Apply Preprocessing", disabled=True):
            st.info("Preprocessing features coming soon!")


def render_process_results_tab():
    """Render the Process & Results tab."""
    st.header("⚡ Process & Results")
    
    if st.session_state.validation_data is None or 'validation_settings' not in st.session_state:
        st.warning("⚠️ Please complete configuration in Tabs 1 and 2 first.")
        return
    
    if not ENHANCED_VALIDATION_AVAILABLE:
        st.error("❌ Enhanced validation components not available. Please check installation.")
        return
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🚀 Run Validation")
        
        settings = st.session_state.validation_settings
        data = st.session_state.validation_data
        
        # Validation summary
        st.info(f"""
        **Validation Summary:**
        - Ticker: {settings['ticker']}
        - Data Points: {len(data)}
        - Training Size: {settings['initial_train_size']}
        - Test Size: {settings['test_size']}
        - Step Size: {settings['step_size']}
        - Window Type: {settings['window_type']}
        - Enhanced Features: {settings['enable_enhanced_validation']}
        """)
        
        # Run validation button
        if st.button("🚀 Start Enhanced Validation", type="primary", use_container_width=True):
            with st.spinner("Running enhanced walk-forward validation..."):
                try:
                    # Initialize validator
                    validator = EnhancedWalkForwardValidator(
                        initial_train_size=settings['initial_train_size'],
                        test_size=settings['test_size'],
                        step_size=settings['step_size'],
                        window_type=settings['window_type'],
                        enable_enhanced_validation=settings['enable_enhanced_validation'],
                        enable_supertrend_ai=settings['enable_supertrend_ai'],
                        enable_kdj_features=settings['enable_kdj_features']
                    )
                    
                    # Run validation
                    summary = validator.validate_ensemble_enhanced(
                        data, 
                        ticker=settings['ticker'],
                        save_results=True
                    )
                    
                    st.session_state.validation_results = summary
                    st.success("✅ Validation completed successfully!")
                    
                except Exception as e:
                    st.error(f"❌ Validation failed: {e}")
                    logger.error(f"Validation error: {e}")
    
    with col2:
        st.subheader("📊 Quick Stats")
        
        if st.session_state.validation_results is not None:
            summary = st.session_state.validation_results
            
            # Key metrics
            col_metric_1, col_metric_2 = st.columns(2)
            
            with col_metric_1:
                st.metric("Total Windows", summary.total_windows)
                st.metric("Mean MAE", f"{summary.mean_mae:.2f}")
                st.metric("Mean R²", f"{summary.mean_r_squared:.3f}")
            
            with col_metric_2:
                st.metric("Dir. Accuracy", f"{summary.mean_directional_accuracy:.1f}%")
                st.metric("ST Accuracy", f"{summary.mean_supertrend_accuracy:.1f}%")
                st.metric("Quality Score", f"{summary.residual_diagnostics_pass_rate:.1%}")
            
            # Performance targets
            st.subheader("🎯 Performance Targets")
            targets_met = 0
            total_targets = len(summary.performance_targets_met)
            
            for target, met in summary.performance_targets_met.items():
                status = "✅" if met else "❌"
                st.write(f"{status} {target.replace('_', ' ').title()}")
                if met:
                    targets_met += 1
            
            st.metric("Targets Met", f"{targets_met}/{total_targets}")
        else:
            st.info("Run validation to see results")
    
    # Results visualization
    if st.session_state.validation_results is not None:
        st.subheader("📈 Results Visualization")
        
        summary = st.session_state.validation_results
        window_results = summary.window_results
        
        # Create tabs for different visualizations
        viz_tab1, viz_tab2, viz_tab3, viz_tab4 = st.tabs([
            "📊 Performance Trends", 
            "🎯 Regime Analysis", 
            "🤖 SuperTrend AI", 
            "📋 Detailed Report"
        ])
        
        with viz_tab1:
            render_performance_trends(summary, window_results)
        
        with viz_tab2:
            render_regime_analysis(summary, window_results)
        
        with viz_tab3:
            render_supertrend_analysis(summary, window_results)
        
        with viz_tab4:
            render_detailed_report(summary, window_results)
        
        # Export options
        st.subheader("💾 Export Results")
        
        col_export_1, col_export_2, col_export_3 = st.columns(3)
        
        with col_export_1:
            if st.button("📄 Export Summary", use_container_width=True):
                export_summary_to_csv(summary)
        
        with col_export_2:
            if st.button("📊 Export Charts", use_container_width=True):
                export_charts(summary, window_results)
        
        with col_export_3:
            if st.button("📋 Full Report", use_container_width=True):
                generate_full_report(summary, window_results)


def check_data_quality(data: pd.DataFrame) -> Dict[str, Any]:
    """Check data quality and return metrics."""
    metrics = {}
    
    # Basic metrics
    metrics['total_rows'] = len(data)
    metrics['total_columns'] = len(data.columns)
    metrics['missing_values'] = data.isnull().sum().sum()
    metrics['duplicates'] = data.duplicated().sum()
    
    # Completeness
    total_cells = data.size
    missing_cells = data.isnull().sum().sum()
    metrics['completeness'] = (total_cells - missing_cells) / total_cells if total_cells > 0 else 0
    
    # Required columns check
    required_cols = ['open', 'high', 'low', 'close']
    missing_required = [col for col in required_cols if col not in data.columns]
    metrics['missing_required_columns'] = missing_required
    
    # Quality score (0-10)
    quality_score = 10
    if metrics['missing_values'] > 0:
        quality_score -= 2
    if metrics['duplicates'] > 0:
        quality_score -= 1
    if missing_required:
        quality_score -= 3
    if metrics['completeness'] < 0.95:
        quality_score -= 2
    
    metrics['quality_score'] = max(0, quality_score)
    
    return metrics


def display_data_quality(metrics: Dict[str, Any]):
    """Display data quality metrics."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Missing Values", metrics['missing_values'])
    
    with col2:
        st.metric("Duplicates", metrics['duplicates'])
    
    with col3:
        st.metric("Completeness", f"{metrics['completeness']:.1%}")
    
    with col4:
        st.metric("Quality Score", f"{metrics['quality_score']:.1f}/10")
    
    if metrics['missing_required_columns']:
        st.warning(f"⚠️ Missing required columns: {', '.join(metrics['missing_required_columns'])}")


def generate_sample_data() -> pd.DataFrame:
    """Generate sample OHLC data for testing."""
    np.random.seed(42)
    n = 1000
    dates = pd.date_range('2020-01-01', periods=n, freq='D')
    
    # Generate synthetic OHLC data
    returns = np.random.normal(0, 0.02, n)
    prices = 100 * np.exp(np.cumsum(returns))
    
    data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.normal(0, 0.001, n)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.005, n))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.005, n))),
        'close': prices,
        'volume': np.random.randint(1000, 10000, n)
    })
    
    return data


def render_performance_trends(summary: Any, window_results: List[Dict]):
    """Render performance trends visualization."""
    df = pd.DataFrame(window_results)
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('MAE Trend', 'Directional Accuracy', 'R-squared Trend', 'SuperTrend Accuracy'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
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
    
    fig.update_layout(height=600, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def render_regime_analysis(summary: Any, window_results: List[Dict]):
    """Render volatility regime analysis."""
    df = pd.DataFrame(window_results)
    
    # Regime distribution
    regime_counts = df['volatility_regime'].value_counts()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie chart
        fig_pie = go.Figure(data=[go.Pie(labels=regime_counts.index, values=regime_counts.values)])
        fig_pie.update_layout(title="Regime Distribution")
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # MAE by regime
        fig_box = go.Figure()
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            regime_data = df[df['volatility_regime'] == regime]['mae']
            if len(regime_data) > 0:
                fig_box.add_trace(go.Box(y=regime_data, name=regime))
        fig_box.update_layout(title="MAE by Volatility Regime", yaxis_title="MAE")
        st.plotly_chart(fig_box, use_container_width=True)


def render_supertrend_analysis(summary: Any, window_results: List[Dict]):
    """Render SuperTrend AI analysis."""
    df = pd.DataFrame(window_results)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # SuperTrend accuracy trend
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['window'], y=df['supertrend_accuracy'], mode='lines+markers', name='ST Accuracy'))
        fig.update_layout(title="SuperTrend AI Accuracy Over Time", xaxis_title="Window", yaxis_title="Accuracy (%)")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Factor distribution
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=df['supertrend_factor'], nbinsx=20, name='Factor Distribution'))
        fig.update_layout(title="SuperTrend Factor Distribution", xaxis_title="Factor Value", yaxis_title="Frequency")
        st.plotly_chart(fig, use_container_width=True)


def render_detailed_report(summary: Any, window_results: List[Dict]):
    """Render detailed validation report."""
    st.subheader("📋 Detailed Validation Report")
    
    # Executive summary
    with st.expander("📊 Executive Summary", expanded=True):
        st.write(f"**Performance Score:** {summary.mean_directional_accuracy:.1f}%")
        st.write(f"**Total Windows:** {summary.total_windows}")
        st.write(f"**Mean MAE:** {summary.mean_mae:.2f}")
        st.write(f"**Mean R²:** {summary.mean_r_squared:.3f}")
        st.write(f"**SuperTrend Accuracy:** {summary.mean_supertrend_accuracy:.1f}%")
    
    # Performance targets
    with st.expander("🎯 Performance Targets", expanded=True):
        for target, met in summary.performance_targets_met.items():
            status = "✅" if met else "❌"
            st.write(f"{status} {target.replace('_', ' ').title()}")
    
    # Recommendations
    with st.expander("💡 Recommendations", expanded=True):
        for i, rec in enumerate(summary.recommendations, 1):
            st.write(f"{i}. {rec}")
    
    # Window results table
    with st.expander("📊 Window Results", expanded=False):
        df = pd.DataFrame(window_results)
        st.dataframe(df, use_container_width=True)


def export_summary_to_csv(summary: Any):
    """Export validation summary to CSV."""
    # Create summary data
    summary_data = {
        'Metric': ['Total Windows', 'Mean MAE', 'Mean RMSE', 'Mean MAPE', 'Mean Directional Accuracy', 
                  'Mean R²', 'Mean Sharpe Ratio', 'Mean SuperTrend Accuracy', 'Mean KDJ Importance',
                  'Residual Diagnostics Pass Rate', 'Benchmark Avg Rank'],
        'Value': [summary.total_windows, summary.mean_mae, summary.mean_rmse, summary.mean_mape,
                 summary.mean_directional_accuracy, summary.mean_r_squared, summary.mean_sharpe_ratio,
                 summary.mean_supertrend_accuracy, summary.mean_kdj_importance,
                 summary.residual_diagnostics_pass_rate, summary.benchmark_comparison_avg_rank]
    }
    
    df = pd.DataFrame(summary_data)
    csv = df.to_csv(index=False)
    
    st.download_button(
        label="📄 Download Summary CSV",
        data=csv,
        file_name=f"validation_summary_{summary.ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


def export_charts(summary: Any, window_results: List[Dict]):
    """Export validation charts."""
    st.info("Chart export functionality will be implemented with the enhanced validation reporter.")


def generate_full_report(summary: Any, window_results: List[Dict]):
    """Generate full validation report."""
    st.info("Full report generation will be implemented with the enhanced validation reporter.")


# Main function for testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="Enhanced Walk-Forward Validation",
        page_icon="🎯",
        layout="wide"
    )
    
    render_smart_workflow_validation_tab()
