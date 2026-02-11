"""
Technical Indicator Panel Display

Custom panel for displaying technical indicator values, trade signals, and flags.
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


def render_technical_indicator_panel(
    df: pd.DataFrame,
    symbol: str,
    current_index: Optional[int] = None
) -> None:
    """
    Render a custom panel displaying technical indicator values.
    
    Shows:
    - Current price and basic metrics
    - Moving averages (MA20, MA50)
    - Bollinger Bands position
    - RSI (if available)
    - MACD (if available)
    - Trade signals/flags
    
    Args:
        df: DataFrame with OHLCV and technical indicator data
        symbol: Stock symbol
        current_index: Index of current/latest candle (default: last)
    """
    try:
        if df is None or df.empty:
            st.warning("⚠️ No data available for indicator panel")
            return
        
        if current_index is None:
            current_index = len(df) - 1
        
        if current_index >= len(df):
            current_index = len(df) - 1
        
        current_row = df.iloc[current_index]
        
        st.subheader(f"📊 Technical Indicators - {symbol}")
        
        # Create columns for organized display
        col1, col2, col3, col4 = st.columns(4)
        
        # Column 1: Price Metrics
        with col1:
            st.markdown("**Price Metrics**")
            
            if 'close' in df.columns:
                current_price = float(current_row['close'])
                st.metric("Current Price", f"${current_price:.2f}")
            
            if 'open' in df.columns and 'close' in df.columns:
                price_change = float(current_row['close'] - current_row['open'])
                price_change_pct = (price_change / current_row['open']) * 100 if current_row['open'] != 0 else 0
                st.metric(
                    "Change",
                    f"${price_change:.2f}",
                    delta=f"{price_change_pct:.2f}%"
                )
            
            if 'high' in df.columns and 'low' in df.columns:
                day_range = float(current_row['high'] - current_row['low'])
                st.metric("Range", f"${day_range:.2f}")
        
        # Column 2: Moving Averages
        with col2:
            st.markdown("**Moving Averages**")
            
            if 'ma20' in df.columns:
                ma20_val = float(current_row['ma20']) if not pd.isna(current_row['ma20']) else None
                if ma20_val is not None:
                    ma20_status = "✅ Above" if current_price > ma20_val else "❌ Below"
                    st.metric("MA20", f"${ma20_val:.2f}", ma20_status)
            
            if 'ma50' in df.columns:
                ma50_val = float(current_row['ma50']) if not pd.isna(current_row['ma50']) else None
                if ma50_val is not None:
                    ma50_status = "✅ Above" if current_price > ma50_val else "❌ Below"
                    st.metric("MA50", f"${ma50_val:.2f}", ma50_status)
            
            # MA Cross signal
            if 'ma20' in df.columns and 'ma50' in df.columns:
                if not pd.isna(current_row['ma20']) and not pd.isna(current_row['ma50']):
                    if current_row['ma20'] > current_row['ma50']:
                        st.success("🟢 Bullish Cross (MA20 > MA50)")
                    elif current_row['ma20'] < current_row['ma50']:
                        st.error("🔴 Bearish Cross (MA20 < MA50)")
        
        # Column 3: Bollinger Bands
        with col3:
            st.markdown("**Bollinger Bands**")
            
            if all(col in df.columns for col in ['bb_upper', 'bb_lower', 'bb_middle']):
                bb_upper = float(current_row['bb_upper']) if not pd.isna(current_row['bb_upper']) else None
                bb_lower = float(current_row['bb_lower']) if not pd.isna(current_row['bb_lower']) else None
                bb_middle = float(current_row['bb_middle']) if not pd.isna(current_row['bb_middle']) else None
                
                if all(v is not None for v in [bb_upper, bb_lower, bb_middle]):
                    st.metric("BB Upper", f"${bb_upper:.2f}")
                    st.metric("BB Middle", f"${bb_middle:.2f}")
                    st.metric("BB Lower", f"${bb_lower:.2f}")
                    
                    # BB Position indicator
                    if current_price >= bb_upper:
                        st.warning("⚠️ Above Upper Band (Overbought)")
                    elif current_price <= bb_lower:
                        st.info("ℹ️ Below Lower Band (Oversold)")
                    else:
                        band_width_pct = ((bb_upper - bb_lower) / bb_middle) * 100
                        st.success(f"✅ In Bands (Width: {band_width_pct:.1f}%)")
        
        # Column 4: Additional Indicators
        with col4:
            st.markdown("**Other Indicators**")
            
            # RSI (if available)
            if 'rsi' in df.columns:
                rsi_val = float(current_row['rsi']) if not pd.isna(current_row['rsi']) else None
                if rsi_val is not None:
                    rsi_status = ""
                    if rsi_val > 70:
                        rsi_status = "🔴 Overbought"
                    elif rsi_val < 30:
                        rsi_status = "🟢 Oversold"
                    else:
                        rsi_status = "✅ Neutral"
                    st.metric("RSI", f"{rsi_val:.1f}", rsi_status)
            
            # MACD (if available)
            if 'macd' in df.columns and 'macd_signal' in df.columns:
                macd_val = float(current_row['macd']) if not pd.isna(current_row['macd']) else None
                macd_signal = float(current_row['macd_signal']) if not pd.isna(current_row['macd_signal']) else None
                
                if macd_val is not None and macd_signal is not None:
                    macd_diff = macd_val - macd_signal
                    macd_status = "🟢 Bullish" if macd_diff > 0 else "🔴 Bearish"
                    st.metric("MACD", f"{macd_val:.3f}", macd_status)
            
            # Volume
            if 'volume' in df.columns:
                volume = float(current_row['volume']) if not pd.isna(current_row['volume']) else None
                if volume is not None:
                    # Compare to recent average
                    if len(df) > 20:
                        avg_volume = df['volume'].tail(20).mean()
                        vol_ratio = volume / avg_volume if avg_volume > 0 else 0
                        vol_status = "📈 High" if vol_ratio > 1.5 else "📉 Low" if vol_ratio < 0.5 else "✅ Normal"
                        st.metric("Volume", f"{volume:,.0f}", vol_status)
        
        # Trade Signals Summary
        st.markdown("---")
        st.subheader("🎯 Trade Signals Summary")
        
        signals = []
        
        # MA Cross Signal
        if 'ma20' in df.columns and 'ma50' in df.columns:
            if not pd.isna(current_row['ma20']) and not pd.isna(current_row['ma50']):
                if current_row['ma20'] > current_row['ma50']:
                    signals.append("🟢 Bullish MA Cross")
                else:
                    signals.append("🔴 Bearish MA Cross")
        
        # Bollinger Band Signal
        if all(col in df.columns for col in ['bb_upper', 'bb_lower']):
            bb_upper = current_row['bb_upper']
            bb_lower = current_row['bb_lower']
            if not pd.isna(bb_upper) and not pd.isna(bb_lower):
                if current_price <= bb_lower:
                    signals.append("🟢 Oversold (BB Lower)")
                elif current_price >= bb_upper:
                    signals.append("🔴 Overbought (BB Upper)")
        
        # RSI Signal
        if 'rsi' in df.columns:
            rsi_val = current_row['rsi']
            if not pd.isna(rsi_val):
                if rsi_val < 30:
                    signals.append("🟢 RSI Oversold")
                elif rsi_val > 70:
                    signals.append("🔴 RSI Overbought")
        
        # MACD Signal
        if 'macd' in df.columns and 'macd_signal' in df.columns:
            macd_val = current_row['macd']
            macd_signal = current_row['macd_signal']
            if not pd.isna(macd_val) and not pd.isna(macd_signal):
                if macd_val > macd_signal:
                    signals.append("🟢 MACD Bullish")
                else:
                    signals.append("🔴 MACD Bearish")
        
        # Display signals
        if signals:
            for signal in signals:
                st.write(signal)
        else:
            st.info("ℹ️ No active signals detected")
        
    except Exception as e:
        logger.error(f"[INDICATOR_PANEL] Error rendering panel: {e}")
        st.error(f"❌ Error displaying indicator panel: {str(e)}")


def render_trade_flags(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Generate trade flags/signals for each candle.
    
    Args:
        df: DataFrame with OHLCV and technical indicators
        symbol: Stock symbol
    
    Returns:
        DataFrame with additional 'signal' and 'signal_strength' columns
    """
    try:
        df_flags = df.copy()
        
        # Initialize signal columns
        df_flags['signal'] = 'HOLD'
        df_flags['signal_strength'] = 0.0
        
        # Generate signals based on indicators
        for idx in range(len(df_flags)):
            row = df_flags.iloc[idx]
            signals = []
            
            # MA Cross Signal
            if 'ma20' in df_flags.columns and 'ma50' in df_flags.columns:
                if idx > 0:
                    prev_row = df_flags.iloc[idx - 1]
                    if not pd.isna(row['ma20']) and not pd.isna(row['ma50']):
                        # Golden Cross (MA20 crosses above MA50)
                        if row['ma20'] > row['ma50'] and prev_row['ma20'] <= prev_row['ma50']:
                            signals.append(('BUY', 0.3))
                        # Death Cross (MA20 crosses below MA50)
                        elif row['ma20'] < row['ma50'] and prev_row['ma20'] >= prev_row['ma50']:
                            signals.append(('SELL', 0.3))
            
            # Bollinger Band Signal
            if all(col in df_flags.columns for col in ['bb_upper', 'bb_lower', 'close']):
                if not pd.isna(row['bb_upper']) and not pd.isna(row['bb_lower']):
                    if row['close'] <= row['bb_lower']:
                        signals.append(('BUY', 0.2))  # Oversold
                    elif row['close'] >= row['bb_upper']:
                        signals.append(('SELL', 0.2))  # Overbought
            
            # RSI Signal
            if 'rsi' in df_flags.columns:
                rsi_val = row['rsi']
                if not pd.isna(rsi_val):
                    if rsi_val < 30:
                        signals.append(('BUY', 0.2))
                    elif rsi_val > 70:
                        signals.append(('SELL', 0.2))
            
            # MACD Signal
            if 'macd' in df_flags.columns and 'macd_signal' in df_flags.columns:
                if idx > 0:
                    prev_row = df_flags.iloc[idx - 1]
                    macd_val = row['macd']
                    macd_signal = row['macd_signal']
                    prev_macd = prev_row['macd']
                    prev_signal = prev_row['macd_signal']
                    
                    if not pd.isna(macd_val) and not pd.isna(macd_signal):
                        # MACD Cross above signal
                        if macd_val > macd_signal and prev_macd <= prev_signal:
                            signals.append(('BUY', 0.3))
                        # MACD Cross below signal
                        elif macd_val < macd_signal and prev_macd >= prev_signal:
                            signals.append(('SELL', 0.3))
            
            # Aggregate signals
            if signals:
                buy_strength = sum(strength for sig, strength in signals if sig == 'BUY')
                sell_strength = sum(strength for sig, strength in signals if sig == 'SELL')
                
                if buy_strength > sell_strength:
                    df_flags.at[idx, 'signal'] = 'BUY'
                    df_flags.at[idx, 'signal_strength'] = min(buy_strength, 1.0)
                elif sell_strength > buy_strength:
                    df_flags.at[idx, 'signal'] = 'SELL'
                    df_flags.at[idx, 'signal_strength'] = min(sell_strength, 1.0)
        
        logger.info(f"[TRADE_FLAGS] Generated signals for {len(df_flags)} candles")
        return df_flags
        
    except Exception as e:
        logger.error(f"[TRADE_FLAGS] Error generating flags: {e}")
        return df

