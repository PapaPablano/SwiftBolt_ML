# SwiftBolt_ML Cursor Rules

Custom Cursor IDE rules for SwiftBolt_ML - a machine learning-driven quantitative trading platform integrating ML forecasting, options pricing, and real-time trading infrastructure.

## Rule Files Overview

### 1. `.cursorrules` (Master Configuration)
**Purpose**: Master rule file that Cursor IDE loads automatically

**Content**:
- Core project expertise (ML, quantitative finance, trading systems)
- Technology stack overview (Python, Swift, Supabase, AWS)
- Key principles and coding standards
- File organization and structure
- Production checklist

**When to Use**: This is the global context loaded for all interactions with this project.

---

### 2. `python-fastapi-backend.mdc` 
**Purpose**: Python backend development standards

**Coverage**:
- FastAPI endpoint patterns with async/await
- Pydantic models for validation
- Error handling and early returns (guard clauses)
- Supabase database integration with connection pooling
- Parameterized queries and bulk operations
- Async patterns for API calls (retries, concurrency, rate limiting)
- Structured logging at decision points
- Configuration management via environment variables
- Testing patterns with pytest and mocks

**File Patterns**: `backend/**/*.py`

**Use When**:
- Building FastAPI endpoints
- Integrating with Alpaca or other APIs
- Writing database queries
- Implementing error handling and logging

**Key Patterns**:
```python
# Async endpoint with guard clauses
@app.get("/api/v1/options/{symbol}/chain")
async def get_option_chain(
    symbol: str = Path(...),
    expiration_date: str = Query(...),
    db = Depends(get_db_connection)
) -> list[GreeksResponse]:
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    # ... rest of implementation
```

---

### 3. `ml-pipeline-standards.mdc`
**Purpose**: Machine learning pipeline standards

**Coverage**:
- Data ingestion with validation
- Data quality checks (NaN, outliers, logic validation)
- Feature engineering (moving averages, volatility, momentum, RSI, MACD)
- Walk-forward validation for time-series models
- XGBoost training and hyperparameter optimization
- Model monitoring and performance degradation detection
- Data drift detection using statistical tests
- Experiment tracking and reproducibility

**File Patterns**: `backend/ml/**/*.py`

**Use When**:
- Building ML forecasting models
- Creating feature sets for time-series prediction
- Backtesting strategies with walk-forward validation
- Monitoring model performance in production
- Optimizing hyperparameters

**Key Concepts**:
- **Walk-Forward Validation**: Expand training window, fixed test window, expanding step
- **Feature Engineering**: Create 50+ features from price data (moving averages, volatility bands, momentum indicators)
- **Model Monitoring**: Track R², MAPE, and statistical drift
- **Experiment Tracking**: Log all experiments with metadata for reproducibility

**Example**:
```python
# Walk-forward backtest
wfv = WalkForwardValidator(train_size=252, test_size=21, step_size=21)
results = await wfv.backtest_model(model, X, y)
avg_score = np.mean(results["test_scores"])  # Out-of-sample performance
```

---

### 4. `options-greeks-trading.mdc`
**Purpose**: Options pricing, Greeks calculation, and risk management

**Coverage**:
- Black-Scholes option pricing (calls and puts)
- Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
- Greeks interpretation and trading implications
- Portfolio Greeks aggregation
- Greeks monitoring and risk limits
- Multi-leg strategy builders (Iron Butterfly, Long Straddle, etc.)
- Position Greeks with contract multiplier adjustments

**File Patterns**: `backend/trading/**/*.py`

**Use When**:
- Pricing option contracts
- Calculating Greeks for positions
- Monitoring portfolio Greeks exposure
- Building multi-leg strategies
- Implementing risk management

**Key Formulas**:
- **Delta**: Price sensitivity (call: 0→1, put: -1→0, ATM ≈ ±0.5)
- **Gamma**: Delta's rate of change (peaks at ATM, decreases far OTM/ITM)
- **Theta**: Daily time decay (negative for long, positive for short)
- **Vega**: Volatility sensitivity (per 1% IV change)
- **Portfolio Delta**: Sum of (individual delta × 100 × quantity) across all positions

**Example**:
```python
# Calculate Greeks for option
greeks = GreeksCalculator.delta(
    "call", 
    spot_price=150, 
    strike_price=150, 
    time_to_expiry=0.25, 
    volatility=0.30
)  # Returns 0.5 for ATM call

# Aggregate portfolio Greeks
portfolio_greeks = await monitor.aggregate_portfolio_greeks(positions)
if abs(portfolio_greeks.total_delta) > 50:  # Max 50 delta exposure
    await trigger_hedge()
```

---

### 5. `swift-real-time-charting.mdc`
**Purpose**: Swift development standards for iOS/macOS apps

**Coverage**:
- Modern Swift concurrency (async/await, actors)
- Real-time data binding with Combine
- WebSocket integration for live data
- SwiftUI charting components
- API integration with retry logic
- Cache management with TTL (time-to-live)
- Error handling with specific types
- Production app architecture (dependency injection, lifecycle)

**File Patterns**: `frontend/**/*.swift`

**Use When**:
- Building iOS/macOS trading apps
- Implementing real-time charting
- Integrating with WebSocket API
- Caching API responses
- Managing async operations

