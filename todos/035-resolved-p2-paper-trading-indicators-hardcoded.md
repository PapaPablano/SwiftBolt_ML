---
status: pending
priority: p2
issue_id: "035"
tags: [code-review, correctness, paper-trading, indicators]
dependencies: []
---

# 035 — Paper Trading Executor Uses Hardcoded Mock Indicator Values

## Problem Statement
`paper-trading-executor/index.ts` populates the indicator cache with hardcoded values (`RSI = 55`, `MACD = 0.5`, `Volume_MA = 1000000`). Strategy conditions checking RSI, MACD, or crossovers always evaluate against these fixed values regardless of actual market state, producing wrong paper trading signals.

## Findings
- `paper-trading-executor/index.ts` lines 615-619: `indicatorCache.set("RSI", 55)` etc.
- Condition evaluator line 267 reads from indicatorCache — always gets 55
- `cross_up`/`cross_down` operators (lines 304-313) check `indicatorValue > 50`, not actual crossovers
- 100 bars of OHLCV data already fetched (line 568) but never used for indicator math

## Proposed Solutions

### Option A: Compute indicators from fetched bars (Recommended)
Use `sortedBars` already in memory to compute RSI (14-period), MACD (12/26/9), Volume MA (20-period) with standard formulas.
- Effort: Medium (4-8 hours)
- Risk: Low

### Option B: Call technical-indicators Edge Function
Invoke `technical-indicators` as a subroutine and populate cache from response.
- Effort: Small
- Risk: Medium (adds latency, inter-function dependency)

## Recommended Action
Option A — self-contained and uses data already fetched.

## Technical Details
- **Affected files:** `supabase/functions/paper-trading-executor/index.ts`

## Acceptance Criteria
- [ ] RSI computed from 14-period close prices
- [ ] MACD computed from 12/26 EMA with 9-period signal
- [ ] Volume MA computed from 20-period average
- [ ] cross_up/cross_down compares current vs previous indicator value (true crossover)
- [ ] Unit tests verify indicator calculations

## Work Log
- 2026-03-01: Identified by performance-oracle and security-sentinel review agents
