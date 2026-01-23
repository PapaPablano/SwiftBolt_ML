# Entry/Exit Ranking System - Implementation Status
## January 23, 2026

## ✅ Phase 1: Core Infrastructure - COMPLETED

### Python Backend ✅
- **RankingMode Enum**: Added with ENTRY, EXIT, MONITOR modes
- **Weight Configurations**: 
  - Entry: Value 40%, Catalyst 35%, Greeks 25%
  - Exit: Profit 50%, Deterioration 30%, Time 20%
  - Monitor: Momentum 40%, Value 35%, Greeks 25%

### New Scoring Methods ✅
1. **IV Percentile Calculation** - More robust than IV rank
2. **IV Historical Discount** - Contract vs own history
3. **Volume Surge Detection** - Ratio vs absolute (1× to 4×+ scoring)
4. **Catalyst Scoring** - Price momentum + volume surge + OI build
5. **Entry Value Scoring** - IV percentile 40%, IV discount 30%, spread 30%
6. **Profit Protection** - P&L%, IV expansion, price target hit
7. **Deterioration Detection** - Momentum decay, volume drying up, OI stalling
8. **Time Urgency** - DTE urgency + theta burn rate

### Main Ranking Methods ✅
- `_rank_for_entry()` - Calculates entry_rank (0-100)
- `_rank_for_exit()` - Calculates exit_rank (0-100)
- `rank_options()` - Updated to support mode parameter

### Swift Models ✅
- **RankingMode Enum**: Added with display names, descriptions, icons
- **OptionRank Model**: Updated with:
  - `entryRank: Double?`
  - `exitRank: Double?`
  - `rankingMode: RankingMode?`
  - Component scores for each mode
  - `rank(for:)` method to get mode-specific rank

---

## 🚧 Phase 2: Backend Integration - IN PROGRESS

### Remaining Tasks

#### TypeScript Backend 📝
- [ ] Update `trigger-ranking-job/index.ts` to accept mode parameter
- [ ] Update `options-rankings/index.ts` API endpoint
- [ ] Pass mode to Python ML service

#### Python Job Runner 📝
- [ ] Update `options_ranking_job.py` to support modes
- [ ] Save entry_rank and exit_rank to database
- [ ] Add entry_data parameter handling for EXIT mode

#### Database Schema 📝
- [ ] Add `entry_rank` NUMERIC column to `options_ranks`
- [ ] Add `exit_rank` NUMERIC column to `options_ranks`
- [ ] Add `ranking_mode` TEXT column to `options_ranks`
- [ ] Add component score columns (catalyst_score, profit_protection_score, etc.)

---

## 🎨 Phase 3: Frontend - PENDING

### Mode Selector UI 📝
**Location**: `OptionsChainView` or `OptionsRankerView`

```swift
@State private var rankingMode: RankingMode = .entry

Picker("Ranking Mode", selection: $rankingMode) {
    ForEach(RankingMode.allCases) { mode in
        Label(mode.displayName, systemImage: mode.icon)
            .tag(mode)
    }
}
.pickerStyle(.segmented)
.onChange(of: rankingMode) { _, newMode in
    Task {
        await appViewModel.fetchRankings(mode: newMode)
    }
}
```

### Contract Workbench Updates 📝
**Overview Tab**: Show all three ranks side-by-side

```swift
HStack(spacing: 20) {
    VStack {
        Image(systemName: "arrow.down.circle.fill")
            .foregroundColor(.green)
        Text("Entry")
            .font(.caption)
        Text("\(Int(rank.entryRank ?? 0))")
            .font(.title)
    }
    
    VStack {
        Image(systemName: "arrow.up.circle.fill")
            .foregroundColor(.red)
        Text("Exit")
            .font(.caption)
        Text("\(Int(rank.exitRank ?? 0))")
            .font(.title)
    }
    
    VStack {
        Image(systemName: "chart.bar.fill")
            .foregroundColor(.blue)
        Text("Monitor")
            .font(.caption)
        Text("\(Int(rank.compositeRank ?? 0))")
            .font(.title)
    }
}
```

**Why Ranked Tab**: Mode-specific breakdown

```swift
switch appViewModel.selectedContractState.rankingMode {
case .entry:
    // Show: Entry Value 40%, Catalyst 35%, Greeks 25%
    ContributionRow(label: "Entry Value", score: rank.entryValueScore ?? 0, weight: 0.40, color: .blue)
    ContributionRow(label: "Catalyst", score: rank.catalystScore ?? 0, weight: 0.35, color: .green)
    ContributionRow(label: "Greeks", score: rank.greeksScore ?? 0, weight: 0.25, color: .orange)
    
case .exit:
    // Show: Profit 50%, Deterioration 30%, Time 20%
    ContributionRow(label: "Profit Protection", score: rank.profitProtectionScore ?? 0, weight: 0.50, color: .green)
    ContributionRow(label: "Deterioration", score: rank.deteriorationScore ?? 0, weight: 0.30, color: .orange)
    ContributionRow(label: "Time Urgency", score: rank.timeUrgencyScore ?? 0, weight: 0.20, color: .red)
    
case .monitor:
    // Show: Momentum 40%, Value 35%, Greeks 25%
    ContributionRow(label: "Momentum", score: rank.momentumScore ?? 0, weight: 0.40, color: .green)
    ContributionRow(label: "Value", score: rank.valueScore ?? 0, weight: 0.35, color: .blue)
    ContributionRow(label: "Greeks", score: rank.greeksScore ?? 0, weight: 0.25, color: .orange)
}
```

