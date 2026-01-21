# Multi-Leg Options Implementation Roadmap

## Overview

This document provides the complete implementation plan for multi-leg options strategy support in SwiftBolt ML, including phases, dependencies, and integration points.

## Architecture Summary

```
┌────────────────────────────────┐
│        MULTI-LEG OPTIONS ARCHITECTURE               │
├────────────────────────────────┤
│                                                    │
│  DATABASE LAYER (Supabase)                        │
│  ├─ options_strategies (master)                  │
│  ├─ options_legs (individual contracts)          │
│  ├─ options_leg_entries (cost averaging)        │
│  ├─ options_multi_leg_alerts                    │
│  ├─ options_strategy_templates                  │
│  ├─ options_strategy_metrics (snapshots)        │
│  ├─ multi_leg_journal (audit)                   │
│  ├─ user_alert_preferences                      │
│                                                    │
├────────────────────────────────┤
│                                                    │
│  BACKEND LAYER (Python)                           │
│  ├─ pl_calculator.py                             │
│  │   ├─ SingleLegPL                               │
│  │   ├─ MultiLegPL                               │
│  │   ├─ GreeksAggregation                       │
│  │   └─ MaxRiskRewardCalc                        │
│  ├─ strategy_validator.py                        │
│  ├─ alert_evaluator.py                           │
│  ├─ strategy_repository.py                       │
│  ├─ strategy_templates.py                        │
│                                                    │
├────────────────────────────────┤
│                                                    │
│  EDGE FUNCTIONS (Supabase)                        │
│  ├─ /functions/create-strategy                  │
│  ├─ /functions/get-strategy-detail               │
│  ├─ /functions/update-strategy                  │
│  ├─ /functions/close-leg                         │
│  ├─ /functions/list-strategies                  │
│  ├─ /functions/evaluate-strategies (job)         │
│  ├─ /functions/calculate-pl                      │
│                                                    │
├────────────────────────────────┤
│                                                    │
│  FRONTEND LAYER (SwiftUI)                         │
│  ├─ MultiLegStrategyListView                     │
│  ├─ CreateStrategyView                           │
│  ├─ StrategyDetailView                           │
│  ├─ PayoffDiagramView                            │
│  ├─ AlertPanelView                               │
│  ├─ StrategyViewModels                           │
│                                                    │
└────────────────────────────────┘
```

## Phase 1: Foundation (Week 1-2)

### Deliverables

- [x] Database schema (see MULTI_LEG_DATA_MODEL.md)
- [x] TypeScript types generated
- [x] Documentation completed
- [ ] Schema migration created
- [ ] RLS policies applied
- [ ] Initial indexes created

### Tasks

```sql
-- 1. Create migration file
migrations/20260120_001_multi_leg_foundation.sql

-- 2. Execute all schema creation (from MULTI_LEG_DATA_MODEL.md)

-- 3. Verify RLS policies
SELECT * FROM pg_policies WHERE schemaname = 'public';

-- 4. Test indexes
EXPLAIN ANALYZE SELECT * FROM options_strategies 
WHERE user_id = 'test-user' AND status = 'open';
```

### Testing

```python
# tests/test_multi_leg_schema.py

import pytest
from supabase import create_client


async def test_schema_exists():
    """Verify all tables are created."""
    tables = [
        'options_strategies',
        'options_legs',
        'options_leg_entries',
        'options_multi_leg_alerts',
        'options_strategy_templates',
        'options_strategy_metrics'
    ]
    
    for table in tables:
        result = await db.query(
            f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table}'"
        )
        assert len(result) > 0, f"Table {table} not found"


async def test_rls_policies():
    """Verify RLS policies prevent cross-user access."""
    # Create strategy as user A
    strategy_a = await create_strategy(user_id='user-a', name='Test Strategy')
    
    # Try to access as user B (should fail)
    # ... this requires JWT token for user B
    
    # Verify user A can access
    result = await get_strategy(strategy_id=strategy_a['id'], user_id='user-a')
    assert result is not None
```

## Phase 2: Backend Services (Week 3-4)

### Deliverables

- [ ] P&L calculator implemented
- [ ] Strategy validator implemented
- [ ] Alert evaluator job implemented
- [ ] Edge functions deployed
- [ ] Unit tests (>90% coverage)

### Backend Files

```
backend/
├─ services/
│  ├─ pl_calculator.py          # P&L calculations
│  ├─ strategy_validator.py     # Input validation
│  ├─ alert_evaluator.py        # Alert triggers
│  ├─ strategy_repository.py    # CRUD operations
│  ├─ strategy_templates.py     # Template management
│  ├─ greeks_calculator.py      # Black-Scholes
│  └─ pl_snapshot_recorder.py   # Metrics storage
├─ jobs/
│  ├─ evaluate_strategies.py    # Scheduled evaluation
│  └─ rebalance_suggestions.py  # Daily suggestions
├─ models/
│  ├─ strategy_models.py
│  └─ alert_models.py
├─ tests/
│  ├─ test_pl_calculator.py
│  ├─ test_validator.py
│  ├─ test_alert_evaluator.py
│  └─ test_greeks.py
```

