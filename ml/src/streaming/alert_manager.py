"""Alert manager for real-time trading alerts.

Monitor prices, Greeks, and other metrics and trigger alerts
when conditions are met.

Usage:
    from src.streaming.alert_manager import AlertManager, Alert
    
    # Initialize
    manager = AlertManager()
    
    # Add price alert
    alert = Alert(
        name="AAPL Above 150",
        condition=lambda data: data['price'] > 150,
        message="AAPL crossed $150"
    )
    manager.add_alert('AAPL', alert)
    
    # Check conditions
    manager.check_alerts('AAPL', {'price': 151})
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Trading alert definition.
    
    Attributes:
        name: Alert name
        condition: Condition function that takes data dict and returns bool
        message: Alert message
        priority: Priority level (1-5, 5 is highest)
        enabled: Whether alert is active
        triggered_at: When alert was last triggered
        cooldown_seconds: Minimum seconds between triggers
    """
    name: str
    condition: Callable[[Dict], bool]
    message: str
    priority: int = 3
    enabled: bool = True
    triggered_at: Optional[datetime] = None
    cooldown_seconds: int = 60
    
    def can_trigger(self) -> bool:
        """Check if alert can trigger (respects cooldown).
        
        Returns:
            True if alert can trigger
        """
        if not self.enabled:
            return False
        
        if self.triggered_at is None:
            return True
        
        elapsed = (datetime.now() - self.triggered_at).total_seconds()
        return elapsed >= self.cooldown_seconds


