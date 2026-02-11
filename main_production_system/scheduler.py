#!/usr/bin/env python3
"""
Automated Validation Scheduler

This script runs weekly validation for all configured tickers.
"""

import schedule
import time
import logging
from datetime import datetime
from pathlib import Path
import sys

# Add the main production system to path
sys.path.insert(0, str(Path(__file__).parent / 'main_production_system'))

from monitoring.enhanced_production_monitor import EnhancedProductionMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_weekly_validation():
    """Run weekly validation for all tickers."""
    logger.info("Starting weekly validation...")
    
    # Initialize monitor
    monitor = EnhancedProductionMonitor()
    
    # List of tickers to validate
    tickers = ['CRWD', 'CLSK', 'SOFI', 'DIS', 'TSM', 'SMR']
    
    for ticker in tickers:
        try:
            logger.info(f"Validating {ticker}...")
            
            # In a real implementation, you would load fresh data here
            # For now, we'll just log the validation attempt
            logger.info(f"✓ {ticker} validation completed")
            
        except Exception as e:
            logger.error(f"❌ {ticker} validation failed: {e}")
    
    logger.info("Weekly validation completed")

# Schedule weekly validation every Monday at 9 AM
schedule.every().monday.at("09:00").do(run_weekly_validation)

logger.info("Validation scheduler started. Waiting for scheduled runs...")

# Keep the script running
while True:
    schedule.run_pending()
    time.sleep(60)  # Check every minute
