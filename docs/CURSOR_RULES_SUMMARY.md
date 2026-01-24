# SwiftBolt_ML Custom Cursor Rules - Implementation Summary

**Date Created**: January 23, 2026

**Location**: `/Users/ericpeterson/SwiftBolt_ML/.cursor/rules/`

## What Was Created

A comprehensive, production-grade cursor rule set specifically tailored to your SwiftBolt_ML machine learning trading platform. These rules guide the Cursor IDE to generate code and provide context aligned with your project's architecture, best practices, and domain expertise.

---

## Files Created (5 Total)

### 1. **`.cursorrules`** (Master Configuration)
- **Size**: ~3.2 KB
- **Purpose**: Master rule file automatically loaded by Cursor IDE
- **Contains**:
  - Your core expertise in ML trading systems
  - Technology stack: Python, Swift, Supabase, AWS, Streamlit
  - Financial data integration (Alpaca, Finnhub, Polygon)
  - Key principles (async patterns, error handling, production standards)
  - File organization and project structure
  - Production deployment checklist

**How It Works**: Cursor loads this file automatically when working in your project. It provides the foundational context for all code generation and analysis.

---

### 2. **`python-fastapi-backend.mdc`** (FastAPI Standards)
- **Size**: ~8.5 KB
- **Purpose**: Standards for Python backend development
- **Covers**:
  - FastAPI endpoint patterns with async/await
  - Pydantic models and validation
  - Error handling with guard clauses
  - Supabase database integration (connection pooling, parameterized queries)
  - Concurrent API requests with retries and rate limiting
  - Structured logging at decision points
  - Configuration management (environment variables)
  - Testing patterns (pytest, mocks, async tests)

**Applied To**: `ml/**/*.py`, `ml/src/**/*.py`, `ml/api/**/*.py` files

**Example Pattern**:
```python
@app.get("/api/v1/options/{symbol}/chain")
async def get_option_chain(
    symbol: str = Path(...),
    expiration_date: str = Query(...),
    db = Depends(get_db_connection)
) -> list[GreeksResponse]:
    # Guard clauses first
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    
    try:
        chain = await fetch_option_chain_async(symbol, expiration_date)
        if not chain:
            raise HTTPException(status_code=404, detail="No options found")
        # ... process and return
    except ApiError as e:
        logger.error(f"API error: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Market data unavailable")
```

---

### 3. **`ml-pipeline-standards.mdc`** (ML Pipeline Standards)
- **Size**: ~11.2 KB
- **Purpose**: Standards for machine learning pipeline development
- **Covers**:
  - Data ingestion with validation (OHLCV checking)
  - Data cleaning (NaN handling, outlier removal)
  - Feature engineering (50+ features: MAs, volatility, RSI, MACD, etc.)
  - Walk-forward validation (expanding window backtesting)
  - XGBoost training with hyperparameter optimization (Optuna)
  - Model monitoring and performance degradation detection
  - Data drift detection (statistical tests)
  - Experiment tracking and reproducibility

**Applied To**: `ml/src/**/*.py`, `ml/api/**/*.py`, `ml/tests/**/*.py` files

**Key Concept - Walk-Forward Validation**:
```python
# Day 1-252: Train | Day 253-273: Test
# Day 22-273: Train | Day 274-294: Test
# Day 43-294: Train | Day 295-315: Test
# ... continues expanding
```
This ensures out-of-sample performance metrics are realistic.

---

### 4. **`options-greeks-trading.mdc`** (Options & Greeks Standards)
- **Size**: ~12.8 KB
- **Purpose**: Options pricing and Greeks calculation standards
- **Covers**:
  - Black-Scholes option pricing (calls and puts)
  - Greeks calculation:
    - **Delta**: Price sensitivity (0-1 for calls, -1-0 for puts)
    - **Gamma**: Delta's rate of change (peaks at ATM)
    - **Theta**: Time decay per day (negative for long, positive for short)
    - **Vega**: Volatility sensitivity (per 1% IV change)
    - **Rho**: Interest rate sensitivity
  - Portfolio Greeks aggregation (summing across all positions)
  - Greeks monitoring with risk limits
  - Multi-leg strategy builders (Iron Butterfly, Long Straddle, etc.)

**Applied To**: `ml/src/**/*.py`, `ml/api/**/*.py` files

**Example**:
```python
# ATM call with 30% IV and 30 days to expiry
delta = 0.65    # Move $65 per $100 stock move
gamma = 0.05    # Delta increases 0.05 for each $1 stock move
theta = -0.25   # Lose $25 per day from time decay
vega = 45       # Gain/lose $45 for each 1% IV change
```

---

### 5. **`swift-real-time-charting.mdc`** (Swift App Development)
- **Size**: ~10.5 KB
- **Purpose**: Standards for iOS/macOS app development
- **Covers**:
  - Modern Swift concurrency (async/await, actors)
  - Real-time data binding with Combine
  - WebSocket integration for live market data
  - SwiftUI charting components
  - API integration with exponential backoff retry logic
  - Cache management with TTL (time-to-live)
  - Error handling with specific error types
  - Production app architecture (dependency injection, lifecycle management)

**Applied To**: `client-macos/**/*.swift`, `client-macos/SwiftBoltML/**/*.swift` files

**Key Pattern - Real-Time Chart Updates**:
```swift
// Buffer updates and apply in batches to reduce UI redraws
updateSubject
    .buffer(size: 10, timeSpan: 1, scheduler: DispatchQueue.main)
    .sink { updates in
        applyBatchUpdate(updates)  // Update all 10 points at once
    }
    .store(in: &subscriptions)
```

---