### APIClient Updates 📝
```swift
func fetchOptionsRankings(
    symbol: String,
    mode: RankingMode = .monitor
) async throws -> OptionsRankingsResponse {
    var components = URLComponents(string: "\(baseURL)/options-rankings")!
    components.queryItems = [
        URLQueryItem(name: "symbol", value: symbol),
        URLQueryItem(name: "mode", value: mode.rawValue)
    ]
    // ... rest of implementation
}
```

---

## 🧪 Phase 4: Testing - PENDING

### Validation Tests 📝
Create `ml/tests/test_entry_exit_ranking.py`:

```python
def test_entry_mode_weights():
    """Verify entry mode uses correct weights."""
    ranker = OptionsMomentumRanker()
    # Test that entry_rank = value×0.40 + catalyst×0.35 + greeks×0.25

def test_exit_mode_weights():
    """Verify exit mode uses correct weights."""
    # Test that exit_rank = profit×0.50 + deterioration×0.30 + time×0.20

def test_volume_surge_detection():
    """Test volume surge ratio calculation."""
    # Test 1× = 50, 2× = 75, 4× = 100

def test_profit_protection_thresholds():
    """Test P&L thresholds."""
    # Test <10%: 20, 25%: 60, 50%: 80, 100%: 95

def test_time_urgency_by_dte():
    """Test DTE urgency scoring."""
    # Test >30: 20, 14-30: 40, 7-14: 70, <7: 95
```

### Integration Tests 📝
- [ ] Test AAPL ranking in all three modes
- [ ] Verify entry_rank emphasizes low IV + volume surge
- [ ] Verify exit_rank increases with profit >50%
- [ ] Verify exit_rank increases near expiration
- [ ] Test mode switching in frontend

---

## 📊 Expected Results

### Entry Mode Rankings
**High Rankers (80-100)**:
- Low IV percentile (<25th)
- Volume surge 2-4×
- OI building +15%+
- Tight spread <2%
- Good delta/gamma positioning

**Low Rankers (0-30)**:
- High IV percentile (>75th)
- No volume surge
- Negative OI growth
- Wide spread >5%

### Exit Mode Rankings
**High Rankers (80-100)**:
- P&L >50%
- Momentum decaying
- DTE <14 days
- Theta >2% daily

**Low Rankers (0-30)**:
- P&L <10%
- Momentum still strong
- DTE >45 days
- Theta <1% daily

---

## 🚀 Deployment Plan

### Week 1: Backend Integration
1. Update TypeScript backend
2. Update Python job runner
3. Add database columns
4. Deploy with `mode=monitor` as default (no behavior change)
5. Test backend endpoints

### Week 2: Frontend Development
1. Add mode selector to Options tab
2. Update Contract Workbench
3. Update API client calls
4. Local testing with all three modes

### Week 3: Testing & Validation
1. Run validation tests
2. Test on AAPL, TSLA, SPY
3. Compare entry vs exit rankings
4. Verify exit rankings make sense for positions

### Week 4: Release
1. Deploy to production
2. Monitor rankings quality
3. Gather user feedback
4. Iterate on thresholds if needed

---

## 📈 Success Metrics

### Technical Metrics
- [ ] All 3 modes return valid rankings (0-100)
- [ ] Entry mode prioritizes low IV + volume surge
- [ ] Exit mode prioritizes profit + deterioration
- [ ] No NaN or Inf values
- [ ] API response time <500ms

### Business Metrics
- [ ] User adoption of mode selector >30%
- [ ] Entry mode used for new position discovery
- [ ] Exit mode used for position management
- [ ] Improved trade outcomes (track P&L)

---

## 💡 Future Enhancements

### Smart Mode Auto-Switch
If user has open position in contract, auto-show exit mode

### Alerts
- "Exit rank >80" triggers notification
- "Entry rank >90" for new opportunities

### ML Optimization
Learn optimal exit thresholds per user based on historical trades

### Portfolio View
Aggregate exit ranks across all open positions

---

## 📝 Notes

### Manual Entry Price Input
For EXIT mode without full position tracking:
- User can manually input entry_price when viewing contract
- Store in local state or simple preferences
- Entry data passed to EXIT ranking via API

### Backward Compatibility
- Monitor mode uses existing formulas
- All new fields are optional in API
- Frontend falls back to compositeRank if mode-specific ranks not available

---

## ✅ Sign-Off

**Phase 1 Completed**: January 23, 2026  
**Backend Core**: ✅ Complete  
**Swift Models**: ✅ Complete  
**Next Phase**: Backend Integration & Frontend UI  
**Status**: 🚧 Ready for Phase 2 implementation

---

## 🔗 Related Documents

- `ENTRY_EXIT_RANKING_PLAN.md` - Full implementation plan
- `RANKING_CALCULATIONS_REVIEW.md` - Formula documentation
- `RANKING_SYSTEM_UPDATES_SUMMARY.md` - Recent weight changes
