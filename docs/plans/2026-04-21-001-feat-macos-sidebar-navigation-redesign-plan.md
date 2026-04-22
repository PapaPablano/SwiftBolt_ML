---
title: "feat: Redesign macOS sidebar navigation and establish design system"
type: feat
status: completed
date: 2026-04-21
origin: docs/brainstorms/2026-04-21-macos-sidebar-navigation-redesign-brainstorm.md
---

# feat: Redesign macOS Sidebar Navigation & Design System

## Overview

Restructure the SwiftBolt ML macOS client's sidebar from a flat, confusing layout into activity-based collapsible sections (Research / Build & Test / Trade), consolidate three duplicate Strategy Builder entry points into one, add glanceable status indicators (active symbol, market status, paper trading positions), replace the detail pane dropdown with a segmented control, and establish a centralized design system with color tokens and typography.

## Problem Frame

The macOS client has grown to 54+ views but the sidebar navigation hasn't evolved to match. Two identically-named "Strategy Builder" sidebar entries do different things (plus a third entry point in the detail pane tabs), sections are grouped under a meaningless "Navigation" header, and there's no visual feedback about app state. Additionally, colors and styling are defined ad-hoc across 40+ files with no centralized design system. (see origin: `docs/brainstorms/2026-04-21-macos-sidebar-navigation-redesign-brainstorm.md`)

## Requirements Trace

- R1. Reorganize sidebar into three collapsible sections: Research, Build & Test, Trade
- R2. Merge Strategy Builders into single entry using `IntegratedStrategyBuilder`
- R3. Collapsible sections with persisted expand/collapse state
- R4. Dev Tools section at bottom, DEBUG only
- R5. Active symbol badge in sidebar
- R6. Status indicators: paper trading positions, market status, connectivity
- R7. Market status visible without scrolling
- R8. Segmented control for detail pane (News | Options | Analysis)
- R9. Remove Strategy Builder from detail pane tabs
- R10. Centralized color token file with semantic colors
- R11. Shared typography styles and spacing scale
- R12. Migrate scattered color definitions to tokens
- R13. Light/dark mode support via adaptive colors

## Scope Boundaries

- **In scope:** Sidebar restructuring, collapsible sections, visual indicators, detail pane tabs, design tokens, color migration
- **Out of scope:** Portfolio view implementation (placeholder stays), new feature views, chart rendering changes, ML pipeline changes
- **Non-goal:** Redesigning individual feature views — this focuses on shell and design foundation

### Deferred to Separate Tasks

- Portfolio view implementation: separate brainstorm
- Chart.js `CHART_COLORS` migration: already centralized, low priority

## Context & Research

### Relevant Code and Patterns

- `client-macos/SwiftBoltML/Views/ContentView.swift` — Current sidebar (`SidebarView`), `SidebarSection` enum, ZStack opacity pattern, `DetailView` with `.menu` picker
- `client-macos/SwiftBoltML/ViewModels/AppViewModel.swift` — `@Published selectedDetailTab: Int`, `selectedSymbol`, `supabaseUnreachable`. Does NOT own MarketStatusService or PaperTradingService
- `client-macos/SwiftBoltML/Services/MarketStatusService.swift` — `@MainActor ObservableObject` with `isMarketOpen: Bool`, `nextEvent: Date?`. Polls every 60s via Supabase Edge Function
- `client-macos/SwiftBoltML/Views/Components/MarketStatusBadge.swift` — Existing badge component rendering green/red dot + countdown
- `client-macos/SwiftBoltML/Services/PaperTradingService.swift` — `@MainActor ObservableObject` with `openPositions: [PaperPosition]`, Supabase Realtime subscription
- `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift` — Single 38KB file, the canonical strategy builder
- `client-macos/SwiftBoltML/Models/PivotLevel.swift` — `PivotColors` struct (closest existing analog to color tokens)
- `client-macos/SwiftBoltML/Resources/WebChart/chart.js` — `const colors` object at line ~1344 (good reference for token naming)
- `client-macos/SwiftBoltML/Views/Components/StandardStateViews.swift` — Shared error/empty/loading views
- `client-macos/SwiftBoltML/Utilities/DeferredBinding.swift` — Shared utility pattern (used in 9 files)
- `client-macos/SwiftBoltML/ViewModels/SelectedContractState.swift` — `@AppStorage("contractWorkbench.*")` convention

