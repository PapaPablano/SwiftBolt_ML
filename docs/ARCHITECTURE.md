# SwiftBolt_ML Architecture

**Last Updated:** February 2026  
**Version:** 1.0.0

---

## 📐 System Overview

SwiftBolt_ML is a full-stack algorithmic trading platform combining machine learning predictions with real-time market data and iOS-native user experience.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         iOS/macOS Client                         │
│                        (SwiftUI + Combine)                       │
└────────────────┬────────────────────────────────────────────────┘
                 │ HTTPS/WebSocket
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Supabase Backend                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Edge Functions│  │  PostgreSQL  │  │  Realtime    │          │
│  │  (Deno/TS)   │  │   Database   │  │  WebSocket   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Data Sources                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Alpaca     │  │   Finnhub    │  │  Market      │          │
│  │  Market Data │  │  News/Events │  │  Intelligence│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                 ▲
                 │
┌────────────────┴────────────────────────────────────────────────┐
│                      ML Pipeline (Python)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Data Ingestion│  │   Models     │  │  Backtesting │          │
│  │  & Features  │  │ ARIMA/XGBoost│  │  & Evaluation│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Component Architecture

### 1. iOS/macOS Client (`client-macos/`)

**Technology Stack:**
- SwiftUI for declarative UI
- Combine for reactive programming
- WebKit for TradingView charts
- URLSession for API communication

**Key Components:**

#### Services Layer
- `APIClient.swift` - HTTP client for Supabase API
- `MarketStatusService.swift` - Real-time market status tracking
- `WebSocketService.swift` - Live data streaming

#### ViewModels
- `ChartViewModel.swift` - Chart data and indicator state
- `SymbolSearchViewModel.swift` - Symbol search and watchlist
- `PortfolioViewModel.swift` - Portfolio tracking

#### Views
- `AdvancedChartView.swift` - Native SwiftUI charts
- `WebChartView.swift` - TradingView integration
- `SymbolSearchView.swift` - Search interface
- `MarketStatusBadge.swift` - Market open/close indicator

**Data Flow:**
```
User Interaction → ViewModel → APIClient → Supabase → Database
                                    ↓
                              Update @Published
                                    ↓
                              SwiftUI Re-render
```

---

### 2. Supabase Backend (`supabase/`)

**Technology Stack:**
- Deno runtime for edge functions
- PostgreSQL 15 for data storage
- PostgREST for auto-generated REST API
- pg_cron for scheduled jobs

**Edge Functions:**

#### Data Collection
- `chart-data-v2` - OHLC data with indicators
- `fetch-bars` - Historical bar fetching
- `run-backfill-worker` - Automated backfill orchestration

#### Market Intelligence
- `sync-market-calendar` - Trading calendar sync (daily)
- `sync-corporate-actions` - Dividend/split tracking (twice daily)
- `adjust-bars-for-splits` - Automatic OHLCV adjustment
- `market-status` - Real-time market status API

#### Analysis
- `options-quotes` - Options chain data
- `support-resistance` - Technical level detection

**Database Schema:**

```sql
-- Core tables
symbols (id, ticker, asset_type, primary_source)
ohlc_bars_v2 (id, symbol_id, timeframe, ts, open, high, low, close, volume, adjusted_for)
market_calendar (date, is_open, market_open, market_close)
corporate_actions (id, symbol, action_type, ex_date, ratio, bars_adjusted)

-- ML & Strategy
ga_strategy_params (id, symbol_id, params, fitness_score)
ranking_evaluations (id, symbol, rank_ic, stability, hit_rate)

-- User data
user_symbols (user_id, symbol_id, is_active)
user_portfolios (user_id, symbol_id, quantity, avg_cost)
```

**Cron Jobs:**
```sql
-- Daily at 2 AM CST
sync-market-calendar-daily

-- Twice daily at 3 AM & 3 PM CST
sync-corporate-actions-twice-daily
```

---

### 3. ML Pipeline (`ml/`)

**Technology Stack:**
- Python 3.10+
- pandas/numpy for data manipulation
- scikit-learn for ML utilities
- statsmodels for time series (ARIMA-GARCH)
- XGBoost for gradient boosting
- pytest for testing

**Module Structure:**

#### `ml/src/models/`
- `arima_garch_forecaster.py` - ARIMA-GARCH time series and volatility (production)
- `tabpfn_forecaster.py` - TabPFN for regime/classification
- `baseline_forecaster.py` - Baseline (Random Forest)
- `enhanced_ensemble_integration.py` / `multi_model_ensemble.py` - 2-model ensemble (LSTM + ARIMA-GARCH) in Phase 7 canary
- `xgboost_forecaster.py` - XGBoost (optional; disabled in canary)

