# SwiftBolt_ML: App-Centric Validation Strategy

**Status**: Strategy Document (Updated Implementation Plan)  
**Date**: January 21, 2026  
**Change**: Moving validator from backend Python to Swift app (on-device) with API endpoint  

---

## 🎯 The Three Core Issues (Unchanged)

### 1. Dashboard Confusion ⚠️ (NOW FIXED IN APP)
Your dashboards show contradictory metrics:

| Source | Shows | Training Window | Problem |
|--------|-------|---|---|
| Statistical Validation Tab | 98.8% precision | 3 months (backtesting) | Historical accuracy |
| Live AAPL Forecast | 40% BEARISH | Real-time | Current prediction |
| Multi-TF Bars | M15: -48%, H1: -40%, D1: -40% | Different lookbacks | Which to trust? |

**Root Cause**: No reconciliation logic. Dashboard shows raw metrics without context.

**New Fix**: Create `UnifiedValidator` running **in Swift app** (on-device) that:
- Receives backtesting (40%) + walkforward (35%) + live (25%) from backend API endpoint
- Reconciles multi-timeframe signals on-device
- Generates single confidence score with drift alerts
- Works offline with cached predictions
- **User controls validation weights directly in app settings** (no backend redeploy needed)

**Why app-side?**
- ✅ User controls logic (adjustable weights)
- ✅ Offline-capable (cached metrics)
- ✅ Faster UI updates (on-device calculation)
- ✅ Clear separation (backend = metrics, app = meaning)
- ✅ Audit trail (syncs decisions back to backend)

---

### 2. Symbol Tracking Blocked 🚫 (UNCHANGED)
Swift app successfully calls Edge Function, but creates 0 jobs.

**Root Cause**: `symbols` table is empty.  
**Fix**: Seed symbols table (1 hour work).  
**Status**: Ready to implement Day 1

---

### 3. Script Accumulation 📚 (UNCHANGED)
35+ backend scripts with overlapping functionality.

**Fix**: Create shared library + consolidate to 4 canonical scripts.  
**Status**: Planned for next week (lower priority)

---

## 📊 Quick Wins (Updated Timeline)

### Day 1: Unblock Swift App (1 hour)
```bash
cd backend
psql $DATABASE_URL < scripts/seed-symbols.sql
./test_symbol_sync.sh  # Should show jobs_updated: 3 (not 0)
```
**Outcome**: Swift app can now create backfill jobs

---

### Day 2-3: Create Validation API Endpoint (2 days)
**File**: `backend/supabase/functions/get-unified-validation/index.ts`

**Purpose**: Backend provides raw metrics, app handles reconciliation

**API Spec**:
```
GET /functions/v1/get-unified-validation?symbol=AAPL

Response:
{
  "symbol": "AAPL",
  "backtest_score": 0.988,       // Historical (3mo backtest)
  "walkforward_score": 0.825,    // Recent out-of-sample
  "live_score": 0.40,            // Current real-time
  "m15_signal": "BULLISH",       // M15 consensus
  "h1_signal": "BEARISH",        // H1 consensus
  "d1_signal": "BEARISH",        // D1 consensus
  "timestamp": 1737460700
}
```

**Implementation**:
```bash
cd backend/supabase/functions
touch get-unified-validation/index.ts

# Add function that:
# 1. Fetches latest backtest/walkforward/live scores from DB
# 2. Gets multi-TF signals for symbol
# 3. Returns as JSON

touch log-validation-audit/index.ts
# Add function to receive audit trail from Swift app (optional, fire & forget)
```

**Test**:
```bash
curl 'https://<project>.supabase.co/functions/v1/get-unified-validation?symbol=AAPL'
# Should return validation metrics
```

---

### Day 4-6: Build Swift Validator Module (3 days)

#### File 1: `SwiftBolt/Models/UnifiedValidator.swift`
**Purpose**: Data model + reconciliation logic

```swift
struct UnifiedValidator {
    let symbol: String
    let backtestScore: Double
    let walkforwardScore: Double
    let liveScore: Double
    let m15Signal: Signal
    let h1Signal: Signal
    let d1Signal: Signal
    let timestamp: Date
    
    // User-configurable weights (persisted to UserDefaults)
    let weights: ValidationWeights
    
    // Reconciliation result (on-device calculation)
    var confidence: Double {
        backtestScore * weights.backtest +
        walkforwardScore * weights.walkforward +
        liveScore * weights.live
    }
    
    var hasDrift: Bool {
        abs(liveScore - backtestScore) > weights.driftThreshold
    }
    
    var timeframeConsensus: Signal {
        // Reconcile M15, H1, D1
        // e.g., "if 2+ votes for same direction" or "weight by timeframe"
        reconcileTimeframes(m15Signal, h1Signal, d1Signal, weights: weights)
    }
}

struct ValidationWeights: Codable {
    var backtest: Double = 0.40      // User-adjustable
    var walkforward: Double = 0.35
    var live: Double = 0.25
    var driftThreshold: Double = 0.15
    var timeframeWeight: TimeframeWeight = .durationBased
    
    enum TimeframeWeight {
        case durationBased        // D1 weighted higher (50%/30%/20%)
        case recentPerformance    // Weight by live score quality
        case equal                // 1/3 each
    }
    
    func save() {
        let encoder = JSONEncoder()
        if let data = try? encoder.encode(self) {
            UserDefaults.standard.set(data, forKey: "validationWeights")
        }
    }
    
    static func load() -> ValidationWeights {
        let decoder = JSONDecoder()
        if let data = UserDefaults.standard.data(forKey: "validationWeights"),
           let weights = try? decoder.decode(ValidationWeights.self, from: data) {
            return weights
        }
        return ValidationWeights()  // Defaults
    }
}

enum Signal: String, Codable {
    case bullish = "BULLISH"
    case bearish = "BEARISH"
    case neutral = "NEUTRAL"
}
```

