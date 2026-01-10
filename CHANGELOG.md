# Changelog

All notable changes to SwiftBolt_ML will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Market Intelligence Layer with automated calendar and corporate actions tracking
- Real-time market status API endpoint
- Automatic stock split detection and OHLCV bar adjustment
- Comprehensive project organization with `pyproject.toml`
- Contributing guidelines and code standards documentation
- Enhanced `.gitignore` for Python, Swift, and Node.js

### Changed
- Migrated to Alpaca-only data provider (95% complete)
- Consolidated Supabase edge functions
- Improved error handling in corporate actions sync

### Fixed
- Corporate actions sync API type mapping for Alpaca
- Date range limits for Alpaca corporate actions API (90-day limit)
- Table name references in market intelligence queries

## [1.0.0] - 2026-01-10

### Added
- Initial release of SwiftBolt_ML
- iOS/macOS SwiftUI application for trading interface
- Python ML backend with ARIMA-GARCH and XGBoost models
- Supabase backend with edge functions for data processing
- Alpaca API integration for market data
- Real-time chart data with multiple timeframes
- Options chain analysis and Greeks calculations
- Genetic algorithm for strategy optimization
- Backtesting framework for strategy validation
- Multi-timeframe data collection and analysis

### Infrastructure
- Supabase edge functions for serverless compute
- PostgreSQL database with optimized schema
- Automated cron jobs for data synchronization
- Rate limiting and caching for API calls

### Machine Learning
- ARIMA-GARCH models for volatility forecasting
- XGBoost for price prediction
- Feature engineering pipeline
- Model calibration and regime conditioning
- Ranking evaluation system

### iOS Application
- Real-time chart visualization with TradingView integration
- Symbol search and watchlist management
- Market data display with technical indicators
- Portfolio tracking and analysis
- Dark mode support

---

## Version History

### [1.0.0] - 2026-01-10
Initial production release with core trading platform functionality.

---

## Upgrade Notes

### Migrating to 1.0.0
No migration needed for initial release.

---

## Deprecation Warnings

### Polygon Data Provider
- **Deprecated in**: 1.0.0
- **Removal planned**: 1.1.0
- **Migration path**: All data now sourced from Alpaca API
- **Action required**: Remove Polygon API keys from environment

### Yahoo Finance Provider
- **Deprecated in**: 1.0.0
- **Removal planned**: 1.1.0
- **Migration path**: Use Alpaca for all OHLC data
- **Action required**: Update iOS client to remove yfinance references

---

## Security Updates

### 1.0.0
- Implemented secure API key management via environment variables
- Added rate limiting to prevent API abuse
- Configured Supabase RLS policies for data access control

---

## Performance Improvements

### 1.0.0
- Optimized database queries with proper indexing
- Implemented caching layer for frequently accessed data
- Added connection pooling for database connections
- Reduced API response times to <500ms for chart data

---

## Known Issues

### 1.0.0
- Market calendar coverage at 20 days (target: 30 days) - will auto-resolve
- iOS market intelligence components not yet integrated
- Some TypeScript lint warnings in edge functions (expected in Deno environment)

---

## Contributors

Thank you to all contributors who have helped build SwiftBolt_ML!

- Eric Peterson - Initial development and architecture

---

## Links

- [GitHub Repository](https://github.com/yourusername/SwiftBolt_ML)
- [Documentation](./docs/)
- [Issue Tracker](https://github.com/yourusername/SwiftBolt_ML/issues)
- [Contributing Guidelines](./CONTRIBUTING.md)
