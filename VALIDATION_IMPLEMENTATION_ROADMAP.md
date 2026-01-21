# SwiftBolt_ML Validation Framework & Dashboard Integration Roadmap

**Status**: ✅ UnifiedValidator Framework DEPLOYED  
**Deployment Date**: January 21, 2026  
**System State**: Ready for dashboard integration  
**Next Phase**: Live integration + metric reconciliation

---

## 📊 Executive Summary

Your validation system is **architecturally sound** with a complete `UnifiedValidator` engine already implemented. However, **three critical gaps** remain between the validator and your live dashboard:

### Gap 1: Dashboard-to-Validator Data Pipeline ⚠️
- Dashboard shows raw metrics from 3 sources (backtesting, live forecasts, multi-TF bars)
- Validator has the reconciliation logic but **receives no live data feeds**
- Solution: Route real-time metrics to `UnifiedValidator.validate()` method

### Gap 2: Metric Reconciliation Display 📺
- Users see conflicting percentages (98.8% vs 40% vs -48%)
- No visual explanation of **why** metrics conflict or **which to trust**
- Solution: Create reconciliation dashboard tab showing unified confidence + drift explanation

### Gap 3: Integration with Forecast Jobs 🔄
- Forecast jobs (`intraday_forecast_job.py`, `forecast_job.py`) generate predictions
- Validator logic exists but **not called** in forecast pipeline
- Solution: Embed validation in forecast output pipeline

---

## 🎯 The Three Core Issues (DETAILED)

### Issue 1: Dashboard Confusion ⚠️
Your dashboards show contradictory metrics:

| Source | Shows | Training Window | Problem |
|--------|-------|---|---|
| Statistical Validation Tab | 98.8% precision | 3 months (backtesting) | Historical accuracy |
| Live AAPL Forecast | 40% BEARISH | Real-time | Current prediction |
| Multi-TF Bars | M15: -48%, H1: -40%, D1: +60% | Different lookbacks | Which to trust? |

**Root Cause**: No reconciliation logic. Dashboard shows raw metrics without context.

**Current Status**: ✅ UnifiedValidator engine exists (see `ml/src/validation/unified_framework.py`)

**What's Missing**: Dashboard integration layer that feeds live metrics to validator

### Issue 2: Multi-Timeframe Conflict Resolution 📊
Your multi-TF bars show opposing signals across timeframes:
- **Intraday (M15, H1)**: Bearish (-48%, -40%)
- **Swing (H4, D1)**: Mixed (-35% to +60%)
- **Trend (W1)**: Bullish (+70%)

**Root Cause**: No hierarchy weighting. All timeframes treated equally.

**Current Status**: ✅ TF_HIERARCHY implemented in validator:
```python
TF_HIERARCHY = {
    "W1": 0.35,    # Weekly: 35% (longest-term trend)
    "D1": 0.25,    # Daily: 25%
    "H4": 0.20,    # 4-hour: 20%
    "H1": 0.15,    # Hourly: 15%
    "M15": 0.05,   # 15-min: 5% (noise)
}
```

**What's Missing**: Multi-TF bars dashboard needs to display weighted consensus (not just raw scores)

### Issue 3: Drift Detection & Retraining Triggers ⚠️
Your live performance (40%) has **58% drift** from backtesting (98.8%)

**Root Cause**: No automated drift monitoring. Dashboard shows divergence but doesn't flag it.

**Current Status**: ✅ Drift detection fully implemented:
```python
DRIFT_MINOR_THRESHOLD = 0.15      # 15% divergence = warning
DRIFT_MODERATE_THRESHOLD = 0.25   # 25% = flag for review
DRIFT_SEVERE_THRESHOLD = 0.50     # 50% = auto-investigate
DRIFT_CRITICAL_THRESHOLD = 0.75   # 75% = consider retraining
```

**What's Missing**: Drift alerts not surfaced to dashboard. Retraining not triggered automatically.

---

