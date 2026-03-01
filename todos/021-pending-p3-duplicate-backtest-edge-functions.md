---
status: pending
priority: p3
issue_id: "021"
tags: [code-review, agent-native, api, backtesting, cleanup]
dependencies: []
---

# 021: Duplicate backtest Edge Functions — strategy-backtest vs backtest-strategy

## Problem Statement

Two distinct Edge Functions exist for triggering backtests: `backtest-strategy` and `strategy-backtest`. Both write to `strategy_backtest_jobs`. Agents or developers reading the Edge Function list cannot tell which to use. `backtest-strategy` is the newer one (auto-triggers the worker, supports preset strategies); `strategy-backtest` is an older version.

## Findings

**Files:**
- `supabase/functions/backtest-strategy/index.ts` — newer, canonical
- `supabase/functions/strategy-backtest/index.ts` — older version, should be deprecated

**Source:** agent-native-reviewer agent (Warning #5)

## Proposed Solution

1. Deprecate `strategy-backtest` — add a deprecation notice in its index.ts that redirects callers to `backtest-strategy`
2. Update `BacktestingView` if it still calls `strategy-backtest`
3. Remove `strategy-backtest` in a future cleanup PR (after confirming no callers)
4. Document `backtest-strategy` as the canonical endpoint in CLAUDE.md

**Effort:** Small | **Risk:** Low

## Acceptance Criteria

- [ ] `strategy-backtest` has a deprecation comment or 301 redirect to `backtest-strategy`
- [ ] All UI and agent callers use `backtest-strategy`
- [ ] CLAUDE.md documents `backtest-strategy` as the canonical backtest endpoint

## Work Log

- 2026-02-28: Identified by agent-native-reviewer in PR #23 code review
