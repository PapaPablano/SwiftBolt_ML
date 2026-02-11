"""
PHASE 3: Model Loading & Inference
"""

import pickle
import os
import joblib
from pathlib import Path
import logging
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Any
import os
import yaml
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from main_production_system.core.hybrid_ensemble import HybridEnsemble
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error

try:
    from xgboost import XGBRegressor

    XGB_AVAILABLE = True
except Exception:
    XGB_AVAILABLE = False

# Import Perplexity Pipeline for market intelligence enrichment
try:
    from main_production_system.connectors.perplexity_connector import (
        PerplexityConnector,
    )

    PERPLEXITY_AVAILABLE = True
except ImportError:
    PERPLEXITY_AVAILABLE = False

# Import monitoring (optional - fails gracefully if not available)
try:
    from main_production_system.monitoring.ml_model_monitor import MLModelMonitor

    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    logger.debug("[MODEL_MANAGER] ML monitoring not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Version info
try:
    from main_production_system import __version__

    SYSTEM_VERSION = __version__
except ImportError:
    SYSTEM_VERSION = "2.0.0"


def load_xgboost_model():
    """Robust model loading with multiple fallback paths and enhanced logging"""
    import os
    from pathlib import Path

    # Get absolute workspace path
    workspace_root = Path(__file__).parent.parent.parent.parent.absolute()

    candidate_paths = [
        "main_production_system/models/xgboost_advanced_directional_model.pkl",
        "./main_production_system/models/xgboost_advanced_directional_model.pkl",
        "../main_production_system/models/xgboost_advanced_directional_model.pkl",
        "models/xgboost_advanced_directional_model.pkl",
        str(
            workspace_root
            / "main_production_system"
            / "models"
            / "xgboost_advanced_directional_model.pkl"
        ),
        str(workspace_root / "models" / "xgboost_advanced_directional_model.pkl"),
    ]

    # Add absolute path if workspace is known
    if "ericpeterson" in str(workspace_root):
        candidate_paths.append(
            str(
                workspace_root
                / "main_production_system"
                / "models"
                / "xgboost_advanced_directional_model.pkl"
            )
        )

    logger.info(
        f"[MODEL] Attempting to load XGBoost from {len(candidate_paths)} candidate paths"
    )

    for path in candidate_paths:
        # Resolve path
        resolved_path = Path(path).resolve()
        if resolved_path.exists():
            try:
                logger.info(f"[MODEL] Found model at: {resolved_path}")
                with open(resolved_path, "rb") as f:
                    model = pickle.load(f)

                # Validate model
                if not hasattr(model, "predict"):
                    logger.error(
                        f"[MODEL] Model at {resolved_path} missing predict() method"
                    )
                    continue

                logger.info(
                    f"[MODEL] ✅ Successfully loaded XGBoost model from {resolved_path}"
                )
                logger.info(f"[MODEL] Model type: {type(model).__name__}")
                if hasattr(model, "n_features_in_"):
                    logger.info(f"[MODEL] Expected features: {model.n_features_in_}")

                return model
            except Exception as e:
                logger.warning(f"[MODEL] Load failed from {resolved_path}: {e}")
                continue
        else:
            logger.debug(f"[MODEL] Path does not exist: {resolved_path}")

    logger.error(
        f"[MODEL] ❌ XGBoost model not found in any of {len(candidate_paths)} paths"
    )
    logger.error(f"[MODEL] Searched in workspace: {workspace_root}")
    return None


def _log_with_context(level: str, message: str, **kwargs):
    """
    Enhanced logging with ISO 8601 timestamps and context.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message
        **kwargs: Additional context to include in message
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")

    context_parts = []
    if kwargs:
        context = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        context_parts.append(context)
    context_parts.append(f"version={SYSTEM_VERSION}")

    if context_parts:
        context_str = " | " + " | ".join(context_parts)
    else:
        context_str = ""

    full_message = f"[{timestamp}]{context_str} {message}"

    if level == "DEBUG":
        logger.debug(full_message)
    elif level == "INFO":
        logger.info(full_message)
    elif level == "WARNING":
        logger.warning(full_message)
    elif level == "ERROR":
        logger.error(full_message)


# Import Kaggle-Prophet Hybrid
try:
    from core.kaggle_hybrid_with_prophet import KaggleProphetHybrid

    KAGGLE_HYBRID_AVAILABLE = True
except ImportError as e:
    logger.warning(f"KaggleProphetHybrid not available: {e}")
    KAGGLE_HYBRID_AVAILABLE = False


def _get_model_path(model_name: str = "xgboost") -> Path:
    """
    Get model path from environment variable, config file, or default.

    Priority order:
    1. MODEL_PATH environment variable
    2. config/model_config.yaml
    3. Default hardcoded path

    Args:
        model_name: Name of the model (xgboost, ensemble, etc.)

    Returns:
        Path object pointing to model file
    """
    # Check environment variable first
    env_path = os.getenv("MODEL_PATH")
    if env_path:
        model_path = Path(env_path)
        if model_path.exists():
            logger.info(f"[CONFIG] Using MODEL_PATH from environment: {model_path}")
            return model_path
        else:
            logger.warning(
                f"[CONFIG] MODEL_PATH from environment does not exist: {model_path}"
            )

    # Check config file
    config_path = Path("main_production_system/config/model_config.yaml")
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                if config and "models" in config:
                    model_config = config["models"].get(model_name, {})
                    if model_config and "path" in model_config:
                        config_model_path = Path(model_config["path"])
                        if config_model_path.exists():
                            logger.info(
                                f"[CONFIG] Using model path from config file: {config_model_path}"
                            )
                            return config_model_path
                        else:
                            logger.warning(
                                f"[CONFIG] Model path from config does not exist: {config_model_path}"
                            )
        except Exception as e:
            logger.warning(f"[CONFIG] Failed to read config file {config_path}: {e}")

    # Default fallback - search multiple candidate paths
    workspace_root = Path(__file__).parent.parent.parent.parent.absolute()
    candidate_paths = [
        "main_production_system/models/xgboost_advanced_directional_model.pkl",
        "./main_production_system/models/xgboost_advanced_directional_model.pkl",
        "models/xgboost_advanced_directional_model.pkl",
        str(
            workspace_root
            / "main_production_system"
            / "models"
            / "xgboost_advanced_directional_model.pkl"
        ),
        str(workspace_root / "models" / "xgboost_advanced_directional_model.pkl"),
        "./xgboost_tuned_model.pkl",  # Legacy path
    ]

    # Add absolute path if workspace is known
    if "ericpeterson" in str(workspace_root) or "Attention-Based" in str(
        workspace_root
    ):
        candidate_paths.append(
            "/Users/ericpeterson/Attention-Based Multi-Timeframe-Transformer/main_production_system/models/xgboost_advanced_directional_model.pkl"
        )

    logger.info(
        f"[CONFIG] Searching {len(candidate_paths)} candidate paths for model..."
    )

    for path in candidate_paths:
        p = Path(path)
        if p.exists():
            logger.info(f"[CONFIG] Found model at: {p}")
            return p

    # If none found, return the first as default (for error message)
    default_path = Path(candidate_paths[0])
    logger.warning(
        f"[CONFIG] Model not found in any candidate path, using default: {default_path}"
    )
    return default_path


def _load_with_timeout(func, timeout_seconds: int = 30, *args, **kwargs):
    """
    Execute a function with timeout protection.

    Args:
        func: Function to execute
        timeout_seconds: Maximum time to wait
        *args, **kwargs: Arguments to pass to function

    Returns:
        Function result or None if timeout
    """
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        logger.error(f"[MODEL] ⏱️ Timeout after {timeout_seconds}s loading model")
        return None
    except Exception as e:
        logger.error(f"[MODEL] Error during timeout-protected load: {e}")
        raise


@st.cache_resource
def load_ml_models() -> dict:
    """
    Centralized model loading with fallback chain.
    Models are cached at session level using @st.cache_resource.
    Persists for entire app session.

    Returns:
        {
            'xgboost': Loaded XGBoost model or None,
            'ensemble': Initialized HybridEnsemble or None,
            'status': {'xgboost': 'Ready'/'Failed', 'ensemble': 'Ready'/'Failed'}
        }
    """

    models = {}
    status = {}

    # Load XGBoost with timeout protection
    def _load_xgboost():
        """Helper function to load XGBoost model."""
        # Try robust loader first
        xgb_model = load_xgboost_model()
        if xgb_model is not None:
            if not hasattr(xgb_model, "predict"):
                raise ValueError("XGBoost model missing predict() method")
            return xgb_model

        # Fallback to configured path resolution
        model_path = _get_model_path("xgboost")
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path.absolute()}. "
                f"To fix: ensure the model file exists, or set MODEL_PATH environment variable, "
                f"or configure in main_production_system/config/model_config.yaml"
            )
        logger.info(f"[MODEL] Loading XGBoost from {model_path.absolute()}...")
        with open(model_path, "rb") as f:
            xgb_model = pickle.load(f)
        if not hasattr(xgb_model, "predict"):
            raise ValueError("XGBoost model missing predict() method")
        return xgb_model

    try:
        xgb_model = _load_with_timeout(_load_xgboost, timeout_seconds=30)
        if xgb_model is None:
            raise TimeoutError("XGBoost model loading timed out after 30 seconds")
        models["xgboost"] = xgb_model
        status["xgboost"] = "Ready"
        logger.info(f"[MODEL] ✅ XGBoost loaded: {type(xgb_model).__name__}")
        # Debug: model availability and expected input size
        try:
            logger.info(f"XGBoost model loaded: {xgb_model is not None}")
            if hasattr(xgb_model, "n_features_in_"):
                logger.info(f"Model input features: {xgb_model.n_features_in_}")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"[MODEL] ❌ XGBoost load failed: {e}")
        models["xgboost"] = None
        error_msg = str(e)[:100]  # Limit error message length
        status["xgboost"] = f"Failed: {error_msg}"

    # Load Kaggle-Prophet Hybrid (new elite model) with timeout protection
    if KAGGLE_HYBRID_AVAILABLE:

        def _load_kaggle_prophet_hybrid():
            """Helper function to load Kaggle-Prophet Hybrid model."""
            from main_production_system.core.kaggle_hybrid_with_prophet import (
                KaggleProphetHybrid,
            )

            return KaggleProphetHybrid(
                prophet_regressors=["rsi", "macd"],
                use_uncertainty_intervals=True,
                enable_multiscale=True,
            )

        try:
            logger.info(f"[MODEL] Initializing Kaggle-Prophet Hybrid...")
            kaggle_prophet_hybrid = _load_with_timeout(
                _load_kaggle_prophet_hybrid, timeout_seconds=45
            )
            if kaggle_prophet_hybrid is None:
                raise TimeoutError(
                    "Kaggle-Prophet Hybrid initialization timed out after 45 seconds"
                )
            models["kaggle_prophet_hybrid"] = kaggle_prophet_hybrid
            status["kaggle_prophet_hybrid"] = "Ready"
            logger.info(f"[MODEL] ✅ Kaggle-Prophet Hybrid initialized")
        except Exception as e:
            logger.error(f"[MODEL] ❌ Kaggle-Prophet Hybrid initialization failed: {e}")
            models["kaggle_prophet_hybrid"] = None
            error_msg = str(e)[:100]
            status["kaggle_prophet_hybrid"] = f"Failed: {error_msg}"

    # Load HybridEnsemble (legacy) with timeout protection
    def _load_ensemble():
        """Helper function to load HybridEnsemble model."""
        ensemble = HybridEnsemble()
        model_path = _get_model_path("xgboost")  # Use same path as XGBoost
        try:
            ensemble.load_models(str(model_path))
            logger.info(
                f"[MODEL] Ensemble loaded pre-trained weights from {model_path}"
            )
        except Exception as e:
            logger.warning(f"[MODEL] Ensemble weights load failed: {e}, using defaults")
        if not hasattr(ensemble, "predict"):
            raise ValueError("HybridEnsemble missing predict() method")
        return ensemble

    try:
        logger.info(f"[MODEL] Initializing HybridEnsemble...")
        ensemble = _load_with_timeout(_load_ensemble, timeout_seconds=30)
        if ensemble is None:
            raise TimeoutError(
                "HybridEnsemble initialization timed out after 30 seconds"
            )
        models["ensemble"] = ensemble
        status["ensemble"] = "Ready"
        logger.info(f"[MODEL] ✅ HybridEnsemble initialized: {type(ensemble).__name__}")
    except Exception as e:
        logger.error(f"[MODEL] ❌ Ensemble initialization failed: {e}")
        models["ensemble"] = None
        error_msg = str(e)[:100]
        status["ensemble"] = f"Failed: {error_msg}"

    # Load ES market regime model if available
    es_model = None
    es_path = Path("main_production_system/models") / "market_regime_garch.pkl"
    if es_path.exists():
        try:
            with open(es_path, "rb") as f:
                es_data = pickle.load(f)
            es_model = es_data.get("model")
            if es_model is not None:
                logger.info("✅ ES market regime GARCH loaded")
                models["es_market"] = es_model
                status["es_market"] = "Ready"
            else:
                logger.warning("ES model data missing model key")
                models["es_market"] = None
                status["es_market"] = "Failed: Model key missing"
        except Exception as e:
            logger.warning(f"ES load failed: {e}")
            models["es_market"] = None
            status["es_market"] = f"Failed: {str(e)[:50]}"

    # Load individual stock ARIMA-GARCH models
    arima_garch_models = {}
    models_dir = Path("main_production_system/models")
    stock_symbols = [
        "CRWD",
        "AAPL",
        "SPY",
        "MSFT",
        "TSLA",
        "QQQ",
        "NVDA",
    ]  # Common symbols

    for symbol in stock_symbols:
        arima_path = models_dir / f"arima_garch_{symbol}_trained.pkl"
        if arima_path.exists():
            try:
                with open(arima_path, "rb") as f:
                    arima_data = pickle.load(f)
                arima_model = arima_data.get("model")
                if arima_model is not None:
                    arima_garch_models[symbol] = arima_model
                    logger.info(f"✅ ARIMA-GARCH model loaded for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to load ARIMA-GARCH model for {symbol}: {e}")

    models["arima_garch_models"] = arima_garch_models
    if arima_garch_models:
        status["arima_garch"] = f"Loaded {len(arima_garch_models)} models"
        logger.info(f"✅ Loaded {len(arima_garch_models)} ARIMA-GARCH stock models")
    else:
        status["arima_garch"] = "No models found"
        logger.info("No ARIMA-GARCH stock models found (will train on demand)")

    if es_model is None:
        logger.info(f"ES market model not found at {es_path}")
        models["es_market"] = None
        status["es_market"] = "Not available"

    # Initialize Perplexity connector
    try:
        from main_production_system.data_sources.perplexity_service import (
            PerplexityService,
        )

        perplexity_conn = PerplexityService()
        models["perplexity"] = perplexity_conn
        status["perplexity"] = "Ready"
        logger.info("✅ Perplexity connector initialized")
    except Exception as e:
        logger.warning(f"Perplexity initialization failed: {e}")
        models["perplexity"] = None
        status["perplexity"] = f"Failed: {str(e)[:50]}"

    models["status"] = status
    logger.info(f"[MODEL] 📊 Session Status: {status}")
    return models


def get_model_status(models_dict: dict) -> dict:
    xgb_ready = models_dict.get("xgboost") is not None
    ensemble_ready = models_dict.get("ensemble") is not None
    models_loaded = int(xgb_ready) + int(ensemble_ready)
    if models_loaded == 2:
        message = "✅ All models ready"
    elif models_loaded == 1:
        message = f"⚠️ Partial: {[k for k,v in [('XGBoost',xgb_ready), ('Ensemble',ensemble_ready)] if v]}"
    else:
        message = "❌ No models available"
    return {
        "models_loaded": models_loaded,
        "xgboost_ready": xgb_ready,
        "ensemble_ready": ensemble_ready,
        "inference_available": ensemble_ready,
        "message": message,
        "status": models_dict.get("status", {}),
    }


def prepare_features_for_inference(
    df_features: pd.DataFrame,
    drop_ohlcv: bool = True,
    export_matrix: bool = False,
    export_dir: Optional[str] = None,
) -> pd.DataFrame:
    """
    Enhanced feature preparation for inference with comprehensive NaN handling and logging.

    Ensures all columns passed to models are free of NaNs through multi-stage imputation:
    1. Forward/backward fill (preserves temporal patterns)
    2. Column medians (robust to outliers)
    3. Zero fill (final safeguard)

    Args:
        df_features: Input DataFrame with features
        drop_ohlcv: Whether to drop OHLCV columns
        export_matrix: Whether to export feature matrix for debugging (if model inference fails)
        export_dir: Directory to export feature matrix (default: data/cache/debug)

    Returns:
        DataFrame with NaN-free features ready for model inference
    """
    _log_with_context(
        "INFO",
        "[INFERENCE] Starting feature preparation",
        rows=len(df_features),
        columns=len(df_features.columns),
    )
    logger.info(f"[INFERENCE] Preparing features for inference: {df_features.shape}...")

    df_prep = df_features.copy()

    # Store pre-processing stats
    pre_stats = {
        "initial_rows": len(df_prep),
        "initial_columns": len(df_prep.columns),
        "initial_nan_count": df_prep.isna().sum().sum(),
        "columns_with_nan": df_prep.columns[df_prep.isna().any()].tolist(),
    }

    # Step 1: Drop Date column
    if "Date" in df_prep.columns:
        df_prep = df_prep.drop("Date", axis=1)
        _log_with_context("DEBUG", "[INFERENCE] Dropped Date column")
        logger.info(f"[INFERENCE] Dropped Date column")

    # Step 2: Drop OHLCV if requested
    if drop_ohlcv:
        ohlcv_cols = ["Open", "High", "Low", "Close", "Volume"]
        cols_to_drop = [c for c in ohlcv_cols if c in df_prep.columns]
        if cols_to_drop:
            df_prep = df_prep.drop(cols_to_drop, axis=1)
            _log_with_context(
                "DEBUG", f"[INFERENCE] Dropped OHLCV columns: {cols_to_drop}"
            )
            logger.info(f"[INFERENCE] Dropped OHLCV columns: {cols_to_drop}")

    # Step 3: Pre-imputation NaN analysis
    initial_rows = len(df_prep)
    initial_nan = df_prep.isna().sum().sum()
    nan_by_column = df_prep.isna().sum().to_dict()
    high_nan_columns = {
        col: count for col, count in nan_by_column.items() if count > initial_rows * 0.1
    }

    _log_with_context(
        "INFO",
        "[INFERENCE] Pre-imputation NaN analysis",
        total_nan=initial_nan,
        columns_with_nan=len([c for c in nan_by_column.values() if c > 0]),
        high_nan_count=len(high_nan_columns),
    )

    if initial_nan > 0:
        logger.warning(
            f"[INFERENCE] Found {initial_nan} NaN values in {initial_rows} rows"
        )

        if high_nan_columns:
            logger.warning(f"[INFERENCE] High NaN columns (>10%): {high_nan_columns}")

        # Stage 1: Forward/backward fill (preserves temporal patterns)
        _log_with_context("INFO", "[INFERENCE] Stage 1/3: Forward/backward fill")
        df_prep = df_prep.ffill().bfill()
        stage1_nan = df_prep.isna().sum().sum()
        stage1_reduced = initial_nan - stage1_nan

        _log_with_context(
            "INFO",
            f"[INFERENCE] After forward/backward fill: {stage1_nan} NaN remaining (reduced by {stage1_reduced})",
        )
        logger.info(
            f"[INFERENCE] After forward/backward fill: {stage1_nan} NaN remaining (reduced by {stage1_reduced})"
        )

        # Stage 2: Column medians (robust for tails)
        if stage1_nan > 0:
            _log_with_context("INFO", "[INFERENCE] Stage 2/3: Column median imputation")
            medians = df_prep.median(numeric_only=True)
            medians_dict = medians.to_dict()

            # Fill NaN with medians
            df_prep = df_prep.fillna(medians)
            stage2_nan = df_prep.isna().sum().sum()
            stage2_reduced = stage1_nan - stage2_nan

            _log_with_context(
                "INFO",
                f"[INFERENCE] After median fill: {stage2_nan} NaN remaining (reduced by {stage2_reduced})",
                median_imputed=len([v for v in medians_dict.values() if pd.notna(v)]),
            )
            logger.info(
                f"[INFERENCE] After median fill: {stage2_nan} NaN remaining (reduced by {stage2_reduced})"
            )

        # Stage 3: Zero fill (final safeguard)
        if stage2_nan > 0:
            _log_with_context(
                "WARNING",
                f"[INFERENCE] Stage 3/3: Zero fill (fallback) - {stage2_nan} NaN remaining",
            )
            logger.warning(
                f"[INFERENCE] Still {stage2_nan} NaN after median fill; filling remaining with 0"
            )
            df_prep = df_prep.fillna(0)

        # Final verification
        final_nan = df_prep.isna().sum().sum()
        if final_nan > 0:
            _log_with_context(
                "ERROR",
                f"[INFERENCE] CRITICAL: {final_nan} NaN values remain after all imputation stages!",
            )
            logger.error(
                "[INFERENCE] CRITICAL: NaNs remain after all imputations; replacing with 0"
            )
            df_prep = df_prep.fillna(0)
            final_nan = df_prep.isna().sum().sum()

        if final_nan == 0:
            _log_with_context(
                "INFO", "[INFERENCE] ✅ All NaN values successfully imputed"
            )
            logger.info(f"[INFERENCE] ✅ All NaN values successfully imputed")
    else:
        _log_with_context("INFO", "[INFERENCE] ✅ No NaN values found - features ready")
        logger.info(f"[INFERENCE] ✅ No NaN values found - features ready")

    # Post-imputation stats
    post_stats = {
        "final_rows": len(df_prep),
        "final_columns": len(df_prep.columns),
        "final_nan_count": df_prep.isna().sum().sum(),
        "imputation_stages_applied": initial_nan > 0,
    }

    # Log comprehensive stats
    _log_with_context(
        "INFO",
        "[INFERENCE] Feature preparation complete",
        pre_nan=pre_stats["initial_nan_count"],
        post_nan=post_stats["final_nan_count"],
        rows_retained=post_stats["final_rows"],
        columns_final=post_stats["final_columns"],
    )

    logger.info(f"[INFERENCE] ✅ Prepared: {df_prep.shape} (was {df_features.shape})")
    logger.info(
        f"[INFERENCE] Pre-imputation: {pre_stats['initial_nan_count']} NaN | Post-imputation: {post_stats['final_nan_count']} NaN"
    )

    # Optional: Export feature matrix for debugging
    if export_matrix:
        try:
            if export_dir is None:
                export_dir = Path("data/cache/debug")
            else:
                export_dir = Path(export_dir)

            export_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = export_dir / f"inference_features_{timestamp}.parquet"

            df_prep.to_parquet(export_path)
            _log_with_context(
                "INFO",
                f"[INFERENCE] Exported feature matrix for debugging: {export_path}",
            )
            logger.info(
                f"[INFERENCE] Exported feature matrix for debugging: {export_path}"
            )
        except Exception as e:
            _log_with_context(
                "WARNING", f"[INFERENCE] Failed to export feature matrix: {str(e)}"
            )
            logger.warning(f"[INFERENCE] Failed to export feature matrix: {e}")

    # Final validation: ensure no NaNs
    if df_prep.isna().sum().sum() > 0:
        _log_with_context(
            "ERROR", "[INFERENCE] VALIDATION FAILED: DataFrame contains NaN values"
        )
        raise ValueError(
            "Feature preparation failed: DataFrame still contains NaN values after imputation"
        )

    return df_prep


def get_ensemble_breakdown(
    prediction_result: dict, models_dict: dict
) -> Dict[str, Any]:
    """
    Extract detailed ensemble breakdown from prediction result.

    Provides model weights, sub-model predictions, and confidence breakdown.

    Args:
        prediction_result: Result dictionary from predict_signal()
        models_dict: Models dictionary from load_ml_models()

    Returns:
        Dictionary with ensemble breakdown:
        - component_weights: Dict of model weights
        - component_predictions: Dict of individual model predictions
        - confidence_breakdown: Dict of confidence scores per component
        - ensemble_forecast: Combined prediction
    """
    breakdown = {
        "ensemble_forecast": prediction_result.get("signal", 0),
        "confidence": prediction_result.get("confidence", 0.0),
        "model_used": prediction_result.get("model_used", "unknown"),
        "component_weights": {},
        "component_predictions": {},
        "confidence_breakdown": {},
    }

    model_used = prediction_result.get("model_used", "unknown")

    # Kaggle-Prophet Hybrid breakdown
    if model_used == "kaggle_prophet_hybrid":
        hybrid_model = models_dict.get("kaggle_prophet_hybrid")
        if hybrid_model and hasattr(hybrid_model, "weights"):
            breakdown["component_weights"] = {
                "bilstm": (
                    hybrid_model.weights[0] if len(hybrid_model.weights) > 0 else 0.0
                ),
                "xgboost": (
                    hybrid_model.weights[1] if len(hybrid_model.weights) > 1 else 0.0
                ),
                "bilstm_residual": (
                    hybrid_model.weights[2] if len(hybrid_model.weights) > 2 else 0.0
                ),
                "prophet": (
                    hybrid_model.weights[3] if len(hybrid_model.weights) > 3 else 0.0
                ),
            }

            # Try to get component predictions if available
            if hasattr(hybrid_model, "last_component_predictions"):
                breakdown["component_predictions"] = (
                    hybrid_model.last_component_predictions
                )

            # Confidence breakdown (equal for now, can be enhanced)
            breakdown["confidence_breakdown"] = {
                "bilstm": breakdown["confidence"],
                "xgboost": breakdown["confidence"],
                "prophet": breakdown["confidence"],
            }

    # HybridEnsemble breakdown
    elif model_used == "ensemble":
        ensemble = models_dict.get("ensemble")
        if ensemble and hasattr(ensemble, "config"):
            weights = ensemble.config.get("ensemble_weights", {})
            breakdown["component_weights"] = {
                "xgboost": weights.get("xgboost", 0.6),
                "arima_garch": weights.get("arima_garch", 0.4),
            }

            # Try to extract component predictions if available
            if hasattr(ensemble, "last_prediction"):
                last_pred = ensemble.last_prediction
                if hasattr(last_pred, "xgboost_forecast"):
                    breakdown["component_predictions"] = {
                        "xgboost": last_pred.xgboost_forecast,
                        "arima_garch": last_pred.arima_forecast,
                    }

    # XGBoost (single model)
    elif model_used == "xgboost":
        breakdown["component_weights"] = {"xgboost": 1.0}
        breakdown["component_predictions"] = {"xgboost": breakdown["ensemble_forecast"]}
        breakdown["confidence_breakdown"] = {"xgboost": breakdown["confidence"]}

    return breakdown


def log_ensemble_breakdown(breakdown: Dict[str, Any]) -> None:
    """
    Log ensemble breakdown to logger for monitoring.

    Args:
        breakdown: Breakdown dictionary from get_ensemble_breakdown()
    """
    model_used = breakdown.get("model_used", "unknown")
    weights = breakdown.get("component_weights", {})
    predictions = breakdown.get("component_predictions", {})

    _log_with_context(
        "INFO",
        "[ENSEMBLE] Ensemble breakdown",
        model=model_used,
        confidence=breakdown.get("confidence", 0.0),
    )

    logger.info(f"[ENSEMBLE] Model: {model_used}")
    logger.info(f"[ENSEMBLE] Confidence: {breakdown.get('confidence', 0.0):.2f}")

    if weights:
        logger.info(f"[ENSEMBLE] Component Weights:")
        for component, weight in weights.items():
            logger.info(f"  - {component}: {weight:.2%}")

    if predictions:
        logger.info(f"[ENSEMBLE] Component Predictions:")
        for component, pred in predictions.items():
            logger.info(f"  - {component}: {pred:.4f}")


def display_ensemble_breakdown(breakdown: Dict[str, Any]) -> None:
    """
    Display ensemble breakdown in Streamlit dashboard.

    Shows component weights, predictions, and confidence scores.

    Args:
        breakdown: Breakdown dictionary from get_ensemble_breakdown()
    """
    st.subheader("📊 Ensemble Breakdown")

    # Model used
    model_used = breakdown.get("model_used", "unknown")
    confidence = breakdown.get("confidence", 0.0)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Model", model_used.replace("_", " ").title())
    with col2:
        st.metric("Confidence", f"{confidence:.1%}")

    # Component weights
    weights = breakdown.get("component_weights", {})
    if weights:
        st.write("**Component Weights:**")
        weight_cols = st.columns(len(weights))
        for idx, (component, weight) in enumerate(weights.items()):
            with weight_cols[idx]:
                st.metric(component.replace("_", " ").title(), f"{weight:.1%}")

        # Weight visualization (simple bar chart)
        if len(weights) > 0:
            weight_df = pd.DataFrame(
                {"Component": list(weights.keys()), "Weight": list(weights.values())}
            )
            weight_df["Component"] = (
                weight_df["Component"].str.replace("_", " ").str.title()
            )

            st.bar_chart(weight_df.set_index("Component"))

    # Component predictions
    predictions = breakdown.get("component_predictions", {})
    if predictions:
        with st.expander("🔍 Component Predictions"):
            for component, pred in predictions.items():
                if pred is not None:
                    st.write(f"**{component.replace('_', ' ').title()}**: {pred:.4f}")

    # Confidence breakdown
    confidence_breakdown = breakdown.get("confidence_breakdown", {})
    if confidence_breakdown:
        with st.expander("📈 Confidence Breakdown"):
            for component, conf in confidence_breakdown.items():
                st.write(f"**{component.replace('_', ' ').title()}**: {conf:.1%}")


def fit_garch_vol(
    df_stock: pd.DataFrame,
    df_es: Optional[pd.DataFrame] = None,
    lookback: int = 252,
    horizon: int = 5,
    data_pipeline=None,
) -> Dict[str, Any]:
    """
    Fit GARCH(1,1) model on ES futures for market volatility and blend with stock volatility.

    Args:
        df_stock: Stock OHLCV data
        df_es: ES futures OHLCV data (optional, will fetch if None)
        lookback: Number of days for GARCH fitting (default: 252 trading days)
        horizon: Forecast horizon in days (default: 5)
        data_pipeline: DataPipeline instance for fetching ES data

    Returns:
        Dict with:
            - vol_forecast: Blended volatility forecast (70% ES + 30% stock)
            - es_vol: ES market volatility
            - stock_vol: Stock-specific volatility
            - garch_params: GARCH model parameters (omega, alpha, beta)
            - garch_res: Full GARCH results object
    """
    try:
        from arch import arch_model
        from scipy import stats
    except ImportError:
        logger.warning(
            "[GARCH] arch or scipy not available - returning default volatility"
        )
        return {
            "vol_forecast": 0.015,
            "es_vol": 0.012,
            "stock_vol": 0.02,
            "garch_params": {},
        }

    # Fetch ES data if not provided
    if df_es is None or df_es.empty:
        try:
            if data_pipeline is not None:
                df_es = data_pipeline.get_data("ES1!", timeframe="1d", days=lookback)
            else:
                # Try to import and use PolygonProvider
                from src.option_analysis.data_providers import PolygonProvider
                import os

                polygon_key = os.getenv("POLYGON_API_KEY")
                if polygon_key:
                    provider = PolygonProvider(api_key=polygon_key)
                    df_es = provider.get_es_futures(days_back=lookback, interval="day")
        except Exception as e:
            logger.warning(f"[GARCH] Failed to fetch ES data: {e} - using defaults")

    if df_es is None or df_es.empty or len(df_es) < 50:
        logger.warning("[GARCH] Insufficient ES data - returning default volatility")
        return {
            "vol_forecast": 0.015,
            "es_vol": 0.012,
            "stock_vol": 0.02,
            "garch_params": {},
        }

    try:
        # Calculate ES log returns (daily)
        if "Close" in df_es.columns:
            es_close = df_es["Close"]
        elif "close" in df_es.columns:
            es_close = df_es["close"]
        else:
            logger.warning("[GARCH] No Close column in ES data")
            return {
                "vol_forecast": 0.015,
                "es_vol": 0.012,
                "stock_vol": 0.02,
                "garch_params": {},
            }

        # ES returns: 100 * log(price_t / price_{t-1})
        es_rets = 100 * np.log(es_close / es_close.shift(1)).dropna().tail(lookback)

        if len(es_rets) < 50:
            logger.warning(
                f"[GARCH] Only {len(es_rets)} ES returns available - need at least 50"
            )
            return {
                "vol_forecast": 0.015,
                "es_vol": 0.012,
                "stock_vol": 0.02,
                "garch_params": {},
            }

        # Fit GARCH(1,1) - zero mean, conditional heteroskedasticity
        model = arch_model(es_rets, vol="Garch", p=1, q=1, rescale=False, mean="Zero")
        res = model.fit(disp="off", show_warning=False)

        # Forecast volatility
        forecast = res.forecast(horizon=horizon)
        es_vol = (
            np.sqrt(forecast.variance.iloc[-1].mean()) / 100
        )  # Daily vol (de-scale from %)

        # Calculate stock volatility: Recent 30-day rolling std
        if "Close" in df_stock.columns:
            stock_close = df_stock["Close"]
        elif "close" in df_stock.columns:
            stock_close = df_stock["close"]
        else:
            stock_close = df_stock.iloc[:, 3]  # Assume 4th column is close

        stock_rets = (
            100 * np.log(stock_close.tail(30) / stock_close.shift(1).tail(30)).dropna()
        )
        stock_vol = stock_rets.std() / 100 if len(stock_rets) > 0 else 0.02

        # Blend weights: Market-dominant (70% ES, 30% stock)
        blended_vol = 0.7 * es_vol + 0.3 * stock_vol

        # Extract GARCH parameters
        params = {
            k: f"{v:.4f}"
            for k, v in res.params.items()
            if any(x in k for x in ["omega", "alpha", "beta"])
        }

        logger.info(
            f"[GARCH] ES={es_vol:.2%}, Stock={stock_vol:.2%}, Blended={blended_vol:.2%}, Params={params}"
        )

        return {
            "vol_forecast": blended_vol,
            "es_vol": es_vol,
            "stock_vol": stock_vol,
            "garch_params": params,
            "garch_res": res,  # For monitoring
        }

    except Exception as e:
        logger.error(f"[GARCH] Fitting failed: {e}")
        return {
            "vol_forecast": 0.015,
            "es_vol": 0.012,
            "stock_vol": 0.02,
            "garch_params": {},
        }


def fit_arima_garch(
    df_stock: pd.DataFrame, p: int = 1, d: int = 1, q: int = 1, symbol: str = "STOCK"
) -> Dict[str, Any]:
    """
    Fit ARIMA(p,d,q)-GARCH(1,1) model for stock volatility forecasting.

    Returns residual-based GARCH volatility forecast and saves model to disk.
    """
    try:
        from statsmodels.tsa.arima.model import ARIMA
        import joblib
        import os

        # Get returns
        if "Close" in df_stock.columns:
            close = df_stock["Close"]
        elif "close" in df_stock.columns:
            close = df_stock["close"]
        else:
            close = df_stock.iloc[:, 3]

        rets = 100 * np.log(close / close.shift(1)).dropna()

        if len(rets) < 50:
            logger.warning(
                f"[ARIMA-GARCH] Insufficient data for {symbol}: {len(rets)} returns"
            )
            return {"vol_forecast": 0.015, "arima_model": None, "garch_model": None}

        # Fit ARIMA on returns
        arima_model = ARIMA(rets, order=(p, d, q)).fit()
        residuals = arima_model.resid

        # Fit GARCH(1,1) on residuals
        garch = arch_model(residuals, vol="Garch", p=1, q=1, mean="Zero").fit(
            disp="off", show_warning=False
        )

        # Forecast volatility
        forecast = garch.forecast(horizon=5)
        vol_forecast = np.sqrt(forecast.variance.iloc[-1].mean()) / 100

        # Save models
        os.makedirs("models", exist_ok=True)
        model_path = f"models/arima_garch_{symbol.lower()}.pkl"
        joblib.dump(
            {
                "arima": arima_model,
                "garch": garch,
                "vol_forecast": vol_forecast,
                "symbol": symbol,
            },
            model_path,
        )

        logger.info(
            f"✅ ARIMA-GARCH fitted for {symbol}: Vol={vol_forecast:.2%}, saved to {model_path}"
        )

        return {
            "arima_model": arima_model,
            "garch_model": garch,
            "vol_forecast": vol_forecast,
            "model_path": model_path,
        }

    except Exception as e:
        logger.error(f"[ARIMA-GARCH] Failed for {symbol}: {e}")
        return {"vol_forecast": 0.015, "arima_model": None, "garch_model": None}


def fit_market_regime(df_es: pd.DataFrame, symbol: str = "ES") -> Dict[str, Any]:
    """
    Fit market regime detection model based on ES futures volatility clustering.

    Classifies market into Low/Medium/High volatility regimes.
    """
    try:
        import joblib
        import os

        # Get ES returns
        if "Close" in df_es.columns:
            close = df_es["Close"]
        elif "close" in df_es.columns:
            close = df_es["close"]
        else:
            close = df_es.iloc[:, 3]

        es_rets = 100 * np.log(close / close.shift(1)).dropna()

        if len(es_rets) < 100:
            logger.warning(
                f"[MARKET-REGIME] Insufficient ES data: {len(es_rets)} returns"
            )
            return {"current_regime": "Medium", "garch_model": None}

        # Fit GARCH for conditional volatility
        garch = arch_model(es_rets, vol="Garch", p=1, q=1, mean="Zero").fit(
            disp="off", show_warning=False
        )

        # Classify into regimes based on conditional vol percentiles
        cond_vol = garch.conditional_volatility
        low_thresh = cond_vol.quantile(0.33)
        high_thresh = cond_vol.quantile(0.67)

        def classify_regime(vol):
            if vol < low_thresh:
                return "Low"
            elif vol < high_thresh:
                return "Medium"
            else:
                return "High"

        regimes = cond_vol.apply(classify_regime)
        current_regime = regimes.iloc[-1]
        current_vol = cond_vol.iloc[-1] / 100  # Convert to decimal

        # Save model
        os.makedirs("models", exist_ok=True)
        model_path = f"models/market_regime_{symbol.lower()}.pkl"
        joblib.dump(
            {
                "garch": garch,
                "regimes": regimes,
                "current_regime": current_regime,
                "current_vol": current_vol,
                "thresholds": {"low": low_thresh, "high": high_thresh},
            },
            model_path,
        )

        logger.info(
            f"✅ Market regime fitted for {symbol}: Current={current_regime} ({current_vol:.2%}), saved to {model_path}"
        )

        return {
            "garch_model": garch,
            "regimes": regimes,
            "current_regime": current_regime,
            "current_vol": current_vol,
            "model_path": model_path,
        }

    except Exception as e:
        logger.error(f"[MARKET-REGIME] Failed for {symbol}: {e}")
        return {"current_regime": "Medium", "garch_model": None}


def _ensure_models_trained(
    models_dict: dict,
    df_ohlcv: Optional[pd.DataFrame] = None,
    symbol: Optional[str] = None,
) -> None:
    """
    Auto-train missing ARIMA-GARCH and ES market regime models on-demand.

    Checks if model files exist; if not, trains them using available data.
    """
    import os
    import joblib

    try:
        # Check and train ARIMA-GARCH if missing
        arima_path = f'models/arima_garch_{(symbol or "stock").lower()}.pkl'
        if (
            not os.path.exists(arima_path)
            and df_ohlcv is not None
            and len(df_ohlcv) > 100
        ):
            logger.info(
                f"[AUTO-TRAIN] ARIMA-GARCH model not found for {symbol}, training on-demand..."
            )
            result = fit_arima_garch(df_ohlcv, symbol=symbol or "STOCK")
            if result.get("arima_model") is not None:
                models_dict["arima_garch"] = result
        elif os.path.exists(arima_path):
            # Load existing model
            if "arima_garch" not in models_dict:
                try:
                    models_dict["arima_garch"] = joblib.load(arima_path)
                    logger.debug(
                        f"[AUTO-TRAIN] Loaded existing ARIMA-GARCH from {arima_path}"
                    )
                except Exception as e:
                    logger.warning(f"[AUTO-TRAIN] Could not load ARIMA-GARCH: {e}")

        # Check and train ES market regime if missing
        regime_path = "models/market_regime_es.pkl"
        if not os.path.exists(regime_path):
            logger.info(
                "[AUTO-TRAIN] ES market regime model not found, training on-demand..."
            )
            try:
                # Try to fetch ES data
                from main_production_system.dashboard.core.data_pipeline import (
                    get_data_and_features_with_friendly_errors,
                )

                df_es, _ = get_data_and_features_with_friendly_errors(
                    "ES=F", "1d", 365, use_polygon=False
                )

                if df_es is not None and len(df_es) > 100:
                    result = fit_market_regime(df_es, symbol="ES")
                    if result.get("garch_model") is not None:
                        models_dict["market_regime"] = result
                else:
                    logger.info(
                        "[AUTO-TRAIN] Insufficient ES data for regime model, skipping"
                    )
            except Exception as e:
                logger.warning(f"[AUTO-TRAIN] ES market regime training failed: {e}")
        elif os.path.exists(regime_path):
            # Load existing model
            if "market_regime" not in models_dict:
                try:
                    models_dict["market_regime"] = joblib.load(regime_path)
                    logger.debug(
                        f"[AUTO-TRAIN] Loaded existing market regime from {regime_path}"
                    )
                except Exception as e:
                    logger.warning(f"[AUTO-TRAIN] Could not load market regime: {e}")

    except Exception as e:
        logger.debug(f"[AUTO-TRAIN] Non-critical failure: {e}")


def predict_signal(
    df_features: pd.DataFrame,
    models_dict: dict,
    df_ohlcv=None,
    return_probas: bool = False,
    symbol: Optional[str] = None,
) -> dict:
    logger.info(f"[INFERENCE] Generating signal from {df_features.shape[0]} candles...")
    try:
        # Auto-train missing models on-demand
        _ensure_models_trained(models_dict, df_ohlcv, symbol)

        df_prep = prepare_features_for_inference(df_features, drop_ohlcv=True)
        if df_prep.shape[0] == 0:
            raise ValueError("No valid rows after feature preparation")

        # Try Kaggle-Prophet Hybrid first (elite model)
        if models_dict.get("kaggle_prophet_hybrid") is not None:
            logger.info(f"[INFERENCE] Using Kaggle-Prophet Hybrid for prediction...")
            try:
                hybrid_model = models_dict["kaggle_prophet_hybrid"]

                # Check if model is trained
                if (
                    not hasattr(hybrid_model, "is_trained")
                    or not hybrid_model.is_trained
                ):
                    logger.warning(
                        "[INFERENCE] Kaggle-Prophet Hybrid not trained yet, falling back..."
                    )
                else:
                    signals, confidence = hybrid_model.predict(
                        X_test=df_prep, df_ohlcv_test=df_ohlcv
                    )

                    latest_signal = int(signals[-1]) if len(signals) > 0 else 0
                    conf_score = float(confidence[-1]) if len(confidence) > 0 else 0.5

                    result = {
                        "signal": latest_signal,
                        "signal_text": (
                            "BUY"
                            if latest_signal == 1
                            else "SELL" if latest_signal == -1 else "HOLD"
                        ),
                        "confidence": conf_score,
                        "ensemble_ready": True,
                        "model_used": "kaggle_prophet_hybrid",
                        "model": "Kaggle-Prophet Hybrid",
                        "timestamp": pd.Timestamp.now(),
                        "error": None,
                    }

                    # Add ensemble breakdown
                    breakdown = get_ensemble_breakdown(result, models_dict)
                    result["component_breakdown"] = breakdown

                    # Log ensemble breakdown
                    log_ensemble_breakdown(breakdown)

                    logger.info(
                        f"[INFERENCE] ✅ Kaggle-Prophet Hybrid prediction: signal={latest_signal}, confidence={conf_score:.2f}"
                    )

                    # Monitor model performance (if monitoring available)
                    if MONITORING_AVAILABLE and df_ohlcv is not None:
                        try:
                            monitor = MLModelMonitor()
                            if "Close" in df_ohlcv.columns:
                                actuals = df_ohlcv["Close"].values[-len(signals) :]
                                # Only monitor if we have actuals
                                if len(actuals) == len(signals):
                                    monitor.check_model_performance(
                                        model_name="kaggle_prophet_hybrid",
                                        predictions=signals.astype(float),
                                        actuals=actuals.astype(float),
                                    )
                        except Exception as monitor_error:
                            logger.debug(
                                f"[MODEL_MANAGER] Monitoring failed (non-critical): {monitor_error}"
                            )

                    # Enrich with Perplexity market intelligence
                    if symbol:
                        result = enrich_forecast_with_perplexity(result, symbol)

                    return result
            except Exception as e:
                logger.warning(
                    f"[INFERENCE] Kaggle-Prophet Hybrid predict failed: {e}, falling back to legacy models"
                )

        # Fallback to legacy ensemble
        if models_dict.get("ensemble") is not None:
            logger.info(f"[INFERENCE] Using HybridEnsemble for prediction...")
            try:
                df_ens = df_prep.copy()
                if hasattr(models_dict["ensemble"], "n_features_"):
                    expected_n = int(models_dict["ensemble"].n_features_)
                    actual_n = df_ens.shape[1]

                    logger.info(
                        f"[INFERENCE] Ensemble feature alignment: Provided={actual_n}, Expected={expected_n}"
                    )

                    if actual_n > expected_n:
                        logger.warning(
                            f"[INFERENCE] ⚠️ Too many features ({actual_n} > {expected_n}). Truncating to first {expected_n} columns."
                        )
                        df_ens = df_ens.iloc[:, :expected_n]
                    elif actual_n < expected_n:
                        missing = expected_n - actual_n
                        logger.error(
                            f"[INFERENCE] ❌ CRITICAL: Feature dimension mismatch! Provided {actual_n} features, ensemble expects {expected_n}. Missing {missing} features."
                        )

                        # Pad with zeros
                        padding = np.zeros((df_ens.shape[0], missing))
                        df_ens_padded = pd.DataFrame(
                            np.hstack([df_ens.values, padding]),
                            columns=list(df_ens.columns)
                            + [f"missing_feature_{i+1}" for i in range(missing)],
                            index=df_ens.index,
                        )
                        logger.warning(
                            f"[INFERENCE] ⚠️ Padded {missing} missing features with zeros."
                        )
                        df_ens = df_ens_padded
                    else:
                        logger.info(
                            f"[INFERENCE] ✅ Ensemble feature count matches: {actual_n} features"
                        )

                predictions = models_dict["ensemble"].predict(df_ens.values)
                latest_signal = int(predictions[-1]) if len(predictions) > 0 else 0
                try:
                    confidence = models_dict["ensemble"].get_model_status()
                    conf_score = (
                        confidence.get("confidence", 0.5)
                        if isinstance(confidence, dict)
                        else 0.5
                    )
                except Exception:
                    conf_score = 0.7
                result = {
                    "signal": latest_signal,
                    "signal_text": (
                        "BUY"
                        if latest_signal == 1
                        else "SELL" if latest_signal == -1 else "HOLD"
                    ),
                    "confidence": conf_score,
                    "ensemble_ready": True,
                    "model_used": "ensemble",
                    "model": "HybridEnsemble",
                    "timestamp": pd.Timestamp.now(),
                    "error": None,
                }

                # Add ensemble breakdown
                breakdown = get_ensemble_breakdown(result, models_dict)
                result["component_breakdown"] = breakdown

                # Log ensemble breakdown
                log_ensemble_breakdown(breakdown)

                logger.info(
                    f"[INFERENCE] ✅ Ensemble prediction: signal={latest_signal}, confidence={conf_score:.2f}"
                )

                # === GARCH VOLATILITY BLENDING (ES + Stock) ===
                try:
                    if (
                        df_ohlcv is not None
                        and isinstance(df_ohlcv, pd.DataFrame)
                        and len(df_ohlcv) > 0
                    ):
                        garch = fit_garch_vol(
                            df_stock=df_ohlcv, df_es=None, lookback=252, horizon=5
                        )
                        if garch and garch.get("vol_forecast") is not None:
                            vol_forecast = float(garch["vol_forecast"])
                            # Dampen confidence and provide adjusted signal strength (leave discrete signal unchanged)
                            vol_factor = max(0.5, 1 / (1 + vol_forecast * 20))
                            result["confidence"] = (
                                float(result.get("confidence", 0.6)) * vol_factor
                            )
                            result["signal_strength"] = (
                                float(result["signal"]) * vol_factor
                            )
                            # Attach monitoring fields
                            result["vol_forecast"] = vol_forecast
                            result["es_vol"] = float(garch.get("es_vol", 0.0))
                            result["stock_vol"] = float(garch.get("stock_vol", 0.0))
                            result["garch_params"] = garch.get("garch_params", {})
                            result["vol_factor"] = vol_factor
                            # Optional: monitor drift if available
                            if MONITORING_AVAILABLE:
                                try:
                                    monitor = MLModelMonitor()
                                    monitor.track_vol_drift(
                                        "garch",
                                        current_vol=vol_forecast,
                                        threshold=0.05,
                                        baseline_vol=0.015,
                                    )
                                except Exception as me:
                                    logger.debug(f"[GARCH] Monitoring skip: {me}")
                except Exception as e:
                    logger.debug(f"[GARCH] Blend step failed (non-critical): {e}")

                # Monitor model performance (if monitoring available)
                if MONITORING_AVAILABLE and df_ohlcv is not None:
                    try:
                        monitor = MLModelMonitor()
                        if "Close" in df_ohlcv.columns:
                            actuals = df_ohlcv["Close"].values[-len(predictions) :]
                            if len(actuals) == len(predictions):
                                monitor.check_model_performance(
                                    model_name="ensemble",
                                    predictions=predictions.astype(float),
                                    actuals=actuals.astype(float),
                                )
                    except Exception as monitor_error:
                        logger.debug(
                            f"[MODEL_MANAGER] Monitoring failed (non-critical): {monitor_error}"
                        )

                # Enrich with Perplexity market intelligence
                if symbol:
                    result = enrich_forecast_with_perplexity(result, symbol)

                return result
            except Exception as e:
                logger.warning(
                    f"[INFERENCE] Ensemble predict failed: {e}, falling back to XGBoost"
                )
        if models_dict.get("xgboost") is not None:
            logger.info(
                f"[INFERENCE] Using XGBoost for prediction (ensemble unavailable)..."
            )
            try:
                df_xgb = df_prep.copy()
                if hasattr(models_dict["xgboost"], "n_features_in_"):
                    expected_n = int(models_dict["xgboost"].n_features_in_)
                    actual_n = df_xgb.shape[1]

                    # Debug: provided feature matrix vs model expectation
                    logger.info(
                        f"[INFERENCE] Feature alignment: Provided={actual_n}, Expected={expected_n}"
                    )

                    if actual_n > expected_n:
                        # Too many features: truncate to expected count
                        logger.warning(
                            f"[INFERENCE] ⚠️ Too many features ({actual_n} > {expected_n}). Truncating to first {expected_n} columns."
                        )
                        df_xgb = df_xgb.iloc[:, :expected_n]
                    elif actual_n < expected_n:
                        # CRITICAL: Too few features - pad with zeros or mean values
                        missing = expected_n - actual_n
                        logger.error(
                            f"[INFERENCE] ❌ CRITICAL: Feature dimension mismatch! Provided {actual_n} features, model expects {expected_n}. Missing {missing} features."
                        )

                        # Try to pad with zeros (safe fallback)
                        # Alternative: pad with column means (more sophisticated)
                        padding = np.zeros((df_xgb.shape[0], missing))

                        # Option: Use mean values for padding (uncomment if preferred)
                        # col_means = df_xgb.mean(axis=0).values
                        # padding = np.tile(col_means[:missing], (df_xgb.shape[0], 1))

                        df_xgb_padded = pd.DataFrame(
                            np.hstack([df_xgb.values, padding]),
                            columns=list(df_xgb.columns)
                            + [f"missing_feature_{i+1}" for i in range(missing)],
                            index=df_xgb.index,
                        )
                        logger.warning(
                            f"[INFERENCE] ⚠️ Padded {missing} missing features with zeros. Model may not perform optimally."
                        )
                        df_xgb = df_xgb_padded
                    else:
                        logger.info(
                            f"[INFERENCE] ✅ Feature count matches: {actual_n} features"
                        )
                else:
                    # Model doesn't have n_features_in_ attribute - log warning
                    logger.warning(
                        f"[INFERENCE] ⚠️ Model doesn't have n_features_in_ attribute. Cannot verify feature alignment."
                    )
                    logger.info(f"[INFERENCE] Provided features: {df_xgb.shape}")

                predictions = models_dict["xgboost"].predict(df_xgb.values)
                if len(predictions) == 0:
                    xgb_signal = 0
                else:
                    latest_raw = float(predictions[-1])
                    # Map regression outputs to {-1,0,1}
                    if latest_raw in (-1.0, 0.0, 1.0):
                        xgb_signal = int(latest_raw)
                    else:
                        xgb_signal = (
                            1 if latest_raw > 0 else (-1 if latest_raw < 0 else 0)
                        )
                conf_score = 0.6
                if hasattr(models_dict["xgboost"], "predict_proba"):
                    try:
                        probas = models_dict["xgboost"].predict_proba(df_xgb.values)
                        conf_score = float(np.max(probas[-1]))
                    except Exception:
                        pass

                # Get ARIMA-GARCH forecast if available
                volatility_signal = 0
                arima_forecast = None
                arima_volatility = None
                symbol = None
                if df_ohlcv is not None and "Close" in df_ohlcv.columns:
                    # Try to extract symbol from session state or features
                    try:
                        # Try multiple possible session state keys
                        symbol = (
                            st.session_state.get("current_symbol")
                            or st.session_state.get("symbol")
                            or st.session_state.get("ticker")
                            or "CRWD"
                        )
                    except:
                        symbol = "CRWD"

                    # Get ARIMA-GARCH model for this symbol if available (already loaded)
                    arima_garch_models = models_dict.get("arima_garch_models", {})
                    if symbol in arima_garch_models:
                        try:
                            arima_model = arima_garch_models[symbol]

                            if arima_model and hasattr(arima_model, "forecast_with_es"):
                                # Get ES returns for forecast (use recent ES returns)
                                try:
                                    from core.data_providers.futures_data_handler import (
                                        FuturesDataHandler,
                                    )

                                    handler = FuturesDataHandler()
                                    es_data = handler.fetch_es_historical(days=30)
                                    if es_data is not None and not es_data.empty:
                                        es_returns = np.log(
                                            es_data["Close"] / es_data["Close"].shift(1)
                                        ).dropna()
                                        # Use recent ES returns for forecast
                                        recent_es = es_returns.tail(5).values

                                        forecast = arima_model.forecast_with_es(
                                            recent_es, steps=1
                                        )
                                        if forecast:
                                            arima_volatility = (
                                                forecast.get(
                                                    "forecast_volatility", [0]
                                                )[0]
                                                / 100.0
                                            )  # Convert from %
                                            # Convert volatility to signal direction (high vol = bearish, low vol = bullish)
                                            volatility_signal = (
                                                -1
                                                if arima_volatility > 0.02
                                                else (
                                                    1 if arima_volatility < 0.01 else 0
                                                )
                                            )
                                            arima_forecast = forecast.get(
                                                "forecast_returns", [0]
                                            )[0]
                                            logger.info(
                                                f"[INFERENCE] ARIMA-GARCH forecast for {symbol}: volatility={arima_volatility:.4f}, signal={volatility_signal}"
                                            )
                                except Exception as e:
                                    logger.warning(
                                        f"[INFERENCE] ARIMA-GARCH forecast failed: {e}"
                                    )
                        except Exception as e:
                            logger.warning(
                                f"[INFERENCE] Failed to load ARIMA-GARCH model for {symbol}: {e}"
                            )

                # Get ES market adjustment
                market_adjust = 0
                es_market_vol = None
                if models_dict.get("es_market"):
                    es_model = models_dict["es_market"]
                    try:
                        if df_ohlcv is not None and "Close" in df_ohlcv.columns:
                            # Get ES forecast
                            try:
                                from core.data_providers.futures_data_handler import (
                                    FuturesDataHandler,
                                )

                                handler = FuturesDataHandler()
                                es_data = handler.fetch_es_historical(days=30)
                                if es_data is not None and not es_data.empty:
                                    es_returns = np.log(
                                        es_data["Close"] / es_data["Close"].shift(1)
                                    ).dropna()
                                    recent_es = es_returns.tail(5).values

                                    if hasattr(es_model, "forecast_with_es"):
                                        es_forecast = es_model.forecast_with_es(
                                            recent_es, steps=1
                                        )
                                        if es_forecast:
                                            es_market_vol = (
                                                es_forecast.get(
                                                    "forecast_volatility", [0]
                                                )[0]
                                                / 100.0
                                            )  # Convert from %
                                            market_adjust = (
                                                -0.2 if es_market_vol > 0.02 else 0.2
                                            )  # Penalize high market vol, boost low
                                            logger.info(
                                                f"ES market adjustment: {market_adjust:+.2f}, volatility={es_market_vol:.4f}"
                                            )
                            except Exception as e:
                                logger.warning(f"ES market forecast failed: {e}")
                    except Exception as e:
                        logger.warning(f"No ES market model available: {e}")
                else:
                    logger.debug("No ES market model")

                # Get Perplexity sentiment score
                sentiment_score = 0.0
                if models_dict.get("perplexity") is not None and symbol:
                    try:
                        import asyncio

                        perplexity_svc = models_dict["perplexity"]

                        # Get market intelligence asynchronously
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        intelligence = loop.run_until_complete(
                            perplexity_svc.get_market_intelligence([symbol])
                        )
                        loop.close()

                        if intelligence and symbol in intelligence:
                            intel = intelligence[symbol]
                            sentiment = intel.get("sentiment", "neutral")
                            confidence = intel.get("confidence", 0.5)

                            # Convert sentiment to numeric signal
                            if sentiment == "bullish":
                                sentiment_score = confidence
                            elif sentiment == "bearish":
                                sentiment_score = -confidence
                            else:
                                sentiment_score = 0.0

                            logger.info(
                                f"[INFERENCE] Perplexity sentiment for {symbol}: {sentiment} (score={sentiment_score:+.2f})"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[INFERENCE] Perplexity sentiment fetch failed: {e}"
                        )
                        sentiment_score = 0.0

                # Enhanced Ensemble: XGBoost (45%) + GARCH (30%) + ES Market (15%) + Perplexity (10%)
                if xgb_signal != 0:
                    ensemble_signal_raw = (
                        0.45 * xgb_signal
                        + 0.30 * volatility_signal
                        + 0.15 * market_adjust
                        + 0.10 * sentiment_score
                    )
                    # Convert back to signal {-1, 0, 1}
                    if ensemble_signal_raw > 0.3:
                        latest_signal = 1
                    elif ensemble_signal_raw < -0.3:
                        latest_signal = -1
                    else:
                        latest_signal = 0
                    logger.info(
                        f"[INFERENCE] Ensemble: XGBoost={xgb_signal}, GARCH={volatility_signal}, ES={market_adjust:.2f}, Sentiment={sentiment_score:+.2f} → Final={latest_signal}"
                    )
                else:
                    # Fallback if XGBoost unavailable
                    ensemble_signal_raw = (
                        0.30 * volatility_signal
                        + 0.15 * market_adjust
                        + 0.10 * sentiment_score
                    )
                    if ensemble_signal_raw > 0.2:
                        latest_signal = 1
                    elif ensemble_signal_raw < -0.2:
                        latest_signal = -1
                    else:
                        latest_signal = 0

                result = {
                    "signal": latest_signal,
                    "signal_text": (
                        "BUY"
                        if latest_signal == 1
                        else "SELL" if latest_signal == -1 else "HOLD"
                    ),
                    "confidence": conf_score,
                    "ensemble_ready": (
                        True
                        if (arima_forecast is not None or es_market_vol is not None)
                        else False
                    ),
                    "model_used": (
                        "ensemble"
                        if (arima_forecast is not None or es_market_vol is not None)
                        else "xgboost"
                    ),
                    "model": (
                        "Ensemble (XGBoost+GARCH+ES+Perplexity)"
                        if (arima_forecast is not None or es_market_vol is not None)
                        else "XGBoost"
                    ),
                    "timestamp": pd.Timestamp.now(),
                    "error": None,
                    "es_market_vol": es_market_vol,
                    "market_adjust": market_adjust,
                    "arima_volatility": arima_volatility,
                    "arima_forecast": arima_forecast,
                    "xgboost_signal": xgb_signal,
                    "garch_signal": volatility_signal,
                    "sentiment_score": sentiment_score,
                }

                # Add ensemble breakdown (single model)
                breakdown = get_ensemble_breakdown(result, models_dict)
                result["component_breakdown"] = breakdown

                # Log ensemble breakdown
                log_ensemble_breakdown(breakdown)

                logger.info(
                    f"[INFERENCE] ✅ XGBoost prediction: signal={latest_signal}, confidence={conf_score:.2f}"
                )

                # === GARCH VOLATILITY BLENDING (ES + Stock) ===
                try:
                    if (
                        df_ohlcv is not None
                        and isinstance(df_ohlcv, pd.DataFrame)
                        and len(df_ohlcv) > 0
                    ):
                        garch = fit_garch_vol(
                            df_stock=df_ohlcv, df_es=None, lookback=252, horizon=5
                        )
                        if garch and garch.get("vol_forecast") is not None:
                            vol_forecast = float(garch["vol_forecast"])
                            vol_factor = max(0.5, 1 / (1 + vol_forecast * 20))
                            result["confidence"] = (
                                float(result.get("confidence", 0.6)) * vol_factor
                            )
                            result["signal_strength"] = (
                                float(result["signal"]) * vol_factor
                            )
                            result["vol_forecast"] = vol_forecast
                            result["es_vol"] = float(garch.get("es_vol", 0.0))
                            result["stock_vol"] = float(garch.get("stock_vol", 0.0))
                            result["garch_params"] = garch.get("garch_params", {})
                            result["vol_factor"] = vol_factor
                            if MONITORING_AVAILABLE:
                                try:
                                    monitor = MLModelMonitor()
                                    monitor.track_vol_drift(
                                        "garch",
                                        current_vol=vol_forecast,
                                        threshold=0.05,
                                        baseline_vol=0.015,
                                    )
                                except Exception as me:
                                    logger.debug(f"[GARCH] Monitoring skip: {me}")
                except Exception as e:
                    logger.debug(f"[GARCH] Blend step failed (non-critical): {e}")

                # Monitor model performance (if monitoring available)
                if MONITORING_AVAILABLE and df_ohlcv is not None:
                    try:
                        monitor = MLModelMonitor()
                        if "Close" in df_ohlcv.columns:
                            actuals = df_ohlcv["Close"].values[-len(predictions) :]
                            if len(actuals) == len(predictions):
                                monitor.check_model_performance(
                                    model_name="xgboost",
                                    predictions=predictions.astype(float),
                                    actuals=actuals.astype(float),
                                )
                    except Exception as monitor_error:
                        logger.debug(
                            f"[MODEL_MANAGER] Monitoring failed (non-critical): {monitor_error}"
                        )

                # Enrich with Perplexity market intelligence
                if symbol:
                    result = enrich_forecast_with_perplexity(result, symbol)

                return result
            except Exception as e:
                logger.error(f"[INFERENCE] XGBoost predict failed: {e}")
                logger.exception(f"[INFERENCE] XGBoost exception details")

        # Fallback: Return neutral signal if all models fail
        logger.warning(
            "[INFERENCE] ⚠️ Both ensemble and XGBoost prediction failed - returning neutral signal"
        )
        logger.warning(
            "[INFERENCE] This may indicate model loading issues. Check logs for model path errors."
        )

        return {
            "signal": 0,
            "signal_text": "HOLD",
            "confidence": 0.0,
            "ensemble_ready": False,
            "model_used": None,
            "model": "Fallback",
            "timestamp": pd.Timestamp.now(),
            "error": "Both ensemble and XGBoost prediction failed",
            "component_breakdown": {
                "ensemble_forecast": 0,
                "confidence": 0.0,
                "model_used": "fallback",
                "component_weights": {},
                "component_predictions": {},
                "confidence_breakdown": {},
            },
        }
    except Exception as e:
        _log_with_context("ERROR", f"[INFERENCE] Signal generation failed: {str(e)}")
        logger.error(f"[INFERENCE] ❌ Signal generation failed: {e}")
        logger.exception("Signal generation exception")

        # Export feature matrix on error for debugging
        try:
            prepare_features_for_inference(
                df_features, drop_ohlcv=True, export_matrix=True
            )
        except:
            pass

        return {
            "signal": 0,
            "confidence": 0.0,
            "ensemble_ready": False,
            "model_used": None,
            "timestamp": pd.Timestamp.now(),
            "error": str(e),
            "component_breakdown": {
                "ensemble_forecast": 0,
                "confidence": 0.0,
                "model_used": "error",
                "component_weights": {},
                "component_predictions": {},
                "confidence_breakdown": {},
            },
        }


def enrich_forecast_with_perplexity(forecast: dict, symbol: str) -> dict:
    """
    Enrich forecast with Perplexity market intelligence (sentiment, news, analysis).

    Args:
        forecast: Existing forecast dictionary to enrich
        symbol: Stock symbol for intelligence lookup

    Returns:
        Enriched forecast with Perplexity fields added
    """
    if not PERPLEXITY_AVAILABLE:
        logger.debug(
            "[PERPLEXITY] Perplexity connector not available, skipping enrichment"
        )
        return forecast

    try:
        logger.info(
            f"[PERPLEXITY] Enriching forecast with market intelligence for {symbol}..."
        )
        connector = PerplexityConnector()

        # Get market sentiment
        sentiment_data = connector.get_market_sentiment(symbol)

        # Add Perplexity fields to forecast
        forecast["perplexity_sentiment"] = sentiment_data.get("sentiment", "neutral")
        forecast["perplexity_confidence"] = sentiment_data.get("confidence", 0.5)
        forecast["perplexity_analysis"] = sentiment_data.get(
            "analysis", "No analysis available"
        )
        forecast["perplexity_sentiment_score"] = sentiment_data.get(
            "sentiment_score", 0.0
        )

        # Truncate analysis for display
        if len(forecast["perplexity_analysis"]) > 200:
            forecast["news_summary"] = forecast["perplexity_analysis"][:197] + "..."
        else:
            forecast["news_summary"] = forecast["perplexity_analysis"]

        # Optional: Blend sentiment score into confidence (10% weight)
        if "confidence" in forecast and forecast["confidence"] is not None:
            sentiment_weight = 0.1
            sentiment_boost = forecast["perplexity_sentiment_score"] * sentiment_weight
            forecast["confidence_with_sentiment"] = (
                forecast["confidence"] + sentiment_boost
            )
            logger.info(
                f"[PERPLEXITY] Sentiment boost: {sentiment_boost:+.3f} (10% weight)"
            )

        logger.info(
            f"[PERPLEXITY] ✅ Enriched forecast: sentiment={forecast['perplexity_sentiment']}, "
            f"score={forecast['perplexity_sentiment_score']:.2f}, "
            f"confidence={forecast['perplexity_confidence']:.2f}"
        )

    except Exception as e:
        logger.warning(f"[PERPLEXITY] Failed to enrich forecast: {e}")
        # Add placeholder fields on error
        forecast["perplexity_sentiment"] = "unavailable"
        forecast["perplexity_confidence"] = 0.0
        forecast["news_summary"] = "Market intelligence unavailable"
        forecast["perplexity_sentiment_score"] = 0.0

    return forecast


def batch_predict_signals(df_features: pd.DataFrame, models_dict: dict) -> pd.DataFrame:
    logger.info(f"[INFERENCE] Batch predicting {len(df_features)} rows...")
    try:
        df_prep = prepare_features_for_inference(df_features, drop_ohlcv=True)
        if models_dict.get("ensemble") is not None:
            predictions = models_dict["ensemble"].batch_predict(df_prep.values)
            model_used = "ensemble"
        elif models_dict.get("xgboost") is not None:
            predictions = models_dict["xgboost"].predict(df_prep.values)
            model_used = "xgboost"
        else:
            raise ValueError("No models available for batch prediction")
        result_df = pd.DataFrame(
            {
                "Date": df_features["Date"],
                "Signal": predictions,
                "Confidence": 0.7,
                "Model": model_used,
            }
        )
        logger.info(f"[INFERENCE] ✅ Batch prediction complete: {len(result_df)} rows")
        return result_df
    except Exception as e:
        logger.error(f"[INFERENCE] ❌ Batch prediction failed: {e}")
        raise


def signal_to_action(signal: int) -> str:
    signal_map = {-1: "SELL", 0: "HOLD", 1: "BUY"}
    return signal_map.get(signal, "UNKNOWN")


def format_prediction_result(pred_dict: dict) -> dict:
    return {
        "action": signal_to_action(pred_dict["signal"]),
        "signal_raw": pred_dict["signal"],
        "confidence": f"{pred_dict['confidence']*100:.1f}%",
        "confidence_raw": pred_dict["confidence"],
        "model": pred_dict["model_used"],
        "timestamp": pred_dict["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
        "status": "error" if pred_dict.get("error") else "success",
        "error_message": pred_dict.get("error", ""),
    }


def load_kaggle_prophet_ensemble(transformer_model=None):
    """
    Load Kaggle-Prophet Hybrid ensemble model.

    Args:
        transformer_model: Optional transformer model with predict() method

    Returns:
        KaggleProphetHybrid instance or None if loading fails
    """
    if not KAGGLE_HYBRID_AVAILABLE:
        logger.warning("[MODEL] KaggleProphetHybrid module not available")
        return None

    try:
        hybrid = KaggleProphetHybrid(transformer_model=transformer_model)
        logger.info(
            "[MODEL] Kaggle-Prophet Hybrid loaded (untrained - call fit() to train)"
        )
        return hybrid
    except Exception as e:
        logger.error(f"[MODEL] Hybrid load failed: {e}")
        return None


def get_ensemble_breakdown(prediction_result: dict, models_dict: dict) -> dict:
    """
    Get detailed ensemble breakdown for dashboard display.

    Args:
        prediction_result: Result from predict_signal()
        models_dict: Models dictionary from load_ml_models()

    Returns:
        Dictionary with ensemble breakdown details
    """
    breakdown = {
        "signal": prediction_result.get("signal", 0),
        "confidence": prediction_result.get("confidence", 0.0),
        "model_used": prediction_result.get("model_used", "unknown"),
        "components": {},
    }

    # If using Kaggle-Prophet Hybrid, get detailed breakdown
    if models_dict.get("kaggle_prophet") is not None:
        try:
            model = models_dict["kaggle_prophet"]
            model_info = model.get_model_info()

            breakdown["components"] = {
                "transformer": {
                    "weight": model.weights[0],
                    "available": model_info["models"]["transformer"],
                },
                "xgboost": {
                    "weight": model.weights[1],
                    "available": model_info["models"]["xgboost"],
                },
                "bilstm": {
                    "weight": model.weights[2],
                    "available": model_info["models"]["bilstm"],
                },
                "prophet": {
                    "weight": model.weights[3],
                    "available": model_info["models"]["prophet"],
                },
            }

            # Add Prophet-specific info if available
            if model_info["models"]["prophet"]:
                breakdown["prophet_info"] = {
                    "has_regressors": len(model.prophet_regressors) > 0,
                    "regressor_count": len(model.prophet_regressors),
                    "has_custom_holidays": model.custom_holidays is not None,
                    "uncertainty_intervals_enabled": model.use_uncertainty_intervals,
                }
        except Exception as e:
            logger.warning(f"[DASHBOARD] Could not get ensemble breakdown: {e}")

    return breakdown


def format_ensemble_display(breakdown: dict) -> str:
    """
    Format ensemble breakdown for Streamlit display.

    Args:
        breakdown: Breakdown dictionary from get_ensemble_breakdown()

    Returns:
        Formatted string for display
    """
    if not breakdown.get("components"):
        return f"Model: {breakdown.get('model_used', 'unknown')}"

    components = breakdown["components"]
    lines = []

    lines.append("**Ensemble Breakdown:**")
    for component_name, component_info in components.items():
        weight_pct = component_info["weight"] * 100
        status = "✓" if component_info["available"] else "✗"
        lines.append(f"  {status} {component_name.title()}: {weight_pct:.1f}%")

    # Add Prophet-specific details
    if "prophet_info" in breakdown:
        prophet_info = breakdown["prophet_info"]
        if prophet_info["available"]:
            lines.append(f"\n**Prophet Details:**")
            lines.append(f"  Regressors: {prophet_info['regressor_count']}")
            lines.append(
                f"  Custom Holidays: {'Yes' if prophet_info['has_custom_holidays'] else 'No'}"
            )
            lines.append(
                f"  Uncertainty Intervals: {'Enabled' if prophet_info['uncertainty_intervals_enabled'] else 'Disabled'}"
            )

    return "\n".join(lines)


def predict_with_confidence(
    model,
    features: pd.DataFrame,
    method: str = "bootstrap",  # 'bootstrap' or 'quantile'
    confidence_level: float = 0.95,
    n_bootstrap: int = 100,
) -> Dict[str, np.ndarray]:
    """
    Generate predictions with confidence intervals.

    Args:
        model: Trained model (XGBoost, Prophet, or Ensemble)
        features: Feature DataFrame for prediction
        method: 'bootstrap' for bootstrapping, 'quantile' for quantile regression
        confidence_level: Confidence level (e.g., 0.95 for 95% CI)
        n_bootstrap: Number of bootstrap samples

    Returns:
        Dict with keys:
        - 'predictions': Point predictions
        - 'lower_bound': Lower confidence bound
        - 'upper_bound': Upper confidence bound
        - 'std': Standard deviation of predictions
        - 'confidence_level': Confidence level used
        - 'method': Method used ('bootstrap' or 'quantile')
    """
    logger.info(
        f"[PREDICT] Generating predictions with {confidence_level:.0%} confidence intervals (method: {method})"
    )

    if features is None or features.empty:
        raise ValueError("Features DataFrame is empty")

    if method == "bootstrap":
        # Bootstrap method: resample data and aggregate predictions
        predictions_list = []

        for i in range(n_bootstrap):
            try:
                # Resample features with replacement
                sample_idx = np.random.choice(
                    len(features), size=len(features), replace=True
                )
                features_sample = features.iloc[sample_idx]

                # Predict on sample
                if hasattr(model, "predict"):
                    pred = model.predict(features_sample.values)
                elif hasattr(model, "forecast"):
                    pred = model.forecast(features_sample)
                else:
                    logger.warning(
                        f"[PREDICT] Model doesn't have predict() or forecast() method"
                    )
                    # Fallback: single prediction
                    if i == 0:
                        try:
                            pred = model.predict(features.values)
                        except:
                            raise ValueError("Model prediction method not found")
                    else:
                        continue

                # Handle array/list outputs
                if isinstance(pred, (list, tuple)):
                    pred = np.array(pred)
                elif hasattr(pred, "values"):
                    pred = pred.values

                # Ensure 1D array
                if pred.ndim > 1:
                    pred = pred.flatten()

                predictions_list.append(pred)

            except Exception as e:
                logger.warning(f"[PREDICT] Bootstrap sample {i} failed: {e}")
                if i == 0:
                    # First iteration failed - try single prediction
                    try:
                        if hasattr(model, "predict"):
                            pred = model.predict(features.values)
                        elif hasattr(model, "forecast"):
                            pred = model.forecast(features)
                        else:
                            raise ValueError("Model prediction method not found")

                        if isinstance(pred, (list, tuple)):
                            pred = np.array(pred)
                        elif hasattr(pred, "values"):
                            pred = pred.values

                        if pred.ndim > 1:
                            pred = pred.flatten()

                        predictions_list.append(pred)
                        logger.info(f"[PREDICT] Using single prediction as fallback")
                    except Exception as fallback_error:
                        logger.error(
                            f"[PREDICT] Fallback prediction also failed: {fallback_error}"
                        )
                        raise

        if not predictions_list:
            raise ValueError("No successful bootstrap predictions generated")

        # Aggregate bootstrap predictions
        predictions_array = np.array(predictions_list)

        # Calculate point predictions and statistics
        point_predictions = np.mean(predictions_array, axis=0)
        std_predictions = np.std(predictions_array, axis=0)

        # Calculate confidence interval using percentiles
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        lower_bound = np.percentile(predictions_array, lower_percentile, axis=0)
        upper_bound = np.percentile(predictions_array, upper_percentile, axis=0)

        logger.info(
            f"[PREDICT] ✅ Bootstrap complete: {len(predictions_list)} samples, mean std: ${np.mean(std_predictions):.2f}"
        )

    elif method == "quantile":
        # Quantile regression (if model supports it)
        # For now, use simplified approach with multiplier

        try:
            if hasattr(model, "predict"):
                point_predictions = model.predict(features.values)
            elif hasattr(model, "forecast"):
                point_predictions = model.forecast(features)
            else:
                raise ValueError("Model prediction method not found")

            # Handle array/list outputs
            if isinstance(point_predictions, (list, tuple)):
                point_predictions = np.array(point_predictions)
            elif hasattr(point_predictions, "values"):
                point_predictions = point_predictions.values

            # Ensure 1D array
            if point_predictions.ndim > 1:
                point_predictions = point_predictions.flatten()

        except Exception as e:
            logger.error(f"[PREDICT] Quantile method prediction failed: {e}")
            raise

        # Estimate std from residuals (if available)
        # Fallback: use 10% of prediction value as std (conservative)
        std_predictions = np.abs(point_predictions) * 0.10

        # Z-score for confidence level
        try:
            from scipy import stats

            z_score = stats.norm.ppf((1 + confidence_level) / 2)
        except ImportError:
            logger.warning("[PREDICT] scipy not available, using approximate z-score")
            # Approximate z-scores for common confidence levels
            z_score_map = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
            z_score = z_score_map.get(confidence_level, 1.96)

        lower_bound = point_predictions - z_score * std_predictions
        upper_bound = point_predictions + z_score * std_predictions

        logger.info(
            f"[PREDICT] ✅ Quantile method complete: z-score={z_score:.2f}, mean std: ${np.mean(std_predictions):.2f}"
        )

    else:
        raise ValueError(f"Unknown method: {method}. Use 'bootstrap' or 'quantile'")

    # Ensure all outputs are numpy arrays first
    if not isinstance(point_predictions, np.ndarray):
        point_predictions = np.array(point_predictions)
    if not isinstance(lower_bound, np.ndarray):
        lower_bound = np.array(lower_bound)
    if not isinstance(upper_bound, np.ndarray):
        upper_bound = np.array(upper_bound)
    if not isinstance(std_predictions, np.ndarray):
        std_predictions = np.array(std_predictions)

    # Convert numpy arrays to pandas Series
    if isinstance(point_predictions, np.ndarray):
        if point_predictions.size == 1:
            point_predictions = pd.Series([point_predictions.item()])
        else:
            point_predictions = pd.Series(point_predictions)
    elif not isinstance(point_predictions, pd.Series):
        point_predictions = pd.Series(
            [point_predictions] if np.isscalar(point_predictions) else point_predictions
        )

    if isinstance(lower_bound, np.ndarray):
        if lower_bound.size == 1:
            lower_bound = pd.Series([lower_bound.item()])
        else:
            lower_bound = pd.Series(lower_bound)
    elif not isinstance(lower_bound, pd.Series):
        lower_bound = pd.Series(
            [lower_bound] if np.isscalar(lower_bound) else lower_bound
        )

    if isinstance(upper_bound, np.ndarray):
        if upper_bound.size == 1:
            upper_bound = pd.Series([upper_bound.item()])
        else:
            upper_bound = pd.Series(upper_bound)
    elif not isinstance(upper_bound, pd.Series):
        upper_bound = pd.Series(
            [upper_bound] if np.isscalar(upper_bound) else upper_bound
        )

    # Keep std_predictions as numpy array (not used downstream)

    result = {
        "predictions": point_predictions,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "std": std_predictions,
        "confidence_level": confidence_level,
        "method": method,
    }

    logger.info(
        f"[PREDICT] ✅ Generated {len(point_predictions)} predictions with {confidence_level:.0%} CI"
    )

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Minimal training utility (data-efficient, NaN-aware, scaled)
# ──────────────────────────────────────────────────────────────────────────────
def train_model(
    features: pd.DataFrame,
    target: pd.Series,
    *,
    max_window: int = 50,
    drop_ohlcv: bool = True,
    fill_method: str = "ffill",
    model: Any | None = None,
    holdout_ratio: float = 0.2,
    tune_hyperparams: bool = False,
    n_trials: int = 50,
    use_pca: bool = False,
    use_gpu: bool = False,
) -> Dict[str, Any]:
    """
    Train a simple XGBoost regressor on features with minimal NaN handling and scaling.

    - Drops the initial warm-up period (max_window)
    - Optionally drops OHLCV columns
    - Forward/backward fills minimal NaNs, then final dropna
    - Scales features with StandardScaler
    - Optional PCA dimensionality reduction (95% variance retention)
    - 80/20 holdout validation for generalization testing
    - Optional Optuna hyperparameter tuning
    - GPU acceleration support (if CUDA available)

    Args:
        features: Feature DataFrame
        target: Target series (aligned to features index)
        max_window: Warm-up rows to exclude (default: 50)
        drop_ohlcv: Drop raw OHLCV columns (default: True)
        fill_method: NaN imputation method ('ffill' or 'bfill')
        model: Pre-configured model (if None, creates XGBRegressor)
        holdout_ratio: Fraction of data for test set (default: 0.2)
        tune_hyperparams: Enable Optuna hyperparameter tuning (default: False)
        n_trials: Number of Optuna trials (default: 50)
        use_pca: Enable PCA dimensionality reduction (default: False)
        use_gpu: Enable GPU acceleration with tree_method='gpu_hist' (default: False)

    Returns:
        dict with: model, scaler, pca (if enabled), X_shape, y_shape, train_rows, warmup,
                   X_train, y_train, X_test, y_test, test_mse, cv_mse,
                   feature_names, best_params (if tuning enabled)
    """
    if features is None or features.empty:
        raise ValueError("features is empty")
    if target is None or len(target) == 0:
        raise ValueError("target is empty")

    dfX = features.copy()

    # Optionally remove raw OHLCV columns (models typically use engineered features)
    if drop_ohlcv:
        ohlcv_cols = [
            c
            for c in dfX.columns
            if c.lower() in {"open", "high", "low", "close", "volume"}
        ]
        if ohlcv_cols:
            dfX = dfX.drop(columns=ohlcv_cols)

    # Warm-up exclusion
    start_idx = int(max_window) if max_window and max_window > 0 else 0
    dfX = dfX.iloc[start_idx:]
    y = target.iloc[start_idx:]

    # Minimal NaN handling: forward/backward fill then drop residuals
    if fill_method == "ffill":
        dfX = dfX.ffill().bfill()
    elif fill_method == "bfill":
        dfX = dfX.bfill().ffill()

    train_df = dfX.dropna()
    # Align target
    y = y.loc[train_df.index].dropna()
    train_df = train_df.loc[y.index]

    if train_df.empty:
        raise ValueError("No rows left after NaN handling")

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(train_df.values)

    # === PCA DIMENSIONALITY REDUCTION (Optional) ===
    pca = None
    if use_pca:
        try:
            from sklearn.decomposition import PCA

            logger.info(
                f"[TRAIN] Applying PCA (n_components=0.95) on {X_scaled.shape[1]} features"
            )
            pca = PCA(n_components=0.95, random_state=42)  # Retain 95% variance
            X_scaled = pca.fit_transform(X_scaled)

            explained_var = pca.explained_variance_ratio_.sum()
            n_components = pca.n_components_
            logger.info(
                f"[TRAIN] ✅ PCA complete: {X_scaled.shape[1]} dims → {n_components} components "
                f"({explained_var:.1%} variance explained)"
            )
        except ImportError:
            logger.warning("[TRAIN] PCA requested but sklearn not available, skipping")
            use_pca = False
        except Exception as e:
            logger.warning(
                f"[TRAIN] PCA failed: {e}, proceeding without dimensionality reduction"
            )
            use_pca = False

    # === GPU ACCELERATION CHECK (Optional) ===
    tree_method = "hist"  # Default CPU method
    if use_gpu:
        try:
            import torch

            if torch.cuda.is_available():
                tree_method = "gpu_hist"
                logger.info(
                    f"[TRAIN] ✅ CUDA detected: Using tree_method='gpu_hist' for GPU acceleration"
                )
            else:
                logger.warning(
                    "[TRAIN] GPU requested but CUDA not available, using CPU"
                )
        except ImportError:
            logger.warning("[TRAIN] GPU requested but torch not available, using CPU")

    # === HOLDOUT SPLIT (80/20 train/test) ===
    split_idx = int(len(X_scaled) * (1 - holdout_ratio))
    X_train_split = X_scaled[:split_idx]
    X_test_split = X_scaled[split_idx:]
    y_train_split = y.values[:split_idx]
    y_test_split = y.values[split_idx:]

    logger.info(
        f"[TRAIN] Holdout split: {len(X_train_split)} train, {len(X_test_split)} test (ratio={holdout_ratio:.1%})"
    )

    # === OPTUNA HYPERPARAMETER TUNING (optional) ===
    best_params = None
    if tune_hyperparams:
        try:
            import optuna

            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def objective(trial):
                """Optuna objective for hyperparameter search."""
                params = {
                    "n_estimators": 300,
                    "learning_rate": trial.suggest_float(
                        "learning_rate", 0.01, 0.3, log=True
                    ),
                    "max_depth": trial.suggest_int("max_depth", 3, 10),
                    "subsample": trial.suggest_float("subsample", 0.8, 1.0),
                    "colsample_bytree": trial.suggest_float(
                        "colsample_bytree", 0.7, 1.0
                    ),
                    "reg_alpha": trial.suggest_float(
                        "reg_alpha", 0.0, 0.5
                    ),  # L1 regularization
                    "reg_lambda": trial.suggest_float(
                        "reg_lambda", 0.0, 0.5
                    ),  # L2 regularization
                    "random_state": 42,
                    "n_jobs": 4,
                }

                # TimeSeriesSplit CV on training split
                tss = TimeSeriesSplit(n_splits=3)
                cv_scores = []
                temp_model = XGBRegressor(**params)

                for tr_idx, va_idx in tss.split(X_train_split):
                    X_tr, X_va = X_train_split[tr_idx], X_train_split[va_idx]
                    y_tr, y_va = y_train_split[tr_idx], y_train_split[va_idx]
                    temp_model.fit(X_tr, y_tr)
                    pred_va = temp_model.predict(X_va)
                    mse = float(mean_squared_error(y_va, pred_va))
                    cv_scores.append(mse)

                return float(np.mean(cv_scores))

            logger.info(
                f"[TRAIN] Starting Optuna hyperparameter search ({n_trials} trials)..."
            )
            study = optuna.create_study(
                direction="minimize", study_name="xgboost_tuning"
            )
            study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

            best_params = study.best_params
            best_params.update(
                {
                    "n_estimators": 300,
                    "random_state": 42,
                    "n_jobs": 4,
                }
            )

            logger.info(
                f"[TRAIN] ✅ Optuna complete: best_cv_mse={study.best_value:.6f}"
            )
            logger.info(f"[TRAIN] Best params: {best_params}")

        except ImportError:
            logger.warning(
                "[TRAIN] Optuna not available, skipping hyperparameter tuning"
            )
            tune_hyperparams = False

    # Model setup (use tuned params if available)
    if model is None:
        if not XGB_AVAILABLE:
            raise ImportError("xgboost is not available; cannot train default model")

        if tune_hyperparams and best_params:
            # Add tree_method to best_params
            best_params["tree_method"] = tree_method
            model = XGBRegressor(**best_params)
        else:
            model = XGBRegressor(
                n_estimators=300,
                learning_rate=0.1,
                max_depth=6,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_lambda=0.1,  # L2 regularization to prevent overfitting
                tree_method=tree_method,  # GPU or CPU
                random_state=42,
                n_jobs=4,
            )

    # TimeSeriesSplit validation on training split (quick sanity check)
    cv_mse_list = []
    try:
        tss = TimeSeriesSplit(n_splits=3)
        for tr_idx, va_idx in tss.split(X_train_split):
            X_tr, X_va = X_train_split[tr_idx], X_train_split[va_idx]
            y_tr, y_va = y_train_split[tr_idx], y_train_split[va_idx]
            model.fit(X_tr, y_tr)
            pred_va = model.predict(X_va)
            cv_mse_list.append(float(mean_squared_error(y_va, pred_va)))
        logger.info(
            f"[TRAIN] CV MSE (mean over {len(cv_mse_list)} folds): {np.mean(cv_mse_list):.6f}"
        )
    except Exception as e:
        logger.debug(f"[TRAIN] CV skipped: {e}")

    # Final fit on full training split
    model.fit(X_train_split, y_train_split)

    # === HOLDOUT TEST EVALUATION ===
    test_preds = model.predict(X_test_split)
    test_mse = float(mean_squared_error(y_test_split, test_preds))
    test_rmse = float(np.sqrt(test_mse))

    logger.info(
        f"[TRAIN] Training on {len(X_train_split)} rows (maximized from original {len(features)})"
    )
    logger.info(f"[TRAIN] ✅ Holdout Test MSE: {test_mse:.6f}, RMSE: {test_rmse:.6f}")

    # Check for overfitting warning
    if cv_mse_list and test_mse > np.mean(cv_mse_list) * 1.5:
        logger.warning(
            f"[TRAIN] ⚠️ Potential overfitting: test_mse ({test_mse:.6f}) >> cv_mse ({np.mean(cv_mse_list):.6f})"
        )

    return {
        "model": model,
        "scaler": scaler,
        "pca": pca,  # PCA object (None if not used)
        "X_shape": X_scaled.shape,
        "y_shape": y.shape,
        "train_rows": int(len(X_train_split)),
        "test_rows": int(len(X_test_split)),
        "warmup": int(start_idx),
        "X_train": X_train_split,  # Training split (scaled, PCA-transformed if enabled)
        "y_train": y_train_split,  # Training targets
        "X_test": X_test_split,  # Test split (scaled, PCA-transformed if enabled)
        "y_test": y_test_split,  # Test targets
        "test_mse": test_mse,
        "test_rmse": test_rmse,
        "cv_mse": float(np.mean(cv_mse_list)) if cv_mse_list else None,
        "feature_names": list(train_df.columns),  # Original column names (before PCA)
        "best_params": best_params,  # Optuna best params (if tuning enabled)
        "n_components": (
            pca.n_components_ if pca is not None else None
        ),  # PCA components count
        "tree_method": tree_method,  # GPU or CPU
    }
