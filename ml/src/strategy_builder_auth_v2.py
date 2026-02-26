"""
Enhanced authentication bypass for Trade Station strategy builder.

This implementation provides a safe way to bypass authentication while maintaining
compatibility with the existing configuration system. It handles edge cases 
and provides appropriate logging for debugging.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Set up logging
logger = logging.getLogger(__name__)

def setup_hardcoded_env() -> Dict[str, str]:
    """
    Set up hardcoded environment variables for the Trade Station strategy builder
    to bypass authentication verification issues.
    
    Returns:
        Dict[str, str]: Dictionary of set environment variables
    """
    
    # Check if we're in simulation mode and should skip Tradestation connection
    if os.environ.get("SKIP_TRADESTATION_CONNECTION", "").lower() == "true":
        logger.info("Skipping Tradestation connection setup - simulation mode active")
        return {}
    
    # Create a mock environment dictionary with all required credentials
    hardcoded_env = {
        "TRADIER_API_KEY": "BusvWaAgCGG5cLfvpUAWvI6A8Ayv",
        "ALPACA_API_KEY": "AK7VELM3TFKFFRKLHCEUYGTDTI", 
        "ALPACA_API_SECRET": "EwkQJyu5qMMKn38WXsmJWKAF7CV6YZ7FmJ56MwUnjH96",
        "SUPABASE_URL": "https://cygflaemtmwiwaviclks.supabase.co",
        "SUPABASE_ANON_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs",
        "SUPABASE_SERVICE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTIxMTMzNiwiZXhwIjoyMDgwNzg3MzM2fQ.YajeNHOQ63uBDDZhJ2YYHK7L-BKmnZAviDqrlk2TQxU",
        "FINNHUB_API_KEY": "d3slu8hr01qpdd5k9hngd3slu8hr01qpdd5k9ho0",
        "MASSIVE_API_KEY": "yHWJ5XAQcK_ebnCCHY2xqBurHpkTEUXL",
        "DATABENTO_API_KEY": "db-UusqXRExE4ekMmyunVTenHbkPM7eN",
        # Additional configuration flags for adaptive strategy components
        "ENABLE_ADAPTIVE_SUPERTREND": "true",
        "ADAPTIVE_ST_OPTIMIZATION": "true",
        "ADAPTIVE_ST_CACHING": "true",
        "ADAPTIVE_ST_CACHE_TTL_HOURS": "24",
        "ADAPTIVE_ST_METRIC_OBJECTIVE": "sharpe",
        "ADAPTIVE_ST_MIN_BARS": "60",
    }
    
    # Set the environment variables
    set_vars = {}
    for key, value in hardcoded_env.items():
        try:
            # Set environment variable
            os.environ[key] = value
            set_vars[key] = value
            logger.debug(f"Set environment variable {key}")
        except Exception as e:
            logger.warning(f"Failed to set environment variable {key}: {e}")
    
    logger.info("Hardcoded environment variables configured successfully for Trade Station strategy builder")
    return set_vars

def is_hardcoded_env_active() -> bool:
    """
    Check if hardcoded environment is active.
    
    Returns:
        bool: True if hardcoded environment is active
    """
    # In simulation mode, we won't have the hardcoded credentials set
    if os.environ.get("SKIP_TRADESTATION_CONNECTION", "").lower() == "true":
        return False
        
    required_keys = ["TRADIER_API_KEY", "ALPACA_API_KEY"]
    return all(key in os.environ for key in required_keys)

# This will be called when the module is imported
if __name__ == "__main__":
    setup_hardcoded_env()
    print("Hardcoded environment variables set for Trade Station strategy builder")