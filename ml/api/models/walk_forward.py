"""Pydantic models for walk-forward optimization API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class WalkForwardRequest(BaseModel):
    """Request model for walk-forward optimization."""

    symbol: str = Field(..., description="Stock ticker symbol")
    horizon: str = Field(..., description="Forecast horizon (1D, 1W)")
    forecaster: str = Field(..., description="Forecaster type (baseline, enhanced)")
    timeframe: Optional[str] = Field("d1", description="Timeframe")
    trainWindow: Optional[int] = Field(None, description="Training window size (days)")
    testWindow: Optional[int] = Field(None, description="Test window size (days)")
    stepSize: Optional[int] = Field(None, description="Step size between windows (days)")


class WalkForwardMetrics(BaseModel):
    """Walk-forward performance metrics."""

    accuracy: float
    precision: float
    recall: float
    f1Score: float
    sharpeRatio: float
    sortinoRatio: float
    maxDrawdown: float
    winRate: float
    profitFactor: float
    totalTrades: int
    winningTrades: int
    losingTrades: int
    avgWinSize: float
    avgLossSize: float


class Period(BaseModel):
    """Time period information."""

    start: str
    end: str


class Windows(BaseModel):
    """Walk-forward windows information."""

    trainWindow: int
    testWindow: int
    stepSize: int
    testPeriods: List[Period]


class WalkForwardResponse(BaseModel):
    """Response model for walk-forward optimization."""

    symbol: str
    horizon: str
    forecaster: str
    timeframe: str
    period: Period
    windows: Windows
    metrics: WalkForwardMetrics
    barsUsed: int
    error: Optional[str] = None
