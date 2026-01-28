"""
Interactive web-based pivot levels visualization for trading charts.

Optimized for:
- Real-time streaming data
- Responsive charts with zoom/pan
- Multi-period pivot level rendering
- Performance on large datasets (1000+ bars)
- Export to interactive HTML

Features:
- Plotly-based interactive charts
- Period-aware styling and layering
- Confluence zone highlighting
- Analytics dashboard integration
- Mobile-responsive design
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


class PivotLevelsWebChart:
    """
    Interactive Plotly-based pivot levels visualization.

    Optimized for web rendering with real-time updates.
    """

    # Period-based color scheme (matching TradingView)
    PERIOD_COLORS = {
        3: '#A9A9A9',      # Dark gray (ultra micro)
        5: '#C0C0C0',      # Silver (micro)
        10: '#4D94FF',     # Blue (short-short)
        13: '#5CA7FF',     # Light blue
        25: '#3399FF',     # Cyan (short)
        50: '#00CCCC',     # Bright cyan (medium)
        100: '#FFD700',    # Gold (long)
        200: '#FF8C00',    # Dark orange (very long)
    }

    # Status-based colors (support, resistance, active)
    STATUS_COLORS = {
        'support': '#26A69A',      # Green
        'resistance': '#EF5350',   # Red
        'active': '#1B85FF',       # Blue
    }

    def __init__(self, theme: str = 'dark', height: int = 700, width: int = 1200):
        """
        Initialize web chart visualizer.

        Args:
            theme: 'dark' or 'light' template
            height: Chart height in pixels
            width: Chart width in pixels
        """
        self.theme = theme
        self.height = height
        self.width = width
        self.template = 'plotly_dark' if theme == 'dark' else 'plotly_white'

    def create_chart(
        self,
        df: pd.DataFrame,
        pivot_levels: List[Dict[str, Any]],
        analytics: Optional[Dict[str, Any]] = None,
        volume_data: Optional[pd.Series] = None,
        show_volume: bool = True,
    ) -> go.Figure:
        """
        Create interactive pivot levels chart.

        Args:
            df: OHLC DataFrame with columns: timestamp, open, high, low, close
            pivot_levels: List of dicts with 'period', 'levelHigh', 'levelLow', 'status'
            analytics: Optional analytics data (strength, confidence, etc)
            volume_data: Optional volume series
            show_volume: Show volume subplot

        Returns:
            Plotly Figure object
        """
        # Create subplots
        rows = 2 if show_volume else 1
        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03 if show_volume else 0,
            row_heights=[0.75, 0.25] if show_volume else [1],
            subplot_titles=('OHLC with Pivot Levels', 'Volume') if show_volume else None,
        )

        # Add candlesticks
        fig.add_trace(
            go.Candlestick(
                x=df.index if isinstance(df.index, pd.DatetimeIndex) else range(len(df)),
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='OHLC',
                increasing_line_color='#26A69A',
                decreasing_line_color='#EF5350',
                hovertemplate=(
                    '<b>%{x}</b><br>' +
                    'O: %{open:.4f}<br>' +
                    'H: %{high:.4f}<br>' +
                    'L: %{low:.4f}<br>' +
                    'C: %{close:.4f}<extra></extra>'
                ),
            ),
            row=1, col=1
        )

        # Add pivot levels
        self._add_pivot_levels(fig, pivot_levels, df)

        # Add volume if present
        if show_volume and 'volume' in df.columns:
            colors = [
                '#26A69A' if df.iloc[i]['close'] >= df.iloc[i]['open'] else '#EF5350'
                for i in range(len(df))
            ]
            fig.add_trace(
                go.Bar(
                    x=df.index if isinstance(df.index, pd.DatetimeIndex) else range(len(df)),
                    y=df['volume'],
                    name='Volume',
                    marker=dict(color=colors, opacity=0.5),
                    hovertemplate='Volume: %{y:,.0f}<extra></extra>',
                ),
                row=2, col=1
            )

        # Update layout
        self._update_layout(fig, analytics)

        return fig

    def _add_pivot_levels(
        self,
        fig: go.Figure,
        pivot_levels: List[Dict[str, Any]],
        df: pd.DataFrame
    ):
        """Add pivot level lines to chart."""
        x_axis = df.index if isinstance(df.index, pd.DatetimeIndex) else range(len(df))
        x_extended = list(x_axis) + [x_axis[-1] + (x_axis[-1] - x_axis[-2])] * 20

        # Group by period for better organization
        by_period = {}
        for level in pivot_levels:
            period = level.get('period', 50)
            if period not in by_period:
                by_period[period] = []
            by_period[period].append(level)

        # Plot each period
        for period in sorted(by_period.keys(), reverse=True):
            levels = by_period[period]
            color = self.PERIOD_COLORS.get(period, '#808080')

            for level in levels:
                level_high = level.get('levelHigh')
                level_low = level.get('levelLow')
                status = level.get('status', 'active')

                # High pivot level
                if level_high:
                    fig.add_trace(
                        go.Scatter(
                            x=x_extended,
                            y=[level_high] * len(x_extended),
                            mode='lines',
                            name=f'P{period} High',
                            line=dict(
                                color=color,
                                width=1.5,
                                dash='dash' if status == 'active' else 'solid',
                            ),
                            opacity=0.6,
                            hovertemplate=f'P{period} High: {level_high:.4f}<extra></extra>',
                            showlegend=(period == sorted(by_period.keys())[-1]),
                        ),
                        row=1, col=1
                    )

                # Low pivot level
                if level_low:
                    fig.add_trace(
                        go.Scatter(
                            x=x_extended,
                            y=[level_low] * len(x_extended),
                            mode='lines',
                            name=f'P{period} Low',
                            line=dict(
                                color=color,
                                width=1.5,
                                dash='dot' if status == 'active' else 'solid',
                            ),
                            opacity=0.6,
                            hovertemplate=f'P{period} Low: {level_low:.4f}<extra></extra>',
                            showlegend=(period == sorted(by_period.keys())[-1]),
                        ),
                        row=1, col=1
                    )

                # Zone fill between high and low
                if level_high and level_low:
                    fig.add_trace(
                        go.Scatter(
                            x=x_extended + x_extended[::-1],
                            y=[level_high] * len(x_extended) + [level_low] * len(x_extended),
                            fill='toself',
                            fillcolor=color,
                            line=dict(color='rgba(0,0,0,0)'),
                            opacity=0.1,
                            name=f'P{period} Zone',
                            showlegend=False,
                            hoverinfo='skip',
                        ),
                        row=1, col=1
                    )

    def _update_layout(self, fig: go.Figure, analytics: Optional[Dict[str, Any]]):
        """Update chart layout and styling."""
        fig.update_layout(
            template=self.template,
            height=self.height,
            width=self.width,
            hovermode='x unified',
            xaxis_rangeslider_visible=False,
            margin=dict(l=60, r=20, t=80, b=60),
        )

        # Add annotations for analytics
        if analytics:
            annotations = self._create_analytics_annotations(analytics)
            fig.update_layout(annotations=list(fig.layout.annotations) + annotations)

        # Update axis labels
        fig.update_xaxes(title_text="Date/Time" if hasattr(fig, 'data') else "Bar Index")
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1) if len(fig.data) > 1 else None

    def _create_analytics_annotations(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create text annotations for analytics metrics."""
        annotations = []

        # Overall strength
        if 'overall_strength' in analytics:
            strength = analytics['overall_strength']
            strength_text = f"Strength: {strength * 100:.1f}%"
            annotations.append(
                dict(
                    text=strength_text,
                    xref='paper', yref='paper',
                    x=0.02, y=0.98,
                    showarrow=False,
                    bgcolor='rgba(0,0,0,0.7)',
                    bordercolor='#888',
                    borderwidth=1,
                    font=dict(size=12, color='white'),
                    align='left'
                )
            )

        # Pivot count
        if 'pivot_count' in analytics:
            pivot_text = f"Pivots: {analytics['pivot_count']}"
            annotations.append(
                dict(
                    text=pivot_text,
                    xref='paper', yref='paper',
                    x=0.02, y=0.92,
                    showarrow=False,
                    bgcolor='rgba(0,0,0,0.7)',
                    bordercolor='#888',
                    borderwidth=1,
                    font=dict(size=12, color='white'),
                    align='left'
                )
            )

        return annotations

    def save_html(self, fig: go.Figure, filepath: str, include_plotlyjs: str = 'cdn'):
        """
        Save chart as interactive HTML.

        Args:
            fig: Plotly figure
            filepath: Output file path
            include_plotlyjs: 'cdn', 'inline', or 'require' for plotly.js inclusion
        """
        fig.write_html(
            filepath,
            include_plotlyjs=include_plotlyjs,
            config={'responsive': True, 'scrollZoom': True}
        )
        logger.info(f"Interactive chart saved to {filepath}")

    def save_static(self, fig: go.Figure, filepath: str, width: int = 1200, height: int = 700):
        """Save chart as static image (requires kaleido)."""
        try:
            fig.write_image(filepath, width=width, height=height, scale=2)
            logger.info(f"Static image saved to {filepath}")
        except ImportError:
            logger.error("Install kaleido for static image export: pip install kaleido")


