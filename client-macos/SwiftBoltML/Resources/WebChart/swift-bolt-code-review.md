# SwiftBolt Charting – Focused Code Review
_Generated: Jan 6, 2026_

### Scope
- Reviewed SwiftUI view layer for charting and analysis UI:
  - AdvancedChartView.swift
  - WebChartView.swift
  - WebChartControlsView.swift
  - IndicatorPanelViews.swift
  - ChartView.swift, AnalysisView.swift, ForecastHorizonsView.swift, PredictionsView.swift, WatchlistView.swift
- Assumptions: macOS target (uses `NSViewRepresentable`), Swift 5.10, Xcode 16, Swift Charts + WKWebView.

## High‑impact fixes (quick wins)
1) **`ForEach(Array(visibleRange))` → `ForEach(visibleRange)`** *(perf, allocs)*
   - In `IndicatorPanelViews.swift` there are 11 instances of `ForEach(Array(visibleRange), id: \..self)`.
   - Using `Array(...)` allocates every render. Ranges already conform to `RandomAccessCollection`.

   **Patch:**
```swift
// Before
ForEach(Array(visibleRange), id: \.self) { index in ... }
// After
ForEach(visibleRange, id: \.self) { index in ... }
```

2) **Hardcoded dev resource path for web chart** *(portability, CI)*
   - `WebChartView.makeNSView` falls back to an absolute path:
     `/Users/ericpeterson/.../Resources/WebChart`. Gate this behind `#if DEBUG` and prefer `Bundle`/env overrides.
   **Patch:**
```swift
#if DEBUG
if let devRoot = ProcessInfo.processInfo.environment["WEBCHART_DEV_ROOT"] {
    let htmlURL = URL(fileURLWithPath: devRoot).appendingPathComponent("index.html")
    if FileManager.default.fileExists(atPath: htmlURL.path) {
        webView.loadFileURL(htmlURL, allowingReadAccessTo: htmlURL.deletingLastPathComponent())
        return
    }
}
#endif
```

3) **WebView cleanup** *(leaks, dangling refs)*
   - You already remove the `bridge` script handler in `dismantleNSView`. Also nil out the `navigationDelegate` and clear Combine subscriptions.
   **Patch:**
```swift
static func dismantleNSView(_ nsView: WKWebView, coordinator: Coordinator) {
    nsView.configuration.userContentController.removeScriptMessageHandler(forName: "bridge")
    nsView.navigationDelegate = nil
    coordinator.cancellables.removeAll()
}
```

4) **Throttle expensive indicator updates** *(jank, main‑thread work)*
   - Indicator toggles push full arrays to JS. Debounce rapid changes (e.g. toggling multiple) and move JSON encoding off the main actor.
   **Sketch:**
```swift
parent.viewModel.$indicatorConfig
    .removeDuplicates()
    .debounce(for: .milliseconds(150), scheduler: DispatchQueue.main)
    .sink { [weak self] _ in self?.applyIndicators() }
    .store(in: &cancellables)
```

## WebChartView
- ✅ Good separation with `Coordinator` and Combine pipelines; `eventPublisher` for visible‑range sync is solid.
- ❗ **Resource loading:** Prefer `Bundle.main.url(forResource:withExtension:subdirectory:)` first (you do), keep dev path `#if DEBUG` only.
- ❗ **MainActor:** Mark `Coordinator` methods that touch UI/bridge with `@MainActor` to ensure UI thread affinity.
- 🔒 **Preferences:** If you rely on JS, ensure `config.defaultWebpagePreferences.allowsContentJavaScript = true` (on macOS 12+).
- 🧹 **WKUserScript:** Consider injecting a small bootstrap script at `.atDocumentStart` to register the Swift ↔ JS bridge early.
- 🧪 **Testability:** Wrap WebView creation behind a protocol so you can unit‑test the coordinator with a fake bridge.

**Minor nit:** Replace `print` with a lightweight logger that you can silence in release builds.

## AdvancedChartView & IndicatorPanelViews (Swift Charts)
- ✅ Uses `ChartProxy`, `.chartOverlay`, `.chartLegend`, crosshair via `onContinuousHover`—nice.
- ❗ **Allocation hot‑paths:** Avoid building temporary arrays in marks; iterate ranges directly (see quick win #1).
- ❗ **Downsampling:** Swift Charts slows > ~3–5k marks. Add an LTTB/Min‑Max sampler in the ViewModel and feed reduced points based on current pixel width.
```swift
struct Downsampler {
  static func lttb(_ points: [CGPoint], threshold: Int) -> [CGPoint] { /* implement */ }
}
```
- 🎨 **Theming:** `ChartColors` are static dark‑optimized values. For light mode, use dynamic colors or asset catalog named colors.
- 📈 **Legend:** Consider suppressing per‑series legends when many overlays are on; it can trigger expensive re‑layout. Use a custom compact legend instead.
- 🧭 **Selection reset:** When dataset/symbol changes, clear `selectedBar/selectedIndex` to avoid stale overlays.
- 🧩 **Reuse:** Repeated mark pipelines (e.g., RSI, MACD) can be factored into small `View` builders to reduce body diff noise and compile time.

## ChartView / AnalysisView / PredictionsView / WatchlistView
- ✅ Good `Task { await ... }` usage when reacting to selection changes.
- ❗ **Cancellation:** Store the in‑flight `Task` and cancel on a new trigger to avoid overlapping loads.
```swift
@State private var loadTask: Task<Void, Never>?
onChange(of: appViewModel.selectedSymbol) { _, new in
  loadTask?.cancel()
  loadTask = Task { await analysisViewModel.loadAlerts(for: new?.ticker) }
}
```
- ♿ **Accessibility:** Add labels/hints for interactive chart areas (hover overlay) and ensure text contrasts in both color schemes.
- 🧰 **Previews:** Consider a couple of SwiftUI previews with stubbed view models for the most complex views to speed design iteration.

## Suggested file‑level edits
- `IndicatorPanelViews.swift`: replace all `ForEach(Array(visibleRange))` → `ForEach(visibleRange)` (11 instances).
- `WebChartView.swift`:
  - Gate the dev path with `#if DEBUG` and optional `WEBCHART_DEV_ROOT`.
  - In `dismantleNSView`: nil `navigationDelegate`, clear `cancellables`.
  - Consider `@MainActor` on `Coordinator` and `ChartBridge`.
- `AdvancedChartView.swift`: extract duplicated indicator mark code into small views; add downsampling.

## Nice‑to‑have (phase 2)
- **GPU‑friendly overlays:** For custom trendlines/polynomials, render heavy paths via `Canvas` with `.drawingGroup()` when the segment count is high.
- **State coalescing:** Enforce a single source of truth for visible range (either JS or Swift Charts) and broadcast changes to avoid ping‑pong updates.
- **Metrics:** Emit frame time / mark count counters using `os_signpost` to catch regressions.

---
### Appendix — counts & quick stats
- Files reviewed: 9
- AdvancedChartView.swift LOC: ~2328
- IndicatorPanelViews: multiple `Chart {}` sections; 11 array‑based iterations over visible range.
- WebChartView: 8 Combine sinks; message handler removed on dismantle ✅