## ✅ COMPLETED: UnifiedValidator Implementation

### What's Already Built

Your `ml/src/validation/unified_framework.py` contains:

#### 1. **ValidationScores Dataclass** ✅
Stores input metrics from 3 sources:
```python
@dataclass
class ValidationScores:
    backtesting_score: float      # 0-1 (3-month accuracy)
    walkforward_score: float      # 0-1 (quarterly rolling accuracy)
    live_score: float             # 0-1 (last 30 predictions)
    multi_tf_scores: Dict[str, float]  # {"M15": -0.48, "H1": -0.40, ...}
    timestamp: Optional[datetime]
```

#### 2. **UnifiedPrediction Output** ✅
Comprehensive prediction object with:
- Unified confidence score (0-1)
- Component breakdown (backtesting, walkforward, live)
- Multi-TF consensus with conflict detection
- Drift analysis (magnitude, severity, explanation)
- Retraining triggers with suggested schedule
- Actionable recommendations

#### 3. **UnifiedValidator Engine** ✅
Core validation logic:
- **Weight combination**: 0.40 * backtest + 0.35 * walkforward + 0.25 * live
- **Drift detection**: Calculates magnitude between components
- **Multi-TF reconciliation**: Weighted voting by timeframe hierarchy
- **Confidence adjustment**: Applies penalties/bonuses based on drift and conflict
- **Retraining logic**: Triggers at 75%+ drift, severe drift >7 days, or 30-day schedule

#### 4. **Real Example (From Your Audit)** ✅
Run this to see the exact AAPL scenario:
```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
python -m src.validation.unified_framework
```

Output:
```
============================================================
UNIFIED PREDICTION FOR AAPL
============================================================

Direction: BULLISH
Unified Confidence: 58.1% 🟡

Component Scores:
  Backtesting:  98.8%
  Walk-forward: 78.0%
  Live:         40.0%

Drift Analysis:
  Detected:   True
  Magnitude:  58.0%
  Severity:   severe
  Explanation: Live score (40.0%) is 58.0% lower than backtesting (98.8%) - likely model degradation or market regime change

Multi-Timeframe Reconciliation:
  Conflict:   True
  Consensus:  BULLISH
  Explanation: Weak consensus (26.4% margin) (Bullish: D1, W1; Bearish: M15, H1, H4)

Adjustments Applied:
  - Drift penalty: -13.4%
  - Multi-TF conflict: -15%
  - Consensus alignment: +8%

Recommendation: Moderate confidence - trade with normal risk

Retraining:
  Trigger:  False
  Reason:   Model within acceptable drift range
  Next:     2026-02-20 10:40

============================================================
```

---

## 🔴 INCOMPLETE: Dashboard Integration

### Current State

**What the dashboard currently does:**
- Displays backtesting metrics (98.8% accuracy, Sharpe ratio, win rate) ✅
- Shows live forecast signals (BULLISH, BEARISH, NEUTRAL) ✅
- Displays multi-TF bars (M15: -48%, H1: -40%, D1: +60%, W1: +70%) ✅
- **Missing**: Reconciliation or explanation of conflicting metrics ❌

**User experience problem:**
> "The dashboard shows 98.8% accuracy from backtesting, but the live AAPL forecast is 40% BEARISH. Which one should I trust? Why do the multi-TF bars show -48% on M15 and +70% on W1?"

### Required Integration: 5-Step Plan

#### Step 1: Create Validation Data Pipeline ⚡
**File**: `ml/src/services/validation_service.py` (NEW)

Purpose: Connect real-time metrics to validator

