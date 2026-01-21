# Multi-Horizon Forecasting System

## Overview

The **Multi-Horizon Forecasting System** creates a cascading portrait of predictions across timeframes, providing both near-term precision and long-term context. Each timeframe generates multiple overlapping forecasts that seamlessly hand off to adjacent timeframes.

## Architecture

### Horizon Structure by Timeframe

```python
TIMEFRAME_HORIZONS = {
    "m15": {
        "horizons": ["4h", "1d", "1w"],
        "horizon_days": [0.167, 1, 7],
        "training_bars": 950
    },
    "h1": {
        "horizons": ["5d", "15d", "30d"],
        "horizon_days": [5, 15, 30],
        "training_bars": 950
    },
    "h4": {
        "horizons": ["30d", "45d", "90d"],
        "horizon_days": [30, 45, 90],
        "training_bars": 616
    },
    "d1": {
        "horizons": ["30d", "60d", "120d"],
        "horizon_days": [30, 60, 120],
        "training_bars": 500
    },
    "w1": {
        "horizons": ["90d", "180d", "360d"],
        "horizon_days": [90, 180, 360],
        "training_bars": 104
    }
}
```

### Key Design Principles

1. **Cascading Coverage**: Each timeframe provides multiple horizons that overlap with adjacent timeframes
2. **Progressive Expansion**: Shorter timeframes provide near-term precision, longer timeframes provide broader context
3. **Seamless Handoffs**: H4's 30d forecast bridges to D1's 30d for continuity
4. **Confidence Tracking**: Handoff confidence shows trust in next timeframe
5. **Redundant Validation**: Multiple forecasts for same time periods provide cross-validation

## Components

### 1. Core Data Models (`multi_horizon_forecast.py`)

#### MultiHorizonForecast
Represents all forecasts for a single timeframe:
- **timeframe**: Source timeframe (e.g., "m15", "h1")
- **base_horizon**: Primary horizon (first in list)
- **extended_horizons**: Additional horizons
- **forecasts**: Dict of horizon → ForecastResult
- **consensus_weights**: Weight of each forecast in consensus
- **handoff_confidence**: Confidence in transitioning to next timeframe

#### CascadingConsensus
Combines overlapping forecasts from multiple timeframes:
- **direction**: Consensus direction (BULLISH/BEARISH/NEUTRAL)
- **confidence**: Weighted confidence score
- **contributing_timeframes**: Which timeframes contributed
- **agreement_score**: How much timeframes agree (0-1)
- **handoff_quality**: Quality of timeframe transitions (0-1)

### 2. Forecast Generation (`forecast_synthesizer.py`)

Enhanced `ForecastSynthesizer` with variable horizon support:

```python
synthesizer = ForecastSynthesizer()

# Generate forecast for any horizon
result = synthesizer.generate_forecast(
    current_price=150.0,
    df=df,
    supertrend_info=st_info,
    sr_response=sr_levels,
    ensemble_result=ml_result,
    horizon_days=30.0,  # 30-day forecast
    symbol="AAPL",
    timeframe="d1"
)
```

**Horizon Scaling**: ATR-based moves scale with `sqrt(horizon_days)` to account for volatility expansion over time.

### 3. Multi-Horizon Job (`multi_horizon_forecast_job.py`)

Orchestrates forecast generation across all timeframes:

```bash
# Generate multi-horizon forecasts for symbols
python ml/src/multi_horizon_forecast_job.py --symbols AAPL NVDA TSLA

# Process specific timeframe only
python ml/src/multi_horizon_forecast_job.py --symbols AAPL --timeframe d1
```

**Process Flow**:
1. Fetch features for all timeframes
2. Generate multi-horizon forecasts per timeframe
3. Calculate handoff confidence between timeframes
4. Build cascading consensus forecasts
5. Store in database

### 4. Database Schema (`20260121000000_multi_horizon_forecasts.sql`)

**New Columns**:
- `timeframe`: Source timeframe or "consensus"
- `is_base_horizon`: True for primary horizon
- `is_consensus`: True for consensus forecasts
- `handoff_confidence`: Transition confidence (0-1)
- `consensus_weight`: Weight in consensus calculation

**New Functions**:
- `get_multi_horizon_forecasts(symbol, timeframe)`: All horizons for a timeframe
- `get_consensus_forecasts(symbol)`: Consensus forecasts only
- `get_forecast_cascade(symbol, horizon)`: All forecasts for a specific horizon

### 5. Swift UI Components (`MultiHorizonForecastView.swift`)

Three view modes:

#### By Timeframe
Shows each timeframe with its cascading horizons:
- Primary (base) horizon highlighted
- Extended horizons with handoff confidence
- Key drivers and layer agreement

#### By Horizon
Groups forecasts by horizon across timeframes:
- Shows cascade of predictions for same time period
- Highlights agreement/disagreement between timeframes

#### Consensus
Displays consensus forecasts:
- Agreement score
- Handoff quality
- Contributing timeframes
- Weighted target and confidence

## Usage Examples

### Python: Generate Multi-Horizon Forecasts

```python
from src.multi_horizon_forecast_job import process_symbol_all_timeframes

# Generate forecasts for all timeframes
all_forecasts = process_symbol_all_timeframes("AAPL")

# Access specific timeframe
d1_forecast = all_forecasts["d1"]
print(f"D1 base horizon: {d1_forecast.base_horizon}")
print(f"D1 extended horizons: {d1_forecast.extended_horizons}")

# Access specific horizon forecast
forecast_30d = d1_forecast.forecasts["30d"]
print(f"30d target: ${forecast_30d.target:.2f}")
print(f"30d confidence: {forecast_30d.confidence:.2%}")
print(f"Handoff confidence: {d1_forecast.handoff_confidence['30d']:.2%}")
```