**Key patterns:**
- `.pickerStyle(.segmented)` used in 15+ views — dominant pattern for tab switching
- `@AppStorage("module.settingName")` convention for persistence
- `#if DEBUG case devtools #endif` for exhaustive switch without `default:`
- No `DisclosureGroup` usage in codebase — new pattern introduction
- File-level `private let` for formatters/constants (institutional learning)
- 300-line file limit with `extension` blocks for organization

### Institutional Learnings

- **Task lifecycle discipline** (from `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md`): Store Task handles, cancel before re-creating, prefer `.task` modifier. Relevant for status indicator subscriptions.
- **Enum exhaustiveness** (same doc): Use explicit cases with `#if DEBUG`, never bare `default:` on module-owned enums. Critical for new `SidebarSection` redesign.
- **Struct scope in long files** (from `docs/solutions/integration-issues/backtest-auth-api-type-boundary-p1-bugs.md`): Keep files under 300 lines, use `extension` blocks. ContentView.swift is currently 261 lines — will need careful organization after adding collapsible sections.
- **WKWebView lifecycle checklist**: Parameterized NSViewRepresentable, WeakScriptHandler, host whitelist. Sidebar restructure must preserve ZStack opacity pattern.

## Key Technical Decisions

- **Design tokens as caseless enums (no-case enum with static properties):** Standard Swift pattern for namespace-only containers — prevents accidental instantiation. Allows namespacing (`DesignTokens.Colors.success`, `DesignTokens.Typography.heading`) and easy Xcode Preview access. Asset Catalog has only one color (`AccentColor`) — no precedent for that approach.
- **DisclosureGroup for collapsible sections:** SwiftUI's native disclosure pattern. New to this codebase but maps directly to the collapsible requirement. Persist state via `@AppStorage("sidebar.research.expanded")` etc.
- **Phased approach (sidebar first, migration second):** Units 1-5 ship the sidebar redesign + tokens file. Unit 6 migrates existing colors. This lets navigation improvements land independently of the larger color migration effort.
- **MarketStatusService + PaperTradingService as @StateObject on SidebarView:** These services are sidebar-specific. Adding them to AppViewModel would bloat it further (it already manages 10+ child VMs). SidebarView owns them directly.
- **MultiLeg goes under Build & Test:** It's strategy-related construction, not active trading.
- **Charts & Analysis stays as implicit default:** Selecting a watchlist symbol auto-switches to charts. The Research section provides explicit entry but the ZStack opacity pattern continues to keep WKWebView alive.

## Open Questions

### Resolved During Planning

- **Where do 54+ secondary views live?** They are sub-navigation within parent views (e.g., WalkForwardOptimization accessed from Backtesting, ModelTraining from Predictions). The 7 sidebar items are top-level entry points, not exhaustive view list.
- **Market badge states:** MarketStatusService provides `isMarketOpen: Bool` and `nextEvent: Date?`. Badge shows: Open (green dot + "closes in X"), Closed (red dot + "opens in X"). Pre-market/post-market derivable from `nextEvent` time comparison. Weekend/holiday handled by same closed state.
- **Symbol badge data source:** Tracks `appViewModel.selectedSymbol` — the same property that drives chart loading. Updates reactively when user selects from watchlist or search.
- **selectedDetailTab migration:** Current Int-based tags (0-3) become (0-2). AppViewModel's `selectedDetailTab` default is 0, so removing tag 3 only requires removing the branch and picker entry. No other code sets `selectedDetailTab = 3` programmatically.
- **StrategyBuilderWebView removal scope:** Three touchpoints to remove: (1) sidebar `.strategyPlatform(.builder)` case, (2) detail pane picker tab 3, (3) ZStack `if activeSection == .strategyPlatform(.builder)` branch. No deep links, keyboard shortcuts, or other paths reach it.

### Deferred to Implementation

