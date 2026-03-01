---
status: pending
priority: p3
issue_id: "046"
tags: [code-review, architecture, data-integrity, backtest]
dependencies: []
---

# 046 — strategy-backtest-worker Uses Yahoo Finance Instead of ohlc_bars_v2

## Problem Statement
The backtest worker fetches OHLCV data from Yahoo Finance (`YFinanceClient`), not from `ohlc_bars_v2` which is the production data source populated by Alpaca. Backtest results may diverge from live paper trading because they train on different price data. CLAUDE.md declares Alpaca as the primary data provider.

## Findings
- `supabase/functions/strategy-backtest-worker/index.ts` line 98: `yfinance.getHistoricalBars()`
- Production pipeline: Alpaca → `ohlc_bars_v2` (stored, normalized)
- Backtest pipeline: Yahoo Finance → temporary variable (different source, different OHLC values)
- Discrepancy can cause strategies to appear more/less profitable in backtest than in paper trading

## Proposed Solutions
Replace YFinance call with `ohlc_bars_v2` query:
```typescript
const { data: bars } = await supabase
  .from('ohlc_bars_v2')
  .select('ts, open, high, low, close, volume')
  .eq('symbol_id', symbolId)
  .eq('timeframe', timeframe)
  .gte('ts', start)
  .lte('ts', end)
  .order('ts', { ascending: true });
```
Trigger backfill if data missing for date range.
- Effort: Medium (requires symbol_id lookup, backfill fallback)
- Risk: Low

## Acceptance Criteria
- [ ] Backtest worker reads from ohlc_bars_v2, not Yahoo Finance
- [ ] If data missing for range, triggers backfill before proceeding
- [ ] Backtest results reproducible from the same data as paper trading

## Work Log
- 2026-03-01: Identified by architecture-strategist review agent
