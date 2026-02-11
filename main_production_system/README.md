# ML Analysis Platform - KDJ Enhanced Production System

## 🚀 Overview

This is the **production-ready KDJ-Enhanced Hybrid Ensemble System** for stock market prediction. It combines XGBoost machine learning with KDJ technical indicators and ARIMA-GARCH time series analysis for superior forecasting performance.

## 📊 Key Features

### ✅ KDJ-Enhanced XGBoost
- **31 features** including 5 KDJ (Stochastic) technical indicators
- **Data leakage prevention** with proper time-series validation
- **Hyperparameter optimization** using GridSearchCV
- **2-3% improvement** over baseline models

### ✅ Hybrid Ensemble System
- **Weighted combination** of XGBoost (60%) + ARIMA-GARCH (40%)
- **Confidence scoring** based on model agreement
- **Directional signals** (UP/DOWN/NEUTRAL) for trading decisions
- **Real-time predictions** with <100ms latency

### ✅ Production Monitoring
- **Real-time performance tracking** with 7+ metrics
- **6 alert types** for model degradation detection
- **Drift detection** using statistical tests
- **Automated reporting** with health assessments

### ✅ Interactive Dashboard
- **Streamlit web interface** for live predictions
- **Feature importance analysis** with KDJ breakdown
- **Performance monitoring** with real-time charts
- **Configuration management** for ensemble weights

## 📁 System Architecture

```
main_production_system/
├── core/
│   ├── data_processor.py          # Data loading & validation
│   ├── kdj_feature_engineer.py    # KDJ indicator calculation
│   ├── xgboost_trainer.py         # ML model training
│   └── hybrid_ensemble.py         # Ensemble system
├── monitoring/
│   └── production_monitor.py      # Real-time monitoring
├── dashboard/
│   └── main_dashboard.py          # Streamlit interface
├── config/
│   └── production_config.json     # System configuration
└── main_app.py                    # Main application runner
```

## 🚀 Quick Start

### 1. Load Pre-trained Model
```bash
# Ensure your trained model exists
ls -la xgboost_tuned_model.pkl  # Should show ~523KB file
```

### 2. Run Dashboard
```bash
cd main_production_system
python main_app.py --mode dashboard
# Navigate to http://localhost:8501
```

### 3. Make Predictions
```bash
# Batch predictions
python main_app.py --mode predict --data CRWD_engineered.csv --output prediction_results.json
```

### 4. Monitor Performance
```bash
# Run monitoring check
python main_app.py --mode monitor
```

### 5. Check System Status
```bash
# Get system status
python main_app.py --mode status
```

## 📊 Performance Results

### Current Production Model
- **Cross-Validation MAE**: 18.47
- **Hold-out MAE**: 11.68 (33% better than baseline)
- **MAPE**: 2.58% (excellent accuracy)
- **Directional Accuracy**: 60-65% (vs 50% baseline)

### KDJ Enhancement Results
| Dataset | MAE Improvement | Directional Accuracy | KDJ Importance |
|---------|----------------|---------------------|----------------|
| **CRWD** | **+2.7%** | **+2.7%** (64.0% → 66.7%) | 4.2% |
| **CLSK** | **+3.1%** | **+2.3%** (47.8% → 50.1%) | 2.1% |
| **Average** | **+2.9%** | **+2.5%** | 3.2% |

## 🔧 Configuration

### Ensemble Weights (Adjustable)
```json
{
  "ensemble_weights": {
    "xgboost": 0.6,
    "arima_garch": 0.4
  }
}
```

### KDJ Parameters
```json
{
  "kdj_period": 9,
  "k_smooth": 3,
  "d_smooth": 3
}
```

### Alert Thresholds
```json
{
  "alert_thresholds": {
    "mae_degradation": 15.0,
    "accuracy_drop": 50.0,
    "drift_threshold": 0.05,
    "latency_threshold": 100.0
  }
}
```

## 📈 Dashboard Usage

### 1. Live Predictions Tab
- Upload CSV data or enter manual OHLC values
- Generate ensemble predictions with confidence scores
- View component predictions (XGBoost + ARIMA)
- Get directional signals for trading decisions

### 2. Model Performance Tab
- View feature importance rankings
- Analyze KDJ indicator contributions
- Compare model components
- Track performance metrics

### 3. Feature Analysis Tab
- Explore KDJ indicator configuration
- Demo feature engineering process
- Validate feature quality
- Group features by type

### 4. Monitoring Tab
- Real-time system health status
- Performance trend analysis
- Alert history and severity
- Prediction latency tracking

### 5. Configuration Tab
- Adjust ensemble weights
- Update prediction thresholds
- Modify alert settings
- Save configuration changes

## 🏗️ Development Workflow

### Training New Models
```bash
# Train on new data
python main_app.py --mode train --data new_data.csv
```

### Updating Features
```python
# Modify KDJ parameters
from core.kdj_feature_engineer import KDJFeatureEngineer
engineer = KDJFeatureEngineer()
engineer.update_config({'kdj_period': 14})  # Try 14-period instead of 9
```