```python
from src.validation import UnifiedValidator, ValidationScores
from src.data.supabase_db import SupabaseDatabase

class ValidationService:
    """Routes real-time metrics to UnifiedValidator."""
    
    def __init__(self):
        self.validator = UnifiedValidator()
        self.db = SupabaseDatabase()
    
    async def get_live_validation(self, symbol: str, direction: str) -> UnifiedPrediction:
        """
        Get reconciled validation for a symbol.
        
        Fetches:
        1. Backtesting score from ml_model_metrics table
        2. Walk-forward score from rolling_evaluation table
        3. Live score from indicator_values (last 30 predictions)
        4. Multi-TF scores from ohlc_bars_v2
        
        Returns unified prediction with drift/conflict analysis.
        """
        # Fetch backtesting score (3-month window)
        backtest_score = await self._get_backtesting_score(symbol)
        
        # Fetch walk-forward score (quarterly rolling)
        walkforward_score = await self._get_walkforward_score(symbol)
        
        # Fetch live score (last 30 predictions)
        live_score = await self._get_live_score(symbol)
        
        # Fetch multi-TF scores
        multi_tf_scores = await self._get_multi_tf_scores(symbol)
        
        # Create scores object
        scores = ValidationScores(
            backtesting_score=backtest_score,
            walkforward_score=walkforward_score,
            live_score=live_score,
            multi_tf_scores=multi_tf_scores
        )
        
        # Validate
        result = self.validator.validate(symbol, direction, scores)
        
        # Store result for dashboard
        await self._store_validation_result(result)
        
        return result
    
    async def _get_backtesting_score(self, symbol: str) -> float:
        """Fetch 3-month historical accuracy."""
        # Query ml_model_metrics where timeframe='1D' and created_at > 90 days ago
        pass
    
    async def _get_walkforward_score(self, symbol: str) -> float:
        """Fetch quarterly rolling accuracy."""
        # Query rolling_evaluation for last 13-week window
        pass
    
    async def _get_live_score(self, symbol: str) -> float:
        """Fetch last 30 predictions accuracy."""
        # Query live_predictions last 30 rows, calculate accuracy
        pass
    
    async def _get_multi_tf_scores(self, symbol: str) -> Dict[str, float]:
        """Fetch current multi-TF prediction scores."""
        # Query indicator_values for M15, H1, H4, D1, W1
        # Return raw prediction scores (not normalized)
        pass
    
    async def _store_validation_result(self, result: UnifiedPrediction) -> None:
        """Store unified validation result for dashboard retrieval."""
        # Insert into validation_results table
        pass
```

#### Step 2: Add Validation Query Endpoint 🔌
**File**: `ml/src/api/validation_api.py` (NEW)