- Exact disclosure triangle styling/animation — use SwiftUI defaults initially, polish if needed
- Whether MarketStatusBadge component is reusable as-is or needs sidebar-specific variant
- Final spacing values for the design tokens spacing scale — derive from existing views during migration

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```
New SidebarSection Enum
========================
enum SidebarSection: Hashable {
    case research(ResearchSection)    // .chartsAndAnalysis, .predictions
    case buildAndTest(BuildSection)   // .strategyBuilder, .backtesting, .multiLeg
    case trade(TradeSection)          // .paperTrading, .liveTrading, .portfolio
    #if DEBUG
    case devtools
    #endif
}

Sidebar Layout
==============
┌─────────────────────────┐
│ [Symbol Search]         │
│ [Watchlist]             │
│ ─── AAPL ── Market: 🟢 │  ← Symbol badge + market status (always visible)
│                         │
│ ▼ Research              │  ← DisclosureGroup, @AppStorage persisted
│   Charts & Analysis     │
│   Predictions           │
│                         │
│ ▼ Build & Test          │
│   Strategy Builder      │  ← Single entry → IntegratedStrategyBuilder
│   Backtesting           │
│   Multi-Leg             │
│                         │
│ ▼ Trade                 │
│   Paper Trading    🟢   │  ← Green dot when positions open
│   Live Trading          │
│   Portfolio             │
│                         │
│ ▼ Dev Tools (DEBUG)     │
└─────────��───────────────┘

Design Tokens Structure
========================
DesignTokens/
���── ColorTokens.swift     — Semantic colors (success, warning, error, accent...)
│                           + chart-specific (support, resistance, signal...)
│                           + adaptive Color initializers for light/dark
├── Typography.swift      — Font styles as ViewModifiers (.heading, .body, .caption, .mono)
└── Spacing.swift         — Spacing scale (xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32)
```

## Implementation Units

- [x] **Unit 1: Design System Foundation**

**Goal:** Create centralized design tokens that all subsequent units and future views can use.

**Requirements:** R10, R11, R13

**Dependencies:** None

**Files:**
- Create: `client-macos/SwiftBoltML/DesignSystem/ColorTokens.swift`
- Create: `client-macos/SwiftBoltML/DesignSystem/Typography.swift`
- Create: `client-macos/SwiftBoltML/DesignSystem/Spacing.swift`

**Approach:**
- `ColorTokens` as a caseless enum with nested namespaces: `Colors.primary`, `Colors.success`, `Colors.chartSupport`, etc. Use `Color(_:Color)` adaptive initializer pattern for light/dark mode.
- Port `PivotColors` values (support green `#1ED67D`, resistance orange `#EB7C14`, active blue `#1B85FF`) as chart-specific tokens.
- Mirror `const colors` naming from `chart.js` (line ~1344) where applicable for cross-platform consistency.
- `Typography` as ViewModifiers: `.heading` (title2, semibold), `.body` (body), `.caption` (caption, secondary), `.mono` (monospaced for prices).
- `Spacing` as caseless enum with static CGFloat constants.

**Patterns to follow:**
- `PivotColors` struct in `client-macos/SwiftBoltML/Models/PivotLevel.swift` — existing color grouping pattern
- `CHART_COLORS` in `client-macos/SwiftBoltML/Resources/WebChart/chart.js` — naming reference
- File-level constants convention from institutional learnings

**Test scenarios:**
- Test expectation: none — pure styling constants with no behavioral logic. Verification is visual.

**Verification:**
- All three files compile without warnings
- Colors render correctly in Xcode Previews in both light and dark appearance

---

- [x] **Unit 2: Sidebar Section Enum Redesign + Collapsible Sections**

**Goal:** Replace the flat `SidebarSection` enum with activity-based nested enums and implement collapsible `DisclosureGroup` sections with persisted state.

**Requirements:** R1, R3, R4

**Dependencies:** Unit 1 (for consistent styling)

**Files:**
- Modify: `client-macos/SwiftBoltML/Views/ContentView.swift`

