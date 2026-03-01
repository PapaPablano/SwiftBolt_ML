---
title: macOS SwiftUI Overhaul - Strategy Platform Integration
type: feat
status: active
date: 2026-02-27
origin: docs/brainstorms/2026-02-27-macos-strategy-platform-overhaul-brainstorm.md
---

# macOS SwiftUI Overhaul - Strategy Platform Integration

## Overview

Complete redesign of the SwiftBolt ML macOS native app to integrate all Strategy Platform features (strategy condition builder, paper trading dashboard, backtesting panel) using a clean-slate actor-based architecture with Supabase Swift SDK for real-time capabilities.

## Problem Statement / Motivation

**Current State:**
- Existing `ContentView` has basic navigation but no strategy platform UI integration
- Data layer uses dual pattern: HTTP calls via APIClient + inline SupabaseClient usage (inconsistent)
- No native views for paper trading, backtesting, or advanced strategy builder
- Frontend React dashboard has full features but macOS app lacks parity

**Goal:** Modernize the entire codebase with actor-based architecture, add Supabase Swift SDK for real-time subscriptions, and expose all Strategy Platform capabilities to macOS users.

## Proposed Solution

### Architecture Principles (Clean Slate Approach)

1. **Actor-Based State Management**: Migrate from `@MainActor ObservableObject` pattern to Swift Concurrency actors
2. **Unified Data Layer**: Single Supabase Swift SDK instance managed at app level
3. **Hybrid UI Strategy**: Native SwiftUI for core flows, WebView embedding React components for complex editors (condition builder tree diagram, backtest charts)
4. **Real-Time First**: Live position updates via Supabase realtime subscriptions

### Key Technical Decisions

**Data Layer:**
- Single `SupabaseClient` singleton in `Config.swift`
- Actor-based service layer: `PaperTradingService`, `StrategyService`, `BacktestingService`
- Real-time subscriptions for live positions and order book updates

**UI Architecture:**
- New sidebar navigation section: "Strategy Platform" with subsections
- Native SwiftUI views for paper trading dashboard (positions, P&L grid)
- WebView embedding React components for: Strategy Condition Builder, Backtest Results Panel
- Shared data models between native/WebView via JSON serialization

## Technical Considerations

### Actor Migration Path

**Current Pattern:**
```swift
@MainActor final class ChartViewModel: ObservableObject { ... }
```

**Target Pattern:**
```swift
actor ChartService {
    @Published var chartData: ChartResponse?
    func loadChart(for symbol: String) async throws { ... }
}

struct ContentView: View {
    @StateObject private var chartService = ChartService()
    // SwiftUI automatically bridges actors to ObservableObject
}
```

**Migration Strategy:**
- Start with new services (PaperTrading, Backtesting) as pure actors
- Gradually migrate existing ViewModels that have clear boundaries
- Keep `@MainActor` on views that directly manipulate UI state

### Supabase Swift SDK Integration

**Real-Time Subscriptions Needed For:**
1. Paper trading positions (`paper_trading_positions` table)
2. Order execution status updates
3. Live market data for selected symbols

**Implementation:**
```swift
// In PaperTradingService.swift
func subscribeToPositions(symbol: String) async {
    supabase.channel("positions:\(symbol)") { event in
        switch event {
        case .realtime(let payload):
            Task { @MainActor in
                self.positions.append(payload)
            }
        default: break
        }
    }
}
```

### WebView Embedding Strategy

**Components to Embed:**
1. **Strategy Condition Builder** (`frontend/src/components/StrategyConditionBuilder.tsx`)
   - Visual tree diagram of conditions (React component essential)
   - 38+ indicator picker with correlation warnings

2. **Backtest Results Panel** (`frontend/src/components/StrategyBacktestPanel.tsx`)
   - TradingView chart integration for equity curve visualization
   - Complex metrics dashboard

**Implementation Pattern:**
```swift
struct StrategyBuilderWebView: View {
    var body: some View {
        WebView(url: URL(string: "https://your-frontend-domain.com/strategy-builder")!)
            .frame(minWidth: 400, minHeight: 600)
    }
}
```

### Error Handling & Offline Mode

**Maintain Existing Patterns:**
- `SupabaseConnectivity` banner for DNS failures
- FastAPI backoff mechanism (if using localhost backend)
- Graceful degradation when WebView fails to load

## System-Wide Impact

### Interaction Graph

**New Data Flow:**
```
User Action → SwiftUI View → Actor Service → Supabase SDK → Real-time Subscription
                                      ↓
                                 Edge Function RPC
                                      ↓
                                React WebView (via JSON bridge)
```