class AlertManager:
    """Manage and monitor trading alerts."""
    
    def __init__(self):
        """Initialize alert manager."""
        self.alerts: Dict[str, List[Alert]] = {}  # {symbol: [alerts]}
        self.alert_history: List[Dict] = []
        self.callbacks: List[Callable] = []
        
        logger.info("AlertManager initialized")
    
    def add_alert(
        self,
        symbol: str,
        alert: Alert
    ):
        """Add alert for a symbol.
        
        Args:
            symbol: Asset symbol
            alert: Alert object
        """
        if symbol not in self.alerts:
            self.alerts[symbol] = []
        
        self.alerts[symbol].append(alert)
        logger.info(f"Added alert for {symbol}: {alert.name}")
    
    def remove_alert(
        self,
        symbol: str,
        alert_name: str
    ):
        """Remove alert by name.
        
        Args:
            symbol: Asset symbol
            alert_name: Alert name
        """
        if symbol not in self.alerts:
            return
        
        self.alerts[symbol] = [
            a for a in self.alerts[symbol]
            if a.name != alert_name
        ]
        
        logger.info(f"Removed alert: {alert_name}")
    
    def add_callback(self, callback: Callable[[str, Alert], None]):
        """Add callback for alert triggers.
        
        Args:
            callback: Function(symbol, alert)
        """
        self.callbacks.append(callback)
    
    def check_alerts(
        self,
        symbol: str,
        data: Dict
    ):
        """Check alerts for a symbol.
        
        Args:
            symbol: Asset symbol
            data: Current market data dict
        """
        if symbol not in self.alerts:
            return
        
        for alert in self.alerts[symbol]:
            if not alert.can_trigger():
                continue
            
            try:
                # Evaluate condition
                if alert.condition(data):
                    self._trigger_alert(symbol, alert, data)
                    
            except Exception as e:
                logger.error(f"Error checking alert {alert.name}: {e}")
    
    def _trigger_alert(
        self,
        symbol: str,
        alert: Alert,
        data: Dict
    ):
        """Trigger an alert.
        
        Args:
            symbol: Asset symbol
            alert: Alert object
            data: Current data
        """
        # Update trigger time
        alert.triggered_at = datetime.now()
        
        # Log alert
        alert_record = {
            'timestamp': alert.triggered_at,
            'symbol': symbol,
            'alert_name': alert.name,
            'message': alert.message,
            'priority': alert.priority,
            'data': data
        }
        
        self.alert_history.append(alert_record)
        
        # Log
        logger.warning(f"🚨 ALERT [{alert.priority}]: {symbol} - {alert.message}")
        
        # Call callbacks
        for callback in self.callbacks:
            try:
                callback(symbol, alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def get_alert_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get alert history.
        
        Args:
            symbol: Filter by symbol (optional)
            limit: Maximum number of alerts
        
        Returns:
            List of alert records
        """
        history = self.alert_history
        
        if symbol:
            history = [a for a in history if a['symbol'] == symbol]
        
        # Most recent first
        return list(reversed(history[-limit:]))
    
    def clear_alert_history(self):
        """Clear alert history."""
        self.alert_history = []
        logger.info("Alert history cleared")
    
    @staticmethod
    def create_price_alert(
        name: str,
        target_price: float,
        above: bool = True
    ) -> Alert:
        """Create price alert.
        
        Args:
            name: Alert name
            target_price: Target price
            above: True for above, False for below
        
        Returns:
            Alert object
        """
        if above:
            condition = lambda data: data.get('price', 0) > target_price
            message = f"Price crossed above ${target_price:.2f}"
        else:
            condition = lambda data: data.get('price', float('inf')) < target_price
            message = f"Price crossed below ${target_price:.2f}"
        
        return Alert(
            name=name,
            condition=condition,
            message=message,
            priority=4
        )
    
    @staticmethod
    def create_greek_alert(
        name: str,
        greek: str,
        threshold: float,
        above: bool = True
    ) -> Alert:
        """Create Greek alert.
        
        Args:
            name: Alert name
            greek: Greek name ('delta', 'gamma', etc.)
            threshold: Threshold value
            above: True for above, False for below
        
        Returns:
            Alert object
        """
        if above:
            condition = lambda data: data.get(greek, 0) > threshold
            message = f"{greek.capitalize()} exceeded {threshold:.4f}"
        else:
            condition = lambda data: data.get(greek, float('inf')) < threshold
            message = f"{greek.capitalize()} fell below {threshold:.4f}"
        
        return Alert(
            name=name,
            condition=condition,
            message=message,
            priority=3
        )


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Alert Manager - Self Test")
    print("=" * 70)
    
    # Initialize
    manager = AlertManager()
    
    # Test 1: Price alerts
    print("\n📊 Test 1: Price Alerts")
    
    alert1 = AlertManager.create_price_alert(
        "AAPL Above 150",
        target_price=150,
        above=True
    )
    
    manager.add_alert('AAPL', alert1)
    
    # Test with price below threshold
    manager.check_alerts('AAPL', {'price': 148})
    print("Price $148: No alert triggered (correct)")
    
    # Test with price above threshold
    manager.check_alerts('AAPL', {'price': 152})
    print("Price $152: Alert should be triggered")
    
    # Test 2: Greek alerts
    print("\n📊 Test 2: Greek Alerts")
    
    alert2 = AlertManager.create_greek_alert(
        "High Delta",
        greek='delta',
        threshold=0.70,
        above=True
    )
    
    manager.add_alert('SPY', alert2)
    
    # Test with low delta
    manager.check_alerts('SPY', {'delta': 0.55})
    print("Delta 0.55: No alert (correct)")
    
    # Test with high delta
    manager.check_alerts('SPY', {'delta': 0.75})
    print("Delta 0.75: Alert should be triggered")
    
    # Test 3: Custom alert
    print("\n📊 Test 3: Custom Alert")
    
    alert3 = Alert(
        name="VIX Spike",
        condition=lambda data: data.get('vix', 0) > 30,
        message="VIX above 30 - High volatility!",
        priority=5
    )
    
    manager.add_alert('VIX', alert3)
    manager.check_alerts('VIX', {'vix': 35})
    print("VIX 35: Alert triggered")
    
    # Test 4: Alert history
    print("\n📊 Test 4: Alert History")
    
    history = manager.get_alert_history()
    print(f"Total alerts triggered: {len(history)}")
    
    for record in history:
        print(f"  [{record['priority']}] {record['symbol']}: {record['alert_name']}")
    
    # Test 5: Cooldown
    print("\n📊 Test 5: Cooldown Test")
    
    # Try to trigger same alert again immediately
    manager.check_alerts('AAPL', {'price': 153})
    print("Immediate re-trigger: Should be blocked by cooldown")
    
    # Check history
    recent = manager.get_alert_history(symbol='AAPL')
    print(f"AAPL alerts: {len(recent)} (should still be 1 due to cooldown)")
    
    print("\n" + "=" * 70)
    print("✅ Alert manager test complete!")
    print("=" * 70)
