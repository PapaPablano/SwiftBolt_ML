"""Volatility surface visualization.

Create 3D plots of implied volatility surfaces across strikes and maturities.

Usage:
    from src.visualization.volatility_surfaces import VolatilitySurfacePlotter
    from src.models.volatility_surface import VolatilitySurface
    
    # Build surface
    surface = VolatilitySurface()
    # ... add slices ...
    surface.fit()
    
    # Plot
    plotter = VolatilitySurfacePlotter(surface)
    fig = plotter.plot_3d_surface()
    fig.show()
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

logger = logging.getLogger(__name__)


class VolatilitySurfacePlotter:
    """Volatility surface 3D plotter."""
    
    def __init__(self, volatility_surface):
        """Initialize plotter.
        
        Args:
            volatility_surface: VolatilitySurface object (must be fitted)
        """
        self.surface = volatility_surface
        
        if not self.surface.surface_fitted:
            raise ValueError("VolatilitySurface must be fitted before plotting")
        
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly not available")
    
    def plot_3d_surface(
        self,
        n_strikes: int = 50,
        n_maturities: int = 30
    ):
        """Plot 3D volatility surface.
        
        Args:
            n_strikes: Number of strike points
            n_maturities: Number of maturity points
        
        Returns:
            Plotly figure
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        # Create grid
        strike_min, strike_max = self.surface.strike_range
        mat_min, mat_max = self.surface.maturity_range
        
        strikes = np.linspace(strike_min, strike_max, n_strikes)
        maturities = np.linspace(mat_min, mat_max, n_maturities)
        
        strikes_grid, maturities_grid = np.meshgrid(strikes, maturities)
        
        # Calculate implied vols
        iv_grid = np.zeros_like(strikes_grid)
        
        for i in range(n_maturities):
            for j in range(n_strikes):
                K = strikes_grid[i, j]
                T = maturities_grid[i, j]
                iv_grid[i, j] = self.surface.get_volatility(K, T)
        
        # Plot
        fig = go.Figure(data=[go.Surface(
            x=strikes_grid,
            y=maturities_grid * 365,  # Convert to days
            z=iv_grid * 100,  # Convert to percentage
            colorscale='Jet',
            colorbar=dict(title='Implied Vol (%)')
        )])
        
        fig.update_layout(
            title='Implied Volatility Surface',
            scene=dict(
                xaxis_title='Strike Price',
                yaxis_title='Days to Maturity',
                zaxis_title='Implied Vol (%)'
            ),
            width=900,
            height=700
        )
        
        return fig
    
    def plot_volatility_smile(
        self,
        maturity_days: int = 30
    ):
        """Plot volatility smile for a specific maturity.
        
        Args:
            maturity_days: Maturity in days
        
        Returns:
            Plotly figure
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        T = maturity_days / 365
        
        strike_min, strike_max = self.surface.strike_range
        strikes = np.linspace(strike_min, strike_max, 100)
        
        ivs = [self.surface.get_volatility(K, T) for K in strikes]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=strikes,
            y=np.array(ivs) * 100,
            mode='lines',
            name=f'{maturity_days}D Smile',
            line=dict(width=3)
        ))
        
        fig.update_layout(
            title=f'Volatility Smile - {maturity_days} Days to Maturity',
            xaxis_title='Strike Price',
            yaxis_title='Implied Volatility (%)',
            hovermode='x'
        )
        
        return fig


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Volatility Surface Plotter - Self Test")
    print("=" * 70)
    
    if not PLOTLY_AVAILABLE:
        print("\n⚠️ Plotly not available, skipping tests")
    else:
        try:
            from ..models.volatility_surface import VolatilitySurface
        except ImportError:
            from src.models.volatility_surface import VolatilitySurface
        
        # Create sample surface
        print("\n📊 Creating sample volatility surface...")
        
        surface = VolatilitySurface()
        
        # Add sample slices
        base_vol = 0.25
        strikes = np.array([80, 90, 100, 110, 120])
        
        for T in [30/365, 60/365, 90/365]:
            # Create smile
            moneyness = strikes / 100
            smile = base_vol + 0.05 * (moneyness - 1)**2
            
            surface.add_slice(T, strikes, smile, F=100)
        
        surface.fit()
        
        # Create plotter
        plotter = VolatilitySurfacePlotter(surface)
        
        print("\n📊 Generating 3D surface...")
        fig_3d = plotter.plot_3d_surface(n_strikes=30, n_maturities=20)
        print("3D surface generated")
        
        print("\n📊 Generating volatility smile...")
        fig_smile = plotter.plot_volatility_smile(maturity_days=45)
        print("Smile plot generated")
        
        print("\n✅ Visualization tests complete!")
    
    print("\n" + "=" * 70)
    print("✅ Volatility surface plotter test complete!")
    print("=" * 70)