### Monitoring Setup
```python
# Initialize monitoring
from monitoring.production_monitor import ProductionMonitor
monitor = ProductionMonitor()
monitor.update_alert_thresholds({'mae_degradation': 10.0})  # Stricter threshold
```

## 📊 Monitoring & Alerts

### Health Status Levels
- **🟢 HEALTHY**: All systems operating optimally
- **🟡 MONITORING**: Performance below optimal but stable
- **🔴 DEGRADED**: Critical issues detected, intervention needed

### Alert Types
1. **MAE Degradation**: >15% increase in mean absolute error
2. **RMSE Degradation**: >15% increase in root mean squared error
3. **Accuracy Drop**: Directional accuracy below 50%
4. **Ensemble Improvement**: Improvement below 5%
5. **Drift Detection**: Statistical drift detected (p<0.05)
6. **Latency Alert**: Prediction time >100ms

## 🔍 Troubleshooting

### Model Loading Issues
```bash
# Check model file exists and is readable
ls -la xgboost_tuned_model.pkl
python -c "import joblib; model = joblib.load('xgboost_tuned_model.pkl'); print('Model loaded successfully')"
```

### Dashboard Won't Start
```bash
# Install/update Streamlit
pip install streamlit plotly

# Run dashboard directly
streamlit run main_production_system/dashboard/main_dashboard.py
```

### Prediction Errors
```bash
# Test with sample data
python main_app.py --mode predict --data CRWD_engineered.csv
```

### Performance Issues
- **Check data quality**: Ensure OHLC relationships are valid
- **Verify features**: Run feature validation on input data
- **Monitor alerts**: Check for drift or degradation warnings

## 📚 API Reference

### Core Classes

#### `HybridEnsemble`
Main ensemble system combining XGBoost and ARIMA-GARCH.
```python
ensemble = HybridEnsemble()
ensemble.load_models('xgboost_tuned_model.pkl')
prediction = ensemble.predict(data)
```

#### `KDJFeatureEngineer`
Handles KDJ indicator calculation and feature engineering.
```python
engineer = KDJFeatureEngineer()
features = engineer.create_features(data, include_kdj=True)
```

#### `ProductionMonitor`
Real-time monitoring and alerting system.
```python
monitor = ProductionMonitor()
monitor.record_metrics(performance_metrics)
health = monitor.get_model_health()
```

## 📊 Legacy System Archive

All previous version files have been moved to `archive_v1_legacy/` including:
- Legacy Python scripts
- Old documentation
- Previous analysis reports
- Experimental notebooks

## 🚀 Next Steps

1. **Production Deployment**: Deploy to server environment
2. **API Integration**: Wrap in FastAPI for REST endpoints
3. **Scheduled Retraining**: Set up automated model updates
4. **Dashboard Enhancement**: Add more visualization features
5. **Performance Optimization**: Profile and optimize latency

## 📞 Support

For issues or questions:
1. Check troubleshooting section above
2. Review monitoring reports for system health
3. Analyze feature validation results
4. Verify model file integrity

---

**Version**: 2.0.0 (KDJ-Enhanced)  
**Last Updated**: October 22, 2025  
**Status**: ✅ Production Ready
---

## 🎛️ Unified Dashboard Configuration

The Unified ML Trading Dashboard supports flexible configuration for model paths and settings.

### Model Path Configuration

Models are searched in this priority order:

1. **Environment Variable** (highest priority)
   ```bash
   export MODEL_PATH="/path/to/your/model.pkl"
   ```

2. **Configuration File**
   Edit `main_production_system/config/model_config.yaml`:
   ```yaml
   models:
     xgboost:
       enabled: true
       path: "./xgboost_tuned_model.pkl"
       timeout_seconds: 30
   ```

3. **Default Location** (fallback)
   - `./xgboost_tuned_model.pkl` (project root)

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MODEL_PATH` | Path to XGBoost model file | `./xgboost_tuned_model.pkl` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

### Model Configuration File

Location: `main_production_system/config/model_config.yaml`

```yaml
models:
  xgboost:
    enabled: true
    path: "./xgboost_tuned_model.pkl"
    timeout_seconds: 30
  kaggle_prophet_hybrid:
    enabled: true
    timeout_seconds: 45
  ensemble:
    enabled: true
    timeout_seconds: 30

settings:
  default_model_dir: "./"
  fail_fast: false
  log_level: "INFO"
```

### Logging Configuration

Dashboard logs are written to:
- **File**: `main_production_system/logs/dashboard.log` (rotating, 10MB max, 5 backups)
- **Console**: Terminal output

Configure log level:
```bash
export LOG_LEVEL=DEBUG  # or INFO, WARNING, ERROR
```

### Health Check

The dashboard includes built-in health monitoring:
- Check status in sidebar
- View model load status
- Monitor data pipeline availability

### Troubleshooting

For detailed troubleshooting, see:
- `main_production_system/dashboard/TROUBLESHOOTING.md`

Common issues:
- **Model not found**: Check `MODEL_PATH` or config file
- **Dashboard won't load**: Check logs in `main_production_system/logs/dashboard.log`
- **Import errors**: Ensure virtual environment is activated

