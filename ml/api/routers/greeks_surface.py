"""Router for Greeks surface endpoint."""

import logging
import sys
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException

from api.models.greeks_surface import GreeksSurfaceRequest, GreeksSurfaceResponse

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

# Import from visualization directory
from src.visualization.greeks_surfaces import GreeksSurfacePlotter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/greeks-surface", response_model=GreeksSurfaceResponse)
async def get_greeks_surface(request: GreeksSurfaceRequest):
    """
    Calculate and return Greeks surface data for visualization.
    
    Returns 3D surface data for all Greeks (delta, gamma, theta, vega, rho)
    across strike prices and time to maturity.
    """
    try:
        # Set defaults for strike and time ranges
        strike_range = request.strikeRange or [0.7, 1.3]
        time_range = request.timeRange or [0.01, 1.0]
        
        # Create plotter
        plotter = GreeksSurfacePlotter(
            S0=request.underlyingPrice,
            r=request.riskFreeRate,
            sigma=request.volatility
        )
        
        # Calculate Greeks grid
        strikes_grid, times_grid, greeks_grids = plotter._calculate_greeks_grid(
            strike_range=tuple(strike_range),
            time_range=tuple(time_range),
            n_strikes=request.nStrikes,
            n_times=request.nTimes,
            option_type=request.optionType
        )
        
        # Convert numpy arrays to lists for JSON serialization
        # Extract unique strikes and times (from grid)
        strikes = strikes_grid[0, :].tolist()  # First row has all strikes
        times = times_grid[:, 0].tolist()  # First column has all times
        
        # Convert 2D grids to lists
        delta = greeks_grids['delta'].tolist()
        gamma = greeks_grids['gamma'].tolist()
        theta = greeks_grids['theta'].tolist()
        vega = greeks_grids['vega'].tolist()
        rho = greeks_grids['rho'].tolist()
        
        return GreeksSurfaceResponse(
            symbol=request.symbol.upper(),
            underlyingPrice=request.underlyingPrice,
            riskFreeRate=request.riskFreeRate,
            volatility=request.volatility,
            optionType=request.optionType,
            strikes=strikes,
            times=times,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho
        )
        
    except Exception as e:
        logger.error(f"Error calculating Greeks surface: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