**Key Points**:
- All reconciliation happens here
- Weights stored in UserDefaults (persists across sessions)
- Confidence score combines all three metrics
- Drift detection automatic
- Works with cached data

---

#### File 2: `SwiftBolt/ViewModels/ValidationViewModel.swift`
**Purpose**: API polling + caching + state management

```swift
@MainActor
class ValidationViewModel: ObservableObject {
    @Published var validator: UnifiedValidator?
    @Published var isLoading = false
    @Published var error: String?
    @Published var isOffline = false
    @Published var lastSyncTime: Date?
    
    @Published var userWeights = ValidationWeights.load() {
        didSet {
            userWeights.save()
            recalculateIfNeeded()  // Instant UI update on weight change
        }
    }
    
    let symbol: String
    private var pollTimer: Timer?
    private let cacheDuration: TimeInterval = 5 * 60  // 5 minutes
    private let reachability: NetworkReachability
    private let apiClient: SupabaseClient
    
    func startPolling() {
        // Poll every 5 minutes
        pollTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            Task { await self?.fetchValidation() }
        }
        // Initial fetch
        Task { await fetchValidation() }
    }
    
    func stopPolling() {
        pollTimer?.invalidate()
    }
    
    func fetchValidation() async {
        // Check if online
        guard reachability.isConnected else {
            isOffline = true
            loadFromCache()
            return
        }
        
        isOffline = false
        isLoading = true
        error = nil
        
        do {
            // Call API endpoint
            let response = try await apiClient.call(
                "get-unified-validation",
                params: ["symbol": symbol]
            )
            
            // Create validator with user's weights
            var validator = UnifiedValidator(
                from: response,
                weights: userWeights
            )
            
            self.validator = validator
            self.lastSyncTime = Date()
            
            // Cache for offline access
            cacheValidator(validator)
            
            // Sync audit log (fire & forget, don't block UI)
            Task { await syncAuditLog(validator) }
            
        } catch {
            self.error = error.localizedDescription
            loadFromCache()  // Fall back to cache on error
        }
        
        isLoading = false
    }
    
    private func loadFromCache() {
        if let cached = UserDefaults.standard.data(forKey: "validationCache_\(symbol)"),
           let validator = try? JSONDecoder().decode(UnifiedValidator.self, from: cached) {
            self.validator = validator
            // Mark as stale
            self.error = "Showing cached data (updated \(validator.lastUpdatedAgo))"
        }
    }
    
    private func cacheValidator(_ validator: UnifiedValidator) {
        if let encoded = try? JSONEncoder().encode(validator) {
            UserDefaults.standard.set(encoded, forKey: "validationCache_\(symbol)")
        }
    }
    
    private func recalculateIfNeeded() {
        guard var validator = validator else { return }
        validator = UnifiedValidator(
            symbol: validator.symbol,
            backtestScore: validator.backtestScore,
            walkforwardScore: validator.walkforwardScore,
            liveScore: validator.liveScore,
            m15Signal: validator.m15Signal,
            h1Signal: validator.h1Signal,
            d1Signal: validator.d1Signal,
            timestamp: validator.timestamp,
            weights: userWeights  // Re-calculate with new weights
        )
        self.validator = validator
    }
    
    private func syncAuditLog(_ validator: UnifiedValidator) async {
        do {
            try await apiClient.call(
                "log-validation-audit",
                params: [
                    "symbol": validator.symbol,
                    "confidence": validator.confidence,
                    "weights": userWeights,
                    "timestamp": Int(validator.timestamp.timeIntervalSince1970)
                ]
            )
        } catch {
            // Fail silently—auditing is non-critical
            print("Failed to sync audit log: \(error)")
        }
    }
}
```

**Key Points**:
- Polls every 5 minutes
- Handles network failures gracefully
- Caches results for offline access
- Recalculates confidence when user changes weights (instant UI update)
- Syncs audit trail (non-blocking)

---

#### File 3: `SwiftBolt/Views/ValidationDashboardView.swift`
**Purpose**: UI display of validation results

(Refer to comprehensive design doc for full SwiftUI code)

