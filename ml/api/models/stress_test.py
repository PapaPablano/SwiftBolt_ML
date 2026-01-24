"""Pydantic models for stress testing API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StressTestRequest(BaseModel):
    """Request model for stress testing."""

    positions: Dict[str, float] = Field(..., description="Position sizes (symbol -> quantity)")
    prices: Dict[str, float] = Field(..., description="Current prices (symbol -> price)")
    scenario: Optional[str] = Field(None, description="Historical scenario name")
    customShocks: Optional[Dict[str, float]] = Field(None, description="Custom price shocks (symbol -> shock %)")
    varLevel: Optional[float] = Field(0.95, description="VaR confidence level")


class PortfolioInfo(BaseModel):
    """Portfolio value information."""

    currentValue: float
    change: float
    changePercent: float


class RiskInfo(BaseModel):
    """Risk information."""

    varLevel: float
    varBreached: bool
    severity: str  # "low", "medium", "high", "critical"


class StressTestResponse(BaseModel):
    """Response model for stress testing."""

    scenario: Optional[str]
    portfolio: PortfolioInfo
    risk: RiskInfo
    positionChanges: Dict[str, float] = Field(..., description="Position changes (symbol -> change)")
    positions: Dict[str, float] = Field(..., description="Original positions (symbol -> quantity)")
    prices: Dict[str, float] = Field(..., description="Current prices (symbol -> price)")
    error: Optional[str] = None
