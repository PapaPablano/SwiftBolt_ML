/**
 * Test suite for validators
 * Ensures market data, position constraints, and risk parameters are validated correctly
 */

import {
  assertEquals,
  assertObjectMatch,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import {
  Bar,
  PositionConstraints,
  validateBeforeExecution,
  validateMarketData,
  validateOperator,
  validatePositionConstraints,
  validateSlippage,
  validateSLTPBounds,
} from "./validators.ts";

// ============================================================================
// TEST: MARKET DATA VALIDATION
// ============================================================================

Deno.test("validateMarketData: Valid bars", () => {
  const validBars: Bar[] = [
    {
      time: "2026-01-01",
      open: 100,
      high: 105,
      low: 99,
      close: 102,
      volume: 1000,
    },
    {
      time: "2026-01-02",
      open: 102,
      high: 108,
      low: 101,
      close: 105,
      volume: 1200,
    },
    {
      time: "2026-01-03",
      open: 105,
      high: 110,
      low: 104,
      close: 108,
      volume: 1100,
    },
  ];

  const result = validateMarketData(validBars);
  assertEquals(result.valid, true);
  assertEquals(result.errors.length, 0);
});

Deno.test("validateMarketData: Null bars", () => {
  const result = validateMarketData(null);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("No market data")), true);
});

Deno.test("validateMarketData: Empty array", () => {
  const result = validateMarketData([]);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("empty")), true);
});

Deno.test("validateMarketData: Single bar (need minimum 2)", () => {
  const bars: Bar[] = [
    {
      time: "2026-01-01",
      open: 100,
      high: 105,
      low: 99,
      close: 102,
      volume: 1000,
    },
  ];
  const result = validateMarketData(bars);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("at least 2 bars")), true);
});

Deno.test("validateMarketData: Null OHLC values", () => {
  const barsWithNulls: any[] = [
    {
      time: "2026-01-01",
      open: null,
      high: 105,
      low: 99,
      close: 102,
      volume: 1000,
    },
    {
      time: "2026-01-02",
      open: 102,
      high: 108,
      low: 101,
      close: 105,
      volume: 1200,
    },
  ];
  const result = validateMarketData(barsWithNulls);
  assertEquals(result.valid, false);
  assertEquals(
    result.errors.some((e) => e.includes("Open price is null")),
    true,
  );
});

Deno.test("validateMarketData: Negative prices", () => {
  const negativeBar: Bar[] = [
    {
      time: "2026-01-01",
      open: -100,
      high: 105,
      low: 99,
      close: 102,
      volume: 1000,
    },
    {
      time: "2026-01-02",
      open: 102,
      high: 108,
      low: 101,
      close: 105,
      volume: 1200,
    },
  ];
  const result = validateMarketData(negativeBar);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("negative")), true);
});

Deno.test("validateMarketData: Close outside [Low, High]", () => {
  const invalidBar: Bar[] = [
    {
      time: "2026-01-01",
      open: 100,
      high: 105,
      low: 99,
      close: 110,
      volume: 1000,
    }, // close > high
    {
      time: "2026-01-02",
      open: 102,
      high: 108,
      low: 101,
      close: 105,
      volume: 1200,
    },
  ];
  const result = validateMarketData(invalidBar);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("outside")), true);
});

Deno.test("validateMarketData: Large gap (>15%)", () => {
  const gapBars: Bar[] = [
    {
      time: "2026-01-01",
      open: 100,
      high: 105,
      low: 99,
      close: 100,
      volume: 1000,
    },
    {
      time: "2026-01-02",
      open: 120,
      high: 125,
      low: 119,
      close: 122,
      volume: 1200,
    }, // 20% gap
  ];
  const result = validateMarketData(gapBars);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("Gap detected")), true);
});

// ============================================================================
// TEST: POSITION CONSTRAINTS VALIDATION
// ============================================================================

Deno.test("validatePositionConstraints: Valid long position", () => {
  const constraints: PositionConstraints = {
    entryPrice: 100,
    quantity: 50,
    slPct: 2,
    tpPct: 5,
    direction: "long",
  };
  const result = validatePositionConstraints(constraints);
  assertEquals(result.valid, true);
  assertEquals(result.errors.length, 0);
});

Deno.test("validatePositionConstraints: Valid short position", () => {
  const constraints: PositionConstraints = {
    entryPrice: 100,
    quantity: 50,
    slPct: 2,
    tpPct: 5,
    direction: "short",
  };
  const result = validatePositionConstraints(constraints);
  assertEquals(result.valid, true);
  assertEquals(result.errors.length, 0);
});

Deno.test("validatePositionConstraints: Invalid entry price (zero)", () => {
  const constraints: PositionConstraints = {
    entryPrice: 0,
    quantity: 50,
    slPct: 2,
    tpPct: 5,
    direction: "long",
  };
  const result = validatePositionConstraints(constraints);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("Entry price")), true);
});

