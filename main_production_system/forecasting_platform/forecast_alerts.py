#!/usr/bin/env python3
"""
Forecast Alerts System

Monitors forecasts and sends alerts for:
- High confidence signals
- Regime changes
- Forecast direction flips

Usage:
    python forecast_alerts.py TSM --email your@email.com
    python forecast_alerts.py SPY --check-interval 3600
"""

import argparse
import time
import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

from multi_timeframe_forecaster import Forecaster


class AlertSystem:
    """
    Alert system for forecast changes.
    """

    def __init__(self, symbol: str, email: Optional[str] = None):
        """
        Initialize alert system.

        Args:
            symbol: Stock symbol to monitor
            email: Email address for alerts (optional)
        """
        self.symbol = symbol
        self.email = email
        self.forecaster = Forecaster()
        self.last_forecast = None
        self.last_regime = None

        # Train forecaster
        print(f"Initializing alert system for {symbol}...")
        self.forecaster.train_on_recent_data(symbol)
        print("✅ Alert system ready!")

    def send_email_alert(self, subject: str, message: str):
        """Send email alert (requires SMTP setup)."""
        if not self.email:
            return

        # NOTE: Configure your SMTP settings here
        # This is a placeholder - requires actual SMTP server
        print(f"\n📧 EMAIL ALERT: {subject}")
        print(f"   To: {self.email}")
        print(f"   {message}")

    def send_terminal_alert(self, alert_type: str, message: str):
        """Display terminal alert."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        icons = {
            'high_confidence': '🚀',
            'regime_change': '⚠️ ',
            'direction_flip': '🔄',
            'info': 'ℹ️ '
        }

        icon = icons.get(alert_type, 'ℹ️ ')

        print(f"\n{icon} ALERT [{timestamp}]")
        print("="*80)
        print(message)
        print("="*80)

    def check_for_alerts(self):
        """Check for alertable conditions."""
        # Get current forecast
        forecast = self.forecaster.forecast(self.symbol)

        if 'error' in forecast:
            return

        # Check for high confidence signal
        if forecast['4hr_confidence'] > 70:
            if (self.last_forecast is None or 
                self.last_forecast['4hr_direction'] != forecast['4hr_direction']):

                message = f"""
HIGH CONFIDENCE FORECAST

Symbol: {forecast['symbol']}
Direction: {forecast['4hr_direction']}
Confidence: {forecast['4hr_confidence']:.1f}%
Regime: {forecast['regime']}

{forecast['recommendation']}

Current Price: ${forecast['current_price']:.2f}
Support: ${forecast['support']:.2f}
Resistance: ${forecast['resistance']:.2f}
"""
                self.send_terminal_alert('high_confidence', message)
                self.send_email_alert(
                    f"High Confidence {forecast['4hr_direction']} Signal - {forecast['symbol']}",
                    message
                )

        # Check for regime change
        if self.last_regime and self.last_regime != forecast['regime']:
            message = f"""
REGIME CHANGE DETECTED

Symbol: {forecast['symbol']}
Previous: {self.last_regime}
Current: {forecast['regime']}

Expected Accuracy: {forecast['expected_accuracy']*100:.0f}%
Confidence Level: {forecast['regime_confidence']}
"""
            self.send_terminal_alert('regime_change', message)
            self.send_email_alert(
                f"Regime Change - {forecast['symbol']}",
                message
            )

        # Check for direction flip
        if (self.last_forecast and 
            self.last_forecast['4hr_direction'] != forecast['4hr_direction']):

            message = f"""
FORECAST DIRECTION CHANGE

Symbol: {forecast['symbol']}
Previous: {self.last_forecast['4hr_direction']}
Current: {forecast['4hr_direction']}
Confidence: {forecast['4hr_confidence']:.1f}%
"""
            self.send_terminal_alert('direction_flip', message)

        # Update state
        self.last_forecast = forecast
        self.last_regime = forecast['regime']

    def run(self, check_interval: int = 3600):
        """
        Run alert monitoring.

        Args:
            check_interval: Check interval in seconds (default: 1 hour)
        """
        print(f"\n👀 Monitoring {self.symbol} for alerts...")
        print(f"   Check interval: {check_interval} seconds")
        print(f"   Press Ctrl+C to stop\n")

        try:
            while True:
                self.check_for_alerts()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            print("\n\n👋 Alert monitoring stopped.")


def main():
    parser = argparse.ArgumentParser(
        description='Forecast Alert System'
    )
    parser.add_argument(
        'symbol', type=str,
        help='Stock symbol to monitor'
    )
    parser.add_argument(
        '--email', type=str, default=None,
        help='Email address for alerts (requires SMTP setup)'
    )
    parser.add_argument(
        '--check-interval', type=int, default=3600,
        help='Check interval in seconds (default: 3600 = 1 hour)'
    )

    args = parser.parse_args()

    alert_system = AlertSystem(args.symbol, args.email)
    alert_system.run(args.check_interval)


if __name__ == "__main__":
    main()
