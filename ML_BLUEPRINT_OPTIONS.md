# ML Blueprint: Options Ranking Pipeline

## Overview

This document describes the complete ML pipeline for options contract ranking in SwiftBolt ML, from data ingestion to UI display.

---

## 1. Data Sources

### Options Chain Data
| Source | Provider | Data Type |
|--------|----------|-----------|
| Polygon.io (via Massive) | `massive-client.ts` | Options chain, Greeks |
| Market Data API | `options-chain` Edge Function | Real-time options quotes |

### Underlying Stock Data
| Source | Purpose |
|--------|---------|
| `ohlc_bars` table | Historical prices for trend analysis |
| `ml_forecasts` table | ML predictions for directional bias |
| `supertrend_signals` table | SuperTrend signals for momentum |

### Data Flow
```
Options API → options-chain Edge Function → Options Ranker → options_rankings table
     │
     └── Stock ML Pipeline (trend analysis) ──┘
```

### Database Tables
| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `symbols` | Symbol registry | id, ticker, asset_type |
| `ohlc_bars` | Underlying price history | symbol_id, timeframe, ts, OHLC |
| `ml_forecasts` | Stock ML predictions | symbol_id, overall_label, confidence |
| `options_rankings` | Ranked contracts | symbol, contract_symbol, ml_score, expiry |
| `job_queue` | Async job processing | job_type="ranking", symbol, status |

---

## 2. Options Data Structure

### Options Chain Response
```json
{
  "underlying": "AAPL",
  "underlyingPrice": 250.00,
  "calls": [
    {
      "contractSymbol": "AAPL250117C00250000",
      "strike": 250.0,
      "expiration": "2025-01-17",
      "side": "call",
      "bid": 5.20,
      "ask": 5.40,
      "last": 5.30,
      "volume": 1250,
      "openInterest": 8500,
      "impliedVolatility": 0.32,
      "delta": 0.52,
      "gamma": 0.045,
      "theta": -0.08,
      "vega": 0.15
    }
  ],
  "puts": [...]
}
```

---

## 3. ML Models

### Model 1: Base Options Ranker

**Script:** `ml/src/models/options_ranker.py`

**Class:** `OptionsRanker`

### Scoring Weights
| Component | Weight | Description |
|-----------|--------|-------------|
| Moneyness | 25% | Distance from strike to underlying |
| IV Rank | 20% | IV relative to historical volatility |
| Liquidity | 15% | Volume + Open Interest score |
| Delta Score | 15% | Delta alignment with trend |
| Theta Decay | 10% | Time decay favorability |
| Momentum | 15% | Underlying trend alignment |

### Scoring Functions

#### Moneyness Score
```python
def _score_moneyness(strike, side, underlying_price, trend):
    # Favors:
    # - Bullish trend → slightly OTM calls, ITM puts
    # - Bearish trend → ITM calls, slightly OTM puts
    # - Neutral → ATM options
    moneyness = (strike - underlying_price) / underlying_price
    # Score 0-1 based on optimal moneyness for trend
```

#### IV Rank Score
```python
def _score_iv_rank(implied_vol, historical_vol):
    # Favors options where IV < HV (underpriced)
    iv_ratio = implied_vol / historical_vol
    # Score higher when IV is relatively low
```

#### Liquidity Score
```python
def _score_liquidity(volume, open_interest):
    # Combines volume and OI into liquidity score
    # Higher is better for execution
```

#### Delta Score
```python
def _score_delta(delta, side, trend):
    # Bullish: favor high delta calls, low delta puts
    # Bearish: favor low delta calls, high delta puts
```

---

### Model 2: Enhanced Options Ranker

**Script:** `ml/src/models/enhanced_options_ranker.py`

**Class:** `EnhancedOptionsRanker` (extends `OptionsRanker`)

### Enhanced Scoring Weights
| Component | Weight | Description |
|-----------|--------|-------------|
| Moneyness | 20% | Distance from strike |
| IV Rank | 15% | IV vs HV |
| Liquidity | 15% | Volume + OI |
| Delta Score | 10% | Delta alignment |
| Theta Decay | 10% | Time decay |
| Momentum | 10% | Price momentum |
| **Trend Strength** | 10% | Multi-indicator signal strength |
| **SuperTrend** | 10% | SuperTrend AI alignment |

### Integration with Stock ML

