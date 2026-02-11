# Dashboard Troubleshooting Guide

This guide covers common issues, failure modes, and recovery steps for the Unified ML Trading Dashboard.

## Table of Contents

1. [Model Loading Failures](#model-loading-failures)
2. [Cache Issues](#cache-issues)
3. [Data Pipeline Errors](#data-pipeline-errors)
4. [UI/Display Issues](#ui-display-issues)
5. [Import Errors](#import-errors)
6. [Performance Issues](#performance-issues)

---

## Model Loading Failures

### Symptoms
- Dashboard loads but shows "⚠️ ML Model unavailable - predictions disabled"
- Terminal logs show "❌ XGBoost load failed" or similar errors
- Health check shows "degraded" or "unhealthy" status

### Common Causes

#### 1. Model File Not Found
**Error Message:**
```
Model not found at ./xgboost_tuned_model.pkl
```

**Recovery Steps:**
1. Verify the model file exists:
   ```bash
   ls -lh ./xgboost_tuned_model.pkl
   ```

2. Check the expected location. Models are searched in this order:
   - Environment variable `MODEL_PATH` (if set)
   - `main_production_system/config/model_config.yaml` (if exists)
   - Default: `./xgboost_tuned_model.pkl` (project root)

3. Set the correct path:
   ```bash
   # Option 1: Set environment variable
   export MODEL_PATH="/path/to/your/model.pkl"
   
   # Option 2: Update config file
   # Edit main_production_system/config/model_config.yaml
   ```

4. Move model to expected location:
   ```bash
   mv /path/to/model.pkl ./xgboost_tuned_model.pkl
   ```

#### 2. Model File Corrupted
**Error Message:**
```
ValueError: XGBoost model missing predict() method
```

**Recovery Steps:**
1. Verify model file integrity:
   ```bash
   python3 -c "import pickle; f=open('xgboost_tuned_model.pkl','rb'); pickle.load(f)"
   ```

2. If file is corrupted:
   - Restore from backup if available
   - Re-train the model if needed
   - Check disk space and file permissions

#### 3. Model Loading Timeout
**Error Message:**
```
⏱️ Timeout after 30s loading model
```

**Recovery Steps:**
1. Check system resources (CPU, memory, disk I/O)
2. Increase timeout in `model_config.yaml`:
   ```yaml
   models:
     xgboost:
       timeout_seconds: 60  # Increase from 30
   ```
3. Verify no other processes are blocking file access
4. Try reloading models via the "🔄 Reload ML Models" button in sidebar

### UI Fallback Locations

When models fail to load:
- **Sidebar**: Shows warning message with expected model path
- **Health Check**: Displays "degraded" status
- **Logs**: Detailed error in `main_production_system/logs/dashboard.log`

The dashboard continues to function for data visualization and non-ML features.

---

## Cache Issues

### Symptoms
- Models not reloading after update
- Stale data displayed
- "Cache cleared" messages but changes not reflected

### Recovery Steps

#### Clear Streamlit Cache

**Method 1: Via UI**
1. Click "⚡" button in sidebar (force reload)
2. Or click "🔄 Reload ML Models" button

**Method 2: Via Command Line**
```bash
# Clear Streamlit cache
rm -rf ~/.streamlit/cache/
```

**Method 3: Programmatic**
```python
import streamlit as st
st.cache_resource.clear()
st.cache_data.clear()
```

#### Clear Session State

If cache clearing doesn't work:
1. Restart the Streamlit app (Ctrl+C, then restart)
2. Clear browser cache and refresh
3. Use incognito/private browsing mode

---

## Data Pipeline Errors

### Symptoms
- "❌ Data pipeline unavailable" error
- Data loading fails with friendly error messages
- No data displayed for symbols

### Common Causes

#### 1. API Key Missing
**Error:** "API key not configured"

**Recovery:**
1. Check environment variables:
   ```bash
   echo $POLYGON_API_KEY
   echo $ALPHA_VANTAGE_API_KEY
   ```
2. Set API keys:
   ```bash
   export POLYGON_API_KEY="your_key_here"
   ```
3. Or configure in `.env` file (if supported)

#### 2. Network/API Rate Limiting
**Error:** "Rate limit exceeded" or timeout errors

**Recovery:**
1. Wait and retry after rate limit window
2. Switch to alternative data provider (use Polygon toggle)
3. Check API quota/billing status

#### 3. Invalid Symbol
**Error:** "No data for SYMBOL"

**Recovery:**
1. Verify symbol is valid and actively traded
2. Try different timeframe (1h, 4h, 1d)
3. Check if market is open (for intraday data)

---

## UI/Display Issues

### Symptoms
- Dashboard shows blank page
- Browser shows default Firefox/Chrome page instead of dashboard
- Terminal shows "You can now view your Streamlit app" but nothing loads

### Recovery Steps

#### 1. Verify Streamlit is Running
```bash
# Check if process is running
ps aux | grep streamlit

# Check if port 8501 is in use
lsof -i :8501
```

#### 2. Check for Import Errors
Look for errors in terminal output during startup:
```
❌ Failed to load trading_page: ...
```

**Fix:** Check that all dependencies are installed:
```bash
pip install -r requirements.txt
```

#### 3. Check for Syntax Errors
```bash
python3 -m py_compile main_production_system/dashboard/unified_dashboard.py
```

#### 4. Clear Browser Cache
- Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
- Or use incognito/private browsing mode

#### 5. Check Logs
```bash
tail -f main_production_system/logs/dashboard.log
```

---

## Import Errors

### Symptoms
- "ModuleNotFoundError" in terminal
- "Failed to load trading_page" or similar
- Dashboard fails to start

### Common Fixes

#### 1. Python Path Issues
**Error:** `ModuleNotFoundError: No module named 'main_production_system'`

**Fix:**
1. Ensure you're running from project root:
   ```bash
   cd "/Users/ericpeterson/Attention-Based Multi-Timeframe-Transformer"
   streamlit run main_production_system/dashboard/unified_dashboard.py
   ```

2. Check PYTHONPATH:
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

#### 2. Missing Dependencies
**Error:** `ImportError: No module named 'streamlit'`

**Fix:**
```bash
pip install -r requirements.txt
# Or specific package
pip install streamlit pandas numpy plotly
```

#### 3. Virtual Environment Not Activated
**Fix:**
```bash
source .venv/bin/activate  # Or your venv path
```

---

## Performance Issues

### Symptoms
- Dashboard loads slowly (>10 seconds)
- UI freezes during model loading
- High CPU/memory usage

### Optimization Steps

#### 1. Reduce Lookback Period
In sidebar, reduce "Days Back" slider (default: 30, try 15)

#### 2. Disable Unused Models
Edit `model_config.yaml`:
```yaml
models:
  kaggle_prophet_hybrid:
    enabled: false  # Disable if not needed
```

#### 3. Check Logs for Timeouts
```bash
grep "Timeout" main_production_system/logs/dashboard.log
```

#### 4. Monitor System Resources
```bash
# Check memory usage
top -p $(pgrep -f streamlit)

# Check disk I/O
iostat -x 1
```

---

## How to Reload or Reset

### Reload Models (Without Restart)
1. Use "🔄 Reload ML Models" button in sidebar
2. Or clear cache and rerun:
   ```python
   st.cache_resource.clear()
   ```

### Reset Session State
1. Click "⚡" (force reload) button
2. Or restart Streamlit app

### Full Reset
1. Stop Streamlit (Ctrl+C)
2. Clear cache: `rm -rf ~/.streamlit/cache/`
3. Clear logs: `rm main_production_system/logs/dashboard.log`
4. Restart: `streamlit run main_production_system/dashboard/unified_dashboard.py`

---

## Getting Help

### Check Logs
Primary log location:
```
main_production_system/logs/dashboard.log
```

View recent errors:
```bash
tail -n 100 main_production_system/logs/dashboard.log | grep -i error
```

### Report Issues
1. Use "📋 Report Issue" button in sidebar
2. Include:
   - Error messages from logs
   - Steps to reproduce
   - Environment details (Python version, OS)

### Common Log Locations
- Dashboard logs: `main_production_system/logs/dashboard.log`
- Streamlit logs: Terminal output
- System logs: `~/Library/Logs/` (macOS) or `/var/log/` (Linux)

---

## Prevention Best Practices

1. **Keep Models Backed Up**
   - Version control model files (if small)
   - Store backups separately
   - Document model training dates

2. **Monitor Health Checks**
   - Check health status regularly
   - Set up alerts for "unhealthy" status

3. **Test After Updates**
   - Test dashboard after dependency updates
   - Verify model loading after model updates

4. **Document Configuration**
   - Keep `model_config.yaml` in version control
   - Document environment variables needed

5. **Regular Maintenance**
   - Rotate logs (automatic with rotating handler)
   - Clear old cache periodically
   - Monitor disk space
