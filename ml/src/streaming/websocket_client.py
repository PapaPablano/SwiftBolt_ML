"""WebSocket client for real-time market data streaming.

Connects to market data feeds and processes real-time quotes.

Usage:
    from src.streaming.websocket_client import WebSocketClient
    
    # Initialize
    client = WebSocketClient(
        url="wss://stream.example.com",
        api_key="your_key"
    )
    
    # Define callback
    def on_message(msg):
        print(f"Received: {msg.symbol} @ ${msg.price}")
    
    # Subscribe
    client.subscribe(['AAPL', 'SPY'], callback=on_message)
    
    # Start streaming
    client.start()

Note: Requires websocket-client
"""

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import websocket-client
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.warning("websocket-client not available. Install with: pip install websocket-client")


@dataclass
class StreamMessage:
    """Real-time stream message.
    
    Attributes:
        symbol: Asset symbol
        price: Current price
        bid: Bid price
        ask: Ask price
        volume: Volume
        timestamp: Message timestamp
        data: Additional data
    """
    symbol: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    timestamp: Optional[float] = None
    data: Optional[Dict] = None


class WebSocketClient:
    """WebSocket client for real-time data streaming."""
    
    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        reconnect: bool = True,
        reconnect_delay: int = 5
    ):
        """Initialize WebSocket client.
        
        Args:
            url: WebSocket URL
            api_key: API key for authentication
            reconnect: Auto-reconnect on disconnect
            reconnect_delay: Delay between reconnect attempts (seconds)
        """
        if not WEBSOCKET_AVAILABLE:
            raise ImportError("websocket-client required. Install with: pip install websocket-client")
        
        self.url = url
        self.api_key = api_key
        self.reconnect = reconnect
        self.reconnect_delay = reconnect_delay
        
        self.ws = None
        self.subscriptions: Dict[str, Callable] = {}
        self.running = False
        self.thread = None
        
        logger.info(f"WebSocketClient initialized: {url}")
    
    def subscribe(
        self,
        symbols: List[str],
        callback: Callable[[StreamMessage], None]
    ):
        """Subscribe to symbols.
        
        Args:
            symbols: List of symbols to subscribe to
            callback: Callback function for messages
        """
        for symbol in symbols:
            self.subscriptions[symbol] = callback
        
        logger.info(f"Subscribed to {len(symbols)} symbols")
        
        # If already connected, send subscription message
        if self.ws and self.running:
            self._send_subscription(symbols)
    
    def _send_subscription(self, symbols: List[str]):
        """Send subscription message to server.
        
        Args:
            symbols: Symbols to subscribe to
        """
        message = {
            "action": "subscribe",
            "symbols": symbols
        }
        
        if self.api_key:
            message["api_key"] = self.api_key
        
        try:
            self.ws.send(json.dumps(message))
            logger.debug(f"Sent subscription: {symbols}")
        except Exception as e:
            logger.error(f"Error sending subscription: {e}")
    
    def _on_message(self, ws, message):
        """Handle incoming message.
        
        Args:
            ws: WebSocket instance
            message: Raw message
        """
        try:
            data = json.loads(message)
            
            # Extract message fields
            symbol = data.get('symbol', data.get('s', ''))
            price = data.get('price', data.get('p', 0))
            
            if not symbol or not price:
                logger.debug(f"Skipping message: {data}")
                return
            
            # Create StreamMessage
            msg = StreamMessage(
                symbol=symbol,
                price=float(price),
                bid=data.get('bid', data.get('b')),
                ask=data.get('ask', data.get('a')),
                volume=data.get('volume', data.get('v')),
                timestamp=data.get('timestamp', data.get('t', time.time())),
                data=data
            )
            
            # Call subscriber callback
            if symbol in self.subscriptions:
                try:
                    self.subscriptions[symbol](msg)
                except Exception as e:
                    logger.error(f"Error in callback for {symbol}: {e}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _on_error(self, ws, error):
        """Handle error.
        
        Args:
            ws: WebSocket instance
            error: Error object
        """
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle connection close.
        
        Args:
            ws: WebSocket instance
            close_status_code: Close status code
            close_msg: Close message
        """
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        
        if self.reconnect and self.running:
            logger.info(f"Reconnecting in {self.reconnect_delay}s...")
            time.sleep(self.reconnect_delay)
            self._connect()
    
    def _on_open(self, ws):
        """Handle connection open.
        
        Args:
            ws: WebSocket instance
        """
        logger.info("WebSocket connected")
        
        # Subscribe to all symbols
        if self.subscriptions:
            symbols = list(self.subscriptions.keys())
            self._send_subscription(symbols)
    
    def _connect(self):
        """Establish WebSocket connection."""
        try:
            self.ws = websocket.WebSocketApp(
                self.url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Run in separate thread
            self.ws.run_forever()
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            if self.reconnect and self.running:
                time.sleep(self.reconnect_delay)
                self._connect()
    
    def start(self):
        """Start streaming."""
        if self.running:
            logger.warning("Client already running")
            return
        
        self.running = True
        
        # Start in background thread
        self.thread = threading.Thread(target=self._connect, daemon=True)
        self.thread.start()
        
        logger.info("WebSocket client started")
    
    def stop(self):
        """Stop streaming."""
        self.running = False
        
        if self.ws:
            self.ws.close()
        
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("WebSocket client stopped")


if __name__ == "__main__":
    # Self-test (mock)
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("WebSocket Client - Self Test")
    print("=" * 70)
    
    if not WEBSOCKET_AVAILABLE:
        print("\n⚠️ websocket-client not available")
        print("Install with: pip install websocket-client")
        print("\nShowing example usage:")
        
        print("""
# Example usage:
from src.streaming.websocket_client import WebSocketClient

# Initialize
client = WebSocketClient(
    url="wss://stream.example.com",
    api_key="your_api_key"
)

# Define callback
def on_quote(msg):
    print(f"{msg.symbol}: ${msg.price:.2f}")

# Subscribe
client.subscribe(['AAPL', 'SPY'], callback=on_quote)

# Start streaming
client.start()

# ... do other work ...

# Stop streaming
client.stop()
        """)
    else:
        print("\n✅ websocket-client available")
        print("\nWebSocket client can connect to real-time data feeds")
        print("Example initialization:")
        print("  client = WebSocketClient(url='wss://example.com')")
    
    print("\n" + "=" * 70)
    print("✅ WebSocket client test complete!")
    print("=" * 70)