```python
from fastapi import APIRouter, HTTPException
from src.services.validation_service import ValidationService

router = APIRouter(prefix="/api/validation", tags=["validation"])
validation_service = ValidationService()

@router.get("/unified/{symbol}/{direction}")
async def get_unified_validation(symbol: str, direction: str):
    """
    Get reconciled validation for symbol.
    
    Returns:
    {
        "symbol": "AAPL",
        "direction": "BULLISH",
        "unified_confidence": 0.581,
        "backtesting_score": 0.988,
        "walkforward_score": 0.78,
        "live_score": 0.40,
        "drift_detected": true,
        "drift_magnitude": 0.58,
        "drift_severity": "severe",
        "multi_tf_consensus": {"M15": -0.48, "H1": -0.40, ...},
        "timeframe_conflict": true,
        "recommendation": "Moderate confidence - trade with normal risk",
        "retraining_trigger": false
    }
    """
    try:
        result = await validation_service.get_live_validation(symbol, direction)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### Step 3: Create "Validation Reconciliation" Dashboard Tab 📺
**File**: `ml/src/dashboard/validation_reconciliation.py` (NEW)

Add to `forecast_dashboard.py`:

```python
def render_validation_reconciliation(df: pd.DataFrame):
    """
    NEW TAB: Shows reconciled validation metrics.
    
    Replaces the confusing "3 different metrics" view with:
    - Unified confidence score (single source of truth)
    - Component breakdown (why each metric differs)
    - Drift explanation (historical vs live gap)
    - Multi-TF consensus (which timeframes agree/disagree)
    - Retraining alert (if model degradation detected)
    """
    st.title("🔄 Validation Reconciliation")
    st.markdown(
        "*Shows how backtesting, walk-forward, and live metrics combine into a single confidence score*"
    )
    
    # Symbol selector
    symbol = st.selectbox("Select Symbol", df["symbol"].unique())
    
    # Fetch unified validation
    validation = fetch_unified_validation(symbol)
    
    if not validation:
        st.error("No validation data available")
        return
    
    # Top-level metric: Unified Confidence (SINGLE SOURCE OF TRUTH)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        emoji = validation["get_status_emoji"]()
        st.metric(
            "Unified Confidence",
            f"{validation['unified_confidence']:.1%}",
            emoji
        )
    
    with col2:
        st.metric(
            "Drift Detected",
            validation['drift_severity'],
            help=validation['drift_explanation']
        )
    
    with col3:
        if validation['retraining_trigger']:
            st.error("⚠️ RETRAIN NOW")
            st.caption(validation['retraining_reason'])
        else:
            st.success("✅ Model Healthy")
    
    st.markdown("---")
    
    # Component breakdown chart
    st.subheader("Component Scores")
    
    components = {
        "Backtesting (40%)": validation['backtesting_score'],
        "Walk-Forward (35%)": validation['walkforward_score'],
        "Live (25%)": validation['live_score'],
    }
    
    # Horizontal bar chart
    fig = px.barh(
        x=list(components.values()),
        y=list(components.keys()),
        color=list(components.values()),
        color_continuous_scale=["#ff5252", "#ffc107", "#00c853"],
        range_x=[0, 1]
    )
    fig.add_vline(x=validation['unified_confidence'], line_dash="dash", line_color="white")
    st.plotly_chart(fig, use_container_width=True)
    
    # Multi-TF reconciliation
    st.subheader("Multi-Timeframe Consensus")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Consensus Direction**: {validation['consensus_direction']}")
        st.write(f"**Conflict**: {'Yes ⚠️' if validation['timeframe_conflict'] else 'No ✅'}")
        st.write(f"**Explanation**: {validation['conflict_explanation']}")
    
    with col2:
        # Multi-TF breakdown
        tf_scores = validation['multi_tf_consensus']
        fig = px.bar(
            x=list(tf_scores.keys()),
            y=list(tf_scores.values()),
            color=list(tf_scores.values()),
            color_continuous_scale=["#ff5252", "#ffc107", "#00c853"],
            range_y=[-1, 1]
        )
        fig.add_hline(y=0, line_dash="dash", line_color="white")
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Adjustments applied
    st.subheader("Confidence Adjustments")
    
    for adjustment in validation['adjustments']:
        st.write(f"• {adjustment}")
    
    st.markdown("---")
    
    # Recommendation
    st.subheader("Trading Recommendation")
    
    if validation['unified_confidence'] >= 0.75:
        st.success(f"✅ {validation['recommendation']}")
    elif validation['unified_confidence'] >= 0.60:
        st.info(f"⚠️ {validation['recommendation']}")
    elif validation['unified_confidence'] >= 0.45:
        st.warning(f"🟠 {validation['recommendation']}")
    else:
        st.error(f"🔴 {validation['recommendation']}")
    
    # Retraining schedule
    if validation['retraining_trigger']:
        st.error(
            f"\n⚠️ **RETRAINING RECOMMENDED**\n\n"
            f"Reason: {validation['retraining_reason']}\n\n"
            f"Suggested Date: {validation['next_retraining_date']}"
        )
```

#### Step 4: Integrate into Forecast Pipeline 🔄
**File**: `ml/src/intraday_forecast_job.py`

Modify forecast generation to include validation:

```python
from src.validation import UnifiedValidator, ValidationScores
from src.services.validation_service import ValidationService