### Implementation Priority

1. **P&L Calculator** (highest priority)
   ```python
   # backend/services/pl_calculator.py
   class MultiLegPLCalculator:
       def calculate_strategy_pl(strategy, underlying_price) -> PLSnapshot
       def calculate_leg_pl(leg, underlying_price) -> LegPLSnapshot
       def calculate_max_risk_reward() -> Tuple[Decimal, Decimal, List[Decimal]]
   ```

2. **Strategy Validator**
   ```python
   # backend/services/strategy_validator.py
   def validate_creation(data) -> List[str]  # Returns errors
   def validate_leg_update(leg) -> List[str]
   def validate_leg_closure(leg) -> List[str]
   ```

3. **Alert Evaluator** (uses P&L Calculator)
   ```python
   # backend/jobs/evaluate_strategies.py
   async def evaluate_all_strategies()
   async def evaluate_single_strategy(strategy)
   ```

4. **Greeks Calculator** (Black-Scholes implementation)
   ```python
   # backend/services/greeks_calculator.py
   def calculate_option_greeks(spot, strike, dte, iv) -> Dict[Greeks]
   ```

### Testing Framework

```bash
# Run backend tests
pytest tests/test_multi_leg_*.py -v --cov=services --cov-report=html

# Minimum coverage: 90%
```

## Phase 3: Edge Functions (Week 4)

### Deliverables

- [ ] CRUD edge functions
- [ ] P&L calculation endpoint
- [ ] Alert generation endpoint
- [ ] List strategies endpoint (with filtering)

### Edge Functions to Create

```typescript
// supabase/functions/multi-leg/create-strategy/index.ts
export default async (req: Request) => {
  // Input validation
  // Create strategy + legs in transaction
  // Calculate max risk/reward
  // Initialize alerts
  // Return strategy record
}

// supabase/functions/multi-leg/list-strategies/index.ts
export default async (req: Request) => {
  // Filter by status, underlying, strategy type
  // Join with latest alerts
  // Calculate current P&L
  // Return paginated list
}

// supabase/functions/multi-leg/calculate-pl/index.ts
export default async (req: Request) => {
  // Input: strategy_id, current_prices
  // Calculate P&L per leg and total
  // Calculate Greeks
  // Return snapshot
}

// supabase/functions/multi-leg/evaluate-strategies/index.ts (scheduled job)
export default async (req: Request) => {
  // Fetch all open strategies
  // Evaluate against alerts
  // Generate new alerts
  // Update strategy state
}
```

## Phase 4: Frontend Views (Week 5-6)

### Deliverables

- [ ] Strategy list view
- [ ] Create strategy wizard
- [ ] Strategy detail view with payoff diagram
- [ ] Alert panel
- [ ] ViewModels with state management
- [ ] Integration tests

### SwiftUI Views

```swift
// client-macos/SwiftBoltML/Views/MultiLeg/

// 1. List view
MultiLegStrategyListView
  - Shows open strategies
  - Filters: status, underlying, strategy type
  - Quick actions: create, view detail

// 2. Create wizard
CreateStrategyWizardView
  - Step 1: Select type
  - Step 2: Select underlying
  - Step 3: Configure legs (from template or manual)
  - Step 4: Review P&L profile
  - Step 5: Confirm entry

// 3. Detail view
StrategyDetailView
  - Payoff diagram (real-time)
  - Current P&L per leg + total
  - Greeks summary
  - Alert panel
  - Actions: close leg, roll, close all

// 4. Alert panel
MultiLegAlertPanelView
  - Shows critical alerts first
  - Collapse/expand by severity
  - Quick action buttons
```

### ViewModels

```swift
class StrategyListViewModel: ObservableObject {
    @Published var strategies: [MultiLegStrategy] = []
    @Published var isLoading = false
    @Published var selectedFilter: StrategyFilter = .all
    
    func loadStrategies() async
    func deleteStrategy(_ id: UUID) async
}

class StrategyDetailViewModel: ObservableObject {
    @Published var strategy: MultiLegStrategy
    @Published var plSnapshot: StrategyPLSnapshot?
    @Published var alerts: [MultiLegAlert] = []
    @Published var isUpdating = false
    
    func loadDetail() async
    func updatePrices() async
    func closeLeg(_ legId: UUID, exitPrice: Decimal) async
    func acknowledgeAlert(_ alertId: UUID) async
}

class CreateStrategyViewModel: ObservableObject {
    @Published var selectedType: StrategyType = .bullCallSpread
    @Published var underlying: Symbol?
    @Published var legs: [CreateLegInput] = []
    @Published var maxRisk: Decimal = 0
    @Published var maxReward: Decimal = 0
    
    func selectTemplate(_ template: StrategyTemplate) async
    func updateLeg(_ index: Int, strike: Decimal, price: Decimal) async
    func createStrategy() async
}
```

## Phase 5: Integration & Testing (Week 7)