```python
def rank_options_with_trend(options_df, underlying_price, trend_analysis):
    """
    trend_analysis dict contains:
    - trend: 'bullish', 'bearish', 'neutral'
    - signal_strength: 0-10
    - supertrend_factor: float
    - supertrend_performance: float
    - indicator_signals: dict
    """
```

---

## 4. Job Execution

### Trigger Methods

| Method | Schedule | Script |
|--------|----------|--------|
| GitHub Actions | Nightly | `.github/workflows/options-nightly.yml` |
| Manual | On-demand | `python -m src.options_ranking_job --symbol AAPL` |
| UI Sync Button | User-triggered | `POST /refresh-data` with `refreshOptions: true` |

### Options Ranking Job Flow

**Script:** `ml/src/options_ranking_job.py`

```python
def run_ranking_job(symbol: str):
    # 1. Fetch options chain from API
    options_data = fetch_options_from_api(symbol)
    
    # 2. Parse into DataFrame
    options_df = parse_options_chain(options_data)
    
    # 3. Get underlying price and trend
    underlying_price = options_data["underlyingPrice"]
    
    # 4. Fetch ML forecast for trend
    forecast = db.get_latest_forecast(symbol)
    trend = forecast.overall_label.lower()
    
    # 5. Calculate historical volatility
    ohlc = db.fetch_ohlc_bars(symbol, "d1", limit=30)
    historical_vol = calculate_historical_volatility(ohlc)
    
    # 6. Run ranker
    ranker = EnhancedOptionsRanker()
    ranked_df = ranker.rank_options_with_trend(
        options_df,
        underlying_price,
        trend_analysis={
            "trend": trend,
            "signal_strength": forecast.trend_confidence,
            "supertrend_factor": forecast.supertrend_factor,
        },
        historical_vol=historical_vol
    )
    
    # 7. Save to database
    db.upsert_options_rankings(symbol, ranked_df)
```

---

## 5. Data Storage

### options_rankings Table Schema

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| symbol | TEXT | Underlying ticker |
| contract_symbol | TEXT | Full option symbol |
| strike | FLOAT | Strike price |
| expiry | DATE | Expiration date |
| side | TEXT | "call" or "put" |
| ml_score | FLOAT | Composite ML score (0-100) |
| moneyness_score | FLOAT | Component score |
| iv_rank_score | FLOAT | Component score |
| liquidity_score | FLOAT | Component score |
| delta_score | FLOAT | Component score |
| theta_score | FLOAT | Component score |
| momentum_score | FLOAT | Component score |
| trend_strength_score | FLOAT | Component score |
| supertrend_score | FLOAT | Component score |
| underlying_price | FLOAT | Price at ranking time |
| implied_volatility | FLOAT | Contract IV |
| delta | FLOAT | Option delta |
| gamma | FLOAT | Option gamma |
| theta | FLOAT | Option theta |
| vega | FLOAT | Option vega |
| volume | INT | Daily volume |
| open_interest | INT | Open interest |
| bid | FLOAT | Bid price |
| ask | FLOAT | Ask price |
| run_at | TIMESTAMP | When ranking was generated |

---

## 6. API Endpoints

### Options Chain
```
GET /functions/v1/options-chain?underlying=AAPL
```
Returns: Raw options chain with Greeks

### Options Rankings
```
GET /functions/v1/options-rankings?symbol=AAPL&limit=50
```
Returns: Ranked options with ML scores

### Trigger Ranking Job
```
POST /functions/v1/trigger-ranking
Body: { "symbol": "AAPL" }
```
Returns: Job status and estimated completion time

### Refresh Data (Coordinated Sync)
```
POST /functions/v1/refresh-data
Body: { "symbol": "AAPL", "refreshML": true, "refreshOptions": true }
```
Actions:
1. Fetch new OHLC bars
2. Queue ML forecast job
3. Queue options ranking job

---

## 7. UI Display

### Swift Views

| View | File | Data Source |
|------|------|-------------|
| **Options Ranker** | `OptionsRankerView.swift` | `/options-rankings` |
| **By Expiry View** | `OptionsRankerExpiryView.swift` | Grouped rankings |
| **Rank Detail** | `OptionRankDetailView.swift` | Individual contract |
| **Options Chain** | `OptionsChainView.swift` | `/options-chain` |

### ViewModel

**File:** `ViewModels/OptionsRankerViewModel.swift`