#### `ml/src/features/`
- `technical_indicators.py` - RSI, MACD, Bollinger Bands
- `market_regime.py` - Trend/volatility regime detection
- `feature_engineering.py` - Feature creation pipeline

#### `ml/src/strategies/`
- `momentum_strategy.py` - Momentum-based trading
- `mean_reversion_strategy.py` - Mean reversion logic
- `options_strategy.py` - Options-specific strategies

#### `ml/src/backtesting/`
- `backtest_engine.py` - Strategy validation
- `performance_metrics.py` - Sharpe, max drawdown, etc.

**ML Workflow:**
```
1. Data Ingestion (Alpaca API, Supabase ohlc_bars)
   ↓
2. Feature Engineering (technical indicators, simplified 29-feature set, regime detection)
   ↓
3. Model Training (LSTM, ARIMA-GARCH; XGBoost/TabPFN for experiments)
   ↓
4. Prediction Generation (unified_forecast_job.py, intraday_forecast_job.py)
   ↓
5. Walk-Forward Validation & Divergence Monitoring (Phase 7 canary)
   ↓
6. Performance Monitoring (evaluation_job_daily/intraday, ensemble_validation_metrics)
```

**Phase 7 / Ensemble & Canary (Feb 2026):** Production ensemble uses 2 models (LSTM + ARIMA-GARCH). Transformer disabled. Walk-forward optimizer and divergence monitor feed `ensemble_validation_metrics`. Canary runs on AAPL, MSFT, SPY (1D) for 6 days; GO/NO-GO decision per `1_27_Phase_7.1_Schedule.md`.

---

## 🔄 Data Flow

### Real-Time Chart Data Flow

```
1. iOS App requests chart data
   GET /functions/v1/chart-data-v2?symbol=AAPL&timeframe=1D
   
2. Edge function checks cache
   - Cache hit: Return cached data
   - Cache miss: Proceed to step 3
   
3. Query database for existing bars
   SELECT * FROM ohlc_bars_v2 
   WHERE symbol_id = ? AND timeframe = ?
   
4. Identify gaps in data
   
5. Fetch missing bars from Alpaca
   alpaca.get_bars(symbol, timeframe, start, end)
   
6. Store new bars in database
   INSERT INTO ohlc_bars_v2 (...)
   
7. Calculate technical indicators
   - RSI, MACD, Bollinger Bands, SuperTrend
   
8. Return enriched data to client
   {
     bars: [...],
     indicators: {...},
     provider: "alpaca"
   }
```

### Corporate Actions Flow

```
1. Cron job triggers sync-corporate-actions (3 AM, 3 PM CST)
   
2. Fetch active symbols from database
   SELECT ticker FROM symbols
   
3. Query Alpaca for corporate actions (past 90 days)
   alpaca.queryCorporateActions(symbols, types: "split,dividend")
   
4. Upsert to corporate_actions table
   INSERT INTO corporate_actions (...) ON CONFLICT DO UPDATE
   
5. For new splits: trigger adjust-bars-for-splits
   
6. Adjust historical OHLCV data
   UPDATE ohlc_bars_v2 
   SET open = open / ratio,
       high = high / ratio,
       low = low / ratio,
       close = close / ratio,
       volume = volume * ratio,
       adjusted_for = corporate_action_id
   WHERE ts < ex_date AND adjusted_for IS NULL
   
7. Mark corporate action as processed
   UPDATE corporate_actions SET bars_adjusted = true
```

---

## 🔐 Security Architecture

### Authentication & Authorization

**Supabase Auth:**
- JWT-based authentication
- Row-Level Security (RLS) policies
- Service role key for backend operations
- Anon key for client-side access

**API Security:**
```sql
-- Example RLS policy
CREATE POLICY "Users can only see their own symbols"
ON user_symbols FOR SELECT
USING (auth.uid() = user_id);
```

### Secrets Management

**Environment Variables:**
- `ALPACA_API_KEY` - Alpaca market data API
- `ALPACA_API_SECRET` - Alpaca secret key
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Backend service key
- `FINNHUB_API_KEY` - News and events data

**Storage:**
- Local development: `.env` file (gitignored)
- Production: Supabase edge function secrets
- CI/CD: GitHub Actions secrets

