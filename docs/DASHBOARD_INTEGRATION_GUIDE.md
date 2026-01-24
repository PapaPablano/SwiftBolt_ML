# Dashboard Integration Guide: Validation Reconciliation Tab

**Objective**: Add a new dashboard tab that shows how backtesting (98.8%), walk-forward (78%), and live (40%) metrics reconcile into a single unified confidence score.

**Status**: Ready to implement  
**Complexity**: Medium (4-6 hours of work)  
**Files to Modify**: `ml/src/dashboard/forecast_dashboard.py`  
**Files to Create**: `ml/src/dashboard/validation_reconciliation.py`

---

## Overview: The Problem We're Solving

### Current State (Confusing)
```
Dashboard shows 3 conflicting metrics:

✅ Statistical Validation Tab: 98.8% accuracy (3-month historical)
🟡 Live AAPL Forecast: 40% BEARISH (real-time prediction)
📊 Multi-TF Bars: M15: -48%, H1: -40%, D1: +60%, W1: +70% (across timeframes)

User's Question: "Which one do I trust?"
```

### New State (Clear)
```
Validation Reconciliation Tab shows:

🟡 Unified Confidence: 58% (TRADE WITH CAUTION)

Explanation:
├─ Backtesting:  98.8% (40% weight) ✅
├─ Walk-forward: 78%   (35% weight) 🟡
├─ Live:         40%   (25% weight) ❌
└─ Weighted Average: 0.40 × 98.8% + 0.35 × 78% + 0.25 × 40% = 71% (before adjustments)

Drift Analysis:
├─ Drift Detected: YES
├─ Magnitude: 58% (live vs backtesting gap)
├─ Severity: SEVERE
└─ Explanation: Live performance (40%) is 58% lower than historical (98.8%)

Multi-Timeframe Consensus:
├─ Consensus: BULLISH (weighted by hierarchy)
├─ Conflict: YES (intraday bearish vs daily bullish)
├─ W1: +70% (35% weight)
├─ D1: +60% (25% weight)
├─ H4: -35% (20% weight)
├─ H1: -40% (15% weight)
└─ M15: -48% (5% weight)

Recommendation: "Moderate confidence - trade with normal risk"
```

---

## Step 1: Create validation_reconciliation.py

**File**: `ml/src/dashboard/validation_reconciliation.py`

This new module contains all dashboard rendering logic for the Validation Reconciliation tab.

