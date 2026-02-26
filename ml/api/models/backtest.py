"""Pydantic models for backtesting API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    """Request model for backtesting."""

    symbol: str = Field(..., description="Stock ticker symbol")
    strategy: str = Field(..., description="Strategy name (supertrend_ai, sma_crossover, buy_and_hold)")
    startDate: str = Field(..., description="Start date (YYYY-MM-DD)")
    endDate: str = Field(..., description="End date (YYYY-MM-DD)")
    timeframe: Optional[str] = Field("d1", description="Timeframe")
    initialCapital: Optional[float] = Field(10000, description="Initial capital")
    params: Optional[Dict[str, Any]] = Field(None, description="Strategy-specific parameters")


class EquityPoint(BaseModel):
    """Equity curve data point."""

    date: str
    value: float


class Trade(BaseModel):
    """Trade record."""

    date: str
    symbol: str
    action: str
    quantity: int
    price: float
    pnl: Optional[float] = None
    entryPrice: Optional[float] = None
    exitPrice: Optional[float] = None
    duration: Optional[float] = None  # e.g. bars or days
    fees: Optional[float] = None


class BacktestMetrics(BaseModel):
    """Backtest performance metrics."""

    sharpeRatio: Optional[float] = None
    maxDrawdown: Optional[float] = None
    winRate: Optional[float] = None
    totalTrades: int
    profitFactor: Optional[float] = None
    averageTrade: Optional[float] = None
    cagr: Optional[float] = None


class BacktestResponse(BaseModel):
    """Response model for backtesting."""

    symbol: str
    strategy: str
    period: Dict[str, str]
    initialCapital: float
    finalValue: float
    totalReturn: float
    metrics: BacktestMetrics
    equityCurve: List[EquityPoint]
    trades: List[Trade]
    barsUsed: int
    error: Optional[str] = None


class StrategyBacktestResultsResponse(BaseModel):
    """Response for GET /strategy-backtest-results (stored job result from DB)."""

    jobId: str
    status: str
    symbol: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    metrics: Dict[str, Any]
    trades: List[Dict[str, Any]]
    equityCurve: List[Dict[str, Any]]
    error: Optional[str] = None