### 6. **`README.md`** (Comprehensive Documentation)
- **Size**: ~8.3 KB
- **Purpose**: Complete guide to using the cursor rules
- **Contains**:
  - Overview of all rule files
  - Integration instructions
  - Quick reference for common tasks
  - Key principles and best practices
  - File structure and organization
  - Configuration examples
  - Links to related documentation

---

## How to Use These Rules

### Automatic Loading
1. The `.cursorrules` file is automatically loaded whenever you work in the SwiftBolt_ML project
2. File-specific rules (`.mdc` files) apply automatically based on glob patterns

### Manual Reference
1. **In Cursor IDE**, use slash commands:
   ```
   /request_rules python-fastapi-backend.mdc
   /request_rules options-greeks-trading.mdc
   ```

2. **In Cursor Chat**, reference specific patterns:
   ```
   "Following ml-pipeline-standards, how would I implement feature engineering?"
   ```

### Practical Examples

**Building a new API endpoint**:
- Start with `python-fastapi-backend.mdc` patterns
- Use async/await, Pydantic models, guard clauses
- Example: `/request_rules python-fastapi-backend.mdc` then "Create endpoint to fetch option chain"

**Creating ML forecast model**:
- Use `ml-pipeline-standards.mdc` patterns
- Ingest → validate → engineer features → walk-forward backtest
- Example: "/request_rules ml-pipeline-standards.mdc" then "Build XGBoost model for price prediction"

**Calculating portfolio Greeks**:
- Use `options-greeks-trading.mdc` patterns
- Calculate Greeks for each position, aggregate across portfolio
- Example: "/request_rules options-greeks-trading.mdc" then "Monitor portfolio Greeks and check limits"

**Building real-time chart UI**:
- Use `swift-real-time-charting.mdc` patterns
- WebSocket → buffer updates → batch UI redraws
- Example: "/request_rules swift-real-time-charting.mdc" then "Create real-time price chart"

---

## Key Improvements Over Generic Rules

### 1. Domain-Specific Expertise
✅ Options pricing and Greeks calculations (not just generic trading)
✅ Walk-forward validation for time-series ML models
✅ Multi-leg options strategy builders
✅ Portfolio risk management patterns
✅ Quantitative finance best practices

### 2. Your Technology Stack
✅ FastAPI + async/await patterns (not generic REST)
✅ Supabase integration with connection pooling
✅ Alpaca Markets API specific patterns
✅ Swift concurrency (async/await, actors)
✅ Combine reactive programming

### 3. Production Standards
✅ Structured logging at decision points
✅ Error handling with specific exception types
✅ Configuration management (environment variables)
✅ Circuit breakers and graceful degradation
✅ Real-time monitoring patterns

### 4. Your Project Structure
✅ Backend ML pipeline organization
✅ Trading logic and risk management
✅ Frontend real-time charting
✅ Database schema patterns
✅ Cloud deployment (AWS Lambda)

---

## Integration with awesome-cursorrules

These rules were created by:
1. **Studying patterns** from awesome-cursorrules examples (FastAPI, React, etc.)
2. **Adapting to your domain**: Machine learning + quantitative trading
3. **Incorporating your expertise**: Options Greeks, walk-forward validation, multi-timeframe analysis
4. **Using your project context**: Python backend, Swift frontend, Supabase database

The result is a highly specialized rule set that's more useful than generic rules for your specific project.

---

## Updating and Extending

As your project evolves, you can:

1. **Update existing rules** as patterns change:
   ```bash
   vi .cursor/rules/python-fastapi-backend.mdc
   ```

2. **Create new domain rules** for new areas:
   ```bash
   # Example: Database query patterns
   touch .cursor/rules/database-sql-patterns.mdc
   ```

3. **Reference in code**: Link new rules to file patterns in the rule file header:
   ```yaml
   ---
   description: Database query optimization patterns
   globs: backend/data/**/*.py
   ---
   ```

4. **Version control**: All rules are tracked in git, so you can see evolution

---

## Next Steps

1. **Start using the rules**: Open Cursor IDE and work on the project as normal
   - The `.cursorrules` file will automatically provide context
   - Rules will guide code generation and suggestions

2. **Reference specific rules** when asking for code:
   ```
   "/request_rules options-greeks-trading.mdc Calculate portfolio Greeks"
   ```

3. **Integrate with existing code**: Use rules when refactoring
   ```
   "/request_rules python-fastapi-backend.mdc Refactor this endpoint to follow patterns"
   ```

4. **Train the model**: The more you use these rules, the better Cursor learns your patterns

---

## File Locations

```
SwiftBolt_ML/
└── .cursor/
    └── rules/
        ├── .cursorrules                    ← Main rule file (auto-loaded)
        ├── README.md                       ← Documentation
        ├── python-fastapi-backend.mdc      ← FastAPI patterns
        ├── ml-pipeline-standards.mdc       ← ML pipeline patterns
        ├── options-greeks-trading.mdc      ← Options & Greeks patterns
        └── swift-real-time-charting.mdc    ← Swift app patterns
```

---

## Summary

You now have a **complete, production-grade cursor rule set** that:

✅ **Guides code generation** with domain-specific patterns
✅ **Enforces best practices** for ML trading systems
✅ **Reduces boilerplate** by automating common patterns
✅ **Improves code quality** with structured error handling and logging
✅ **Accelerates development** with ready-to-use implementations
✅ **Maintains consistency** across Python, Swift, and SQL code
✅ **Scales with your project** as new patterns emerge

These rules will significantly improve your development velocity and code consistency across SwiftBolt_ML!

---

**Created By**: Claude (AI Assistant)
**For**: SwiftBolt_ML Project  
**Based On**: awesome-cursorrules + project-specific customization  
**Date**: January 23, 2026
