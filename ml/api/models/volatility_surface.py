"""Pydantic models for volatility surface API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class VolatilitySurfaceSlice(BaseModel):
    """A single volatility slice (for a specific maturity)."""
    
    maturityDays: float = Field(..., description="Maturity in days")
    strikes: List[float] = Field(..., description="Strike prices")
    impliedVols: List[float] = Field(..., description="Implied volatilities (as decimals, e.g., 0.25 for 25%)")
    forwardPrice: Optional[float] = Field(default=None, description="Forward price")


class VolatilitySurfaceRequest(BaseModel):
    """Request model for volatility surface calculation."""
    
    symbol: str = Field(..., description="Stock ticker symbol")
    slices: List[VolatilitySurfaceSlice] = Field(..., description="Volatility slices to fit")
    nStrikes: int = Field(default=50, description="Number of strike points for surface")
    nMaturities: int = Field(default=30, description="Number of maturity points for surface")


class VolatilitySurfaceResponse(BaseModel):
    """Response model for volatility surface."""
    
    symbol: str
    strikes: List[float] = Field(..., description="Strike prices")
    maturities: List[float] = Field(..., description="Maturities in days")
    impliedVols: List[List[float]] = Field(..., description="Implied volatility surface (2D grid, as percentages)")
    strikeRange: List[float] = Field(..., description="Strike range [min, max]")
    maturityRange: List[float] = Field(..., description="Maturity range [min_days, max_days]")
