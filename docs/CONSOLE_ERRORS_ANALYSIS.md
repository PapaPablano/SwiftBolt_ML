# Console Errors Analysis - 2026-01-23

## Critical Errors to Fix

### 1. 🔴 CRITICAL: Value Score Still Exceeding 100
**Error:**
```
"value_score":257.567238661848
```

**Issue**: Despite implementing score capping in the Python code, the database still contains old rankings with uncapped scores (257/100).

**Impact**: 
- Value score dominates composite rankings
- Weights don't work as intended
- Rankings are inaccurate

**Fix Required**:
```bash
# Re-run ranking job to regenerate all data with capped scores
cd /Users/ericpeterson/SwiftBolt_ML/ml
python -m src.options_ranking_job --symbol AAPL --mode monitor
```

**Status**: ⚠️ Python code fixed, but database needs regeneration

---

### 2. 🔴 CRITICAL: Publishing Changes From Within View Updates
**Error** (appears 40+ times):
```
Publishing changes from within view updates is not allowed, this will cause undefined behavior.
```

**Issue**: SwiftUI state (@Published properties) is being modified during view rendering, causing potential crashes and undefined behavior.

**Root Cause**: Likely in one of these ViewModels:
- `OptionsRankerViewModel`
- `OptionsChainViewModel`
- `ChartViewModel`
- `AppViewModel`

**Common Patterns That Cause This**:
```swift
// BAD: Publishing from computed property or view body
var body: some View {
    someView
        .onAppear {
            // This is OK
        }
        .onChange(of: someValue) { oldValue, newValue in
            self.publishedProperty = newValue // This is OK
        }
}

// BAD: Publishing from within a computed property
var someComputedValue: String {
    self.publishedProperty = "new value" // ❌ NOT OK
    return "value"
}
```

**Fix Required**: Need to identify which ViewModel is publishing during view updates and move the state change to an async Task or onChange handler.

**Impact**: Can cause app crashes, UI glitches, and unpredictable behavior.

---

### 3. 🟡 MODERATE: Technical Indicators API 404
**Error** (appears multiple times):
```
[DEBUG] API Response status: 500
[DEBUG] API Error response: {"error":"Not Found"}
[DEBUG] API Request: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/technical-indicators?symbol=AAPL&timeframe=d1
```

**Issue**: The `technical-indicators` Supabase function is returning 404/500 errors.

**Impact**: Analysis tab indicators don't load properly.

**Fix Required**: Either:
1. Deploy the missing `technical-indicators` function, OR
2. Update the Swift code to handle this gracefully (already has retry logic)

**Status**: ⚠️ Non-critical (app still works, just missing one feature)

---

## Minor Warnings (Non-Critical)

### 4. ⚪ WebContent Sandbox Warnings
```
WebContent[30639] Connection to 'pboard' server had an error
WebContent[30639] The sandbox in this process does not allow access to RunningBoard
WebContent[30639] networkd_settings_read_from_file Sandbox is preventing...
```

**Issue**: Normal macOS sandbox restrictions for WebView components.

**Impact**: None - these are expected warnings when using WKWebView in a sandboxed app.

**Fix Required**: None (or add entitlements if clipboard/system access is needed).

---

### 5. ⚪ Missing SF Symbols
```
No symbol named 'chart.pie.circle' found in system symbol set
No symbol named 'exclamationmark.triangle.circle' found in system symbol set
No symbol named 'chart.3d' found in system symbol set
```

**Issue**: Trying to use SF Symbols that don't exist in the current macOS version.

**Impact**: Icons won't display, but app still works.

**Fix Required**: Replace with valid SF Symbol names or use fallback icons.

---

### 6. ⚪ Layout Recursion Warning
```
It's not legal to call -layoutSubtreeIfNeeded on a view which is already being laid out.
```

**Issue**: SwiftUI layout recursion (logged only once).

**Impact**: Minimal - logged only once, so not a persistent issue.

**Fix Required**: None (unless it causes visible UI issues).

---

## Recommended Fix Priority

### Priority 1: Fix Publishing Changes Error
**Location to investigate**:
```swift
// Search for patterns like:
// 1. @Published properties being set in computed properties
// 2. @Published properties being set in view body
// 3. @Published properties being set synchronously in API callbacks

// Likely culprits:
- OptionsRankerViewModel.swift
- AppViewModel.swift  
- ChartViewModel.swift
```

**Search command**:
```bash
cd /Users/ericpeterson/SwiftBolt_ML/client-macos
# Find all @Published properties
rg "@Published" -A 10 --type swift

# Find onChange handlers
rg "\.onChange" -A 5 --type swift
```

### Priority 2: Regenerate Rankings Database
**Command**:
```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml

# Regenerate AAPL rankings with score capping
python -m src.options_ranking_job --symbol AAPL --mode monitor

# Optional: Regenerate other symbols
python -m src.options_ranking_job --symbol NVDA --mode monitor
python -m src.options_ranking_job --symbol TSLA --mode monitor
```

### Priority 3: Fix Missing SF Symbols
**Files to update**:
- Search for `chart.pie.circle`, `exclamationmark.triangle.circle`, `chart.3d`
- Replace with valid symbols or add fallback

---

## Testing After Fixes

1. **Verify Score Capping**:
   - Open Options Ranker
   - Select any contract
   - Open Contract Workbench → Why Ranked
   - Verify all scores ≤ 100

2. **Verify No Publishing Errors**:
   - Run app in Xcode
   - Monitor console
   - Navigate through all tabs
   - Ensure no "Publishing changes" warnings

3. **Test Mode Switching**:
   - Switch between Entry/Exit/Monitor modes
   - Verify no crashes or warnings

---

## Summary

| Issue | Severity | Status | Fix Needed |
|-------|----------|--------|------------|
| Value scores >100 | 🔴 Critical | ⚠️ Code fixed, DB needs update | Regenerate rankings |
| Publishing changes | 🔴 Critical | ❌ Not fixed | Identify and fix state management |
| Technical indicators 404 | 🟡 Moderate | ⚠️ Handled with retries | Deploy function or improve error handling |
| WebContent sandbox | ⚪ Minor | ✅ Expected | None |
| Missing SF Symbols | ⚪ Minor | ⚠️ Cosmetic | Replace with valid symbols |
| Layout recursion | ⚪ Minor | ✅ One-time | Monitor for recurrence |

## Next Steps

1. ✅ Score capping code is fixed
2. ⏳ **Need to fix "Publishing changes" error** (most critical)
3. ⏳ Need to regenerate rankings database
4. ⏳ Optional: Fix missing SF Symbols
