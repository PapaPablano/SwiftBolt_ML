# SwiftBolt ML - Current Status & Next Phase

**Last Updated**: 2025-12-09
**Current Phase**: Phase 2 Complete ✅ → Moving to Phase 3

---

## 📊 Latest Test Results

### ✅ Working Features

1. **Chart Data Loading**
   - ✅ AAPL loaded 69 bars successfully
   - ✅ Date parsing handles fractional seconds: `2025-09-02T04:00:00.000Z`
   - ✅ Backend ProviderRouter with rate limiting operational
   - ✅ DB caching + memory caching working

2. **Symbol Search**
   - ✅ NVDA search: Found correctly
   - ✅ CRWD search: Found correctly
   - ✅ Backend `/symbols-search` returning proper results

3. **Backend Infrastructure**
   - ✅ Provider abstraction layer complete
   - ✅ Rate limiting (Finnhub: 30/s 60/m, Massive: 1/s 5/m)
   - ✅ Automatic failover with health tracking
   - ✅ Two-tier caching (memory + Postgres)

### 🔧 Just Fixed

**News Date Format Issue**
- **Problem**: News dates use `2025-12-09T13:35:38+00:00` (no fractional seconds)
- **Solution**: Updated `NewsItem.swift` to try both formatters:
  1. With fractional seconds: `.000Z`
  2. Without fractional seconds: `+00:00`
- **Status**: Ready for testing after rebuild

---

## ✅ Completed Phases

### Phase 0: Project Setup ✅
- [x] Mono-repo structure
- [x] Supabase configuration
- [x] Environment variables documented

### Phase 1: Backend Core ✅
- [x] Database schema (symbols, ohlc_bars, quotes, news_items)
- [x] Symbol management and seeding
- [x] `/symbols-search` endpoint
- [x] `/chart` endpoint with ProviderRouter
- [x] `/news` endpoint with ProviderRouter
- [x] Provider migration to live ingestion
  - [x] DataProviderAbstraction interface
  - [x] TokenBucketRateLimiter
  - [x] MemoryCache with TTL
  - [x] FinnhubClient and MassiveClient
  - [x] ProviderRouter with fallback

### Phase 2: macOS Client Skeleton ✅
- [x] Xcode project created
- [x] Folder structure (Models, Services, ViewModels, Views)
- [x] Models implemented with proper decoding
- [x] APIClient with async/await
- [x] ViewModels (AppViewModel, ChartViewModel, NewsViewModel, SymbolSearchViewModel)
- [x] Views (ContentView, ChartView, NewsListView, SymbolSearchView)
- [x] End-to-end data flow verified

---

## 🎯 Phase 3: Charting & Basic Technicals (NEXT)

**Goal**: Replace basic chart with proper candlestick chart and add technical indicators.

### 3.1. Chart Rendering

**Current State**:
- Basic `PriceChartView` exists but needs improvement
- Data loads successfully (69 bars for AAPL)
- Currently displays a simple line/area chart

**Requirements**:
- [ ] **Choose charting library or native SwiftUI approach**
  - Option A: Native SwiftUI Charts (iOS 16+/macOS 13+)
  - Option B: Third-party like Charts framework
  - Option C: Custom Canvas-based rendering

- [ ] **Implement proper candlestick chart**
  - [ ] Red/green candles based on open/close
  - [ ] Wicks showing high/low
  - [ ] Proper scaling and padding
  - [ ] Time axis with readable labels
  - [ ] Price axis with currency formatting

- [ ] **Interactive features**
  - [ ] Crosshair on hover
  - [ ] Tooltip showing OHLCV values
  - [ ] Zoom in/out capability
  - [ ] Pan left/right through historical data

### 3.2. Technical Indicators

**Current State**: No indicators implemented yet

**Phase 3 Requirements** (Client-Side Indicators):
- [ ] **Moving Averages**
  - [ ] SMA (Simple Moving Average) - 20, 50, 200 period
  - [ ] EMA (Exponential Moving Average) - 9, 21 period
  - [ ] Overlay on price chart with different colors
  - [ ] Toggle visibility in UI

- [ ] **Momentum Indicators** (separate panel)
  - [ ] RSI (Relative Strength Index) - 14 period
  - [ ] Display in panel below main chart
  - [ ] Overbought/oversold zones (70/30)

- [ ] **Volume**
  - [ ] Volume bars below price chart
  - [ ] Color-coded by price movement

**Implementation Approach**:
1. Create `TechnicalIndicators` utility class
2. Compute indicators in `ChartViewModel` from loaded bars
3. Add toggle controls in `TopControlBarView`
4. Update `ChartView` to render indicators alongside price

### 3.3. Watchlist (Local Storage)

**Current State**: No watchlist yet

**Requirements**:
- [ ] **WatchlistViewModel**
  - [ ] Store list of watched symbols
  - [ ] Add/remove functionality
  - [ ] Persist to UserDefaults or local JSON