**Key Patterns**:
```swift
// Async/await with error handling
func fetchStockPrice(symbol: String) async throws -> Double {
    let price = try await apiClient.getLatestPrice(symbol: symbol)
    return price
}

// Real-time chart updates with batching
price
    .buffer(size: 10, timeSpan: 1, scheduler: DispatchQueue.main)
    .sink { updates in
        applyBatchUpdate(updates)  // Batch UI updates
    }
    .store(in: &subscriptions)

// Cache with 5-minute TTL
optionChainCache.set(chain, forKey: cacheKey, ttl: 300)
```

---

## Integration with Cursor IDE

### How to Use

1. **Automatic Loading**: Place `.cursorrules` in project root - Cursor loads automatically

2. **Manual Reference**: Reference specific `.mdc` files in Cursor commands:
   ```
   /request_rules python-fastapi-backend.mdc
   /request_rules options-greeks-trading.mdc
   ```

3. **Glob Pattern Matching**: Cursor applies rules based on file patterns:
   - Python backend rules apply to `backend/**/*.py`
   - ML rules apply to `backend/ml/**/*.py`
   - Swift rules apply to `frontend/**/*.swift`

### Cursor Features

- **Slash Commands**: Use `/request_rules filename.mdc` to load specific context
- **Context Window**: Rules provide context for code generation and analysis
- **Code Generation**: Generated code follows established patterns and standards
- **Error Prevention**: Catches common mistakes (missing guards, unhandled errors, etc.)

---

## Quick Reference: Common Tasks

### Building a New FastAPI Endpoint
**Reference**: `python-fastapi-backend.mdc`

1. Define Pydantic request/response models
2. Use `async def` for I/O operations
3. Add guard clauses at function start
4. Use `.guard()` pattern for error handling
5. Log at decision points
6. Add database integration with parameterized queries
7. Write tests with mocks

### Creating ML Forecasting Model
**Reference**: `ml-pipeline-standards.mdc`

1. Ingest data with validation
2. Create feature set (50+ features)
3. Split with walk-forward validator
4. Train XGBoost with optimized hyperparameters
5. Validate out-of-sample performance
6. Monitor for performance degradation and data drift
7. Log experiments with metadata

### Calculating Option Greeks
**Reference**: `options-greeks-trading.mdc`

1. Calculate time to expiry in years
2. Compute d1, d2 using Black-Scholes
3. Calculate Greeks (delta, gamma, theta, vega, rho)
4. Multiply by contract multiplier (100) and quantity
5. Aggregate Greeks across positions
6. Check against risk limits

### Building Real-Time Chart
**Reference**: `swift-real-time-charting.mdc`

1. Create data models (ChartDataPoint)
2. Set up WebSocket subscription
3. Buffer updates to batch UI redraws
4. Display with SwiftUI Charts
5. Cache API responses with TTL
6. Handle errors with specific error types
7. Use async/await for concurrency

---

## Key Principles

### Code Quality
- **Type Safety**: Use type hints (Python) and explicit types (Swift)
- **Error Handling**: Guard clauses, specific error types, comprehensive logging
- **Performance**: Async operations, caching, batching updates
- **Testing**: Unit tests for critical logic, walk-forward for ML models

### Production Standards
- Configuration via environment variables
- Structured logging at decision points
- Graceful error handling and recovery
- Resource cleanup (connection pooling, cache TTL)
- Monitoring and alerting
- No hardcoded secrets or credentials

### Data Quality
- Validate at ingestion
- Log quality metrics
- Detect and handle outliers
- Monitor for data drift
- Version datasets

---

## File Structure

```
SwiftBolt_ML/
├── .cursor/
│   ├── rules/
│   │   ├── .cursorrules                    # Master config
│   │   ├── README.md                       # This file
│   │   ├── python-fastapi-backend.mdc      # FastAPI patterns
│   │   ├── ml-pipeline-standards.mdc       # ML pipeline standards
│   │   ├── options-greeks-trading.mdc      # Options and Greeks
│   │   └── swift-real-time-charting.mdc    # Swift app development
│   ├── references/                         # Reference documentation
│   └── skills/                             # Specialized skills
├── backend/                                # Python ML/API backend
│   ├── ml/                                 # Model training, inference
│   ├── api/                                # FastAPI endpoints
│   ├── data/                               # Data processing
│   ├── trading/                            # Trading logic, risk management
│   └── utils/                              # Shared utilities
├── frontend/                               # Swift/iOS/macOS apps
└── database/                               # Supabase migrations
```

---

## Configuration Files

### Environment Variables (.env)
```bash
# API Keys
ALPACA_API_KEY=pk_...
ALPACA_SECRET_KEY=...
SUPABASE_URL=https://...
SUPABASE_KEY=...

# Trading Configuration
MAX_POSITION_LOSS=1000.0
MAX_PORTFOLIO_DELTA=0.5
ENABLE_LIVE_TRADING=false
```

---

## Related Documentation

See `.cursor/references/` for detailed guides:
- **greeks.md** - Greeks calculation reference
- **options_reference_scripts/** - Example implementations
- **strategies.md** - Trading strategy descriptions
- **artifacts.md** - Model artifact storage and versioning

---

## Updating Rules

As the project evolves:

1. **Update `.cursorrules`** for new global principles
2. **Create new `.mdc` files** for new domains (e.g., `database-queries.mdc`)
3. **Refactor rules** when patterns change
4. **Document new patterns** in `.mdc` files
5. **Version control**: Track rule changes in git

---

**Last Updated**: January 23, 2026

**Customized For**: SwiftBolt_ML - ML-Driven Quantitative Trading Platform

**Based On**: awesome-cursorrules + project-specific adaptations