```python
"""
Validation Reconciliation Dashboard Tab

Displays unified validation metrics with drift analysis and multi-TF reconciliation.

Integrates with:
- validation_service.ValidationService
- validation_api endpoints
- Streamlit UI components
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import pandas as pd
import requests

logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8000/api/validation"


def fetch_unified_validation(symbol: str, direction: str = "BULLISH") -> Optional[Dict]:
    """
    Fetch unified validation from API.
    
    Args:
        symbol: Trading symbol
        direction: Prediction direction
    
    Returns:
        Validation result dict or None if error
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/unified/{symbol}/{direction}",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching validation: {e}")
        st.error(f"Failed to fetch validation: {e}")
        return None


def fetch_validation_history(symbol: str, days: int = 7) -> Optional[Dict]:
    """
    Fetch validation history from API.
    
    Args:
        symbol: Trading symbol
        days: Number of days of history
    
    Returns:
        History dict or None if error
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/history/{symbol}",
            params={"days": days, "limit": 100},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return None


def render_validation_reconciliation(symbols: list):
    """
    Main render function for Validation Reconciliation tab.
    
    Args:
        symbols: List of available trading symbols
    """
    st.title("🔄 Validation Reconciliation")
    st.markdown(
        "*Shows how backtesting, walk-forward, and live metrics combine into a "
        "single unified confidence score with drift analysis*"
    )
    
    # Sidebar: Symbol and direction selection
    col_symbol, col_direction = st.columns(2)
    
    with col_symbol:
        symbol = st.selectbox("Select Symbol", symbols, key="val_symbol")
    
    with col_direction:
        direction = st.selectbox(
            "Prediction Direction",
            ["BULLISH", "BEARISH", "NEUTRAL"],
            index=0,
            key="val_direction"
        )
    
    # Fetch unified validation
    st.markdown("---")
    
    with st.spinner(f"Fetching validation for {symbol}..."):
        validation = fetch_unified_validation(symbol, direction)
    
    if not validation:
        st.error("Failed to load validation data")
        return
    
    # Display unified confidence (HERO METRIC)
    st.markdown("## 📊 Unified Confidence Score")
    
    col_conf, col_status, col_drift = st.columns(3)
    
    with col_conf:
        confidence = validation["unified_confidence"]
        emoji = "🟢" if confidence >= 0.75 else "🟡" if confidence >= 0.60 else "🟠" if confidence >= 0.45 else "🔴"
        st.metric(
            "Unified Confidence",
            f"{confidence:.1%}",
            help="Weighted combination of backtesting, walk-forward, and live scores"
        )
        st.write(f"{emoji} {validation['status']}")
    
    with col_status:
        drift = validation["drift"]
        st.metric(
            "Drift Severity",
            drift["severity"].upper(),
            help=drift["explanation"][:100] + "..."
        )
        st.write(f"Magnitude: {drift['magnitude']:.1%}")
    
    with col_drift:
        if drift["detected"]:
            st.warning("⚠️ Drift Detected")
            if validation["retraining"]["trigger"]:
                st.error(f"🔴 RETRAIN NOW\n{validation['retraining']['reason']}")
            else:
                st.info(f"🟡 Monitor for retraining")
        else:
            st.success("✅ Model Healthy")
    
    st.markdown("---")
    
    # Component Breakdown
    st.markdown("## 📈 Component Scores")
    
    components = validation["components"]
    
    # Create horizontal bar chart with weights
    component_data = [
        {"Component": "Backtesting (40%)", "Score": components["backtesting_score"]},
        {"Component": "Walk-Forward (35%)", "Score": components["walkforward_score"]},
        {"Component": "Live (25%)", "Score": components["live_score"]},
    ]
    
    df_components = pd.DataFrame(component_data)
    
    fig_components = px.bar(
        df_components,
        y="Component",
        x="Score",
        orientation="h",
        color="Score",
        color_continuous_scale=["#ff5252", "#ffc107", "#00c853"],
        range_x=[0, 1],
        text=[f"{s:.1%}" for s in df_components["Score"]],
    )
    
    # Add unified confidence line
    fig_components.add_vline(
        x=validation["unified_confidence"],
        line_dash="dash",
        line_color="white",
        line_width=3,
        annotation_text=f"Unified: {validation['unified_confidence']:.1%}",
        annotation_position="top right",
    )
    
    fig_components.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        xaxis_title="Accuracy Score",
        yaxis_title="",
        showlegend=False,
        coloraxis_showscale=False,
        height=300,
    )
    
    st.plotly_chart(fig_components, use_container_width=True)
    
    st.markdown("---")
    
    # Drift Analysis
    st.markdown("## ⚠️ Drift Analysis")
    
    col_drift_info, col_drift_detail = st.columns(2)
    
    with col_drift_info:
        st.write("**Drift Detection Summary**")
        st.write(f"- **Detected**: {drift['detected']}")
        st.write(f"- **Magnitude**: {drift['magnitude']:.1%}")
        st.write(f"- **Severity**: {drift['severity'].upper()}")
        st.write(f"- **Trend**: {'Increasing' if drift['magnitude'] > 0.5 else 'Moderate' if drift['magnitude'] > 0.25 else 'Stable'}")
    
    with col_drift_detail:
        st.write("**Explanation**")
        st.info(drift["explanation"])
    
    st.markdown("---")
    
    # Multi-Timeframe Reconciliation
    st.markdown("## 📊 Multi-Timeframe Consensus")
    
    multi_tf = validation["multi_tf"]
    
    col_consensus, col_breakdown = st.columns(2)
    
    with col_consensus:
        st.write("**Consensus Information**")
        st.write(f"- **Direction**: {multi_tf['consensus']}")
        st.write(f"- **Conflict**: {'YES ⚠️' if multi_tf['conflict'] else 'NO ✅'}")
        st.write(f"- **Explanation**: {multi_tf['explanation']}")
    
    with col_breakdown:
        st.write("**Timeframe Breakdown**")
        
        # Multi-TF bar chart
        tf_scores = multi_tf["breakdown"]
        tf_df = pd.DataFrame([
            {"Timeframe": tf, "Score": score}
            for tf, score in tf_scores.items()
        ])
        
        fig_tf = px.bar(
            tf_df,
            x="Timeframe",
            y="Score",
            color="Score",
            color_continuous_scale=["#ff5252", "white", "#00c853"],
            range_y=[-1, 1],
        )
        
        fig_tf.add_hline(
            y=0,
            line_dash="dash",
            line_color="white",
            opacity=0.5
        )
        
        fig_tf.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            xaxis_title="",
            yaxis_title="Score (-1 to +1)",
            showlegend=False,
            coloraxis_showscale=False,
            height=300,
        )
        
        st.plotly_chart(fig_tf, use_container_width=True)
    
    st.markdown("---")
    
    # Confidence Adjustments
    st.markdown("## 🔧 Confidence Adjustments")
    
    st.write("The unified confidence is adjusted based on drift and conflicts:")
    
    for adjustment in validation["adjustments"]:
        if "+" in adjustment:
            st.success(f"✅ {adjustment}")
        else:
            st.warning(f"⚠️ {adjustment}")
    
    st.markdown("---")
    
    # Trading Recommendation
    st.markdown("## 💡 Trading Recommendation")
    
    confidence = validation["unified_confidence"]
    recommendation = validation["recommendation"]
    
    if confidence >= 0.75:
        st.success(f"🟢 **HIGH CONFIDENCE**\n\n{recommendation}")
    elif confidence >= 0.60:
        st.info(f"🟡 **MODERATE CONFIDENCE**\n\n{recommendation}")
    elif confidence >= 0.45:
        st.warning(f"🟠 **LOW CONFIDENCE**\n\n{recommendation}")
    else:
        st.error(f"🔴 **VERY LOW CONFIDENCE**\n\n{recommendation}")
    
    st.markdown("---")
    
    # Retraining Information
    retraining = validation["retraining"]
    
    st.markdown("## 🔄 Retraining Status")
    
    col_retrain_status, col_retrain_schedule = st.columns(2)
    
    with col_retrain_status:
        if retraining["trigger"]:
            st.error(f"**⚠️ RETRAINING REQUIRED**\n\n{retraining['reason']}")
        else:
            st.success(f"**✅ No Retraining Needed**\n\n{retraining['reason']}")
    
    with col_retrain_schedule:
        if retraining["next_date"]:
            st.write(f"**Next Evaluation**: {retraining['next_date']}")
    
    st.markdown("---")
    
    # Historical Trend
    st.markdown("## 📈 Confidence Trend")
    
    history = fetch_validation_history(symbol, days=7)
    
    if history and history.get("history"):
        # Convert history to DataFrame
        hist_data = []
        for record in history["history"]:
            hist_data.append({
                "Timestamp": pd.to_datetime(record["timestamp"]),
                "Confidence": record["unified_confidence"],
                "Drift Magnitude": record["drift_magnitude"],
            })
        
        df_hist = pd.DataFrame(hist_data)
        df_hist = df_hist.sort_values("Timestamp")
        
        # Create dual-axis chart
        fig_hist = px.line(
            df_hist,
            x="Timestamp",
            y="Confidence",
            markers=True,
            title="Confidence Over Time (Last 7 Days)",
        )
        
        fig_hist.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            xaxis_title="Time",
            yaxis_title="Confidence",
            yaxis_range=[0, 1],
            height=400,
        )
        
        st.plotly_chart(fig_hist, use_container_width=True)
        
        # Show trend summary
        trend = history.get("trend", {})
        col_trend_1, col_trend_2, col_trend_3, col_trend_4 = st.columns(4)
        
        with col_trend_1:
            st.metric("Avg Confidence", f"{trend.get('avg_confidence', 0):.1%}")
        
        with col_trend_2:
            st.metric("Min Confidence", f"{trend.get('min_confidence', 0):.1%}")
        
        with col_trend_3:
            st.metric("Max Confidence", f"{trend.get('max_confidence', 0):.1%}")
        
        with col_trend_4:
            st.metric("Drift Trend", trend.get("drift_trend", "unknown").upper())
    else:
        st.info("Insufficient historical data for trend analysis")
    
    st.markdown("---")
    
    # Export validation result
    st.markdown("## 📥 Export")
    
    import json
    
    json_str = json.dumps(validation, indent=2, default=str)
    
    st.download_button(
        label="Download Validation as JSON",
        data=json_str,
        file_name=f"validation_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
    )


if __name__ == "__main__":
    # Test locally
    render_validation_reconciliation(["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"])
```