- [ ] **WatchlistView in Sidebar**
  - [ ] List of watched symbols with current prices (if available)
  - [ ] Quick select to load symbol
  - [ ] Add/remove buttons

---

## 🔄 Recommended Next Steps

### Immediate (Fix News Loading):
1. **Rebuild and test** - Verify news dates now parse correctly
2. **Remove bootstrap debug code** - Delete `ContentView.swift` lines 22-29 (`.onAppear` block)
3. **Test full flow** - Search → Select → Chart + News load

### Phase 3 Priorities:

#### Week 1: Chart Improvements
1. **Day 1-2**: Research and select charting approach
   - Evaluate SwiftUI Charts vs custom Canvas
   - Create proof-of-concept candlestick chart

2. **Day 3-4**: Implement candlestick rendering
   - Full OHLC candlesticks with proper styling
   - Time and price axes
   - Basic interactivity (crosshair)

3. **Day 5**: Polish and testing
   - Smooth animations
   - Handle edge cases (single bar, missing data)
   - Responsive layout

#### Week 2: Technical Indicators
1. **Day 1-2**: Implement indicator calculations
   - Create `TechnicalIndicators.swift` utility
   - SMA, EMA, RSI computations
   - Unit tests for accuracy

2. **Day 3-4**: Render indicators on chart
   - Moving average overlays
   - RSI panel below main chart
   - Volume bars

3. **Day 5**: UI controls and polish
   - Toggle switches for each indicator
   - Color pickers (optional)
   - Save user preferences

#### Week 3: Watchlist & Polish
1. **Day 1-2**: Implement watchlist
   - ViewModel with persistence
   - UI in sidebar
   - Quick symbol switching

2. **Day 3-5**: Polish and testing
   - Edge case handling
   - Performance optimization
   - User testing and feedback

---

## 📚 Technical Decisions Needed

### Charting Library Selection

**Option A: Native SwiftUI Charts** (Recommended)
- ✅ Native, no dependencies
- ✅ Works well with SwiftUI data flow
- ✅ Automatic dark mode support
- ❌ Limited customization
- ❌ May require macOS 13+ (check compatibility)

**Option B: Custom Canvas Rendering**
- ✅ Full control over rendering
- ✅ Can achieve any design
- ✅ Better performance for large datasets
- ❌ More code to maintain
- ❌ Requires manual dark mode handling

**Option C: Third-Party (e.g., Charts framework)**
- ✅ Rich feature set
- ✅ Battle-tested
- ❌ External dependency
- ❌ May not integrate perfectly with SwiftUI

**Recommendation**: Start with **SwiftUI Charts** if macOS 13+ is acceptable, otherwise go with **Custom Canvas** for full control.

---

## 🐛 Known Issues

1. ~~News date parsing fails~~ → FIXED (awaiting test)
2. No chart interactivity yet (crosshair, zoom)
3. No technical indicators
4. No watchlist functionality
5. Chart rendering is basic (needs candlesticks)

---

## 📈 Progress Summary

**Phases Complete**: 2/7 (29%)
- ✅ Phase 0: Setup
- ✅ Phase 1: Backend Core
- ✅ Phase 2: Client Skeleton
- 🎯 Phase 3: Charting (NEXT)
- ⏳ Phase 4: ML Pipeline
- ⏳ Phase 5: ML Integration
- ⏳ Phase 6: Advanced Features
- ⏳ Phase 7: Production Polish

**Current Architecture**:
```
┌─────────────────────────────────────────────────┐
│          macOS SwiftUI App (Phase 2 ✅)         │
│  - Symbol Search ✅                              │
│  - Chart Loading ✅                              │
│  - News Loading ✅ (fixing dates)                │
│  - Basic UI Layout ✅                            │
└─────────────────┬───────────────────────────────┘
                  │ HTTPS
                  ▼
┌─────────────────────────────────────────────────┐
│       Supabase Edge Functions (Phase 1 ✅)      │
│  /symbols-search  /chart  /news                 │
│         ▲                                        │
│         │                                        │
│    ProviderRouter (with health tracking)        │
│         │                                        │
│    ┌────┴────┐                                   │
│    │         │                                   │
│ Finnhub   Massive                                │
│ (30/s)    (5/m)                                  │
│    │         │                                   │
│    └────┬────┘                                   │
│         ▼                                        │
│  Memory Cache (LRU, TTL)                         │
│         │                                        │
│         ▼                                        │
│  Postgres DB (symbols, ohlc_bars, news_items)   │
└─────────────────────────────────────────────────┘
```

**What Works**:
- ✅ Search for any seeded symbol (AAPL, NVDA, CRWD, etc.)
- ✅ Load chart data with rate limiting and caching
- ✅ Load news with rate limiting and caching
- ✅ Automatic failover if primary provider unavailable
- ✅ Pre-emptive rate limiting (no 429 errors)

**What's Next (Phase 3)**:
- 🎯 Proper candlestick chart
- 🎯 Technical indicators (SMA, EMA, RSI)
- 🎯 Interactive features (crosshair, zoom)
- 🎯 Watchlist functionality
