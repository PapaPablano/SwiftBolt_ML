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
// #156: Use import map specifier (not bare esm.sh URL) to prevent version drift
import type { SupabaseClient } from "@supabase/supabase-js";
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

-- Re-create affected indexes using CORRECT EXISTING NAMES (#152)
-- Original names from 20260303110000_live_trading_tables.sql lines 86+91
DROP INDEX IF EXISTS idx_live_positions_active_unique;
DROP INDEX IF EXISTS idx_live_positions_user_strategy;

CREATE UNIQUE INDEX idx_live_positions_active_unique
  ON live_trading_positions (user_id, strategy_id, symbol_id)
  WHERE status IN ('pending_entry', 'pending_bracket', 'open');

CREATE INDEX idx_live_positions_user_strategy
  ON live_trading_positions (user_id, strategy_id, symbol_id, status, created_at DESC);
```

---

### Phase 2: Database & Infrastructure (P1 + P2)
**Todos:** #115, #120, #121, #122
**New migration:** `supabase/migrations/20260303130000_live_trading_infra_fixes.sql`

#### 2.1 — Define `increment_rate_limit` RPC (#115, #153, #169, #170)
```sql
CREATE OR REPLACE FUNCTION increment_rate_limit(
  p_user_id      UUID,
  p_window_start TIMESTAMPTZ,
  p_max_requests INT
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp  -- #170: prevent search_path hijacking
AS $$
DECLARE v_count INT;
BEGIN
  -- #169: Defense in depth — reject cross-user calls
  IF auth.uid() IS DISTINCT FROM p_user_id THEN
    RAISE EXCEPTION 'unauthorized: caller % cannot increment rate limit for %',
      auth.uid(), p_user_id
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  -- #153: Two-statement form (upsert + SELECT) because
  -- RETURNING...INTO after INSERT ON CONFLICT DO UPDATE is invalid PL/pgSQL
  INSERT INTO live_order_rate_limits (user_id, window_start, request_count)
  VALUES (p_user_id, p_window_start, 1)
  ON CONFLICT (user_id, window_start)
  DO UPDATE SET request_count = live_order_rate_limits.request_count + 1;

  SELECT request_count INTO v_count
  FROM live_order_rate_limits
  WHERE user_id = p_user_id AND window_start = p_window_start;

  RETURN v_count <= p_max_requests;
END;
$$;

-- #169: Revoke public access; only service_role should call this RPC
REVOKE EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) FROM anon;
REVOKE EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) FROM authenticated;
GRANT EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) TO service_role;
```

> **Note:** The executor must use the `service_role` key (not anon key) to call this RPC.

#### 2.2 — Add `updated_at` auto-update trigger to `live_trading_positions` (#120, #158)
```sql
CREATE OR REPLACE FUNCTION update_live_positions_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- #158: Drop-then-create for idempotency (matches paper trading migration convention)
DROP TRIGGER IF EXISTS live_positions_updated_at ON live_trading_positions;
CREATE TRIGGER live_positions_updated_at
  BEFORE UPDATE ON live_trading_positions
  FOR EACH ROW EXECUTE FUNCTION update_live_positions_updated_at();
```

#### 2.3 — Fix FK delete inconsistency (#121, #166)
`live_trading_trades.user_id` uses `ON DELETE RESTRICT`; `live_trading_positions.user_id` uses `ON DELETE CASCADE`. Both should be `RESTRICT` — never silently delete financial records when a user is deleted.

```sql
-- Re-create FK on live_trading_positions to use RESTRICT instead of CASCADE
-- #166: Changing CASCADE → RESTRICT: financial records must never be silently deleted.
-- GDPR deletion requires manual ordered purge:
--   1. DELETE FROM live_trading_trades WHERE user_id = $1;
--   2. DELETE FROM live_trading_positions WHERE user_id = $1;
--   3. DELETE FROM auth.users WHERE id = $1;
-- Note: live_trading_trades.position_id has ON DELETE NO ACTION (RESTRICT default),
--       so step 1 must precede step 2.
-- The system has no automated GDPR purge path — this is intentional (financial audit).
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
      -- #154: Match UPPERCASE casing from live_trading_positions CHECK constraint
      'SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE',
      'GAP_FORCED_CLOSE', 'PARTIAL_FILL_CANCELLED',
      'BROKER_ERROR', 'BRACKET_PLACEMENT_FAILED',
      'EMERGENCY_CLOSE',     -- new: Phase 5 recovery scan
      'CIRCUIT_BREAKER'      -- new: Phase 8.6
    )),
  -- #167: Sanity bounds on pnl — catches multiplier bugs before they enter the immutable audit trail
  -- Assumes max 10% position size and maximum realistic account equity ~$10M
  ADD CONSTRAINT live_trades_pnl_sane
    CHECK (pnl BETWEEN -1000000 AND 1000000),
  ADD CONSTRAINT live_trades_pnl_pct_sane
    CHECK (pnl_pct IS NULL OR pnl_pct BETWEEN -1000 AND 1000);
