---
status: pending
priority: p3
issue_id: "020"
tags: [code-review, agent-native, api, paper-trading, discoverability]
dependencies: []
---

# 020: No discovery endpoint for active paper-trading strategies

## Problem Statement

`POST /paper-trading-executor` requires `{ symbol, timeframe }` but there is no `GET` route to discover which strategies are currently paper-trading-enabled and on what symbols/timeframes. An agent wanting to trigger execution for all active strategies must know the DB schema and query `strategy_user_strategies` directly.

## Findings

**File:** `supabase/functions/paper-trading-executor/index.ts` — no GET route implemented

The executor only handles POST requests. An agent asking "run all active paper trading strategies" currently cannot do so without direct database access.

**Source:** agent-native-reviewer agent (Warning #4)

## Proposed Solutions

### Option A: Add GET route to paper-trading-executor

```typescript
// GET /paper-trading-executor → returns active strategies
if (req.method === 'GET') {
  const { data } = await supabase
    .from('strategy_user_strategies')
    .select('id, name, symbol_id, symbols(ticker), timeframe')
    .eq('paper_trading_enabled', true)
    .eq('is_active', true);
  return new Response(JSON.stringify({ strategies: data }), { headers: corsHeaders });
}
```
- **Effort:** Small | **Risk:** Very Low

### Option B: Filter parameter on existing GET /strategies

Add `?paper_trading_enabled=true` as a query parameter to the existing `strategies` GET endpoint.
- **Pros:** Single endpoint for all strategy queries
- **Effort:** Small | **Risk:** Very Low

## Recommended Action

Option B (add filter to existing strategies GET). Less endpoint sprawl.

## Technical Details

**Affected files:**
- `supabase/functions/strategies/index.ts` or `paper-trading-executor/index.ts`

## Acceptance Criteria

- [ ] Agent can GET a list of active paper trading strategies (with symbol + timeframe) via a single HTTP call
- [ ] Response includes enough info to construct a valid `POST /paper-trading-executor` payload
- [ ] No direct DB access required to discover active strategies

## Work Log

- 2026-02-28: Identified by agent-native-reviewer in PR #23 code review