---

## Step 2: Integrate into forecast_dashboard.py

Modify `ml/src/dashboard/forecast_dashboard.py` to add the new tab:

```python
# At the top of the file, add import
from src.dashboard.validation_reconciliation import render_validation_reconciliation

# In render_sidebar() function, update view options:
def render_sidebar():
    """Render sidebar with filters and controls."""
    st.sidebar.title("📈 SwiftBolt ML")
    st.sidebar.markdown("---")

    # View selection - ADD VALIDATION RECONCILIATION
    view = st.sidebar.radio(
        "Select View",
        [
            "Overview",
            "Forecast Details",
            "🔄 Validation Reconciliation",  # NEW TAB
            "Model Performance",
            "Feature Importance",
            "Support & Resistance",
        ],
        index=0,
    )
    
    # ... rest of sidebar code ...
    
    return view, horizon_filter, label_filter, min_confidence

# In main rendering section, add handler for new tab:
def main():
    db = get_db_connection()
    df = fetch_forecasts(db)
    
    view, horizon_filter, label_filter, min_confidence = render_sidebar()
    
    # Apply filters
    df = df[
        (df["horizon"].isin(horizon_filter))
        & (df["label"].isin(label_filter))
        & (df["confidence"] >= min_confidence)
    ]
    
    # Route to correct view
    if view == "🔄 Validation Reconciliation":
        # Get unique symbols from database
        symbols = sorted(df["symbol"].unique().tolist())
        render_validation_reconciliation(symbols)
    
    elif view == "Overview":
        render_overview(df)
    
    elif view == "Forecast Details":
        render_forecast_details(df)
    
    elif view == "Model Performance":
        render_model_performance(df)
    
    elif view == "Feature Importance":
        render_feature_importance(df)
    
    elif view == "Support & Resistance":
        render_support_resistance(df)

if __name__ == "__main__":
    main()
```