### Integration Points

1. **With Options Ranker**
   - Pre-populate leg prices from ranker
   - Update legs with latest prices every 15 min
   - Link to ranker for historical data

2. **With ML Forecasts**
   - Attach forecast_id to strategy
   - Check alignment on eval job
   - Surface forecast misalignment alerts

3. **With Watchlist**
   - Add multi-leg strategies to watchlist
   - Show strategy summary badge
   - Link to strategy detail from watchlist

4. **With Dashboard**
   - Add multi-leg widget
   - Show top alerts
   - Quick access to strategies

### E2E Test Suite

```swift
// client-macos/SwiftBoltMLTests/MultiLegE2ETests.swift

func testCreateAndTrackStrategy() async {
    // 1. Create bull call spread
    let strategy = await createStrategy(
        type: .bullCallSpread,
        underlying: "AAPL",
        longStrike: 150,
        shortStrike: 155,
        expiry: Date().addingTimeInterval(30 * 86400)  // 30 DTE
    )
    
    // 2. Verify strategy created
    XCTAssertNotNil(strategy.id)
    XCTAssertEqual(strategy.status, .open)
    
    // 3. Simulate price update
    await updateOptionPrices([
        (legId: strategy.legs[0].id, price: 2.50),
        (legId: strategy.legs[1].id, price: 0.50)
    ])
    
    // 4. Verify P&L calculated
    let plSnapshot = await calculatePL(strategy.id)
    XCTAssertGreaterThan(plSnapshot.totalPL, 0)  // Profit
    
    // 5. Verify alerts
    let alerts = await fetchAlerts(strategy.id)
    // Should have no alerts initially
    XCTAssertEqual(alerts.count, 0)
    
    // 6. Close leg
    await closeLeg(strategy.legs[0].id, exitPrice: 2.25)
    
    // 7. Verify leg closed
    let updatedStrategy = await getStrategy(strategy.id)
    XCTAssertTrue(updatedStrategy.legs[0].isClosed)
}
```

## Phase 6: Performance & Polish (Week 8)

### Optimization Tasks

1. **Database**
   - Profile slow queries
   - Add missing indexes
   - Optimize RLS policies
   - Consider materialized views for dashboards

2. **Backend**
   - Batch strategy evaluation (not one-by-one)
   - Cache option prices from ranker
   - Implement Redis for alert dedup
   - Use connection pooling

3. **Frontend**
   - Debounce price updates
   - Lazy-load strategy details
   - Memoize calculations
   - Optimize redraws

### Monitoring & Alerting

```yaml
# monitoring/multi_leg_metrics.yml

metrics:
  - strategy_creation_latency (p50, p95, p99)
  - alert_evaluation_latency
  - pl_calculation_latency
  - api_error_rate
  - database_query_time
  - cache_hit_rate

alerts:
  - alert_evaluation > 30s (critical)
  - api_error_rate > 5% (warning)
  - strategy_list query > 2s (warning)
```

## Dependencies & Prerequisites

### Before Phase 1

- [x] Options chain implementation
- [x] Options ranker service
- [x] ML forecast service
- [x] Supabase project with auth

### Before Phase 3

- [x] Python backend setup
- [x] Edge functions environment
- [x] Service-to-service auth

### Before Phase 4

- [x] SwiftUI base components
- [x] MVVM architecture established
- [x] Supabase iOS SDK integrated

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Complexity of P&L for complex strategies | Thorough unit tests, real market data validation |
| Greeks calculation accuracy | Use established Black-Scholes lib, compare with ranker |
| Real-time alert spam | Batch alerts, dedup logic, user preferences |
| Data consistency across services | Transactions, audit journal, retry logic |
| Performance under load | Caching, batch processing, index optimization |

## Timeline

```
Week 1-2: Foundation (Schema, types, docs)
Week 3-4: Backend (P&L, validation, alerts)
Week 4:   Edge functions
Week 5-6: Frontend (Views, state management)
Week 7:   Integration & E2E testing
Week 8:   Polish, optimization, monitoring

TARGET: MVP Launch = End of Week 7
```

## Success Metrics

- ✅ All unit tests pass (>90% coverage)
- ✅ E2E tests for create/track/close workflow
- ✅ P&L accuracy within 0.01% vs manual calc
- ✅ Alert evaluation < 5s per strategy
- ✅ UI responsive (< 500ms for strategy list)
- ✅ Zero data integrity issues in audit log
- ✅ Documentation complete with examples

## Next Steps

1. **Approve roadmap** and secure resources
2. **Create Jira tickets** for each phase
3. **Set up development environment** (branch, CI/CD)
4. **Begin Phase 1** (schema migration)

---

## References

- [Multi-Leg Options Overview](./MULTI_LEG_OPTIONS_OVERVIEW.md)
- [Data Model Spec](./MULTI_LEG_DATA_MODEL.md)
- [Alert System Design](./MULTI_LEG_ALERT_SYSTEM.md)
- [P&L Calculator](./MULTI_LEG_PL_CALCULATOR.md)
