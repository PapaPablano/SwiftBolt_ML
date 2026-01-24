# Options Watchlist / Strike Positions Plan

## Goal
Add strike-based positions (manual entry from the options ranker) and surface them in **Active Alerts** with a HOLD/SELL recommendation that reflects current price, forecast trajectory, and option risk.

## Current Anchors
- Active Alerts UI: `client-macos/SwiftBoltML/Views/AnalysisView.swift` (AlertsSection, AlertRow).
- Options ranker UI/data: `client-macos/SwiftBoltML/Views/OptionsRankerView.swift`, `OptionsRankerExpiryView.swift`, `OptionsRankerViewModel.swift`.
- Supabase tables already in use: `options_ranks`, `options_chain_snapshots`, `options_price_history`, `ml_forecasts`, `ml_forecasts_intraday`, `scanner_alerts`, `forecast_monitoring_alerts`.

## Proposed Data Model (Supabase)
Create three new tables (or extend if already planned):
1. `options_positions`
   - `id` (uuid), `user_id`, `underlying_symbol_id` (FK -> symbols), `option_symbol` (text),
     `strike` (numeric), `option_type` (call/put), `expiry` (date),
     `status` (open/closed), `created_at`, `updated_at`.
2. `options_position_entries`
   - `id`, `position_id` (FK), `entry_price`, `contracts`, `entered_at`, `notes`.
   - Supports multiple entries/average cost.
3. `options_position_alerts`
   - `id`, `position_id` (FK), `label` (HOLD/SELL), `reason` (text),
     `details` (jsonb), `severity` (info/warn/critical), `created_at`.

RLS: user-owned rows only. Indexes on `(user_id, status)`, `(underlying_symbol_id, expiry)`.

## Alert Logic (HOLD/SELL)
Inputs: option snapshot, option rank, forecast trend/trajectory, underlying trend indicators.
- HOLD if:
  - forecast trend aligns with position thesis AND
  - strike is favorable vs forecast path (e.g., call strike below upper forecast band) AND
  - risk flags are low (low spread, healthy OI/volume, theta decay within threshold).
- SELL if:
  - forecast flips against thesis (e.g., bullish forecast while holding bearish put) OR
  - expected move threatens position P/L (strike likely to be worthless/invalid) OR
  - liquidity degrades / IV crush risk becomes dominant.

Use `ml_forecasts`/`ml_forecasts_intraday` for direction + confidence and `options_ranks`/`options_chain_snapshots` for liquidity + greeks.

## UX Flow
1. **Options Ranker Detail**: add "Add Position" CTA.
2. **Entry Modal**: select strike (from ranker row), input entry price + contracts, confirm.
3. **Active Alerts Panel**: show open positions with HOLD/SELL badge + concise reason.
4. **Position Detail**: show forecast trend, strike relationship, and rule triggers.

## Services / Jobs
- Add a small evaluator in ML or a lightweight edge function:
  - Pull open positions.
  - Fetch latest option snapshot + ranks + forecast.
  - Compute recommendation and write to `options_position_alerts`.
- If pulling OHLC for supporting indicators, process **all timeframes** together: `['m15','h1','h4','d1','w1']`.

## Implementation Phases
1. **Schema + RLS**: create the three tables and indexes. Update types.
2. **Backend evaluator**: compute HOLD/SELL rules and write alerts.
3. **SwiftUI wiring**:
   - Add "Add Position" flow in options ranker.
   - Display alerts in AnalysisView Active Alerts.
4. **Polish**: reasoning badges, quick filters (Open/Closed), empty states.

## Next MCP Calls
- Supabase: inspect existing tables + migrations for options ranks and alerts.
- GitHub MCP: search for patterns (SwiftUI Supabase realtime lists, options position trackers).
