"""
Organized Dashboard Layout Component

Provides standardized layout following:
Controls > Key Metrics > Chart > Data Table > Model Details

With tooltips, info-boxes, and brief instructions for non-technical users.

Author: ML Analysis Platform Team
Date: 2025-01-27
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Dict, Any, List
from datetime import datetime

from main_production_system.dashboard.utils.accessibility import (
    apply_accessible_styles,
    info_box,
    help_tooltip,
    section_header,
    instructions_box,
    accessible_metric,
    create_accessible_chart_layout,
    get_wcag_compliant_plotly_colors,
    AccessibleColors,
    AccessibleFonts,
    AccessibleSpacing
)


def render_organized_dashboard(
    controls_section: callable,
    key_metrics: Dict[str, Any],
    chart_data: Optional[pd.DataFrame],
    chart_config: Optional[Dict],
    data_table: Optional[pd.DataFrame],
    model_details: Optional[Dict[str, Any]],
    title: str = "Dashboard",
    show_instructions: bool = True
):
    """
    Render dashboard with standardized layout:
    1. Controls
    2. Key Metrics
    3. Chart
    4. Data Table
    5. Model Details
    
    Args:
        controls_section: Function that renders controls in sidebar or top section
        key_metrics: Dictionary of key metrics to display
        chart_data: DataFrame for chart rendering
        chart_config: Chart configuration dictionary
        data_table: DataFrame for data table display
        model_details: Dictionary of model details
        title: Dashboard title
        show_instructions: Whether to show instructions box
    """
    # Apply accessibility styles
    apply_accessible_styles()
    
    # Title
    st.title(title)
    
    # Brief instructions for non-technical users
    if show_instructions:
        instructions_box(
            title="How to Use This Dashboard",
            steps=[
                "Use the **Controls** section (left sidebar) to select your stock symbol and settings",
                "Review the **Key Metrics** to see current predictions and confidence levels",
                "Examine the **Chart** to visualize price trends and forecasts",
                "Check the **Data Table** for detailed historical data",
                "Explore **Model Details** to understand how predictions are made"
            ]
        )
    
    # =========================================================================
    # SECTION 1: CONTROLS
    # =========================================================================
    section_header(
        "⚙️ Controls",
        level=2,
        help_text="Use these controls to configure your analysis"
    )
    
    # Render controls (typically in sidebar, but can be in main area)
    if controls_section:
        controls_section()
    
    st.markdown("---")
    
    # =========================================================================
    # SECTION 2: KEY METRICS
    # =========================================================================
    section_header(
        "📊 Key Metrics",
        level=2,
        help_text="Current predictions and performance indicators"
    )
    
    if key_metrics:
        render_key_metrics_section(key_metrics)
    else:
        info_box(
            "No Metrics Available",
            "Metrics will appear here once analysis is run. Use the Controls section to start.",
            icon="⚠️"
        )
    
    st.markdown("---")
    
    # =========================================================================
    # SECTION 3: CHART
    # =========================================================================
    section_header(
        "📈 Chart",
        level=2,
        help_text="Visual representation of price data and predictions"
    )
    
    if chart_data is not None and chart_config:
        render_chart_section(chart_data, chart_config)
    else:
        info_box(
            "No Chart Data",
            "Chart will appear here once data is loaded. Use the Controls section to fetch data.",
            icon="📊"
        )
    
    st.markdown("---")
    
    # =========================================================================
    # SECTION 4: DATA TABLE
    # =========================================================================
    section_header(
        "📋 Data Table",
        level=2,
        help_text="Detailed historical data and predictions"
    )
    
    if data_table is not None and len(data_table) > 0:
        render_data_table_section(data_table)
    else:
        info_box(
            "No Data Available",
            "Data table will appear here once data is loaded. Use the Controls section to fetch data.",
            icon="📋"
        )
    
    st.markdown("---")
    
    # =========================================================================
    # SECTION 5: MODEL DETAILS
    # =========================================================================
    section_header(
        "🔧 Model Details",
        level=2,
        help_text="Technical information about the prediction models"
    )
    
    if model_details:
        render_model_details_section(model_details)
    else:
        info_box(
            "No Model Details",
            "Model details will appear here once models are loaded. Use the Controls section to load models.",
            icon="🔧"
        )


def render_key_metrics_section(metrics: Dict[str, Any]):
    """
    Render key metrics in an accessible grid layout.
    
    Args:
        metrics: Dictionary with metric_name: metric_value pairs
    """
    # Group metrics into columns (responsive grid)
    metric_items = list(metrics.items())
    
    # Create 3-4 columns depending on number of metrics
    num_cols = min(4, len(metric_items))
    cols = st.columns(num_cols)
    
    for idx, (label, value_dict) in enumerate(metric_items):
        col = cols[idx % num_cols]
        
        with col:
            if isinstance(value_dict, dict):
                value = value_dict.get('value', 'N/A')
                delta = value_dict.get('delta')
                help_text = value_dict.get('help')
                delta_color = value_dict.get('delta_color', 'normal')
                
                accessible_metric(
                    label=label,
                    value=str(value),
                    delta=delta,
                    help_text=help_text,
                    delta_color=delta_color
                )
            else:
                st.metric(label, str(value_dict))


def render_chart_section(data: pd.DataFrame, config: Dict[str, Any]):
    """
    Render chart with accessibility considerations.
    
    Args:
        data: DataFrame with chart data
        config: Chart configuration dict with keys:
            - title: Chart title
            - x_col: Column name for x-axis
            - y_col: Column name for y-axis
            - chart_type: 'line', 'candlestick', 'bar', etc.
            - additional_traces: List of additional trace configs
    """
    chart_type = config.get('chart_type', 'line')
    title = config.get('title', 'Chart')
    x_col = config.get('x_col', data.columns[0])
    y_col = config.get('y_col', data.columns[1])
    
    # Create accessible layout
    layout = create_accessible_chart_layout(title, height=500)
    
    # Create figure
    fig = go.Figure(layout=layout)
    
    # Add main trace
    colors = get_wcag_compliant_plotly_colors()
    
    if chart_type == 'line':
        fig.add_trace(go.Scatter(
            x=data[x_col],
            y=data[y_col],
            mode='lines',
            name=config.get('trace_name', y_col),
            line=dict(color=colors[0], width=2)
        ))
    elif chart_type == 'candlestick' and all(col in data.columns for col in ['open', 'high', 'low', 'close']):
        fig.add_trace(go.Candlestick(
            x=data[x_col] if x_col in data.columns else data.index,
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            name='Price',
            increasing_line_color=AccessibleColors.SUCCESS,
            decreasing_line_color=AccessibleColors.ERROR
        ))
    
    # Add additional traces if specified
    if 'additional_traces' in config:
        for i, trace_config in enumerate(config['additional_traces']):
            fig.add_trace(go.Scatter(
                x=data[trace_config.get('x_col', x_col)],
                y=data[trace_config.get('y_col')],
                mode=trace_config.get('mode', 'lines'),
                name=trace_config.get('name', f'Trace {i+1}'),
                line=dict(color=colors[(i+1) % len(colors)], width=2)
            ))
    
    # Display chart with info
    info_box(
        "Chart Information",
        f"This chart shows {title.lower()}. Use the zoom and pan tools to explore different time periods. "
        "Hover over data points for detailed values.",
        icon="📊"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_data_table_section(data: pd.DataFrame, max_rows: int = 100):
    """
    Render data table with accessibility considerations.
    
    Args:
        data: DataFrame to display
        max_rows: Maximum rows to display (default 100 for performance)
    """
    if len(data) > max_rows:
        st.info(f"Showing first {max_rows} rows of {len(data)} total rows. Use filters to see more.")
        display_data = data.head(max_rows)
    else:
        display_data = data
    
    # Info box explaining the table
    info_box(
        "Data Table",
        "This table shows detailed historical data. Columns include price information (Open, High, Low, Close), "
        "Volume, and any calculated indicators or predictions.",
        icon="📋"
    )
    
    # Display with styling
    st.dataframe(
        display_data,
        use_container_width=True,
        height=400
    )
    
    # Download option
    csv = display_data.to_csv(index=False)
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv,
        file_name=f"data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        help=help_tooltip("Download the displayed data as a CSV file")
    )


def render_model_details_section(details: Dict[str, Any]):
    """
    Render model details in an organized, accessible format.
    
    Args:
        details: Dictionary with model information:
            - model_name: Name of the model
            - model_type: Type of model (XGBoost, ARIMA-GARCH, etc.)
            - parameters: Dict of model parameters
            - performance: Dict of performance metrics
            - feature_importance: Optional DataFrame or dict
    """
    model_name = details.get('model_name', 'Unknown Model')
    model_type = details.get('model_type', 'Unknown Type')
    
    st.markdown(f"### Model: {model_name}")
    st.caption(f"Type: {model_type}")
    
    # Parameters section
    if 'parameters' in details:
        st.markdown("#### 📐 Model Parameters")
        params = details['parameters']
        if isinstance(params, dict):
            params_df = pd.DataFrame([
                {"Parameter": k, "Value": str(v)}
                for k, v in params.items()
            ])
            st.dataframe(params_df, use_container_width=True, hide_index=True)
    
    # Performance section
    if 'performance' in details:
        st.markdown("#### 📊 Performance Metrics")
        perf = details['performance']
        
        # Display as metrics
        perf_items = list(perf.items())
        num_cols = min(3, len(perf_items))
        cols = st.columns(num_cols)
        
        for idx, (metric_name, metric_value) in enumerate(perf_items):
            with cols[idx % num_cols]:
                accessible_metric(
                    label=metric_name,
                    value=str(metric_value),
                    help_text=f"{metric_name} performance metric"
                )
    
    # Feature importance (if available)
    if 'feature_importance' in details:
        st.markdown("#### 🔍 Feature Importance")
        feat_imp = details['feature_importance']
        
        info_box(
            "Feature Importance",
            "This shows which features (indicators) the model considers most important when making predictions. "
            "Higher values indicate greater influence on the model's predictions.",
            icon="🔍"
        )
        
        if isinstance(feat_imp, pd.DataFrame):
            st.dataframe(feat_imp, use_container_width=True)
        elif isinstance(feat_imp, dict):
            feat_df = pd.DataFrame([
                {"Feature": k, "Importance": v}
                for k, v in feat_imp.items()
            ]).sort_values('Importance', ascending=False)
            st.dataframe(feat_df, use_container_width=True)
    
    # Additional information
    if 'additional_info' in details:
        with st.expander("📚 Additional Information"):
            st.markdown(details['additional_info'])

