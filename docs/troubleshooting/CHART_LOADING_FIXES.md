# Chart Loading Fixes - Implementation Plan

## Issues Identified
1. **Cancellation race (-999)**: Multiple loads fire simultaneously, earlier ones get cancelled, UI never recovers
2. **Empty data with no retry**: Fresh symbols return 0 bars, backfill runs but UI never refetches
3. **Overlays without candles**: SuperTrend/indicators render on empty grid
4. **WebView not ready**: Commands sent before WebView process is ready
5. **Adaptive MA crash**: Range calculation can produce invalid bounds

## Fixes to Apply

### A) Single-Flight Load Pattern (ChartViewModel.swift)
- Cancel existing task before starting new one
- Swallow CancellationError instead of setting isLoading=false
- Add auto-retry: if 0 bars → ensureCoverage → poll → refetch
- Apply to ALL timeframes (not just intraday)

### B) Guard Overlay Rendering (WebChartView.swift)
- Only push overlays when candles.count > 0
- Clear chart when no data

### C) WebView Ready Queue (ChartBridge.swift)
- Buffer commands until WebView signals ready
- Flush pending on ready signal

### D) Safe Adaptive MA (SuperTrendAIIndicator.swift)
- Use windowed average with rolling buffer
- No negative ranges

### E) Single Trigger (ChartView.swift)
- Replace multiple .onChange with single .task(id:)
- Deterministic reload on symbol|timeframe change

## Implementation Order
1. Fix adaptive MA crash (safety)
2. Implement single-flight load with auto-retry
3. Guard overlay rendering
4. Add WebView ready queue
5. Replace triggers with .task(id:)
