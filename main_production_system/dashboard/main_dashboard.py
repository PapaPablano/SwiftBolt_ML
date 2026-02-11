#!/usr/bin/env python3
"""
Main Dashboard - Production System
Streamlit dashboard for monitoring and interacting with the KDJ-Enhanced Hybrid Ensemble.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, List, Optional
import logging
from pathlib import Path
import json
from datetime import datetime, timedelta
import sys

# Add core modules to path
sys.path.append(str(Path(__file__).parent.parent))

from core.hybrid_ensemble import HybridEnsemble, EnsemblePrediction
from core.data_processor import DataProcessor
from core.kdj_feature_engineer import KDJFeatureEngineer

# Import forecasting tab
from dashboard.forecasting_tab import render_forecasting_tab
from main_production_system.dashboard.sidebar_controls import DashboardControls

# Import SuperTrend AI for technical analysis
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.option_analysis.supertrend_ai import calculate_supertrend_ai_features
    SUPERTREND_AVAILABLE = True
    SUPERTREND_SOURCE = "src"
except ImportError:
    # Fallback to core adaptive SuperTrend implementation
    try:
        from core.wave_detection.supertrend_ai import AdaptiveSuperTrend, SuperTrendConfig
        SUPERTREND_AVAILABLE = True
        SUPERTREND_SOURCE = "core"
    except Exception:
        SUPERTREND_AVAILABLE = False
        SUPERTREND_SOURCE = "none"

logger = logging.getLogger(__name__)

class MainDashboard:
    """Production Dashboard for KDJ-Enhanced Hybrid Ensemble System."""
    
    def __init__(self):
        # Initialize session state for model loading if not already set
        if 'models_loaded' not in st.session_state:
            st.session_state.models_loaded = False
        if 'model_path' not in st.session_state:
            st.session_state.model_path = None
        if 'ensemble_initialized' not in st.session_state:
            st.session_state.ensemble_initialized = False
        
        self.ensemble = None
        self.data_processor = DataProcessor()
        self.setup_page_config()
        
        # Restore ensemble if it was previously loaded
        self._restore_ensemble()
        
    def setup_page_config(self):
        """Configure Streamlit page settings."""
        st.set_page_config(
            page_title="ML Analysis Platform - KDJ Enhanced",
            page_icon="📈",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Apply accessibility styles
        try:
            from main_production_system.dashboard.utils.accessibility import apply_accessible_styles
            apply_accessible_styles()
        except ImportError:
            pass  # Continue if accessibility module not available
    
    def _restore_ensemble(self):
        """Restore ensemble from session state if models were previously loaded."""
        if st.session_state.models_loaded and st.session_state.model_path:
            try:
                logger.info(f"[MODEL LOAD] Restoring ensemble from session state with path: {st.session_state.model_path}")
                self.ensemble = HybridEnsemble()
                self.ensemble.load_models(Path(st.session_state.model_path))
                logger.info("[MODEL LOAD] ✅ Ensemble restored successfully")
                st.session_state.ensemble_initialized = True
            except Exception as e:
                logger.error(f"[MODEL LOAD] ❌ Failed to restore ensemble: {e}")
                st.session_state.models_loaded = False
                st.session_state.model_path = None
                self.ensemble = None
        
    def run(self):
        """Run the main dashboard application."""
        st.title("🚀 ML Analysis Platform - KDJ Enhanced Hybrid Ensemble")
        st.markdown("*Production-grade stock prediction with KDJ technical indicators*")
        
        # Sidebar
        self.render_sidebar()
        
        # Main content
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📊 Live Predictions", 
            "📈 Model Performance", 
            "🔧 Feature Analysis",
            "📊 Technical Analysis",
            "⚡ Real-time Monitoring",
            "🌊 Live Forecasting",
            "⚙️ Configuration"
        ])
        
        with tab1:
            self.render_predictions_tab()
            
        with tab2:
            self.render_performance_tab()
            
        with tab3:
            self.render_features_tab()
            
        with tab4:
            self.render_technical_analysis_tab()
            
        with tab5:
            self.render_monitoring_tab()
            
        with tab6:
            self.render_forecasting_tab()
            
        with tab7:
            self.render_config_tab()
    
    def render_sidebar(self):
        """Render sidebar with model controls and accessibility features."""
        try:
            from main_production_system.dashboard.utils.accessibility import (
                help_tooltip,
                info_box,
                section_header
            )
            use_accessibility = True
        except ImportError:
            use_accessibility = False
        
        st.sidebar.header("⚙️ Model Controls")
        
        if use_accessibility:
            st.sidebar.markdown("**Use these controls to configure and load your prediction models.**")
        
        # Model loading section
        st.sidebar.subheader("Load Models")
        
        # XGBoost model path with tooltip
        help_text = help_tooltip("Enter the file path to your trained XGBoost model. Default is 'xgboost_tuned_model.pkl'.")
        xgb_path = st.sidebar.text_input(
            "XGBoost Model Path",
            value="xgboost_tuned_model.pkl",
            help=help_text if use_accessibility else "Path to the trained XGBoost model file"
        )
        
        # Load models button
        load_clicked = st.sidebar.button("🔄 Load Models", type="primary", key="load_models_btn")
        
        if load_clicked:
            logger.info(f"[MODEL LOAD] 🔄 Load Models button clicked with path: {xgb_path}")
            try:
                # Validate model path exists
                model_path_obj = Path(xgb_path)
                if not model_path_obj.exists():
                    error_msg = f"Model file not found: {xgb_path}"
                    logger.error(f"[MODEL LOAD] ❌ {error_msg}")
                    st.sidebar.error(f"❌ {error_msg}")
                else:
                    logger.info(f"[MODEL LOAD] Loading models from: {model_path_obj}")
                    # Create and load ensemble
                    self.ensemble = HybridEnsemble()
                    self.ensemble.load_models(model_path_obj)
                    
                    # Store in session state for persistence
                    st.session_state.models_loaded = True
                    st.session_state.model_path = xgb_path
                    st.session_state.ensemble_initialized = True
                    
                    logger.info("[MODEL LOAD] ✅ Models loaded successfully and stored in session state")
                    st.sidebar.success("✅ Models loaded successfully!")
                    
                    # Verify models are actually loaded
                    if self.ensemble and hasattr(self.ensemble, 'xgboost_model') and self.ensemble.xgboost_model:
                        logger.info("[MODEL LOAD] ✅ XGBoost model verified as loaded")
                    else:
                        logger.warning("[MODEL LOAD] ⚠️ Ensemble created but XGBoost model may not be loaded")
                    
                    # Rerun to update UI
                    st.rerun()
            except FileNotFoundError as e:
                error_msg = f"Model file not found: {xgb_path}"
                logger.error(f"[MODEL LOAD] ❌ {error_msg}: {e}")
                st.sidebar.error(f"❌ {error_msg}")
            except Exception as e:
                error_msg = f"Error loading models: {e}"
                logger.error(f"[MODEL LOAD] ❌ {error_msg}", exc_info=True)
                st.sidebar.error(f"❌ {error_msg}")
                # Clear session state on error
                st.session_state.models_loaded = False
                st.session_state.model_path = None
                st.session_state.ensemble_initialized = False
        
        # Model status
        if self.ensemble:
            try:
                status = self.ensemble.get_model_status()
                st.sidebar.subheader("📊 Model Status")
                st.sidebar.success(f"✅ XGBoost: {'Loaded' if status.get('xgboost_loaded', False) else 'Not Loaded'}")
                st.sidebar.info(f"ℹ️ ARIMA: {'Loaded' if status.get('arima_loaded', False) else 'Not Available'}")
                st.sidebar.metric("Predictions Made", status.get('predictions_made', 0))
            except Exception as e:
                logger.warning(f"[MODEL STATUS] Error getting model status: {e}")
                st.sidebar.info("✅ Models Loaded")
        elif st.session_state.models_loaded:
            # Models marked as loaded in session state but ensemble not initialized
            st.sidebar.warning("⚠️ Models marked as loaded but ensemble not initialized")
            st.sidebar.info(f"Model path: {st.session_state.model_path}")
        else:
            st.sidebar.info("ℹ️ Models Not Loaded")
        
        # Quick actions
        st.sidebar.subheader("⚡ Quick Actions")
        
        if st.sidebar.button("📊 Generate Test Prediction"):
            if self.ensemble:
                self.generate_test_prediction()
            else:
                st.sidebar.error("Load models first!")
                
        if st.sidebar.button("📈 Refresh Dashboard"):
            st.rerun()
    
    def render_predictions_tab(self):
        """Render live predictions tab with organized layout."""
        try:
            from main_production_system.dashboard.components.organized_layout import (
                render_organized_dashboard,
                section_header,
                info_box,
                help_tooltip,
                instructions_box
            )
            use_organized_layout = True
        except ImportError:
            use_organized_layout = False
        
        if not use_organized_layout:
            # Fallback to original layout
            st.header("📊 Live Predictions")
        
        if not self.ensemble:
            info_box(
                "Models Not Loaded",
                "Please load models first using the sidebar controls (⚙️ Model Controls section).",
                icon="⚠️"
            )
            return
        
        if use_organized_layout:
            # Use organized layout: Controls > Key Metrics > Chart > Data Table > Model Details
            self._render_organized_predictions()
        else:
            # Original layout as fallback
            self._render_original_predictions()
    
    def _render_organized_predictions(self):
        """Render predictions using organized layout component."""
        from main_production_system.dashboard.components.organized_layout import (
            render_organized_dashboard,
            render_key_metrics_section,
            render_chart_section,
            render_data_table_section,
            render_model_details_section,
            section_header,
            info_box,
            help_tooltip
        )
        
        # Prepare data for organized layout
        # For now, use placeholder data - will be populated from actual predictions
        key_metrics = {}
        chart_data = None
        chart_config = None
        data_table = None
        model_details = None
        
        # Try to get recent prediction if available
        if self.ensemble and self.ensemble.prediction_history:
            latest_pred = self.ensemble.prediction_history[-1]
            key_metrics = {
                "Ensemble Forecast": {
                    "value": f"${latest_pred.ensemble_forecast:.2f}",
                    "help": "Combined prediction from all models"
                },
                "Confidence": {
                    "value": f"{latest_pred.confidence_score:.1%}",
                    "help": "Prediction confidence based on model agreement"
                },
                "Signal": {
                    "value": latest_pred.directional_signal,
                    "help": "Expected price direction (UP/DOWN/NEUTRAL)"
                }
            }
        
        # Model details
        if self.ensemble:
            status = self.ensemble.get_model_status()
            model_details = {
                "model_name": "KDJ-Enhanced Hybrid Ensemble",
                "model_type": "XGBoost + ARIMA-GARCH",
                "parameters": {
                    "XGBoost Weight": self.ensemble.config['ensemble_weights'].get('xgboost', 0.6),
                    "ARIMA-GARCH Weight": self.ensemble.config['ensemble_weights'].get('arima_garch', 0.4),
                    "Confidence Threshold": self.ensemble.config.get('confidence_threshold', 0.7)
                },
                "performance": status
            }
        
        # Render using organized layout
        render_organized_dashboard(
            controls_section=None,  # Controls are in sidebar
            key_metrics=key_metrics,
            chart_data=chart_data,
            chart_config=chart_config,
            data_table=data_table,
            model_details=model_details,
            title="📊 Live Predictions",
            show_instructions=True
        )
        
        # Add prediction input section
        section_header("🎯 Make New Prediction", level=2, help_text="Generate a new prediction using your data")
        self._render_prediction_inputs()
    
    def _render_prediction_inputs(self):
        """Render prediction input controls with tooltips."""
        try:
            from main_production_system.dashboard.utils.accessibility import help_tooltip, info_box
            use_accessibility = True
        except ImportError:
            use_accessibility = False
        
        # Data input methods
        input_method = st.radio(
            "Input Method:",
            ["Upload CSV File", "Manual Entry", "Sample Data"],
            horizontal=True,
            help=help_tooltip("Choose how to provide data: Upload a file, enter manually, or use sample data") if use_accessibility else None
        )
        
        prediction_data = None
        
        if input_method == "Upload CSV File":
            info_box(
                "Upload CSV File",
                "Upload a CSV file with OHLC (Open, High, Low, Close) data. The file should have columns: date, open, high, low, close, and optionally volume.",
                icon="📁"
            )
            uploaded_file = st.file_uploader(
                "Choose CSV file",
                type="csv",
                help=help_tooltip("Select a CSV file with stock price data") if use_accessibility else None
            )
            if uploaded_file:
                try:
                    prediction_data = pd.read_csv(uploaded_file)
                    st.success(f"✅ Loaded {len(prediction_data)} rows")
                    st.dataframe(prediction_data.head())
                except Exception as e:
                    st.error(f"Error loading file: {e}")
        
        elif input_method == "Manual Entry":
            info_box(
                "Manual Entry",
                "Enter the most recent OHLC (Open, High, Low, Close) prices for the stock. The system will create a time series based on this data.",
                icon="✍️"
            )
            col_open, col_high, col_low, col_close = st.columns(4)
            
            with col_open:
                open_price = st.number_input("Open", value=100.0, step=0.01, help=help_tooltip("Opening price") if use_accessibility else None)
            with col_high:
                high_price = st.number_input("High", value=105.0, step=0.01, help=help_tooltip("Highest price") if use_accessibility else None)
            with col_low:
                low_price = st.number_input("Low", value=98.0, step=0.01, help=help_tooltip("Lowest price") if use_accessibility else None)
            with col_close:
                close_price = st.number_input("Close", value=103.0, step=0.01, help=help_tooltip("Closing price") if use_accessibility else None)
            
            if st.button("Create Prediction Data", help=help_tooltip("Generate time series data from entered prices") if use_accessibility else None):
                dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
                base_prices = np.linspace(95, close_price, 30)
                
                prediction_data = pd.DataFrame({
                    'date': dates,
                    'open': base_prices + np.random.normal(0, 1, 30),
                    'high': base_prices + np.random.normal(2, 1, 30),
                    'low': base_prices + np.random.normal(-2, 1, 30),
                    'close': base_prices + np.random.normal(0, 0.5, 30)
                })
                prediction_data.iloc[-1] = [dates[-1], open_price, high_price, low_price, close_price]
        
        elif input_method == "Sample Data":
            if st.button("Load CRWD Sample Data", help=help_tooltip("Load sample data from CRWD_engineered.csv file") if use_accessibility else None):
                try:
                    if Path("CRWD_engineered.csv").exists():
                        prediction_data = pd.read_csv("CRWD_engineered.csv").tail(30)
                        st.success("✅ Loaded CRWD sample data")
                    else:
                        st.error("CRWD_engineered.csv not found")
                except Exception as e:
                    st.error(f"Error loading sample data: {e}")
        
        # Generate prediction
        if prediction_data is not None and st.button("🔮 Generate Prediction", type="primary", help=help_tooltip("Generate prediction using loaded data") if use_accessibility else None):
            try:
                with st.spinner("Generating prediction..."):
                    prediction = self.ensemble.predict(prediction_data)
                    self.display_prediction_results(prediction)
            except Exception as e:
                st.error(f"Prediction failed: {e}")
    
    def _render_original_predictions(self):
        """Original predictions tab layout (fallback)."""
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🎯 Make New Prediction")
            
            # Data input methods
            input_method = st.radio(
                "Input Method:",
                ["Upload CSV File", "Manual Entry", "Sample Data"],
                horizontal=True
            )
            
            prediction_data = None
            
            # Same input logic as _render_prediction_inputs but without accessibility features
            if input_method == "Upload CSV File":
                uploaded_file = st.file_uploader("Choose CSV file", type="csv")
                if uploaded_file:
                    try:
                        prediction_data = pd.read_csv(uploaded_file)
                        st.success(f"✅ Loaded {len(prediction_data)} rows")
                        st.dataframe(prediction_data.head())
                    except Exception as e:
                        st.error(f"Error loading file: {e}")
            
            elif input_method == "Manual Entry":
                st.subheader("Enter OHLC Data")
                col_open, col_high, col_low, col_close = st.columns(4)
                
                with col_open:
                    open_price = st.number_input("Open", value=100.0, step=0.01)
                with col_high:
                    high_price = st.number_input("High", value=105.0, step=0.01)
                with col_low:
                    low_price = st.number_input("Low", value=98.0, step=0.01)
                with col_close:
                    close_price = st.number_input("Close", value=103.0, step=0.01)
                
                if st.button("Create Prediction Data"):
                    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
                    base_prices = np.linspace(95, close_price, 30)
                    
                    prediction_data = pd.DataFrame({
                        'date': dates,
                        'open': base_prices + np.random.normal(0, 1, 30),
                        'high': base_prices + np.random.normal(2, 1, 30),
                        'low': base_prices + np.random.normal(-2, 1, 30),
                        'close': base_prices + np.random.normal(0, 0.5, 30)
                    })
                    prediction_data.iloc[-1] = [dates[-1], open_price, high_price, low_price, close_price]
            
            elif input_method == "Sample Data":
                if st.button("Load CRWD Sample Data"):
                    try:
                        if Path("CRWD_engineered.csv").exists():
                            prediction_data = pd.read_csv("CRWD_engineered.csv").tail(30)
                            st.success("✅ Loaded CRWD sample data")
                        else:
                            st.error("CRWD_engineered.csv not found")
                    except Exception as e:
                        st.error(f"Error loading sample data: {e}")
            
            # Generate prediction
            if prediction_data is not None and st.button("🔮 Generate Prediction", type="primary"):
                try:
                    with st.spinner("Generating prediction..."):
                        prediction = self.ensemble.predict(prediction_data)
                        self.display_prediction_results(prediction)
                except Exception as e:
                    st.error(f"Prediction failed: {e}")
        
        with col2:
            st.subheader("📋 Recent Predictions")
            if self.ensemble and self.ensemble.prediction_history:
                recent_predictions = self.ensemble.prediction_history[-5:]
                for i, pred in enumerate(reversed(recent_predictions)):
                    with st.expander(f"Prediction #{len(self.ensemble.prediction_history)-i}"):
                        st.metric("Ensemble Forecast", f"${pred.ensemble_forecast:.2f}")
                        st.metric("Confidence", f"{pred.confidence_score:.1%}")
                        st.metric("Signal", pred.directional_signal)
                        st.caption(pred.timestamp)
            else:
                st.info("No predictions yet")
    
    def render_performance_tab(self):
        """Render model performance analysis tab."""
        st.header("📈 Model Performance Analysis")
        
        if not self.ensemble:
            st.warning("⚠️ Load models first using the sidebar controls.")
            return
        
        # Model information
        model_info = self.ensemble.xgboost_trainer.get_model_info()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Features", model_info.get('n_features', 'N/A'))
            
        with col2:
            st.metric("Estimators", model_info.get('n_estimators', 'N/A'))
            
        with col3:
            kdj_info = model_info.get('kdj_analysis', {})
            kdj_pct = kdj_info.get('kdj_importance_percentage', 0)
            st.metric("KDJ Importance", f"{kdj_pct:.1f}%")
        
        # Feature importance
        if self.ensemble.xgboost_model:
            st.subheader("🔍 Feature Importance")
            
            importance = self.ensemble.xgboost_trainer.get_feature_importance()
            
            # Top 15 features
            top_features = importance.head(15)
            
            fig = px.bar(
                x=top_features.values,
                y=top_features.index,
                orientation='h',
                title="Top 15 Feature Importance",
                labels={'x': 'Importance', 'y': 'Features'}
            )
            fig.update_layout(height=600)
            st.plotly_chart(fig, use_container_width=True)
            
            # KDJ feature analysis
            kdj_features = importance[importance.index.str.contains('kdj', case=False)]
            if len(kdj_features) > 0:
                st.subheader("📊 KDJ Feature Analysis")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig_kdj = px.pie(
                        values=kdj_features.values,
                        names=kdj_features.index,
                        title="KDJ Feature Importance Distribution"
                    )
                    st.plotly_chart(fig_kdj, use_container_width=True)
                
                with col2:
                    st.dataframe(kdj_features.to_frame('Importance'))
    
    def render_features_tab(self):
        """Render feature analysis tab."""
        st.header("🔧 Feature Engineering Analysis")
        
        st.subheader("📊 KDJ Indicator Configuration")
        
        # Current KDJ settings
        feature_engineer = KDJFeatureEngineer()
        current_config = feature_engineer.config
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("KDJ Period", current_config['kdj_period'])
            
        with col2:
            st.metric("K Smoothing", current_config['k_smooth'])
            
        with col3:
            st.metric("D Smoothing", current_config['d_smooth'])
        
        # Feature engineering demo
        st.subheader("🧪 Feature Engineering Demo")
        
        if st.button("Demo Feature Creation"):
            # Create sample data
            dates = pd.date_range('2024-01-01', periods=100, freq='D')
            sample_data = pd.DataFrame({
                'date': dates,
                'open': 100 + np.cumsum(np.random.normal(0, 1, 100)),
                'high': 100 + np.cumsum(np.random.normal(0.5, 1, 100)),
                'low': 100 + np.cumsum(np.random.normal(-0.5, 1, 100)),
                'close': 100 + np.cumsum(np.random.normal(0, 0.8, 100))
            })
            
            # Generate features
            features = feature_engineer.create_features(sample_data, include_kdj=True)
            
            st.success(f"✅ Generated {len(features.columns)} features from {len(sample_data)} data points")
            
            # Show feature groups
            feature_groups = feature_engineer.get_feature_importance_groups(features)
            
            for group_name, group_features in feature_groups.items():
                with st.expander(f"{group_name.title()} ({len(group_features)} features)"):
                    st.write(group_features)
        
        # Feature validation
        st.subheader("✅ Feature Validation")
        
        sample_file = st.selectbox(
            "Select data file for validation:",
            ["CRWD_engineered.csv", "CRWD_daily.csv", "Upload custom file"]
        )
        
        if sample_file != "Upload custom file" and Path(sample_file).exists():
            if st.button("Validate Features"):
                try:
                    data = pd.read_csv(sample_file)
                    features = feature_engineer.create_features(data, include_kdj=True)
                    validation = feature_engineer.validate_features(features)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Total Features", validation['total_features'])
                        st.metric("KDJ Features", len(validation['kdj_features']))
                        st.metric("Valid Samples", validation['total_samples'])
                    
                    with col2:
                        st.json(validation['warnings'])
                        
                except Exception as e:
                    st.error(f"Validation failed: {e}")
    
    def render_technical_analysis_tab(self):
        """Render technical analysis tab with SuperTrend AI visualization."""
        st.header("📊 Technical Analysis")
        st.caption("Advanced technical indicators including SuperTrend AI")
        
        if not SUPERTREND_AVAILABLE:
            st.error("❌ SuperTrend AI module not available. Please check installation.")
            return
        
        # Data input section
        st.subheader("📈 Data Input")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Sample data options
            data_option = st.radio(
                "Choose data source:",
                ["Sample Data", "Upload CSV", "Manual Entry"],
                horizontal=True
            )
            
            sample_data = None
            
            if data_option == "Sample Data":
                if st.button("Generate Sample Data"):
                    # Create sample OHLC data
                    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
                    np.random.seed(42)
                    base_price = 100
                    prices = base_price + np.cumsum(np.random.normal(0, 1.5, 100))
                    
                    sample_data = pd.DataFrame({
                        'timestamp': dates,
                        'open': prices + np.random.normal(0, 0.5, 100),
                        'high': prices + np.random.normal(1, 0.5, 100),
                        'low': prices + np.random.normal(-1, 0.5, 100),
                        'close': prices + np.random.normal(0, 0.3, 100),
                        'volume': np.random.randint(1000000, 5000000, 100)
                    })
                    st.success("✅ Sample data generated")
            
            elif data_option == "Upload CSV":
                uploaded_file = st.file_uploader("Choose CSV file", type="csv")
                if uploaded_file:
                    try:
                        sample_data = pd.read_csv(uploaded_file)
                        # Ensure required columns exist
                        required_cols = ['open', 'high', 'low', 'close']
                        if all(col in sample_data.columns for col in required_cols):
                            st.success(f"✅ Loaded {len(sample_data)} rows")
                        else:
                            st.error(f"❌ Missing required columns: {required_cols}")
                            sample_data = None
                    except Exception as e:
                        st.error(f"Error loading file: {e}")
            
            elif data_option == "Manual Entry":
                st.subheader("Enter OHLC Data")
                col_open, col_high, col_low, col_close = st.columns(4)
                
                with col_open:
                    open_price = st.number_input("Open", value=100.0, step=0.01)
                with col_high:
                    high_price = st.number_input("High", value=105.0, step=0.01)
                with col_low:
                    low_price = st.number_input("Low", value=98.0, step=0.01)
                with col_close:
                    close_price = st.number_input("Close", value=103.0, step=0.01)
                
                if st.button("Create Sample Series"):
                    # Create sample time series for features
                    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
                    base_prices = np.linspace(95, close_price, 30)
                    
                    sample_data = pd.DataFrame({
                        'timestamp': dates,
                        'open': base_prices + np.random.normal(0, 1, 30),
                        'high': base_prices + np.random.normal(2, 1, 30),
                        'low': base_prices + np.random.normal(-2, 1, 30),
                        'close': base_prices + np.random.normal(0, 0.5, 30),
                        'volume': np.random.randint(1000000, 5000000, 30)
                    })
                    sample_data.iloc[-1] = [dates[-1], open_price, high_price, low_price, close_price, 2000000]
                    st.success("✅ Sample series created")
        
        with col2:
            st.metric("Data Points", len(sample_data) if sample_data is not None else 0)
            if sample_data is not None:
                current_price = sample_data['close'].iloc[-1]
                st.metric("Current Price", f"${current_price:.2f}")
        
        # SuperTrend AI Analysis
        if sample_data is not None:
            st.divider()
            st.subheader("🤖 SuperTrend AI Analysis")
            
            try:
                with st.spinner("Calculating SuperTrend AI..."):
                    if SUPERTREND_SOURCE == "src":
                        # Existing src-based implementation
                        st_features = calculate_supertrend_ai_features(
                            sample_data,
                            atr_length=10,
                            min_mult=1.0,
                            max_mult=5.0,
                            step=0.5,
                            perf_alpha=10.0,
                            from_cluster='Best',
                        )
                    elif SUPERTREND_SOURCE == "core":
                        # New core adaptive SuperTrend implementation
                        required_cols = ['open', 'high', 'low', 'close']
                        if 'volume' not in sample_data.columns:
                            sample_data['volume'] = 0
                        if not all(c in sample_data.columns for c in required_cols):
                            raise ValueError(f"Missing required columns: {required_cols}")
                        ast = AdaptiveSuperTrend(SuperTrendConfig())
                        st_core = ast.compute_features(sample_data)
                        # Map to expected column names used below for display
                        st_features = pd.DataFrame(index=sample_data.index)
                        st_features['supertrend_ai'] = st_core['st_band']
                        st_features['supertrend_ai_trend'] = st_core['st_trend_dir']
                        st_features['supertrend_ai_signal'] = st_core['st_long_entry'].replace({0: 0, 1: 1})
                        st_features['supertrend_ai_upper'] = np.where(
                            st_core['st_trend_dir'] > 0, st_core['st_band'], np.nan
                        )
                        st_features['supertrend_ai_lower'] = np.where(
                            st_core['st_trend_dir'] < 0, st_core['st_band'], np.nan
                        )
                        st_features['supertrend_ai_distance'] = (
                            (sample_data['close'] - st_core['st_band']) / sample_data['close'] * 100
                        )
                        st_features['supertrend_ai_ama'] = st_core['st_best_multiplier']
                    else:
                        raise RuntimeError("SuperTrend AI source unavailable")
                
                # Display current SuperTrend status
                current_supertrend = st_features['supertrend_ai'].iloc[-1]
                current_trend = st_features['supertrend_ai_trend'].iloc[-1]
                current_signal = st_features['supertrend_ai_signal'].iloc[-1]
                current_price = sample_data['close'].iloc[-1]
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("SuperTrend Level", f"${current_supertrend:.2f}")
                
                with col2:
                    trend_text = "Bullish" if current_trend == 1 else "Bearish"
                    trend_color = "normal" if current_trend == 1 else "inverse"
                    st.metric("Trend", trend_text, delta_color=trend_color)
                
                with col3:
                    if current_signal == 1:
                        st.metric("Signal", "BUY", delta="Buy Signal", delta_color="normal")
                    elif current_signal == -1:
                        st.metric("Signal", "SELL", delta="Sell Signal", delta_color="inverse")
                    else:
                        st.metric("Signal", "HOLD", delta="Hold", delta_color="off")
                
                with col4:
                    distance = current_price - current_supertrend
                    distance_pct = (distance / current_price) * 100
                    st.metric("Distance", f"{distance_pct:+.2f}%")
                
                # SuperTrend Chart
                st.subheader("📈 SuperTrend AI Chart")
                
                # Create the chart
                fig = go.Figure()
                
                # Add candlestick chart
                fig.add_trace(go.Candlestick(
                    x=sample_data['timestamp'],
                    open=sample_data['open'],
                    high=sample_data['high'],
                    low=sample_data['low'],
                    close=sample_data['close'],
                    name="Price",
                    increasing_line_color='#26a69a',
                    decreasing_line_color='#ef5350'
                ))
                
                # Add SuperTrend AI with dynamic coloring
                if 'supertrend_ai' in st_features.columns and 'supertrend_ai_trend' in st_features.columns:
                    # Create segments for dynamic coloring
                    trend_changes = st_features['supertrend_ai_trend'].diff().fillna(0) != 0
                    segment_starts = st_features.index[trend_changes].tolist() + [len(st_features)]
                    
                    for i in range(len(segment_starts) - 1):
                        start_idx = segment_starts[i]
                        end_idx = segment_starts[i + 1]
                        segment_df = st_features.iloc[start_idx:end_idx]
                        segment_timestamps = sample_data['timestamp'].iloc[start_idx:end_idx]
                        
                        # Determine color based on trend
                        trend_value = segment_df['supertrend_ai_trend'].iloc[0]
                        color = '#10b981' if trend_value == 1 else '#ef4444'
                        
                        # Create segment
                        fig.add_trace(go.Scatter(
                            x=segment_timestamps,
                            y=segment_df['supertrend_ai'],
                            name='SuperTrend AI' if i == 0 else None,
                            line=dict(color=color, width=3),
                            mode='lines',
                            hovertemplate='SuperTrend: $%{y:.2f}<br>Trend: %{customdata}<extra></extra>',
                            customdata=[('Bullish' if trend_value == 1 else 'Bearish')] * len(segment_df),
                            showlegend=False if i > 0 else True
                        ))
                
                # Add upper and lower bands
                if 'supertrend_ai_upper' in st_features.columns and 'supertrend_ai_lower' in st_features.columns:
                    fig.add_trace(go.Scatter(
                        x=sample_data['timestamp'],
                        y=st_features['supertrend_ai_upper'],
                        name='Upper Band',
                        line=dict(color='rgba(16, 185, 129, 0.3)', width=1, dash='dash'),
                        mode='lines',
                        hovertemplate='Upper: $%{y:.2f}<extra></extra>'
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=sample_data['timestamp'],
                        y=st_features['supertrend_ai_lower'],
                        name='Lower Band',
                        line=dict(color='rgba(239, 68, 68, 0.3)', width=1, dash='dash'),
                        mode='lines',
                        hovertemplate='Lower: $%{y:.2f}<extra></extra>'
                    ))
                
                # Update layout
                fig.update_layout(
                    title="SuperTrend AI Analysis",
                    xaxis_title="Date",
                    yaxis_title="Price ($)",
                    hovermode='x unified',
                    height=600,
                    showlegend=True
                )
                
                # Remove range selector for cleaner look
                fig.update_layout(xaxis=dict(rangeslider=dict(visible=False)))
                
                st.plotly_chart(fig, use_container_width=True)
                
                # SuperTrend Statistics
                st.subheader("📊 SuperTrend Statistics")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Trend Analysis**")
                    bullish_periods = (st_features['supertrend_ai_trend'] == 1).sum()
                    bearish_periods = (st_features['supertrend_ai_trend'] == -1).sum()
                    total_periods = len(st_features)
                    
                    st.metric("Bullish Periods", f"{bullish_periods} ({bullish_periods/total_periods*100:.1f}%)")
                    st.metric("Bearish Periods", f"{bearish_periods} ({bearish_periods/total_periods*100:.1f}%)")
                
                with col2:
                    st.markdown("**Signal Analysis**")
                    buy_signals = (st_features['supertrend_ai_signal'] == 1).sum()
                    sell_signals = (st_features['supertrend_ai_signal'] == -1).sum()
                    
                    st.metric("Buy Signals", buy_signals)
                    st.metric("Sell Signals", sell_signals)
                
                # Feature details
                with st.expander("🔍 SuperTrend AI Feature Details"):
                    feature_cols = ['supertrend_ai', 'supertrend_ai_trend', 'supertrend_ai_ama', 
                                  'supertrend_ai_signal', 'supertrend_ai_distance']
                    display_df = st_features[feature_cols].tail(10)
                    st.dataframe(display_df, use_container_width=True)
                
            except Exception as e:
                st.error(f"❌ SuperTrend AI calculation failed: {e}")
                import traceback
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())
        else:
            st.info("👆 Please select or generate data to view SuperTrend AI analysis")
    
    def render_monitoring_tab(self):
        """Render real-time monitoring tab."""
        st.header("⚡ Real-time System Monitoring")
        
        # System status
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if self.ensemble:
                status = self.ensemble.get_model_status()
                if status['xgboost_loaded']:
                    st.success("🟢 System Online")
                else:
                    st.error("🔴 System Offline")
            else:
                st.error("🔴 Models Not Loaded")
        
        with col2:
            st.metric("Uptime", "98.5%")  # Placeholder
            
        with col3:
            st.metric("Response Time", "45ms")  # Placeholder
        
        # Prediction history chart
        if self.ensemble and self.ensemble.prediction_history:
            st.subheader("📈 Prediction History")
            
            history_df = pd.DataFrame([
                {
                    'timestamp': pred.timestamp,
                    'forecast': pred.ensemble_forecast,
                    'confidence': pred.confidence_score,
                    'signal': pred.directional_signal
                }
                for pred in self.ensemble.prediction_history
            ])
            
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('Forecast Values', 'Confidence Scores'),
                vertical_spacing=0.1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=history_df['timestamp'],
                    y=history_df['forecast'],
                    name='Ensemble Forecast',
                    line=dict(color='blue')
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=history_df['timestamp'],
                    y=history_df['confidence'],
                    name='Confidence Score',
                    line=dict(color='green')
                ),
                row=2, col=1
            )
            
            fig.update_layout(height=600, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        
        # Performance metrics (if available)
        st.subheader("📊 Performance Metrics")
        
        if Path("monitoring_reports").exists():
            try:
                # Load latest monitoring report
                reports = list(Path("monitoring_reports").glob("*.txt"))
                if reports:
                    latest_report = max(reports, key=lambda x: x.stat().st_mtime)
                    with open(latest_report, 'r') as f:
                        report_content = f.read()
                    
                    st.text_area(
                        "Latest Monitoring Report",
                        report_content,
                        height=300,
                        disabled=True
                    )
            except Exception as e:
                st.error(f"Error loading monitoring reports: {e}")
    
    def render_forecasting_tab(self):
        """Render the Live Forecasting tab."""
        render_forecasting_tab()
    
    def render_config_tab(self):
        """Render configuration tab."""
        st.header("⚙️ System Configuration")
        
        if not self.ensemble:
            st.warning("⚠️ Load models first to access configuration.")
            return
        
        # Ensemble weights configuration
        st.subheader("⚖️ Ensemble Weights")
        
        current_weights = self.ensemble.config['ensemble_weights']
        
        col1, col2 = st.columns(2)
        
        with col1:
            xgb_weight = st.slider(
                "XGBoost Weight",
                min_value=0.0,
                max_value=1.0,
                value=current_weights['xgboost'],
                step=0.05
            )
        
        with col2:
            arima_weight = st.slider(
                "ARIMA-GARCH Weight",
                min_value=0.0,
                max_value=1.0,
                value=current_weights['arima_garch'],
                step=0.05
            )
        
        # Normalize weights
        total_weight = xgb_weight + arima_weight
        if total_weight > 0:
            xgb_weight_norm = xgb_weight / total_weight
            arima_weight_norm = arima_weight / total_weight
            
            st.info(f"Normalized weights: XGBoost {xgb_weight_norm:.2f}, ARIMA-GARCH {arima_weight_norm:.2f}")
            
            if st.button("Update Weights"):
                try:
                    self.ensemble.update_ensemble_weights({
                        'xgboost': xgb_weight_norm,
                        'arima_garch': arima_weight_norm
                    })
                    st.success("✅ Weights updated successfully!")
                except Exception as e:
                    st.error(f"Error updating weights: {e}")
        
        # Prediction settings
        st.subheader("🎯 Prediction Settings")
        
        confidence_threshold = st.slider(
            "Confidence Threshold",
            min_value=0.0,
            max_value=1.0,
            value=self.ensemble.config['confidence_threshold'],
            step=0.05,
            help="Minimum confidence for reliable predictions"
        )
        
        directional_threshold = st.slider(
            "Directional Threshold (%)",
            min_value=0.5,
            max_value=5.0,
            value=self.ensemble.config['directional_threshold'] * 100,
            step=0.1,
            help="Minimum price change % for directional signals"
        )
        
        if st.button("Update Settings"):
            self.ensemble.config['confidence_threshold'] = confidence_threshold
            self.ensemble.config['directional_threshold'] = directional_threshold / 100
            st.success("✅ Settings updated!")
    
    def display_prediction_results(self, prediction: EnsemblePrediction):
        """Display prediction results in an organized format."""
        st.subheader("🎯 Prediction Results")
        
        # Main metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🎯 Ensemble Forecast",
                f"${prediction.ensemble_forecast:.2f}",
                help="Combined prediction from all models"
            )
        
        with col2:
            confidence_color = "normal"
            if prediction.confidence_score > 0.8:
                confidence_color = "normal"
            elif prediction.confidence_score > 0.6:
                confidence_color = "normal"
            else:
                confidence_color = "inverse"
                
            st.metric(
                "🎯 Confidence",
                f"{prediction.confidence_score:.1%}",
                help="Prediction confidence based on model agreement"
            )
        
        with col3:
            signal_emoji = {"UP": "📈", "DOWN": "📉", "NEUTRAL": "➡️"}
            st.metric(
                "📊 Signal",
                f"{signal_emoji.get(prediction.directional_signal, '❓')} {prediction.directional_signal}",
                help="Expected price direction"
            )
        
        with col4:
            st.metric(
                "🤖 XGBoost",
                f"${prediction.xgboost_forecast:.2f}",
                help="XGBoost component prediction"
            )
        
        # Component breakdown
        st.subheader("🔍 Component Analysis")
        
        components_data = {
            'Model': ['XGBoost', 'ARIMA-GARCH'],
            'Forecast': [prediction.xgboost_forecast, prediction.arima_forecast or 0],
            'Weight': [prediction.component_weights['xgboost'], prediction.component_weights['arima_garch']],
            'Contribution': [
                prediction.xgboost_forecast * prediction.component_weights['xgboost'],
                (prediction.arima_forecast or 0) * prediction.component_weights['arima_garch']
            ]
        }
        
        components_df = pd.DataFrame(components_data)
        st.dataframe(components_df, use_container_width=True)
        
        # Metadata
        with st.expander("📋 Prediction Metadata"):
            st.json(prediction.prediction_metadata)
    
    def generate_test_prediction(self):
        """Generate a test prediction with sample data."""
        try:
            # Create sample data
            sample_data = pd.DataFrame({
                'open': [100.0, 101.0, 99.5],
                'high': [102.0, 103.0, 101.0],
                'low': [99.0, 100.0, 98.5],
                'close': [101.5, 99.8, 100.3]
            })
            
            with st.spinner("Generating test prediction..."):
                prediction = self.ensemble.predict(sample_data)
                
            st.sidebar.success("✅ Test prediction generated!")
            
            # Display in sidebar
            st.sidebar.metric("Test Forecast", f"${prediction.ensemble_forecast:.2f}")
            st.sidebar.metric("Confidence", f"{prediction.confidence_score:.1%}")
            
        except Exception as e:
            st.sidebar.error(f"Test prediction failed: {e}")

def main():
    """Main function to run the dashboard with optional page routing."""
    # Unified sidebar rendered once at top level
    try:
        DashboardControls.render_sidebar()
    except Exception:
        # If controls module unavailable, continue with legacy sidebar
        pass

    # Simple page switch to new Technical Analysis page without disrupting legacy tabs
    st.sidebar.markdown("---")
    page_choice = st.sidebar.radio(
        "Navigation",
        ("Legacy Dashboard", "📊 Technical Analysis (New)")
    )

    if page_choice == "📊 Technical Analysis (New)":
        try:
            from main_production_system.dashboard.pages.technical_analysis import (
                render_technical_analysis,
            )

            render_technical_analysis()
            return
        except Exception as exc:
            st.warning(f"Falling back to legacy dashboard: {exc}")

    dashboard = MainDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()