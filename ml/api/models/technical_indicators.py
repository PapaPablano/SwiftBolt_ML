"""Pydantic models for technical indicators API."""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class TechnicalIndicatorsResponse(BaseModel):
    """Response model for technical indicators."""

    symbol: str
    timeframe: str
    timestamp: str
    indicators: Dict[str, Optional[float]] = Field(..., description="Technical indicator values")
    price: Dict[str, float] = Field(..., description="Latest OHLC price data")
    bars_used: int = Field(..., description="Number of bars used for calculation")
    cached: Optional[bool] = None
    error: Optional[str] = None
