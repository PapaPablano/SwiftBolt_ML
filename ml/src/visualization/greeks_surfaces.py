"""3D Greeks surface visualization.

Creates interactive 3D plots of option Greeks across strike prices
and time to maturity.

Usage:
    from src.visualization.greeks_surfaces import GreeksSurfacePlotter
    
    plotter = GreeksSurfacePlotter(S0=100, r=0.05, sigma=0.25)
    
    # Plot delta surface
    fig = plotter.plot_delta_surface()
    fig.show()
    
    # Plot all Greeks
    fig = plotter.plot_all_greeks()
    fig.show()

Requires: plotly
"""

import logging
from typing import Optional, Tuple

import numpy as np

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logging.warning("Plotly not available. Install with: pip install plotly")

logger = logging.getLogger(__name__)


class GreeksSurfacePlotter:
    """3D Greeks surface plotter."""
    
    def __init__(
        self,
        S0: float,
        r: float,
        sigma: float
    ):
        """Initialize Greeks surface plotter.
        
        Args:
            S0: Current stock price
            r: Risk-free rate
            sigma: Volatility
        """
        self.S0 = S0
        self.r = r
        self.sigma = sigma
        
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly not available. Plotting will be disabled.")
        
        logger.info(f"GreeksSurfacePlotter initialized: S0=${S0}, σ={sigma:.2%}")
    
    def _calculate_greeks_grid(
        self,
        strike_range: Tuple[float, float] = (0.7, 1.3),
        time_range: Tuple[float, float] = (0.01, 1.0),
        n_strikes: int = 50,
        n_times: int = 50,
        option_type: str = 'call'
    ) -> Tuple[np.ndarray, np.ndarray, dict]:
        """Calculate Greeks on a 2D grid.
        
        Args:
            strike_range: (min_moneyness, max_moneyness)
            time_range: (min_time_years, max_time_years)
            n_strikes: Number of strike points
            n_times: Number of time points
            option_type: 'call' or 'put'
        
        Returns:
            Tuple of (strikes_grid, times_grid, greeks_dict)
        """
        try:
            from ..models.options_pricing import BlackScholesModel
        except ImportError:
            from src.models.options_pricing import BlackScholesModel
        
        # Create grids
        strikes = np.linspace(
            self.S0 * strike_range[0],
            self.S0 * strike_range[1],
            n_strikes
        )
        times = np.linspace(time_range[0], time_range[1], n_times)
        
        strikes_grid, times_grid = np.meshgrid(strikes, times)
        
        # Initialize Greeks grids
        greeks_grids = {
            'delta': np.zeros_like(strikes_grid),
            'gamma': np.zeros_like(strikes_grid),
            'theta': np.zeros_like(strikes_grid),
            'vega': np.zeros_like(strikes_grid),
            'rho': np.zeros_like(strikes_grid)
        }
        
        # Calculate Greeks for each point
        bs_model = BlackScholesModel(risk_free_rate=self.r)
        
        for i in range(n_times):
            for j in range(n_strikes):
                K = strikes_grid[i, j]
                T = times_grid[i, j]
                
                pricing = bs_model.calculate_greeks(
                    S=self.S0,
                    K=K,
                    T=T,
                    sigma=self.sigma,
                    option_type=option_type
                )
                
                greeks_grids['delta'][i, j] = pricing.delta
                greeks_grids['gamma'][i, j] = pricing.gamma
                greeks_grids['theta'][i, j] = pricing.theta
                greeks_grids['vega'][i, j] = pricing.vega
                greeks_grids['rho'][i, j] = pricing.rho
        
        return strikes_grid, times_grid, greeks_grids
    
    def plot_delta_surface(
        self,
        option_type: str = 'call',
        **kwargs
    ):
        """Plot delta surface.
        
        Args:
            option_type: 'call' or 'put'
            **kwargs: Additional arguments for _calculate_greeks_grid
        
        Returns:
            Plotly figure
        """
        if not PLOTLY_AVAILABLE:
            print("Plotly not available")
            return None
        
        strikes_grid, times_grid, greeks_grids = self._calculate_greeks_grid(
            option_type=option_type,
            **kwargs
        )
        
        fig = go.Figure(data=[go.Surface(
            x=strikes_grid,
            y=times_grid,
            z=greeks_grids['delta'],
            colorscale='RdYlGn',
            colorbar=dict(title='Delta')
        )])
        
        fig.update_layout(
            title=f'Delta Surface ({option_type.capitalize()})',
            scene=dict(
                xaxis_title='Strike Price',
                yaxis_title='Time to Maturity (years)',
                zaxis_title='Delta'
            ),
            width=800,
            height=700
        )
        
        return fig
    
    def plot_gamma_surface(
        self,
        option_type: str = 'call',
        **kwargs
    ):
        """Plot gamma surface.
        
        Args:
            option_type: 'call' or 'put'
            **kwargs: Additional arguments
        
        Returns:
            Plotly figure
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        strikes_grid, times_grid, greeks_grids = self._calculate_greeks_grid(
            option_type=option_type,
            **kwargs
        )
        
        fig = go.Figure(data=[go.Surface(
            x=strikes_grid,
            y=times_grid,
            z=greeks_grids['gamma'],
            colorscale='Viridis',
            colorbar=dict(title='Gamma')
        )])
        
        fig.update_layout(
            title=f'Gamma Surface ({option_type.capitalize()})',
            scene=dict(
                xaxis_title='Strike Price',
                yaxis_title='Time to Maturity (years)',
                zaxis_title='Gamma'
            ),
            width=800,
            height=700
        )
        
        return fig
    
    def plot_all_greeks(
        self,
        option_type: str = 'call',
        **kwargs
    ):
        """Plot all Greeks in subplots.
        
        Args:
            option_type: 'call' or 'put'
            **kwargs: Additional arguments
        
        Returns:
            Plotly figure with subplots
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        strikes_grid, times_grid, greeks_grids = self._calculate_greeks_grid(
            option_type=option_type,
            **kwargs
        )
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Delta', 'Gamma', 'Vega', 'Theta'),
            specs=[[{'type': 'surface'}, {'type': 'surface'}],
                   [{'type': 'surface'}, {'type': 'surface'}]]
        )
        
        # Delta
        fig.add_trace(
            go.Surface(
                x=strikes_grid,
                y=times_grid,
                z=greeks_grids['delta'],
                colorscale='RdYlGn',
                showscale=False,
                name='Delta'
            ),
            row=1, col=1
        )
        
        # Gamma
        fig.add_trace(
            go.Surface(
                x=strikes_grid,
                y=times_grid,
                z=greeks_grids['gamma'],
                colorscale='Viridis',
                showscale=False,
                name='Gamma'
            ),
            row=1, col=2
        )
        
        # Vega
        fig.add_trace(
            go.Surface(
                x=strikes_grid,
                y=times_grid,
                z=greeks_grids['vega'],
                colorscale='Blues',
                showscale=False,
                name='Vega'
            ),
            row=2, col=1
        )
        
        # Theta
        fig.add_trace(
            go.Surface(
                x=strikes_grid,
                y=times_grid,
                z=greeks_grids['theta'],
                colorscale='Reds',
                showscale=False,
                name='Theta'
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title=f'Greeks Surfaces ({option_type.capitalize()})',
            height=900,
            width=1200,
            showlegend=False
        )
        
        return fig


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Greeks Surface Plotter - Self Test")
    print("=" * 70)
    
    if not PLOTLY_AVAILABLE:
        print("\n⚠️ Plotly not available")
        print("Install with: pip install plotly")
        print("\nSkipping visualization tests")
    else:
        # Initialize plotter
        plotter = GreeksSurfacePlotter(
            S0=100,
            r=0.05,
            sigma=0.25
        )
        
        print("\n📊 Generating Greeks surfaces...")
        print("(This may take a moment...)")
        
        # Test 1: Delta surface
        print("\n📊 Test 1: Delta Surface")
        delta_fig = plotter.plot_delta_surface(option_type='call')
        print("Delta surface generated (call delta_fig.show() to display)")
        
        # Test 2: Gamma surface
        print("\n📊 Test 2: Gamma Surface")
        gamma_fig = plotter.plot_gamma_surface(option_type='call')
        print("Gamma surface generated")
        
        # Test 3: All Greeks
        print("\n📊 Test 3: All Greeks")
        all_greeks_fig = plotter.plot_all_greeks(option_type='call')
        print("All Greeks surfaces generated")
        
        print("\n📊 Summary:")
        print("  3 visualizations created successfully")
        print("  To display: fig.show() or fig.write_html('filename.html')")
    
    print("\n" + "=" * 70)
    print("✅ Greeks surface plotter test complete!")
    print("=" * 70)