class PivotLevelsDashboard:
    """
    Multi-chart dashboard for pivot level analysis.

    Shows:
    - Main OHLC chart with pivot levels
    - Period effectiveness comparison
    - Strength distribution
    - Confluence zone map
    """

    def __init__(self, theme: str = 'dark'):
        self.theme = theme
        self.template = 'plotly_dark' if theme == 'dark' else 'plotly_white'

    def create_dashboard(
        self,
        df: pd.DataFrame,
        pivot_levels: List[Dict[str, Any]],
        metrics: Optional[Dict[str, Any]] = None,
    ) -> go.Figure:
        """
        Create multi-panel dashboard.

        Args:
            df: OHLC data
            pivot_levels: Pivot levels with period info
            metrics: Period effectiveness metrics

        Returns:
            Plotly Figure with subplots
        """
        # Create 2x2 grid
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Price Chart', 'Period Effectiveness',
                'Pivot Distribution', 'Strength Heatmap'
            ),
            specs=[
                [{'secondary_y': False}, {'secondary_y': False}],
                [{'secondary_y': False}, {'secondary_y': False}],
            ]
        )

        # Panel 1: Price chart with pivots
        chart = PivotLevelsWebChart(theme=self.theme)
        price_fig = chart.create_chart(df, pivot_levels)

        # Extract candlestick and pivot traces
        for trace in price_fig.data:
            fig.add_trace(trace, row=1, col=1)

        # Panel 2: Period effectiveness
        if metrics:
            self._add_period_effectiveness(fig, metrics)

        # Panel 3: Pivot distribution
        self._add_pivot_distribution(fig, pivot_levels)

        # Panel 4: Strength heatmap
        if metrics:
            self._add_strength_heatmap(fig, metrics)

        fig.update_layout(
            template=self.template,
            height=1000,
            width=1600,
            showlegend=True,
        )

        return fig

    def _add_period_effectiveness(self, fig: go.Figure, metrics: Dict[str, Any]):
        """Add period effectiveness bar chart."""
        if 'period_effectiveness' not in metrics:
            return

        periods = [m['period'] for m in metrics['period_effectiveness']]
        effectiveness = [m['effectiveness'] for m in metrics['period_effectiveness']]

        fig.add_trace(
            go.Bar(
                x=periods,
                y=effectiveness,
                name='Effectiveness',
                marker_color='#26A69A',
            ),
            row=1, col=2
        )

        fig.update_xaxes(title_text='Period', row=1, col=2)
        fig.update_yaxes(title_text='Score', row=1, col=2)

    def _add_pivot_distribution(self, fig: go.Figure, pivot_levels: List[Dict[str, Any]]):
        """Add pivot distribution histogram."""
        levels = [l['levelHigh'] for l in pivot_levels if l.get('levelHigh')]
        levels.extend([l['levelLow'] for l in pivot_levels if l.get('levelLow')])

        fig.add_trace(
            go.Histogram(
                x=levels,
                nbinsx=20,
                name='Pivot Distribution',
                marker_color='#3399FF',
            ),
            row=2, col=1
        )

        fig.update_xaxes(title_text='Price Level', row=2, col=1)
        fig.update_yaxes(title_text='Frequency', row=2, col=1)

    def _add_strength_heatmap(self, fig: go.Figure, metrics: Dict[str, Any]):
        """Add strength heatmap."""
        if 'strength_matrix' not in metrics:
            return

        strength_data = metrics['strength_matrix']

        fig.add_trace(
            go.Heatmap(
                z=strength_data,
                name='Strength',
                colorscale='RdYlGn',
            ),
            row=2, col=2
        )

    def save_dashboard(self, fig: go.Figure, filepath: str):
        """Save dashboard as HTML."""
        fig.write_html(
            filepath,
            config={'responsive': True, 'scrollZoom': True}
        )
        logger.info(f"Dashboard saved to {filepath}")


def create_interactive_pivot_chart(
    df: pd.DataFrame,
    pivot_levels: List[Dict[str, Any]],
    analytics: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
    theme: str = 'dark'
) -> go.Figure:
    """
    Quick function to create interactive pivot chart.

    Args:
        df: OHLC DataFrame
        pivot_levels: List of pivot level dicts
        analytics: Optional analytics metrics
        output_path: Optional path to save HTML
        theme: 'dark' or 'light'

    Returns:
        Plotly Figure
    """
    chart = PivotLevelsWebChart(theme=theme)
    fig = chart.create_chart(df, pivot_levels, analytics=analytics)

    if output_path:
        chart.save_html(fig, output_path)

    return fig
