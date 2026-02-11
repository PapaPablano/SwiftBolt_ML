"""
Session state and cache utilities for the unified dashboard.

Author: Cursor Agent
Created: 2025-10-31
"""

from __future__ import annotations

# Third-party imports
import streamlit as st

# Standard library imports
import logging

# Local imports
from .model_manager import load_ml_models

logger = logging.getLogger(__name__)


def initialize_session_state() -> None:
    """Initialize Streamlit session state with required keys and cached models."""
    try:
        if "models" not in st.session_state:
            logger.info("[SESSION] Loading models into session state...")
            models = load_ml_models()
            # Always ensure models dict exists, even if empty
            if not isinstance(models, dict):
                logger.warning("[SESSION] load_ml_models() did not return a dict, creating empty models dict")
                st.session_state.models = {}
            else:
                st.session_state.models = models
                # Log model initialization status
                status = models.get('status', {})
                models_loaded = sum(1 for v in status.values() if isinstance(v, str) and 'Ready' in v)
                if models_loaded == 0:
                    logger.warning("[SESSION] ⚠️ No models loaded successfully")
                else:
                    logger.info(f"[SESSION] ✅ {models_loaded} model(s) initialized")
        else:
            logger.debug("[SESSION] Models already in session state")
            
        if "market_data" not in st.session_state:
            st.session_state.market_data = {}
        if "current_symbol" not in st.session_state:
            st.session_state.current_symbol = "AAPL"
        if "current_timeframe" not in st.session_state:
            st.session_state.current_timeframe = "1d"
            
        logger.info("[SESSION] ✅ Session state initialized successfully")
        
    except Exception as e:
        logger.error(f"[SESSION] ❌ Failed to initialize session state: {e}", exc_info=True)
        # Ensure models dict exists even on failure
        if "models" not in st.session_state:
            st.session_state.models = {}
        if "market_data" not in st.session_state:
            st.session_state.market_data = {}
        if "current_symbol" not in st.session_state:
            st.session_state.current_symbol = "AAPL"
        if "current_timeframe" not in st.session_state:
            st.session_state.current_timeframe = "1d"
        # Don't raise - allow dashboard to continue with degraded functionality
        logger.warning("[SESSION] Continuing with empty models dict - ML features will be unavailable")


def initialize_models_in_session():
    """Initialize model cache in session state on app startup."""
    try:
        if 'models' not in st.session_state:
            logger.info("[SESSION] Initializing models in session state...")
            models = load_ml_models()
            # Validate models dict
            if not isinstance(models, dict):
                logger.error("[SESSION] load_ml_models() returned invalid type, creating empty dict")
                st.session_state.models = {}
                return {}
            
            st.session_state.models = models
            logger.info("[SESSION] ✅ Models loaded")
        else:
            logger.debug("[SESSION] Models already initialized in session state")
        
        # Ensure we always return a dict
        models = st.session_state.get('models', {})
        if not isinstance(models, dict):
            logger.warning("[SESSION] Models in session state is not a dict, resetting")
            st.session_state.models = {}
            return {}
            
        return models
        
    except Exception as e:
        logger.error(f"[SESSION] ❌ Failed to initialize models: {e}", exc_info=True)
        # Return empty dict on failure - don't crash the app
        st.session_state.models = {}
        return {}


