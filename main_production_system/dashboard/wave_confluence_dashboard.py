#!/usr/bin/env python3
"""
🌊 Wave Confluence Dashboard
Multi-timeframe wave pattern analysis for trading signals

Launch this dashboard from PROJECT ROOT:
    cd /Users/ericpeterson/Attention-Based\ Multi-Timeframe-Transformer
    streamlit run main_production_system/dashboard/wave_confluence_dashboard.py

Or set PYTHONPATH explicitly:
    export PYTHONPATH="/Users/ericpeterson/Attention-Based Multi-Timeframe-Transformer:$PYTHONPATH"
    streamlit run main_production_system/dashboard/wave_confluence_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from core.wave_detection.multi_timeframe_detector import MultiTimeframeDetector
from core.wave_detection.confluence_analyzer import ConfluenceAnalyzer
from src.option_analysis.data_providers import DataProviderManager
from core.wave_detection.signal_tracker import SignalTracker, TrackedSignal

# Page config
st.set_page_config(
    page_title="🌊 Wave Confluence Analysis",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize signal tracker
tracker = SignalTracker()

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .signal-card {
        border: 3px solid;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #007bff;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<h1 class="main-header">🌊 Multi-Timeframe Wave Confluence Analysis</h1>', unsafe_allow_html=True)
st.markdown("**Detect pressure building across timeframes for high-probability trading signals**")

# Sidebar - Controls
with st.sidebar:
    st.header("⚙️ Analysis Settings")
    
    # Symbol input with common symbols
    symbol = st.text_input(
        "Stock Symbol",
        value="SPY",
        help="Enter ticker symbol (e.g., SPY, AAPL, QQQ)"
    ).upper()
    
    # Quick symbol selector
    st.markdown("**Quick Select:**")
    cols = st.columns(3)
    if cols[0].button("SPY", use_container_width=True):
        symbol = "SPY"
        st.rerun()
    if cols[1].button("QQQ", use_container_width=True):
        symbol = "QQQ"
        st.rerun()
    if cols[2].button("AAPL", use_container_width=True):
        symbol = "AAPL"
        st.rerun()
    
    st.divider()
    
    # Lookback period (focus 4h)
    st.subheader("📅 Lookback Period")
    lookback_4h = st.slider("4-hour data (days)", 30, 180, 60)
    
    st.divider()
    
    # Analysis button
    # Quality filter
    quality_threshold = st.slider(
        "Minimum Wave Quality",
        min_value=30,
        max_value=90,
        value=50,
        step=10,
        help="Filter out low-quality waves"
    )

    analyze_btn = st.button("🔍 Analyze Waves", type="primary", use_container_width=True)
    
    # Auto-refresh option
    auto_refresh = st.checkbox("Auto-refresh (every 10 min)", value=False)
    if auto_refresh:
        import time
        time.sleep(600)  # 10 minutes
        st.rerun()

# Main content area
if analyze_btn or symbol:
    
    # Show loading state
    with st.spinner(f"🔄 Analyzing {symbol} across all timeframes..."):
        
        try:
            # Initialize detector
            detector = MultiTimeframeDetector()
            
            # Detect waves on all timeframes
            waves_dict = detector.detect_all_timeframes(symbol, min_quality=float(quality_threshold))
            
            # Analyze confluence
            analyzer = ConfluenceAnalyzer(symbol)
            signals = analyzer.detect_confluence_flexible(waves_dict)

            # Track newly detected confluence signals
            if signals:
                for sig in signals:
                    try:
                        dir_value = getattr(sig, 'direction', '')
                        dir_str = dir_value.value if hasattr(dir_value, 'value') else str(dir_value)
                        direction_norm = 'bullish' if dir_str.lower() in ('up', 'bullish') else 'bearish'
                        confidence_val = float(getattr(sig, 'confidence', 0.0)) / 100.0
                        signal_id = tracker.track_signal(TrackedSignal(
                            symbol=symbol,
                            direction=direction_norm,
                            confidence=confidence_val,
                            entry_price=float(getattr(sig, 'entry_price', 0.0)),
                            target_price=float(getattr(sig, 'target_price', 0.0)),
                            stop_loss=float(getattr(sig, 'stop_loss', 0.0)),
                            timeframes_aligned=list(getattr(sig, 'timeframes_aligned', [])),
                            quality_score=float(getattr(sig, 'pressure_score', 0.0)),
                        ))
                        st.session_state[f'signal_{signal_id}'] = {
                            'id': signal_id,
                            'entry': float(getattr(sig, 'entry_price', 0.0)),
                            'target': float(getattr(sig, 'target_price', 0.0)),
                            'stop': float(getattr(sig, 'stop_loss', 0.0)),
                            'timestamp': datetime.now()
                        }
                        st.success(f"✅ Signal tracked! ID: {signal_id}")
                    except Exception as _e:
                        st.warning(f"Could not track signal: {_e}")
            
            # Sidebar: Wave quality distribution (after quality slider)
            if waves_dict.get('4h'):
                st.sidebar.markdown("---")
                st.sidebar.markdown("**Wave Quality Distribution**")
                waves_4h = waves_dict.get('4h', [])
                grade_a = len([w for w in waves_4h if getattr(w, 'quality_score', 0.0) >= 80])
                grade_b = len([w for w in waves_4h if 60 <= getattr(w, 'quality_score', 0.0) < 80])
                grade_c = len([w for w in waves_4h if getattr(w, 'quality_score', 0.0) < 60])
                st.sidebar.write(f"🟢 Grade A (80+): {grade_a}")
                st.sidebar.write(f"🟡 Grade B (60-79): {grade_b}")
                st.sidebar.write(f"🔴 Grade C (<60): {grade_c}")

            # Top metrics row (4h focus)
            if waves_dict:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    total_4h = len(waves_dict.get('4h', []))
                    high_quality = len([w for w in waves_dict.get('4h', []) if getattr(w, 'quality_score', 0.0) >= 70])
                    st.metric(label="🔵 4h Waves", value=total_4h, delta=f"{high_quality} high quality")
                with col2:
                    bullish = len([w for w in waves_dict.get('4h', []) if getattr(getattr(w, 'direction', ''), 'value', str(getattr(w, 'direction', ''))) == 'up'])
                    st.metric(label="📈 Bullish", value=bullish, delta="Up waves")
                with col3:
                    bearish = len([w for w in waves_dict.get('4h', []) if getattr(getattr(w, 'direction', ''), 'value', str(getattr(w, 'direction', ''))) == 'down'])
                    st.metric(label="📉 Bearish", value=bearish, delta="Down waves")
                with col4:
                    avg_quality = float(np.mean([getattr(w, 'quality_score', 0.0) for w in waves_dict.get('4h', [])])) if waves_dict.get('4h') else 0.0
                    st.metric(label="⭐ Avg Quality", value=f"{avg_quality:.0f}", delta="Score")

            st.divider()

            # Prominent confluence alerts (before chart)
            if signals:
                st.subheader("🔥 Active Confluence Signals")
                for signal in signals:
                    if getattr(signal, 'confidence', 0) >= 80:
                        st.success(
                            f"⚡⚡⚡ **STRONG {signal.direction.upper()} SIGNAL**\n\n"
                            f"Entry: ${signal.entry_price:.2f} | "
                            f"Target: ${signal.target_price:.2f} | "
                            f"Stop: ${signal.stop_loss:.2f}\n\n"
                            f"Confidence: {signal.confidence}% | "
                            f"Timeframes: {', '.join(signal.timeframes_aligned)}"
                        )
                    elif getattr(signal, 'confidence', 0) >= 60:
                        st.warning(
                            f"⚡⚡ **MODERATE {signal.direction.upper()} SIGNAL**\n\n"
                            f"Entry: ${signal.entry_price:.2f} | "
                            f"Target: ${signal.target_price:.2f} | "
                            f"Stop: ${signal.stop_loss:.2f}\n\n"
                            f"Confidence: {signal.confidence}%"
                        )
                    else:
                        st.info(
                            f"⚡ **WATCH {signal.direction.upper()}**\n\n"
                            f"Entry: ${signal.entry_price:.2f} | Confidence: {signal.confidence}%"
                        )
                st.markdown("---")
            else:
                st.info("ℹ️ No confluence signals detected. Monitor for alignment.")

            # ========================================
            # SECTION 1: WAVE DETECTION STATUS
            # ========================================
            st.header("📊 Wave Detection Status")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    label="🔵 10-Minute Waves",
                    value=len(waves_dict.get('10min', [])),
                    delta="Micro-trends"
                )
                if waves_dict.get('10min'):
                    st.success("✓ Active")
                else:
                    st.warning("⚠ No waves detected")
            
            with col2:
                st.metric(
                    label="🟢 1-Hour Waves",
                    value=len(waves_dict.get('1h', [])),
                    delta="Hourly swings"
                )
                if waves_dict.get('1h'):
                    st.success("✓ Active")
                else:
                    st.warning("⚠ No waves detected")
            
            with col3:
                st.metric(
                    label="🔴 4-Hour Waves",
                    value=len(waves_dict.get('4h', [])),
                    delta="Major waves"
                )
                if waves_dict.get('4h'):
                    st.success("✓ Active")
                else:
                    st.warning("⚠ No waves detected")
            
            st.divider()
            
            # ========================================
            # SECTION 2: MULTI-TIMEFRAME CHART
            # ========================================
            st.header("📈 Multi-Timeframe Wave Chart")
            
            # Fetch price data for charting
            provider = DataProviderManager()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_4h)
            
            df_chart = provider.fetch(
                symbol=symbol,
                start=start_date,
                end=end_date,
                interval='4h'
            )
            
            if df_chart is None or df_chart.empty:
                st.error("❌ Unable to fetch chart data")
            else:
                # Ensure proper index
                if 'timestamp' in df_chart.columns:
                    df_chart = df_chart.set_index('timestamp')
                if not isinstance(df_chart.index, pd.DatetimeIndex):
                    df_chart.index = pd.to_datetime(df_chart.index)

                # Create figure - Candlestick for professional clarity
                fig = go.Figure()
                # Prepare nicely formatted hover text for candlesticks
                _hovertext = [dt.strftime('%b %d, %Y %H:%M') for dt in df_chart.index]
                fig.add_trace(go.Candlestick(
                    x=df_chart.index,
                    open=df_chart['open'],
                    high=df_chart['high'],
                    low=df_chart['low'],
                    close=df_chart['close'],
                    name='Price',
                    increasing_line_color='#26A69A',
                    decreasing_line_color='#EF5350',
                    hovertext=_hovertext
                ))

                # Add 4h waves ONLY - clean trend lines from start to end
                for wave in waves_dict.get('4h', []):
                    direction_up = (getattr(wave.direction, 'value', str(wave.direction)) == 'up') if hasattr(wave, 'direction') else (wave.end_price > wave.start_price)
                    wave_color = '#00E676' if direction_up else '#FF1744'
                    projected_end = wave.end_time
                    _now = pd.Timestamp.now(tz=projected_end.tz) if getattr(projected_end, 'tz', None) else datetime.now()
                    is_active = projected_end > _now
                    if is_active:
                        time_remaining = (projected_end - _now).total_seconds() / 3600.0
                        time_left_str = (f"{time_remaining/24:.1f} days left" if time_remaining > 24 else f"{time_remaining:.1f}h left")
                    else:
                        time_left_str = 'Complete'
                    projected_end_str = projected_end.strftime('%b %d, %Y %H:%M')
                    start_str = wave.start_time.strftime('%b %d, %H:%M')
                    fig.add_trace(go.Scatter(
                        x=[wave.start_time, wave.end_time],
                        y=[wave.start_price, wave.end_price],
                        mode='lines',
                        name='4h Wave',
                        line=dict(color=wave_color, width=3),
                        showlegend=False,
                        hovertemplate=(
                            f'<b>4h Wave</b><br>'
                            f'Direction: {"BULLISH" if direction_up else "BEARISH"}<br>'
                            f'Start: {start_str}<br>'
                            f'Projected End: {projected_end_str}<br>'
                            f'Status: {time_left_str}<br>'
                            f'Amplitude: ${getattr(wave, "amplitude", 0.0):.2f}<br>'
                            f'Start Price: ${getattr(wave, "start_price", 0.0):.2f}<br>'
                            f'End Price: ${getattr(wave, "end_price", 0.0):.2f}<br>'
                            '<extra></extra>'
                        )
                    ))

                # Add confluence zones (gold vrects) if signals exist
                if signals:
                    from datetime import timedelta as _td
                    for signal in signals:
                        if waves_dict.get('4h'):
                            last_wave = waves_dict['4h'][-1]
                            x1 = getattr(last_wave, 'end_time', None)
                            if x1 is not None:
                                x0 = x1 - _td(hours=4)
                                fig.add_vrect(
                                    x0=x0,
                                    x1=x1,
                                    fillcolor="gold",
                                    opacity=0.2,
                                    line_width=0,
                                    annotation_text="⚡ Confluence",
                                    annotation_position="top left"
                                )

                # Update layout
                fig.update_layout(
                    title=f"{symbol} - 4H Wave Analysis",
                    xaxis_title="Date",
                    yaxis_title="Price ($)",
                    hovermode='x unified',
                    height=700,
                    template='plotly_dark',
                    showlegend=False
                )

                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={'displayModeBar': True, 'displaylogo': False, 'modeBarButtonsToRemove': ['pan2d', 'lasso2d']}
                )
            
            st.divider()
            
            # ========================================
            # SECTION 3: CONFLUENCE SIGNALS
            # ========================================
            st.header("🔥 Confluence Signals")
            
            if signals:
                
                for i, signal in enumerate(signals):
                    
                    # Determine styling based on confidence
                    if signal.confidence >= 90:
                        color = "#28a745"  # Green
                        emoji = "⚡⚡⚡"
                        alert_text = "STRONG BUY/SELL"
                    elif signal.confidence >= 75:
                        color = "#ffc107"  # Yellow
                        emoji = "⚡⚡"
                        alert_text = "MODERATE SIGNAL"
                    else:
                        color = "#17a2b8"  # Blue
                        emoji = "⚡"
                        alert_text = "WATCH"
                    
                    # Signal card
                    st.markdown(f"""
                    <div style="border: 3px solid {color}; border-radius: 10px; padding: 20px; margin: 15px 0; background-color: rgba{tuple(int(color[i:i+2], 16) for i in (1, 3, 5)) + (0.1,)};">
                        <h2 style="color: {color}; margin: 0;">
                            {emoji} {signal.direction.upper()} SIGNAL - {alert_text}
                        </h2>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Signal metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Confidence", f"{signal.confidence}%")
                    
                    with col2:
                        st.metric("Pressure Score", f"{signal.pressure_score:.1f}/100")
                    
                    with col3:
                        risk = signal.entry_price - signal.stop_loss
                        reward = signal.target_price - signal.entry_price
                        rr_ratio = reward / risk if risk > 0 else 0
                        st.metric("Risk/Reward", f"1:{rr_ratio:.1f}")
                    
                    with col4:
                        timeframes_str = " + ".join(signal.timeframes_aligned)
                        st.metric("Timeframes", timeframes_str)
                    
                    # Trade levels
                    st.markdown("**Trade Levels:**")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.success(f"**Entry:** ${signal.entry_price:.2f}")
                    
                    with col2:
                        profit = signal.target_price - signal.entry_price
                        st.success(f"**Target:** ${signal.target_price:.2f} (+${profit:.2f})")
                    
                    with col3:
                        loss = signal.entry_price - signal.stop_loss
                        st.error(f"**Stop:** ${signal.stop_loss:.2f} (-${loss:.2f})")
                    
                    st.divider()
            
            else:
                st.info("ℹ️ **No confluence signals detected at this time.**\n\n"
                       "This is normal - confluence is rare! When all timeframes align, it indicates "
                       "a high-probability setup. Keep monitoring or try different symbols.")
            
            st.divider()
            
            # ========================================
            # SECTION 4: WAVE DETAILS (EXPANDABLE)
            # ========================================
            st.header("📋 Wave Details")
            
            with st.expander("📊 View All Detected Waves", expanded=False):
                
                tab1, tab2, tab3 = st.tabs(["10-Minute", "1-Hour", "4-Hour"])
                
                with tab1:
                    if waves_dict.get('10min'):
                        wave_data = []
                        for w in waves_dict['10min']:
                            projected_end = w.end_time
                            _now = pd.Timestamp.now(tz=projected_end.tz) if getattr(projected_end, 'tz', None) else datetime.now()
                            is_active = projected_end > _now
                            if is_active:
                                time_remaining = (projected_end - _now).total_seconds() / 3600.0
                                duration_display = f"{w.duration_hours:.1f}h ({time_remaining:.1f}h left)"
                            else:
                                duration_display = f"{w.duration_hours:.1f}h (complete)"
                            wave_data.append({
                                'Start': w.start_time.strftime('%Y-%m-%d %H:%M'),
                                'Projected End': projected_end.strftime('%Y-%m-%d %H:%M'),
                                'Status': '🟢 Active' if is_active else '⚪ Complete',
                                'Direction': w.direction.value if hasattr(w.direction, 'value') else str(w.direction),
                                'Start Price': f"${w.start_price:.2f}",
                                'End Price': f"${w.end_price:.2f}",
                                'Amplitude': f"${w.amplitude:.2f}",
                                'Duration': duration_display
                            })
                        df_waves = pd.DataFrame(wave_data)
                        df_waves = df_waves.sort_values('Start', ascending=False).reset_index(drop=True)
                        st.dataframe(df_waves, use_container_width=True)
                    else:
                        st.info("No 10-minute waves detected")
                
                with tab2:
                    if waves_dict.get('1h'):
                        wave_data = []
                        for w in waves_dict['1h']:
                            projected_end = w.end_time
                            _now = pd.Timestamp.now(tz=projected_end.tz) if getattr(projected_end, 'tz', None) else datetime.now()
                            is_active = projected_end > _now
                            if is_active:
                                time_remaining = (projected_end - _now).total_seconds() / 3600.0
                                duration_display = f"{w.duration_hours:.1f}h ({time_remaining:.1f}h left)"
                            else:
                                duration_display = f"{w.duration_hours:.1f}h (complete)"
                            wave_data.append({
                                'Start': w.start_time.strftime('%Y-%m-%d %H:%M'),
                                'Projected End': projected_end.strftime('%Y-%m-%d %H:%M'),
                                'Status': '🟢 Active' if is_active else '⚪ Complete',
                                'Direction': w.direction.value if hasattr(w.direction, 'value') else str(w.direction),
                                'Start Price': f"${w.start_price:.2f}",
                                'End Price': f"${w.end_price:.2f}",
                                'Amplitude': f"${w.amplitude:.2f}",
                                'Duration': duration_display
                            })
                        df_waves = pd.DataFrame(wave_data)
                        df_waves = df_waves.sort_values('Start', ascending=False).reset_index(drop=True)
                        st.dataframe(df_waves, use_container_width=True)
                    else:
                        st.info("No 1-hour waves detected")
                
                with tab3:
                    if waves_dict.get('4h'):
                        wave_data = []
                        for w in waves_dict['4h']:
                            projected_end = w.end_time
                            _now = pd.Timestamp.now(tz=projected_end.tz) if getattr(projected_end, 'tz', None) else datetime.now()
                            is_active = projected_end > _now
                            if is_active:
                                time_remaining = (projected_end - _now).total_seconds() / 3600.0
                                duration_display = f"{w.duration_hours:.1f}h ({time_remaining:.1f}h left)"
                            else:
                                duration_display = f"{w.duration_hours:.1f}h (complete)"
                            wave_data.append({
                                'Start': w.start_time.strftime('%Y-%m-%d %H:%M'),
                                'Projected End': projected_end.strftime('%Y-%m-%d %H:%M'),
                                'Status': '🟢 Active' if is_active else '⚪ Complete',
                                'Direction': w.direction.value if hasattr(w.direction, 'value') else str(w.direction),
                                'Start Price': f"${w.start_price:.2f}",
                                'End Price': f"${w.end_price:.2f}",
                                'Amplitude': f"${w.amplitude:.2f}",
                                'Duration': duration_display,
                                'Quality': f"{getattr(w, 'quality_score', 0.0):.0f}/100",
                                'Grade': ('A' if getattr(w, 'quality_score', 0.0) >= 80 else ('B' if getattr(w, 'quality_score', 0.0) >= 60 else 'C'))
                            })
                        df_waves = pd.DataFrame(wave_data)
                        df_waves = df_waves.sort_values('Start', ascending=False).reset_index(drop=True)
                        st.dataframe(df_waves, use_container_width=True)
                    else:
                        st.info("No 4-hour waves detected")
        
        except Exception as e:
            st.error(f"❌ Error during analysis: {str(e)}")
            with st.expander("Show error details"):
                st.exception(e)

else:
    # Welcome screen when no analysis run yet
    st.info("👆 Enter a symbol and click 'Analyze Waves' to begin")

st.markdown("---")

st.markdown("""
### 🌊 How It Works

**Multi-Timeframe Wave Detection:**
- Detects waves on 10-minute, 1-hour, and 4-hour timeframes
- Each timeframe provides different insight (micro-trends → major waves)

**Confluence Signals:**
- When waves align across all timeframes = high confidence
- System calculates pressure score (0-100)
- Provides entry, target, and stop loss levels

**Color Coding:**
- 🔵 Blue = 10-minute waves (micro-trends)
- 🟢 Green = 1-hour waves (hourly swings)
- 🔴 Red = 4-hour waves (major waves)
- ⭐ Gold Star = Confluence point

**Trade Levels:**
- Light green line = Entry point
- Dark green line = Target (profit)
- Red line = Stop loss (risk management)
""")

# Footer
st.markdown("---")
st.markdown("**Built with the Wave Analogy Multi-Timeframe Analysis System**")
