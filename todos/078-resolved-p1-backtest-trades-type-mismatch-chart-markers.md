---
status: resolved
priority: p1
issue_id: "078"
tags: [code-review, swift, backtest, chart, notification]
dependencies: []
---

# Backtest trades type mismatch — chart markers never render

## Problem Statement

`BacktestingViewModel` posts `display.trades` (type `[BacktestResponse.Trade]`, a Swift `Decodable` struct) over `NotificationCenter`. `WebChartView` attempts to cast it as `[[String: Any]]`, which always fails. The result is that `trades` is always `[]` and **no backtest entry/exit markers ever render on the chart**. The core overlay feature of PR #25 is non-functional.

## Findings

**File:** `client-macos/SwiftBoltML/ViewModels/BacktestingViewModel.swift`

```swift
NotificationCenter.default.post(
    name: .backtestTradesUpdated,
    object: nil,
    userInfo: [
        "trades": display.trades,   // ← [BacktestResponse.Trade] — a Swift struct
        "symbol": sym,
        "generation": generation
    ]
)
```

`BacktestResponse.Trade` is defined as:
```swift
// BacktestingModels.swift line 225
struct Trade: Decodable, Identifiable { ... }
```

**File:** `client-macos/SwiftBoltML/Views/WebChartView.swift` lines 258-268

```swift
// Receiver cast always fails:
let trades = notification.userInfo?["trades"] as? [[String: Any]] ?? []
// ↑ [BacktestResponse.Trade] cannot be cast to [[String: Any]] → always []
```

`ChartBridge.setBacktestTrades()` expects `[[String: Any]]` for JSONSerialization, so the type mismatch is at the boundary between the VM notification and the chart bridge.

## Proposed Solutions

### Option A: Serialize at post site (Recommended)

Convert `display.trades` to `[[String: Any]]` before posting:

```swift
let tradesPayload = display.trades.map { trade -> [String: Any] in
    [
        "id": trade.id.uuidString,
        "entryDate": trade.entryDate,
        "exitDate": trade.exitDate as Any,
        "entryPrice": trade.entryPrice,
        "exitPrice": trade.exitPrice as Any,
        "side": trade.side,
        "pnl": trade.pnl as Any,
        "pnlPercent": trade.pnlPercent as Any
    ]
}
NotificationCenter.default.post(
    name: .backtestTradesUpdated,
    object: nil,
    userInfo: ["trades": tradesPayload, "symbol": sym, "generation": generation]
)
```

**Pros:** Receiver code unchanged; clean boundary at VM. **Cons:** Manual mapping — must stay in sync with Trade struct.

### Option B: Pass struct, deserialize at receiver

Keep posting `[BacktestResponse.Trade]` but change `WebChartView` to accept it and convert to `[[String: Any]]` using JSONSerialization:

```swift
if let trades = notification.userInfo?["trades"] as? [BacktestResponse.Trade] {
    let data = try JSONEncoder().encode(trades)
    let tradesJSON = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] ?? []
    chartBridge.setBacktestTrades(tradesJSON)
}
```

**Pros:** Avoids manual mapping. **Cons:** Extra encode/decode round-trip; couples WebChartView to BacktestResponse.Trade type.

### Option C: Use JSONEncoder at post site

Encode trades to `Data` and post the encoded data:
```swift
let data = try? JSONEncoder().encode(display.trades)
userInfo: ["tradesData": data as Any, ...]
// Receiver: JSONSerialization.jsonObject(with: tradesData)
```

**Pros:** Type-safe, no manual mapping. **Cons:** More complex receiver code.

## Acceptance Criteria

- [ ] Backtest trade markers appear on the chart after a successful backtest
- [ ] `WebChartView` correctly receives and parses trade data from notification
- [ ] `ChartBridge.setBacktestTrades()` receives non-empty array when trades exist
- [ ] No force-cast or force-try in the conversion path

## Work Log

- 2026-03-02: Discovered during PR #25 review (Performance Oracle); confirmed by inspecting BacktestingModels.swift (Trade is `struct Decodable`) and WebChartView.swift cast site

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- File: `client-macos/SwiftBoltML/ViewModels/BacktestingViewModel.swift` (notification post)
- File: `client-macos/SwiftBoltML/Views/WebChartView.swift` lines 258-268 (notification receiver)
- File: `client-macos/SwiftBoltML/Services/ChartBridge.swift` (setBacktestTrades consumer)
