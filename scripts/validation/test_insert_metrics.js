#!/usr/bin/env node
const { createClient } = require("@supabase/supabase-js");

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
  console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables");
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

(async () => {
  console.log("Inserting test divergence metrics for AAPL, MSFT, SPY...");

  const testData = [
    {
      symbol_id: "symbol_aapl",
      symbol: "AAPL",
      horizon: "1D",
      validation_date: new Date().toISOString(),
      window_id: 1,
      val_rmse: 0.045,
      test_rmse: 0.0468,
      divergence: 0.04,
      is_overfitting: false,
      model_count: 2,
      models_used: ["LSTM", "ARIMA_GARCH"],
      divergence_threshold: 0.2,
    },
    {
      symbol_id: "symbol_msft",
      symbol: "MSFT",
      horizon: "1D",
      validation_date: new Date().toISOString(),
      window_id: 1,
      val_rmse: 0.048,
      test_rmse: 0.0495,
      divergence: 0.0313,
      is_overfitting: false,
      model_count: 2,
      models_used: ["LSTM", "ARIMA_GARCH"],
      divergence_threshold: 0.2,
    },
    {
      symbol_id: "symbol_spy",
      symbol: "SPY",
      horizon: "1D",
      validation_date: new Date().toISOString(),
      window_id: 1,
      val_rmse: 0.052,
      test_rmse: 0.054,
      divergence: 0.0385,
      is_overfitting: false,
      model_count: 2,
      models_used: ["LSTM", "ARIMA_GARCH"],
      divergence_threshold: 0.2,
    },
  ];

  const { data, error } = await supabase
    .from("ensemble_validation_metrics")
    .insert(testData);

  if (error) {
    console.error("✗ Insert failed:", error);
    process.exit(1);
  }

  console.log("✓ Inserted 3 test records successfully\n");
  console.log("Data inserted:");
  testData.forEach((d) => {
    console.log(
      `  ${d.symbol} 1D: divergence=${(d.divergence * 100).toFixed(2)}%, ` +
      `overfitting=${d.is_overfitting}`
    );
  });

  console.log("\nNow run:");
  console.log("  node scripts/canary_daily_monitoring_supabase.js");
  console.log("\nYou should see real data in the monitoring report.");
})();
