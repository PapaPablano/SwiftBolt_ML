# Multi-Leg Options Strategy Documentation Index

## Quick Navigation

All multi-leg options documentation is organized in the `docs/features/` directory. Start here:

### Core Documentation

1. **[MULTI_LEG_OPTIONS_OVERVIEW.md](./MULTI_LEG_OPTIONS_OVERVIEW.md)** ⤵ START HERE
   - Strategy types and classifications (spreads, straddles, condors, etc.)
   - Supported strategies by type
   - Data model at 50,000 feet
   - User workflows and integration points
   - Best for: Understanding the domain

2. **[MULTI_LEG_DATA_MODEL.md](./MULTI_LEG_DATA_MODEL.md)** ⤵ FOR ARCHITECTS
   - Complete Postgres schema (7 tables)
   - TypeScript type definitions
   - Swift model definitions
   - Validation rules
   - Best for: Database setup, type generation

3. **[MULTI_LEG_ALERT_SYSTEM.md](./MULTI_LEG_ALERT_SYSTEM.md)** ⤵ FOR BACKEND DEVS
   - Alert types (8 categories)
   - Trigger conditions with pseudocode
   - Scheduled evaluation job (every 15 min)
   - User preferences configuration
   - Best for: Implementing alert evaluator

4. **[MULTI_LEG_PL_CALCULATOR.md](./MULTI_LEG_PL_CALCULATOR.md)** ⤵ FOR QUANT/BACKEND
   - P&L calculation formulas
   - Greeks aggregation
   - Black-Scholes implementation (Python + Swift)
   - Max risk/reward for each strategy type
   - Best for: P&L engine implementation

5. **[MULTI_LEG_IMPLEMENTATION_ROADMAP.md](./MULTI_LEG_IMPLEMENTATION_ROADMAP.md)** ⤵ FOR PM/LEADS
   - 8-week implementation plan
   - 6 phases with deliverables
   - File structure and tasks
   - Testing strategy
   - Risk mitigation
   - Best for: Project planning and execution

---

## Quick Reference

### Supported Strategy Types

**2-Leg Spreads**
- Bull Call Spread: Long ATM Call + Short OTM Call
- Bear Call Spread: Short ATM Call + Long OTM Call
- Bull Put Spread: Short ATM Put + Long OTM Put  
- Bear Put Spread: Long OTM Put + Short ATM Put

**Straddles & Strangles**
- Long Straddle: Long Call + Long Put (same strike)
- Short Straddle: Short Call + Short Put (same strike)
- Long Strangle: Long OTM Call + Long OTM Put
- Short Strangle: Short OTM Call + Short OTM Put

**Multi-Leg (3-4 legs)**
- Iron Condor: Bull Call Spread + Bull Put Spread (4 legs)
- Iron Butterfly: Sell ATM, Buy OTM both sides (4 legs)
- Call Ratio Backspread: Sell ATM Call, Buy OTM Calls (3+ legs)
- Put Ratio Backspread: Sell ATM Put, Buy OTM Puts (3+ legs)

**Time-Based**
- Calendar Spread: Same strike, different expirations
- Diagonal Spread: Different strikes AND expirations
- Butterfly Spread: Buy ATM, Sell x2 middle, Buy ATM (3 legs)

### Database Schema (Quick Reference)