```

---

### Phase 3: CORS Security & Pagination (P1)
**Todos:** #114, #132

#### 3.1 — Fix CORS echoing unknown origins (#114, #159)
**File:** `supabase/functions/_shared/cors.ts` line 85–87

Current behavior: Unknown origins receive `allowed[0]` (e.g., `https://swiftbolt.app`) as the CORS response — this is a bypass vector.

Fix: Conditionally omit the `Access-Control-Allow-Origin` header for unknown origins (#159 — omitting the header is RFC-compliant; an empty string value is not):
```typescript
// Before:
const responseOrigin = origin && allowed.includes(origin)
  ? origin
  : allowed[0];  // BUG: echoes first allowed origin to all callers

// After (#159): Conditionally include Access-Control-Allow-Origin
export function getCorsHeaders(origin: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Max-Age": "86400",
  };

  if (origin && allowed.includes(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
  }
  // If origin not in allowlist, header is omitted entirely (no CORS grant)

  return headers;
}
```

> **Deployment prerequisite:** Verify `ALLOWED_ORIGINS` is set in Supabase Secrets for all environments before deploying. Run `grep -r 'getCorsHeaders' supabase/functions/` to audit all callers.

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
// #175: Add has_more boolean for deterministic agent pagination
return {
  positions: data,
  total: count ?? 0,
  limit,
  offset,
  has_more: (offset + limit) < (count ?? 0),
};
```

Apply `has_more` consistently to all three paginated endpoints: `?action=positions`, `?action=trades`, `?action=summary`.

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

Fix: Cancel the market order on any insert failure. Use a `cancelOnce` guard to prevent double-cancel (#149 — the original try/catch nesting called `cancelOrder` twice on non-23505 errors). The `cancelOnce` function checks `cancelled.ok` (#172 — if cancel fails, the position may be open at the broker with no DB record; this must be logged as a critical alert for manual investigation):

```typescript
// #149: cancelOnce prevents double-cancel when the rethrown error hits the outer catch
let cancelCalled = false;
const cancelOnce = async () => {
  if (!cancelCalled) {
    cancelCalled = true;
    try {
      const cancelled = await cancelOrder(token.access_token, accountId, entryOrderId);
      if (!cancelled.ok) {
        console.error(`[live-executor] cancelOrder failed (${cancelled.status}) for order ${entryOrderId}`);
      }
    } catch (cancelErr) {
      console.error("[live-executor] CRITICAL: cancelOrder threw — position may be untracked at broker", cancelErr);
    }
  }
};

const { error: insertError } = await supabase.from("live_trading_positions").insert({...});
if (insertError) {
  await cancelOnce();
  if (insertError.code !== "23505") {
    throw insertError; // Non-duplicate errors propagate after cancel
  }
  // 23505 = duplicate position already exists — normal race condition, cancel succeeded
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

#### 4.5 — Poll fill price after manual close (#140, #155)
**File:** `live-trading-executor/index.ts`, `closeLivePosition` function

**Prerequisite:** Add optional `timeoutMs` parameter to `pollOrderFill` (#155 — the current signature only accepts 3 args):
```typescript
// Updated signature (backward-compatible default):
async function pollOrderFill(
  accessToken: string,
  accountId: string,
  orderId: string,
  timeoutMs: number = POLL_TIMEOUT_MS,  // defaults to 15s
): Promise<OrderFillResult> {
  const deadline = Date.now() + timeoutMs;
  // ... existing poll loop uses deadline instead of POLL_TIMEOUT_MS
}
```

**#182 — Integration boundary:** The poll is called in the handler (Option B — not inside `closeLivePosition`). The handler polls for the fill price, then passes the actual fill price as the `exitPrice` argument to `closeLivePosition`. This avoids a signature change to `closeLivePosition` and keeps the poll explicit at the call site:

After placing the closing market order, poll for the actual fill price:

```typescript
const closeOrderId = await placeMarketOrder(token.access_token, accountId, closeAction, qty, symbol);

// Poll for actual fill — 10s timeout for close orders (not 5s: illiquid assets may take longer)
let closeFill: OrderFillResult;
try {
  closeFill = await pollOrderFill(token.access_token, accountId, closeOrderId, 10_000);
  exitPrice = closeFill.fillPrice;
} catch {
  // Poll timed out — use current_price as approximation, flag for reconciliation
  console.warn(`[live-executor] Close fill poll timed out for order ${closeOrderId} — using estimated price`);
  // exitPrice remains current_price (already set)
  // NOTE: This is the fallback that #140 is designed to minimize. For illiquid assets,
  // the 10s timeout may still be insufficient. Manual reconciliation is required.
}
```

---

### Phase 5: State Machine Recovery (P1)
**Todo:** #108
**Files:** `live-trading-executor/index.ts`

This is the highest-consequence fix. A position stuck in `pending_bracket` with no SL/TP orders is an unprotected open position with real market risk.

#### 5.1 — Add stuck-position recovery scan (#108, #150, #151, #179, #180)

Add a `recoverStuckPositions` function called at the top of `executeLiveTradingCycle` (before the per-strategy loop).

**Call site — must be wrapped in try/catch (#179):**
```typescript
// Recovery failure must not abort the entire execution cycle
try {
  await recoverStuckPositions(supabase, token, accountId, userId);
} catch (err) {
  console.error("[live-executor] recovery_scan_failed — continuing with strategy execution", err);
}
```

**Implementation — with concurrency guard (#151) and NULL handling (#180):**
```typescript
// #163: Use 5 minutes (per institutional learnings doc Section 8), not 2 minutes.
// 2min is too aggressive — broker slowdowns during market open/close can take 60-90s per cycle.
// Configurable via env var for operational tuning (min: 180s, max: 600s).
const thresholdSeconds = Math.min(
  Math.max(
    parseInt(Deno.env.get("STUCK_POSITION_THRESHOLD_SECONDS") ?? "300", 10),
    180,  // minimum: 3 minutes
  ),
  600,    // maximum: 10 minutes
);
const STUCK_POSITION_THRESHOLD_MS = thresholdSeconds * 1000;

async function recoverStuckPositions(
  supabase: Db, token: BrokerToken, accountId: string, userId: string
): Promise<void> {
  const threshold = new Date(Date.now() - STUCK_POSITION_THRESHOLD_MS).toISOString();

  // #180: Include positions with NULL order_submitted_at (NULL < value = NULL, excluded by .lt())
  const { data: stuckPositions } = await supabase
    .from("live_trading_positions")
    .select("*")
    .eq("user_id", userId)
    .in("status", ["pending_entry", "pending_bracket"])
    .or(`order_submitted_at.lt.${threshold},order_submitted_at.is.null`);

  for (const pos of (stuckPositions ?? [])) {
    // #179: Per-position try/catch — one failing position must not abort the entire scan
    try {
      // #151: Optimistic status transition — claim position before any broker call
      // to prevent concurrent invocations from double-closing
      const { data: claimed } = await supabase
        .from("live_trading_positions")
        .update({ status: "closing_emergency" })
        .eq("id", pos.id)
        .in("status", ["pending_entry", "pending_bracket"])
        .select()
        .single();

      if (!claimed) {
        // Another invocation already claimed this position — skip
        continue;
      }

      if (pos.status === "pending_entry" && pos.broker_order_id) {
        // Re-poll entry fill — getOrderStatus may 404 for aged-out orders
        let fill: OrderFillResult | null = null;
        try {
          fill = await getOrderStatus(token.access_token, pos.account_id ?? accountId, pos.broker_order_id);
        } catch {
          // Order not found (404) or API error — treat as unknown state
          console.error(`[live-executor] getOrderStatus failed for ${pos.broker_order_id} — treating as filled (emergency close)`);
        }

        if (!fill || fill.filledQuantity > 0) {
          // #150: Entry filled (or unknown) — EMERGENCY CLOSE, not advance to open
          // A position without brackets is unprotected live capital
          console.error(
            `[live-executor] CRITICAL: Position ${pos.id} filled in pending_entry but no brackets placed. Emergency closing.`
          );
          await closeLivePosition(
            supabase,
            token.access_token,        // #151: correct arg count (7 args, not 4)
            pos.account_id ?? accountId,
            claimed,
            claimed.current_price ?? claimed.entry_price,
            "EMERGENCY_CLOSE",
            claimed.symbol_id,
          );
        } else {
          // Not filled — cancel the order and set cancelled
          await cancelOrder(token.access_token, pos.account_id ?? accountId, pos.broker_order_id);
          await supabase.from("live_trading_positions")
            .update({ status: "cancelled" })
            .eq("id", pos.id).eq("status", "closing_emergency");
        }
      } else if (pos.status === "pending_bracket") {
        // Entry filled but bracket not placed — emergency close
        console.error(`[live-executor] ALERT: Stuck pending_bracket position ${pos.id} — initiating emergency close`);
        await closeLivePosition(
          supabase,
          token.access_token,
          pos.account_id ?? accountId,
          claimed,
          claimed.current_price ?? claimed.entry_price,
          "EMERGENCY_CLOSE",
          claimed.symbol_id,
        );
      }
    } catch (err) {
      console.error(`[live-executor] recovery_position_failed for ${pos.id}`, err);
      // Continue to next position — do not abort scan
    }
  }
}
```

> **Note:** Requires adding `'closing_emergency'` to the `live_trading_positions.status` CHECK constraint in the migration. Also requires `order_submitted_at` to have `NOT NULL DEFAULT NOW()` (add to Phase 1.3 migration) to prevent future NULL insertions.
>
> **#187:** Also add `'EMERGENCY_CLOSE'` and `'CIRCUIT_BREAKER'` to the `live_trading_positions.close_reason` CHECK constraint. Without this, Phase 5's `closeLivePosition(..., "EMERGENCY_CLOSE")` will fail the DB write even when the broker-side close order succeeds — leaving the position stuck despite a successful broker close:
> ```sql
> ALTER TABLE live_trading_positions
>   DROP CONSTRAINT live_trading_positions_close_reason_check,
>   ADD CONSTRAINT live_trading_positions_close_reason_check
>     CHECK (close_reason IS NULL OR close_reason IN (
>       'SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE',
>       'GAP_FORCED_CLOSE', 'PARTIAL_FILL_CANCELLED',
>       'BROKER_ERROR', 'BRACKET_PLACEMENT_FAILED',
>       'EMERGENCY_CLOSE', 'CIRCUIT_BREAKER'
>     ));
> ```

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
  delay = Math.floor(Math.min(delay * 1.5, MAX_DELAY)); // #165: Math.floor for integer ms in logs
  // 500 → 750 → 1125 → 1687 → 2531 → 3796 → 5000
}
throw new Error("fill_poll_timeout");
```

Total budget is still bounded by `POLL_TIMEOUT_MS = 15_000`.

#### 6.2 — Per-position `account_id` in `checkBracketFills` (#116, #160, #162)
**File:** `live-trading-executor/index.ts`, `checkBracketFills` function

> **Prerequisite (#160):** Phase 7.4 must be implemented before or together with Phase 6.2. Phase 6.2 increases `getBatchOrderStatus` calls from 1 to N (one per account). Without the date filter from Phase 7.4, this multiplies the unbounded payload problem.

Group open positions by their stored `account_id` column and issue one `getBatchOrderStatus` call per distinct account. **#162:** Skip positions with missing `account_id` (not fallback to current account — wrong account is worse than no check):

```typescript
// Group positions by account_id
const byAccount = new Map<string, typeof positions>();
for (const pos of positions) {
  // #162: Skip positions with no account_id — fallback to current account risks
  // routing bracket fill checks to wrong account (e.g., equity instead of futures)
  if (!pos.account_id) {
    console.error(`[live-executor] ALERT: Position ${pos.id} has no account_id — skipping bracket fill check. Manual review required.`);
    continue;
  }
  if (!byAccount.has(pos.account_id)) byAccount.set(pos.account_id, []);
  byAccount.get(pos.account_id)!.push(pos);
}

for (const [acct, acctPositions] of byAccount) {
  const orderIds = acctPositions.flatMap(p =>
    [p.broker_sl_order_id, p.broker_tp_order_id].filter(Boolean)
  );
  const fills = await getBatchOrderStatus(token.access_token, acct, orderIds);
  // ... process fills for acctPositions
}
```

> **Note:** `account_id NOT NULL` constraint in the migration prevents this in production, but the defensive code provides belt-and-suspenders for data migrated before the constraint was added.

#### 6.3 — Remove silent always-allow fallback from `checkRateLimit` (#141, #171)
**File:** `live-trading-executor/index.ts` lines 126–151

Now that the `increment_rate_limit` RPC exists (Phase 2.1), remove the manual fallback path. **#171:** Distinguish DB errors from genuine rate limits so the handler returns the correct HTTP status (503 for transient DB errors, 429 for genuine rate limits):

```typescript
interface RateLimitResult {
  allowed: boolean;
  reason?: "rate_limited" | "db_error";
}

async function checkRateLimit(supabase: Db, userId: string): Promise<RateLimitResult> {
  const windowStart = new Date(
    Math.floor(Date.now() / RATE_LIMIT_WINDOW_MS) * RATE_LIMIT_WINDOW_MS,
  ).toISOString();

  try {
    const { data, error } = await supabase.rpc("increment_rate_limit", {
      p_user_id: userId,
      p_window_start: windowStart,
      p_max_requests: RATE_LIMIT_MAX_REQUESTS,
    });

    if (error) {
      // #171: DB error — fail closed but distinguishable from genuine rate limit
      console.error("rate_limit_rpc_failed", { userId, error: error.message });
      return { allowed: false, reason: "db_error" };
    }

    const allowed = data === true;
    return { allowed, reason: allowed ? undefined : "rate_limited" };
  } catch (err) {
    console.error("rate_limit_rpc_exception", { userId, error: (err as Error).message });
    return { allowed: false, reason: "db_error" };
  }
}

// In the handler:
const rateLimitResult = await checkRateLimit(supabase, userId);
if (!rateLimitResult.allowed) {
  if (rateLimitResult.reason === "db_error") {
    // Transient DB error — 503, retry in 5s (not 60s)
    return corsResponse({ error: "rate_limit_unavailable", retryable: true }, 503, origin);
  }
  // Genuine rate limit — 429 with Retry-After
  return new Response(
    JSON.stringify({ error: "rate_limited", retryAfterSec: 60 }),
    { status: 429, headers: { ...getCorsHeaders(origin), "Retry-After": "60" } }
  );
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

#### 7.3 — Bound summary query by date (#126, #189)
**File:** `live-trading-executor/index.ts`, `handleSummary` function

Add `gte("exit_time", startOfDay)` filter. **#189:** Use Eastern Time (not UTC) for start-of-day boundary — the trading day starts at midnight ET. Extract `getETStartOfDay()` as a shared utility since `checkDailyLossLimit` already has the same ET logic:

```typescript
// Extract to _shared/trading-time.ts for reuse by checkDailyLossLimit and handleSummary
function getETStartOfDay(): Date {
  const now = new Date();
  const etFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric", month: "2-digit", day: "2-digit",
  });
  const parts = etFormatter.formatToParts(now);
  const year = parts.find(p => p.type === "year")?.value;
  const month = parts.find(p => p.type === "month")?.value;
  const day = parts.find(p => p.type === "day")?.value;
  // America/New_York handles EST/EDT automatically
  return new Date(`${year}-${month}-${day}T00:00:00`);
}

const startOfDay = getETStartOfDay();

const { data } = await supabase
  .from("live_trading_trades")
  .select("pnl, direction")
  .eq("user_id", userId)
  .gte("exit_time", startOfDay.toISOString()) // Today (ET) only
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

#### 8.1 — `handleClose` user feedback (#123, #183)
**File:** `frontend/src/components/LiveTradingDashboard.tsx` lines 122–133

**#183:** The executor can return HTTP 200 with `{ success: false, error: "..." }`. `invokeFunction` only checks HTTP status, so `{ success: false }` does not throw. Must check response body's `success` field explicitly:

```typescript
// Before: swallows error silently (also misses HTTP 200 + success:false)
// After:
try {
  const result = await liveTradingApi.execute({ action: "close_position", positionId });
  // #183: Check application-level success, not just HTTP status
  if (result && !result.success) {
    throw new Error(result.error ?? "Close position failed");
  }
  toast.success("Position close order submitted");
} catch (err) {
  toast.error(`Failed to close position: ${err instanceof Error ? err.message : "Unknown error"}`);
}
```

Apply this `result.success` check pattern consistently to all executor POST operations in the frontend: `close_position`, `save_broker_token`, `disconnect_broker`, `recover_positions`.

#### 8.2 — Add `action` field to execute API call (#124, #192)
**File:** `frontend/src/api/strategiesApi.ts` lines 53–58

> **#192 — Note:** The server does not require `action: "execute"` today — any POST with `symbol` and `timeframe` that does not match a named action falls through to the execution cycle. Adding `action: "execute"` is a defensive improvement for code clarity and forward-compatibility (if the `default` branch is removed in a future refactor), not a bug fix.

```typescript
// Before: body missing action field (works today, but not explicit)
// After (defensive improvement):
async execute(params: { action: string; positionId?: string; symbol?: string }) {
  const { data, error } = await supabaseClient.functions.invoke(
    "live-trading-executor",
    { body: { action: params.action, ...params } }
  );
  if (error) throw error;
  return data;
}
```

#### 8.3 — Narrow `OrderFillResult.status` type (#125, #161)
**File:** `_shared/tradestation-client.ts`

```typescript
// Before:
status: string;

// After — #161: use known TradeStation status codes (FPR, not FLP, for partial fills):
type KnownOrderStatus =
  | "FLL"  // Fully filled
  | "FPR"  // Partial fill (#161: NOT "FLP" — executor lines 302+849 use "FPR")
  | "OPN"  // Open/working
  | "CAN"  // Cancelled
  | "REJ"  // Rejected
  | "EXP"  // Expired
  // Broker also uses full English strings for some codes:
  | "Filled"
  | "Partial Fill"
  | "Canceled"
  | "Rejected";

export interface OrderFillResult {
  filledQuantity: number;
  fillPrice: number;
  status: KnownOrderStatus | string;  // | string: broker may send undocumented codes
}
```

#### 8.4 — Add server-side filters to positions endpoint (#133, #176)
**File:** `live-trading-executor/index.ts`, `handlePositions` function

```typescript
// Accept ?status=open|closed|all query param
const statusFilter = url.searchParams.get("status") ?? "open";
// #176: Accept ?strategy_id=UUID for per-strategy position queries
const strategyIdFilter = url.searchParams.get("strategy_id");

let query = supabase.from("live_trading_positions").select("*").eq("user_id", userId);
if (statusFilter !== "all") {
  query = query.eq("status", statusFilter);
}
if (strategyIdFilter) {
  query = query.eq("strategy_id", strategyIdFilter);
}
```

> **Agent pre-execution check:** `GET ?action=positions&status=open&strategy_id=<uuid>` — the canonical query for "Are there open positions for this strategy?" Uses `idx_live_positions_user_strategy` index.

#### 8.5 — Paused strategy response with context (#134, #173)
When a strategy is paused, return a structured response with recovery context instead of generic `no_action`:

```typescript
return {
  success: true,
  action: "skipped",
  reason: "strategy_paused",
  strategyId: strategy.id,
  paused_at: strategy.live_trading_paused_at ?? null,  // #173: ISO 8601 timestamp
  suggested_action: "unpause_strategy",                // #173: agent-actionable recovery hint
};
```

> **Schema dependency (#173):** Add `live_trading_paused_at TIMESTAMPTZ` column to the strategies table. Set to `NOW()` when `live_trading_paused = true`, null when unpaused. Valid `suggested_action` values: `"unpause_strategy"` | `"contact_support"`.
>
> **#184 — Consumer note:** The `results[]` array containing paused-strategy data has no identified frontend consumer. Execution is triggered by an external cron/webhook, and neither `LiveTradingDashboard` nor `LiveTradingStatusWidget` calls `execute`. Phase 8.5's structured response provides value as **log observability only** — the structured data appears in Edge Function logs for operational alerting. Follow-up: build a cron-side log consumer or frontend component that surfaces paused-strategy warnings.

#### 8.6 — Circuit breaker response includes blocking rule, reset timing, and recovery hint (#135, #174)
```typescript
// #174: Add reset_at and suggested_action so agents know WHEN and HOW to recover
return jsonResponse({
  success: false,
  action: "circuit_breaker",
  rule: result.rule,
  reason: result.reason,
  reset_at: computeResetTimestamp(result.rule),     // ISO 8601 or null
  suggested_action: circuitBreakerAction(result.rule), // agent-actionable hint
}, 200);
```

**Helper functions (#174):**
```typescript
function computeResetTimestamp(rule: string): string | null {
  switch (rule) {
    case "market_hours": return nextMarketOpen().toISOString();  // extract from checkMarketHours
    case "daily_loss":   return endOfTradingDay().toISOString(); // midnight ET
    case "max_positions": return null;                           // depends on position closes
    case "position_size_cap": return null;                       // immediate if config changed
    default: return null;
  }
}

function circuitBreakerAction(rule: string): string {
  switch (rule) {
    case "market_hours": return "wait_for_market_open";
    case "daily_loss":   return "wait_for_daily_reset";
    case "max_positions": return "wait_for_position_close";
    case "position_size_cap": return "reduce_position_size";
    default: return "contact_support";
  }
}
```

> **Prerequisite:** Extract `nextMarketOpen()` from `checkMarketHours()` as a reusable utility so it can be used in the response payload.

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

**#185 — Semantic change:** This replaces *unrealized* P&L (computed from open positions) with *realized* P&L (from closed trades). A user with profitable open positions and no closed trades today will see "$0" instead of live gains. Label the displayed PnL as **"Today's Realized P&L"** to distinguish from unrealized. Consider showing both: "Open P&L" (from positions) and "Today's P&L" (from summary) — but at minimum, the label must be accurate to avoid UX confusion.

#### 8.10 — Add `disconnect_broker` open position safeguard (#186)
**File:** `live-trading-executor/index.ts`, `disconnect_broker` handler

Disconnecting while holding live positions disables bracket fill monitoring — SL/TP orders at the broker are never detected. Add a guard:

```typescript
case "disconnect_broker": {
  // #186: Check for open positions before revoking broker token
  const { count } = await supabase
    .from("live_trading_positions")
    .select("id", { count: "exact", head: true })
    .eq("user_id", user.id)
    .in("status", ["open", "pending_entry", "pending_bracket"]);
  if (count && count > 0) {
    return corsResponse({
      success: false,
      error: `Cannot disconnect: ${count} open position(s). Close all positions first.`,
      open_position_count: count,
    }, 409, origin);
  }
  await supabase.from("broker_tokens").delete().eq("user_id", user.id);
  return corsResponse({ success: true }, 200, origin);
}
```

Frontend: add confirmation dialog on "Disconnect Broker" button warning about SL/TP monitoring loss when positions exist.

#### 8.11 — Add standalone `recover_positions` endpoint (#181)
**File:** `live-trading-executor/index.ts`, POST handler switch

`recoverStuckPositions` only runs during execution cycles. A position stuck on a low-volume symbol with no signals has no manual escape path. Add a standalone trigger:

```typescript
case "recover_positions":
  // Runs recovery for all user positions — no symbol/timeframe needed
  await recoverStuckPositions(supabase, token, accountId, userId);
  return corsResponse({ success: true, action: "recover_positions" }, 200, origin);
```

Also extend `close_position` to accept `pending_bracket` positions (currently restricted to `status = 'open'`):
```typescript
// Before: .eq("status", "open")
// After:
.in("status", ["open", "pending_bracket"])
```

#### 8.12 — Opposite-leg cancellation in `checkBracketFills` (#188)
**File:** `live-trading-executor/index.ts`, `checkBracketFills` function

When SL fills, the TP order remains live (and vice versa). If price reverses, the orphaned order creates an untracked position.

> **Prerequisite:** Determine whether TradeStation `BRK` order type is OCO (auto-cancel). Test on SIM: place bracket order, trigger SL, check if TP auto-cancels. If `BRK` is OCO, add a code comment documenting this; no code change needed.

If `BRK` is NOT OCO:
```typescript
if (orderStatuses.sl?.filled) {
  await closeLivePositionFromBracket(supabase, pos, slFillPrice, "SL_HIT");
  // Cancel the unfilled TP leg
  if (pos.broker_tp_order_id) {
    const cancelled = await cancelOrder(accessToken, accountId, pos.broker_tp_order_id);
    if (!cancelled.ok) {
      console.error("cancel_opposite_leg_failed", {
        filledLeg: "SL", orderId: pos.broker_tp_order_id,
      });
    }
  }
}
// Mirror for TP fill → cancel SL
```

---

### Phase 1.3 Addendum: Rollback Documentation (#164)

Phase 1.3 (UUID→TEXT) is a **one-way migration** once non-UUID strings are written to `symbol_id`.

| Direction | Safe? | Notes |
|-----------|-------|-------|
| Forward (UUID→TEXT) | Yes | UUID strings are valid TEXT; implicit cast succeeds |
| Rollback (before non-UUID data) | Yes | `ALTER COLUMN symbol_id TYPE UUID USING symbol_id::uuid` succeeds |
| Rollback (after non-UUID data) | **No** | Cast fails on "AAPL", "@ES", etc. Requires data deletion first |

**Recommendation:** Take a row-count snapshot before migration and verify 0 rows in `live_trading_positions` before applying if a rollback path must be preserved.

---

### Phase 5 Addendum: Recovery Observability (#177)

`recoverStuckPositions` produces `console.error` logs only — there is no queryable API for recovery events. Agents must poll for positions with `close_reason = 'EMERGENCY_CLOSE'` to detect recovery actions.

**Follow-up:** Add `close_reason` as a server-side filter on the trades GET endpoint (alongside the `?status=` filter in Phase 8.4), enabling: `GET ?action=trades&close_reason=EMERGENCY_CLOSE&since=<ISO>`.

---

### Phase 6 Addendum: Rate Limit Status Endpoint (#178)

Add `GET ?action=rate_limit_status` to allow agents to check headroom before submitting execution requests:

```typescript
if (action === "rate_limit_status") {
  const windowStart = new Date(
    Math.floor(Date.now() / RATE_LIMIT_WINDOW_MS) * RATE_LIMIT_WINDOW_MS,
  ).toISOString();
  const { data } = await supabase
    .from("live_order_rate_limits")
    .select("request_count")
    .eq("user_id", user.id)
    .eq("window_start", windowStart)
    .maybeSingle();
  const requestsUsed = data?.request_count ?? 0;
  return corsResponse({
    requests_used: requestsUsed,
    requests_remaining: Math.max(0, RATE_LIMIT_MAX_REQUESTS - requestsUsed),
    limit: RATE_LIMIT_MAX_REQUESTS,
    window_resets_at: new Date(
      Math.ceil(Date.now() / RATE_LIMIT_WINDOW_MS) * RATE_LIMIT_WINDOW_MS,
    ).toISOString(),
  }, 200, origin);
}
```

Read-only, does not count against the rate limit. Uses `live_order_rate_limits` table from Phase 2.1.

---

## Rollback Plan (#191)

For each deployment step, the system state if the NEXT step fails:

| Step | Failure | State | Safe? |
|------|---------|-------|-------|
| Migration 1 deployed | Function deploy fails | `symbol_id` is TEXT, old function inserts UUIDs as TEXT | Yes |
| Migration 2 deployed | Function deploy fails | `increment_rate_limit` RPC exists, FK is RESTRICT | Yes |
| Function deployed | Need to roll back function | If Migration 1 wrote non-UUID `symbol_id` values, old function + UUID column rollback is NOT possible without data deletion | One-way door |

See Phase 1.3 Addendum (#164) for rollback constraints.

---

## Test Matrix for P2 Acceptance Criteria (#190)

### SL/TP Fill Price Verification (#119)
- **Setup:** `TRADESTATION_USE_SIM=true`, strategy with SL=2%, TP=4%
- **Action:** Submit execution, let `pollOrderFill` return `{ fillPrice: 150.00 }` (bar close is 149.50)
- **Assert:** `stop_loss_price = 150.00 * 0.98 = 147.00` (not `149.50 * 0.98 = 146.51`)

### FK RESTRICT Verification (#121)
- **Setup:** Insert test user, position row, trades row
- **Action:** `DELETE FROM auth.users WHERE id = $test_user_id` in transaction
- **Assert:** FK constraint violation raised (not silent cascade)
- **SQL:** Add to `docs/DEPLOYMENT_VERIFICATION_PR28_LIVE_TRADING.md`

### CHECK Constraint Verification (#122)
- **Setup:** Attempt `INSERT INTO live_trading_trades` with `pnl = 2000000`
- **Assert:** CHECK constraint violation (`live_trades_pnl_sane`)
- **Note:** Direct SQL test required (trades are immutable; trigger blocks UPDATE)

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
- [ ] `increment_rate_limit` RPC: valid PL/pgSQL syntax (#153), REVOKE+GRANT (#169), auth.uid() check (#169), SET search_path (#170)
- [ ] `checkBracketFills` groups by position's `account_id`, not outer-scope ID (#116)
- [ ] Positions stuck in `pending_bracket` OR filled `pending_entry` are emergency-closed, not advanced to open (#108, #150)
- [ ] Recovery scan: concurrency guard via `closing_emergency` status prevents double-close (#151)
- [ ] Recovery scan: try/catch at call site + per-position (#179), NULL order_submitted_at included (#180)
- [ ] Recovery scan: `closeLivePosition` called with all 7 required args (#151)
- [ ] Manual and exit-signal closes poll fill price; `pollOrderFill` signature accepts optional `timeoutMs` (#140, #155)
- [ ] `total` in paginated responses reflects DB row count, not page size (#132)
- [ ] Phase 4.2: `cancelOrder` called exactly once per error path — no double-cancel (#149)
- [ ] Phase 2.4: `close_reason` CHECK uses UPPERCASE matching existing casing (#154)
- [ ] Phase 1.3: DROP INDEX targets correct existing names (#152)
- [ ] Circuit breaker response includes `reset_at` and `suggested_action` (#174)
- [ ] Paused strategy response includes `paused_at` and `suggested_action` (#173)

### P2 — Should pass before merge
- [ ] SL/TP recalculated from fill price before bracket placement (#119)
- [ ] `live_trading_positions.updated_at` auto-updates on every UPDATE; trigger uses DROP-then-CREATE (#120, #158)
- [ ] Both FK delete policies are `RESTRICT`; GDPR deletion order documented (#121, #166)
- [ ] `live_trading_trades` has CHECK constraints on price, quantity, close_reason, pnl bounds (#122, #167)
- [ ] `handleClose` shows toast/error on failure; checks `result.success` for HTTP 200 with `success: false` (#123, #183)
- [ ] Execute API includes `action` field (defensive improvement, not required by server) (#124, #192)
- [ ] `OrderFillResult.status` uses union type with `"FPR"` (not `"FLP"`) for partial fills (#125, #161)
- [ ] Summary endpoint bounded to today (ET, not UTC) by default; `getETStartOfDay()` shared utility (#126, #189)
- [ ] Positions endpoint accepts `?status=` and `?strategy_id=` filters (#133, #176)
- [ ] Paused strategy returns structured response (log observability — no frontend consumer identified) (#134, #184)
- [ ] Circuit breaker response includes `rule`, `reason`, `reset_at`, `suggested_action` (#135)
- [ ] API client handles 429 with user-facing message (#136)
- [ ] `getBatchOrderStatus` fetches at most 48h of order history (#146)
- [ ] `executeStrategy` split into ≤3 focused sub-functions (#142)
- [ ] `LiveTradingStatusWidget` uses summary endpoint; PnL labeled "Today's Realized P&L" (#143, #185)
- [ ] CORS: unknown origins receive no header (conditional omission), not empty string (#159)
- [ ] Phase 6.2: positions with missing `account_id` are skipped (not fallback to current account) (#162)
- [ ] Phase 5.1: stuck threshold 5 minutes (configurable via env var), not 2 minutes (#163)
- [ ] Phase 6.3: DB errors return 503, genuine rate limits return 429 (#171)
- [ ] Phase 4.2: `cancelOnce` checks `cancelled.ok` and logs critical alert on failure (#172)
- [ ] Paginated responses include `has_more: boolean` (#175)
- [ ] Phase 4.5: poll boundary clarified — handler polls, passes fill price to `closeLivePosition` (#182)
- [ ] `disconnect_broker` checks for open positions and returns 409 if any exist (#186)
- [ ] `EMERGENCY_CLOSE` added to `live_trading_positions.close_reason` CHECK constraint (#187)
- [ ] Opposite-leg cancellation in `checkBracketFills` documented (or OCO behavior confirmed) (#188)
- [ ] Standalone `POST action: "recover_positions"` endpoint available (#181)
- [ ] Phase 6.2 deployed together with or after Phase 7.4 date filter (#160)

### P3 — Nice to have (addressed in plan but not blocking)
- [ ] Phase 1.3 rollback documented as one-way door (#164)
- [ ] `Math.floor()` added to exponential backoff (#165)
- [ ] Recovery scan observability gap documented; `close_reason` filter follow-up noted (#177)
- [ ] `GET ?action=rate_limit_status` endpoint added (#178)
- [ ] Test matrix for P2 acceptance criteria documented (#190)
- [ ] Deployment rollback plan table documented (#191)
- [ ] Phase 8.2 framing corrected (defensive improvement, not bug fix) (#192)

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
