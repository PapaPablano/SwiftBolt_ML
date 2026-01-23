"""Pydantic models for Greeks surface API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class GreeksSurfaceRequest(BaseModel):
    """Request model for Greeks surface calculation."""
    
    symbol: str = Field(..., description="Stock ticker symbol")
    underlyingPrice: float = Field(..., description="Current underlying price")
    riskFreeRate: float = Field(default=0.05, description="Risk-free rate (annual)")
    volatility: float = Field(..., description="Volatility (annualized)")
    optionType: str = Field(default="call", description="Option type: 'call' or 'put'")
    strikeRange: Optional[List[float]] = Field(
        default=None,
        description="Strike range as [min_moneyness, max_moneyness]. Default: [0.7, 1.3]"
    )
    timeRange: Optional[List[float]] = Field(
        default=None,
        description="Time range as [min_years, max_years]. Default: [0.01, 1.0]"
    )
    nStrikes: int = Field(default=50, description="Number of strike points")
    nTimes: int = Field(default=50, description="Number of time points")
    greek: Optional[str] = Field(
        default=None,
        description="Specific Greek to plot: 'delta', 'gamma', 'theta', 'vega', 'rho', or None for all"
    )


class GreeksSurfaceData(BaseModel):
    """Greeks surface data point."""
    
    strike: float
    timeToMaturity: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class GreeksSurfaceResponse(BaseModel):
    """Response model for Greeks surface."""
    
    symbol: str
    underlyingPrice: float
    riskFreeRate: float
    volatility: float
    optionType: str
    strikes: List[float] = Field(..., description="Strike prices")
    times: List[float] = Field(..., description="Time to maturity (years)")
    delta: List[List[float]] = Field(..., description="Delta surface (2D grid)")
    gamma: List[List[float]] = Field(..., description="Gamma surface (2D grid)")
    theta: List[List[float]] = Field(..., description="Theta surface (2D grid)")
    vega: List[List[float]] = Field(..., description="Vega surface (2D grid)")
    rho: List[List[float]] = Field(..., description="Rho surface (2D grid)")