**Approach:**
- Replace `SidebarSection` and `StrategyPlatformSection` enums with new structure: `SidebarSection.research(ResearchSection)`, `.buildAndTest(BuildSection)`, `.trade(TradeSection)`, `#if DEBUG .devtools #endif`. Keep Hashable conformance for `NavigationLink(value:)`.
- Map existing cases: `.stocks` → `.research(.chartsAndAnalysis)`, `.predictions` → `.research(.predictions)`, `.tradestation` → `.buildAndTest(.strategyBuilder)`, `.strategyPlatform(.backtesting)` → `.buildAndTest(.backtesting)`, `.multileg` → `.buildAndTest(.multiLeg)`, `.strategyPlatform(.paperTrading)` → `.trade(.paperTrading)`, `.strategyPlatform(.liveTrading)` → `.trade(.liveTrading)`, `.portfolio` → `.trade(.portfolio)`.
- Replace `List(selection:) { Section { NavigationLink } }` with `List(selection:) { DisclosureGroup(isExpanded:) { NavigationLink } }`.
- Persist expand/collapse state with `@AppStorage("sidebar.research.expanded") private var researchExpanded = true` (and similar for each section). Default all sections to expanded on first launch.
- Update the ZStack in `ContentView.body` to match new enum cases. Preserve opacity pattern for charts.
- Update `onChange(of: appViewModel.selectedSymbol)` to set `activeSection = .research(.chartsAndAnalysis)`.
- Note: `.trade(.liveTrading)` currently has no view implementation (the existing `.strategyPlatform(.liveTrading)` NavigationLink has no ZStack branch). Mount a `Text("Live Trading")` placeholder matching the existing Portfolio pattern.
- Keep file under 300 lines. Extract sub-enums to a separate `SidebarModels.swift` file if ContentView exceeds limit.

**Patterns to follow:**
- `@AppStorage("contractWorkbench.showAdvancedControls")` in `SelectedContractState` — persistence naming convention
- `#if DEBUG case devtools #endif` — existing enum exhaustiveness pattern
- `NavigationLink(value:)` with `List(selection:)` — current navigation pattern

**Test scenarios:**
- Happy path: Each sidebar item navigates to its corresponding view
- Happy path: Collapsing a section hides its items; expanding reveals them
- Edge case: All sections collapsed — sidebar shows only section headers
- Edge case: App restart — collapsed state is preserved from previous session
- Edge case: Selecting a watchlist symbol switches to Research > Charts & Analysis
- Integration: ZStack opacity pattern — chart WKWebView stays alive when switching to non-chart section

**Verification:**
- All 7 sidebar items navigate correctly
- Collapse/expand persists across app relaunch
- Chart JS context survives section switching (verify chart renders without reload after switching away and back)
- No compiler warnings about non-exhaustive switch

---

- [x] **Unit 3: Strategy Builder Consolidation**

**Goal:** Remove the duplicate Strategy Builder entries and the detail pane Strategy Builder tab, leaving one entry point.

**Requirements:** R2, R9

**Dependencies:** Unit 2 (new enum structure)

**Files:**
- Modify: `client-macos/SwiftBoltML/Views/ContentView.swift`

**Approach:**
- Remove the old `.strategyPlatform(.builder)` case handling from the ZStack (the `StrategyBuilderWebView` mount).
- Remove `Text("Strategy Builder").tag(3)` from DetailView's picker and the corresponding `IntegratedStrategyBuilder` branch in the `else` clause.
- Update `AppViewModel.selectedDetailTab` — no code sets it to 3 programmatically, so removal is safe. If any call site does `selectedDetailTab = 3`, it becomes a dead branch that should be removed.
- The `.buildAndTest(.strategyBuilder)` case (from Unit 2) maps to `IntegratedStrategyBuilder` — this is now the sole entry point.

**Patterns to follow:**
- Existing ZStack conditional mounting pattern in ContentView

**Test scenarios:**
- Happy path: Sidebar "Strategy Builder" opens IntegratedStrategyBuilder
- Happy path: Detail pane picker shows only News | Options | Analysis (3 items)
- Edge case: No path in the app opens StrategyBuilderWebView
- Edge case: selectedDetailTab value 3 is unreachable

**Verification:**
- Only one "Strategy Builder" label appears in the entire sidebar
- Detail pane has exactly 3 tabs
- IntegratedStrategyBuilder loads correctly from sidebar

---

- [x] **Unit 4: Detail Pane Segmented Control**

**Goal:** Replace the dropdown `.menu` picker with a visible segmented control.

**Requirements:** R8

**Dependencies:** Unit 3 (Strategy Builder tab removed, leaving 3 tabs)

**Files:**
- Modify: `client-macos/SwiftBoltML/Views/ContentView.swift`

**Approach:**
- Change `.pickerStyle(.menu)` to `.pickerStyle(.segmented)` on the DetailView picker.
- Remove the `.frame(minWidth: 160)` constraint (segmented controls size to content).
- Update padding to match segmented control visual weight — use `DesignTokens.Spacing` values.

