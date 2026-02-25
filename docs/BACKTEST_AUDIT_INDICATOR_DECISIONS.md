# Backtest Audit: Indicator Usage and Why Trades Trigger

This doc explains how **user-provided strategy config** connects to **executed data** so you can pinpoint why each backtest entry/exit fired, and why the worker’s decisions can differ from the canonical indicator values in the audit.

---

## 1. Two Data Sources (Worker vs Audit)

| Source | Where | What it uses |
|--------|--------|----------------|
| **Worker** (Supabase `strategy-backtest-worker`) | Fetches OHLC from yfinance, computes its **own** indicators in TS | SMA20, EMA12/26, MACD, RSI, ATR, Stoch, ADX=25. **SuperTrend** is computed in TS (period=7, multiplier=2.0, TradingView-style) so decisions align with the audit. |
| **Audit** (`audit_backtest_data.py`) | Same OHLC (yfinance), then **canonical ML pipeline** (`add_technical_features`) | Full indicator set: RSI, MACD, KDJ, **real SuperTrend**, ADX, regime, S/R, etc. |

So:

- **`trading_data.csv`** columns like `entry_supertrend_trend`, `exit_supertrend_trend`, `entry_rsi_14`, etc. are the **canonical** (real) indicator values at entry/exit dates—what actually happened on those bars.
- The **worker** computes its own indicators in TS, including **real SuperTrend** via `calculateSuperTrend(highs, lows, closes, 7, 2.0)` (TradingView-style, ATR period 7, multiplier 2.0). So `supertrend_trend` (1 = bullish, 0 = bearish), `supertrend_signal`, and `supertrend_factor` (2.0) are now aligned with the audit’s indicator logic.

---

## 2. How the Worker Decides Entry/Exit

1. Loads strategy config from `strategy_user_strategies.config` (camelCase `entryConditions` / `exitConditions` from the frontend).
2. Normalizes to `entry_conditions` / `exit_conditions` with `type: "indicator"` and `name` = indicator id (e.g. `rsi`, `supertrend_trend`).
3. For each bar (from index 30 onward):
   - **Entry**: if flat and `evaluateConditions(entry_conditions, i)` is true → buy.
   - **Exit**: if long and (`evaluateConditions(exit_conditions, i)` **or** take profit **or** stop loss) → sell.

So the **same number of inputs** (one row per trade) is correct: the worker has one entry decision and one exit decision per trade. Your audit adds **more detail** by attaching the canonical indicator levels at those same dates.

---

## 3. Why Your Three Trades Fired (Supertrend RSI example)

For a strategy named **"Supertrend RSI"** the idea is usually: **enter when SuperTrend is bullish and RSI is oversold** (buy the dip), **exit when RSI is overbought** (or stop/target).

- **Worker behaviour**
  - It now uses **real SuperTrend** (period 7, multiplier 2.0), so `supertrend_trend` is 1 when bullish and 0 when bearish.
  - Entry requires **both** SuperTrend bullish and RSI &lt; 30 (and any other entry conditions). Exit is **RSI &gt; 70** or stop/target (e.g. +4% / -2%).
- So the three entries in the **previous** (hardcoded) run triggered when:
  1. Worker saw RSI &lt; 30 and “SuperTrend” = 1 (hardcoded).
  2. Worker then exited on the next bar(s) when RSI &gt; 70 or +4% / -2% was hit.
- With **real SuperTrend**, a bar where SuperTrend is bearish (0) will no longer satisfy “SuperTrend bullish + RSI oversold,” so that third trade (entry on a bearish SuperTrend bar) would not occur.

Your audit shows:

- **Trade 1 & 2**: `entry_supertrend_trend, exit_supertrend_trend` = **1, 1**  
  → In the **canonical** data, SuperTrend was bullish on both entry and exit bars. So the “bullish + RSI oversold” idea lines up with what actually happened on the chart.

- **Trade 3**: `entry_supertrend_trend, exit_supertrend_trend` = **0, 0**  
  → In the **canonical** data, SuperTrend was **bearish** on both entry and exit. With the **updated worker** (real SuperTrend), the worker would **not** enter on that bar because it would see `supertrend_trend = 0`. So that third trade would no longer occur when the worker uses real SuperTrend; entry would require both SuperTrend bullish and RSI oversold.

---

## 4. Connecting User-Provided Data to Executed Data

1. **Strategy rules**  
   After each run with `--strategy-name` or `--strategy-id`, the audit writes **`strategy_config.json`** in the output dir. It contains the saved `entryConditions` and `exitConditions` (and risk etc.) so you can see exactly which conditions the worker was supposed to use.

2. **Indicator levels at execution**  
   **`trading_data.csv`** has one row per trade and includes:
   - Core: `entry_date`, `exit_date`, `entry_price`, `exit_price`, `pnl`, `pnl_pct`, …
   - For each selected strategy indicator: `entry_<indicator>`, `exit_<indicator>` (e.g. `entry_supertrend_trend`, `exit_supertrend_trend`, `entry_rsi_14`, `exit_rsi_14`).

3. **How to read it**
   - Open `strategy_config.json` → see e.g. “entry: RSI &lt; 30, SuperTrend == 1”.
   - Open `trading_data.csv` → for that trade, check `entry_rsi_14` and `entry_supertrend_trend`.
   - That shows: **what the rule is** (config) and **what the canonical data actually was** at entry/exit (CSV). The worker used its own indicators (and hardcoded SuperTrend), so if you want to align with the audit, the worker would need to use the same indicator pipeline or at least real SuperTrend.

---

## 5. “Supertrend bullish but RSI oversold” – does that happen?

Yes. In the **canonical** data you can have:

- `supertrend_trend == 1` (bullish) and `rsi_14 < 30` (oversold) on the same bar.

So the idea “buy when trend is bullish but price is temporarily oversold” is valid. The issue in your run is not that the combo never happens, but that the **worker** does not use real SuperTrend; it always uses 1, so it can enter on bars where the **real** SuperTrend is bearish (e.g. trade 3).

---

## 6. Worker–Audit Alignment (Done)

The worker now uses **real SuperTrend**:

- **Implementation**: `calculateSuperTrend(highs, lows, closes, 7, 2.0)` in `strategy-backtest-worker/index.ts` (TradingView-style: ATR period 7, Wilder smoothing, multiplier 2.0). Same semantics as the ML pipeline: `supertrend_trend` 1 = bullish, 0 = bearish; `supertrend_signal` = percent distance from SuperTrend line; `supertrend_factor` = 2.0.
- **Effect**: Entry/exit decisions that depend on SuperTrend (e.g. “Supertrend RSI”: enter when SuperTrend bullish and RSI oversold) now match the audit’s canonical indicator values, so trades like the previous “trade 3” (entry on a bearish SuperTrend bar) no longer occur.

For full alignment of other indicators (e.g. RSI period, ADX), the worker would need to use the same formulas/periods as the ML pipeline; SuperTrend is now aligned.

Use:

- **`strategy_config.json`** → what rules the worker was given.  
- **`trading_data.csv`** → what actually happened on the chart (canonical indicators at entry/exit).  
- This doc → how worker and audit align (real SuperTrend; other indicator periods may still differ).

That’s how you pinpoint why each of the three entries triggered and how user-provided data and executed data connect.
