---
description: JS vs Swift support/resistance validation checklist
---

# Support/Resistance JS ↔ Swift Validation

## 1. Capture Swift Reference Outputs

### Symbols & Timeframes
- AAPL – m15, h1, d1
- NVDA – m15, h1, d1
- SPY – m15, h1

### Steps
1. Launch the macOS app with `useWebChart = false` in `IndicatorConfig` so overlays are sourced exclusively from Swift.
2. Enable the following toggles in the chart HUD:
   - Polynomial S/R
   - Logistic S/R
   - Pivot Levels
3. For each symbol/timeframe combination:
   1. Load the chart and wait for indicators to finish recalculating.
   2. Open **Console.app** or Xcode’s console and record the latest `PolynomialSR` and `LogisticSR` debug dumps. (Set the indicator objects’ `isDebugLoggingEnabled` flag, or temporarily insert `print` statements near `RegressionLine`/`LogisticSRLevel` assignments.)
   3. Export the OHLC sequence by choosing **File ▸ Export ▸ Chart Snapshot** (JSON) or use the `ChartBridge` debug option `dumpRawBars()`.
   4. Save logs to `docs/validation/data/swift/<symbol>_<timeframe>_(poly|logistic).json`.

> Tip: When inserting temporary logging, prefer lightweight structs (price, index, timestamp) so that diffing against JS outputs remains straightforward.

## 2. Run JS Chart Comparison

1. Switch back to `useWebChart = true` and reload the same symbol/timeframe pairs.
2. In the Web Inspector devtools console (Safari ▸ Develop ▸ Show Web Inspector on the WKWebView), execute:
   ```js
   window.chartApi.exportSRState();
   ```
   (Add this helper in `chart.js` to emit current polynomial/logistic payloads.)
3. Download the emitted JSON and store it under `docs/validation/data/js/...` using the same naming convention as the Swift reference files.

## 3. Quantitative Cross-Check (Optional Script)

Use a quick Python notebook or script with `pandas`:
```python
import json
from pathlib import Path

def load(path):
    with open(path) as f:
        return json.load(f)

swift = load("docs/validation/data/swift/AAPL_m15_polynomial.json")
js = load("docs/validation/data/js/AAPL_m15_polynomial.json")

# Example tolerance check (5 bps)
for s_point, j_point in zip(swift["resistance"], js["resistance"]):
    if abs(s_point["value"] - j_point["value"]) > 0.0005 * s_point["value"]:
        print("Mismatch", s_point, j_point)
```
Record any mismatches in the table below.

## 4. Results Table

| Symbol | TF  | Indicator | Max Δ (bps) | Notes |
|--------|-----|-----------|-------------|-------|
| AAPL   | m15 | Polynomial |             |       |
| AAPL   | m15 | Logistic   |             |       |
|        |     |           |             |       |

## 5. Swift Overlay Disable Confirmation

1. While `useWebChart = true`, toggle each indicator on/off.
2. Observe the chart: only JS-rendered layers should appear.
3. Switch `useWebChart = false`; confirm the legacy Swift overlays reappear.
4. Document observations:

```
- Polynomial (JS mode): [PASS/FAIL] — description
- Logistic (JS mode): [PASS/FAIL] — description
- Pivot levels (JS mode): [PASS/FAIL] — description
```

## 6. Follow-Up