**Patterns to follow:**
- `.pickerStyle(.segmented)` usage in `OptionsChainView`, `PredictionsView`, `BacktestResultsView` — 15+ established examples

**Test scenarios:**
- Happy path: Three segments visible (News, Options, Analysis) — all tappable
- Happy path: Selected segment visually highlighted
- Edge case: Narrow window — segmented control truncates gracefully or scrolls

**Verification:**
- Segmented control renders with 3 visible segments
- Tab switching works identically to before (same views load)

---

- [x] **Unit 5: Sidebar Visual Indicators**

**Goal:** Add active symbol badge, market status badge, and paper trading position indicator to the sidebar.

**Requirements:** R5, R6, R7

**Dependencies:** Unit 2 (sidebar structure), Unit 1 (design tokens for colors)

**Files:**
- Modify: `client-macos/SwiftBoltML/Views/ContentView.swift`
- Possibly create: `client-macos/SwiftBoltML/Views/Components/SidebarStatusBar.swift` (if ContentView exceeds 300 lines)

**Approach:**
- **Symbol badge (R5):** Add a compact bar between the Watchlist and the collapsible sections showing `appViewModel.selectedSymbol?.ticker` in a styled badge. Reactive to symbol changes.
- **Market status (R6, R7):** Instantiate `MarketStatusService` on `SidebarView`. Note: `MarketStatusService.init(supabaseURL:supabaseKey:)` requires credentials — either refactor it to use `SupabaseService.shared` internally (matching `PaperTradingService` pattern) or pass credentials via a factory initializer. Place `MarketStatusBadge` (or a compact variant) next to the symbol badge — always visible without scrolling.
- **Paper trading dot (R6):** Instantiate `PaperTradingService` as `@StateObject` on `SidebarView`. Add a green circle overlay on the Paper Trading `NavigationLink` label when `!paperTradingService.openPositions.isEmpty`. Use `DesignTokens.Colors.success` for the dot color.
- **Connectivity (R6):** `appViewModel.supabaseUnreachable` is already tracked. Add a small warning icon near the status bar when `true`.
- **Timer lifecycle note:** `MarketStatusService` uses `Timer.scheduledTimer` (not Swift Concurrency Task), so `.task` cancellation will NOT stop its internal timer. Must call `marketService.stopMonitoring()` explicitly in `.onDisappear`, or refactor the service to use `Task.sleep`-based polling. `PaperTradingService` uses Supabase Realtime which self-manages lifecycle.

**Patterns to follow:**
- `MarketStatusBadge` in `client-macos/SwiftBoltML/Views/Components/MarketStatusBadge.swift` — existing market status rendering
- `.task` modifier for async service initialization
- `DesignTokens.Colors` for all indicator colors

**Test scenarios:**
- Happy path: Symbol badge shows currently selected ticker, updates on symbol change
- Happy path: Market status shows green when market open, red when closed
- Happy path: Green dot appears on Paper Trading when openPositions is non-empty
- Happy path: Green dot disappears when all positions are closed
- Edge case: No symbol selected — badge shows placeholder or is hidden
- Edge case: Supabase unreachable — connectivity warning icon appears
- Edge case: MarketStatusService returns nextEvent — countdown displays correctly
- Integration: Paper trading dot updates in real-time when position is opened/closed in PaperTradingDashboardView

**Verification:**
- All three indicators visible and reactive in sidebar
- Market status badge visible without scrolling
- Switching sections does not disrupt indicator state

---

- [x] **Unit 6: Color Migration to Design Tokens**

**Goal:** Migrate hardcoded color definitions across existing files to use centralized design tokens.

**Requirements:** R12

**Dependencies:** Unit 1 (design tokens exist)

**Files:**
- Modify: `client-macos/SwiftBoltML/Models/PivotLevel.swift` — replace `PivotColors` struct with re-exports from `DesignTokens.Colors`
- Modify: `client-macos/SwiftBoltML/Models/RealtimeForecastModels.swift` — replace hex string literals
- Modify: `client-macos/SwiftBoltML/Services/PivotPeriodManager.swift` — replace `Color(red:)` period color literals (micro=gray, short=blue, medium=cyan, long=gold — these are NOT PivotColors)
- Modify: `client-macos/SwiftBoltML/Services/PivotChartDrawing.swift` — replace PivotColors references
- Modify: `client-macos/SwiftBoltML/Services/PivotLevelsIndicator.swift` — replace PivotColors references
- Modify: `client-macos/SwiftBoltML/Views/ForecastHorizonsView.swift` — replace gradient color literals
- Modify: Additional files discovered during implementation (40+ files use `Color.green`/`.red`/`.orange` — migrate only semantic uses, not SwiftUI standard palette uses)