**Key Elements**:
- Large confidence score badge (colored by confidence level)
- Score breakdown (3 columns: Backtest, Walkforward, Live)
- Multi-timeframe consensus display (M15, H1, D1 signals)
- Drift alert (automatic when performance degrades)
- Settings button (adjust weights)
- Offline indicator
- Last updated timestamp

---

## 🔄 Data Flow (App-Centric)

```
Backend (Provides Metrics)          Swift App (Reconciles & Displays)
═════════════════════════          ═════════════════════════════════

ML Orchestration                    Every 5 minutes:
Backtest scores ──┐                ┌──────────────────┐
Walkforward ─────┼───→ API Endpoint│ ValidationViewModel
Live predictions─┤   ├─────────────┤  • Polls endpoint
Multi-TF signals─┤   │             │  • Caches result
                 │   │             │  • Handles offline
                 └───│             └──────────────────┘
                     │                    │
                     │                    ▼
                     │             ┌──────────────────┐
                     │             │ UnifiedValidator
                     │             │ (On-Device Logic)
                     │             │ • Weighs scores
                     │             │ • Detects drift
                     │             │ • Reconciles TF
                     │             │ • Generates
                     │             │   confidence
                     │             └──────────────────┘
                     │                    │
                     │                    ▼
                     │             ┌──────────────────┐
                     │             │ ValidationDash
                     │             │ • Confidence
                     │             │ • Breakdown
                     │             │ • Consensus
                     │             │ • Drift alerts
                     │             │ • Settings
                     │             └──────────────────┘
                     │                    │
                     │ (sync audit)        │
                     │ (every 15min)       │
                     └────────────────────→│
                   Backend Audit Log

Result: Single source of truth (on-device)
        Validation logic in app (user controls it)
        Offline-capable
        Backend provides metrics only
        Audit trail for debugging
```

---

## 📋 File Structure Updates

```
SwiftBolt_ML/
├── backend/
│   └── supabase/
│       └── functions/
│           ├── get-unified-validation/  (NEW: Provides metrics)
│           │   └── index.ts
│           ├── log-validation-audit/    (NEW: Receives audit trail)
│           │   └── index.ts
│           └── sync-user-symbols/       (existing)
│
├── SwiftBolt/
│   ├── Models/
│   │   └── UnifiedValidator.swift       (NEW: Validation logic)
│   ├── ViewModels/
│   │   └── ValidationViewModel.swift    (NEW: Polling + caching)
│   └── Views/
│       └── ValidationDashboardView.swift (NEW: UI display)
│
└── docs/
    ├── SWIFTBOLT_APP_VALIDATOR_STRATEGY.md (THIS FILE)
    └── APP_VALIDATOR_GUIDE.md             (NEW: Detailed guide)
```

---

## ✅ Implementation Checklist

### Week 1 (This Week)
- [ ] Day 1: Seed symbols table (1 hour)
- [ ] Day 2-3: Build validation API endpoint (2 days)
  - [ ] Create `get-unified-validation` function
  - [ ] Create `log-validation-audit` function
  - [ ] Test endpoints manually
- [ ] Day 4-6: Build Swift validator module (3 days)
  - [ ] Create `UnifiedValidator.swift` model
  - [ ] Create `ValidationViewModel.swift` (polling + caching)
  - [ ] Create `ValidationDashboardView.swift` (UI)
  - [ ] Integrate into Dashboard tab
  - [ ] Test on simulator

### Week 2
- [ ] Polish Settings UI (adjust weights)
- [ ] Test offline mode
- [ ] Monitor audit logs from backend
- [ ] Deploy to TestFlight
- [ ] Gather user feedback

---

## 🎛️ Configuration Defaults (In App)

User can adjust these directly in Settings:

```swift
// Validation Weights (default)
backtesting: 40%
walkforward: 35%
live: 25%

// Drift Threshold (default)
15% divergence = alert triggered

// Timeframe Hierarchy (default)
Duration-based: D1 (50%) > H1 (30%) > M15 (20%)

// Cache Duration
5 minutes between API polls

// Offline Behavior
Show cached results + "Offline" badge
```

---

## 📊 Effort & Timeline

| Task | Effort | Value | Priority |
|------|--------|-------|----------|
| Fix symbols table | 1 hour | 🟢 High | NOW |
| Validation API Endpoint | 2 days | 🟢 High | THIS WEEK |
| Swift Validator Module | 3 days | 🟢 High | THIS WEEK |
| Consolidate scripts | 2 days | 🟡 Medium | NEXT WEEK |
| Options integration | 2 weeks | 🟢 High | MONTH 2 |
| **Total** | **~2 weeks** | | |

---

## 🚀 Why This Approach?

**Old (Backend-Centric)**
- Validator in Python backend
- One-size-fits-all logic
- Requires backend redeploy to adjust
- No offline support
- Dashboard shows confusing metrics

**New (App-Centric)** ✅
- Validator in Swift app
- User-configurable weights
- No backend redeploy needed
- Works offline (cached metrics)
- Clear, single confidence score
- Audit trail for debugging
- Faster UI updates
- Separation of concerns (backend = data, app = logic)

---

**Status**: Ready to implement. Start with Day 1 (seed symbols table)!
