# SwiftBoltML System Architecture - Current State

## Overview
Multi-platform financial charting application with real-time OHLC data across 5 timeframes (m15, h1, h4, d1, w1).

## Current Architecture

### 1. Data Flow
```
Alpaca API → GitHub Actions/Cron → Supabase Edge Functions → PostgreSQL → Swift App → Chart Display
```

### 2. Components

#### A. Data Ingestion Layer
**Location:** Multiple locations (this is a problem)
- `ml/src/scripts/alpaca_backfill_ohlc_v2.py` - Python backfill script
- `.github/workflows/alpaca-intraday-cron.yml` - GitHub Actions cron
- `.github/workflows/backfill-ohlc.yml` - Backfill workflow
- `.github/workflows/daily-data-refresh.yml` - Daily refresh
- `supabase/functions/_shared/backfill-adapter.ts` - Edge function adapter

**Current State:** 
- Multiple backfill mechanisms (Python scripts, Edge Functions, GitHub Actions)
- Unclear which is active/primary
- No single source of truth for data ingestion

#### B. Database Layer
**Location:** `supabase/migrations/`
- PostgreSQL with `ohlc_bars_v2` table
- Function: `get_chart_data_v2_dynamic()` - **FIXED** ✅
- Stores data from multiple providers (transitioning to Alpaca-only)

**Current State:**
- Query logic is correct (returns most recent N bars)
- **Problem:** Database lacks recent data (AAPL daily stops at July 2024)

#### C. API Layer
**Location:** `supabase/functions/chart-data-v2/`
- Edge Function that calls PostgreSQL RPC
- Returns data in layers: historical, intraday, forecast
- **Status:** Working correctly ✅

#### D. Client Layer (Swift)
**Location:** `client-macos/SwiftBoltML/`
- `ViewModels/ChartViewModel.swift` - Fetches and manages chart data
- `Services/APIClient.swift` - HTTP client
- Cache: `ChartCache` - File-based caching
- **Status:** Working correctly ✅

#### E. Chart Rendering
**Location:** `client-macos/SwiftBoltML/Resources/WebChart/`
- `chart.js` - Lightweight Charts integration
- `WebChartView.swift` - WKWebView wrapper
- **Status:** Working correctly ✅

## Current Issues

### 1. **CRITICAL: Data Ingestion Broken**
- AAPL Daily (d1): Last bar is **July 17, 2024** (543 days old)
- AAPL Hourly (h1): Last bar is **October 22, 2025** (80 days old)
- AAPL 15-min (m15): Last bar is **December 24, 2025** (18 days old)

**Root Cause:** Unknown - need to investigate:
- Are GitHub Actions running?
- Are they completing successfully?
- Are Alpaca API keys valid?
- Are there rate limits being hit?

### 2. **Architectural Complexity**
- Multiple data ingestion paths (Python, TypeScript, GitHub Actions)
- Unclear ownership of data freshness
- No monitoring/alerting for stale data
- Complex provider migration (Polygon → Alpaca)

### 3. **Cache Invalidation**
- Client-side cache doesn't know when data is stale
- No server-side cache headers
- Manual cache clearing required

## Questions for Perplexity

### Question 1: Real-Time Financial Chart Data Architecture
"I'm building a macOS financial charting app that displays OHLC candlestick data across 5 timeframes (15m, 1h, 4h, daily, weekly) for ~10 stock symbols. The app needs to:
- Display up to 1000 bars per timeframe
- Support real-time updates during market hours
- Work offline with cached data
- Handle data from a single provider (Alpaca Markets API)

If you were architecting this from scratch as a senior engineer, what would be the recommended architecture for:
1. Data ingestion pipeline (how to fetch and store data)
2. Database schema and indexing strategy
3. API design between backend and iOS app
4. Caching strategy (client and server)
5. Real-time update mechanism

Please provide specific technology recommendations and explain the trade-offs."

### Question 2: iOS Chart Data Caching Strategy
"For an iOS/macOS financial charting app that displays 1000-bar OHLC candlestick charts across 5 timeframes:

Current implementation:
- File-based cache (JSON files per symbol/timeframe)
- Cache invalidation based on age (hours old)
- No server-side cache headers
- Manual cache clearing

Problems:
- App shows stale data (months old) even after cache clearing
- No way to know if server has newer data without fetching
- Cache invalidation logic is complex

What's the industry best practice for:
1. Client-side caching of time-series financial data?
2. Cache invalidation strategies (ETags, timestamps, versioning)?
3. Handling the 'newest bar' problem (ensuring latest data is always shown)?
4. Offline-first vs online-first approaches?

Please provide code examples or references to production implementations."

### Question 3: Multi-Timeframe Data Ingestion Pipeline
"I need to design a data ingestion pipeline that:
- Fetches OHLC bars from Alpaca Markets API
- Supports 5 timeframes: 15m, 1h, 4h, daily, weekly
- Handles ~10 symbols
- Runs automatically (cron/scheduled)
- Ensures data freshness (newest bars always available)
- Handles market hours vs after-hours
- Manages API rate limits

Current problems:
- Multiple ingestion mechanisms (Python scripts, GitHub Actions, Edge Functions)
- Data stops updating (goes stale for months)
- No monitoring or alerting
- Unclear which mechanism is responsible

What's the recommended architecture for:
1. Single vs multiple ingestion jobs?
2. Scheduling strategy (how often to run)?
3. Incremental updates vs full refreshes?
4. Error handling and retry logic?
5. Monitoring and alerting for stale data?

Please provide a production-ready design with specific tools/services."