class IntraydayForecastJob:
    """
    Generate intraday forecasts with integrated validation.
    """
    
    def __init__(self):
        self.validator = UnifiedValidator()
        self.validation_service = ValidationService()
    
    async def generate_forecast(self, symbol: str) -> Dict:
        """
        Generate forecast with integrated validation.
        
        Returns:
        {
            "symbol": "AAPL",
            "forecast": {
                "direction": "BULLISH",
                "confidence": 0.72,
                "timeframe": "1H"
            },
            "validation": {
                "unified_confidence": 0.581,
                "drift_detected": true,
                "multi_tf_conflict": true,
                "recommendation": "Moderate confidence - trade with normal risk"
            }
        }
        """
        # Generate raw forecast (existing code)
        forecast = await self._generate_raw_forecast(symbol)
        
        # Get unified validation
        validation = await self.validation_service.get_live_validation(
            symbol,
            forecast['direction']
        )
        
        # Combine results
        return {
            "symbol": symbol,
            "forecast": forecast,
            "validation": validation.to_dict(),
            "timestamp": datetime.now()
        }
```

#### Step 5: Update Dashboard View Selection 🎨
**File**: `ml/src/dashboard/forecast_dashboard.py`

Add to sidebar view options:

```python
def render_sidebar():
    """Render sidebar with filters and controls."""
    st.sidebar.title("📈 SwiftBolt ML")
    st.sidebar.markdown("---")

    # View selection - ADD NEW TAB
    view = st.sidebar.radio(
        "Select View",
        [
            "Overview",
            "Forecast Details",
            "🔄 Validation Reconciliation",  # NEW
            "Model Performance",
            "Feature Importance",
            "Support & Resistance",
        ],
        index=0,
    )
    
    # ... rest of sidebar code ...
    
    return view, horizon_filter, label_filter, min_confidence

# In main dash render section:
def main():
    view, horizon_filter, label_filter, min_confidence = render_sidebar()
    
    if view == "🔄 Validation Reconciliation":
        render_validation_reconciliation(df)
    elif view == "Overview":
        render_overview(df)
    # ... etc
```

---

## 📋 Implementation Checklist

### Phase 1: Data Pipeline (1-2 hours)
- [ ] Create `ml/src/services/validation_service.py`
- [ ] Implement `_get_backtesting_score()` method
- [ ] Implement `_get_walkforward_score()` method
- [ ] Implement `_get_live_score()` method
- [ ] Implement `_get_multi_tf_scores()` method
- [ ] Test with sample data

### Phase 2: API Integration (30 mins)
- [ ] Create `ml/src/api/validation_api.py`
- [ ] Add GET endpoint `/api/validation/unified/{symbol}/{direction}`
- [ ] Test endpoint with curl/Postman

### Phase 3: Dashboard Tab (2 hours)
- [ ] Create `ml/src/dashboard/validation_reconciliation.py`
- [ ] Implement reconciliation view with charts
- [ ] Add tab to sidebar view selection
- [ ] Test dashboard rendering

### Phase 4: Forecast Pipeline Integration (1 hour)
- [ ] Modify `intraday_forecast_job.py` to call validator
- [ ] Modify `forecast_job.py` similarly
- [ ] Store validation results in database
- [ ] Test end-to-end forecast generation

### Phase 5: Testing & Deployment (2 hours)
- [ ] Run integration tests
- [ ] Deploy to staging
- [ ] Verify dashboard displays reconciled metrics
- [ ] Monitor for 24 hours
- [ ] Deploy to production

**Total Estimated Time**: 6-8 hours

---

## 🧪 Testing Plan

### Unit Tests

```bash
# Test validator logic
python -m pytest ml/src/validation/test_unified_framework.py -v

# Test validation service
python -m pytest ml/src/services/test_validation_service.py -v
```

### Integration Tests

```bash
# Test full pipeline: forecast generation -> validation -> storage
python -m pytest ml/src/tests/test_forecast_with_validation.py -v

# Test API endpoint
curl http://localhost:8000/api/validation/unified/AAPL/BULLISH
```

### Manual Dashboard Testing

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
streamlit run src/dashboard/forecast_dashboard.py

# Navigate to "Validation Reconciliation" tab
# Verify metrics reconcile correctly
# Verify drift alerts display
# Verify retraining triggers show
```

