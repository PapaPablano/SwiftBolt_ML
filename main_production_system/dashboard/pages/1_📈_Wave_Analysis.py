#!/usr/bin/env python3
from __future__ import annotations

import sys
import os
from pathlib import Path

import streamlit as st

# Ensure project root is on sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Page config for this page
st.set_page_config(page_title="Wave Analysis", page_icon="📈", layout="wide")
st.sidebar.info("💡 View results in Performance page")

# Import original module contents
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

from core.wave_detection.multi_timeframe_detector import MultiTimeframeDetector
from core.wave_detection.confluence_analyzer import ConfluenceAnalyzer
from src.option_analysis.data_providers import DataProviderManager
from core.wave_detection.signal_tracker import SignalTracker, TrackedSignal

# Initialize signal tracker
tracker = SignalTracker()

# Custom CSS
st.markdown(
    """
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 1rem; }
    .signal-card { border: 3px solid; border-radius: 10px; padding: 20px; margin: 15px 0; }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #007bff; }
</style>
""",
    unsafe_allow_html=True,
)

# Title
st.markdown('<h1 class="main-header">🌊 Multi-Timeframe Wave Confluence Analysis</h1>', unsafe_allow_html=True)
st.markdown("**Detect pressure building across timeframes for high-probability trading signals**")

# Sidebar - Controls
with st.sidebar:
    st.header("⚙️ Analysis Settings")
    symbol = st.text_input("Stock Symbol", value="SPY", help="Enter ticker (e.g., SPY, AAPL, QQQ)").upper()
    st.markdown("**Quick Select:**")
    cols = st.columns(3)
    if cols[0].button("SPY", use_container_width=True):
        symbol = "SPY"; st.rerun()
    if cols[1].button("QQQ", use_container_width=True):
        symbol = "QQQ"; st.rerun()
    if cols[2].button("AAPL", use_container_width=True):
        symbol = "AAPL"; st.rerun()
    st.divider()
    st.subheader("📅 Lookback Period")
    lookback_4h = st.slider("4-hour data (days)", 30, 180, 60)
    st.divider()
    quality_threshold = st.slider("Minimum Wave Quality", min_value=30, max_value=90, value=50, step=10)
    analyze_btn = st.button("🔍 Analyze Waves", type="primary", use_container_width=True)

