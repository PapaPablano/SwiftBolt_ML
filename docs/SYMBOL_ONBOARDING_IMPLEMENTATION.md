# Symbol Onboarding Fail-Safe – Implementation Checklist

Single contract: `ensure-symbol-ready` is the **only** supported entry point for "user added ticker → ready for intraday." All other paths (watchlist-sync, symbol-init, L1 gate) call it.

---

## Request/Response JSON: `ensure-symbol-ready`

### Request (POST)
```json
{
  "ticker": "AAPL",
  "timeframe": "m15",
  "min_bars": 1000
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| ticker | string | required | Uppercase ticker |
| timeframe | string | "m15" | Target timeframe; m15 for L1 gate |
| min_bars | number | 1000 | Minimum bars to consider "ready" |

### Response
```json
{
  "status": "ready",
  "symbol_id": "uuid",
  "bars_ready": 2350,
  "reason": null
}
```

| status | meaning |
|--------|---------|
| `ready` | Symbol exists, bars >= min_bars |
| `pending_backfill` | Symbol exists (or was created), m15 backfill enqueued; bars < min_bars |
| `invalid_symbol` | Provider rejected ticker; symbols.status = 'invalid' |

| Field | When present |
|-------|--------------|
| symbol_id | Always when status != invalid_symbol |
| bars_ready | When symbol exists (count of m15 bars in ohlc_bars_v2) |
| reason | Optional; e.g. "Provider rejected: unknown ticker" |

---

## MUST (Required)

1. **Migration**  
   Add to `symbols`: `status TEXT DEFAULT 'active' CHECK (status IN ('active','pending','invalid'))`, `last_ingested_at`, `ingest_error`.

2. **Edge Function `ensure-symbol-ready`**  
   - If ticker missing: insert placeholder `symbols` row with `status='pending'`.  
   - If ticker exists and `status='invalid'`: return `invalid_symbol`.  
   - If bars < min_bars: enqueue m15 backfill via SPEC-8 (see below), return `pending_backfill`.  
   - If bars >= min_bars: return `ready`.  
   - Enqueue m15 by calling `ensure-coverage` (supabase/functions) with appropriate `fromTs`/`toTs`.

3. **SPEC-8 m15 enqueue (inside ensure-symbol-ready)**  
   Use `supabase/functions/ensure-coverage`. Call with:
   - `symbol`: ticker (uppercase)  
   - `timeframe`: `"m15"` (backfill-adapter accepts m15 or 15m; use m15 for consistency with ohlc_bars_v2)  
   - `fromTs`: ISO string ~60 days ago, e.g. `new Date(Date.now() - 60*24*60*60*1000).toISOString().slice(0,19)+"Z"`  
   - `toTs`: now ISO, e.g. `new Date().toISOString().slice(0,19)+"Z"`  

   **Constraint**: Symbol must exist in `symbols` before calling ensure-coverage. `get_coverage` joins symbols; `run-backfill-worker`’s `fetchIntradayForDay` calls `getSymbolId()` which throws if symbol missing. So: create symbol first, then call ensure-coverage.

4. **symbol-init calls ensure-symbol-ready**  
   At start of symbol-init:
   - `POST ensure-symbol-ready { ticker, timeframe: "m15", min_bars: 1000 }`.  
   - If `invalid_symbol`: return early with error.  
   - If `pending_backfill`: continue (d1 work, forecasts); m15 will fill in background.  
   - If `ready`: continue normally.  
   - Remove or simplify symbol-init’s own get-or-create + chart fetch; let ensure-symbol-ready own symbol creation.

5. **watchlist-sync calls ensure-symbol-ready first**  
   Before get-or-create symbol:
   - `POST ensure-symbol-ready { ticker, timeframe: "m15", min_bars: 1000 }`.  
   - If `invalid_symbol`: return 400 with reason.  
   - Otherwise proceed with add to watchlist and trigger symbol-init (which will call ensure-symbol-ready again; idempotent).

6. **L1 gate pre-check**  
   Before `db.fetch_ohlc_bars()` for each symbol:
   - Call Python helper `ensure_symbol_ready(ticker, timeframe="m15", min_bars=args.min_bars_per_symbol)`.  
   - If not `ready`: record in `skipped_symbols` with explicit reason (`pending_backfill`, `invalid_symbol`, etc.).  
   - Only fetch when `ready`.

7. **Python helper `ml/src/data/symbol_ready.py`**  
   - `ensure_symbol_ready(ticker, timeframe="m15", min_bars=1000) -> SymbolReadyResult`.  
   - Calls Edge Function via HTTP; returns status, symbol_id, bars_ready, reason.

---

## SHOULD (Recommended)

8. **user-refresh uses ensure-symbol-ready**  
   Replace direct `symbol_backfill_queue` enqueue with a call to `ensure-symbol-ready`. This avoids "d1/h1/w1 ready but m15 missing."

9. **Provider validation**  
   Before creating a symbol, call chart/provider to validate ticker; if rejected, insert with `status='invalid'` and return `invalid_symbol`.

---

## NICE (Optional)

10. **fetch_ohlc_bars `.limit(1)` refactor**  
    Replace `.single()` with `.limit(1)` and check `resp.data`; avoids exception-based control. Functionally equivalent to current soft-fail.

11. **symbol_ingestion_queue table**  
    Per-timeframe tracking for debugging (ticker, timeframe, status, error, bars_inserted).

---

## Canonical ensure-coverage (SPEC-8)

Use **`supabase/functions/ensure-coverage`** (not `backend/supabase/functions/ensure-coverage`).

- Expects: `{ symbol, timeframe, fromTs, toTs }`.  
- Uses `get_coverage` RPC and creates `backfill_jobs` + `backfill_chunks`.  
- `run-backfill-worker` processes chunks via `claim_backfill_chunks`.  
- **Constraint**: Symbol must exist before calling ensure-coverage (get_coverage joins symbols; worker’s `getSymbolId` throws if missing). So ensure-symbol-ready creates the symbol first, then calls ensure-coverage.

---

## Integration Points (exact locations)

### ensure-symbol-ready flow
```
1. Lookup symbols by ticker (limit 1)
2. If 0 rows:
   a. Validate ticker with provider (optional; if invalid, could defer to first backfill failure)
   b. INSERT symbols (ticker, status='pending')
   c. Call ensure-coverage(symbol, "m15", fromTs, toTs)  // 60 days back
   d. Return { status: "pending_backfill", symbol_id }
