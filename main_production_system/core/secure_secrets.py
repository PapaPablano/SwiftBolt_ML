"""
Secure Secrets Management for API Keys

Provides secure access to API keys using Streamlit secrets with fallback to environment variables.
Never hardcodes API keys in source code.

Usage:
    from main_production_system.core.secure_secrets import get_api_key
    
    polygon_key = get_api_key('POLYGON_API_KEY')
    alpha_key = get_api_key('ALPHA_VANTAGE_API_KEY')

Author: ML Analysis Platform Team
Date: 2025-01-27
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Try to import streamlit (only available in Streamlit context)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    st = None


def get_api_key(key_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get API key securely from Streamlit secrets or environment variable.
    
    Priority order:
    1. Streamlit secrets (if in Streamlit context)
    2. Environment variable
    
    Args:
        key_name: Name of the API key (e.g., 'POLYGON_API_KEY', 'ALPHA_VANTAGE_API_KEY')
        default: Default value if key not found (None = no default)
    
    Returns:
        API key string or None/default if not found
    
    Example:
        >>> polygon_key = get_api_key('POLYGON_API_KEY')
        >>> alpha_key = get_api_key('ALPHA_VANTAGE_API_KEY', default='')
    """
    # Priority 1: Streamlit secrets (most secure for Streamlit apps)
    if STREAMLIT_AVAILABLE and st is not None:
        try:
            if hasattr(st, 'secrets') and st.secrets is not None:
                # Try direct key access first
                if key_name in st.secrets:
                    logger.debug(f"API key '{key_name}' loaded from Streamlit secrets")
                    return st.secrets[key_name]
                
                # Try using .get() method (more graceful)
                if hasattr(st.secrets, 'get'):
                    value = st.secrets.get(key_name)
                    if value:
                        logger.debug(f"API key '{key_name}' loaded from Streamlit secrets")
                        return value
        except (AttributeError, KeyError, Exception) as e:
            logger.debug(f"Could not load '{key_name}' from Streamlit secrets: {e}")
    
    # Priority 2: Environment variable
    env_value = os.getenv(key_name)
    if env_value:
        logger.debug(f"API key '{key_name}' loaded from environment variable")
        return env_value
    
    # Return default or None
    if default is not None:
        logger.debug(f"API key '{key_name}' using default value")
        return default
    
    logger.warning(f"API key '{key_name}' not found in secrets or environment variables")
    return None


def get_polygon_key() -> Optional[str]:
    """Get Polygon.io API key securely."""
    return get_api_key('POLYGON_API_KEY')


def get_alpha_vantage_key() -> Optional[str]:
    """Get Alpha Vantage API key securely."""
    return get_api_key('ALPHA_VANTAGE_API_KEY', default='')


def get_finnhub_key() -> Optional[str]:
    """Get Finnhub API key securely."""
    return get_api_key('FINNHUB_API_KEY', default='')

def get_aws_access_key() -> Optional[str]:
    """Get AWS Access Key ID securely."""
    return get_api_key('AWS_ACCESS_KEY_ID')

def get_aws_secret_key() -> Optional[str]:
    """Get AWS Secret Access Key securely."""
    return get_api_key('AWS_SECRET_ACCESS_KEY')

def get_aws_region() -> Optional[str]:
    """Get AWS Default Region securely."""
    return get_api_key('AWS_DEFAULT_REGION', default='us-east-1')


def has_api_key(key_name: str) -> bool:
    """
    Check if API key is available without returning the value.
    
    Args:
        key_name: Name of the API key
    
    Returns:
        True if key is available, False otherwise
    """
    key = get_api_key(key_name)
    return key is not None and key != ''


def validate_api_keys() -> dict:
    """
    Validate which API keys are configured.
    
    Returns:
        Dictionary with status for each provider:
        {
            'polygon': bool,
            'alpha_vantage': bool,
            'finnhub': bool,
            'yahoo_finance': True  # Always available (no key needed)
        }
    """
    return {
        'polygon': has_api_key('POLYGON_API_KEY'),
        'alpha_vantage': has_api_key('ALPHA_VANTAGE_API_KEY'),
        'finnhub': has_api_key('FINNHUB_API_KEY'),
        'yahoo_finance': True,  # Always available (no API key needed)
        'aws_access_key': has_api_key('AWS_ACCESS_KEY_ID'),
        'aws_secret_key': has_api_key('AWS_SECRET_ACCESS_KEY'),
        'aws_region': has_api_key('AWS_DEFAULT_REGION')
    }


# Convenience function for backward compatibility
def load_secret_api_key(provider: str = 'alpha_vantage') -> Optional[str]:
    """
    Load API key for a specific provider (backward compatibility function).
    
    Args:
        provider: Provider name ('alpha_vantage', 'polygon', 'finnhub')
    
    Returns:
        API key or None
    """
    provider_map = {
        'alpha_vantage': 'ALPHA_VANTAGE_API_KEY',
        'polygon': 'POLYGON_API_KEY',
        'finnhub': 'FINNHUB_API_KEY',
        'aws': 'AWS_ACCESS_KEY_ID'
    }
    
    key_name = provider_map.get(provider.lower())
    if not key_name:
        logger.warning(f"Unknown provider: {provider}")
        return None
    
    return get_api_key(key_name, default='')

