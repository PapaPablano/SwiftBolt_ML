"""Order Management System (OMS)."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class Order:
    """Order representation."""
    order_id: str
    symbol: str
    quantity: float
    order_type: OrderType
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0
    filled_price: Optional[float] = None
    created_at: datetime = None
    filled_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class OrderManager:
    """Order Management System."""
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        logger.info("OrderManager initialized")
    
    def create_order(self, symbol: str, quantity: float, order_type: str = 'market',
                    limit_price: float = None, stop_price: float = None) -> str:
        """Create new order.
        
        Returns:
            order_id
        """
        order_id = str(uuid.uuid4())
        order = Order(
            order_id=order_id,
            symbol=symbol,
            quantity=quantity,
            order_type=OrderType(order_type),
            limit_price=limit_price,
            stop_price=stop_price
        )
        self.orders[order_id] = order
        logger.info(f"Created order: {order_id} {symbol} {quantity:+.2f}")
        return order_id
    
    def submit_order(self, order_id: str) -> bool:
        """Submit order to broker."""
        if order_id not in self.orders:
            logger.error(f"Order not found: {order_id}")
            return False
        
        order = self.orders[order_id]
        order.status = OrderStatus.SUBMITTED
        logger.info(f"Submitted order: {order_id}")
        return True
    
    def fill_order(self, order_id: str, filled_price: float, filled_quantity: float = None):
        """Mark order as filled."""
        if order_id not in self.orders:
            return
        
        order = self.orders[order_id]
        order.filled_price = filled_price
        order.filled_quantity = filled_quantity or order.quantity
        order.filled_at = datetime.now()
        
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIAL
        
        logger.info(f"Filled order: {order_id} @ ${filled_price:.2f}")
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            return False
        
        order.status = OrderStatus.CANCELLED
        self.order_history.append(order)
        del self.orders[order_id]
        logger.info(f"Cancelled order: {order_id}")
        return True
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)
    
    def get_active_orders(self) -> List[Order]:
        """Get all active orders."""
        return [o for o in self.orders.values() if o.status not in [OrderStatus.FILLED, OrderStatus.CANCELLED]]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("Order Manager - Self Test")
    print("=" * 70)
    
    om = OrderManager()
    
    # Create and submit order
    order_id = om.create_order('AAPL', 10, 'limit', limit_price=150.0)
    om.submit_order(order_id)
    
    # Fill order
    om.fill_order(order_id, 150.0)
    
    order = om.get_order(order_id)
    print(f"Order status: {order.status}")
    print(f"Filled at: ${order.filled_price:.2f}")
    
    print("\n✅ Order manager test complete!")
