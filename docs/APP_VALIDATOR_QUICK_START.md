# App Validator: Quick Start (Copy-Paste Ready)

**Updated Strategy**: Validator in app (not backend)

---

## This Week's Tasks

### 🟢 Day 1: Seed Symbols (1 hour)
```bash
cd backend
psql $DATABASE_URL < scripts/seed-symbols.sql
./test_symbol_sync.sh
# ✅ Verify: jobs_updated should be 3 (not 0)
```

### 🟣 Day 2-3: API Endpoint (2 days)
```bash
# Create two endpoint functions
touch backend/supabase/functions/get-unified-validation/index.ts
touch backend/supabase/functions/log-validation-audit/index.ts

# See APP_VALIDATOR_IMPLEMENTATION_GUIDE.md for code
# Deploy: npm run deploy

# Test
curl 'https://<project>.supabase.co/functions/v1/get-unified-validation?symbol=AAPL'
```

### 🟤 Day 4-6: Swift App Module (3 days)
```bash
# Create 3 files
touch SwiftBolt/Models/UnifiedValidator.swift
touch SwiftBolt/ViewModels/ValidationViewModel.swift
touch SwiftBolt/Views/ValidationDashboardView.swift

# See APP_VALIDATOR_IMPLEMENTATION_GUIDE.md for code

# Test on simulator
# Cmd+U (run tests)
# Cmd+R (build & run)
```

---

## Architecture at a Glance

```
Backend                    App                     User
══════                    ═══                     ════

Metrics                 Reconciliation          Controls
Backtest (0.988)  →  UnifiedValidator  →  "Adjust Weights"
Walkforward (0.825)→  (on-device)      →  • See live confidence
Live (0.40)        →  Confidence: 0.72 →  • Drift alerts
M15/H1/D1 signals  →  Timeframe merge   →  • Offline support
                      Cache locally      →  • Settings

Result: Backend provides data,
        App handles meaning
```

---

## File Structure Changes

### Backend
```
backend/supabase/functions/
  ├── get-unified-validation/
  │   └── index.ts                 (NEW)
  ├── log-validation-audit/
  │   └── index.ts                 (NEW)
  └── sync-user-symbols/        (existing)
```

### App
```
SwiftBolt/
  ├── Models/
  │   └── UnifiedValidator.swift       (NEW)
  ├── ViewModels/
  │   └── ValidationViewModel.swift    (NEW)
  └── Views/
      └── ValidationDashboardView.swift (NEW)
```

---

## API Response Format

**Endpoint**: `GET /functions/v1/get-unified-validation?symbol=AAPL`

**Response**:
```json
{
  "symbol": "AAPL",
  "backtest_score": 0.988,
  "walkforward_score": 0.825,
  "live_score": 0.40,
  "m15_signal": "BULLISH",
  "h1_signal": "BEARISH",
  "d1_signal": "BEARISH",
  "timestamp": 1737460700000
}
```

---

## Key Components

### Model: `UnifiedValidator`
- Stores backtest/walkforward/live scores + TF signals
- Applies weights → calculates single confidence score
- Detects drift (>15% divergence)
- Reconciles multi-timeframe consensus
- Works with cached data

### ViewModel: `ValidationViewModel`
- Polls API every 5 minutes
- Handles network failures gracefully
- Caches results in UserDefaults
- Recalculates when user changes weights
- Syncs audit trail (non-critical)

### View: `ValidationDashboardView`
- Large confidence badge (colored by score)
- Score breakdown (3 columns)
- Multi-TF consensus section
- Drift alerts
- Settings button
- Offline indicator

---

## Default Configuration (In App)

```swift
ValidationWeights(
    backtest: 0.40,           // Historical accuracy
    walkforward: 0.35,        // Recent out-of-sample
    live: 0.25,              // Current real-time
    driftThreshold: 0.15,     // Alert if >15% divergence
    timeframeWeight: .durationBased  // D1 > H1 > M15
)
```

**User can adjust all of these in Settings!**

---

## Testing Shortcuts

### Test API Endpoint
```bash
curl 'https://<project>.supabase.co/functions/v1/get-unified-validation?symbol=AAPL'
```

### Test Model Calculation
```swift
let validator = UnifiedValidator(
    backtest: 0.988,
    walkforward: 0.825,
    live: 0.40,
    weights: ValidationWeights()
)
print(validator.confidence)  // Should be ~0.72
print(validator.hasDrift)    // false (divergence < 15%)
```

### Test Offline Mode
```swift
// In ValidationViewModel
reachability.isConnected = false
await viewModel.fetchValidation()
// Should load from cache with "Offline" badge
```

---

## Effort Summary

| Task | Time | Notes |
|------|------|-------|
| Seed symbols | 1h | Unblocks Swift app |
| API endpoints | 2d | Two functions (metrics + audit) |
| Swift models | 1d | Data structures + logic |
| ViewModel | 1d | Polling + caching |
| UI views | 1d | Dashboard + settings |
| **Total** | ~6d | Achievable this week |

---

## Why This Approach?

**Backend = Data Provider**
- Computes: backtesting, walkforward, live scores
- Provides: multi-TF signals
- Stores: metrics in DB for auditing

**App = Intelligence Layer**
- Weights scores (user-configurable)
- Detects drift
- Reconciles timeframes
- Works offline
- Shows single confidence score

**Result**
- ✅ User controls logic (adjustable weights)
- ✅ No backend redeploys
- ✅ Works offline
- ✅ Instant UI updates
- ✅ Clear separation of concerns
- ✅ Audit trail for debugging

---

## Documentation

- **Full Strategy**: `SWIFTBOLT_APP_VALIDATOR_STRATEGY.md` (this explains the why)
- **Implementation Guide**: `APP_VALIDATOR_IMPLEMENTATION_GUIDE.md` (copy-paste code)
- **This file**: Quick reference (you are here)

---

**Status**: Ready to start! Begin with Day 1 (seed symbols table).
