---
status: pending
priority: p1
issue_id: "091"
tags: [code-review, live-trading, security, input-validation, injection]
dependencies: []
---

# Symbol and timeframe inputs not validated against an allowlist before use

## Problem Statement

The executor accepts `symbol` and `timeframe` from the POST request body and passes them directly to: TradeStation API URL paths, Postgres queries (`.eq("symbol", symbol)`), and `normalizeSymbol()`. The only validation is a truthy check. A crafted symbol value could produce path traversal in TradeStation API calls (SSRF), unexpected behavior in PostgREST filters, or bypass `normalizeSymbol()` entirely for unknown symbols. For timeframe, an unrecognized value silently queries ohlc_bars_v2 for a timeframe that may not exist.

## Findings

**Security Sentinel (SEC-04 P1):** "In the live executor, [symbol/timeframe] values are used in two additional attack surfaces beyond the DB query: TradeStation API call, and timeframe injection into DB queries. Validate symbol against strict regex: `/^[A-Z0-9.@\/]{1,10}$/`. Validate timeframe against a hardcoded allowlist."

**Security Sentinel (SEC-16 P3):** "`normalizeSymbol()` maps an unbounded input set; unknown symbols fall through to live order submission."

**Current plan (Phase 3d):** Inherits the paper executor's pattern:
```typescript
const { symbol, timeframe } = body;
if (!symbol || !timeframe) { return error(400); }
// Used directly without further validation
```

## Proposed Solutions

### Option A: Strict allowlist validation at handler entry point (Recommended)
At the beginning of the executor handler (before any DB or TradeStation calls):
```typescript
const VALID_TIMEFRAMES = new Set(['1m','5m','15m','30m','1h','4h','1D','1W']);
const SYMBOL_REGEX = /^[A-Z0-9.@]{1,10}$/;

function validateInputs(symbol: string, timeframe: string): ValidationResult {
  if (!SYMBOL_REGEX.test(symbol)) return { valid: false, reason: 'invalid_symbol_format' };
  if (!VALID_TIMEFRAMES.has(timeframe)) return { valid: false, reason: 'invalid_timeframe' };
  return { valid: true };
}
```

And in `normalizeSymbol()`: throw an explicit typed error for unrecognized symbols instead of falling through to live order submission.

**Pros:** Catches injection at entry, self-documenting, consistent error responses
**Cons:** Must keep timeframe list in sync with ohlc_bars_v2 data
**Effort:** Small
**Risk:** Low

### Option B: Validate only within normalizeSymbol
Move all validation into `normalizeSymbol()` and throw on unknown input.

**Pros:** Single validation point
**Cons:** Validation happens after DB queries have already run with the input, not at entry point
**Effort:** Small
**Risk:** Medium

## Recommended Action

Implement Option A. Add `validateInputs()` to `live-trading-executor/index.ts` handler entry. Update `normalizeSymbol()` in `_shared/tradestation-client.ts` to throw `{ code: 'unknown_symbol', symbol }` for any symbol not in the known equity pattern or futures set — no fallthrough.

## Technical Details

**Affected files:**
- `supabase/functions/live-trading-executor/index.ts` — add `validateInputs()` at handler entry
- `supabase/functions/_shared/tradestation-client.ts` — `normalizeSymbol()` must throw on unknown symbol

## Acceptance Criteria

- [ ] `symbol` validated against regex `/^[A-Z0-9.@]{1,10}$/` before any use
- [ ] `timeframe` validated against hardcoded allowlist before any DB query
- [ ] `normalizeSymbol()` throws typed error for unrecognized symbols (no silent fallthrough)
- [ ] Both validations return 400 with `{ code: 'invalid_input' }` — no internal details exposed

## Work Log

- 2026-03-03: Finding created from Security Sentinel (SEC-04, SEC-16).