- If discrepancies exceed tolerance, capture screenshots and attach both JSON payloads.
- File an issue tagged `chart-validation` summarizing the symbol, timeframe, and indicator with mismatched behaviour.
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ========================================
[DEBUG] ContentView.onAppear - Bootstrapping with AAPL
[DEBUG] ========================================
[DEBUG] ========================================
[DEBUG] bootstrapForDebug() - Loading AAPL for testing
[DEBUG] ========================================
[DEBUG] ========================================
[DEBUG] AppViewModel.selectSymbol() CALLED
[DEBUG] - Ticker: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Description: Apple Inc.
[DEBUG] ========================================
[DEBUG] 🔴 selectedSymbol DIDSET TRIGGERED
[DEBUG] - Old value: nil
[DEBUG] - New value: AAPL
[DEBUG] ========================================
[DEBUG] AppViewModel.handleSymbolChange() triggered
[DEBUG] - New symbol: AAPL
[DEBUG] - Asset type: stock
[DEBUG] ========================================
[DEBUG] ========================================
[DEBUG] ContentView detected selectedSymbol change
[DEBUG] - Old: nil
[DEBUG] - New: AAPL
[DEBUG] ========================================
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is nil
- barCount: -1
[DEBUG] 🔵 ChartHeader.body rendering with symbol: nil
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ========================================
[DEBUG] AppViewModel.refreshData() START
[DEBUG] - selectedSymbol (AppViewModel): AAPL
[DEBUG] - chartViewModel.selectedSymbol (BEFORE): nil
[DEBUG] - Setting chartViewModel.selectedSymbol to: AAPL
[DEBUG] 🟢 ChartViewModel.selectedSymbol DIDSET TRIGGERED
[DEBUG] - Old value: nil
[DEBUG] - New value: AAPL
[DEBUG] - chartViewModel.selectedSymbol (AFTER): AAPL
[DEBUG] - Loading news and options (chart loads via didSet)...
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 502, newest bar age: 16h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: d1 (sending: d1)
[DEBUG] - Is Intraday: false
[DEBUG] - Starting chart data fetch...
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=d1, cacheBuster=1768600281
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600281&symbol=AAPL&timeframe=d1
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] ========================================
[DEBUG] NewsViewModel.loadNews() CALLED
[DEBUG] - Symbol: AAPL
[DEBUG] ========================================
[DEBUG] OptionsChainViewModel.loadOptionsChain() CALLED for AAPL
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/news?symbol=AAPL
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/options-chain?underlying=AAPL
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","items":[{"id":"d8a24f6a-eacc-4eb5-a78d-e4aaed94d1c5","title":"Top 10 Congress Stock Traders 2025: Nancy Pelosi, Marjorie Taylor Greene Both Bet Big On NVDA — But Who Came Out On Top?","source":"benzinga","url":"https://www.benzinga.com/news/politics/26/01/49980468/top-10-congress-stock-traders-2025-nancy-pelosi-marjorie-taylor-greene-both-bet-big-on-nvda-but-who-came-out-on-top","publishedAt":"2026-01-16T21:29:34+00:00","summary":"The trading activity of members of Congress con
[DEBUG] NewsViewModel.loadNews() - SUCCESS!
[DEBUG] - Received 20 news items
[DEBUG] NewsViewModel.loadNews() COMPLETED
[DEBUG] ========================================
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"underlying":"AAPL","timestamp":1768600281,"expirations":[1768521600],"calls":[{"symbol":"AAPL260116C00005000","underlying":"AAPL","strike":5,"expiration":1768521600,"type":"call","bid":251.18,"ask":255.24,"last":255.5,"mark":253.21,"volume":0,"openInterest":61,"lastTradeTime":1768506170},{"symbol":"AAPL260116C00010000","underlying":"AAPL","strike":10,"expiration":1768521600,"type":"call","bid":244.35,"ask":247.64,"last":248.53,"mark":245.995,"volume":0,"openInterest":29,"lastTradeTime":1768505
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] OptionsChainViewModel.loadOptionsChain() - SUCCESS!
[DEBUG] - Received 96 calls and 4 puts
[DEBUG] - Expirations: 1
[DEBUG] OptionsChainViewModel.loadOptionsChain() COMPLETED
[DEBUG] AppViewModel.refreshData() COMPLETED
[DEBUG] ========================================
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 📊 Response Headers for AAPL/d1
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"d1","bars":[{"ts":"2024-01-18T05:00:00+00:00","open":186.06,"high":189.135,"low":185.89,"close":188.7,"volume":1405733,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-19T05:00:00+00:00","open":189.35,"high":191.945,"low":188.845,"close":191.55,"volume":1126703,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-22T05:00:00+00:00","open":192.39,"high":195.325,"low":192.32,"close":193.89,"volume":
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 502
[DEBUG] - ML: ✓
[ChartCache] Saved 502 bars to AAPL_d1.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 502 bars
[PolynomialSR] First bar close: 188.70
[PolynomialSR] Last bar close: 255.47
[PolynomialSR] Found 31 resistance pivots, 28 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [191.01, 185.01, 178.61, 178.35, 186.97]
[PolynomialSR] Support pivot prices (first 5): [179.25, 180.01, 168.50, 168.27, 167.12]
[PolynomialSR] Resistance: Linear, pivots=11, range=[10-135], pred@0=298.46
[PolynomialSR]   Generated 156 points
[PolynomialSR]   First point: barIdx=366, price=218.01
[PolynomialSR]   Last point: barIdx=521, price=310.38
[PolynomialSR] Support: Linear, pivots=8, range=[6-146], pred@0=274.03
[PolynomialSR]   Generated 167 points
[PolynomialSR]   First point: barIdx=355, price=195.86
[PolynomialSR]   Last point: barIdx=521, price=284.74
[PolynomialSR] ========================================
[PolynomialSR] Result: R=298.46, S=274.03
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 🔄 Auto-refreshing chart for 1D (last refresh: 63904369882s ago)
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 502, newest bar age: 16h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: d1 (sending: d1)
[DEBUG] - Is Intraday: false
[DEBUG] - Starting chart data fetch...
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=d1, cacheBuster=1768600282
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600282&symbol=AAPL&timeframe=d1
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] 📊 Response Headers for AAPL/d1
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"d1","bars":[{"ts":"2024-01-18T05:00:00+00:00","open":186.06,"high":189.135,"low":185.89,"close":188.7,"volume":1405733,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-19T05:00:00+00:00","open":189.35,"high":191.945,"low":188.845,"close":191.55,"volume":1126703,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-22T05:00:00+00:00","open":192.39,"high":195.325,"low":192.32,"close":193.89,"volume":
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 502
[DEBUG] - ML: ✓
[ChartCache] Saved 502 bars to AAPL_d1.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 502 bars
[PolynomialSR] First bar close: 188.70
[PolynomialSR] Last bar close: 255.47
[PolynomialSR] Found 31 resistance pivots, 28 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [191.01, 185.01, 178.61, 178.35, 186.97]
[PolynomialSR] Support pivot prices (first 5): [179.25, 180.01, 168.50, 168.27, 167.12]
[PolynomialSR] Resistance: Linear, pivots=11, range=[10-135], pred@0=298.46
[PolynomialSR]   Generated 156 points
[PolynomialSR]   First point: barIdx=366, price=218.01
[PolynomialSR]   Last point: barIdx=521, price=310.38
[PolynomialSR] Support: Linear, pivots=8, range=[6-146], pred@0=274.03
[PolynomialSR]   Generated 167 points
[PolynomialSR]   First point: barIdx=355, price=195.86
[PolynomialSR]   Last point: barIdx=521, price=284.74
[PolynomialSR] ========================================
[PolynomialSR] Result: R=298.46, S=274.03
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
Unable to obtain a task name port right for pid 404: (os/kern) failure (0x5)
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[DEBUG] 🕒 timeframe changed to m15 (apiToken=m15)
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 950, newest bar age: 1h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: m15 (sending: m15)
[DEBUG] - Is Intraday: true
[DEBUG] - Starting chart data fetch...
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=m15, cacheBuster=1768600298
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600298&symbol=AAPL&timeframe=m15
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 950
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] 📊 Response Headers for AAPL/m15
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"m15","bars":[{"ts":"2025-12-22T10:15:00Z","open":273.72,"high":273.75,"low":273.67,"close":273.67,"volume":1992,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2025-12-22T10:30:00Z","open":273.69,"high":273.8,"low":273.69,"close":273.8,"volume":1105,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2025-12-22T10:45:00Z","open":273.67,"high":273.67,"low":273.67,"close":273.67,"volume":552,"upper_band":null,"lo
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 950
[DEBUG] - ML: ✗
[ChartCache] Saved 950 bars to AAPL_m15.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 950 bars
[PolynomialSR] First bar close: 273.67
[PolynomialSR] Last bar close: 255.47
[PolynomialSR] Found 63 resistance pivots, 66 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [273.87, 271.13, 271.14, 271.90, 272.31]
[PolynomialSR] Support pivot prices (first 5): [273.01, 271.52, 270.52, 270.51, 270.62]
[PolynomialSR] Resistance: Linear, pivots=9, range=[7-150], pred@0=258.63
[PolynomialSR]   Generated 171 points
[PolynomialSR]   First point: barIdx=799, price=262.14
[PolynomialSR]   Last point: barIdx=969, price=258.17
[PolynomialSR] Support: Linear, pivots=8, range=[12-135], pred@0=256.13
[PolynomialSR]   Generated 156 points
[PolynomialSR]   First point: barIdx=814, price=259.81
[PolynomialSR]   Last point: barIdx=969, price=255.59
[PolynomialSR] ========================================
[PolynomialSR] Result: R=258.63, S=256.13
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[Canvas] Support: 156 pts, price[259.8->255.6], screenX[616->733]
[Canvas] Resistance: 171 pts, price[262.1->258.2], screenX[605->733]
[DEBUG] 🕒 timeframe changed to h1 (apiToken=h1)
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 950, newest bar age: 3h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: h1 (sending: h1)
[DEBUG] - Is Intraday: true
[DEBUG] - Starting chart data fetch...
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=h1, cacheBuster=1768600303
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600303&symbol=AAPL&timeframe=h1
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 950
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] 📊 Response Headers for AAPL/h1
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"h1","bars":[{"ts":"2025-10-16T14:00:00Z","open":247.56,"high":248.89,"low":246.92,"close":248.58,"volume":142693,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2025-10-16T15:00:00Z","open":248.61,"high":248.99,"low":247.54,"close":247.955,"volume":114251,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2025-10-16T16:00:00Z","open":247.91,"high":248.13,"low":246.07,"close":247.59,"volume":165224,"upper_band"
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 950
[DEBUG] - ML: ✗
[ChartCache] Saved 950 bars to AAPL_h1.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 950 bars
[PolynomialSR] First bar close: 248.58
[PolynomialSR] Last bar close: 256.51
[PolynomialSR] Found 68 resistance pivots, 65 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [264.35, 265.26, 263.40, 260.59, 264.12]
[PolynomialSR] Support pivot prices (first 5): [244.01, 260.69, 255.44, 257.55, 259.20]
[PolynomialSR] Resistance: Linear, pivots=11, range=[11-147], pred@0=258.65
[PolynomialSR]   Generated 168 points
[PolynomialSR]   First point: barIdx=802, price=276.16
[PolynomialSR]   Last point: barIdx=969, price=256.27
[PolynomialSR] Support: Linear, pivots=9, range=[16-144], pred@0=252.47
[PolynomialSR]   Generated 165 points
[PolynomialSR]   First point: barIdx=805, price=273.20
[PolynomialSR]   Last point: barIdx=969, price=249.59
[PolynomialSR] ========================================
[PolynomialSR] Result: R=258.65, S=252.47
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[Canvas] Support: 165 pts, price[273.2->249.6], screenX[606->734]
[Canvas] Resistance: 168 pts, price[276.2->256.3], screenX[604->734]
[DEBUG] 🕒 timeframe changed to d1 (apiToken=d1)
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 502, newest bar age: 16h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: d1 (sending: d1)
[DEBUG] - Is Intraday: false
[DEBUG] - Starting chart data fetch...
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=d1, cacheBuster=1768600317
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600317&symbol=AAPL&timeframe=d1
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] 📊 Response Headers for AAPL/d1
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"d1","bars":[{"ts":"2024-01-18T05:00:00+00:00","open":186.06,"high":189.135,"low":185.89,"close":188.7,"volume":1405733,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-19T05:00:00+00:00","open":189.35,"high":191.945,"low":188.845,"close":191.55,"volume":1126703,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-22T05:00:00+00:00","open":192.39,"high":195.325,"low":192.32,"close":193.89,"volume":
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 502
[DEBUG] - ML: ✓
[ChartCache] Saved 502 bars to AAPL_d1.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 502 bars
[PolynomialSR] First bar close: 188.70
[PolynomialSR] Last bar close: 255.47
[PolynomialSR] Found 31 resistance pivots, 28 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [191.01, 185.01, 178.61, 178.35, 186.97]
[PolynomialSR] Support pivot prices (first 5): [179.25, 180.01, 168.50, 168.27, 167.12]
[PolynomialSR] Resistance: Linear, pivots=11, range=[10-135], pred@0=298.46
[PolynomialSR]   Generated 156 points
[PolynomialSR]   First point: barIdx=366, price=218.01
[PolynomialSR]   Last point: barIdx=521, price=310.38
[PolynomialSR] Support: Linear, pivots=8, range=[6-146], pred@0=274.03
[PolynomialSR]   Generated 167 points
[PolynomialSR]   First point: barIdx=355, price=195.86
[PolynomialSR]   Last point: barIdx=521, price=284.74
[PolynomialSR] ========================================
[PolynomialSR] Result: R=298.46, S=274.03
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]
[Canvas] Support: 167 pts, price[195.9->284.7], screenX[-986->939]
[Canvas] Resistance: 156 pts, price[218.0->310.4], screenX[-858->939]



##Second test


[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ========================================
[DEBUG] ContentView.onAppear - Bootstrapping with AAPL
[DEBUG] ========================================
[DEBUG] ========================================
[DEBUG] bootstrapForDebug() - Loading AAPL for testing
[DEBUG] ========================================
[DEBUG] ========================================
[DEBUG] AppViewModel.selectSymbol() CALLED
[DEBUG] - Ticker: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Description: Apple Inc.
[DEBUG] ========================================
[DEBUG] 🔴 selectedSymbol DIDSET TRIGGERED
[DEBUG] - Old value: nil
[DEBUG] - New value: AAPL
[DEBUG] ========================================
[DEBUG] AppViewModel.handleSymbolChange() triggered
[DEBUG] - New symbol: AAPL
[DEBUG] - Asset type: stock
[DEBUG] ========================================
[DEBUG] ========================================
[DEBUG] ContentView detected selectedSymbol change
[DEBUG] - Old: nil
[DEBUG] - New: AAPL
[DEBUG] ========================================
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is nil
- barCount: -1
[DEBUG] 🔵 ChartHeader.body rendering with symbol: nil
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ========================================
[DEBUG] AppViewModel.refreshData() START
[DEBUG] - selectedSymbol (AppViewModel): AAPL
[DEBUG] - chartViewModel.selectedSymbol (BEFORE): nil
[DEBUG] - Setting chartViewModel.selectedSymbol to: AAPL
[DEBUG] 🟢 ChartViewModel.selectedSymbol DIDSET TRIGGERED
[DEBUG] - Old value: nil
[DEBUG] - New value: AAPL
[DEBUG] - chartViewModel.selectedSymbol (AFTER): AAPL
[DEBUG] - Loading news and options (chart loads via didSet)...
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 502, newest bar age: 16h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: d1 (sending: d1)
[DEBUG] - Is Intraday: false
[DEBUG] - Starting chart data fetch...
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=d1, cacheBuster=1768600484
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600484&symbol=AAPL&timeframe=d1
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ========================================
[DEBUG] NewsViewModel.loadNews() CALLED
[DEBUG] - Symbol: AAPL
[DEBUG] ========================================
[DEBUG] OptionsChainViewModel.loadOptionsChain() CALLED for AAPL
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/news?symbol=AAPL
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/options-chain?underlying=AAPL
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","items":[{"id":"d8a24f6a-eacc-4eb5-a78d-e4aaed94d1c5","title":"Top 10 Congress Stock Traders 2025: Nancy Pelosi, Marjorie Taylor Greene Both Bet Big On NVDA — But Who Came Out On Top?","source":"benzinga","url":"https://www.benzinga.com/news/politics/26/01/49980468/top-10-congress-stock-traders-2025-nancy-pelosi-marjorie-taylor-greene-both-bet-big-on-nvda-but-who-came-out-on-top","publishedAt":"2026-01-16T21:29:34+00:00","summary":"The trading activity of members of Congress con
[DEBUG] NewsViewModel.loadNews() - SUCCESS!
[DEBUG] - Received 20 news items
[DEBUG] NewsViewModel.loadNews() COMPLETED
[DEBUG] ========================================
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"underlying":"AAPL","timestamp":1768600485,"expirations":[1768521600],"calls":[{"symbol":"AAPL260116C00005000","underlying":"AAPL","strike":5,"expiration":1768521600,"type":"call","bid":251.18,"ask":255.24,"last":255.5,"mark":253.21,"volume":0,"openInterest":61,"lastTradeTime":1768506170},{"symbol":"AAPL260116C00010000","underlying":"AAPL","strike":10,"expiration":1768521600,"type":"call","bid":244.35,"ask":247.64,"last":248.53,"mark":245.995,"volume":0,"openInterest":29,"lastTradeTime":1768505
[DEBUG] OptionsChainViewModel.loadOptionsChain() - SUCCESS!
[DEBUG] - Received 96 calls and 4 puts
[DEBUG] - Expirations: 1
[DEBUG] OptionsChainViewModel.loadOptionsChain() COMPLETED
[DEBUG] AppViewModel.refreshData() COMPLETED
[DEBUG] ========================================
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] 📊 Response Headers for AAPL/d1
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"d1","bars":[{"ts":"2024-01-18T05:00:00+00:00","open":186.06,"high":189.135,"low":185.89,"close":188.7,"volume":1405733,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-19T05:00:00+00:00","open":189.35,"high":191.945,"low":188.845,"close":191.55,"volume":1126703,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-22T05:00:00+00:00","open":192.39,"high":195.325,"low":192.32,"close":193.89,"volume":
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 502
[DEBUG] - ML: ✓
[ChartCache] Saved 502 bars to AAPL_d1.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 502 bars
[PolynomialSR] First bar close: 188.70
[PolynomialSR] Last bar close: 255.47
[PolynomialSR] Found 31 resistance pivots, 28 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [191.01, 185.01, 178.61, 178.35, 186.97]
[PolynomialSR] Support pivot prices (first 5): [179.25, 180.01, 168.50, 168.27, 167.12]
[PolynomialSR] Resistance: Linear, pivots=11, range=[10-135], pred@0=298.46
[PolynomialSR]   Generated 156 points
[PolynomialSR]   First point: barIdx=366, price=218.01
[PolynomialSR]   Last point: barIdx=521, price=310.38
[PolynomialSR] Support: Linear, pivots=8, range=[6-146], pred@0=274.03
[PolynomialSR]   Generated 167 points
[PolynomialSR]   First point: barIdx=355, price=195.86
[PolynomialSR]   Last point: barIdx=521, price=284.74
[PolynomialSR] ========================================
[PolynomialSR] Result: R=298.46, S=274.03
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[WebChartView] Loading chart from bundle root: file:///Users/ericpeterson/Library/Developer/Xcode/DerivedData/SwiftBoltML-fvczbmwpxtcqewgbpaecwhupjwxf/Build/Products/Debug/SwiftBoltML.app/Contents/Resources/index.html
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] 🔄 Auto-refreshing chart for 1D (last refresh: 63904370085s ago)
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 502, newest bar age: 16h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: d1 (sending: d1)
[DEBUG] - Is Intraday: false
[DEBUG] - Starting chart data fetch...
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=d1, cacheBuster=1768600485
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600485&symbol=AAPL&timeframe=d1
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
AFIsDeviceGreymatterEligible Missing entitlements for os_eligibility lookup
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
Unable to create bundle at URL ((null)): normalized URL null
precondition failure: unable to load binary archive for shader library: /System/Library/PrivateFrameworks/IconRendering.framework/Resources/binary.metallib, The file file:///System/Library/PrivateFrameworks/IconRendering.framework/Resources/binary.metallib has an invalid format.
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] 📊 Response Headers for AAPL/d1
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"d1","bars":[{"ts":"2024-01-18T05:00:00+00:00","open":186.06,"high":189.135,"low":185.89,"close":188.7,"volume":1405733,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-19T05:00:00+00:00","open":189.35,"high":191.945,"low":188.845,"close":191.55,"volume":1126703,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-22T05:00:00+00:00","open":192.39,"high":195.325,"low":192.32,"close":193.89,"volume":
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 502
[DEBUG] - ML: ✓
[ChartCache] Saved 502 bars to AAPL_d1.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 502 bars
[PolynomialSR] First bar close: 188.70
[PolynomialSR] Last bar close: 255.47
[PolynomialSR] Found 31 resistance pivots, 28 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [191.01, 185.01, 178.61, 178.35, 186.97]
[PolynomialSR] Support pivot prices (first 5): [179.25, 180.01, 168.50, 168.27, 167.12]
[PolynomialSR] Resistance: Linear, pivots=11, range=[10-135], pred@0=298.46
[PolynomialSR]   Generated 156 points
[PolynomialSR]   First point: barIdx=366, price=218.01
[PolynomialSR]   Last point: barIdx=521, price=310.38
[PolynomialSR] Support: Linear, pivots=8, range=[6-146], pred@0=274.03
[PolynomialSR]   Generated 167 points
[PolynomialSR]   First point: barIdx=355, price=195.86
[PolynomialSR]   Last point: barIdx=521, price=284.74
[PolynomialSR] ========================================
[PolynomialSR] Result: R=298.46, S=274.03
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[WebChartView] Loading chart from bundle root: file:///Users/ericpeterson/Library/Developer/Xcode/DerivedData/SwiftBoltML-fvczbmwpxtcqewgbpaecwhupjwxf/Build/Products/Debug/SwiftBoltML.app/Contents/Resources/index.html
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
WebContent[41778] Connection to 'pboard' server had an error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41778] Failed to set up CFPasteboardRef 'Apple CFPasteboard general'. Error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41778] Failed to set up CFPasteboardRef 'Apple CFPasteboard general'. Error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41778] send_message_with_reply_sync(): XPC_ERROR_CONNECTION_INVALID for message 0xc010a8a80
WebContent[41778] TCCAccessRequest_block_invoke: Connection invalid
WebContent[41778] Conn 0x0 is not a valid connection ID.
WebContent[41778] Conn 0x0 is not a valid connection ID.
WebContent[41778] Conn 0x0 is not a valid connection ID.
WebContent[41778] Got an XPC_ERROR_INVALID on our server connection, so failing.
WebContent[41778] CRASHSTRING: XPC_ERROR_CONNECTION_INVALID from launchservicesd
WebContent[41778] CRASHSTRING: <private>
WebContent[41778] CRASHSTRING: <rdar://problem/28724618> Process unable to create connection because the sandbox denied the right to lookup com.apple.coreservices.launchservicesd and so this process cannot talk to launchservicesd.
WebContent[41778] rdar://problem/28724618 Unable to register with launchservicsed, couldn't create connection object.
WebContent[41778] invalid product id '(null)'
WebContent[41778] checkinWithServer Failed bootstrap_lookup2 for name of coreservicesd, kern_return_t=#1100/0x44c Permission denied name=com.apple.CoreServices.coreservicesd
WebContent[41778] The sandbox in this process does not allow access to RunningBoard.
WebContent[41778] Handshake aborted as the connection has been invalidated
WebContent[41778] Conn 0x0 is not a valid connection ID.
WebContent[41778] Conn 0x0 is not a valid connection ID.
WebContent[41778] Conn 0x0 is not a valid connection ID.
WebContent[41778] Conn 0x0 is not a valid connection ID.
WebContent[41778] Conn 0x0 is not a valid connection ID.
WebContent[41778] Conn 0x0 is not a valid connection ID.
WebContent[41778] Missing the com.apple.linkd.autoShortcut mach-lookup entitlement, will NOT register the process
WebContent[41778] Error registering app with intents framework: Error Domain=LNProcessInstanceRegistryClientErrorDomain Code=1
WebContent[41778] AudioComponentPluginMgr.mm:590   reg server remote proxy error Error Domain=NSCocoaErrorDomain Code=4099 "The connection to service named com.apple.audio.AudioComponentRegistrar was invalidated: Connection init failed at lookup with error 1 - Operation not permitted." UserInfo={NSDebugDescription=The connection to service named com.apple.audio.AudioComponentRegistrar was invalidated: Connection init failed at lookup with error 1 - Operation not permitted.}
WebContent[41778] networkd_settings_read_from_file Sandbox is preventing this process from reading networkd settings file at "/Library/Preferences/com.apple.networkd.plist", please add an exception.
WebContent[41778] networkd_settings_read_from_file Sandbox is preventing this process from reading networkd settings file at "/Library/Preferences/com.apple.networkd.plist", please add an exception.
WebContent[41778] Unable to hide query parameters from script (missing data)
[ChartBridge] Flushed 1 pending commands
[ChartBridge] Chart ready
[ChartBridge] Heikin-Ashi toggled: true
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] Candles: 502 bars
[ChartBridge] First: 2024-01-18 05:00:00 +0000 O:186.06 H:189.135 L:185.89 C:188.7
[ChartBridge] Last: 2026-01-16 05:00:00 +0000 O:258.08 H:258.89 L:254.93 C:255.475
[WebChartView] SuperTrend: 502 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 493 aligned points
[WebChartView] Chart updated with 502 bars
[WebChartView] Navigation finished
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] Candles: 502 bars
[ChartBridge] First: 2024-01-18 05:00:00 +0000 O:186.06 H:189.135 L:185.89 C:188.7
[ChartBridge] Last: 2026-01-16 05:00:00 +0000 O:258.08 H:258.89 L:254.93 C:255.475
[WebChartView] SuperTrend: 502 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 493 aligned points
[WebChartView] Chart updated with 502 bars
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
Unable to obtain a task name port right for pid 404: (os/kern) failure (0x5)
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] Candles: 502 bars
[ChartBridge] First: 2024-01-18 05:00:00 +0000 O:186.06 H:189.135 L:185.89 C:188.7
[ChartBridge] Last: 2026-01-16 05:00:00 +0000 O:258.08 H:258.89 L:254.93 C:255.475
[WebChartView] SuperTrend: 502 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 493 aligned points
[WebChartView] Chart updated with 502 bars
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] Candles: 502 bars
[ChartBridge] First: 2024-01-18 05:00:00 +0000 O:186.06 H:189.135 L:185.89 C:188.7
[ChartBridge] Last: 2026-01-16 05:00:00 +0000 O:258.08 H:258.89 L:254.93 C:255.475
[WebChartView] SuperTrend: 502 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 493 aligned points
[WebChartView] Chart updated with 502 bars
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] Candles: 502 bars
[ChartBridge] First: 2024-01-18 05:00:00 +0000 O:186.06 H:189.135 L:185.89 C:188.7
[ChartBridge] Last: 2026-01-16 05:00:00 +0000 O:258.08 H:258.89 L:254.93 C:255.475
[WebChartView] SuperTrend: 502 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 493 aligned points
[WebChartView] Chart updated with 502 bars
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] 🕒 timeframe changed to m15 (apiToken=m15)
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 950, newest bar age: 1h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: m15 (sending: m15)
[DEBUG] - Is Intraday: true
[DEBUG] - Starting chart data fetch...
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
Error acquiring assertion: <Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}>
0x12a1bc120 - ProcessAssertion::acquireSync Failed to acquire RBS assertion 'XPCConnectionTerminationWatchdog' for process with PID=41778, error: Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}
Error acquiring assertion: <Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}>
0x12a1bc180 - ProcessAssertion::acquireSync Failed to acquire RBS assertion 'WebProcess NearSuspended Assertion' for process with PID=41778, error: Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=m15, cacheBuster=1768600502
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600502&symbol=AAPL&timeframe=m15
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] 📊 Response Headers for AAPL/m15
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"m15","bars":[{"ts":"2025-12-22T10:15:00Z","open":273.72,"high":273.75,"low":273.67,"close":273.67,"volume":1992,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2025-12-22T10:30:00Z","open":273.69,"high":273.8,"low":273.69,"close":273.8,"volume":1105,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2025-12-22T10:45:00Z","open":273.67,"high":273.67,"low":273.67,"close":273.67,"volume":552,"upper_band":null,"lo
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 950
[DEBUG] - ML: ✗
[ChartCache] Saved 950 bars to AAPL_m15.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 950 bars
[PolynomialSR] First bar close: 273.67
[PolynomialSR] Last bar close: 255.47
[PolynomialSR] Found 63 resistance pivots, 66 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [273.87, 271.13, 271.14, 271.90, 272.31]
[PolynomialSR] Support pivot prices (first 5): [273.01, 271.52, 270.52, 270.51, 270.62]
[PolynomialSR] Resistance: Linear, pivots=9, range=[7-150], pred@0=258.63
[PolynomialSR]   Generated 171 points
[PolynomialSR]   First point: barIdx=799, price=262.14
[PolynomialSR]   Last point: barIdx=969, price=258.17
[PolynomialSR] Support: Linear, pivots=8, range=[12-135], pred@0=256.13
[PolynomialSR]   Generated 156 points
[PolynomialSR]   First point: barIdx=814, price=259.81
[PolynomialSR]   Last point: barIdx=969, price=255.59
[PolynomialSR] ========================================
[PolynomialSR] Result: R=258.63, S=256.13
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[WebChartView] Loading chart from bundle root: file:///Users/ericpeterson/Library/Developer/Xcode/DerivedData/SwiftBoltML-fvczbmwpxtcqewgbpaecwhupjwxf/Build/Products/Debug/SwiftBoltML.app/Contents/Resources/index.html
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
WebContent[41785] Connection to 'pboard' server had an error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41785] Failed to set up CFPasteboardRef 'Apple CFPasteboard general'. Error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41785] Failed to set up CFPasteboardRef 'Apple CFPasteboard general'. Error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41785] send_message_with_reply_sync(): XPC_ERROR_CONNECTION_INVALID for message 0xa4b0a4a80
WebContent[41785] TCCAccessRequest_block_invoke: Connection invalid
WebContent[41785] Conn 0x0 is not a valid connection ID.
WebContent[41785] Conn 0x0 is not a valid connection ID.
WebContent[41785] Conn 0x0 is not a valid connection ID.
WebContent[41785] Got an XPC_ERROR_INVALID on our server connection, so failing.
WebContent[41785] CRASHSTRING: XPC_ERROR_CONNECTION_INVALID from launchservicesd
WebContent[41785] CRASHSTRING: <private>
WebContent[41785] CRASHSTRING: <rdar://problem/28724618> Process unable to create connection because the sandbox denied the right to lookup com.apple.coreservices.launchservicesd and so this process cannot talk to launchservicesd.
WebContent[41785] rdar://problem/28724618 Unable to register with launchservicsed, couldn't create connection object.
WebContent[41785] invalid product id '(null)'
WebContent[41785] checkinWithServer Failed bootstrap_lookup2 for name of coreservicesd, kern_return_t=#1100/0x44c Permission denied name=com.apple.CoreServices.coreservicesd
WebContent[41785] The sandbox in this process does not allow access to RunningBoard.
WebContent[41785] Handshake aborted as the connection has been invalidated
WebContent[41785] Conn 0x0 is not a valid connection ID.
WebContent[41785] Conn 0x0 is not a valid connection ID.
WebContent[41785] Conn 0x0 is not a valid connection ID.
WebContent[41785] Conn 0x0 is not a valid connection ID.
WebContent[41785] Conn 0x0 is not a valid connection ID.
WebContent[41785] Conn 0x0 is not a valid connection ID.
WebContent[41785] Missing the com.apple.linkd.autoShortcut mach-lookup entitlement, will NOT register the process
WebContent[41785] Error registering app with intents framework: Error Domain=LNProcessInstanceRegistryClientErrorDomain Code=1
WebContent[41785] AudioComponentPluginMgr.mm:590   reg server remote proxy error Error Domain=NSCocoaErrorDomain Code=4099 "The connection to service named com.apple.audio.AudioComponentRegistrar was invalidated: Connection init failed at lookup with error 1 - Operation not permitted." UserInfo={NSDebugDescription=The connection to service named com.apple.audio.AudioComponentRegistrar was invalidated: Connection init failed at lookup with error 1 - Operation not permitted.}
WebContent[41785] networkd_settings_read_from_file Sandbox is preventing this process from reading networkd settings file at "/Library/Preferences/com.apple.networkd.plist", please add an exception.
WebContent[41785] networkd_settings_read_from_file Sandbox is preventing this process from reading networkd settings file at "/Library/Preferences/com.apple.networkd.plist", please add an exception.
[ChartBridge] Flushed 0 pending commands
[ChartBridge] Chart ready
[WebChartView] Navigation finished
[ChartBridge] Heikin-Ashi toggled: true
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] ⚠️ Detected 5 large time gaps (> 86400s). Top gaps:
[ChartBridge]   Gap 1.5 days between 2025-12-24 21:45:00 +0000 and 2025-12-26 09:00:00 +0000
[ChartBridge]   Gap 2.3 days between 2025-12-27 00:45:00 +0000 and 2025-12-29 09:00:00 +0000
[ChartBridge]   Gap 1.3 days between 2026-01-01 00:45:00 +0000 and 2026-01-02 09:00:00 +0000
[ChartBridge] Candles: 950 bars
[ChartBridge] First: 2025-12-22 10:15:00 +0000 O:273.72 H:273.75 L:273.67 C:273.67
[ChartBridge] Last: 2026-01-16 20:45:00 +0000 O:255.66 H:255.88 L:255.16 C:255.475
[WebChartView] SuperTrend: 950 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 941 aligned points
[WebChartView] Chart updated with 950 bars
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] ⚠️ Detected 5 large time gaps (> 86400s). Top gaps:
[ChartBridge]   Gap 1.5 days between 2025-12-24 21:45:00 +0000 and 2025-12-26 09:00:00 +0000
[ChartBridge]   Gap 2.3 days between 2025-12-27 00:45:00 +0000 and 2025-12-29 09:00:00 +0000
[ChartBridge]   Gap 1.3 days between 2026-01-01 00:45:00 +0000 and 2026-01-02 09:00:00 +0000
[ChartBridge] Candles: 950 bars
[ChartBridge] First: 2025-12-22 10:15:00 +0000 O:273.72 H:273.75 L:273.67 C:273.67
[ChartBridge] Last: 2026-01-16 20:45:00 +0000 O:255.66 H:255.88 L:255.16 C:255.475
[WebChartView] SuperTrend: 950 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 941 aligned points
[WebChartView] Chart updated with 950 bars
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] 🕒 timeframe changed to h1 (apiToken=h1)
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 950, newest bar age: 3h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: h1 (sending: h1)
[DEBUG] - Is Intraday: true
[DEBUG] - Starting chart data fetch...
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
Error acquiring assertion: <Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}>
0x12a1bc180 - ProcessAssertion::acquireSync Failed to acquire RBS assertion 'XPCConnectionTerminationWatchdog' for process with PID=41785, error: Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}
Error acquiring assertion: <Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}>
0x12a1bc1e0 - ProcessAssertion::acquireSync Failed to acquire RBS assertion 'WebProcess NearSuspended Assertion' for process with PID=41785, error: Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=h1, cacheBuster=1768600508
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600508&symbol=AAPL&timeframe=h1
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] 📊 Response Headers for AAPL/h1
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"h1","bars":[{"ts":"2025-10-16T14:00:00Z","open":247.56,"high":248.89,"low":246.92,"close":248.58,"volume":142693,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2025-10-16T15:00:00Z","open":248.61,"high":248.99,"low":247.54,"close":247.955,"volume":114251,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2025-10-16T16:00:00Z","open":247.91,"high":248.13,"low":246.07,"close":247.59,"volume":165224,"upper_band"
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 950
[DEBUG] - ML: ✗
[ChartCache] Saved 950 bars to AAPL_h1.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 950 bars
[PolynomialSR] First bar close: 248.58
[PolynomialSR] Last bar close: 256.51
[PolynomialSR] Found 68 resistance pivots, 65 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [264.35, 265.26, 263.40, 260.59, 264.12]
[PolynomialSR] Support pivot prices (first 5): [244.01, 260.69, 255.44, 257.55, 259.20]
[PolynomialSR] Resistance: Linear, pivots=11, range=[11-147], pred@0=258.65
[PolynomialSR]   Generated 168 points
[PolynomialSR]   First point: barIdx=802, price=276.16
[PolynomialSR]   Last point: barIdx=969, price=256.27
[PolynomialSR] Support: Linear, pivots=9, range=[16-144], pred@0=252.47
[PolynomialSR]   Generated 165 points
[PolynomialSR]   First point: barIdx=805, price=273.20
[PolynomialSR]   Last point: barIdx=969, price=249.59
[PolynomialSR] ========================================
[PolynomialSR] Result: R=258.65, S=252.47
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[WebChartView] Loading chart from bundle root: file:///Users/ericpeterson/Library/Developer/Xcode/DerivedData/SwiftBoltML-fvczbmwpxtcqewgbpaecwhupjwxf/Build/Products/Debug/SwiftBoltML.app/Contents/Resources/index.html
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
WebContent[41791] Connection to 'pboard' server had an error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41791] Failed to set up CFPasteboardRef 'Apple CFPasteboard general'. Error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41791] Failed to set up CFPasteboardRef 'Apple CFPasteboard general'. Error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41791] send_message_with_reply_sync(): XPC_ERROR_CONNECTION_INVALID for message 0x7710b8a80
WebContent[41791] TCCAccessRequest_block_invoke: Connection invalid
WebContent[41791] Conn 0x0 is not a valid connection ID.
WebContent[41791] Conn 0x0 is not a valid connection ID.
WebContent[41791] Conn 0x0 is not a valid connection ID.
WebContent[41791] Got an XPC_ERROR_INVALID on our server connection, so failing.
WebContent[41791] CRASHSTRING: XPC_ERROR_CONNECTION_INVALID from launchservicesd
WebContent[41791] CRASHSTRING: <private>
WebContent[41791] CRASHSTRING: <rdar://problem/28724618> Process unable to create connection because the sandbox denied the right to lookup com.apple.coreservices.launchservicesd and so this process cannot talk to launchservicesd.
WebContent[41791] rdar://problem/28724618 Unable to register with launchservicsed, couldn't create connection object.
WebContent[41791] invalid product id '(null)'
WebContent[41791] checkinWithServer Failed bootstrap_lookup2 for name of coreservicesd, kern_return_t=#1100/0x44c Permission denied name=com.apple.CoreServices.coreservicesd
WebContent[41791] The sandbox in this process does not allow access to RunningBoard.
WebContent[41791] Handshake aborted as the connection has been invalidated
WebContent[41791] Conn 0x0 is not a valid connection ID.
WebContent[41791] Conn 0x0 is not a valid connection ID.
WebContent[41791] Conn 0x0 is not a valid connection ID.
WebContent[41791] Conn 0x0 is not a valid connection ID.
WebContent[41791] Conn 0x0 is not a valid connection ID.
WebContent[41791] Conn 0x0 is not a valid connection ID.
WebContent[41791] Missing the com.apple.linkd.autoShortcut mach-lookup entitlement, will NOT register the process
WebContent[41791] Error registering app with intents framework: Error Domain=LNProcessInstanceRegistryClientErrorDomain Code=1
WebContent[41791] AudioComponentPluginMgr.mm:590   reg server remote proxy error Error Domain=NSCocoaErrorDomain Code=4099 "The connection to service named com.apple.audio.AudioComponentRegistrar was invalidated: Connection init failed at lookup with error 1 - Operation not permitted." UserInfo={NSDebugDescription=The connection to service named com.apple.audio.AudioComponentRegistrar was invalidated: Connection init failed at lookup with error 1 - Operation not permitted.}
WebContent[41791] networkd_settings_read_from_file Sandbox is preventing this process from reading networkd settings file at "/Library/Preferences/com.apple.networkd.plist", please add an exception.
WebContent[41791] networkd_settings_read_from_file Sandbox is preventing this process from reading networkd settings file at "/Library/Preferences/com.apple.networkd.plist", please add an exception.
[ChartBridge] Flushed 0 pending commands
[ChartBridge] Chart ready
[WebChartView] Navigation finished
[ChartBridge] Heikin-Ashi toggled: true
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] ⚠️ Detected 16 large time gaps (> 86400s). Top gaps:
[ChartBridge]   Gap 2.4 days between 2025-10-17 23:00:00 +0000 and 2025-10-20 08:00:00 +0000
[ChartBridge]   Gap 2.4 days between 2025-10-24 23:00:00 +0000 and 2025-10-27 08:00:00 +0000
[ChartBridge]   Gap 2.4 days between 2025-10-31 23:00:00 +0000 and 2025-11-03 09:00:00 +0000
[ChartBridge] Candles: 950 bars
[ChartBridge] First: 2025-10-16 14:00:00 +0000 O:247.56 H:248.89 L:246.92 C:248.58
[ChartBridge] Last: 2026-01-16 18:00:00 +0000 O:255.165 H:256.815 L:255.09 C:256.51
[WebChartView] SuperTrend: 950 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 941 aligned points
[WebChartView] Chart updated with 950 bars
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] ⚠️ Detected 16 large time gaps (> 86400s). Top gaps:
[ChartBridge]   Gap 2.4 days between 2025-10-17 23:00:00 +0000 and 2025-10-20 08:00:00 +0000
[ChartBridge]   Gap 2.4 days between 2025-10-24 23:00:00 +0000 and 2025-10-27 08:00:00 +0000
[ChartBridge]   Gap 2.4 days between 2025-10-31 23:00:00 +0000 and 2025-11-03 09:00:00 +0000
[ChartBridge] Candles: 950 bars
[ChartBridge] First: 2025-10-16 14:00:00 +0000 O:247.56 H:248.89 L:246.92 C:248.58
[ChartBridge] Last: 2026-01-16 18:00:00 +0000 O:255.165 H:256.815 L:255.09 C:256.51
[WebChartView] SuperTrend: 950 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 941 aligned points
[WebChartView] Chart updated with 950 bars
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 950
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] 🕒 timeframe changed to d1 (apiToken=d1)
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() CALLED
[DEBUG] ========================================
[DEBUG] ChartViewModel.loadChart() - Using cached bars: 502, newest bar age: 16h
[DEBUG] - Symbol: AAPL
[DEBUG] - Asset Type: stock
[DEBUG] - Timeframe: d1 (sending: d1)
[DEBUG] - Is Intraday: false
[DEBUG] - Starting chart data fetch...
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
Error acquiring assertion: <Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}>
0x12a1bc1e0 - ProcessAssertion::acquireSync Failed to acquire RBS assertion 'XPCConnectionTerminationWatchdog' for process with PID=41791, error: Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}
Error acquiring assertion: <Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}>
0x12a1bc240 - ProcessAssertion::acquireSync Failed to acquire RBS assertion 'WebProcess NearSuspended Assertion' for process with PID=41791, error: Error Domain=RBSServiceErrorDomain Code=1 "(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)" UserInfo={NSLocalizedFailureReason=(target is not running or doesn't have entitlement com.apple.runningboard.assertions.webkit AND originator doesn't have entitlement com.apple.runningboard.assertions.webkit)}
[DEBUG] 📊 Fetching chart-read: symbol=AAPL, timeframe=d1, cacheBuster=1768600521
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-read?t=1768600521&symbol=AAPL&timeframe=d1
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: true
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[SymbolSync] ✅ Synced AAPL (chart_view): 5 jobs created/updated
[DEBUG] 📊 Response Headers for AAPL/d1
[DEBUG] - Status: 200
[DEBUG] - Cache-Control: no-cache, no-store, must-revalidate
[DEBUG] - Age: 0s
[DEBUG] - Via: direct
[DEBUG] - ETag: none
[DEBUG] - CF-Cache-Status: DYNAMIC
[DEBUG] API Response status: 200
[DEBUG] API Response body: {"symbol":"AAPL","assetType":"stock","timeframe":"d1","bars":[{"ts":"2024-01-18T05:00:00+00:00","open":186.06,"high":189.135,"low":185.89,"close":188.7,"volume":1405733,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-19T05:00:00+00:00","open":189.35,"high":191.945,"low":188.845,"close":191.55,"volume":1126703,"upper_band":null,"lower_band":null,"confidence_score":null},{"ts":"2024-01-22T05:00:00+00:00","open":192.39,"high":195.325,"low":192.32,"close":193.89,"volume":
[DEBUG] ChartViewModel.loadChart() - chart-read SUCCESS!
[DEBUG] - Bars: 502
[DEBUG] - ML: ✓
[ChartCache] Saved 502 bars to AAPL_d1.json
[DEBUG] ChartViewModel.loadChart() COMPLETED
[DEBUG] - Final state: chartData=non-nil, isLoading=false, errorMessage=nil
[DEBUG] ========================================
[PolynomialSR] ========================================
[PolynomialSR] Calculating for 502 bars
[PolynomialSR] First bar close: 188.70
[PolynomialSR] Last bar close: 255.47
[PolynomialSR] Found 31 resistance pivots, 28 support pivots
[PolynomialSR] Resistance pivot prices (first 5): [191.01, 185.01, 178.61, 178.35, 186.97]
[PolynomialSR] Support pivot prices (first 5): [179.25, 180.01, 168.50, 168.27, 167.12]
[PolynomialSR] Resistance: Linear, pivots=11, range=[10-135], pred@0=298.46
[PolynomialSR]   Generated 156 points
[PolynomialSR]   First point: barIdx=366, price=218.01
[PolynomialSR]   Last point: barIdx=521, price=310.38
[PolynomialSR] Support: Linear, pivots=8, range=[6-146], pred@0=274.03
[PolynomialSR]   Generated 167 points
[PolynomialSR]   First point: barIdx=355, price=195.86
[PolynomialSR]   Last point: barIdx=521, price=284.74
[PolynomialSR] ========================================
[PolynomialSR] Result: R=298.46, S=274.03
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔵 ChartHeader.body rendering with symbol: AAPL
[WebChartView] Loading chart from bundle root: file:///Users/ericpeterson/Library/Developer/Xcode/DerivedData/SwiftBoltML-fvczbmwpxtcqewgbpaecwhupjwxf/Build/Products/Debug/SwiftBoltML.app/Contents/Resources/index.html
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
WebContent[41798] Connection to 'pboard' server had an error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41798] Failed to set up CFPasteboardRef 'Apple CFPasteboard general'. Error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41798] Failed to set up CFPasteboardRef 'Apple CFPasteboard general'. Error: <dictionary: 0x20bcb7c10> { count = 1, transaction: 0, voucher = 0x0, contents =
	"XPCErrorDescription" => <string: 0x20bcb7d58> { string cache = 0x0, length = 18, contents = "Connection invalid" }
}
Invalidation reason: Connection init failed at lookup with error 159 - Sandbox restriction
WebContent[41798] send_message_with_reply_sync(): XPC_ERROR_CONNECTION_INVALID for message 0xac9094a80
WebContent[41798] TCCAccessRequest_block_invoke: Connection invalid
WebContent[41798] Conn 0x0 is not a valid connection ID.
WebContent[41798] Conn 0x0 is not a valid connection ID.
WebContent[41798] Conn 0x0 is not a valid connection ID.
WebContent[41798] Got an XPC_ERROR_INVALID on our server connection, so failing.
WebContent[41798] CRASHSTRING: XPC_ERROR_CONNECTION_INVALID from launchservicesd
WebContent[41798] CRASHSTRING: <private>
WebContent[41798] CRASHSTRING: <rdar://problem/28724618> Process unable to create connection because the sandbox denied the right to lookup com.apple.coreservices.launchservicesd and so this process cannot talk to launchservicesd.
WebContent[41798] rdar://problem/28724618 Unable to register with launchservicsed, couldn't create connection object.
WebContent[41798] invalid product id '(null)'
WebContent[41798] checkinWithServer Failed bootstrap_lookup2 for name of coreservicesd, kern_return_t=#1100/0x44c Permission denied name=com.apple.CoreServices.coreservicesd
WebContent[41798] The sandbox in this process does not allow access to RunningBoard.
WebContent[41798] Handshake aborted as the connection has been invalidated
WebContent[41798] Conn 0x0 is not a valid connection ID.
WebContent[41798] Conn 0x0 is not a valid connection ID.
WebContent[41798] Conn 0x0 is not a valid connection ID.
WebContent[41798] Conn 0x0 is not a valid connection ID.
WebContent[41798] Conn 0x0 is not a valid connection ID.
WebContent[41798] Conn 0x0 is not a valid connection ID.
WebContent[41798] Missing the com.apple.linkd.autoShortcut mach-lookup entitlement, will NOT register the process
WebContent[41798] Error registering app with intents framework: Error Domain=LNProcessInstanceRegistryClientErrorDomain Code=1
WebContent[41798] AudioComponentPluginMgr.mm:590   reg server remote proxy error Error Domain=NSCocoaErrorDomain Code=4099 "The connection to service named com.apple.audio.AudioComponentRegistrar was invalidated: Connection init failed at lookup with error 1 - Operation not permitted." UserInfo={NSDebugDescription=The connection to service named com.apple.audio.AudioComponentRegistrar was invalidated: Connection init failed at lookup with error 1 - Operation not permitted.}
WebContent[41798] networkd_settings_read_from_file Sandbox is preventing this process from reading networkd settings file at "/Library/Preferences/com.apple.networkd.plist", please add an exception.
WebContent[41798] networkd_settings_read_from_file Sandbox is preventing this process from reading networkd settings file at "/Library/Preferences/com.apple.networkd.plist", please add an exception.
[ChartBridge] Flushed 1 pending commands
[ChartBridge] Chart ready
[WebChartView] Navigation finished
[ChartBridge] Heikin-Ashi toggled: true
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] Candles: 502 bars
[ChartBridge] First: 2024-01-18 05:00:00 +0000 O:186.06 H:189.135 L:185.89 C:188.7
[ChartBridge] Last: 2026-01-16 05:00:00 +0000 O:258.08 H:258.89 L:254.93 C:255.475
[WebChartView] SuperTrend: 502 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 493 aligned points
[WebChartView] Chart updated with 502 bars
[ChartBridge] ✅ No large price jumps (>25%) detected
[ChartBridge] Candles: 502 bars
[ChartBridge] First: 2024-01-18 05:00:00 +0000 O:186.06 H:189.135 L:185.89 C:188.7
[ChartBridge] Last: 2026-01-16 05:00:00 +0000 O:258.08 H:258.89 L:254.93 C:255.475
[WebChartView] SuperTrend: 502 points, AI factors: [3.0, 3.0, 3.0, 3.0, 3.0]
[ChartBridge] SuperTrend: 493 aligned points
[WebChartView] Chart updated with 502 bars
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
[DEBUG] ChartView.body
- isLoading: false
- error: nil
- chartData is non-nil
- barCount: 502
[DEBUG] 🔴 SymbolSearchView.body rendering
[DEBUG] - Search results count: 0
[DEBUG] - Search query: ''
[DEBUG] - Is searching: false
---
