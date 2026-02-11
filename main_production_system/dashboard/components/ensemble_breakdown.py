"""
Ensemble Component Breakdown Visualization

Displays interactive breakdown of ensemble model weights and contributions.

Author: ML Analysis Platform Team
Created: 2025-11-05
"""

import logging
from typing import Dict, Optional
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

logger = logging.getLogger(__name__)


def render_ensemble_breakdown(
    prediction_result: Optional[Dict],
    models_dict: Dict
) -> None:
    """
    Render ensemble breakdown visualization.
    
    Args:
        prediction_result: Result from predict_signal() or None
        models_dict: Models dictionary from load_ml_models()
    """
    if prediction_result is None:
        st.info("ℹ️ No prediction available - generate a prediction first")
        return
    
    st.subheader("🔬 ML Model Breakdown")
    
    try:
        from main_production_system.dashboard.core.model_manager import (
            get_ensemble_breakdown
        )
        
        # Get detailed breakdown
        breakdown = get_ensemble_breakdown(prediction_result, models_dict)
        
        if not breakdown:
            st.warning("⚠️ Could not generate ensemble breakdown")
            return
        
        # Display model info
        model_used = breakdown.get('model_used', 'unknown')
        confidence = breakdown.get('confidence', 0.0)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Model Used", model_used.replace('_', ' ').title())
        with col2:
            st.metric("Confidence", f"{confidence:.1%}")
        with col3:
            ensemble_forecast = breakdown.get('ensemble_forecast', 0)
            signal_text = 'BUY' if ensemble_forecast == 1 else 'SELL' if ensemble_forecast == -1 else 'HOLD'
            st.metric("Signal", signal_text)
        
        st.markdown("---")
        
        # Component weights visualization
        weights = breakdown.get('component_weights', {})
        if weights:
            render_component_weights(weights)
        
        # Component predictions
        predictions = breakdown.get('component_predictions', {})
        if predictions:
            render_component_predictions(predictions)
        
        # Confidence breakdown
        confidence_breakdown = breakdown.get('confidence_breakdown', {})
        if confidence_breakdown:
            render_confidence_breakdown(confidence_breakdown)
        
        # Metadata
        render_component_metadata(breakdown, models_dict)
        
    except Exception as e:
        logger.error(f"Error rendering ensemble breakdown: {e}", exc_info=True)
        st.error(f"Failed to render breakdown: {str(e)[:100]}")


def render_component_weights(weights: Dict[str, float]) -> None:
    """Render component weights as bar chart and pie chart."""
    st.write("**Component Weights:**")
    
    if not weights:
        st.info("No weight information available")
        return
    
    # Create DataFrame for visualization
    weight_df = pd.DataFrame({
        'Component': list(weights.keys()),
        'Weight': list(weights.values())
    })
    weight_df['Component'] = weight_df['Component'].str.replace('_', ' ').str.title()
    weight_df = weight_df.sort_values('Weight', ascending=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Bar chart
        fig_bar = go.Figure(data=[
            go.Bar(
                x=weight_df['Weight'],
                y=weight_df['Component'],
                orientation='h',
                marker=dict(color='lightblue'),
                text=[f"{w:.1%}" for w in weight_df['Weight']],
                textposition='auto'
            )
        ])
        fig_bar.update_layout(
            title="Component Weights (Bar Chart)",
            xaxis_title="Weight",
            yaxis_title="Component",
            height=300,
            template='plotly_dark'
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col2:
        # Pie chart
        fig_pie = px.pie(
            weight_df,
            values='Weight',
            names='Component',
            title="Component Weights (Pie Chart)",
            hole=0.4
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(template='plotly_dark', height=300)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Summary table
    st.dataframe(
        weight_df.style.format({'Weight': '{:.1%}'}),
        use_container_width=True,
        hide_index=True
    )


def render_component_predictions(predictions: Dict[str, float]) -> None:
    """Render component predictions in a table."""
    st.write("**Component Predictions:**")
    
    if not predictions:
        st.info("No component prediction information available")
        return
    
    pred_df = pd.DataFrame({
        'Component': list(predictions.keys()),
        'Prediction': list(predictions.values())
    })
    pred_df['Component'] = pred_df['Component'].str.replace('_', ' ').str.title()
    
    # Format predictions
    def format_pred(pred):
        if pred is None:
            return "N/A"
        elif isinstance(pred, (int, np.integer)):
            return str(pred)
        elif isinstance(pred, (float, np.floating)):
            return f"{pred:.4f}"
        else:
            return str(pred)
    
    pred_df['Prediction'] = pred_df['Prediction'].apply(format_pred)
    
    st.dataframe(pred_df, use_container_width=True, hide_index=True)


def render_confidence_breakdown(confidence_breakdown: Dict[str, float]) -> None:
    """Render confidence scores per component."""
    with st.expander("📈 Confidence Breakdown", expanded=False):
        if not confidence_breakdown:
            st.info("No confidence breakdown available")
            return
        
        conf_df = pd.DataFrame({
            'Component': list(confidence_breakdown.keys()),
            'Confidence': list(confidence_breakdown.values())
        })
        conf_df['Component'] = conf_df['Component'].str.replace('_', ' ').str.title()
        
        # Bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=conf_df['Component'],
                y=conf_df['Confidence'],
                marker=dict(color='lightgreen'),
                text=[f"{c:.1%}" for c in conf_df['Confidence']],
                textposition='auto'
            )
        ])
        fig.update_layout(
            title="Confidence Scores by Component",
            xaxis_title="Component",
            yaxis_title="Confidence",
            yaxis=dict(tickformat='.0%'),
            height=300,
            template='plotly_dark'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Table
        st.dataframe(
            conf_df.style.format({'Confidence': '{:.1%}'}),
            use_container_width=True,
            hide_index=True
        )


def render_component_metadata(breakdown: Dict, models_dict: Dict) -> None:
    """Render textual metadata describing component roles."""
    with st.expander("📋 Component Metadata", expanded=False):
        model_used = breakdown.get('model_used', 'unknown')
        
        st.write("**Model Information:**")
        st.write(f"- **Active Model**: {model_used.replace('_', ' ').title()}")
        
        # Component descriptions
        component_descriptions = {
            'xgboost': "XGBoost: Gradient boosting model for price direction prediction",
            'arima_garch': "ARIMA-GARCH: Statistical time series model for trend and volatility",
            'bilstm': "BiLSTM: Bidirectional LSTM neural network for sequence prediction",
            'prophet': "Prophet: Facebook's time series forecasting model with trend and seasonality",
            'transformer': "Transformer: Attention-based model for sequence-to-sequence prediction"
        }
        
        weights = breakdown.get('component_weights', {})
        if weights:
            st.write("**Component Roles:**")
            for component, weight in weights.items():
                desc = component_descriptions.get(component.lower(), f"{component}: Model component")
                st.write(f"- **{component.replace('_', ' ').title()}** ({weight:.1%}): {desc}")
        
        # Model status
        st.write("**Model Status:**")
        for model_key, model_obj in models_dict.items():
            if model_key == 'status':
                continue
            status = '✅ Loaded' if model_obj is not None else '❌ Not Available'
            st.write(f"- {model_key.replace('_', ' ').title()}: {status}")