Key Properties:
```swift
@Published var rankings: [OptionRank] = []
@Published var isLoading = false
@Published var isGeneratingRankings = false
@Published var rankingStatus: RankingStatus
@Published var selectedExpiry: String?
@Published var selectedSide: OptionSide?
@Published var minScore: Double = 0.0
```

Key Methods:
```swift
func loadRankings(for symbol: String) async
func triggerRankingJob(for symbol: String) async
func syncAndRank(for symbol: String) async  // Coordinated refresh
```

### UI Components

```
┌─────────────────────────────────────────────────────┐
│ 🧠 ML Options Ranker    [Fresh ✓]  [↻] [⟳ Sync]    │
│                                    50 contracts     │
├─────────────────────────────────────────────────────┤
│ [All Contracts] [By Expiry]                         │
├─────────────────────────────────────────────────────┤
│ Expiry: [All ▼]  Side: [All ▼]  Min Score: [0 ▼]   │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ┌─────────────────────────────────────────────────┐ │
│ │ AAPL Jan 17 $250 Call                           │ │
│ │ ML Score: 85/100  ████████░░                    │ │
│ │ Delta: 0.52 | IV: 32% | Vol: 1,250              │ │
│ │ Bid: $5.20 | Ask: $5.40                         │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ ┌─────────────────────────────────────────────────┐ │
│ │ AAPL Jan 17 $255 Call                           │ │
│ │ ML Score: 78/100  ███████░░░                    │ │
│ │ Delta: 0.38 | IV: 34% | Vol: 890                │ │
│ │ Bid: $3.10 | Ask: $3.30                         │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ ... more contracts ...                              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Rank Detail View
```
┌─────────────────────────────────────────────────────┐
│ AAPL Jan 17 $250 Call                    [Close X] │
├─────────────────────────────────────────────────────┤
│ ML Score: 85/100                                    │
│ ████████████████░░░░                                │
├─────────────────────────────────────────────────────┤
│ Score Breakdown:                                    │
│ ├─ Moneyness:      18/20  ████████░░               │
│ ├─ IV Rank:        14/15  █████████░               │
│ ├─ Liquidity:      13/15  ████████░░               │
│ ├─ Delta:           9/10  █████████░               │
│ ├─ Theta:           8/10  ████████░░               │
│ ├─ Momentum:        9/10  █████████░               │
│ ├─ Trend Strength:  7/10  ███████░░░               │
│ └─ SuperTrend:      7/10  ███████░░░               │
├─────────────────────────────────────────────────────┤
│ Greeks:                                             │
│ Delta: 0.52 | Gamma: 0.045 | Theta: -0.08 | Vega: 0.15 │
├─────────────────────────────────────────────────────┤
│ Market Data:                                        │
│ Bid: $5.20 | Ask: $5.40 | Last: $5.30              │
│ Volume: 1,250 | Open Interest: 8,500               │
│ IV: 32% | HV: 28%                                  │
└─────────────────────────────────────────────────────┘
```

---

## 8. Complete Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     OPTIONS DATA INGESTION                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Polygon Options API ──→ options-chain Edge Function            │
│         │                        │                               │
│         └── Greeks, IV, Bid/Ask, Volume, OI                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     STOCK ML INTEGRATION                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ohlc_bars ──→ technical_indicators.py ──→ ml_forecasts         │
│       │                                         │                │
│       └── Historical volatility                 │                │
│                                                 │                │
│  supertrend_signals ────────────────────────────┘                │
│       │                                                          │
│       └── Trend direction, signal strength, stop levels         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     OPTIONS ML RANKING                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  options_ranking_job.py                                         │
│       │                                                          │
│       ├── EnhancedOptionsRanker.rank_options_with_trend()       │
│       │       │                                                  │
│       │       ├── _score_moneyness()                            │
│       │       ├── _score_iv_rank()                              │
│       │       ├── _score_liquidity()                            │
│       │       ├── _score_delta()                                │
│       │       ├── _score_theta()                                │
│       │       ├── _score_momentum()                             │
│       │       ├── _score_trend_strength()                       │
│       │       └── _score_supertrend()                           │
│       │                                                          │
│       └── Weighted composite → ml_score (0-100)                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        DATA STORAGE                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  options_rankings ◄── upsert_options_rankings()                 │
│       │                                                          │
│       └── Ranked contracts with scores and metadata             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        API LAYER                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  /options-chain ────────→ Raw options data                      │
│  /options-rankings ─────→ Ranked contracts with ML scores       │
│  /trigger-ranking ──────→ Queue ranking job                     │
│  /refresh-data ─────────→ Sync + Queue ML + Options jobs        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        SWIFT UI                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  OptionsRankerViewModel ──→ OptionsRankerView                   │
│       │                         ├── RankerHeader                │
│       │                         ├── AllContractsView            │
│       │                         ├── OptionsRankerExpiryView     │
│       │                         └── RankedOptionRow             │
│       │                                                          │
│       └── OptionRankDetailView (sheet)                          │
│               ├── Score breakdown chart                         │
│               ├── Greeks display                                │
│               └── Market data                                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 9. Key Files Reference

| Category | File Path |
|----------|-----------|
| **Base Ranker** | `ml/src/models/options_ranker.py` |
| **Enhanced Ranker** | `ml/src/models/enhanced_options_ranker.py` |
| **Ranking Job** | `ml/src/options_ranking_job.py` |
| **Multi-Indicator Signals** | `ml/src/strategies/multi_indicator_signals.py` |
| **SuperTrend AI** | `ml/src/strategies/supertrend_ai.py` |
| **Database Layer** | `ml/src/data/supabase_db.py` |
| **Options Chain API** | `backend/supabase/functions/options-chain/index.ts` |
| **Rankings API** | `backend/supabase/functions/options-rankings/index.ts` |
| **Trigger Ranking API** | `backend/supabase/functions/trigger-ranking/index.ts` |
| **Ranker ViewModel** | `client-macos/SwiftBoltML/ViewModels/OptionsRankerViewModel.swift` |
| **Ranker View** | `client-macos/SwiftBoltML/Views/OptionsRankerView.swift` |
| **Expiry View** | `client-macos/SwiftBoltML/Views/OptionsRankerExpiryView.swift` |
| **Detail View** | `client-macos/SwiftBoltML/Views/OptionRankDetailView.swift` |

---

## 10. Scoring Weights Summary

### Base Options Ranker
| Component | Weight |
|-----------|--------|
| Moneyness | 25% |
| IV Rank | 20% |
| Liquidity | 15% |
| Delta Score | 15% |
| Theta Decay | 10% |
| Momentum | 15% |
| **Total** | **100%** |

### Enhanced Options Ranker
| Component | Weight |
|-----------|--------|
| Moneyness | 20% |
| IV Rank | 15% |
| Liquidity | 15% |
| Delta Score | 10% |
| Theta Decay | 10% |
| Momentum | 10% |
| Trend Strength | 10% |
| SuperTrend | 10% |
| **Total** | **100%** |

---

## 11. Integration with Stock ML

The options ranking pipeline depends on the stock ML pipeline for:

| Data | Source | Usage |
|------|--------|-------|
| Trend Direction | `ml_forecasts.overall_label` | Bias call/put selection |
| Signal Strength | `ml_forecasts.trend_confidence` | Weight trend alignment |
| SuperTrend Factor | `ml_forecasts.supertrend_factor` | Validate trend strength |
| SuperTrend Signal | `supertrend_signals` | Entry/exit timing |
| Historical Volatility | `ohlc_bars` → 20-day std | Compare to IV |

**Dependency Chain:**
```
ohlc_bars → Stock ML Pipeline → ml_forecasts → Options Ranker → options_rankings
```

This ensures options rankings are aligned with the underlying stock's ML-derived trend analysis.

---

## 12. Automated Options Refresh (pg_cron)

### Scheduled Jobs

| Job | Schedule (UTC) | Schedule (ET) | Function |
|-----|----------------|---------------|----------|
| `hourly-options-refresh` | `30 14-21 * * 1-5` | Every hour at :30, 9 AM - 4 PM | `refresh_watchlist_options()` |

### Database Functions

```sql
-- Queues ranking jobs for all watchlist symbols
CREATE FUNCTION refresh_watchlist_options() RETURNS void;
```

### How It Works
```
pg_cron (hourly during market hours at :30)
     ↓