---

## 🔍 Debugging Guide

### Issue: Dashboard Shows "No Validation Data"

**Cause**: Validation service not connected to real data

**Fix**:
1. Check database connection in `ValidationService.__init__()`
2. Verify `ml_model_metrics` table has recent data
3. Verify `rolling_evaluation` table exists
4. Check `live_predictions` table for recent predictions

### Issue: Unified Confidence Seems Wrong

**Debugging**:
```python
from src.validation import UnifiedValidator, ValidationScores

# Print component scores
scores = ValidationScores(
    backtesting_score=0.988,
    walkforward_score=0.78,
    live_score=0.40,
    multi_tf_scores={"M15": -0.48, "H1": -0.40, "D1": 0.60, "W1": 0.70}
)

validator = UnifiedValidator()
result = validator.validate("AAPL", "BULLISH", scores)

print(f"Base confidence: {result.unified_confidence:.4f}")
print(f"Drift magnitude: {result.drift_magnitude:.4f}")
print(f"Adjustments: {result.adjustments}")
```

### Issue: Multi-TF Consensus Wrong

**Debugging**:
```python
# Check hierarchy weights
print(validator.TF_HIERARCHY)

# Check threshold logic
print(f"Bullish threshold: {validator.BULLISH_THRESHOLD}")
print(f"Bearish threshold: {validator.BEARISH_THRESHOLD}")

# Trace through conflict detection
conflict, explanation, consensus, weights = validator._detect_multi_tf_conflict(
    {"M15": -0.48, "H1": -0.40, "D1": 0.60, "W1": 0.70}
)
print(f"Conflict: {conflict}")
print(f"Explanation: {explanation}")
print(f"Consensus: {consensus}")
```

---

## 📈 Expected Outcomes

Once integrated:

### For You (Developer)
- ✅ Single unified confidence score instead of 3 contradictory metrics
- ✅ Clear drift detection and model degradation alerts
- ✅ Automatic retraining triggers based on quantified drift
- ✅ Multi-TF conflicts surfaced with weighted consensus

### For Your Dashboard
- ✅ "Validation Reconciliation" tab shows WHY metrics conflict
- ✅ Color-coded confidence (🟢 high, 🟡 moderate, 🟠 low, 🔴 critical)
- ✅ Drift magnitude and severity clearly labeled
- ✅ Component breakdown explains each metric contribution
- ✅ Actionable recommendations ("trade with normal risk", "use tight stops", "avoid trading")

### For Trading Accuracy
- ✅ No more confusion about which metric to trust
- ✅ Live performance weighted into confidence (40% backtest + 35% walkforward + 25% live)
- ✅ Multi-TF conflicts trigger reduced position sizes automatically
- ✅ Model degradation detected before it impacts live trades

---

## 🚀 Quick Start: Run Existing Validator

To see the validator in action right now:

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml

# Run the example from unified_framework.py
python -m src.validation.unified_framework
```

This will output the AAPL prediction with all reconciliation logic applied.

---

## 📞 Questions?

**Q: Will integrating the validator break existing forecast code?**  
A: No. The validator operates independently. Add it as a post-processing step to forecast generation.

**Q: How often should I retrain?**  
A: Validator triggers automatically at:
- 75%+ drift (critical)
- 50%+ drift for 7+ days (severe persistent)
- 30 days elapsed (scheduled)

**Q: Can I adjust the weights (40/35/25)?**  
A: Yes. Edit `BACKTEST_WEIGHT`, `WALKFORWARD_WEIGHT`, `LIVE_WEIGHT` in `UnifiedValidator` class.

**Q: What if live score is always low?**  
A: Validator will flag this as drift and recommend retraining. This indicates market conditions have changed and your model needs updating.

---

**Status**: Ready for Phase 1 implementation  
**Next Step**: Create `ml/src/services/validation_service.py`
