# Claude Development Rules for SwiftBolt ML

This document defines the development principles, code standards, and expertise areas for Claude when working on SwiftBolt ML. These rules are merged from both Claude and Cursor configurations to ensure consistency across AI assistants.

---

## Core Expertise

**Machine Learning & Quantitative Finance**
- Time-series forecasting (ARIMA-GARCH, XGBoost, Transformer networks)
- Options pricing and Greeks calculation (Black-Scholes, Binomial models)
- Technical analysis and indicator development
- Walk-forward analysis and backtesting frameworks
- Portfolio risk management and volatility modeling

**Technologies & Stack**
- Python: ML pipelines, data processing, statistical analysis
- Swift: macOS/iOS applications, real-time charting
- Supabase: PostgreSQL database, edge functions, real-time subscriptions
- AWS: Lambda functions, cloud infrastructure, scheduled jobs
- Streamlit: Rapid dashboard prototyping and data visualization
- Docker: Containerization and deployment

**Financial Data Integration**
- Alpaca Markets API (stock quotes, options chains, live trading)
- Finnhub, Polygon.io, Alpha Vantage APIs
- Real-time price feeds and multi-timeframe charting
- Options data structures and chain processing
- Technical indicators (KDJ, Bollinger Bands, RSI, MACOS, SuperTrend)

---

## Key Principles

- Write concise, technical responses with accurate examples specific to ML trading systems
- Favor modular, testable components over monolithic functions
- Prioritize data quality and reproducibility in ML workflows
- Use functional, declarative programming; avoid unnecessary classes
- Implement comprehensive error handling and input validation
- Design for production: logging, monitoring, graceful degradation
- Use descriptive variable names with domain context (e.g., `is_bullish`, `has_confluence`)
- Optimize for both accuracy and computational efficiency
- NEVER propose code changes without reading the file first
- Avoid over-engineering; only make changes directly requested or clearly necessary
- Trust internal code and framework guarantees; only validate at system boundaries

---

## Code Standards

### Python
- Use async/await for I/O-bound operations (API calls, database queries)
- Type hints for all function signatures
- Docstrings with parameter descriptions and example usage
- Early returns for error conditions (guard clauses)
- Comprehensive logging at decision points
- DRY principle: extract reusable utilities
- Follow PEP 8 with 88-character line limit (Black formatter)

### Swift
- Use modern Swift concurrency (async/await, actors)
- Type-safe implementations with proper error handling
- MARK: comments for code organization
- Leverage SwiftUI for UI components
- Cache manager patterns for API responses
- Real-time data binding with Combine

### SQL (Supabase/PostgreSQL)
- Use parameterized queries to prevent SQL injection
- Index frequently queried columns
- Aggregate data at query time when possible
- Use materialized views for complex calculations
- Implement proper foreign key relationships

---

## Project-Specific Patterns

### ML Pipeline
- Data ingestion → validation → transformation → feature engineering
- Walk-forward validation with expanding windows
- Track experiment metadata (params, metrics, timestamps)
- Version datasets and model artifacts
- Automated retraining on schedule or trigger

### Options Analysis
- Quote option chains from Alpaca API
- Calculate Greeks (delta, gamma, theta, vega, rho) for positions
- Build payoff diagrams for multi-leg strategies
- Monitor implied volatility across expirations
- Track Greeks in portfolio aggregation

### Real-Time Data Processing
- Buffer data points for multi-timeframe analysis
- Implement exponential backoff for API retries
- Cache market data with intelligent TTL
- Handle data gaps and recovery scenarios
- Emit real-time signals for trading automation

### Risk Management
- Position limits enforcement (max loss, Greeks exposure)
- Portfolio greeks monitoring (aggregate delta/gamma/theta/vega)
- Correlation risk tracking across holdings
- Automated hedge calculations
- Daily P/L and performance attribution

---

## File Organization