3. If 1 row and status='invalid': return { status: "invalid_symbol" }
4. Count m15 bars in ohlc_bars_v2 for symbol_id
5. If count < min_bars:
   a. Call ensure-coverage(...)  // idempotent; upsert on (symbol, timeframe, from_ts, to_ts)
   b. Return { status: "pending_backfill", symbol_id, bars_ready: count }
6. Return { status: "ready", symbol_id, bars_ready: count }
```

### symbol-init (backend/supabase/functions/symbol-init/index.ts)
- **Lines 68–92**: Replace the get-or-create block with a call to `ensure-symbol-ready`:
  ```ts
  const ensureUrl = `${Deno.env.get("SUPABASE_URL")}/functions/v1/ensure-symbol-ready`;
  const ensureRes = await fetch(ensureUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")}`,
      apikey: `${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")}`,
    },
    body: JSON.stringify({ ticker: symbol, timeframe: "m15", min_bars: 1000 }),
  });
  const ensure = await ensureRes.json();
  if (ensure.status === "invalid_symbol") {
    result.errors.push(ensure.reason ?? "Invalid symbol");
    return new Response(JSON.stringify(result), { status: 400, headers: {...} });
  }
  symbolRecord = { id: ensure.symbol_id, ticker: symbol, asset_type: "stock" };
  ```
- **Lines 94–131**: Keep d1 fetch/chart for forecast readiness; ensure-symbol-ready handles m15.
- Ensure d1 path still works when m15 is `pending_backfill`.

### watchlist-sync (backend/supabase/functions/watchlist-sync/index.ts)
- **Lines 86–103**: Before get-or-create, call `ensure-symbol-ready`:
  ```ts
  const ensureUrl = `${Deno.env.get("SUPABASE_URL")}/functions/v1/ensure-symbol-ready`;
  const ensureRes = await fetch(ensureUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")}`,
      apikey: `${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")}`,
    },
    body: JSON.stringify({ ticker: body.symbol.toUpperCase(), timeframe: "m15", min_bars: 1000 }),
  });
  const ensure = await ensureRes.json();
  if (ensure.status === "invalid_symbol") {
    return new Response(JSON.stringify({ error: ensure.reason ?? "Invalid symbol" }), { status: 400, headers: {...} });
  }
  ```
- Then proceed with get-or-create (symbol now guaranteed to exist or be created), add to watchlist, trigger symbol-init.

### L1 gate (ml/scripts/l1_gate_validation.py)
- **Lines 110–119**: Insert pre-check before `db.fetch_ohlc_bars()`:
  ```python
  from src.data.symbol_ready import ensure_symbol_ready, SymbolReadyResult

  for symbol in symbols:
      logger.info("Checking readiness for %s...", symbol)
      ready = ensure_symbol_ready(symbol, timeframe="m15", min_bars=args.min_bars_per_symbol)
      if ready.status != "ready":
          skipped_symbols[symbol] = ready.reason or ready.status
          continue
      logger.info("Loading %s m15 bars...", symbol)
      df = db.fetch_ohlc_bars(...)
  ```

---

## Rollout Order

1. Migration (schema only)
2. Edge Function `ensure-symbol-ready`
3. Python `symbol_ready.py`
4. L1 gate pre-check
5. symbol-init → call ensure-symbol-ready
6. watchlist-sync → call ensure-symbol-ready
7. user-refresh → call ensure-symbol-ready (optional)