```
options_strategies          Master strategy record
  ├─ id, user_id, name, strategy_type
  ├─ underlying_symbol_id, underlying_ticker
  ├─ status (open/closed/expired/rolled)
  ├─ net_premium (debit/credit)
  ├─ max_risk, max_reward, breakeven_points
  ├─ combined delta/gamma/theta/vega/rho
  ├─ forecast_id, forecast_alignment, forecast_confidence
  └─ total_pl, total_pl_pct, realized_pl

options_legs                Individual contracts in strategy
  ├─ id, strategy_id
  ├─ leg_number (1, 2, 3, 4)
  ├─ position_type (long/short), option_type (call/put)
  ├─ strike, expiry, dte_at_entry, current_dte
  ├─ entry_price, contracts, total_entry_cost
  ├─ current_price, current_value, unrealized_pl
  ├─ entry_delta/gamma/theta/vega, current_delta/gamma/theta/vega
  ├─ is_assigned, is_exercised
  └─ is_closed, exit_price, exit_timestamp, realized_pl

options_leg_entries         Average cost tracking (optional)
  ├─ id, leg_id
  ├─ entry_price, contracts, entry_timestamp
  └─ notes

options_multi_leg_alerts    Strategy-level alerts
  ├─ id, strategy_id, leg_id (nullable)
  ├─ alert_type (expiration_soon, strike_breached, forecast_flip, ...)
  ├─ severity (info/warning/critical)
  ├─ title, reason, details, suggested_action
  ├─ created_at, acknowledged_at, resolved_at
  └─ action_required

options_strategy_templates  Pre-built configs
  ├─ id, name, strategy_type
  ├─ leg_config (JSON blueprint)
  ├─ typical_max_risk, typical_max_reward
  ├─ market_condition (bullish/bearish/neutral/volatile)
  └─ is_system_template, is_public

options_strategy_metrics    Daily snapshots
  ├─ id, strategy_id, recorded_at
  ├─ underlying_price, total_value, total_pl
  ├─ delta/gamma/theta/vega snapshots
  └─ min_dte, alert_count, critical_alert_count

multi_leg_journal           Audit log
  ├─ id, strategy_id, leg_id (nullable)
  ├─ action (created/leg_added/price_updated/alert_generated/...)
  ├─ actor_user_id, actor_service
  ├─ changes (JSON)
  └─ created_at
```

### Key Formulas

**P&L Calculation**
```
Strategy P&L = Σ(Leg P&L)

Leg P&L = (Current Price - Entry Price) × 100 × Contracts × Position Sign
  where Position Sign = +1 for long, -1 for short

P&L % = P&L / |Entry Cost| × 100
```

**Greeks Aggregation**
```
Portfolio Greeks = Σ(Leg Greeks × Position Sign)
```

**Bull Call Spread Max Risk/Reward**
```
Net Debit = Long Call Premium - Short Call Premium
Max Loss = Net Debit
Max Profit = (Short Strike - Long Strike) - Net Debit
Breakeven = Long Strike + Net Debit
```

### Alert Types

| Type | Trigger | Severity | Action |
|------|---------|----------|--------|
| `expiration_soon` | DTE <= 3 | warning | Close or roll |
| `strike_breached` | Underlying within 1% of strike | critical | Monitor/close |
| `assignment_risk` | Short leg deep ITM + low DTE | critical | Close immediately |
| `forecast_flip` | Strategy thesis vs forecast mismatch | critical | Review/exit |
| `profit_target_hit` | P&L >= target % | warning | Take profit |
| `stop_loss_hit` | P&L <= stop loss % | critical | Close position |
| `volatility_spike` | IV > 2 std dev from mean | warning/info | Monitor |
| `vega_squeeze` | High IV impact on position | info | Let theta work |
| `theta_decay_benefit` | Short strategy earning $X/day | info | Monitor benefit |
| `gamma_risk` | Delta could swing >15% | warning | Rehedge if needed |

### Edge Functions to Implement

```
/functions/multi-leg/
  ├─ create-strategy          POST   Create new strategy
  ├─ list-strategies           GET    List with filters
  ├─ get-strategy-detail       GET    Full strategy + alerts
  ├─ update-strategy           PATCH  Update metadata
  ├─ close-leg                 POST   Close individual leg
  ├─ calculate-pl              POST   Calculate P&L snapshot
  ├─ evaluate-strategies       POST   Scheduled job (15 min)
  ├─ acknowledge-alert         POST   Mark alert as seen
  └─ get-strategy-templates    GET    List templates
```

### SwiftUI Views to Build

```
MultiLegStrategyListView
  ├─ Show open strategies
  ├─ Filter by status/type/underlying
  ├─ Quick actions (create, detail, delete)
  └─ Sort by P&L, DTE, creation date

CreateStrategyWizardView
  ├─ Step 1: Select strategy type
  ├─ Step 2: Select underlying
  ├─ Step 3: Configure legs (template or manual)
  ├─ Step 4: Review P&L profile
  └─ Step 5: Confirm & create

StrategyDetailView
  ├─ Payoff diagram (real-time)
  ├─ Leg table (current prices, P&L)
  ├─ Greeks summary
  ├─ Alert panel
  └─ Actions (close leg, roll, close all)

PayoffDiagramView
  ├─ Draw profit zones
  ├─ Show current underlying price
  ├─ Mark breakeven points
  └─ Display max risk/reward lines

MultiLegAlertPanelView
  ├─ Sort by severity
  ├─ Show action suggestions
  ├─ Acknowledge alerts
  └─ Link to detailed alert view
```

