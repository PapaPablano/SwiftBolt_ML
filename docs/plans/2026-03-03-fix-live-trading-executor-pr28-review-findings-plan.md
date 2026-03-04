---
title: "fix: Resolve all P1+P2 code review findings from PR #28 (live trading executor)"
type: fix
status: active
date: 2026-03-03
origin: docs/brainstorms/2026-03-03-live-trading-executor-tradestation-brainstorm.md
---

# fix: Resolve All P1+P2 Review Findings — Live Trading Executor (PR #28)

## Overview

PR #28 introduced the live trading executor via TradeStation. The code review (PR #28 review) produced 41 findings. This plan resolves all **13 P1 (blocks-merge)** and **19 P2 (should-fix)** findings before the PR can be merged and live trading can be activated.

**Todos in scope:** 108–116, 117–126, 131–132, 133–136, 139–143, 146
**Todos out of scope (P3, addressed later):** 127–130, 137–138, 144–145, 147–148

**Primary reference:** `docs/LIVE_TRADING_EXECUTOR_INSTITUTIONAL_LEARNINGS.md`
**Deployment checklist:** `docs/DEPLOYMENT_VERIFICATION_PR28_LIVE_TRADING.md`

---

## Problem Statement

The live trading executor places real-money orders. Before merging, 13 critical issues must be resolved:

- **Financial safety**: An unprotected open position can result if the executor crashes mid-flow (`pending_bracket` stuck state, #108). A market order fires before the DB insert in some error paths (#110), leaving an untracked live position.
- **Data integrity**: The recorded exit price for manual closes and exit-signal closes is the last bar close price, not the actual broker fill price (#140, #118). SL/TP levels are computed before the fill is known (#119).
- **Runtime errors**: `symbol_id UUID` vs raw symbol string mismatch will crash the first live trade (#117). `Condition` type is not imported — compile error (#139).
- **Security**: CORS echoes unknown origins, enabling cross-origin bypass (#114). The `increment_rate_limit` RPC is missing from migrations; the fallback is non-atomic (#115, #141).
- **Type safety**: Blanket `// deno-lint-ignore-file no-explicit-any` in both executor files hides all type errors, including `supabase: any` across 8+ function signatures (#131).

---

## Technical Approach

### Phased Implementation

Fixes are grouped into 8 phases ordered by: (1) compile errors first, (2) database/infrastructure before application code, (3) financial safety before reliability, (4) API/frontend last.

---

### Phase 1: Compile Errors & Type Safety (P1)
**Todos:** #139, #131, #117
**Files:** `live-trading-executor/index.ts`, `_shared/tradestation-client.ts`, migration

#### 1.1 — Import `Condition` type (#139)
**File:** `supabase/functions/live-trading-executor/index.ts`
**Fix:** Add import at top of file:
```typescript
import type { Condition } from "../_shared/condition-evaluator.ts";
```
Then update `StrategyConfig` interface to use `Condition[]` instead of the unresolved reference.

#### 1.2 — Remove blanket `no-explicit-any`; type Supabase client (#131)
**Files:** `live-trading-executor/index.ts` (line 12), `_shared/tradestation-client.ts` (line 1)

```typescript
// Add to both files:
import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
type Db = SupabaseClient;

// Replace all: supabase: any → supabase: Db
//              authSupabase: any → authSupabase: Db
```

Remove both `// deno-lint-ignore-file no-explicit-any` directives. Any remaining `any` usages must be individually suppressed with a justification comment.

Run `deno lint` to surface remaining suppressions needed.

#### 1.3 — Change `symbol_id UUID` to `TEXT` (#117)
**New migration:** `supabase/migrations/20260303120000_fix_live_trading_symbol_type.sql`

```sql
-- Change symbol_id from UUID to TEXT to match how executor passes raw symbol strings
ALTER TABLE live_trading_positions
  ALTER COLUMN symbol_id TYPE TEXT;

-- Re-create affected indexes (DROP + CREATE since column type changed)
DROP INDEX IF EXISTS idx_live_positions_strategy_symbol;
DROP INDEX IF EXISTS idx_live_positions_strategy_symbol_open;

CREATE INDEX idx_live_positions_strategy_symbol
  ON live_trading_positions (user_id, strategy_id, symbol_id);

CREATE UNIQUE INDEX idx_live_positions_strategy_symbol_open
  ON live_trading_positions (user_id, strategy_id, symbol_id)
  WHERE status IN ('pending_entry', 'pending_bracket', 'open');
```

---

### Phase 2: Database & Infrastructure (P1 + P2)
**Todos:** #115, #120, #121, #122
**New migration:** `supabase/migrations/20260303130000_live_trading_infra_fixes.sql`

#### 2.1 — Define `increment_rate_limit` RPC (#115)
```sql
CREATE OR REPLACE FUNCTION increment_rate_limit(
  p_user_id     UUID,
  p_window_start TIMESTAMPTZ,
  p_max_requests INT
) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_count INT;
BEGIN
  INSERT INTO live_order_rate_limits (user_id, window_start, request_count)
  VALUES (p_user_id, p_window_start, 1)
  ON CONFLICT (user_id, window_start)
  DO UPDATE SET request_count = live_order_rate_limits.request_count + 1
  RETURNING request_count INTO v_count;
  RETURN v_count <= p_max_requests;
END;
$$;
```

#### 2.2 — Add `updated_at` auto-update trigger to `live_trading_positions` (#120)
```sql
CREATE OR REPLACE FUNCTION update_live_positions_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER live_positions_updated_at
  BEFORE UPDATE ON live_trading_positions
  FOR EACH ROW EXECUTE FUNCTION update_live_positions_updated_at();
```

#### 2.3 — Fix FK delete inconsistency (#121)
`live_trading_trades.user_id` uses `ON DELETE RESTRICT`; `live_trading_positions.user_id` uses `ON DELETE CASCADE`. Both should be `RESTRICT` — never silently delete financial records when a user is deleted.

```sql
-- Re-create FK on live_trading_positions to use RESTRICT instead of CASCADE
ALTER TABLE live_trading_positions
  DROP CONSTRAINT live_trading_positions_user_id_fkey;

ALTER TABLE live_trading_positions
  ADD CONSTRAINT live_trading_positions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE RESTRICT;
```

#### 2.4 — Add CHECK constraints to `live_trading_trades` (#122)
```sql
ALTER TABLE live_trading_trades
  ADD CONSTRAINT live_trades_positive_prices
    CHECK (entry_price > 0 AND exit_price > 0),
  ADD CONSTRAINT live_trades_positive_quantity
    CHECK (quantity > 0),
  ADD CONSTRAINT live_trades_close_reason_valid
    CHECK (close_reason IN (
      'stop_loss_hit', 'take_profit_hit', 'exit_signal',
      'manual_close', 'emergency_close', 'circuit_breaker'
    ));
```

---

### Phase 3: CORS Security & Pagination (P1)
**Todos:** #114, #132

#### 3.1 — Fix CORS echoing unknown origins (#114)
**File:** `supabase/functions/_shared/cors.ts` line 85–87

Current behavior: Unknown origins receive `allowed[0]` (e.g., `https://swiftbolt.app`) as the CORS response — this is a bypass vector.

Fix: Return empty string or omit `Access-Control-Allow-Origin` for unknown origins:
```typescript
// Before:
const responseOrigin = origin && allowed.includes(origin)
  ? origin
  : allowed[0];  // BUG: echoes first allowed origin to all callers

// After:
const responseOrigin = origin && allowed.includes(origin)
  ? origin
  : "";  // Unknown origin: return empty string (no CORS grant)
```

##### 3.1a — Caller Audit: Update all functions not passing `origin` (#168)

**REQUIRED BEFORE deploying the `getCorsHeaders` fix above.** Currently 20 Edge Functions call `handleCorsOptions()`, `handlePreflight()`, or `errorResponse()` without passing the `origin` argument. These callers pass `null` (default), which `getCorsHeaders(null)` treats as unknown origin → currently returns `allowed[0]` (works). After the fix above, `getCorsHeaders(null)` returns `""` → CORS headers omitted → **all 20 functions break on preflight requests.**

Since `supabase functions deploy` deploys all functions atomically, both the caller updates and the `getCorsHeaders` fix can be deployed together in one PR. However, the caller updates **must be included in the same PR** — deploying the `getCorsHeaders` fix alone will break all callers not passing origin.

**20 functions to update (extract and pass `req.headers.get("Origin")`):**

| # | Function | Calls missing origin |
|---|----------|---------------------|
| 1 | `multi-leg-detail/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 2 | `multi-leg-delete/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 3 | `multi-leg-update/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 4 | `multi-leg-create/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 5 | `multi-leg-close-strategy/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 6 | `multi-leg-close-leg/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 7 | `multi-leg-list/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 8 | `multi-leg-evaluate/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 9 | `options-quotes/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 10 | `options-chain/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 11 | `ga-strategy/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 12 | `symbol-backfill/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 13 | `strategy-backtest/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 14 | `data-health/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 15 | `trigger-ranking-job/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 16 | `symbols-search/index.ts` | `handleCorsOptions()`, `errorResponse("...", N)` |
| 17 | `train-model/index.ts` | `handlePreflight()` |
| 18 | `forecast-quality/index.ts` | `handlePreflight()` |
| 19 | `volatility-surface/index.ts` | `handlePreflight()` |
| 20 | `greeks-surface/index.ts` | `handlePreflight()` |

**14 functions already passing origin (no changes needed):**
`chart`, `sync-futures-data`, `technical-indicators`, `stress-test`, `portfolio-optimize`, `quotes`, `futures-chain`, `futures-roots`, `backtest-strategy`, `paper-trading-executor`, `futures-continuous`, `walk-forward-optimize`, `live-trading-executor`, `strategies`

**Pattern for updating each caller (functions #1–16 using `handleCorsOptions`):**
```typescript
// Before:
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }
  // ...
  return errorResponse("...", 400);
});

// After:
Deno.serve(async (req: Request) => {
  const origin = req.headers.get("Origin");
  if (req.method === "OPTIONS") {
    return handleCorsOptions(origin);
  }
  // ...
  return errorResponse("...", 400, origin);
});
```

**Pattern for updating callers #17–20 using `handlePreflight`:**
```typescript
// Before:
return handlePreflight();

// After:
return handlePreflight(origin);
// (origin already extracted earlier in these functions)
```

#### 3.2 — Fix `total` field in paginated GET responses (#132)
**Files:** `live-trading-executor/index.ts` GET handlers (positions, trades, summary)

The `total` field currently returns the page size (e.g., `limit: 50`) instead of the actual DB row count. Fix by using Supabase's `count: 'exact'` option:

```typescript
const { data, count, error } = await supabase
  .from("live_trading_positions")
  .select("*", { count: "exact" })
  .eq("user_id", userId)
  .range(offset, offset + limit - 1);

// Return count (actual DB total), not data.length
return { positions: data, total: count ?? 0, limit, offset };
```

---

### Phase 4: Order Safety & Financial Integrity (P1)
**Todos:** #109, #110, #111, #112, #140
**File:** `live-trading-executor/index.ts`

#### 4.1 — Check `cancelOrder` response.ok (#109)
**Lines:** 266–277

```typescript
// Before:
await cancelOrder(token.access_token, accountId, orderId);

// After:
const cancelled = await cancelOrder(token.access_token, accountId, orderId);
if (!cancelled.ok) {
  console.error(`[live-executor] cancelOrder failed (${cancelled.status}) for order ${orderId}`);
  // Log but do not throw — this is best-effort. Failure will surface in bracket fill monitoring.
}
```

The `cancelOrder` function should return `{ ok: boolean; status: number }` rather than `void`.

#### 4.2 — Cancel market order on all DB insert errors, not just conflict (#110)
**Line ~810 (after `placeMarketOrder`, before DB insert)**

Current: The executor only cancels the market order on `23505` (unique constraint violation). Other DB errors (network timeout, RLS error) leave an untracked live position at the broker.

Fix: Wrap the DB insert in try/catch; call `cancelOrder` on any non-23505 failure:

```typescript
try {
  const { error: insertError } = await supabase.from("live_trading_positions").insert({...});
  if (insertError) {
    if (insertError.code === "23505") {
      // Duplicate — position exists, cancel the new order
      await cancelOrder(token.access_token, accountId, entryOrderId);
    } else {
      // Unknown DB error — cancel to prevent untracked position
      await cancelOrder(token.access_token, accountId, entryOrderId);
      throw insertError; // Re-throw so the cycle logs the error
    }
  }
} catch (e) {
  await cancelOrder(token.access_token, accountId, entryOrderId);
  throw e;
}
```

#### 4.3 — Null-guard `ensureFreshToken` result (#111)
**Lines 289–297 of `_shared/tradestation-client.ts`**

The re-read path for concurrent refresh returns `freshToken as BrokerToken` without checking for null. Fix:

```typescript
const { data: freshToken } = await supabase
  .from("broker_tokens")
  .select("*")
  .eq("user_id", userId)
  .eq("provider", "tradestation")
  .is("revoked_at", null)
  .single();

if (!freshToken) {
  throw Object.assign(new Error("broker_not_connected"), { status: 401 });
}
return freshToken as BrokerToken;
```

#### 4.4 — Wrap `checkBracketFills` in try/catch (#112)
**Lines ~585–600 in the main cycle**

```typescript
// Before:
await checkBracketFills(supabase, token, accountId, userId);

// After:
try {
  await checkBracketFills(supabase, token, accountId, userId);
} catch (bracketErr) {
  console.error("[live-executor] checkBracketFills error — cycle continues:", bracketErr);
  // Do not rethrow — bracket fill errors must not abort the strategy execution cycle
}
```

#### 4.5 — Poll fill price after manual close (#140)
**File:** `live-trading-executor/index.ts`, `closeLivePosition` function

After placing the closing market order, poll for the actual fill price using the existing `pollOrderFill` function:

```typescript
const closeOrderId = await placeMarketOrder(token.access_token, accountId, closeAction, qty, symbol);

// Poll for actual fill (5s timeout is sufficient for a close order)
let closeFill: OrderFillResult;
try {
  closeFill = await pollOrderFill(token.access_token, accountId, closeOrderId, 5_000);
  exitPrice = closeFill.fillPrice;
} catch {
  // Poll timed out — use current_price as approximation, flag for reconciliation
  console.warn(`[live-executor] Close fill poll timed out for order ${closeOrderId} — using estimated price`);
  // exitPrice remains current_price (already set)
}
```

---

### Phase 5: State Machine Recovery (P1)
**Todo:** #108
**Files:** `live-trading-executor/index.ts`

This is the highest-consequence fix. A position stuck in `pending_bracket` with no SL/TP orders is an unprotected open position with real market risk.

#### 5.1 — Add stuck-position recovery scan

Add a `recoverStuckPositions` function called at the top of `executeLiveTradingCycle` (before the per-strategy loop):

```typescript
const STUCK_POSITION_THRESHOLD_MS = 2 * 60 * 1000; // 2 minutes

async function recoverStuckPositions(
  supabase: Db, token: BrokerToken, accountId: string, userId: string
): Promise<void> {
  const threshold = new Date(Date.now() - STUCK_POSITION_THRESHOLD_MS).toISOString();

  // Find positions stuck in pending states older than threshold
  const { data: stuckPositions } = await supabase
    .from("live_trading_positions")
    .select("*")
    .eq("user_id", userId)
    .in("status", ["pending_entry", "pending_bracket"])
    .lt("order_submitted_at", threshold);

  for (const pos of (stuckPositions ?? [])) {
    if (pos.status === "pending_entry" && pos.broker_order_id) {
      // Re-poll entry fill
      const fill = await getOrderStatus(token.access_token, accountId, pos.broker_order_id);
      if (fill.filledQuantity > 0) {
        // Entry filled — advance to open (without bracket — will be flagged)
        await supabase.from("live_trading_positions")
          .update({ status: "open", entry_price: fill.fillPrice })
          .eq("id", pos.id).eq("status", "pending_entry");
        console.error(`[live-executor] ALERT: Position ${pos.id} recovered from pending_entry — no brackets placed`);
      } else {
        // Not filled — cancel and mark cancelled
        await cancelOrder(token.access_token, accountId, pos.broker_order_id);
        await supabase.from("live_trading_positions")
          .update({ status: "cancelled" })
          .eq("id", pos.id).eq("status", "pending_entry");
      }
    } else if (pos.status === "pending_bracket") {
      // Entry filled but bracket not placed — emergency close
      console.error(`[live-executor] ALERT: Stuck pending_bracket position ${pos.id} — initiating emergency close`);
      await closeLivePosition(supabase, pos, pos.current_price ?? pos.entry_price, "emergency_close");
    }
  }
}
```

---

### Phase 6: Reliability Fixes (P1 + P2)
**Todos:** #113, #116, #141

#### 6.1 — Exponential backoff in `pollOrderFill` (#113)
**File:** `live-trading-executor/index.ts` lines 280–315

```typescript
// Replace fixed POLL_INTERVAL_MS with exponential backoff:
let delay = 500; // Start at 500ms
const MAX_DELAY = 5_000; // Cap at 5s

while (Date.now() < deadline) {
  const result = await getOrderStatus(...);
  if (result.filledQuantity >= expectedQty) return result;

  await new Promise((r) => setTimeout(r, delay));
  delay = Math.min(delay * 1.5, MAX_DELAY); // 500 → 750 → 1125 → 1687 → ... → 5000
}
throw new Error("fill_poll_timeout");
```

Total budget is still bounded by `POLL_TIMEOUT_MS = 15_000`.

#### 6.2 — Per-position `account_id` in `checkBracketFills` (#116)
**File:** `live-trading-executor/index.ts`, `checkBracketFills` function

Group open positions by their stored `account_id` column and issue one `getBatchOrderStatus` call per distinct account:

```typescript
// Group positions by account_id
const byAccount = new Map<string, typeof positions>();
for (const pos of positions) {
  const acct = pos.account_id ?? accountId; // fall back to current if missing
  if (!byAccount.has(acct)) byAccount.set(acct, []);
  byAccount.get(acct)!.push(pos);
}

for (const [acct, acctPositions] of byAccount) {
  const orderIds = acctPositions.flatMap(p =>
    [p.broker_sl_order_id, p.broker_tp_order_id].filter(Boolean)
  );
  const fills = await getBatchOrderStatus(token.access_token, acct, orderIds);
  // ... process fills for acctPositions
}
```

#### 6.3 — Remove silent always-allow fallback from `checkRateLimit` (#141)
**File:** `live-trading-executor/index.ts` lines 126–151

Now that the `increment_rate_limit` RPC exists (Phase 2.1), remove the manual fallback path. The RPC failure should propagate:

```typescript
async function checkRateLimit(supabase: Db, userId: string): Promise<boolean> {
  const windowStart = new Date(
    Math.floor(Date.now() / RATE_LIMIT_WINDOW_MS) * RATE_LIMIT_WINDOW_MS,
  ).toISOString();

  const { data, error } = await supabase.rpc("increment_rate_limit", {
    p_user_id: userId,
    p_window_start: windowStart,
    p_max_requests: RATE_LIMIT_MAX_REQUESTS,
  });

  if (error) {
    // Rate limit check failed → fail closed (deny) rather than allow
    console.error("[live-executor] Rate limit RPC error — denying request:", error);
    return false;
  }

  return data === true;
}
```

---

### Phase 7: Financial Accuracy (P2)
**Todos:** #118, #119, #126, #146

#### 7.1 — Use actual fill price for exit trades (#118)
**File:** `live-trading-executor/index.ts`, exit signal path (~line 659)

After placing the closing order, poll for fill price before recording the trade (same pattern as Phase 4.5):

```typescript
const closeOrderId = await placeMarketOrder(...);
const closeFill = await pollOrderFill(token.access_token, accountId, closeOrderId, 5_000);
const confirmedExitPrice = closeFill.fillPrice;
await closeLivePositionFromBracket(supabase, pos, confirmedExitPrice, "exit_signal");
```

#### 7.2 — Recalculate SL/TP from fill price before bracket placement (#119)
**File:** `live-trading-executor/index.ts`, lines 728–875 (after `pollOrderFill` returns)

```typescript
const fill = await pollOrderFill(token.access_token, accountId, entryOrderId);
const fillPrice = fill.fillPrice;

// Re-derive SL/TP from actual fill price, not bar close
const { sl, tp } = computeSLTP(strategy.config, fillPrice, direction, isFutures, multiplier);

// Use sl/tp (fill-based) for both bracket orders AND the DB record
await supabase.from("live_trading_positions")
  .update({
    status: "pending_bracket",
    entry_price: fillPrice,
    stop_loss_price: sl,     // Updated from fill price
    take_profit_price: tp,   // Updated from fill price
  })
  .eq("id", positionId);
```

Extract the SL/TP computation into a pure `computeSLTP` function so it can be called twice (pre-fill for validation, post-fill for actual values).

#### 7.3 — Bound summary query by date (#126)
**File:** `live-trading-executor/index.ts`, `handleSummary` function

Add `gte("exit_time", startOfDay)` filter:

```typescript
const startOfDay = new Date();
startOfDay.setHours(0, 0, 0, 0);

const { data } = await supabase
  .from("live_trading_trades")
  .select("pnl, direction")
  .eq("user_id", userId)
  .gte("exit_time", startOfDay.toISOString()) // Today only
  .order("exit_time", { ascending: false })
  .limit(1000); // Safety cap
```

Accept optional `date` query param to allow querying other periods.

#### 7.4 — Add date filter and pagination to `getBatchOrderStatus` (#146)
**File:** `_shared/tradestation-client.ts`, `getBatchOrderStatus` function

Pass a `since` parameter to limit order history:

```typescript
// Fetch orders from last 48 hours only
const since = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
const url = buildAccountUrl(accountId, `/orders?since=${encodeURIComponent(since)}`);
```

If the TradeStation API does not support `since`, use `limit=200` as a practical cap.

---

### Phase 8: API & Frontend (P2)
**Todos:** #123, #124, #125, #133, #134, #135, #136, #142, #143

#### 8.1 — `handleClose` user feedback (#123)
**File:** `frontend/src/components/LiveTradingDashboard.tsx` lines 122–133

```typescript
// Before: swallows error silently
// After:
try {
  await liveTradingApi.execute({ action: "close_position", positionId });
  toast.success("Position close order submitted");
} catch (err) {
  toast.error(`Failed to close position: ${err instanceof Error ? err.message : "Unknown error"}`);
}
```

#### 8.2 — Add `action` field to execute API call (#124)
**File:** `frontend/src/api/strategiesApi.ts` lines 53–58

```typescript
// Before: body missing action field
// After:
async execute(params: { action: string; positionId?: string; symbol?: string }) {
  const { data, error } = await supabaseClient.functions.invoke(
    "live-trading-executor",
    { body: { action: params.action, ...params } }
  );
  if (error) throw error;
  return data;
}
```

#### 8.3 — Narrow `OrderFillResult.status` type (#125)
**File:** `_shared/tradestation-client.ts`

```typescript
// Before:
status: string;

// After — use a discriminated union of known TradeStation statuses:
status:
  | "FLL"  // Filled
  | "FLP"  // Partial fill
  | "OPN"  // Open/pending
  | "CAN"  // Cancelled
  | "REJ"  // Rejected
  | "EXP"  // Expired
  | string; // Unknown (fallback)
```

#### 8.4 — Add server-side status filter to positions endpoint (#133)
**File:** `live-trading-executor/index.ts`, `handlePositions` function

```typescript
// Accept ?status=open|closed|all query param
const statusFilter = url.searchParams.get("status") ?? "open";

let query = supabase.from("live_trading_positions").select("*").eq("user_id", userId);
if (statusFilter !== "all") {
  query = query.eq("status", statusFilter);
}
```

#### 8.5 — Paused strategy response with context (#134)
When a strategy is paused, return a structured response instead of generic `no_action`:

```typescript
return {
  success: true,
  action: "skipped",
  reason: "strategy_paused",
  strategyId: strategy.id,
};
```

#### 8.6 — Circuit breaker response includes blocking rule (#135)
```typescript
// Before:
return { allowed: false, reason: "...", rule: "daily_loss" };

// The circuit breaker response is already typed — ensure it propagates to the HTTP response:
return jsonResponse({
  success: false,
  action: "circuit_breaker",
  rule: result.rule,      // "market_hours" | "daily_loss" | "max_positions" | "position_size_cap"
  reason: result.reason,
}, 200);
```

#### 8.7 — API client 429 rate limit handling (#136)
**File:** `frontend/src/api/strategiesApi.ts`

```typescript
const { data, error, status } = await supabaseClient.functions.invoke(...);
if (status === 429) {
  throw new Error("rate_limited: Too many trading requests. Please wait before retrying.");
}
if (error) throw error;
```

#### 8.8 — Extract `executeStrategy` sub-functions (#142)
**File:** `live-trading-executor/index.ts`, `executeStrategy` lines 620–933

Extract three focused functions:
- `runCircuitBreakers(supabase, userId, balance, strategy, latestPrice)` → `CircuitBreakerResult | null` (handles all 4 circuit breaker checks)
- `computeEntryParams(strategy, latestPrice, isFutures, tsSymbol)` → `{ direction, tradeAction, closeAction, sl, tp, qty }`
- `submitEntryWithBracket(supabase, token, accountId, position, params)` → covers market order → insert → poll → bracket → emergency close

Also evaluate signals once at the top of `executeStrategy`:
```typescript
const { entry: entrySignal, exit: exitSignal } = evaluateStrategySignals(
  strategy.config.entry_conditions ?? [],
  strategy.config.exit_conditions ?? [],
  bars,
);
```

#### 8.9 — `LiveTradingStatusWidget` use summary endpoint (#143)
**File:** `frontend/src/components/LiveTradingStatusWidget.tsx`

Replace the `positions` API call + client-side PnL loop with the `summary` endpoint:

```typescript
const [summary, brokerStatus] = await Promise.all([
  liveTradingApi.getSummary(),     // total_pnl, win_rate, total_trades
  liveTradingApi.getBrokerStatus(), // connected, provider, expires_at
]);
```

Label the displayed PnL as "Today's Realized P&L" to accurately describe what `summary.total_pnl` represents.

---

## System-Wide Impact

### Interaction Graph
- **Phase 1 type fixes** → No runtime change. Surfacing type errors may reveal additional issues.
- **Phase 2 migration** → Changes `symbol_id` column type + adds RPC + adds triggers. Requires `supabase db push` before redeploying the function.
- **Phase 3 CORS fix** → Affects all edge functions sharing `cors.ts`. Test with the frontend before deploying.
- **Phase 5 recovery scan** → New code path runs at the start of every execution cycle. Must be fast (< 100ms normally — only does work when stuck positions exist).
- **Phase 6.2 per-account bracket fills** → Behavioral change for users with both equity + futures accounts open simultaneously.

### Error & Failure Propagation
- Phase 6.3 (rate limit fail-closed) changes from "silent allow" to "deny and log" on DB error. Confirm `live_order_rate_limits` is accessible to the executor's service role.
- Phase 4.4 (checkBracketFills try/catch) prevents bracket errors from aborting the entire cycle. Strategy execution continues even if fill monitoring fails.

### State Lifecycle Risks
- Phase 3.1 CORS fix: if `allowed[0]` was relied upon by any frontend in production, changing to `""` will break those callers. Audit usage before deploying.
- Phase 2.3 FK change: CASCADE → RESTRICT on `user_id`. Confirm no test or admin script deletes users while live positions exist.

### Migration Ordering
Phases 1.3, 2 must be deployed **before** the updated Edge Function. The execution order is:
1. Apply migration `20260303120000_fix_live_trading_symbol_type.sql`
2. Apply migration `20260303130000_live_trading_infra_fixes.sql`
3. Deploy all Edge Functions atomically (includes `live-trading-executor` code fixes + `_shared/cors.ts` CORS fix + all 20 caller updates from Phase 3.1a — these must deploy together)

---

## Alternative Approaches Considered

**Symbol_id (#117): Resolve UUID from symbols table** vs **Change column to TEXT**
→ Chose TEXT. The live executor receives raw symbols from the frontend. A UUID lookup would require an additional DB round trip per execution cycle in the already time-constrained 60s window. TEXT is consistent with `live_trading_trades.symbol`.

**Exit price (#118, #140): Store estimated + reconcile later** vs **Poll on every close**
→ Chose poll-on-close with a 5s timeout + fallback. The 5s timeout is within budget (cycle has ~40s left after entry). Reconciliation adds operational complexity and a perpetually "unconfirmed" P&L state.

**Rate limiter (#115, #141): Keep dual-path with fixed fallback** vs **Single atomic RPC path**
→ Chose single RPC path. The fallback's silent-allow behavior is a direct security bypass for a rate limiter on real-money orders.

---

## Acceptance Criteria

### P1 — Must pass before merge
- [ ] `deno check supabase/functions/live-trading-executor/index.ts` — no type errors
- [ ] `deno check supabase/functions/_shared/tradestation-client.ts` — no type errors
- [ ] `deno lint supabase/functions/` — no `no-explicit-any` violations in either file
- [ ] First live trade does not crash with UUID type mismatch (#117)
- [ ] `cancelOrder` response.ok is checked; failed cancels are logged (#109)
- [ ] Market order is cancelled on all DB insert failures, not only 23505 (#110)
- [ ] `ensureFreshToken` re-read path is null-guarded (#111)
- [ ] `checkBracketFills` wrapped in try/catch; errors do not abort cycle (#112)
- [ ] CORS: unknown origins receive no CORS grant (empty string), not `allowed[0]` (#114)
- [ ] CORS: all 20 caller functions updated to pass `origin` before `getCorsHeaders` fix deploys (#168)
- [ ] `increment_rate_limit` RPC exists in DB; `checkRateLimit` fallback removed (#115, #141)
- [ ] `checkBracketFills` groups by position's `account_id`, not outer-scope ID (#116)
- [ ] Positions stuck in `pending_bracket` older than 2 minutes are emergency-closed (#108)
- [ ] Manual and exit-signal closes poll and record actual broker fill price (#140)
- [ ] `total` in paginated responses reflects DB row count, not page size (#132)

### P2 — Should pass before merge
- [ ] SL/TP recalculated from fill price before bracket placement (#119)
- [ ] `live_trading_positions.updated_at` auto-updates on every UPDATE (#120)
- [ ] Both FK delete policies are `RESTRICT` (#121)
- [ ] `live_trading_trades` has CHECK constraints on price, quantity, close_reason (#122)
- [ ] `handleClose` shows toast/error to user on failure (#123)
- [ ] Execute API includes `action` field (#124)
- [ ] `OrderFillResult.status` uses union type (#125)
- [ ] Summary endpoint bounded to today by default (#126)
- [ ] Positions endpoint accepts `?status=` filter (#133)
- [ ] Paused strategy returns structured `{ action: "skipped", reason: "strategy_paused" }` (#134)
- [ ] Circuit breaker response includes `rule` and `reason` (#135)
- [ ] API client handles 429 with user-facing message (#136)
- [ ] `getBatchOrderStatus` fetches at most 48h of order history (#146)
- [ ] `executeStrategy` split into ≤3 focused sub-functions (#142)
- [ ] `LiveTradingStatusWidget` uses summary endpoint; PnL labeled accurately (#143)

### Quality Gates
- [ ] `deno lint supabase/functions/` passes
- [ ] `deno fmt --check supabase/functions/` passes
- [ ] Pre-deploy SQL audits from `docs/DEPLOYMENT_VERIFICATION_PR28_LIVE_TRADING.md` pass
- [ ] Manual test: submit a `GET ?action=broker_status` request returns 401 without auth

---

## Dependencies & Prerequisites

- **Supabase CLI** — `npx supabase db push` to apply migrations
- **TradeStation SIM** — Required for end-to-end testing. Set `TRADESTATION_USE_SIM=true`.
- **Phase ordering** — Migrations must be applied before function deployment (see System-Wide Impact above)
- **CORS change coordination** — `cors.ts` is shared. Any frontend that relied on the CORS fallback behavior must be updated first.

---

## Risk Analysis

| Risk | Mitigation |
|------|-----------|
| CORS fix breaks existing frontend calls | 20 caller functions must be updated in the same PR as the `getCorsHeaders` fix. Since `supabase functions deploy` is atomic (all functions deploy together), both changes deploy simultaneously. **Never deploy the `getCorsHeaders` fix without the caller updates.** See Phase 3.1a for the full caller audit list. |
| FK CASCADE→RESTRICT migration fails if open positions exist at deploy time | Run Phase 2 migration during off-hours (market closed). Verify 0 open positions first. |
| Phase 5 recovery scan adds latency | Only does work when stuck positions exist. Bounded query with index on `order_submitted_at`. |
| `symbol_id` type change requires re-indexing | Done in the migration. Downtime is < 1 second on an empty table. |
| Exponential backoff increases fill wait time | Max delay is 5s (same total budget). Net effect: slightly faster detection on fast fills. |

---

## Sources & References

### Internal References
- All 32 P1+P2 todo files: `todos/108-pending-p1-*.md` through `todos/146-pending-p2-*.md`
- Primary patterns: `docs/LIVE_TRADING_EXECUTOR_INSTITUTIONAL_LEARNINGS.md`
- Deployment checklist: `docs/DEPLOYMENT_VERIFICATION_PR28_LIVE_TRADING.md`
- Original feature plan: `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md`
- CORS utility: `supabase/functions/_shared/cors.ts:81–95`
- Rate limiter: `supabase/functions/live-trading-executor/index.ts:111–152`
- Paper trading executor (template): `supabase/functions/paper-trading-executor/index.ts`
- Strategies GET handler: `supabase/functions/strategies/index.ts:122`
- Live trading migration: `supabase/migrations/20260303110000_live_trading_tables.sql`

### Related Work
- PR #28: feat/live-trading-executor-tradestation (https://github.com/PapaPablano/SwiftBolt_ML/pull/28)
- Previous executor: `supabase/functions/paper-trading-executor/index.ts` (reference implementation)
