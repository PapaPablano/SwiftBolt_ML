"""
Flux Charts Style Visualization for Polynomial S/R Indicator.

Creates TradingView-style charts with:
- OHLC candlesticks
- Polynomial regression curves (support/resistance)
- Pivot point markers
- Break/retest signals
- Forecast extensions
- Dynamic zones

Matches the aesthetic of TradingView's Flux Charts indicator.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

logger = logging.getLogger(__name__)


class FluxChartVisualizer:
    """
    TradingView-style visualization for polynomial S/R indicator.

    Features:
    - Dark theme matching TradingView
    - Smooth polynomial curves
    - Gradient fill zones
    - Interactive hover details
    - Multi-period pivot levels
    - Advanced analytics display
    - Export to PNG/HTML

    Usage:
        viz = FluxChartVisualizer(style='dark')
        fig = viz.plot_polynomial_sr(
            df=ohlc_data,
            support_coeffs=support_coeffs,
            resistance_coeffs=resistance_coeffs,
            pivots=pivot_points,
            pivot_levels=multi_period_levels
        )
        viz.save(fig, 'chart.png')
    """
    
    # TradingView color scheme
    COLORS = {
        'dark': {
            'background': '#131722',
            'grid': '#1E222D',
            'text': '#D1D4DC',
            'candle_up': '#26A69A',
            'candle_down': '#EF5350',
            'support': '#2962FF',
            'resistance': '#F23645',
            'pivot_support': '#089981',
            'pivot_resistance': '#F23645',
            'zone_support': '#2962FF',
            'zone_resistance': '#F23645',
            'break_signal': '#FFB74D',
            'retest_signal': '#9C27B0',
        },
        'light': {
            'background': '#FFFFFF',
            'grid': '#E0E3EB',
            'text': '#131722',
            'candle_up': '#26A69A',
            'candle_down': '#EF5350',
            'support': '#2962FF',
            'resistance': '#F23645',
            'pivot_support': '#089981',
            'pivot_resistance': '#F23645',
            'zone_support': '#2962FF',
            'zone_resistance': '#F23645',
            'break_signal': '#FFB74D',
            'retest_signal': '#9C27B0',
        }
    }
    
    def __init__(
        self,
        style: str = 'dark',
        figsize: Tuple[int, int] = (16, 10),
        dpi: int = 100
    ):
        """
        Initialize visualizer.
        
        Args:
            style: 'dark' or 'light' theme
            figsize: Figure size in inches
            dpi: Resolution
        """
        self.style = style
        self.colors = self.COLORS[style]
        self.figsize = figsize
        self.dpi = dpi
        
        # Set matplotlib style
        plt.style.use('dark_background' if style == 'dark' else 'default')
    
    def plot_polynomial_sr(
        self,
        df: pd.DataFrame,
        regressor: Any,
        pivots: Optional[List[Dict[str, Any]]] = None,
        signals: Optional[List[Dict[str, Any]]] = None,
        forecast_bars: int = 50,
        show_zones: bool = True,
        show_pivots: bool = True,
        show_signals: bool = True,
        pivot_levels: Optional[List[Dict[str, Any]]] = None,
        show_pivot_levels: bool = True,
        analytics: Optional[Dict[str, Any]] = None,
        title: str = "Polynomial Support & Resistance"
    ) -> plt.Figure:
        """
        Create complete Flux Charts style visualization.

        Args:
            df: OHLC DataFrame with columns: open, high, low, close, timestamp
            regressor: SRPolynomialRegressor instance with fitted curves
            pivots: List of pivot points {'index', 'price', 'type'}
            signals: List of break/retest signals
            forecast_bars: Number of bars to extend forecast
            show_zones: Show support/resistance zones
            show_pivots: Show pivot point markers
            show_signals: Show break/retest signals
            pivot_levels: List of multi-period pivot levels with 'period', 'levelHigh', 'levelLow'
            show_pivot_levels: Display multi-period pivot levels
            analytics: Dict with 'overall_strength', 'pivot_count', 'confidence' metrics
            title: Chart title

        Returns:
            Matplotlib figure
        """
        # Create figure
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=self.figsize,
            dpi=self.dpi,
            gridspec_kw={'height_ratios': [4, 1], 'hspace': 0.05}
        )
        
        fig.patch.set_facecolor(self.colors['background'])
        ax1.set_facecolor(self.colors['background'])
        ax2.set_facecolor(self.colors['background'])
        
        # Plot main chart
        self._plot_candlesticks(ax1, df)
        
        # Plot polynomial curves
        if regressor.support_coeffs is not None:
            self._plot_polynomial_curve(
                ax1, df, regressor,
                curve_type='support',
                forecast_bars=forecast_bars,
                show_zone=show_zones
            )
        
        if regressor.resistance_coeffs is not None:
            self._plot_polynomial_curve(
                ax1, df, regressor,
                curve_type='resistance',
                forecast_bars=forecast_bars,
                show_zone=show_zones
            )
        
        # Plot pivot points
        if show_pivots and pivots:
            self._plot_pivots(ax1, pivots)
        
        # Plot break/retest signals
        if show_signals and signals:
            self._plot_signals(ax1, df, signals)

        # Plot multi-period pivot levels
        if show_pivot_levels and pivot_levels:
            self._plot_pivot_levels(ax1, df, pivot_levels)

        # Plot analytics annotations
        if analytics:
            self._add_analytics_panel(ax1, analytics)

        # Plot volume
        self._plot_volume(ax2, df)

        # Styling
        self._apply_styling(ax1, ax2, df, title)
        
        # Add legend
        self._add_legend(ax1, regressor)
        
        plt.tight_layout()
        return fig
    
    def _plot_candlesticks(
        self,
        ax: plt.Axes,
        df: pd.DataFrame
    ):
        """Plot OHLC candlesticks."""
        width = 0.6
        width2 = 0.05
        
        for idx in range(len(df)):
            row = df.iloc[idx]
            
            color = (self.colors['candle_up'] 
                    if row['close'] >= row['open'] 
                    else self.colors['candle_down'])
            
            # Candle body
            height = abs(row['close'] - row['open'])
            bottom = min(row['open'], row['close'])
            
            ax.add_patch(Rectangle(
                (idx - width/2, bottom),
                width, height,
                facecolor=color,
                edgecolor=color,
                alpha=0.8
            ))
            
            # Wicks
            ax.plot(
                [idx, idx],
                [row['low'], row['high']],
                color=color,
                linewidth=1,
                alpha=0.8
            )
    
    def _plot_polynomial_curve(
        self,
        ax: plt.Axes,
        df: pd.DataFrame,
        regressor: Any,
        curve_type: str,
        forecast_bars: int,
        show_zone: bool
    ):
        """Plot polynomial regression curve with forecast."""
        n_bars = len(df)
        
        # Historical range
        hist_indices = np.arange(n_bars)
        
        # Forecast range
        forecast_indices = np.arange(n_bars, n_bars + forecast_bars)
        all_indices = np.concatenate([hist_indices, forecast_indices])
        
        # Get coefficients
        if curve_type == 'support':
            coeffs = regressor.support_coeffs
            color = self.colors['support']
            zone_color = self.colors['zone_support']
        else:
            coeffs = regressor.resistance_coeffs
            color = self.colors['resistance']
            zone_color = self.colors['zone_resistance']
        
        if coeffs is None:
            return
        
        # Evaluate polynomial
        levels = []
        for idx in all_indices:
            level = regressor.predict_level(coeffs, int(idx), curve_type=curve_type)
            levels.append(level)
        
        levels = np.array(levels)
        
        # Plot historical line (solid)
        ax.plot(
            hist_indices,
            levels[:n_bars],
            color=color,
            linewidth=2.5,
            alpha=0.9,
            label=f'{curve_type.capitalize()} Polynomial',
            zorder=5
        )
        
        # Plot forecast line (dashed)
        ax.plot(
            forecast_indices,
            levels[n_bars:],
            color=color,
            linewidth=2.5,
            linestyle='--',
            alpha=0.6,
            zorder=5
        )
        
        # Add gradient zone
        if show_zone:
            self._add_gradient_zone(
                ax, all_indices, levels, zone_color, curve_type
            )
    
    def _add_gradient_zone(
        self,
        ax: plt.Axes,
        indices: np.ndarray,
        levels: np.ndarray,
        color: str,
        curve_type: str
    ):
        """Add gradient-filled zone around S/R line."""
        # Zone width (percentage of price)
        zone_width_pct = 0.003  # 0.3%
        
        upper = levels * (1 + zone_width_pct)
        lower = levels * (1 - zone_width_pct)
        
        if curve_type == 'resistance':
            # Zone above resistance
            ax.fill_between(
                indices,
                levels,
                upper,
                color=color,
                alpha=0.15,
                zorder=3
            )
        else:
            # Zone below support
            ax.fill_between(
                indices,
                lower,
                levels,
                color=color,
                alpha=0.15,
                zorder=3
            )
    
    def _plot_pivots(
        self,
        ax: plt.Axes,
        pivots: List[Dict[str, Any]]
    ):
        """Plot pivot point markers."""
        for pivot in pivots:
            if pivot['type'] == 'low':
                color = self.colors['pivot_support']
                marker = '^'  # Up triangle
                offset = -0.002  # Below price
            else:
                color = self.colors['pivot_resistance']
                marker = 'v'  # Down triangle
                offset = 0.002  # Above price
            
            price_adjusted = pivot['price'] * (1 + offset)
            
            ax.scatter(
                pivot['index'],
                price_adjusted,
                color=color,
                marker=marker,
                s=120,
                zorder=10,
                edgecolors='white',
                linewidths=0.5,
                alpha=0.9
            )
    
    def _plot_signals(
        self,
        ax: plt.Axes,
        df: pd.DataFrame,
        signals: List[Dict[str, Any]]
    ):
        """Plot break and retest signals."""
        for signal in signals:
            signal_type = signal.get('type', '')
            idx = signal.get('index', 0)
            
            if idx >= len(df):
                continue
            
            row = df.iloc[idx]
            
            if 'break' in signal_type.lower():
                color = self.colors['break_signal']
                marker = 'D'  # Diamond
                label = 'Break'
            else:
                color = self.colors['retest_signal']
                marker = 'o'  # Circle
                label = 'Retest'
            
            # Place at high/low depending on type
            if 'support' in signal_type.lower():
                price = row['low'] * 0.998
            else:
                price = row['high'] * 1.002
            
            ax.scatter(
                idx,
                price,
                color=color,
                marker=marker,
                s=100,
                zorder=11,
                edgecolors='white',
                linewidths=1,
                alpha=0.85
            )
            
            # Add label
            ax.annotate(
                label,
                (idx, price),
                textcoords="offset points",
                xytext=(0, -15 if 'support' in signal_type.lower() else 15),
                ha='center',
                fontsize=8,
                color=color,
                weight='bold'
            )
    
    def _plot_pivot_levels(
        self,
        ax: plt.Axes,
        df: pd.DataFrame,
        pivot_levels: List[Dict[str, Any]]
    ):
        """Plot multi-period pivot levels with period-based coloring."""
        # Period-based color map
        period_colors = {
            5: '#C0C0C0',      # Silver (micro)
            10: '#4D94FF',     # Blue (short-short)
            13: '#5CA7FF',     # Light Blue
            25: '#3399FF',     # Cyan (short)
            50: '#00CCCC',     # Bright Cyan (medium)
            100: '#FFD700',    # Gold (long)
        }

        for level in pivot_levels:
            period = level.get('period', 50)
            high_level = level.get('levelHigh')
            low_level = level.get('levelLow')
            color = period_colors.get(period, '#808080')
            alpha = 0.4 + (period / 150.0) * 0.5  # Larger periods more opaque

            # Draw high pivot level
            if high_level:
                ax.axhline(
                    y=high_level,
                    color=color,
                    linestyle='--',
                    linewidth=1.5,
                    alpha=alpha,
                    label=f'Pivot High ({period})'
                )

            # Draw low pivot level
            if low_level:
                ax.axhline(
                    y=low_level,
                    color=color,
                    linestyle=':',
                    linewidth=1.5,
                    alpha=alpha,
                    label=f'Pivot Low ({period})'
                )

            # Add minimal zone shading
            if high_level and low_level:
                ax.fill_between(
                    range(len(df)),
                    low_level,
                    high_level,
                    color=color,
                    alpha=0.05,
                    zorder=2
                )

    def _add_analytics_panel(
        self,
        ax: plt.Axes,
        analytics: Dict[str, Any]
    ):
        """Add analytics information as text annotations."""
        info_text = []

        if 'overall_strength' in analytics:
            strength = analytics['overall_strength']
            strength_pct = f"{strength * 100:.1f}%"
            info_text.append(f"Overall Strength: {strength_pct}")

        if 'pivot_count' in analytics:
            info_text.append(f"Pivots Detected: {analytics['pivot_count']}")

        if 'confidence' in analytics:
            confidence = analytics['confidence']
            conf_pct = f"{confidence * 100:.1f}%"
            info_text.append(f"Confidence: {conf_pct}")

        if info_text:
            text_str = '\n'.join(info_text)
            ax.text(
                0.02, 0.98,
                text_str,
                transform=ax.transAxes,
                fontsize=9,
                verticalalignment='top',
                bbox=dict(
                    boxstyle='round',
                    facecolor=self.colors['background'],
                    edgecolor=self.colors['grid'],
                    alpha=0.8
                ),
                color=self.colors['text'],
                family='monospace'
            )

    def _plot_volume(
        self,
        ax: plt.Axes,
        df: pd.DataFrame
    ):
        """Plot volume bars."""
        if 'volume' not in df.columns:
            ax.set_visible(False)
            return
        
        colors = [
            self.colors['candle_up'] if df.iloc[i]['close'] >= df.iloc[i]['open']
            else self.colors['candle_down']
            for i in range(len(df))
        ]
        
        ax.bar(
            range(len(df)),
            df['volume'],
            color=colors,
            alpha=0.5,
            width=0.8
        )
        
        ax.set_ylabel('Volume', color=self.colors['text'], fontsize=10)
        ax.tick_params(colors=self.colors['text'])
        ax.grid(False)
    
    def _apply_styling(
        self,
        ax1: plt.Axes,
        ax2: plt.Axes,
        df: pd.DataFrame,
        title: str
    ):
        """Apply TradingView-style theme."""
        # Title
        ax1.set_title(
            title,
            color=self.colors['text'],
            fontsize=16,
            weight='bold',
            pad=20
        )
        
        # Grid
        ax1.grid(
            True,
            color=self.colors['grid'],
            linestyle='-',
            linewidth=0.5,
            alpha=0.3
        )
        
        # Axis labels
        ax1.set_ylabel('Price', color=self.colors['text'], fontsize=12)
        ax2.set_xlabel('Bar Index', color=self.colors['text'], fontsize=12)
        
        # Tick colors
        ax1.tick_params(colors=self.colors['text'], labelsize=10)
        ax2.tick_params(colors=self.colors['text'], labelsize=10)
        
        # Spines
        for spine in ax1.spines.values():
            spine.set_edgecolor(self.colors['grid'])
            spine.set_linewidth(1)
        
        for spine in ax2.spines.values():
            spine.set_edgecolor(self.colors['grid'])
            spine.set_linewidth(1)
        
        # X-axis limits
        ax1.set_xlim(-1, len(df) + 50)
        ax2.set_xlim(-1, len(df))
        
        # Remove x-labels from main chart
        ax1.set_xticklabels([])
    
    def _add_legend(
        self,
        ax: plt.Axes,
        regressor: Any
    ):
        """Add custom legend with slope information."""
        legend_elements = []
        
        if regressor.support_coeffs is not None:
            slope = regressor.compute_slope(
                regressor.support_coeffs,
                at_x=1.0,
                curve_type='support'
            )
            slope_str = f"(slope: {slope:.4f})"
            
            legend_elements.append(
                Line2D([0], [0], color=self.colors['support'],
                       linewidth=2.5, label=f'Support {slope_str}')
            )
        
        if regressor.resistance_coeffs is not None:
            slope = regressor.compute_slope(
                regressor.resistance_coeffs,
                at_x=1.0,
                curve_type='resistance'
            )
            slope_str = f"(slope: {slope:.4f})"
            
            legend_elements.append(
                Line2D([0], [0], color=self.colors['resistance'],
                       linewidth=2.5, label=f'Resistance {slope_str}')
            )
        
        # Add pivot markers
        legend_elements.append(
            Line2D([0], [0], marker='^', color='w', 
                   markerfacecolor=self.colors['pivot_support'],
                   markersize=10, linestyle='None', label='Support Pivot')
        )
        
        legend_elements.append(
            Line2D([0], [0], marker='v', color='w',
                   markerfacecolor=self.colors['pivot_resistance'],
                   markersize=10, linestyle='None', label='Resistance Pivot')
        )
        
        ax.legend(
            handles=legend_elements,
            loc='upper left',
            framealpha=0.9,
            facecolor=self.colors['background'],
            edgecolor=self.colors['grid'],
            fontsize=10
        )
    
    def save(
        self,
        fig: plt.Figure,
        filepath: str,
        dpi: Optional[int] = None
    ):
        """
        Save figure to file.
        
        Args:
            fig: Matplotlib figure
            filepath: Output path (.png, .jpg, .svg, .pdf)
            dpi: Override default DPI
        """
        dpi = dpi or self.dpi
        fig.savefig(
            filepath,
            dpi=dpi,
            bbox_inches='tight',
            facecolor=self.colors['background'],
            edgecolor='none'
        )
        logger.info(f"Chart saved to {filepath}")
    
    def show(self, fig: plt.Figure):
        """Display figure interactively."""
        plt.show()


class InteractiveFluxChart:
    """
    Interactive Plotly-based visualization with hover details.
    
    Provides:
    - Hover tooltips with OHLC + S/R levels
    - Zoom/pan controls
    - Export to HTML
    - Responsive design
    """
    
    def __init__(self, style: str = 'dark'):
        """Initialize with plotly."""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            self.go = go
            self.make_subplots = make_subplots
            self.available = True
        except ImportError:
            logger.warning("Plotly not installed. Install with: pip install plotly")
            self.available = False
        
        self.style = style
        self.colors = FluxChartVisualizer.COLORS[style]
    
    def plot_polynomial_sr(
        self,
        df: pd.DataFrame,
        regressor: Any,
        pivots: Optional[List[Dict[str, Any]]] = None,
        forecast_bars: int = 50,
        title: str = "Polynomial Support & Resistance"
    ):
        """
        Create interactive chart.
        
        Args:
            df: OHLC DataFrame
            regressor: Fitted SRPolynomialRegressor
            pivots: Pivot points
            forecast_bars: Forecast extension
            title: Chart title
            
        Returns:
            Plotly figure object
        """
        if not self.available:
            raise RuntimeError("Plotly not installed")
        
        # Create subplots
        fig = self.make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.8, 0.2],
            subplot_titles=(title, 'Volume')
        )
        
        # Add candlesticks
        fig.add_trace(
            self.go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='OHLC',
                increasing_line_color=self.colors['candle_up'],
                decreasing_line_color=self.colors['candle_down']
            ),
            row=1, col=1
        )
        
        # Add polynomial curves
        n_bars = len(df)
        all_indices = list(range(n_bars + forecast_bars))
        
        if regressor.support_coeffs is not None:
            support_levels = [
                regressor.predict_level(
                    regressor.support_coeffs, idx, curve_type='support'
                )
                for idx in all_indices
            ]
            
            fig.add_trace(
                self.go.Scatter(
                    x=all_indices,
                    y=support_levels,
                    mode='lines',
                    name='Support',
                    line=dict(
                        color=self.colors['support'],
                        width=2.5,
                        dash='solid' if True else 'dash'
                    ),
                    hovertemplate='Support: %{y:.2f}<extra></extra>'
                ),
                row=1, col=1
            )
        
        if regressor.resistance_coeffs is not None:
            resistance_levels = [
                regressor.predict_level(
                    regressor.resistance_coeffs, idx, curve_type='resistance'
                )
                for idx in all_indices
            ]
            
            fig.add_trace(
                self.go.Scatter(
                    x=all_indices,
                    y=resistance_levels,
                    mode='lines',
                    name='Resistance',
                    line=dict(
                        color=self.colors['resistance'],
                        width=2.5,
                        dash='solid'
                    ),
                    hovertemplate='Resistance: %{y:.2f}<extra></extra>'
                ),
                row=1, col=1
            )
        
        # Add pivots
        if pivots:
            support_pivots = [p for p in pivots if p['type'] == 'low']
            resistance_pivots = [p for p in pivots if p['type'] == 'high']
            
            if support_pivots:
                fig.add_trace(
                    self.go.Scatter(
                        x=[p['index'] for p in support_pivots],
                        y=[p['price'] for p in support_pivots],
                        mode='markers',
                        name='Support Pivot',
                        marker=dict(
                            symbol='triangle-up',
                            size=12,
                            color=self.colors['pivot_support'],
                            line=dict(color='white', width=1)
                        )
                    ),
                    row=1, col=1
                )
            
            if resistance_pivots:
                fig.add_trace(
                    self.go.Scatter(
                        x=[p['index'] for p in resistance_pivots],
                        y=[p['price'] for p in resistance_pivots],
                        mode='markers',
                        name='Resistance Pivot',
                        marker=dict(
                            symbol='triangle-down',
                            size=12,
                            color=self.colors['pivot_resistance'],
                            line=dict(color='white', width=1)
                        )
                    ),
                    row=1, col=1
                )
        
        # Add volume
        if 'volume' in df.columns:
            colors = [
                self.colors['candle_up'] if df.iloc[i]['close'] >= df.iloc[i]['open']
                else self.colors['candle_down']
                for i in range(len(df))
            ]
            
            fig.add_trace(
                self.go.Bar(
                    x=df.index,
                    y=df['volume'],
                    name='Volume',
                    marker_color=colors,
                    opacity=0.5
                ),
                row=2, col=1
            )
        
        # Update layout
        fig.update_layout(
            template='plotly_dark' if self.style == 'dark' else 'plotly_white',
            xaxis_rangeslider_visible=False,
            height=800,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig
    
    def save_html(self, fig, filepath: str):
        """Save as interactive HTML."""
        fig.write_html(filepath)
        logger.info(f"Interactive chart saved to {filepath}")


# Convenience functions

def create_flux_chart(
    df: pd.DataFrame,
    regressor: Any,
    pivots: Optional[List[Dict[str, Any]]] = None,
    signals: Optional[List[Dict[str, Any]]] = None,
    style: str = 'dark',
    interactive: bool = False,
    save_path: Optional[str] = None,
    pivot_levels: Optional[List[Dict[str, Any]]] = None,
    show_pivot_levels: bool = True,
    analytics: Optional[Dict[str, Any]] = None
):
    """
    Quick function to create Flux-style chart.

    Args:
        df: OHLC DataFrame
        regressor: Fitted SRPolynomialRegressor
        pivots: Pivot points
        signals: Break/retest signals
        style: 'dark' or 'light'
        interactive: Use Plotly instead of Matplotlib
        save_path: Path to save chart
        pivot_levels: Multi-period pivot levels with period metadata
        show_pivot_levels: Display pivot levels on chart
        analytics: Analytics data (strength, confidence, pivot_count)

    Returns:
        Figure object
    """
    if interactive:
        viz = InteractiveFluxChart(style=style)
        fig = viz.plot_polynomial_sr(df, regressor, pivots)
        
        if save_path:
            viz.save_html(fig, save_path)
        
        return fig
    else:
        viz = FluxChartVisualizer(style=style)
        fig = viz.plot_polynomial_sr(
            df, regressor, pivots, signals,
            show_zones=True,
            show_pivots=True,
            show_signals=True,
            pivot_levels=pivot_levels,
            show_pivot_levels=show_pivot_levels,
            analytics=analytics
        )

        if save_path:
            viz.save(fig, save_path)

        return fig


def demo_visualization():
    """Demo with synthetic data."""
    # Create synthetic OHLC data
    np.random.seed(42)
    n_bars = 200
    
    dates = pd.date_range('2024-01-01', periods=n_bars, freq='1h')
    price = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': price + np.random.randn(n_bars) * 0.2,
        'high': price + np.abs(np.random.randn(n_bars)) * 0.5,
        'low': price - np.abs(np.random.randn(n_bars)) * 0.5,
        'close': price + np.random.randn(n_bars) * 0.2,
        'volume': np.random.randint(1000, 10000, n_bars)
    })
    
    # Create synthetic pivots
    pivots = [
        {'index': 20, 'price': df.iloc[20]['low'], 'type': 'low'},
        {'index': 50, 'price': df.iloc[50]['low'], 'type': 'low'},
        {'index': 100, 'price': df.iloc[100]['low'], 'type': 'low'},
        {'index': 150, 'price': df.iloc[150]['low'], 'type': 'low'},
        {'index': 30, 'price': df.iloc[30]['high'], 'type': 'high'},
        {'index': 80, 'price': df.iloc[80]['high'], 'type': 'high'},
        {'index': 120, 'price': df.iloc[120]['high'], 'type': 'high'},
        {'index': 170, 'price': df.iloc[170]['high'], 'type': 'high'},
    ]
    
    # Create mock regressor
    from src.features.sr_polynomial import SRPolynomialRegressor
    
    regressor = SRPolynomialRegressor(degree=2, min_points=4)
    regressor.fit_support_curve(pivots)
    regressor.fit_resistance_curve(pivots)
    
    # Create sample pivot levels for different periods
    pivot_levels = [
        {'period': 5, 'levelHigh': 105, 'levelLow': 95},
        {'period': 25, 'levelHigh': 107, 'levelLow': 93},
        {'period': 50, 'levelHigh': 108, 'levelLow': 92},
    ]

    # Create sample analytics
    analytics = {
        'overall_strength': 0.75,
        'pivot_count': len(pivots),
        'confidence': 0.82
    }

    # Create chart with pivot levels and analytics
    fig = create_flux_chart(
        df=df,
        regressor=regressor,
        pivots=pivots,
        pivot_levels=pivot_levels,
        analytics=analytics,
        style='dark',
        interactive=False,
        save_path='flux_chart_demo.png'
    )

    plt.show()

    print("Demo chart created: flux_chart_demo.png")
    print(f"- Pivots detected: {len(pivots)}")
    print(f"- Pivot levels: {len(pivot_levels)}")
    print(f"- Overall strength: {analytics['overall_strength'] * 100:.1f}%")
    print(f"- Confidence: {analytics['confidence'] * 100:.1f}%")


if __name__ == '__main__':
    demo_visualization()
