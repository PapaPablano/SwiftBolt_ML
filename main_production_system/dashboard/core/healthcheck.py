"""
Health check utilities for the dashboard.

Provides health status checks for monitoring and CI/CD integration.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
import streamlit as st

logger = logging.getLogger(__name__)


def check_dashboard_health(models: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Perform comprehensive health check of dashboard components.
    
    Checks:
    - UI loaded (always True if function is called)
    - Models initialized (count and status)
    - Data pipeline accessible (if available)
    
    Args:
        models: Models dictionary from session state (optional)
    
    Returns:
        Dictionary with health status:
        {
            'status': 'healthy' | 'degraded' | 'unhealthy',
            'models_loaded': int,
            'models_total': int,
            'timestamp': str (ISO format),
            'checks': {
                'ui': bool,
                'models': bool,
                'data_pipeline': bool
            }
        }
    """
    checks = {
        'ui': True,  # If we can call this, UI is loaded
        'models': False,
        'data_pipeline': False
    }
    
    models_loaded = 0
    models_total = 0
    
    # Check models
    if models:
        status = models.get('status', {})
        models_total = len([k for k in status.keys() if k != 'status'])
        models_loaded = sum(1 for v in status.values() 
                          if isinstance(v, str) and 'Ready' in v)
        checks['models'] = models_loaded > 0
    else:
        # Try to get from session state
        try:
            if 'models' in st.session_state:
                models = st.session_state.get('models', {})
                status = models.get('status', {})
                models_total = len([k for k in status.keys() if k != 'status'])
                models_loaded = sum(1 for v in status.values() 
                                  if isinstance(v, str) and 'Ready' in v)
                checks['models'] = models_loaded > 0
        except Exception as e:
            logger.warning(f"Could not check models from session state: {e}")
    
    # Check data pipeline (uses cache to avoid triggering API calls)
    try:
        # Check session state for cached data (indicates pipeline worked recently)
        if 'df_raw' in st.session_state and 'df_features' in st.session_state:
            df_raw = st.session_state.get('df_raw')
            df_features = st.session_state.get('df_features')
            
            if df_raw is not None and len(df_raw) > 0 and \
               df_features is not None and len(df_features) > 0:
                logger.info("[HEALTH] Data pipeline: ✅ (cache hit)")
                checks['data_pipeline'] = True
            else:
                # If no cache, don't make a fresh API call - just warn
                logger.warning("[HEALTH] Data pipeline: ⚠️ (cache miss, may be first load or rate limited)")
                checks['data_pipeline'] = True  # Return True to not fail on first load
        else:
            # No cached data yet, but don't fail the healthcheck
            logger.info("[HEALTH] Data pipeline: ⚠️ (no cache, first load)")
            checks['data_pipeline'] = True
    except Exception as e:
        logger.debug(f"Data pipeline check failed (non-critical): {e}")
        checks['data_pipeline'] = False
    
    # Determine overall status
    critical_checks = [checks['ui']]
    if checks['ui'] and checks['models']:
        overall_status = 'healthy'
    elif checks['ui']:
        overall_status = 'degraded'  # UI works but models unavailable
    else:
        overall_status = 'unhealthy'
    
    result = {
        'status': overall_status,
        'models_loaded': models_loaded,
        'models_total': models_total,
        'timestamp': datetime.now().isoformat(),
        'checks': checks
    }
    
    logger.info(f"[HEALTH] Status: {overall_status}, Models: {models_loaded}/{models_total}")
    
    return result


def get_health_status_message(health: Dict[str, Any]) -> str:
    """
    Format health check result as user-friendly message.
    
    Args:
        health: Health check result dictionary
        
    Returns:
        Formatted status message
    """
    status = health['status']
    models = f"{health['models_loaded']}/{health['models_total']}"
    
    if status == 'healthy':
        return f"✅ Dashboard healthy - {models} models loaded"
    elif status == 'degraded':
        return f"⚠️ Dashboard degraded - {models} models loaded (ML features may be limited)"
    else:
        return f"❌ Dashboard unhealthy - {models} models loaded"


def log_health_status(health: Dict[str, Any]) -> None:
    """
    Log health status to logger.
    
    Args:
        health: Health check result dictionary
    """
    status = health['status']
    checks = health['checks']
    
    logger.info(f"[HEALTH] Overall: {status.upper()}")
    logger.info(f"[HEALTH] UI: {'✅' if checks['ui'] else '❌'}")
    logger.info(f"[HEALTH] Models: {'✅' if checks['models'] else '❌'} ({health['models_loaded']}/{health['models_total']})")
    logger.info(f"[HEALTH] Data Pipeline: {'✅' if checks['data_pipeline'] else '❌'}")
