"""Pydantic models for forecast quality API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class QualityIssue(BaseModel):
    """Forecast quality issue."""
    
    level: str = Field(..., description="Issue level (warning, info, error)")
    type: str = Field(..., description="Issue type")
    message: str = Field(..., description="Issue message")
    action: str = Field(..., description="Recommended action")


class ForecastQualityRequest(BaseModel):
    """Request model for forecast quality."""
    
    symbol: str = Field(..., description="Stock ticker symbol")
    horizon: Optional[str] = Field(default="1D", description="Forecast horizon (1D, 1W, etc.)")
    timeframe: Optional[str] = Field(default="d1", description="Timeframe (d1, h1, etc.)")


class ForecastQualityResponse(BaseModel):
    """Response model for forecast quality."""
    
    symbol: str
    horizon: str
    timeframe: str
    qualityScore: float = Field(..., description="Overall quality score (0-1)")
    confidence: float = Field(..., description="Forecast confidence")
    modelAgreement: float = Field(..., description="Model agreement score")
    issues: List[QualityIssue] = Field(default_factory=list)
    timestamp: str
