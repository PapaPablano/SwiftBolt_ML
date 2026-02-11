"""
Minimal forecast renderer: dots + connecting lines
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import plotly.graph_objects as go


def add_simple_forecast_dots(
    fig: go.Figure,
    predictions_dict: Dict,
    df_ohlcv: Optional[pd.DataFrame] = None,
    colors: Optional[Dict] = None,
) -> go.Figure:
    """
    Add forecast prediction dots with connecting lines.

    Simple approach:
    - One dot per prediction (at exact date and $ price)
    - Lines connecting the dots
    - Three confidence levels: 90%, 95%, 99%
    - Hover shows: date, price, confidence level

    Args:
        fig: Plotly figure
        predictions_dict: {
            '0.90': DataFrame with 'time' and 'predicted_price',
            '0.95': DataFrame with 'time' and 'predicted_price',
            '0.99': DataFrame with 'time' and 'predicted_price'
        }
        df_ohlcv: Historical data (for reference)
        colors: Color mapping {'0.90': color, ...}

    Returns:
        Updated figure with forecast dots/lines
    """

    if colors is None:
        colors = {
            '0.90': 'rgba(255, 193, 7, 1)',      # Yellow - 90%
            '0.95': 'rgba(33, 150, 243, 1)',     # Blue - 95%
            '0.99': 'rgba(76, 175, 80, 1)',      # Green - 99%
        }

    if df_ohlcv is None or len(df_ohlcv) == 0:
        return fig

    # Iterate through confidence levels (reverse order for layering)
    for conf_level in ['0.99', '0.95', '0.90']:
        if conf_level not in predictions_dict or predictions_dict[conf_level] is None:
            continue

        preds = predictions_dict[conf_level]

        if len(preds) == 0 or 'predicted_price' not in preds.columns or 'time' not in preds.columns:
            continue

        color = colors.get(conf_level, 'blue')
        conf_pct = int(float(conf_level) * 100)

        # Add connecting line + markers
        fig.add_trace(
            go.Scatter(
                x=preds['time'],
                y=preds['predicted_price'],
                mode='lines+markers',
                name=f'{conf_pct}% Confidence',
                line=dict(color=color, width=2),
                marker=dict(
                    size=8,
                    color=color,
                    symbol='circle',
                    line=dict(color='white', width=1),  # White outline on dots
                ),
                hovertemplate=(
                    '<b>%{x|%Y-%m-%d %H:%M}</b><br>'
                    f'{conf_pct}% Forecast<br>'
                    'Price: $%{y:.2f}<extra></extra>'
                ),
                opacity=0.9,
            )
        )

    return fig


def add_forecast_table(
    predictions_dict: Dict,
    df_ohlcv: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Create a summary table of all forecasts.

    Returns:
        DataFrame with columns:
        - Date (time)
        - 90% Forecast
        - 95% Forecast
        - 99% Forecast
    """

    if not predictions_dict or all(v is None for v in predictions_dict.values()):
        return pd.DataFrame()

    # Get times from first available prediction
    times = None
    for conf_level in ['0.90', '0.95', '0.99']:
        if conf_level in predictions_dict and predictions_dict[conf_level] is not None:
            preds = predictions_dict[conf_level]
            if 'time' in preds.columns:
                times = preds['time'].values
                break

    if times is None:
        return pd.DataFrame()

    # Build table
    table_data: Dict[str, object] = {
        'Date': times,
        '90% Forecast': None,
        '95% Forecast': None,
        '99% Forecast': None,
    }

    for conf_level in ['0.90', '0.95', '0.99']:
        col_name = f'{int(float(conf_level) * 100)}% Forecast'
        if conf_level in predictions_dict and predictions_dict[conf_level] is not None:
            preds = predictions_dict[conf_level]
            if 'predicted_price' in preds.columns:
                table_data[col_name] = preds['predicted_price'].values

    return pd.DataFrame(table_data)


