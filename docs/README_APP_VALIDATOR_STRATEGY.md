# SwiftBolt_ML: Updated Validation Strategy

**Status**: Documentation Updated  
**Date**: January 21, 2026  
**Change**: Validator moved from backend to Swift app (on-device)

---

## 📄 Documentation Updated

Your local docs have been updated to reflect the **app-centric validation architecture**:

### Files Created

1. **`SWIFTBOLT_APP_VALIDATOR_STRATEGY.md`** (This Week's Plan)
   - Complete strategy overview
   - Architecture diagrams
   - File structure changes
   - Implementation timeline (2 weeks total)
   - Decision framework
   - Why this approach

2. **`APP_VALIDATOR_IMPLEMENTATION_GUIDE.md`** (Step-by-Step Code)
   - Full code for API endpoints (TypeScript)
   - Full code for Swift models (Swift)
   - Full code for ViewModel (Swift)
   - Full code for UI views (SwiftUI)
   - Integration instructions
   - Testing checklist

3. **`APP_VALIDATOR_QUICK_START.md`** (Quick Reference)
   - Daily tasks (copy-paste ready)
   - Architecture at a glance
   - File structure changes
   - Key components
   - Default configuration
   - Testing shortcuts
   - Effort summary

---

## 📊 What Changed?

### Old Approach (Backend-Centric)
```
Backend:
  - ml/src/validation/unified_framework.py
  - One-size-fits-all reconciliation logic
  - Requires redeploy to adjust weights
  - Dashboard shows raw metrics
  - No offline support
```

### New Approach (App-Centric) ✅
```
Backend:
  - backend/supabase/functions/get-unified-validation/ (provides metrics)
  - backend/supabase/functions/log-validation-audit/ (receives audit trail)
  - Data provider only (no reconciliation logic)

App:
  - SwiftBolt/Models/UnifiedValidator.swift (reconciliation logic)
  - SwiftBolt/ViewModels/ValidationViewModel.swift (polling + caching)
  - SwiftBolt/Views/ValidationDashboardView.swift (UI display)
  - User-configurable weights
  - Works offline
  - Instant UI updates
```

---

## 🚀 Key Benefits

| Aspect | Old | New |
|--------|-----|-----|
| **Where logic runs** | Backend (Python) | App (Swift) |
| **User control** | Fixed weights | Adjustable in Settings |
| **Redeploy needed?** | Yes (for config changes) | No |
| **Offline support** | No | Yes (cached metrics) |
| **UI updates** | Slow (backend dependent) | Instant (on-device) |
| **Separation of concerns** | Mixed | Clear (backend=data, app=logic) |
| **Audit trail** | Not recorded | Synced to backend |

---

## 💼 Quick Timeline

### This Week (6 days)
```
Day 1:   Seed symbols table              (1 hour)
Day 2-3: Build validation API endpoint   (2 days)
Day 4-6: Build Swift validator module    (3 days)
         Total: ~2 weeks to full deployment
```

### Next Week
- Polish Settings UI
- Test offline mode
- Deploy to TestFlight
- Gather user feedback

---

## 🔍 What to Read First

### Quick Overview (10 min)
1. This file (README)
2. `APP_VALIDATOR_QUICK_START.md` (quick reference)

### Full Understanding (1 hour)
1. `SWIFTBOLT_APP_VALIDATOR_STRATEGY.md` (complete strategy)
2. Data flow diagrams in strategy doc
3. Decision framework section

### Implementation (6 days)
1. `APP_VALIDATOR_IMPLEMENTATION_GUIDE.md` (code + instructions)
2. Follow daily tasks in Quick Start
3. Copy-paste code from Implementation Guide
4. Test each day before moving on

---

## ✅ Implementation Checklist

### Before You Start
- [ ] Read SWIFTBOLT_APP_VALIDATOR_STRATEGY.md
- [ ] Read APP_VALIDATOR_QUICK_START.md

### Week 1
- [ ] Day 1: Seed symbols table
- [ ] Day 2-3: Build API endpoints
  - [ ] Create `get-unified-validation` function
  - [ ] Create `log-validation-audit` function
  - [ ] Test with curl
- [ ] Day 4-6: Build Swift module
  - [ ] Create `UnifiedValidator.swift`
  - [ ] Create `ValidationViewModel.swift`
  - [ ] Create `ValidationDashboardView.swift`
  - [ ] Integrate into Dashboard
  - [ ] Test on simulator

### Week 2
- [ ] Polish Settings UI
- [ ] Test offline mode
- [ ] Monitor audit logs
- [ ] Deploy to TestFlight

---

## 🔗 File Locations

**Strategy Documents**:
```
docs/SWIFTBOLT_APP_VALIDATOR_STRATEGY.md    (complete overview)
docs/APP_VALIDATOR_IMPLEMENTATION_GUIDE.md  (step-by-step code)
docs/APP_VALIDATOR_QUICK_START.md          (quick reference)
docs/README_APP_VALIDATOR_STRATEGY.md      (this file)
```

**Code Files** (to be created):
```
backend/supabase/functions/
  get-unified-validation/index.ts
  log-validation-audit/index.ts

SwiftBolt/Models/
  UnifiedValidator.swift

SwiftBolt/ViewModels/
  ValidationViewModel.swift

SwiftBolt/Views/
  ValidationDashboardView.swift
```

---

## 📝 Decision Framework

The strategy doc includes a **Decision Framework** with user-configurable options:

| Decision | Default | Adjustable? |
|----------|---------|------------|
| Backtest weight | 40% | ✅ Yes (in Settings) |
| Walkforward weight | 35% | ✅ Yes (in Settings) |
| Live weight | 25% | ✅ Yes (in Settings) |
| Drift threshold | 15% | ✅ Yes (in Settings) |
| Timeframe hierarchy | Duration-based (D1>H1>M15) | ✅ Yes (in Settings) |
| Cache duration | 5 minutes | ❌ In code (can change) |
| Audit logging | Every 15 min | ❌ In code (can change) |

---

## 🔄 Architecture Summary

```
Backend (Data Provider)           App (Intelligence Layer)      User (Control)
════════════════           ═══════════════════      ════════════

ML Orchestration                 Every 5 min:                 Sees:
Computes:
 - Backtest scores ───→ API Endpoint  ──→ Poll data    ──→ Single confidence
 - Walkforward scores        (metrics only)        score
 - Live predictions
 - Multi-TF signals                         ──→ Apply weights  ──→ Breakdown by
                                ────────── Detect drift  ──→ timeframe
                            UnifiedValidator
                            (on-device calc)
                                ────────── Cache locally ──→ Offline support
                                ────────── Sync audit  ──→ Adjust weights
                                (optional)         in Settings
```

---

## 🚅 Code Organization

**SwiftBolt Models**:
- `UnifiedValidator` - Stores scores, applies weights, calculates confidence, detects drift
- `ValidationWeights` - User-configurable weights, persisted to UserDefaults
- `Signal` - BULLISH/BEARISH/NEUTRAL

**SwiftBolt ViewModels**:
- `ValidationViewModel` - Polls API, caches results, handles network, syncs audit

**SwiftBolt Views**:
- `ValidationDashboardView` - Shows confidence badge, breakdown, consensus, alerts
- `ValidationSettingsView` - Adjust weights

---

## 🔊 Questions?

**Q: Why app-centric instead of backend?**
A: User controls logic, no redeploys, works offline, instant UI updates, clear separation.

**Q: What if network is unavailable?**
A: App shows cached results with "Offline" badge. Syncs audit when connection returns.

**Q: Can weights change after deployment?**
A: Yes! User changes them in Settings. Persisted to UserDefaults. Instant recalculation.

**Q: How often does it poll?**
A: Every 5 minutes. Can be adjusted in code if needed.

**Q: Is audit logging critical?**
A: No. Fails silently. Used for debugging why app showed different signals.

**Q: Can I adjust default weights?**
A: Yes. In `ValidationWeights()` struct definition. Defaults are 40/35/25.

---

## 🚀 Next Steps

1. **Read** `SWIFTBOLT_APP_VALIDATOR_STRATEGY.md` (understand strategy)
2. **Read** `APP_VALIDATOR_QUICK_START.md` (understand daily tasks)
3. **Day 1**: Execute seed-symbols task
4. **Days 2-3**: Build API endpoint (follow Implementation Guide)
5. **Days 4-6**: Build Swift module (follow Implementation Guide)
6. **Week 2**: Polish & test

---

**Status**: Documentation complete. Ready to implement!