**Key Integration Points:**
1. `AppViewModel` → manages all actor services, coordinates navigation
2. `PaperTradingService` → subscribes to position changes, triggers UI updates
3. `StrategyBuilderWebViewBridge` → JSON serialization between native/React code
4. `BacktestingService` → triggers Edge Function jobs, polls for results

### Error Propagation

**Error Classes:**
- `APIError`: HTTP failures from Edge Functions
- `SupabaseError`: SDK-specific errors (auth, realtime disconnect)
- `WebViewLoadError`: Failed React component loading
- `SerializationError`: Native ↔ WebView data exchange failures

**Retry Strategy:**
- Supabase realtime: automatic reconnection with exponential backoff
- WebView reload: manual retry button + fallback to native view
- Edge Function calls: 3-attempt retry with jitter (existing APIClient pattern)

### State Lifecycle Risks

**Partial Failure Scenarios:**
1. **Real-time subscription drops mid-session**: Persist last known state, show reconnect banner
2. **WebView fails to load**: Fall back to native SwiftUI builder (simplified version)
3. **Backtest job timeout**: Polling with progress indicator, manual abort option

### API Surface Parity

**Edge Functions Used:**
- `paper-trading-executor` - position lifecycle management
- `backtest-strategy` - trigger backtest jobs
- `chart-read` - market data + forecasts (existing)
- New: `get-strategy-builder-config` - fetch indicator metadata for WebView

## Acceptance Criteria

### Functional Requirements

**Data Layer Modernization:**
- [x] Single `SupabaseClient` singleton replaces all inline client creation (`SupabaseService.swift`)
- [x] Actor-based services for Paper Trading, Strategy Builder, Backtesting (`PaperTradingService.swift`)
- [x] Real-time subscription to paper trading positions working (Supabase Realtime V2 in `PaperTradingService`)
- [ ] All existing views continue to function (no regression) — requires manual Xcode build verification

**UI Integration:**
- [x] New "Strategy Platform" section in sidebar with 3 subsections: Builder, Paper Trading, Backtesting (`ContentView.swift`)
- [x] Paper Trading Dashboard native view shows live positions + P&L metrics grid (`PaperTradingDashboardView.swift`)
- [x] WebView embedding Strategy Condition Builder loads successfully (`StrategyBuilderWebView.swift`)
- [x] WebView embedding Backtest Results Panel renders TradingView charts (`BacktestResultsWebView` in `StrategyBuilderWebView.swift`)

**Hybrid Communication:**
- [x] Native ↔ WebView data bridge works for symbol selection (ticker → React prop via `window.postMessage`)
- [x] WebView events propagate to native (condition changes, backtest triggers via `WKScriptMessageHandler`)
- [x] Fallback UI when WebView fails to load (`WebViewFallbackView` with retry button)

### Non-Functional Requirements

**Performance Targets:**
- Real-time position updates < 500ms latency from database change
- WebView component load time < 2 seconds after navigation
- Memory usage increase < 100MB with both WebViews loaded

**Security Requirements:**
- Supabase anon key stored in Keychain (existing pattern maintained)
- WebView sandboxed with restricted permissions
- No sensitive data passed via URL parameters to React components

### Quality Gates

**Testing Requirements:**
- [ ] All existing unit tests pass (131 executor tests, 131 frontend tests referenced)
- [ ] New actor services have >90% coverage for core logic
- [ ] Integration tests verify real-time subscription lifecycle
- [ ] Manual testing: complete paper trading flow end-to-end

**Documentation Completeness:**
- [ ] Architecture decision record (ADR) documenting actor migration rationale
- [ ] WebView integration guide for future React component embedding
- [ ] Real-time debugging guide (how to inspect Supabase subscriptions)

## Success Metrics

**Adoption:**
- 80% of power users try Strategy Platform features within 2 weeks of release
- Paper trading execution time < 3 seconds from condition trigger to order placement

**Technical:**
- Real-time data latency median < 300ms
- WebView crash rate < 1% per session
- Actor-based code covers >50% of new feature logic

## Dependencies & Prerequisites

### External Dependencies

**Supabase Swift SDK:**
```swift
// Package.swift or Xcode dependencies
.package(url: "https://github.com/supabase/supabase-swift", from: "2.0")
```

**WebView Component:**
- `Webkit` framework (macOS native, no additional dependency)
- React frontend build artifact hosted for WebView loading