---

## Step 3: Start Backend API

The API endpoints must be running for the dashboard to fetch validation data.

### Option A: As Part of Existing Backend

If you have a FastAPI backend, add the validation router:

```python
# In your main FastAPI app (e.g., main.py or app.py)
from fastapi import FastAPI
from src.api import validation_api

app = FastAPI()

# Include validation routes
app.include_router(validation_api.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Option B: Standalone API Server

Create `ml/src/api/server.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import validation_api

app = FastAPI(title="SwiftBolt Validation API")

# Enable CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(validation_api.router)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Run with:
```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
python -m src.api.server
```

---

## Step 4: Run Dashboard

With the API server running, start the dashboard:

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
streamlit run src/dashboard/forecast_dashboard.py
```

Then:
1. Navigate to `http://localhost:8501`
2. Click "🔄 Validation Reconciliation" tab in sidebar
3. Select a symbol (e.g., AAPL)
4. View unified confidence with reconciliation logic

---

## Testing Checklist

### Unit Tests

```python
# ml/src/tests/test_validation_reconciliation.py
import pytest
from src.dashboard.validation_reconciliation import fetch_unified_validation

def test_fetch_unified_validation():
    """Test validation API call."""
    result = fetch_unified_validation("AAPL", "BULLISH")
    assert result is not None
    assert "unified_confidence" in result
    assert "drift" in result
    assert "multi_tf" in result

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

Run:
```bash
python -m pytest ml/src/tests/test_validation_reconciliation.py -v
```

### Manual Testing

1. **Start API Server**
   ```bash
   python -m src.api.server
   ```

2. **Test API Endpoints**
   ```bash
   # Test unified validation
   curl http://localhost:8000/api/validation/unified/AAPL/BULLISH
   
   # Test history
   curl http://localhost:8000/api/validation/history/AAPL?days=7
   
   # Test drift alerts
   curl http://localhost:8000/api/validation/drift-alerts?min_severity=moderate
   ```

3. **Run Dashboard**
   ```bash
   streamlit run src/dashboard/forecast_dashboard.py
   ```

4. **Verify Display**
   - Navigate to Validation Reconciliation tab
   - Select AAPL symbol
   - Verify component breakdown matches calculation
   - Verify drift analysis displays correctly
   - Verify multi-TF consensus shows weighted voting

---

## Troubleshooting

### Issue: "Failed to fetch validation"

**Cause**: API server not running or database not connected

**Fix**:
1. Ensure API server running: `python -m src.api.server`
2. Check database connection in `ValidationService.__init__()`
3. Verify tables exist: `ml_model_metrics`, `rolling_evaluation`, `live_predictions`, `indicator_values`

### Issue: "Confidence seems wrong"

**Debug**:
```python
from src.services.validation_service import ValidationService
import asyncio