if analyze_btn or symbol:
    with st.spinner(f"🔄 Analyzing {symbol} across all timeframes..."):
        try:
            detector = MultiTimeframeDetector()
            waves_dict = detector.detect_all_timeframes(symbol, min_quality=float(quality_threshold))

            # DEBUG: counts per timeframe
            st.write(
                f"DEBUG: Detected waves - 4h: {len(waves_dict.get('4h', []))}, "
                f"1h: {len(waves_dict.get('1h', []))}, "
                f"10min: {len(waves_dict.get('10min', []))}"
            )
            analyzer = ConfluenceAnalyzer(symbol)
            signals = analyzer.detect_confluence_flexible(waves_dict)

            # Track signals
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
                            'timestamp': datetime.now(),
                        }
                        st.success(f"✅ Signal tracked! ID: {signal_id}")
                    except Exception as _e:
                        st.warning(f"Could not track signal: {_e}")

            # Quality distribution
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

            # Metrics
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

            # Prominent confluence alerts
            if signals:
                st.subheader("🔥 Active Confluence Signals")
                for signal in signals:
                    if getattr(signal, 'confidence', 0) >= 80:
                        st.success(
                            f"⚡⚡⚡ **STRONG {signal.direction.upper()} SIGNAL**\n\n"
                            f"Entry: ${signal.entry_price:.2f} | Target: ${signal.target_price:.2f} | Stop: ${signal.stop_loss:.2f}\n\n"
                            f"Confidence: {signal.confidence}% | Timeframes: {', '.join(signal.timeframes_aligned)}"
                        )
                    elif getattr(signal, 'confidence', 0) >= 60:
                        st.warning(
                            f"⚡⚡ **MODERATE {signal.direction.upper()} SIGNAL**\n\n"
                            f"Entry: ${signal.entry_price:.2f} | Target: ${signal.target_price:.2f} | Stop: ${signal.stop_loss:.2f}\n\n"
                            f"Confidence: {signal.confidence}%"
                        )
                    else:
                        st.info(
                            f"⚡ **WATCH {signal.direction.upper()}**\n\n"
                            f"Entry: ${signal.entry_price:.2f} | Confidence: {signal.confidence}%"
                        )
                st.markdown("---")
                # Cross-link to performance page
                if st.button("📊 View in Performance Dashboard"):
                    st.switch_page("pages/2_📊_Performance.py")
            else:
                st.info("ℹ️ No confluence signals detected. Monitor for alignment.")

            st.divider()
            st.header("📈 Multi-Timeframe Wave Chart")

            provider = DataProviderManager()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_4h)
            df_chart = provider.fetch(symbol=symbol, start=start_date, end=end_date, interval='4h')
            if df_chart is None or df_chart.empty:
                st.error("❌ Unable to fetch chart data")
            else:
                if 'timestamp' in df_chart.columns:
                    df_chart = df_chart.set_index('timestamp')
                if not isinstance(df_chart.index, pd.DatetimeIndex):
                    df_chart.index = pd.to_datetime(df_chart.index)
                fig = go.Figure()
                _hover = [dt.strftime('%b %d, %Y %H:%M') for dt in df_chart.index]
                fig.add_trace(go.Candlestick(
                    x=df_chart.index,
                    open=df_chart['open'],
                    high=df_chart['high'],
                    low=df_chart['low'],
                    close=df_chart['close'],
                    name='Price',
                    increasing_line_color='#26A69A',
                    decreasing_line_color='#EF5350',
                    hovertext=_hover
                ))

                # Add 4h waves as colored lines with rich hover
                from datetime import datetime as _dt
                for wave in waves_dict.get('4h', []):
                    dir_value = getattr(wave, 'direction', '')
                    dir_str = dir_value.value if hasattr(dir_value, 'value') else str(dir_value)
                    color = '#00E676' if dir_str.lower() in ('up', 'bullish') else '#FF1744'
                    projected_end = getattr(wave, 'end_time', None)
                    if projected_end is None:
                        continue
                    now = _dt.now(projected_end.tz) if getattr(projected_end, 'tz', None) else _dt.now()
                    is_active = projected_end > now
                    if is_active:
                        time_remaining = (projected_end - now).total_seconds() / 3600.0
                        time_left_str = f"{time_remaining/24:.1f} days left" if time_remaining > 24 else f"{time_remaining:.1f}h left"
                    else:
                        time_left_str = "Complete"
                    fig.add_trace(go.Scatter(
                        x=[getattr(wave, 'start_time', projected_end), projected_end],
                        y=[float(getattr(wave, 'start_price', df_chart['close'].iloc[0])), float(getattr(wave, 'end_price', df_chart['close'].iloc[-1]))],
                        mode='lines',
                        name='4h Wave',
                        line=dict(color=color, width=3),
                        showlegend=False,
                        hovertemplate=(
                            '<b>4h Wave</b><br>'
                            f'Direction: {dir_str.upper()}<br>'
                            f'Start: {getattr(wave, "start_time").strftime("%b %d, %H:%M") if getattr(wave, "start_time", None) else "?"}<br>'
                            f'Projected End: {projected_end.strftime("%b %d, %Y %H:%M")}<br>'
                            f'Status: {time_left_str}<br>'
                            f'Amplitude: ${float(getattr(wave, "amplitude", 0.0)):.2f}<br>'
                            f'Quality: {float(getattr(wave, "quality_score", 0.0)):.0f}/100<br>'
                            '<extra></extra>'
                        )
                    ))
                st.plotly_chart(fig, use_container_width=True)

            st.divider()
            st.header("📋 Wave Details")
            tab4h, tab1h, tab10m = st.tabs(["4-Hour Waves", "1-Hour Waves", "10-Minute Waves"])

            with tab4h:
                waves_4h = waves_dict.get('4h', [])
                if waves_4h:
                    from datetime import datetime as _dt2
                    wave_data = []
                    for w in waves_4h:
                        projected_end = w.end_time
                        now = _dt2.now(projected_end.tz) if getattr(projected_end, 'tz', None) else _dt2.now()
                        is_active = projected_end > now
                        wave_data.append({
                            'Start': w.start_time.strftime('%Y-%m-%d %H:%M'),
                            'Projected End': projected_end.strftime('%Y-%m-%d %H:%M'),
                            'Status': '🟢 Active' if is_active else '⚪ Complete',
                            'Direction': (w.direction.value if hasattr(w.direction, 'value') else str(w.direction)).upper(),
                            'Start Price': f"${w.start_price:.2f}",
                            'End Price': f"${w.end_price:.2f}",
                            'Amplitude': f"${w.amplitude:.2f}",
                            'Quality': f"{getattr(w, 'quality_score', 0.0):.0f}",
                            'Grade': ('A' if getattr(w, 'quality_score', 0.0) >= 80 else ('B' if getattr(w, 'quality_score', 0.0) >= 60 else 'C')),
                        })
                    df_waves = pd.DataFrame(wave_data).sort_values('Start', ascending=False).reset_index(drop=True)
                    st.dataframe(df_waves, use_container_width=True)
                else:
                    st.info("No 4-hour waves detected")

            with tab1h:
                waves_1h = waves_dict.get('1h', [])
                if waves_1h:
                    from datetime import datetime as _dt3
                    wave_data = []
                    for w in waves_1h:
                        projected_end = w.end_time
                        now = _dt3.now(projected_end.tz) if getattr(projected_end, 'tz', None) else _dt3.now()
                        is_active = projected_end > now
                        wave_data.append({
                            'Start': w.start_time.strftime('%Y-%m-%d %H:%M'),
                            'Projected End': projected_end.strftime('%Y-%m-%d %H:%M'),
                            'Status': '🟢 Active' if is_active else '⚪ Complete',
                            'Direction': (w.direction.value if hasattr(w.direction, 'value') else str(w.direction)).upper(),
                            'Start Price': f"${w.start_price:.2f}",
                            'End Price': f"${w.end_price:.2f}",
                            'Amplitude': f"${w.amplitude:.2f}",
                        })
                    df_waves = pd.DataFrame(wave_data).sort_values('Start', ascending=False).reset_index(drop=True)
                    st.dataframe(df_waves, use_container_width=True)
                else:
                    st.info("No 1-hour waves detected")

            with tab10m:
                waves_10m = waves_dict.get('10min', [])
                if waves_10m:
                    from datetime import datetime as _dt4
                    wave_data = []
                    for w in waves_10m:
                        projected_end = w.end_time
                        now = _dt4.now(projected_end.tz) if getattr(projected_end, 'tz', None) else _dt4.now()
                        is_active = projected_end > now
                        wave_data.append({
                            'Start': w.start_time.strftime('%Y-%m-%d %H:%M'),
                            'Projected End': projected_end.strftime('%Y-%m-%d %H:%M'),
                            'Status': '🟢 Active' if is_active else '⚪ Complete',
                            'Direction': (w.direction.value if hasattr(w.direction, 'value') else str(w.direction)).upper(),
                            'Start Price': f"${w.start_price:.2f}",
                            'End Price': f"${w.end_price:.2f}",
                            'Amplitude': f"${w.amplitude:.2f}",
                        })
                    df_waves = pd.DataFrame(wave_data).sort_values('Start', ascending=False).reset_index(drop=True)
                    st.dataframe(df_waves, use_container_width=True)
                else:
                    st.info("No 10-minute waves detected")

        except Exception as e:
            st.error(f"❌ Error during analysis: {str(e)}")
            with st.expander("Show error details"):
                st.exception(e)
else:
    st.info("👆 Enter a symbol and click 'Analyze Waves' to begin")
