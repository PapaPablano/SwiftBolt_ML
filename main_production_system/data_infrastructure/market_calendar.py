"""
Market Calendar & Trading Hours Management

Enforces market hours and trading days at the data layer
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import Tuple, List, Optional
from zoneinfo import ZoneInfo
import logging
import holidays as holiday_lib

try:
    import pandas_market_calendars as mcal
    MCAL_AVAILABLE = True
except ImportError:
    MCAL_AVAILABLE = False
    mcal = None

logger = logging.getLogger(__name__)

# US Holidays (cached, updated annually)
US_HOLIDAYS = holiday_lib.US(years=range(2020, 2030))


class MarketCalendar:
    """
    Centralized market calendar with trading hours validation.
    
    Features:
    - NYSE trading calendar (M-F, 9:30 AM - 4:00 PM ET)
    - Holiday handling (automatic)
    - Early closes (day after Thanksgiving, Christmas Eve, etc.)
    - Timezone-aware operations
    - Pre/post-market support (optional)
    """
    
    # Time Constants (US/Eastern)
    REGULAR_MARKET_OPEN = time(9, 30)      # 9:30 AM ET
    REGULAR_MARKET_CLOSE = time(16, 0)     # 4:00 PM ET
    PREMARKET_OPEN = time(4, 0)            # 4:00 AM ET
    AFTERHOURS_CLOSE = time(20, 0)         # 8:00 PM ET
    
    # Early close times (in addition to holidays)
    EARLY_CLOSE_TIME = time(13, 0)         # 1:00 PM ET
    EARLY_CLOSE_DAYS = {
        'thanksgiving_friday',  # Day after Thanksgiving
        'christmas_eve',        # December 24
        'july_3_before_4th'     # July 3 if July 4 is weekday
    }
    
    def __init__(self):
        """Initialize market calendar with NYSE data"""
        try:
            if MCAL_AVAILABLE:
                self.nyse = mcal.get_calendar('NYSE')
                logger.info("✅ NYSE market calendar initialized")
            else:
                self.nyse = None
                logger.warning("⚠️ pandas_market_calendars not available - using fallback calendar")
        except Exception as e:
            logger.warning(f"⚠️ Market calendar initialization: {e}")
            self.nyse = None
        
        self.tz = ZoneInfo('America/New_York')
    
    def is_trading_day(self, date: pd.Timestamp or datetime.date) -> bool:
        """
        Check if date is a trading day (M-F, not a holiday).
        
        Args:
            date: Date to check
        
        Returns:
            True if trading day, False otherwise
        """
        # Convert to date if needed
        if isinstance(date, pd.Timestamp):
            date = date.date()
        
        # Check weekend (Saturday=5, Sunday=6)
        if date.weekday() > 4:
            logger.debug(f"{date} is weekend")
            return False
        
        # Check US holidays
        if date in US_HOLIDAYS:
            logger.debug(f"{date} is US holiday")
            return False
        
        # Use NYSE calendar if available
        if self.nyse:
            try:
                schedule = self.nyse.schedule(
                    start_date=str(date),
                    end_date=str(date)
                )
                return len(schedule) > 0
            except Exception as e:
                logger.warning(f"NYSE calendar check failed: {e}")
        
        return True
    
    def is_market_hours(
        self,
        dt: datetime,
        session_type: str = 'regular',
        include_premarket: bool = False,
        include_afterhours: bool = False
    ) -> bool:
        """
        Check if datetime is during market hours.
        
        Args:
            dt: Datetime to check (should be timezone-aware)
            session_type: 'regular', 'extended' (pre + regular), or 'full' (pre + regular + after)
            include_premarket: Include 4:00 AM - 9:30 AM ET
            include_afterhours: Include 4:00 PM - 8:00 PM ET
        
        Returns:
            True if within market hours
        """
        
        # Convert to Eastern time if not already
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(self.tz)
        else:
            dt = dt.astimezone(self.tz)
        
        # Check if trading day
        if not self.is_trading_day(dt.date()):
            return False
        
        current_time = dt.time()
        
        # Determine hours based on session type
        if session_type == 'regular':
            return self.REGULAR_MARKET_OPEN <= current_time <= self.REGULAR_MARKET_CLOSE
        
        elif session_type == 'extended':
            return self.PREMARKET_OPEN <= current_time <= self.REGULAR_MARKET_CLOSE
        
        elif session_type == 'full':
            return self.PREMARKET_OPEN <= current_time <= self.AFTERHOURS_CLOSE
        
        else:
            raise ValueError(f"Unknown session_type: {session_type}")
    
    def get_trading_days(
        self,
        start_date: str or datetime,
        end_date: str or datetime
    ) -> List[datetime.date]:
        """
        Get all trading days in a date range.
        
        Args:
            start_date: Start of range
            end_date: End of range
        
        Returns:
            List of trading day dates
        """
        
        if self.nyse:
            try:
                schedule = self.nyse.valid_days(
                    start_date=pd.Timestamp(start_date),
                    end_date=pd.Timestamp(end_date)
                )
                return [d.date() for d in schedule]
            except Exception as e:
                logger.warning(f"NYSE calendar error: {e}")
        
        # Fallback: generate manually
        trading_days = []
        current = pd.Timestamp(start_date).date()
        end = pd.Timestamp(end_date).date()
        
        while current <= end:
            if self.is_trading_day(current):
                trading_days.append(current)
            current += timedelta(days=1)
        
        return trading_days
    
    def filter_trading_hours(
        self,
        df: pd.DataFrame,
        time_column: str = 'time',
        session_type: str = 'regular'
    ) -> pd.DataFrame:
        """
        Filter DataFrame to only include market hours data.
        
        Args:
            df: DataFrame with time column
            time_column: Name of datetime column
            session_type: 'regular', 'extended', or 'full'
        
        Returns:
            Filtered DataFrame
        """
        
        if len(df) == 0:
            return df
        
        # Ensure time column is datetime
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            df[time_column] = pd.to_datetime(df[time_column])
        
        # Convert to Eastern time
        df_copy = df.copy()
        if df_copy[time_column].dt.tz is None:
            df_copy[time_column] = df_copy[time_column].dt.tz_localize('UTC')
        
        df_copy[time_column] = df_copy[time_column].dt.tz_convert(self.tz)
        
        # Filter by trading days
        df_copy['is_trading_day'] = df_copy[time_column].apply(
            lambda x: self.is_trading_day(x.date())
        )
        
        # Filter by market hours
        df_copy['is_market_hours'] = df_copy[time_column].apply(
            lambda x: self.is_market_hours(x, session_type=session_type)
        )
        
        # Apply filters
        filtered = df_copy[df_copy['is_trading_day'] & df_copy['is_market_hours']]
        
        # Remove helper columns
        filtered = filtered.drop(['is_trading_day', 'is_market_hours'], axis=1)
        
        logger.info(
            f"Filtered {len(df)} → {len(filtered)} rows "
            f"(kept {100*len(filtered)/max(len(df),1):.1f}%)"
        )
        
        return filtered
    
    def get_next_market_open(self, dt: Optional[datetime] = None) -> datetime:
        """Get next market open time"""
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            dt = dt.astimezone(self.tz)
        
        current_date = dt.date()
        market_open = datetime.combine(current_date, self.REGULAR_MARKET_OPEN).replace(tzinfo=self.tz)
        
        if dt < market_open:
            return market_open
        
        # Find next trading day
        next_date = current_date + timedelta(days=1)
        while not self.is_trading_day(next_date):
            next_date += timedelta(days=1)
        
        return datetime.combine(next_date, self.REGULAR_MARKET_OPEN).replace(tzinfo=self.tz)
    
    def get_next_market_close(self, dt: Optional[datetime] = None) -> datetime:
        """Get next market close time"""
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            dt = dt.astimezone(self.tz)
        
        current_date = dt.date()
        market_close = datetime.combine(current_date, self.REGULAR_MARKET_CLOSE).replace(tzinfo=self.tz)
        
        if dt < market_close:
            return market_close
        
        # Find next trading day
        next_date = current_date + timedelta(days=1)
        while not self.is_trading_day(next_date):
            next_date += timedelta(days=1)
        
        return datetime.combine(next_date, self.REGULAR_MARKET_CLOSE).replace(tzinfo=self.tz)
    
    def format_trading_status(self, dt: Optional[datetime] = None) -> str:
        """Human-readable market status"""
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            dt = dt.astimezone(self.tz)
        
        if not self.is_trading_day(dt.date()):
            next_open = self.get_next_market_open(dt)
            return f"🔴 Market Closed (Weekend/Holiday). Next open: {next_open.strftime('%a %I:%M %p ET')}"
        
        if self.is_market_hours(dt, session_type='regular'):
            return f"🟢 Market Open (Regular Hours)"
        
        if self.is_market_hours(dt, session_type='extended'):
            if dt.time() < self.REGULAR_MARKET_OPEN:
                return f"🟡 Pre-Market Trading"
            else:
                return f"🟡 After-Hours Trading"
        
        next_open = self.get_next_market_open(dt)
        return f"🔴 Market Closed. Next open: {next_open.strftime('%a %I:%M %p ET')}"


# Global instance
_calendar_instance = None


def get_market_calendar() -> MarketCalendar:
    """Get or create global market calendar instance"""
    global _calendar_instance
    if _calendar_instance is None:
        _calendar_instance = MarketCalendar()
    return _calendar_instance