async def debug():
    service = ValidationService()
    result = await service.get_live_validation("AAPL", "BULLISH")
    print(f"Backtesting: {result.backtesting_score:.1%}")
    print(f"Walk-forward: {result.walkforward_score:.1%}")
    print(f"Live: {result.live_score:.1%}")
    print(f"Unified: {result.unified_confidence:.1%}")
    print(f"Drift Magnitude: {result.drift_magnitude:.1%}")

asyncio.run(debug())
```

### Issue: "Multi-TF consensus doesn't match"

**Debug**:
```python
validator = UnifiedValidator()
conflict, explanation, consensus, weights = validator._detect_multi_tf_conflict({
    "M15": -0.48,
    "H1": -0.40,
    "H4": -0.35,
    "D1": 0.60,
    "W1": 0.70
})
print(f"Conflict: {conflict}")
print(f"Consensus: {consensus}")
print(f"Weights: {weights}")
```

---

## Expected User Experience

When user opens the "Validation Reconciliation" tab:

1. **Immediate clarity**: Single unified confidence score (58% in AAPL example)
2. **Component breakdown**: See why each metric differs (98.8% historical vs 40% live)
3. **Drift visualization**: Understand the magnitude of model degradation
4. **Multi-TF consensus**: See which timeframes agree/disagree with weighted importance
5. **Actionable recommendation**: "Trade with normal risk" vs "Avoid trading"
6. **Retraining alert**: Know when model needs updating

---

**Status**: Ready for implementation  
**Estimated Time**: 4-6 hours  
**Next Step**: Create `ml/src/dashboard/validation_reconciliation.py`