---

## 📊 Performance Considerations

### Database Optimization

**Indexes:**
```sql
-- Critical indexes for query performance
CREATE INDEX idx_ohlc_bars_v2_symbol_timeframe_ts 
ON ohlc_bars_v2(symbol_id, timeframe, ts DESC);

CREATE INDEX idx_corporate_actions_symbol_date 
ON corporate_actions(symbol, ex_date DESC);

CREATE INDEX idx_market_calendar_date 
ON market_calendar(date);
```

**Query Optimization:**
- Use prepared statements
- Limit result sets with pagination
- Leverage database-side aggregations
- Cache frequently accessed data

### Caching Strategy

**Levels:**
1. **Edge Function Memory Cache** - In-memory for single request
2. **Database Query Cache** - PostgreSQL query cache
3. **Client-Side Cache** - iOS URLCache for API responses

**TTL (Time To Live):**
- Market calendar: 24 hours
- OHLC bars (historical): 1 hour
- Real-time quotes: 5 seconds
- Corporate actions: 12 hours

### Rate Limiting

**Alpaca API:**
- Limit: 200 requests/minute (default)
- Can request increase to 1,000 req/min
- Implemented: Token bucket rate limiter

**Implementation:**
```typescript
const rateLimiter = new TokenBucketRateLimiter({
  alpaca: { requestsPerMinute: 200, burstSize: 50 }
});
```

---

## 🔄 Deployment Architecture

### Environments

1. **Development** - Local machine
   - Local Supabase instance (optional)
   - Python virtual environment
   - Xcode simulator

2. **Staging** - Supabase staging project
   - Separate database
   - Test edge functions
   - iOS TestFlight builds

3. **Production** - Supabase production project
   - Live database with backups
   - Deployed edge functions
   - App Store releases

### CI/CD Pipeline

```
GitHub Push → GitHub Actions
    ↓
Run Tests (pytest, XCTest)
    ↓
Lint & Format Check
    ↓
Build Artifacts
    ↓
Deploy to Supabase (main branch only)
    ↓
Run Integration Tests
    ↓
Notify on Slack/Email
```

---

## 🧪 Testing Strategy

### Test Pyramid

```
        /\
       /  \      E2E Tests (5%)
      /────\     - iOS UI tests
     /      \    - End-to-end workflows
    /────────\   
   /          \  Integration Tests (15%)
  /────────────\ - API integration
 /              \- Database queries
/────────────────\
Unit Tests (80%)
- Model logic
- Feature engineering
- Utility functions
```

### Test Coverage Targets

- **Overall:** 70% minimum (enforced by CI)
- **ML Models:** 90%+ (critical path)
- **Edge Functions:** 60%+
- **iOS ViewModels:** 80%+

---

## 📈 Monitoring & Observability

### Metrics to Track

**System Health:**
- API response times (p50, p95, p99)
- Database query performance
- Edge function execution time
- Error rates by endpoint

**Business Metrics:**
- Active users
- Symbols tracked
- Predictions generated
- Backfill completion rate

**ML Performance:**
- Model accuracy (RMSE, MAE)
- Prediction latency
- Feature drift detection
- Ranking IC (information coefficient)

### Logging

**Levels:**
- ERROR: Critical failures
- WARN: Degraded performance
- INFO: Normal operations
- DEBUG: Detailed diagnostics

**Tools:**
- Supabase Logs for edge functions
- Python logging module for ML pipeline
- iOS OSLog for client-side logging

---

## 🔮 Future Architecture Considerations

### Scalability

**Horizontal Scaling:**
- Supabase automatically scales edge functions
- PostgreSQL read replicas for heavy queries
- CDN for static assets

**Vertical Scaling:**
- Upgrade database instance size
- Optimize queries and indexes
- Implement connection pooling

### Potential Enhancements

1. **Real-Time Streaming**
   - WebSocket for live quotes
   - Server-Sent Events for predictions

2. **Microservices**
   - Separate ML prediction service
   - Dedicated backfill service
   - Independent options analysis service

3. **Multi-Region**
   - Deploy edge functions globally
   - Database replication across regions
   - Reduced latency for international users

---

## 📚 Related Documentation

- [ML Models Documentation](./ML_MODELS.md)
- [API Reference](./API_REFERENCE.md)
- [Setup Guide](./SETUP.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Migration Guide](./MIGRATION_GUIDE.md)

---

**Maintained by:** Eric Peterson  
**Questions?** Open an issue on GitHub
