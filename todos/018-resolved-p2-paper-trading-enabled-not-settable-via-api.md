---
status: pending
priority: p2
issue_id: "018"
tags: [code-review, agent-native, api, paper-trading, strategies]
dependencies: []
---

# 018: paper_trading_enabled field not settable via any API endpoint

## Problem Statement

The `strategy_user_strategies` table has a `paper_trading_enabled` column that the executor uses to filter active paper trading strategies (`.eq("paper_trading_enabled", true)`). However, the `strategies` Edge Function's `handleUpdate` only allows updating `name`, `description`, `config`, and `is_active` — `paper_trading_enabled` is excluded. There is no way for an agent or any API caller to arm/disarm paper trading for a specific strategy without direct database access.

The macOS UI's "Active" toggle maps to `is_active`, not `paper_trading_enabled`. The Paper Trading Dashboard has no toggle for this field either.

## Findings

**File:** `supabase/functions/strategies/index.ts` lines ~166-169 — `handleUpdate` allowed fields list

```typescript
// Current handleUpdate (approximate):
const { name, description, config, is_active } = body;
// paper_trading_enabled is NOT included
```

**File:** `supabase/functions/paper-trading-executor/index.ts` line ~541

```typescript
.eq("paper_trading_enabled", true)  // executor reads this field but nothing can write it
```

**Agent impact:** 7 of 13 capabilities are agent-accessible. This is one of the critical write-side gaps.

**Source:** agent-native-reviewer agent (Critical)

## Proposed Solutions

### Option A: Add paper_trading_enabled to strategies PUT handler (Recommended)

```typescript
// In handleUpdate:
const { name, description, config, is_active, paper_trading_enabled } = body;
const updateData: Record<string, unknown> = {};
if (name !== undefined) updateData.name = name;
if (description !== undefined) updateData.description = description;
if (config !== undefined) updateData.config = config;
if (is_active !== undefined) updateData.is_active = is_active;
if (paper_trading_enabled !== undefined) updateData.paper_trading_enabled = paper_trading_enabled;
```

Add a corresponding toggle in `PaperTradingDashboardView` or `IntegratedStrategyBuilder`:

```swift
// In strategy detail/header:
Toggle("Paper Trading", isOn: $strategy.paperTradingEnabled)
    .onChange(of: strategy.paperTradingEnabled) { _, newValue in
        Task { await strategyViewModel.updatePaperTrading(enabled: newValue) }
    }
```
- **Pros:** Minimal change; follows existing update pattern
- **Effort:** Small | **Risk:** Low

### Option B: Dedicated enable/disable paper trading endpoint
`POST /paper-trading-executor` with `{ action: "set_enabled", strategy_id: "...", enabled: true }`.
- **Pros:** Clear semantics; can validate strategy exists and has valid config before enabling
- **Cons:** More endpoints for agents to discover
- **Effort:** Small | **Risk:** Low

## Recommended Action

Option A. Consistent with the existing `strategies` CRUD surface; agents already know about the PUT endpoint.

## Technical Details

**Affected files:**
- `supabase/functions/strategies/index.ts` (`handleUpdate` function)
- `client-macos/SwiftBoltML/Views/` (add UI toggle — either PaperTradingDashboardView or IntegratedStrategyBuilder)
- Native `Strategy` model (add `paperTradingEnabled: Bool` field with CodingKey `paper_trading_enabled`)

## Acceptance Criteria

- [ ] `PUT /strategies?id=xxx` with `{ paper_trading_enabled: true }` updates the field
- [ ] Executor continues to filter by `paper_trading_enabled = true` correctly
- [ ] Agent can enable/disable paper trading with a single PUT call
- [ ] UI toggle visible and functional for `paper_trading_enabled` on strategies
- [ ] Disabling paper trading stops the executor from processing that strategy on subsequent cycles

## Work Log

- 2026-02-28: Identified by agent-native-reviewer in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
- `supabase/functions/strategies/index.ts`
- `supabase/functions/paper-trading-executor/index.ts`