Deno.test("validatePositionConstraints: Quantity out of bounds (too large)", () => {
  const constraints: PositionConstraints = {
    entryPrice: 100,
    quantity: 5000,
    slPct: 2,
    tpPct: 5,
    direction: "long",
  };
  const result = validatePositionConstraints(constraints);
  assertEquals(result.valid, false);
  assertEquals(
    result.errors.some((e) => e.includes("Quantity out of bounds")),
    true,
  );
});

Deno.test("validatePositionConstraints: SL out of bounds (too small)", () => {
  const constraints: PositionConstraints = {
    entryPrice: 100,
    quantity: 50,
    slPct: 0.01, // < 0.1%
    tpPct: 5,
    direction: "long",
  };
  const result = validatePositionConstraints(constraints);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("Stop loss")), true);
});

Deno.test("validatePositionConstraints: Valid risk/reward", () => {
  // For a long: SL=-2%, TP=+5% is valid (risk $2 to gain $5)
  const constraints: PositionConstraints = {
    entryPrice: 100,
    quantity: 50,
    slPct: 2,
    tpPct: 5,
    direction: "long",
  };
  const result = validatePositionConstraints(constraints);
  assertEquals(result.valid, true);
});

// ============================================================================
// TEST: SLIPPAGE VALIDATION
// ============================================================================

Deno.test("validateSlippage: Valid slippage (2%)", () => {
  const result = validateSlippage(2.0);
  assertEquals(result.valid, true);
  assertEquals(result.errors.length, 0);
});

Deno.test("validateSlippage: Too small (<0.01%)", () => {
  const result = validateSlippage(0.001);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("too small")), true);
});

Deno.test("validateSlippage: Too large (>5%)", () => {
  const result = validateSlippage(10.0);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("too large")), true);
});

Deno.test("validateSlippage: Invalid number", () => {
  const result = validateSlippage(NaN);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("valid number")), true);
});

// ============================================================================
// TEST: SL/TP BOUNDS VALIDATION
// ============================================================================

Deno.test("validateSLTPBounds: Valid bounds", () => {
  const result = validateSLTPBounds({ slPct: 2, tpPct: 5 });
  assertEquals(result.valid, true);
  assertEquals(result.errors.length, 0);
});

Deno.test("validateSLTPBounds: SL too small", () => {
  const result = validateSLTPBounds({ slPct: 0.05, tpPct: 5 });
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("SL too small")), true);
});

Deno.test("validateSLTPBounds: TP <= SL", () => {
  const result = validateSLTPBounds({ slPct: 10, tpPct: 5 });
  assertEquals(result.valid, false);
  assertEquals(
    result.errors.some((e) => e.includes("TP") && e.includes("SL")),
    true,
  );
});

// ============================================================================
// TEST: OPERATOR VALIDATION
// ============================================================================

Deno.test("validateOperator: Valid operator with number", () => {
  const result = validateOperator(">", 70);
  assertEquals(result.valid, true);
  assertEquals(result.errors.length, 0);
});

Deno.test("validateOperator: Cross operator without crossWith", () => {
  const result = validateOperator("cross_up", 50);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("crossWith")), true);
});

Deno.test("validateOperator: Cross operator with crossWith", () => {
  const result = validateOperator("cross_up", 50, "MA50");
  assertEquals(result.valid, true);
  assertEquals(result.errors.length, 0);
});

Deno.test("validateOperator: Invalid operator", () => {
  const result = validateOperator("invalid_op" as any, 50);
  assertEquals(result.valid, false);
  assertEquals(result.errors.some((e) => e.includes("Invalid operator")), true);
});

// ============================================================================
// TEST: BATCH VALIDATION
// ============================================================================

Deno.test("validateBeforeExecution: All valid", () => {
  const bars: Bar[] = [
    {
      time: "2026-01-01",
      open: 100,
      high: 105,
      low: 99,
      close: 102,
      volume: 1000,
    },
    {
      time: "2026-01-02",
      open: 102,
      high: 108,
      low: 101,
      close: 105,
      volume: 1200,
    },
  ];

  const constraints: PositionConstraints = {
    entryPrice: 105,
    quantity: 50,
    slPct: 2,
    tpPct: 5,
    direction: "long",
  };

  const result = validateBeforeExecution(bars, constraints, 2.0);
  assertEquals(result.valid, true);
  assertEquals(result.errors.length, 0);
});

Deno.test("validateBeforeExecution: Multiple errors", () => {
  const invalidBars: Bar[] = [
    {
      time: "2026-01-01",
      open: null as any,
      high: 105,
      low: 99,
      close: 102,
      volume: 1000,
    },
    {
      time: "2026-01-02",
      open: 102,
      high: 108,
      low: 101,
      close: 105,
      volume: 1200,
    },
  ];

  const constraints: PositionConstraints = {
    entryPrice: 0, // Invalid
    quantity: 5000, // Invalid
    slPct: 0.01, // Invalid
    tpPct: 5,
    direction: "long",
  };

  const result = validateBeforeExecution(invalidBars, constraints, 10.0); // Invalid slippage
  assertEquals(result.valid, false);
  assertEquals(result.errors.length > 3, true); // Multiple errors
});

console.log("✅ All validator tests passed!");
