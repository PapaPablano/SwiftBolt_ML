"""Pydantic models for portfolio optimization API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PortfolioOptimizeRequest(BaseModel):
    """Request model for portfolio optimization."""

    symbols: List[str] = Field(..., description="List of stock ticker symbols")
    method: str = Field(..., description="Optimization method (max_sharpe, min_variance, risk_parity, efficient)")
    lookbackDays: Optional[int] = Field(252, description="Lookback period in days")
    riskFreeRate: Optional[float] = Field(0.02, description="Risk-free rate")
    targetReturn: Optional[float] = Field(None, description="Target return (required for efficient method)")
    minWeight: Optional[float] = Field(0.0, description="Minimum weight per asset")
    maxWeight: Optional[float] = Field(1.0, description="Maximum weight per asset")


class PortfolioAllocation(BaseModel):
    """Portfolio allocation results."""

    weights: Dict[str, float] = Field(..., description="Asset weights (symbol -> weight)")
    expectedReturn: float
    volatility: float
    sharpeRatio: float


class OptimizationParameters(BaseModel):
    """Optimization parameters used."""

    riskFreeRate: float
    minWeight: float
    maxWeight: float
    targetReturn: Optional[float] = None


class PortfolioOptimizeResponse(BaseModel):
    """Response model for portfolio optimization."""

    symbols: List[str]
    method: str
    timeframe: str
    lookbackDays: int
    allocation: PortfolioAllocation
    parameters: OptimizationParameters
    error: Optional[str] = None
