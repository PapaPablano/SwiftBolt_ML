# Intraday Forecast Points — Storage Contract

**Scope:** `ml_forecasts_intraday.points` (JSONB array of ForecastPoint). Used by production L1 writer, GET /chart, and GET /chart-data-v2.

---

## Step semantics (locked)

**Decided:** **Future step index (1-based).** Only future bars are stored; no anchor (current bar) in `points`.

- **step 1** = first future bar (first predicted step).
- **step 2** = second future bar, etc.
- The production writer assigns `step = i + 1` for the i-th point (0-based array index → 1-based step). The **first element** of `points` is always the first future bar.
- **Short-points path:** `build_intraday_short_points()` emits an anchor at i=0 (current) then future points. Before canonicalize and DB write, the writer **slices off the anchor** (`short_points[1:]`) so only future points are persisted. Thus stored steps are 1, 2, … and match the contract.
- **Path-points path:** `build_intraday_path_points()` already emits only future steps (no anchor); no slice needed.

*Not used:* “array index including anchor” or “step 0 = current bar.” Storage contract is 1-based future steps only.

---

## Timestamp (`ts`)

- **Storage:** Always **UTC ISO 8601** string: `YYYY-MM-DDTHH:MM:SSZ` (e.g. `2026-02-10T15:30:00Z`).
- **Writer:** Production writer normalizes `ts` even when the point already has a string: parse → re-emit UTC so storage is consistent. Unix seconds are converted to this format; existing ISO strings are parsed and re-formatted in UTC.
- **Readers:** 
  - `/chart`: returns `ts` as stored (ISO string).
  - `/chart-data-v2`: converts `ts` to **integer unix seconds** in the response; storage remains ISO.

---

## Point shape (aligned with writer and chart)

The **intraday contract** is **not** top-level `open`/`high`/`low`/`close`. It is:

- **Required:** `ts` (ISO string), `value` (close / target at that step).
- **Optional:** `lower`, `upper`, `timeframe`, `step`, **nested** `ohlc` (`{ open, high, low, close, volume }`), **nested** `indicators` (e.g. `rsi_14`, `macd`, `kdj_k`, …), plus lab-only fields (e.g. `confidence`, `components`, `weights`).

So price at a step is `value` (and optionally `ohlc.close`); bands are `lower`/`upper`. Top-level OHLC is not used in the intraday contract.

- **Timeframe tokens:** Use `m15`, `h1`, `h4` at the API/DB boundary. Edge normalizes `4h_trading` → `h4` in responses.

See [master_blueprint.md](master_blueprint.md) — Canonical Forecast Point Schema (points JSONB) — for full shape.