refresh_watchlist_options()
     ↓
ranking_jobs table (ranking jobs queued)
     ↓
GitHub Actions ranking_job_worker (processes queue)
     ↓
Options rankings updated automatically
```

**Options data refreshes hourly** - no manual sync required. Offset by 30 minutes from OHLC refresh to spread API load.

---

## 13. Data Providers for Options

### Provider Priority (as of Dec 2024)

| Provider | Data Type | Real-time? | Notes |
|----------|-----------|------------|-------|
| **Yahoo Finance** | Options chain, Greeks | ✅ 15-min delay | Primary provider |
| **Polygon (Massive)** | Historical snapshots | ❌ End of day | Backup/historical |

### Options Chain Endpoint
**File:** `backend/supabase/functions/options-chain/index.ts`

- Cache TTL: 15 minutes for intraday freshness
- Includes full Greeks (delta, gamma, theta, vega, rho)
- Implied volatility per contract

---

## 14. Statistical Significance Testing for Options Ranking

### Validation Module
**File:** `ml/src/evaluation/options_ranking_validation.py`

### Available Tests

| Test | Purpose | What It Measures |
|------|---------|------------------|
| **Spearman Correlation** | Score-return relationship | Do higher scores predict higher returns? |
| **Top vs Bottom Quantile** | Quantile spread | Do top-ranked options outperform bottom? |
| **Information Coefficient (IC)** | Predictive power | Industry standard: IC > 0.05 is good |
| **Hit Rate** | Win percentage | % of positive returns in top quintile |
| **Ranking Stability** | Consistency | Kendall's W across time periods |
| **Score Distribution** | Quality check | Skewness, entropy, spread |

### Usage

```python
from src.evaluation import validate_options_ranking