```
SwiftBolt_ML/
├── backend/          # Python ML/API backend
│   ├── ml/          # Model training, inference
│   ├── api/         # FastAPI endpoints
│   ├── data/        # Data processing pipelines
│   ├── trading/     # Trading logic, risk management
│   └── utils/       # Shared utilities
├── frontend/         # Swift/iOS/macOS apps
├── database/        # Supabase migrations, functions
├── cloud/           # AWS Lambda, deployment configs
├── .claude/         # Claude rules and configuration
└── .cursor/         # Cursor IDE rules and references
```

---

## Dependencies & Imports

### Key Python Libraries
- numpy, pandas, scipy: numerical computing
- scikit-learn, xgboost, statsmodels: ML and statistical models
- fastapi, pydantic: API development and validation
- alpaca-trade-api, yfinance: market data
- plotly, streamlit: visualization
- psycopg2, sqlalchemy: database access
- pydantic-settings: configuration management

### Key Swift Frameworks
- SwiftUI, Combine: UI and reactive programming
- URLSession: HTTP networking
- Foundation, os.log: system utilities

---

## Error Handling

- Use specific exception types or Result types
- Log errors with full context (function, parameters, exception)
- Provide user-friendly error messages separate from technical details
- Implement retry logic with exponential backoff for transient failures
- Use early returns to avoid deeply nested if statements

---

## Performance Optimization

- Profile code before optimizing; measure improvements
- Use vectorized operations (numpy/pandas) instead of loops
- Cache expensive API calls and computations
- Lazy load large datasets
- Use generators for memory-efficient processing
- Parallelize independent tasks using async or multiprocessing

---

## Testing & Validation

- Write tests for critical trading logic and calculations
- Use walk-forward validation for ML models
- Validate model predictions against backtested results
- Track data quality metrics continuously
- Implement circuit breakers for anomaly detection

---

## Production Checklist

- [ ] Proper error handling and logging throughout
- [ ] Configuration management via environment variables
- [ ] Database migrations and connection pooling
- [ ] API rate limiting and request validation
- [ ] Real-time monitoring and alerting
- [ ] Graceful shutdown and resource cleanup
- [ ] Security: no hardcoded secrets, SQL injection protection
- [ ] Documentation: README, API docs, trading logic explanations
- [ ] CI/CD: automated tests and deployment pipelines

---

## Claude Code Specific Practices

When using Claude Code CLI or VSCode extension:

- Always read files before proposing edits
- Use TodoWrite tool for multi-step tasks
- Use Task tool with specialized agents (Explore, Plan, etc.) for complex investigations
- Provide markdown links when referencing files: `[filename](path/to/file)`
- Mark todos as completed immediately after finishing
- Avoid creating new files; prefer editing existing ones
- Use parallel tool calls for independent operations
- Trust framework guarantees; only validate at boundaries
- Focus on minimal, focused changes—avoid scope creep

---

## Available Claude Code Skills & Commands

Claude Code provides specialized skills (slash commands) for common workflows:

- **/commit** - Create git commits with proper formatting and co-author tags
- **/review-pr** - Review pull requests and analyze changes
- **/pdf** - Process and analyze PDF files
- **/help** - Get help with Claude Code features and commands
- **TodoWrite** - Track multi-step tasks and manage progress
- **Task** with agents:
  - `Explore` - Fast codebase exploration and analysis
  - `Plan` - Design implementation strategies
  - `Bash` - Execute terminal commands
  - `general-purpose` - Research and multi-step tasks

### When to Use Each Agent Type

| Agent | Best For |
|-------|----------|
| **Explore** | Finding files by pattern, searching code, understanding codebase structure |
| **Plan** | Designing implementation approaches, considering trade-offs, multi-file changes |
| **Bash** | Git operations, command execution, terminal tasks |
| **general-purpose** | Complex questions, code search, multi-step research |

**Important:** Use specialized agents (Explore, Plan) instead of direct tool calls for open-ended code exploration or architectural decisions.
