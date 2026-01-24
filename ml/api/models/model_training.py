"""Pydantic models for model training API."""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class ModelTrainingRequest(BaseModel):
    """Request model for model training."""
    
    symbol: str = Field(..., description="Stock ticker symbol")
    timeframe: Optional[str] = Field(default="d1", description="Timeframe (d1, h1, etc.)")
    lookbackDays: Optional[int] = Field(default=90, description="Number of days of historical data to use")


class TrainingMetrics(BaseModel):
    """Training metrics."""
    
    trainAccuracy: float = Field(..., description="Training accuracy")
    validationAccuracy: float = Field(..., description="Validation accuracy")
    testAccuracy: float = Field(..., description="Test accuracy")
    trainSamples: int = Field(..., description="Number of training samples")
    validationSamples: int = Field(..., description="Number of validation samples")
    testSamples: int = Field(..., description="Number of test samples")


class ModelInfo(BaseModel):
    """Model information."""
    
    modelHash: str = Field(..., description="Model hash/version")
    featureCount: int = Field(..., description="Number of features")
    trainedAt: str = Field(..., description="Training timestamp")


class ModelTrainingResponse(BaseModel):
    """Response model for model training."""
    
    symbol: str
    timeframe: str
    lookbackDays: int
    status: str
    trainingMetrics: TrainingMetrics
    modelInfo: ModelInfo
    ensembleWeights: Dict[str, float] = Field(default_factory=dict)
    featureImportance: Dict[str, float] = Field(default_factory=dict)
