# SwiftBolt ML (macOS)

macOS app for SwiftBolt ML: charts, options ranker, analysis, and strategy builder.

## Run the app

1. Open `SwiftBoltML.xcodeproj` in Xcode.
2. Select scheme **SwiftBoltML** and destination **My Mac**.
3. **Product → Clean Build Folder** (⇧⌘K), then **Product → Run** (⌘R).

## Backend and frontend setup

### Frontend (this app)

- **Config**: `SUPABASE_URL` and `SUPABASE_ANON_KEY` must be set in `SwiftBoltML/Info.plist` (or in environment / Keychain). The app uses these to call Supabase Edge Functions; without them the app will not load chart data.
- **Optional**: `FASTAPI_URL` (default `http://127.0.0.1:8000`) for technical indicators. If the ML backend is not running, indicators may be unavailable; charts and options still work via Supabase.

### Backend (Supabase)

- **Project**: Create or use an existing Supabase project. Set its URL and anon key in the app’s Info.plist (or env).
- **Edge Functions**: Deploy the functions the app calls:
  - **chart-read** — main chart OHLC data (and fallback when chart-data-v2 is not available).  
    Path in repo: `supabase/functions/chart-read/`.
  - **chart-data-v2** (optional) — preferred chart API when available for a symbol.  
    Path: `supabase/functions/chart-data-v2/` (if present).
- **Deploy**: From the repo root, link the project and deploy, e.g.  
  `supabase link --project-ref <ref>` then `supabase functions deploy chart-read` (and `chart-data-v2` if used).
- **Secrets**: If `chart-read` uses Alpaca (or other vendors), set the required secrets in the Supabase dashboard (e.g. `ALPACA_API_KEY`, `ALPACA_API_SECRET`).

If the chart stays on “Loading chart data…”:

1. Confirm **Product → Clean Build Folder** and run again.
2. Check Supabase URL and anon key in Info.plist (or env).
3. Confirm `chart-read` is deployed and that the project has the needed secrets.
4. Use the chart **Sync** button to retry; if the request fails, an error message is shown.

## Config (summary)

- **Supabase**: Required for chart and options. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in Info.plist or env.
- **FastAPI**: Optional; `FASTAPI_URL` for technical indicators (default `http://127.0.0.1:8000`).

## UI overview

- **Left sidebar**
  - Search and watchlist at top.
  - **Navigation**: **Strategy Builder** (first), Portfolio, Multi-Leg, Predictions. Choosing one switches the main detail view.
  - **Development** (DEBUG): Dev Tools.

- **Main area (when a symbol is selected)**
  - **Left**: Chart (timeframes 15M / 1H / 4H / D / W), Sync, Indicators.
  - **Right**: Tab menu — **News** | **Options** | **Analysis** | **Strategy Builder**. Use the dropdown to select **Strategy Builder** (or any tab).
  - You can also open **Strategy Builder** full-screen from the sidebar under **Navigation**.

Chart data loads from Supabase (`chart-read`, or `chart-data-v2` when available). If the chart shows an error, use **Sync** to retry and check backend setup above.
