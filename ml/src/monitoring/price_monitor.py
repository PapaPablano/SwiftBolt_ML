"""Monitor prices and trigger forecast refresh on significant moves.

Implements event-driven forecast updates when:
1. Price moves > 2 ATR from last forecast
2. Price breaks key S/R level
3. Trend reversal detected (SuperTrend flip)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RefreshTrigger:
    """Trigger for forecast refresh."""

    symbol: str
    reason: str
    price_move_pct: float
    atr_move: float
    triggered_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "reason": self.reason,
            "price_move_pct": self.price_move_pct,
            "atr_move": self.atr_move,
            "triggered_at": self.triggered_at.isoformat(),
        }


class PriceMonitor:
    """
    Monitors price movements and triggers forecast refresh.

    Triggers refresh when:
    1. Price moves > 2 ATR from last forecast
    2. Price moves > 5% from last forecast
    3. Trend reversal detected
    """

    MOVE_THRESHOLD_ATR = 2.0  # Trigger on 2+ ATR move
    MOVE_THRESHOLD_PCT = 5.0  # Or 5%+ move

    def __init__(
        self,
        db_client: Any = None,
        move_threshold_atr: float | None = None,
        move_threshold_pct: float | None = None,
    ) -> None:
        """
        Initialize price monitor.

        Args:
            db_client: Database client for fetching forecasts and prices
        """
        self.db = db_client
        self.last_prices: Dict[str, float] = {}
        self.last_atrs: Dict[str, float] = {}
        self.last_check: Dict[str, datetime] = {}
        self.move_threshold_atr = (
            move_threshold_atr
            if move_threshold_atr is not None
            else self.MOVE_THRESHOLD_ATR
        )
        self.move_threshold_pct = (
            move_threshold_pct
            if move_threshold_pct is not None
            else self.MOVE_THRESHOLD_PCT
        )

    def check_for_triggers(
        self,
        symbols: List[str],
    ) -> List[RefreshTrigger]:
        """
        Check all symbols for refresh triggers.

        Args:
            symbols: List of symbols to check

        Returns:
            List of RefreshTrigger for symbols needing refresh
        """
        triggers = []

        for symbol in symbols:
            trigger = self._check_symbol(symbol)
            if trigger:
                triggers.append(trigger)
                logger.info(f"Refresh triggered for {symbol}: {trigger.reason}")

        return triggers

    def _check_symbol(self, symbol: str) -> Optional[RefreshTrigger]:
        """Check single symbol for refresh trigger."""
        if self.db is None:
            logger.warning("No database client configured")
            return None

        # Get last forecast
        forecast = self._get_latest_forecast(symbol)
        if not forecast:
            return None

        forecast_points = forecast.get("points") or []
        last_point = forecast_points[-1] if forecast_points else {}
        forecast_price = last_point.get("value", 0)
        forecast_atr = forecast.get("atr") or (forecast_price * 0.02)

        if forecast_price <= 0:
            return None

        # Get current price
        current = self._get_current_price(symbol)
        if not current:
            return None

        current_price = current.get("close", 0)
        if current_price <= 0:
            return None

        # Calculate move
        move_pct = abs(current_price - forecast_price) / forecast_price * 100
        if forecast_atr > 0:
            move_atr = abs(current_price - forecast_price) / forecast_atr
        else:
            move_atr = 0

        # Check ATR threshold
        if move_atr >= self.move_threshold_atr:
            return RefreshTrigger(
                symbol=symbol,
                reason=f"Price moved {move_atr:.1f} ATR since last forecast",
                price_move_pct=move_pct,
                atr_move=move_atr,
                triggered_at=datetime.now(),
            )

        # Check percentage threshold
        if move_pct >= self.move_threshold_pct:
            return RefreshTrigger(
                symbol=symbol,
                reason=f"Price moved {move_pct:.1f}% since last forecast",
                price_move_pct=move_pct,
                atr_move=move_atr,
                triggered_at=datetime.now(),
            )

        return None

    def _get_latest_forecast(self, symbol: str) -> Optional[Dict]:
        """Get latest forecast for symbol from database."""
        try:
            if hasattr(self.db, "get_latest_forecast"):
                return self.db.get_latest_forecast(symbol)
            elif hasattr(self.db, "client"):
                # Supabase client
                result = (
                    self.db.client.table("ml_forecasts")
                    .select("*")
                    .eq("symbol", symbol)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
        except Exception as e:
            logger.warning(f"Failed to get forecast for {symbol}: {e}")
        return None

    def _get_current_price(self, symbol: str) -> Optional[Dict]:
        """Get current price for symbol from database."""
        try:
            if hasattr(self.db, "get_current_prices"):
                prices = self.db.get_current_prices(symbol)
                return prices.get("d1") if prices else None
            if hasattr(self.db, "get_current_price"):
                return self.db.get_current_price(symbol)
            elif hasattr(self.db, "client"):
                # Supabase client - get latest OHLC bar from v2 (real data)
                symbol_id = self.db.get_symbol_id(symbol)
                result = (
                    self.db.client.table("ohlc_bars_v2")
                    .select("*")
                    .eq("symbol_id", symbol_id)
                    .eq("provider", "alpaca")
                    .eq("is_forecast", False)
                    .order("ts", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
        except Exception as e:
            logger.warning(f"Failed to get current price for {symbol}: {e}")
        return None

    def check_trend_reversal(
        self,
        symbol: str,
        current_trend: str,
        previous_trend: str,
    ) -> Optional[RefreshTrigger]:
        """
        Check for trend reversal (e.g., SuperTrend flip).

        Args:
            symbol: Symbol to check
            current_trend: Current trend direction (bullish/bearish)
            previous_trend: Previous trend direction

        Returns:
            RefreshTrigger if trend reversed, None otherwise
        """
        if current_trend != previous_trend:
            return RefreshTrigger(
                symbol=symbol,
                reason=f"Trend reversal: {previous_trend} -> {current_trend}",
                price_move_pct=0.0,
                atr_move=0.0,
                triggered_at=datetime.now(),
            )
        return None

    def get_stale_forecasts(
        self,
        symbols: List[str],
        max_age_hours: int = 24,
    ) -> List[str]:
        """
        Get list of symbols with stale forecasts.

        Args:
            symbols: List of symbols to check
            max_age_hours: Maximum forecast age in hours

        Returns:
            List of symbols with forecasts older than max_age_hours
        """
        stale = []
        now = datetime.now()

        for symbol in symbols:
            forecast = self._get_latest_forecast(symbol)
            if not forecast:
                stale.append(symbol)
                continue

            created_at = forecast.get("created_at")
            if created_at:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age_hours = (now - created_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    stale.append(symbol)

        return stale


def check_price_triggers(
    db_client: Any,
    symbols: List[str],
) -> List[RefreshTrigger]:
    """
    Convenience function to check for price-based refresh triggers.

    Args:
        db_client: Database client
        symbols: List of symbols to check

    Returns:
        List of RefreshTrigger for symbols needing refresh
    """
    monitor = PriceMonitor(db_client)
    return monitor.check_for_triggers(symbols)