### Backend Services to Implement

```python
# Core services
MultiLegPLCalculator()          # P&L calculations
StrategyValidator()             # Input validation
AlertEvaluator()                # Alert trigger logic
StrategyRepository()            # CRUD operations
GreeksCalculator()              # Black-Scholes

# Jobs
evaluate_all_strategies()       # Every 15 min
rebalance_suggestions()         # Daily at market open
record_daily_metrics()          # Daily close

# Models
MultiLegStrategy
OptionsLeg
OptionsLegEntry
MultiLegAlert
StrategyTemplate
```

---

## Implementation Checklist

### Phase 1: Foundation
- [ ] Schema migration created and tested
- [ ] RLS policies verified
- [ ] Indexes created
- [ ] TypeScript types generated from schema
- [ ] Swift models compiled
- [ ] Documentation reviewed

### Phase 2: Backend
- [ ] P&L calculator implemented (8 strategy types)
- [ ] Strategy validator implemented
- [ ] Alert evaluator job implemented
- [ ] Greeks calculator (Black-Scholes) implemented
- [ ] Unit tests written (>90% coverage)
- [ ] Integration tests for workflows

### Phase 3: Edge Functions
- [ ] All 8 edge functions deployed
- [ ] Authentication verified
- [ ] Error handling implemented
- [ ] Latency verified (<2s)

### Phase 4: Frontend
- [ ] Strategy list view built
- [ ] Create wizard built (5 steps)
- [ ] Strategy detail view built
- [ ] Payoff diagram renders correctly
- [ ] Alert panel displays alerts
- [ ] ViewModels handle state

### Phase 5: Integration
- [ ] Options ranker integration
- [ ] ML forecast integration
- [ ] Watchlist integration
- [ ] Dashboard widget integration
- [ ] E2E tests pass

### Phase 6: Polish
- [ ] Performance optimized (<500ms list)
- [ ] Caching implemented
- [ ] Error recovery added
- [ ] User documentation written
- [ ] Monitoring/alerts configured

---

## Common Questions

### Q: Why separate legs table instead of storing legs in JSON?
**A:** Separate table enables:
- Direct querying ("find all short call legs")
- Efficient indexing on expiry, strike
- Easy cost averaging with entries table
- Better RLS granularity
- Normalized structure for analytics

### Q: How do I calculate P&L for a bull call spread?
**A:** 
```
Total P&L = (Long Call current - Long Call entry) + (Short Call entry - Short Call current)
           = Max(underlying - strike1, 0) - entry_cost - Max(underlying - strike2, 0) + short_credit
```

### Q: When should alerts be generated?
**A:** Every 15 minutes via the `evaluate_strategies` job, which:
1. Fetches current prices from options_ranker
2. Calculates current P&L and Greeks
3. Checks all 10 alert triggers
4. Creates new alerts only if not already unresolved
5. Updates strategy state and metrics

### Q: Can strategies be partially closed?
**A:** Yes, individual legs can be closed. The strategy itself remains open until all legs are closed or expired.

### Q: How is theta displayed?
**A:** Theta is daily decay in dollars (Greeks theta already scaled to daily). For a strategy with $50/day theta, it gains $50 every 24 hours from time decay.

---

## Related Documentation

- [Options Chain Implementation](../OPTIONS_CHAIN_IMPLEMENTATION.md)
- [Options Ranker Setup](../OPTIONS_RANKER_SETUP.md)
- [Options Watchlist Plan](../../options_watchlist.md)
- [Master Blueprint - Options](../master_blueprint.md#42-options-ranker)
- [ML Forecasts](../master_blueprint.md#ml-powered-analytics)

---

## File Locations

```
Docs: /docs/features/MULTI_LEG_*.md

Backend:
  /backend/services/
  /backend/jobs/
  /backend/tests/

Frontend:
  /client-macos/SwiftBoltML/Views/MultiLeg/
  /client-macos/SwiftBoltML/ViewModels/MultiLeg/
  /client-macos/SwiftBoltML/Services/MultiLeg/
  /client-macos/SwiftBoltMLTests/MultiLeg/

Database:
  /supabase/migrations/
  /supabase/functions/multi-leg/
```

---

## Questions or Issues?

- Review the specific doc (Overview, Data Model, Alert System, P&L Calc, or Roadmap)
- Check implementation examples in respective docs
- Reference test files for working code
- Consult the roadmap for timeline and dependencies

**Last Updated:** January 20, 2026