### Python: Build Consensus

```python
from src.multi_horizon_forecast import build_cascading_consensus

# Build consensus for 30d horizon
consensus_30d = build_cascading_consensus(all_forecasts, "30d")

print(f"Consensus direction: {consensus_30d.direction}")
print(f"Consensus target: ${consensus_30d.target:.2f}")
print(f"Agreement score: {consensus_30d.agreement_score:.2%}")
print(f"Contributing: {consensus_30d.contributing_timeframes}")
```

### SQL: Query Multi-Horizon Forecasts

```sql
-- Get all horizons for AAPL on D1 timeframe
SELECT * FROM get_multi_horizon_forecasts('AAPL', 'd1');

-- Get consensus forecasts for AAPL
SELECT * FROM get_consensus_forecasts('AAPL');

-- Get cascade for 30d horizon
SELECT * FROM get_forecast_cascade('AAPL', '30d');

-- Find high-confidence handoffs
SELECT 
    symbol,
    timeframe,
    horizon,
    direction,
    confidence,
    handoff_confidence
FROM multi_horizon_forecast_summary
WHERE handoff_confidence > 0.8
ORDER BY handoff_confidence DESC;
```

### Swift: Display Multi-Horizon Forecasts

```swift
// Add to your view
MultiHorizonForecastGridView(
    symbol: "AAPL",
    currentPrice: 150.0
)
```

## Benefits

### 1. Continuity
Seamless handoffs between timeframes (e.g., H4 30d → D1 30d) provide smooth transitions across time scales.

### 2. Redundancy
Multiple forecasts for the same time period enable cross-validation and confidence assessment.

### 3. Confidence Tracking
Handoff confidence metrics show trust in next timeframe, helping identify regime changes.

### 4. Progressive Detail
- **Near-term** (M15 4h): High precision for intraday trading
- **Mid-term** (D1 30d): Swing trading context
- **Long-term** (W1 360d): Investment horizon perspective

### 5. Flexible Display
UI supports viewing by timeframe, by horizon, or consensus—adapting to user workflow.

## Consensus Building Algorithm

### Effective Weight Calculation

```python
effective_weight = (
    timeframe_weight ×
    forecast_confidence ×
    handoff_confidence
)
```

**Timeframe Weights** (horizon-dependent):
- Intraday horizons (<1d): M15 gets highest weight
- Week horizons (≤7d): H1 gets highest weight
- Month horizons (≤30d): H4 gets highest weight
- Quarter horizons (≤90d): D1 gets highest weight
- Long-term (>90d): W1 gets highest weight

### Direction Consensus

Requires 20% threshold for directional call:
- `bullish_weight > bearish_weight × 1.2` → BULLISH
- `bearish_weight > bullish_weight × 1.2` → BEARISH
- Otherwise → NEUTRAL

### Agreement Score

Proportion of weight supporting the consensus direction (0-1).

### Handoff Quality

Average of all handoff confidence scores for the horizon.

## Performance Considerations

### Volatility Scaling

Forecast targets scale with `sqrt(horizon_days)` because volatility grows with the square root of time:

```python
horizon_scale = np.sqrt(horizon_days)
scaled_atr = atr * horizon_scale
```

This ensures realistic price movement expectations for longer horizons.

### Caching Strategy

Multi-horizon forecasts are computationally expensive. Recommended caching:
- Cache forecasts for 10-15 minutes
- Invalidate on significant price moves (>2 ATR)
- Store in `mlforecasts` table with `created_at` timestamp

### Database Indexes

```sql
CREATE INDEX idx_mlforecasts_timeframe 
ON mlforecasts(symbol_id, timeframe, horizon);

CREATE INDEX idx_mlforecasts_consensus 
ON mlforecasts(symbol_id, is_consensus, horizon) 
WHERE is_consensus = true;
```

## Future Enhancements

### 1. Adaptive Horizon Selection
Dynamically adjust horizons based on volatility regime and market conditions.

### 2. Ensemble Weighting
Use historical accuracy to weight timeframes differently per symbol.

### 3. Regime-Aware Handoffs
Adjust handoff confidence based on detected regime changes.

### 4. Interactive Visualization
Chart showing forecast cascade with confidence bands across all horizons.

### 5. Alert System
Notify when consensus changes or handoff confidence drops significantly.

## Testing

```bash
# Run multi-horizon forecast job
python ml/src/multi_horizon_forecast_job.py --symbols AAPL

# Apply database migration
psql -f supabase/migrations/20260121000000_multi_horizon_forecasts.sql

# Query results
psql -c "SELECT * FROM get_multi_horizon_forecasts('AAPL', 'd1');"
```

## References

- **Forecast Synthesizer**: `ml/src/forecast_synthesizer.py`
- **Multi-Horizon Models**: `ml/src/multi_horizon_forecast.py`
- **Job Runner**: `ml/src/multi_horizon_forecast_job.py`
- **Database Schema**: `supabase/migrations/20260121000000_multi_horizon_forecasts.sql`
- **Swift UI**: `client-macos/SwiftBoltML/Views/MultiHorizonForecastView.swift`
- **Configuration**: `ml/config/settings.py` (TIMEFRAME_HORIZONS)

---

**Status**: ✅ Implemented  
**Version**: 1.0  
**Last Updated**: 2026-01-21
