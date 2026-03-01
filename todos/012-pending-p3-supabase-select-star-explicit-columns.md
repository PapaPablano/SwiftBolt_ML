---
status: pending
priority: p3
issue_id: "012"
tags: [code-review, performance, supabase, database]
dependencies: []
---

# 012: select("*") should use explicit column list

## Problem Statement

Both `fetchOpenPositions()` and `fetchTradeHistory()` use `.select("*")`, which transfers all columns from the database including any future columns added to these tables. Explicit column selection reduces payload size, prevents accidental exposure of new columns added by future migrations, and makes the data contract explicit and auditable.

## Findings

**File:** `client-macos/SwiftBoltML/Services/PaperTradingService.swift` lines 154-155, 165

```swift
.select("*")   // fetchOpenPositions — transfers all columns
.select("*")   // fetchTradeHistory — transfers all columns
```

`PaperPosition` decodes: `id, user_id, strategy_id, symbol_id, ticker, timeframe, entry_price, current_price, quantity, entry_time, direction, stop_loss_price, take_profit_price, status`

`PaperTrade` decodes: `id, user_id, strategy_id, symbol_id, ticker, timeframe, entry_price, exit_price, quantity, direction, entry_time, exit_time, pnl, pnl_pct, trade_reason, created_at`

**Source:** performance-oracle agent (P2)

## Proposed Solutions

### Option A: Explicit column selection (Recommended)

```swift
.select("id,user_id,strategy_id,symbol_id,ticker,timeframe,entry_price,current_price,quantity,entry_time,direction,stop_loss_price,take_profit_price,status")
```

```swift
.select("id,user_id,strategy_id,symbol_id,ticker,timeframe,entry_price,exit_price,quantity,direction,entry_time,exit_time,pnl,pnl_pct,trade_reason,created_at")
```
- **Pros:** Smaller payload; explicit contract; future-proof against added columns
- **Cons:** Must update when CodingKeys change; slightly verbose
- **Effort:** XSmall | **Risk:** Very Low

## Recommended Action

Option A. Quick win that should be done during the P1/P2 fix pass.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Services/PaperTradingService.swift` (2 query locations)

## Acceptance Criteria

- [ ] Both queries use explicit column list matching CodingKeys
- [ ] No decoding errors after change (all required keys present)
- [ ] Optional fields (`ticker`, `currentPrice`, etc.) still decode correctly as nil when absent

## Work Log

- 2026-02-28: Identified by performance-oracle review agent in PR #23 code review