**Approach:**
- **Phase this migration.** Start with the 6 files above that use custom hex/RGB colors (highest visual inconsistency risk). Files using standard SwiftUI palette colors (`.green`, `.red`) are lower priority — migrate them when those views are next modified.
- Replace `PivotColors.support` → `DesignTokens.Colors.chartSupport`, etc. Keep `PivotColors` as a typealias initially for backward compatibility, then remove once all callers are migrated.
- Replace inline hex strings (`#26a69a`) with named token references.
- Do NOT touch `chart.js` `CHART_COLORS` — already centralized, different runtime.

**Execution note:** Run the app and visually verify each migrated view renders identically before and after. Color regressions are hard to catch in tests.

**Patterns to follow:**
- Existing `PivotColors` usage pattern — same call sites, new backing values

**Test scenarios:**
- Happy path: PivotLevel colors render identically after migration (green support, orange resistance, blue active)
- Happy path: Forecast horizon gradients render identically
- Edge case: Dark mode — all migrated colors adapt correctly (no hardcoded light-mode-only values remain)
- Edge case: PivotColors typealias compiles and resolves to new tokens

**Verification:**
- All migrated files compile without warnings
- Visual comparison: chart support/resistance colors, forecast gradients, and pivot period colors match pre-migration appearance in both light and dark mode
- No remaining `Color(red:` or hex string literals in the 6 targeted files

## System-Wide Impact

- **Interaction graph:** Sidebar restructure changes the `SidebarSection` enum consumed by ContentView's ZStack routing. All conditional mounts must be updated atomically. MarketStatusService and PaperTradingService gain new consumers (SidebarView) alongside their existing view consumers.
- **Error propagation:** MarketStatusService poll failures should degrade gracefully (show "Unknown" state, not crash). PaperTradingService subscription errors should hide the indicator, not show stale state.
- **State lifecycle risks:** ZStack opacity pattern must be preserved — changing chart mounting from `opacity(0)` to conditional `if` would destroy the WKWebView JS context. Task handles for MarketStatusService timer must be cancelled on SidebarView disappear.
- **API surface parity:** No API changes — all data sources (Edge Functions) remain unchanged. Client-side only.
- **Integration coverage:** Paper trading indicator updates when positions change via Realtime subscription. Market status updates on 60-second poll. Symbol badge updates on watchlist selection.
- **Unchanged invariants:** All existing views (ChartView, PredictionsView, OptionsChainView, etc.) continue to function identically. The chart WebView lifecycle is preserved. AppViewModel's child VM architecture is not modified.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| DisclosureGroup is new to codebase — may behave unexpectedly with NavigationSplitView | Prototype in Unit 2 early. Fall back to custom expandable Section if needed. |
| Color migration (Unit 6) touches rendering code in Services layer | Phase migration, visual verification, dark mode testing. Ship Units 1-5 first. |
| ContentView exceeds 300-line limit after changes | Extract SidebarStatusBar and sidebar sub-enums to separate files per institutional learning. |
| MarketStatusService uses Timer.scheduledTimer — sidebar mount/unmount could leak timers | Call `stopMonitoring()` in `.onDisappear`. Note: `.task` cancellation does NOT stop Timer-based services. |
| 40+ files with hardcoded colors — Unit 6 scope is large | Prioritize 6 custom-color files first. Standard palette migration deferred to future view modifications. |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-21-macos-sidebar-navigation-redesign-brainstorm.md](docs/brainstorms/2026-04-21-macos-sidebar-navigation-redesign-brainstorm.md)
- Institutional learnings: `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md` (Task lifecycle, enum patterns)
- Institutional learnings: `docs/solutions/integration-issues/backtest-auth-api-type-boundary-p1-bugs.md` (struct scope, 300-line limit)
- Related code: `client-macos/SwiftBoltML/Views/ContentView.swift`, `client-macos/SwiftBoltML/ViewModels/AppViewModel.swift`
