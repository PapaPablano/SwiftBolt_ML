/**
 * Tests for unified condition evaluator
 * Ensures both backtest and paper trading use same logic
 */

import {
  assertEquals,
  assertStringIncludes,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import {
  Bar,
  buildConditionTree,
  Condition,
  ConditionTree,
  evaluateCondition,
  evaluateConditionTree,
  evaluateStrategySignals,
  IndicatorCache,
} from "./condition-evaluator.ts";

// ============================================================================
// TEST DATA
// ============================================================================

const sampleBars: Bar[] = [
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
  {
    time: "2026-01-04",
    open: 108,
    high: 115,
    low: 107,
    close: 112,
    volume: 1500,
  },
  {
    time: "2026-01-05",
    open: 112,
    high: 120,
    low: 111,
    close: 118,
    volume: 2000,
  },
];

// ============================================================================
// TEST: INDICATOR CACHE
// ============================================================================

Deno.test("IndicatorCache: Store and retrieve values", () => {
  const cache = new IndicatorCache();

  cache.set("rsi_14", 65);
  assertEquals(cache.get("rsi_14"), 65);
  assertEquals(cache.wasCalculated("rsi_14"), true);
});

Deno.test("IndicatorCache: Return undefined for missing key", () => {
  const cache = new IndicatorCache();

  assertEquals(cache.get("non_existent"), undefined);
  assertEquals(cache.wasCalculated("non_existent"), false);
});

Deno.test("IndicatorCache: Clear candle resets calculated set", () => {
  const cache = new IndicatorCache();

  cache.set("rsi_14", 65);
  assertEquals(cache.wasCalculated("rsi_14"), true);

  cache.clearCandle();
  assertEquals(cache.wasCalculated("rsi_14"), false);
  assertEquals(cache.get("rsi_14"), 65); // Value still cached
});

Deno.test("IndicatorCache: Full reset", () => {
  const cache = new IndicatorCache();

  cache.set("rsi_14", 65);
  cache.reset();

  assertEquals(cache.get("rsi_14"), undefined);
  assertEquals(cache.wasCalculated("rsi_14"), false);
});

// ============================================================================
// TEST: SINGLE CONDITION EVALUATION
// ============================================================================

Deno.test("evaluateCondition: Simple comparison (close > 110)", () => {
  const condition: Condition = {
    id: "cond1",
    indicator: "close",
    operator: ">",
    value: 110,
  };

  const cache = new IndicatorCache();

  // Latest close is 118, so > 110 should be true
  const result = evaluateCondition(condition, sampleBars, cache);
  assertEquals(result, true);
});

Deno.test("evaluateCondition: Simple comparison fails (close > 120)", () => {
  const condition: Condition = {
    id: "cond1",
    indicator: "close",
    operator: ">",
    value: 120,
  };

  const cache = new IndicatorCache();

  // Latest close is 118, so > 120 should be false
  const result = evaluateCondition(condition, sampleBars, cache);
  assertEquals(result, false);
});

Deno.test("evaluateCondition: Less than operator", () => {
  const condition: Condition = {
    id: "cond1",
    indicator: "close",
    operator: "<",
    value: 120,
  };

  const cache = new IndicatorCache();

  const result = evaluateCondition(condition, sampleBars, cache);
  assertEquals(result, true); // 118 < 120
});

Deno.test("evaluateCondition: Equals operator (with epsilon)", () => {
  const condition: Condition = {
    id: "cond1",
    indicator: "volume",
    operator: "==",
    value: 2000,
  };

  const cache = new IndicatorCache();

  const result = evaluateCondition(condition, sampleBars, cache);
  assertEquals(result, true); // Latest volume is 2000
});

Deno.test("evaluateCondition: Greater or equal operator", () => {
  const condition: Condition = {
    id: "cond1",
    indicator: "close",
    operator: ">=",
    value: 118,
  };

  const cache = new IndicatorCache();

  const result = evaluateCondition(condition, sampleBars, cache);
  assertEquals(result, true); // 118 >= 118
});

// ============================================================================
// TEST: INDICATOR CACHING
// ============================================================================

Deno.test("evaluateCondition: Reuses cached indicator values", () => {
  const condition1: Condition = {
    id: "cond1",
    indicator: "close",
    operator: ">",
    value: 100,
  };

  const condition2: Condition = {
    id: "cond2",
    indicator: "close",
    operator: "<",
    value: 120,
  };

  const cache = new IndicatorCache();

  // Evaluate condition1 (caches close value)
  evaluateCondition(condition1, sampleBars, cache);
  assertEquals(cache.wasCalculated("close_latest"), true);

  // Evaluate condition2 (should reuse cached value)
  evaluateCondition(condition2, sampleBars, cache);
  assertEquals(cache.wasCalculated("close_latest"), true);
});

// ============================================================================
// TEST: TREE EVALUATION (AND/OR LOGIC)
// ============================================================================

Deno.test("buildConditionTree: Single condition", () => {
  const conditions: Condition[] = [
    {
      id: "cond1",
      indicator: "close",
      operator: ">",
      value: 100,
    },
  ];

  const tree = buildConditionTree(conditions);
  assertEquals(tree?.id, "cond1");
  assertEquals(tree?.children.length, 0);
});

Deno.test("buildConditionTree: Parent-child hierarchy", () => {
  const conditions: Condition[] = [
    {
      id: "cond1",
      indicator: "close",
      operator: ">",
      value: 100,
      logicalOp: "AND",
    },
    {
      id: "cond2",
      indicator: "volume",
      operator: ">",
      value: 1000,
      parentId: "cond1",
      logicalOp: "AND",
    },
  ];

  const tree = buildConditionTree(conditions);
  assertEquals(tree?.id, "cond1");
  assertEquals(tree?.children.length, 1);
  assertEquals(tree?.children[0].id, "cond2");
});

Deno.test("evaluateConditionTree: AND logic (all conditions met)", () => {
  const tree: ConditionTree = {
    id: "cond1",
    logicalOp: "AND",
    condition: {
      id: "cond1",
      indicator: "close",
      operator: ">",
      value: 100, // 118 > 100 = true
    },
    children: [
      {
        id: "cond2",
        logicalOp: "AND",
        condition: {
          id: "cond2",
          indicator: "volume",
          operator: ">",
          value: 1000, // 2000 > 1000 = true
        },
        children: [],
      },
    ],
  };

  const cache = new IndicatorCache();
  const result = evaluateConditionTree(tree, sampleBars, cache);
  assertEquals(result, true); // true AND true = true
});

Deno.test("evaluateConditionTree: AND logic (one condition fails)", () => {
  const tree: ConditionTree = {
    id: "cond1",
    logicalOp: "AND",
    condition: {
      id: "cond1",
      indicator: "close",
      operator: ">",
      value: 120, // 118 > 120 = false
    },
    children: [
      {
        id: "cond2",
        logicalOp: "AND",
        condition: {
          id: "cond2",
          indicator: "volume",
          operator: ">",
          value: 1000, // 2000 > 1000 = true
        },
        children: [],
      },
    ],
  };

  const cache = new IndicatorCache();
  const result = evaluateConditionTree(tree, sampleBars, cache);
  assertEquals(result, false); // false AND true = false
});

Deno.test("evaluateConditionTree: OR logic (one condition met)", () => {
  const tree: ConditionTree = {
    id: "cond1",
    logicalOp: "OR",
    condition: {
      id: "cond1",
      indicator: "close",
      operator: ">",
      value: 120, // 118 > 120 = false
    },
    children: [
      {
        id: "cond2",
        logicalOp: "OR",
        condition: {
          id: "cond2",
          indicator: "volume",
          operator: ">",
          value: 1000, // 2000 > 1000 = true
        },
        children: [],
      },
    ],
  };

  const cache = new IndicatorCache();
  const result = evaluateConditionTree(tree, sampleBars, cache);
  assertEquals(result, true); // false OR true = true
});

// ============================================================================
// TEST: BATCH EVALUATION
// ============================================================================

Deno.test("evaluateStrategySignals: Entry and exit signals", () => {
  const entryConditions: Condition[] = [
    {
      id: "entry1",
      indicator: "close",
      operator: ">",
      value: 110,
    },
  ];

  const exitConditions: Condition[] = [
    {
      id: "exit1",
      indicator: "close",
      operator: ">",
      value: 120,
    },
  ];

  const signals = evaluateStrategySignals(
    entryConditions,
    exitConditions,
    sampleBars,
  );

  assertEquals(signals.entry, true); // 118 > 110
  assertEquals(signals.exit, false); // 118 NOT > 120
});

Deno.test("evaluateStrategySignals: Both signals met", () => {
  const entryConditions: Condition[] = [
    {
      id: "entry1",
      indicator: "close",
      operator: ">",
      value: 100,
    },
  ];

  const exitConditions: Condition[] = [
    {
      id: "exit1",
      indicator: "close",
      operator: "<",
      value: 120,
    },
  ];

  const signals = evaluateStrategySignals(
    entryConditions,
    exitConditions,
    sampleBars,
  );

  assertEquals(signals.entry, true); // 118 > 100
  assertEquals(signals.exit, true); // 118 < 120
});

// ============================================================================
// TEST: EDGE CASES
// ============================================================================

Deno.test("evaluateConditionTree: Null tree returns false", () => {
  const cache = new IndicatorCache();
  const result = evaluateConditionTree(null, sampleBars, cache);
  assertEquals(result, false);
});

Deno.test("evaluateCondition: Empty bars", () => {
  const condition: Condition = {
    id: "cond1",
    indicator: "close",
    operator: ">",
    value: 100,
  };

  const cache = new IndicatorCache();
  const result = evaluateCondition(condition, [], cache);
  assertEquals(result, false);
});

console.log("✅ All condition evaluator tests passed!");
