"""Router for volatility surface endpoint."""

import logging
import sys
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException

from api.models.volatility_surface import (
    VolatilitySurfaceRequest,
    VolatilitySurfaceResponse,
)

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

# Import from models and visualization
from src.models.volatility_surface import VolatilitySurface
from src.visualization.volatility_surfaces import VolatilitySurfacePlotter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/volatility-surface", response_model=VolatilitySurfaceResponse)
async def get_volatility_surface(request: VolatilitySurfaceRequest):
    """
    Calculate and return volatility surface data for visualization.
    
    Fits a volatility surface from provided slices and returns 3D surface data.
    """
    try:
        # Create volatility surface
        surface = VolatilitySurface()
        
        # Add slices
        for slice_data in request.slices:
            T = slice_data.maturityDays / 365.0  # Convert to years
            surface.add_slice(
                T=T,
                strikes=np.array(slice_data.strikes),
                vols=np.array(slice_data.impliedVols),  # Note: method expects 'vols' not 'implied_vols'
                F=slice_data.forwardPrice
            )
        
        # Fit surface
        surface.fit()
        
        if not surface.surface_fitted:
            raise HTTPException(
                status_code=400,
                detail="Failed to fit volatility surface. Check input data."
            )
        
        # Get ranges (convert maturity from years to days)
        strike_min, strike_max = surface.strike_range
        mat_min_years, mat_max_years = surface.maturity_range
        mat_min = mat_min_years * 365.0
        mat_max = mat_max_years * 365.0
        
        # Create grid for surface
        strikes = np.linspace(strike_min, strike_max, request.nStrikes)
        maturities_days = np.linspace(mat_min, mat_max, request.nMaturities)
        maturities_years = maturities_days / 365.0
        
        # Calculate implied vols on grid
        iv_grid = np.zeros((len(maturities_years), len(strikes)))
        
        for i, T in enumerate(maturities_years):
            for j, K in enumerate(strikes):
                iv_grid[i, j] = surface.get_volatility(K, T)
        
        # Convert to percentages and lists
        iv_grid_percent = (iv_grid * 100).tolist()
        
        return VolatilitySurfaceResponse(
            symbol=request.symbol.upper(),
            strikes=strikes.tolist(),
            maturities=maturities_days.tolist(),
            impliedVols=iv_grid_percent,
            strikeRange=[float(strike_min), float(strike_max)],
            maturityRange=[float(mat_min), float(mat_max)]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating volatility surface: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