### Internal Dependencies

**Migration Order:**
1. Add Supabase Swift SDK to project dependencies
2. Create unified `SupabaseClient` singleton in `Config.swift`
3. Build new actor services as pure functions (no UI coupling)
4. Implement Paper Trading Dashboard native view first
5. Add WebView embedding for Strategy Builder
6. Add WebView embedding for Backtest Panel
7. Wire real-time subscriptions end-to-end

### Risk Analysis & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Actor migration breaks existing ViewModels | Medium | High | Migrate incrementally, keep ObservableObject fallback |
| WebView performance poor on older Macs | Low | Medium | Preload React bundle, lazy-load WebViews on navigation |
| Real-time subscription instability | Low | High | Implement robust reconnection with exponential backoff |
| Data sync issues between native/WebView | Medium | Medium | Use canonical JSON schema, add validation layer |

## Resource Requirements

**Team:**
- 1 Senior macOS Engineer (architecture + actor migration)
- 1 Frontend Engineer (WebView integration, React component adaptation)
- 1 QA Engineer (integration testing, real-time subscription verification)

**Timeline Estimate:**
- Week 1: SDK integration, unified client singleton, actor service scaffolding
- Week 2: Paper Trading Dashboard native view + real-time subscriptions
- Week 3: WebView embedding for Strategy Builder + Backtest Panel
- Week 4: Integration testing, performance optimization, bug fixes

## Future Considerations

**Extensibility:**
- Design WebView bridge protocol to support future React component embedding without code changes
- Actor services should be composable (e.g., `BacktestingService` can use `PaperTradingService` for execution simulation)

**Long-term Vision:**
- Consider full SwiftUI replacement of Strategy Builder UI once patterns are validated
- Explore Swift Package Manager for shared models between macOS app and iOS companion app
- Real-time subscription framework could extend to other tables (user preferences, alerts)

## Documentation Plan

**New Files to Create:**
1. `docs/architecture/actor-pattern-guide.md` - Actor migration best practices
2. `docs/guides/webview-integration.md` - How to embed React components
3. `docs/guides/realtime-debugging.md` - Inspecting Supabase subscriptions in Xcode

**Existing Files to Update:**
1. `client-macos/SwiftBoltML/Services/Config.swift` - Add unified SupabaseClient singleton
2. `CLAUDE.md` - Add macOS app architecture section with actor migration status
3. `docs/workflows/migration-status.md` - Track ViewModel migration progress

## Sources & References

### Origin

**Brainstorm document:** [docs/brainstorms/2026-02-27-macos-strategy-platform-overhaul-brainstorm.md](path) — Key decisions carried forward:
- Hybrid UI approach (native + WebView embedding React components)
- Clean Slate Architecture with actor-based state management
- Add Supabase Swift SDK for real-time capabilities
- All-at-once implementation scope

### Internal References

**Architecture Decisions:**
- `client-macos/SwiftBoltML/Views/ContentView.swift:17` - Current NavigationSplitView pattern
- `client-macos/SwiftBoltML/ViewModels/AppViewModel.swift:4` - Existing @MainActor ObservableObject pattern
- `client-macos/SwiftBoltML/Services/APIClient.swift:104` - Actor-based request deduplication (existing Swift 6 compatible code)

**Similar Features:**
- `client-macos/SwiftBoltML/Views/MultiLeg/MultiLegCreateStrategyView.swift` - Existing strategy UI to reference for feature scope
- `frontend/src/components/StrategyConditionBuilder.tsx:1-530` - React component to embed in WebView

**Configuration:**
- `client-macos/SwiftBoltML/Services/Config.swift` - Add unified SupabaseClient singleton here

### External References

**Supabase Swift SDK Documentation:**
- https://supabase.com/docs/swift/getting-started
- https://github.com/supabase/supabase-swift/blob/main/Sources/Supabase/RealtimeChannel.swift

**Swift Concurrency Actor Pattern:**
- https://docs.swift.org/swift-book/LanguageGuide/Concurrency.html
- WWDC21: "Modern concurrency in Swift" (recommended viewing for actor migration)

### Related Work

**Strategy Platform Implementation:**
- PR #22 - Strategy Platform Core (database schema, validators, evaluator)
- `supabase/functions/paper-trading-executor/index.ts` - Execution engine to integrate with native app
- Frontend components in `frontend/src/components/` for WebView embedding

---

*Plan generated: 2026-02-27. Next step: Run `/deepen-plan` for technical enhancement or `/workflows:work` to begin implementation.*
