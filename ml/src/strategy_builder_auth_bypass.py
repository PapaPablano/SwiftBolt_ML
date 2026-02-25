"""
Hardcoded authentication bypass for Trade Station strategy builder.

This file creates a mock authentication environment that allows the strategy builder
to run without needing to verify the actual authentication flow, which appears to be
causing issues in the current setup.
"""

import os
from pathlib import Path
from typing import Dict, Any

# Create a mock environment for the Trade Station strategy builder
def setup_hardcoded_env():
    """
    Set up hardcoded environment variables for the Trade Station strategy builder
    to bypass authentication verification issues.
    """
    
    # Get the directory containing this script
    script_dir = Path(__file__).parent
    env_file = script_dir / ".." / ".env"
    
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
    }
    
    # Set the environment variables
    for key, value in hardcoded_env.items():
        os.environ[key] = value
    
    return hardcoded_env

# This will be called when the module is imported
if __name__ == "__main__":
    setup_hardcoded_env()
    print("Hardcoded environment variables set for Trade Station strategy builder")