"""
Data Infrastructure Module

Provides market calendar, TimescaleDB integration, and trading hours enforcement.
"""

from .market_calendar import MarketCalendar, get_market_calendar

__all__ = ['MarketCalendar', 'get_market_calendar']
