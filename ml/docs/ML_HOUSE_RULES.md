# ML House Rules

Explicit rules for the SwiftBolt ML pipeline: environment, data sources, and timeframes.

---

## 1. Environment rule

- **All TabPFN / TabPSM model training and inference must run inside the `swiftbolt/tabpfn-forecaster` Docker image.**
- **Local Python** is reserved for:
  - Baseline models (XGBoost, ARIMA)
  - Data prep, plotting, feature analysis
  - Regime tests (`test_regimes.py`) and non-TabPFN scripts

**How to run TabPFN / hybrid:**

- Walk-forward (XGBoost + ARIMA + Hybrid):  
  `./scripts/run_tabpfn_docker.sh SYMBOL weekly`
- Single-split hybrid (AAPL):  
  `./scripts/run_tabpfn_docker.sh "" hybrid`
- Single-symbol TabPFN job:  
  `./scripts/run_tabpfn_docker.sh SYMBOL single`

Do **not** run `hybrid_tabpfn_xgb_aapl.py`, `walk_forward_weekly.py` with `--no-hybrid` false, or any TabPFN import/training locally; use Docker only.

---

## 2. Data rule

- **Canonical regime analysis uses Supabase daily (d1)** from `ohlc_bars_v2`.
- **Alpaca 4h OHLC clone** (`ohlc_bars_h4_alpaca`) is used only for ML experiment variants:
  - TabPFN / hybrid tests
  - Multi-stock pooling when more samples are needed
- Both sources use the same feature pipeline (`DataCleaner`, `prepare_training_data_binary`) for comparability.

---

## 3. Timeframe rule

- **Regime characterization and long-horizon backtests:** use **daily bars** (d1).
- **TabPFN + hybrid tests** (Docker): use **4h bars** from the Alpaca clone when available, aligned to the same regime date ranges, to get sufficient sample count (e.g. 200–1000+ per regime).
- When 4h data is insufficient (e.g. symbol not in clone or short history), fall back to d1 from Supabase.

---

## Summary

| Use case                    | Environment | Data source           | Timeframe |
|----------------------------|------------|------------------------|-----------|
| Regime tests, XGB/ARIMA    | Local      | Supabase `ohlc_bars_v2` | d1        |
| TabPFN / hybrid walk-forward | Docker     | Supabase d1 or `ohlc_bars_h4_alpaca` (h4) | d1 or h4  |
| TabPFN single-split hybrid | Docker     | Supabase d1 or h4 clone | d1 or h4  |

---

## 4. Using the Alpaca 4h clone

- **Table:** `ohlc_bars_h4_alpaca` (see migration `20260202000000_ohlc_bars_h4_alpaca.sql`).
- **Backfill:** Run once (or periodically) to populate 4h bars from Alpaca:
  ```bash
  cd ml && python scripts/backfill_ohlc_h4_alpaca.py
  python scripts/backfill_ohlc_h4_alpaca.py --symbols PG KO NVDA --start 2020-01-01
  ```
- **Walk-forward with 4h from clone:** Use `--timeframe h4 --h4-source alpaca_clone` (or set env `H4_SOURCE=alpaca_clone` in Docker). Then `fetch_ohlc_bars(..., source="alpaca_4h")` reads from `ohlc_bars_h4_alpaca`.
