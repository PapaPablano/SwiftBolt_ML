"""
Unified sidebar controls for all dashboard tabs.
Single source of truth for symbol, timeframe, days selections.
Optimized for Polygon.io integration with session state synchronization.

Author: Cursor Agent
Created: 2025-10-31
Updated: 2025-01-27 - Added Polygon.io support
Updated: 2025-11-01 - Enhanced with validation, refresh, and cache TTL display
"""

from __future__ import annotations

from typing import Tuple, Optional, List
import os
import streamlit as st
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DashboardControls:
    """Manage all sidebar controls consistently across tabs with Polygon.io support."""

    # Supported symbols (expandable list - can be updated dynamically)
    SUPPORTED_SYMBOLS = [
        "SPY", "QQQ", "AAPL", "COIN", "MSFT", "AMZN", "NVDA", "GOOGL", "TSLA", "CRWD",
        "DIS", "JPM", "V", "MA", "UNH", "HD", "META", "NFLX", "AMD", "INTC",
        "PYPL", "ADBE", "CRM", "ORCL", "WMT", "COST", "PG", "JNJ", "PFE", "ABBV"
    ]

    # Supported timeframes by data provider capability
    SUPPORTED_TIMEFRAMES = ["1h", "4h", "1d"]

    # Timeframes supported by each provider
    PROVIDER_TIMEFRAMES = {
        "polygon": ["1h", "4h", "1d"],
        "yfinance": ["1h", "4h", "1d", "1w", "1mo"],
        "alpha_vantage": ["1h", "4h", "1d"]
    }

    DEFAULT_DAYS = 30

    @staticmethod
    def _initialize_session_state() -> None:
        """Initialize session state variables if not already set."""
        defaults = {
            'current_symbol': 'SPY',
            'current_timeframe': '1h',
            'lookback_days': 30,
            'use_polygon': True,
            'last_fetch_time': None,
            'last_fetch_symbol': None,
            'last_fetch_timeframe': None,
            'cache_ttl_seconds': None,
            'force_data_refresh': False
        }

        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @staticmethod
    def _validate_symbol(symbol: str) -> Tuple[bool, Optional[str]]:
        """
        Validate symbol selection.

        Args:
            symbol: Symbol to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not symbol:
            return False, "Symbol cannot be empty"

        symbol_upper = symbol.strip().upper()

        # Check length (ticker symbols are typically 1-5 characters)
        if len(symbol_upper) > 5:
            return False, f"Symbol '{symbol_upper}' is too long (max 5 characters)"

        # Check for invalid characters (only letters and numbers allowed)
        if not symbol_upper.replace('.', '').replace('-', '').isalnum():
            return False, f"Symbol '{symbol_upper}' contains invalid characters"

        # Check if symbol is in supported list (warning only, not blocking)
        if symbol_upper not in DashboardControls.SUPPORTED_SYMBOLS:
            logger.warning(f"[VALIDATION] Symbol '{symbol_upper}' not in predefined list - may have limited data")

        return True, None

    @staticmethod
    def _validate_timeframe(timeframe: str, use_polygon: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Validate timeframe selection based on provider capabilities.

        Args:
            timeframe: Timeframe to validate
            use_polygon: Whether using Polygon.io

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not timeframe:
            return False, "Timeframe cannot be empty"

        timeframe_lower = timeframe.lower().strip()

        # Check if timeframe is in supported list
        if timeframe_lower not in DashboardControls.SUPPORTED_TIMEFRAMES:
            supported_str = ", ".join(DashboardControls.SUPPORTED_TIMEFRAMES)
            return False, f"Unsupported timeframe '{timeframe}'. Supported: {supported_str}"

        # Provider-specific validation
        if use_polygon:
            polygon_timeframes = DashboardControls.PROVIDER_TIMEFRAMES.get("polygon", [])
            if timeframe_lower not in polygon_timeframes:
                return False, f"Timeframe '{timeframe}' not supported by Polygon.io. Use: {', '.join(polygon_timeframes)}"

        return True, None

    @staticmethod
    def _get_cache_info() -> Tuple[Optional[datetime], Optional[int]]:
        """
        Get cache information from session state.

        Returns:
            Tuple of (last_fetch_time, cache_ttl_seconds)
        """
        last_fetch = st.session_state.get('last_fetch_time')
        ttl = st.session_state.get('cache_ttl_seconds')
        return last_fetch, ttl

    @staticmethod
    def _format_last_fetch_time(last_fetch: Optional[datetime]) -> str:
        """
        Format last fetch time for display.

        Args:
            last_fetch: Last fetch datetime or None

        Returns:
            Formatted string
        """
        if last_fetch is None:
            return "Never"

        if isinstance(last_fetch, str):
            try:
                last_fetch = datetime.fromisoformat(last_fetch.replace('Z', '+00:00'))
            except:
                return "Unknown"

        now = datetime.now()
        diff = now - last_fetch

        if diff.total_seconds() < 60:
            return f"{int(diff.total_seconds())}s ago"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}m ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}hr ago"
        else:
            days = int(diff.total_seconds() / 86400)
            return f"{days}d ago"

    @staticmethod
    def _format_ttl(ttl_seconds: Optional[int]) -> str:
        """
        Format TTL for display.

        Args:
            ttl_seconds: TTL in seconds or None

        Returns:
            Formatted string
        """
        if ttl_seconds is None:
            return "Unknown"

        if ttl_seconds < 60:
            return f"{ttl_seconds}s"
        elif ttl_seconds < 3600:
            minutes = ttl_seconds // 60
            return f"{minutes}min"
        elif ttl_seconds < 86400:
            hours = ttl_seconds // 3600
            return f"{hours}hr"
        else:
            days = ttl_seconds // 86400
            return f"{days}d"

    @staticmethod
    def render_sidebar() -> Tuple[str, str, int, bool, bool]:
        """
        Render unified sidebar controls with session state synchronization.

        Features:
        - Symbol and timeframe validation
        - Session state synchronization
        - Manual refresh button
        - Last fetch time display
        - Cache TTL display

        Returns:
            Tuple of (symbol, timeframe, days, use_polygon, force_refresh)
        """
        # Initialize session state
        DashboardControls._initialize_session_state()

        st.sidebar.title("📊 Dashboard Controls")
        st.sidebar.markdown("---")

        # Check Polygon availability
        # Use secure secrets loader (st.secrets or env vars)
        try:
            from main_production_system.core.secure_secrets import get_polygon_key
            polygon_key = get_polygon_key()
        except ImportError:
            polygon_key = os.getenv('POLYGON_API_KEY')
        polygon_available = bool(polygon_key and len(polygon_key) > 5)

        # Status indicator
        if polygon_available:
            st.sidebar.success("✅ Polygon.io Connected")
        else:
            st.sidebar.warning("⚠️ Polygon.io Not Configured")

        # Symbol selection with validation and custom input
        symbol_mode = st.sidebar.radio(
            "Symbol Selection",
            ["From List", "Custom"],
            horizontal=True,
            help="Choose predefined symbol or enter custom ticker"
        )

        if symbol_mode == "From List":
            # Get current symbol index or default to 0
            current_symbol = st.session_state.get('current_symbol', DashboardControls.SUPPORTED_SYMBOLS[0])
            try:
                default_index = DashboardControls.SUPPORTED_SYMBOLS.index(current_symbol)
            except ValueError:
                default_index = 0

            symbol = st.sidebar.selectbox(
                label="Select Symbol",
                options=DashboardControls.SUPPORTED_SYMBOLS,
                index=default_index,
                key="sidebar_symbol",
                help="Choose ticker from supported list",
            )
        else:
            # Custom symbol input with validation
            default_custom = st.session_state.get('current_symbol', 'SPY')
            symbol = st.sidebar.text_input(
                label="Custom Symbol",
                value=default_custom,
                key="sidebar_symbol_custom",
                help="Enter any stock ticker symbol",
                max_chars=5
            ).strip().upper()

            # Validate custom symbol
            is_valid, error_msg = DashboardControls._validate_symbol(symbol)
            if not is_valid and symbol:
                st.sidebar.error(f"❌ {error_msg}")
                symbol = st.session_state.get('current_symbol', DashboardControls.SUPPORTED_SYMBOLS[0])
            elif symbol:
                st.sidebar.success(f"✅ Valid symbol: {symbol}")

        # Update session state
        st.session_state['current_symbol'] = symbol

        # Timeframe selection with validation
        # Get current timeframe index or default
        current_timeframe = st.session_state.get('current_timeframe', DashboardControls.SUPPORTED_TIMEFRAMES[0])
        try:
            default_timeframe_index = DashboardControls.SUPPORTED_TIMEFRAMES.index(current_timeframe)
        except ValueError:
            default_timeframe_index = 0

        timeframe = st.sidebar.selectbox(
            label="Select Timeframe",
            options=DashboardControls.SUPPORTED_TIMEFRAMES,
            index=default_timeframe_index,
            key="sidebar_timeframe",
            help="1h: 2,500+ candles via Polygon | 1d: Unlimited via yfinance"
        )

        # Validate timeframe based on provider
        use_polygon_preview = st.session_state.get('use_polygon', True)
        is_valid_tf, tf_error = DashboardControls._validate_timeframe(timeframe, use_polygon_preview)
        if not is_valid_tf:
            st.sidebar.error(f"❌ {tf_error}")
            # Reset to valid timeframe
            timeframe = DashboardControls.SUPPORTED_TIMEFRAMES[0]
            st.session_state['sidebar_timeframe'] = 0

        # Update session state
        st.session_state['current_timeframe'] = timeframe

        # Days slider (dynamic based on timeframe) with session state sync
        current_days = st.session_state.get('lookback_days', DashboardControls.DEFAULT_DAYS)

        if timeframe == "1h":
            st.sidebar.info("💡 1-hour: Up to full year available via Polygon.io")
            days = st.sidebar.slider(
                label="Days of Data",
                min_value=30,
                max_value=365,
                value=current_days if 30 <= current_days <= 365 else 30,
                step=10,
                key="sidebar_days",
                help="Polygon.io supports up to 365 days of hourly data"
            )
        elif timeframe == "4h":
            st.sidebar.info("💡 4-hour: Good coverage via Polygon.io")
            days = st.sidebar.slider(
                label="Days of Data",
                min_value=30,
                max_value=365,
                value=current_days if 30 <= current_days <= 365 else 90,
                step=10,
                key="sidebar_days",
                help="Polygon.io provides 4h bars"
            )
        else:  # daily
            st.sidebar.info("💡 Daily: Unlimited history via yfinance fallback")
            days = st.sidebar.slider(
                label="Days of Data",
                min_value=100,
                max_value=1000,
                value=current_days if 100 <= current_days <= 1000 else 365,
                step=50,
                key="sidebar_days",
                help="Yahoo Finance provides unlimited daily data"
            )

        # Update session state
        st.session_state['lookback_days'] = days

        # Model settings
        st.sidebar.subheader("🤖 Model Settings")

        model_type = st.sidebar.selectbox(
            "Model Type",
            ["Kaggle-Prophet Hybrid", "Ensemble Only", "Prophet Baseline"],
            index=0,
            key="model_type",
            help="Kaggle: Full hybrid | Ensemble: XGBoost+Transformer | Prophet: Trend only"
        )

        # Polygon toggle with session state sync
        use_polygon_default = st.session_state.get('use_polygon', timeframe in ['1h', '4h'])
        use_polygon = st.sidebar.checkbox(
            "Use Polygon.io for Data",
            value=use_polygon_default,
            key="use_polygon",
            help="Enable for 1h/4h data - provides 2,500+ candles from Polygon.io"
        )

        # Update session state
        st.session_state['use_polygon'] = use_polygon

        # Cache & Refresh Section
        st.sidebar.subheader("🔄 Cache & Refresh")

        from main_production_system.dashboard.core.data_pipeline import is_market_open, get_market_aware_ttl

        # Show market status
        market_open = is_market_open()
        market_status = "🟢 OPEN" if market_open else "🔴 CLOSED"
        st.sidebar.info(f"Market: {market_status}")

        # Show current TTL
        current_ttl = get_market_aware_ttl(timeframe)
        ttl_display = DashboardControls._format_ttl(current_ttl)
        st.sidebar.metric("Cache TTL", ttl_display, help="Time-to-live for cached data based on market hours")

        # Store TTL in session state
        st.session_state['cache_ttl_seconds'] = current_ttl

        # Last Fetch Time Display
        last_fetch, _ = DashboardControls._get_cache_info()
        last_fetch_str = DashboardControls._format_last_fetch_time(last_fetch)

        # Check if fetch is for current symbol/timeframe
        last_symbol = st.session_state.get('last_fetch_symbol')
        last_tf = st.session_state.get('last_fetch_timeframe')

        if last_symbol == symbol and last_tf == timeframe and last_fetch:
            st.sidebar.metric("Last Fetch", last_fetch_str, help="Last time data was fetched for current symbol/timeframe")
        elif last_fetch:
            st.sidebar.caption(f"Last Fetch: {last_fetch_str} (different symbol/timeframe)")
        else:
            st.sidebar.caption("Last Fetch: Never")

        # Manual Refresh Button
        force_refresh_clicked = st.sidebar.button(
            "🔄 Refresh Data",
            help="Clear cache and fetch fresh data from API",
            key="force_refresh_btn",
            use_container_width=True
        )

        if force_refresh_clicked:
            # Clear cache and force refresh
            st.session_state.force_data_refresh = True

            # Clear Streamlit cache if available
            try:
                from main_production_system.dashboard.core.data_pipeline import _cached_load_market_data
                _cached_load_market_data.clear()
                logger.info("[REFRESH] Streamlit cache cleared")
            except Exception as e:
                logger.warning(f"[REFRESH] Could not clear cache: {e}")

            # Reset last fetch time (will be updated when data is actually fetched)
            st.session_state.last_fetch_time = None
            st.session_state.last_fetch_symbol = None
            st.session_state.last_fetch_timeframe = None

            logger.info(f"[REFRESH] Cache cleared for {symbol} {timeframe} - will fetch fresh data on next load")
            st.sidebar.success("✅ Cache cleared - data will refresh on next load")

        st.sidebar.markdown("---")
        st.sidebar.info(
            f"**Current Selection:**\n"
            f"• Symbol: `{symbol}`\n"
            f"• Timeframe: `{timeframe}`\n"
            f"• Data: `{days} days`\n"
            f"• Model: `{model_type}`\n"
            f"• Polygon: `{'ON' if use_polygon else 'OFF'}`"
        )

        # Data stats
        if timeframe == "1h" and use_polygon:
            expected_candles = int(days * 6.5)
            st.sidebar.metric("Expected Candles", f"~{expected_candles}")

        # Get force refresh flag
        force_refresh = st.session_state.get("force_data_refresh", False)
        if force_refresh:
            st.session_state.force_data_refresh = False  # Clear after reading

        return symbol, timeframe, days, use_polygon, force_refresh

    @staticmethod
    def get_controls() -> Tuple[str, str, int]:
        """
        Backwards-compatible accessor used by tests: (symbol, timeframe, days).
        Returns 3-tuple for legacy compatibility.
        """
        DashboardControls._initialize_session_state()
        symbol = st.session_state.get('current_symbol', 'SPY')
        timeframe = st.session_state.get('current_timeframe', '1h')
        days = int(st.session_state.get('lookback_days', DashboardControls.DEFAULT_DAYS))
        return symbol, timeframe, days

    @staticmethod
    def get_controls_full() -> Tuple[str, str, int, bool, bool]:
        """
        Full accessor used by UI rendering path.
        Returns 5-tuple: (symbol, timeframe, days, use_polygon, force_refresh).
        """
        DashboardControls._initialize_session_state()
        symbol = st.session_state.get('current_symbol', 'SPY')
        timeframe = st.session_state.get('current_timeframe', '1h')
        days = int(st.session_state.get('lookback_days', DashboardControls.DEFAULT_DAYS))
        use_polygon = bool(st.session_state.get('use_polygon', True))
        force_refresh = bool(st.session_state.get('force_data_refresh', False))

        # Clear the force refresh flag after reading
        if force_refresh:
            st.session_state.force_data_refresh = False

        return symbol, timeframe, days, use_polygon, force_refresh