# Quick validation
results = validate_options_ranking(
    rankings_df,      # DataFrame with ml_score
    returns_df,       # DataFrame with actual_return
)

# Output:
# ✅ Spearman Correlation: 0.15 (p=0.001)
# ✅ Top vs Bottom Quantile Spread: 8.34% (p=0.004)
# ✅ Information Coefficient (IC): 0.07 (Good)
# ✅ Hit Rate: 58.2% (p=0.015)
```

### Detailed Validation

```python
from src.evaluation import OptionsRankingValidator

validator = OptionsRankingValidator(confidence_level=0.95)

# Test ranking accuracy
results = validator.validate_ranking_accuracy(rankings_df, returns_df)

# Test ranking stability over time
stability = validator.validate_ranking_stability(
    [rankings_day1, rankings_day2, rankings_day3]
)

# Analyze score distribution
dist_stats = validator.validate_score_distribution(rankings_df["ml_score"])
```

### Sample Validation Report

```
============================================================
OPTIONS RANKING VALIDATION REPORT
============================================================
Confidence Level: 95%

--- Statistical Tests ---
✅ Spearman Correlation: 0.1523 (p=0.0012, CI=[0.08, 0.22])
   Scores positively correlate with returns (ρ=0.152)

✅ Top vs Bottom Quantile Spread: 0.0834 (p=0.0045)
   Top quintile outperforms bottom by 8.34% (significant)

✅ Information Coefficient (IC): 0.0712 (p=0.0023)
   IC = 0.0712 (Good)

✅ Hit Rate (Top Quantile): 0.5820 (p=0.0156)
   Hit rate: 58.2% (47/81 positive)

--- Score Distribution ---
  Mean: 0.6234
  Std Dev: 0.1856
  Skewness: -0.23
  Good score distribution

============================================================
✅ RANKING MODEL IS STATISTICALLY VALIDATED
   4/4 tests passed
============================================================
```

---

## 15. Key Files Reference (Updated)

| Category | File Path |
|----------|-----------|
| **Base Ranker** | `ml/src/models/options_ranker.py` |
| **Enhanced Ranker** | `ml/src/models/enhanced_options_ranker.py` |
| **Ranking Job** | `ml/src/options_ranking_job.py` |
| **Ranking Job Worker** | `ml/src/ranking_job_worker.py` |
| **Statistical Validation** | `ml/src/evaluation/options_ranking_validation.py` |
| **Multi-Indicator Signals** | `ml/src/strategies/multi_indicator_signals.py` |
| **SuperTrend AI** | `ml/src/strategies/supertrend_ai.py` |
| **Database Layer** | `ml/src/data/supabase_db.py` |
| **Options Chain API** | `backend/supabase/functions/options-chain/index.ts` |
| **Yahoo Finance Client** | `backend/supabase/functions/_shared/providers/yahoo-finance-client.ts` |
| **Provider Router** | `backend/supabase/functions/_shared/providers/router.ts` |
| **Ranker ViewModel** | `client-macos/SwiftBoltML/ViewModels/OptionsRankerViewModel.swift` |
| **Ranker View** | `client-macos/SwiftBoltML/Views/OptionsRankerView.swift` |
