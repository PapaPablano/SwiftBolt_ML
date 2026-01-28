"""Models for Support and Resistance API responses."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PivotLevel(BaseModel):
    """A single pivot level."""
    period: int
    level_high: Optional[float]
    level_low: Optional[float]
    high_status: Optional[str]
    low_status: Optional[str]


class PolynomialLevel(BaseModel):
    """Polynomial regression S/R level."""
    level: float
    slope: float
    trend: str  # 'rising', 'falling', 'flat'
    forecast: Optional[List[float]]


class LogisticLevel(BaseModel):
    """Logistic regression S/R level."""
    level: float
    probability: float
    times_respected: int


class SRSignal(BaseModel):
    """Trading signal from S/R indicator."""
    signal: str  # e.g., 'support_retest', 'resistance_break'
    level: float
    confirmation: Optional[str]


class SupportResistanceResponse(BaseModel):
    """Complete support and resistance analysis."""
    symbol: str
    current_price: float
    last_updated: Optional[str]

    # Summary metrics
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]
    support_distance_pct: Optional[float]
    resistance_distance_pct: Optional[float]
    bias: Optional[str]  # 'bullish', 'bearish', 'neutral'

    # Indicator details
    pivot_levels: List[PivotLevel]
    polynomial_support: Optional[PolynomialLevel]
    polynomial_resistance: Optional[PolynomialLevel]
    logistic_supports: List[LogisticLevel]
    logistic_resistances: List[LogisticLevel]

    # All collected levels
    all_supports: List[float]
    all_resistances: List[float]

    # Active signals
    signals: List[SRSignal]

    # Raw indicator output for extensibility
    raw_indicators: Dict[str, Any] = {}


class SupportResistanceError(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str]
