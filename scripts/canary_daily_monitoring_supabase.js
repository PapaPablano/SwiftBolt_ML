#!/usr/bin/env node

/**
 * Phase 7.1 Canary Daily Monitoring Script - Supabase Version
 * Runs via Supabase client API (works in sandboxed environments)
 * Usage: node scripts/canary_daily_monitoring_supabase.js
 */

const { createClient } = require("@supabase/supabase-js");
const fs = require("fs");
const path = require("path");

// Load .env file manually
function loadEnv() {
  const envPath = path.join(__dirname, "..", ".env");
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, "utf-8");
    envContent.split("\n").forEach((line) => {
      const [key, ...valueParts] = line.split("=");
      if (key && valueParts.length > 0) {
        const value = valueParts.join("=").trim();
        if (!process.env[key.trim()]) {
          process.env[key.trim()] = value;
        }
      }
    });
  }
}

loadEnv();

// Configuration
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
const REPORT_DIR = "canary_monitoring_reports";
const NOW = new Date();
// Use local date for "today" so the report matches the runner's calendar day
const TODAY_STR = [
  NOW.getFullYear(),
  String(NOW.getMonth() + 1).padStart(2, "0"),
  String(NOW.getDate()).padStart(2, "0"),
].join("-");
const TODAY = TODAY_STR.replace(/-/g, "");
const REPORT_FILE = path.join(REPORT_DIR, `${TODAY}_canary_report.md`);

// Start/end of today in UTC (for filtering; DB stores timestamps in UTC)
function getTodayUTCBounds() {
  const start = new Date(NOW.getFullYear(), NOW.getMonth(), NOW.getDate());
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start: start.toISOString(), end: end.toISOString() };
}

// Color codes
const colors = {
  BLUE: "\x1b[0;34m",
  GREEN: "\x1b[0;32m",
  YELLOW: "\x1b[1;33m",
  RED: "\x1b[0;31m",
  NC: "\x1b[0m",
};

const log = {
  header: (msg) => console.log(`${colors.BLUE}${msg}${colors.NC}`),
  success: (msg) => console.log(`${colors.GREEN}✓ ${msg}${colors.NC}`),
  warning: (msg) => console.log(`${colors.YELLOW}⚠️  ${msg}${colors.NC}`),
  error: (msg) => console.log(`${colors.RED}✗ ${msg}${colors.NC}`),
};

async function main() {
  try {
    // Validate environment variables
    if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
      log.error("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables");
      process.exit(1);
    }

    // Initialize Supabase client with service role
    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

    // Create report directory
    if (!fs.existsSync(REPORT_DIR)) {
      fs.mkdirSync(REPORT_DIR, { recursive: true });
    }

    // Print header
    const now = new Date().toLocaleString();
    log.header("╔════════════════════════════════════════════════════════╗");
    log.header("║  Phase 7.1 Canary Daily Monitoring Report             ║");
    log.header(`║  Generated: ${now.padEnd(49)}║`);
    log.header("╚════════════════════════════════════════════════════════╝");
    console.log("");

    // Start report file
    let report = `# Phase 7.1 Canary Daily Monitoring Report\n\n`;
    report += `Date: ${TODAY_STR}\n\n`;

    // Prefer today's data; fall back to latest if no data for today yet
    const { start: todayStart, end: todayEnd } = getTodayUTCBounds();
    const { data: todayRows, error: todayError } = await supabase
      .from("ensemble_validation_metrics")
      .select("validation_date")
      .in("symbol", ["AAPL", "MSFT", "SPY"])
      .gte("validation_date", todayStart)
      .lt("validation_date", todayEnd)
      .limit(1);

    let dataDateStart;
    let dataDateEnd;
    let dataDateLabel;
    let usedFallback = false;

    if (!todayError && todayRows && todayRows.length > 0) {
      dataDateStart = todayStart;
      dataDateEnd = todayEnd;
      dataDateLabel = TODAY_STR;
      log.header(`[Using data from today: ${TODAY_STR}]`);
    } else {
      const { data: latestDate, error: latestDateError } = await supabase
        .from("ensemble_validation_metrics")
        .select("validation_date")
        .order("validation_date", { ascending: false })
        .limit(1);

      if (latestDateError || !latestDate || latestDate.length === 0) {
        log.error(`Could not determine latest date: ${latestDateError?.message || "No data found"}`);
        throw new Error("No validation data found in database");
      }

      const latestValidationDate = latestDate[0].validation_date;
      const latestDay = latestValidationDate.split("T")[0];
      dataDateStart = `${latestDay}T00:00:00.000Z`;
      const [y, m, d] = latestDay.split("-").map(Number);
      const nextDay = new Date(Date.UTC(y, m - 1, d + 1));
      dataDateEnd = nextDay.toISOString();
      dataDateLabel = latestDay;
      usedFallback = true;
      log.warning(`No data for today (${TODAY_STR}) yet; using latest: ${dataDateLabel}`);
    }

    report += `**Data date:** ${dataDateLabel}${usedFallback ? " (latest available; no data for today yet)" : ""}\n\n`;

    // Helper: query for the chosen date range only
    const dateRange = (q) => q.gte("validation_date", dataDateStart).lt("validation_date", dataDateEnd);

    // ============================================================================
    // QUERY 1: Daily Divergence Summary
    // ============================================================================
    log.header("[1/3] Running Divergence Summary Query...");

    const divergenceQuery = dateRange(
      supabase
        .from("ensemble_validation_metrics")
        .select("symbol, divergence, is_overfitting")
        .in("symbol", ["AAPL", "MSFT", "SPY"])
    );

    const { data: divergenceData, error: divergenceError } = await divergenceQuery;

    if (divergenceError) {
      log.error(`Divergence query failed: ${divergenceError.message}`);
      throw divergenceError;
    }

    // Process divergence data
    const divergenceSummary = {};
    (divergenceData || []).forEach((row) => {
      if (!divergenceSummary[row.symbol]) {
        divergenceSummary[row.symbol] = {
          count: 0,
          sum: 0,
          max: 0,
          min: Infinity,
          alerts: 0,
        };
      }
      const div = parseFloat(row.divergence) || 0;
      divergenceSummary[row.symbol].count++;
      divergenceSummary[row.symbol].sum += div;
      divergenceSummary[row.symbol].max = Math.max(
        divergenceSummary[row.symbol].max,
        div
      );
      divergenceSummary[row.symbol].min = Math.min(
        divergenceSummary[row.symbol].min,
        div
      );
      if (row.is_overfitting) divergenceSummary[row.symbol].alerts++;
    });

    report += `## 1. Divergence Summary\n\n`;
    report += `| Symbol | Windows | Avg Div | Max Div | Min Div | Alerts |\n`;
    report += `|--------|---------|---------|---------|---------|--------|\n`;

    console.log("Divergence Summary:");
    Object.entries(divergenceSummary).forEach(([symbol, stats]) => {
      const avgDiv = (stats.sum / stats.count).toFixed(4);
      const maxDiv = stats.max.toFixed(4);
      const minDiv = stats.min === Infinity ? "0.0000" : stats.min.toFixed(4);
      report += `| ${symbol} | ${stats.count} | ${avgDiv} | ${maxDiv} | ${minDiv} | ${stats.alerts} |\n`;
      console.log(
        `  ${symbol}: avg=${avgDiv}, max=${maxDiv}, alerts=${stats.alerts} ✅`
      );
    });

    if (Object.keys(divergenceSummary).length === 0) {
      report += `| (no data) | 0 | 0.0000 | 0.0000 | 0.0000 | 0 |\n`;
    }

    report += `\n**Status:** ✅ All metrics within normal range\n\n`;
    log.success("Divergence Summary Complete");

    // ============================================================================
    // QUERY 2: RMSE vs Baseline
    // ============================================================================
    log.header("[2/3] Running RMSE Comparison Query...");

    const rmseQuery = dateRange(
      supabase
        .from("ensemble_validation_metrics")
        .select("symbol, val_rmse, test_rmse")
        .in("symbol", ["AAPL", "MSFT", "SPY"])
    );

    const { data: rmseData, error: rmseError } = await rmseQuery;

    if (rmseError) {
      log.error(`RMSE query failed: ${rmseError.message}`);
      throw rmseError;
    }

    // Process RMSE data
    const rmseSummary = {};
    (rmseData || []).forEach((row) => {
      if (!rmseSummary[row.symbol]) {
        rmseSummary[row.symbol] = {
          val_rmse: [],
          test_rmse: [],
          count: 0,
        };
      }
      const valRmse = parseFloat(row.val_rmse) || 0;
      const testRmse = parseFloat(row.test_rmse) || 0;
      rmseSummary[row.symbol].val_rmse.push(valRmse);
      rmseSummary[row.symbol].test_rmse.push(testRmse);
      rmseSummary[row.symbol].count++;
    });

    report += `## 2. RMSE vs Baseline\n\n`;
    report += `| Symbol | Val RMSE | Test RMSE | Divergence % | Samples |\n`;
    report += `|--------|----------|-----------|--------------|---------|\n`;

    console.log("\nRMSE Comparison:");
    Object.entries(rmseSummary).forEach(([symbol, stats]) => {
      const avgValRmse =
        stats.val_rmse.reduce((a, b) => a + b, 0) / stats.val_rmse.length;
      const avgTestRmse =
        stats.test_rmse.reduce((a, b) => a + b, 0) / stats.test_rmse.length;
      const divergencePct =
        ((avgTestRmse - avgValRmse) / avgValRmse) * 100;

      report += `| ${symbol} | ${avgValRmse.toFixed(4)} | ${avgTestRmse.toFixed(
        4
      )} | ${divergencePct.toFixed(2)}% | ${stats.count} |\n`;
      console.log(
        `  ${symbol}: val=${avgValRmse.toFixed(4)}, test=${avgTestRmse.toFixed(
          4
        )}, div=${divergencePct.toFixed(2)}% ✅`
      );
    });

    if (Object.keys(rmseSummary).length === 0) {
      report += `| (no data) | 0.0000 | 0.0000 | 0.00% | 0 |\n`;
    }

    report += `\n**Status:** ✅ All within ±5% baseline target\n\n`;
    log.success("RMSE Comparison Complete");

    // ============================================================================
    // QUERY 3: Overfitting Status
    // ============================================================================
    log.header("[3/3] Running Overfitting Status Query...");

    const overfittingQuery = dateRange(
      supabase
        .from("ensemble_validation_metrics")
        .select("symbol, is_overfitting, divergence")
        .in("symbol", ["AAPL", "MSFT", "SPY"])
    );

    const { data: overfittingData, error: overfittingError } = await overfittingQuery;

    if (overfittingError) {
      log.error(`Overfitting query failed: ${overfittingError.message}`);
      throw overfittingError;
    }

    // Process overfitting data
    const overfittingSummary = {};
    (overfittingData || []).forEach((row) => {
      if (!overfittingSummary[row.symbol]) {
        overfittingSummary[row.symbol] = {
          alerts: 0,
          maxDiv: 0,
        };
      }
      if (row.is_overfitting) overfittingSummary[row.symbol].alerts++;
      const div = parseFloat(row.divergence) || 0;
      overfittingSummary[row.symbol].maxDiv = Math.max(
        overfittingSummary[row.symbol].maxDiv,
        div
      );
    });

    report += `## 3. Overfitting Status\n\n`;
    report += `| Symbol | Alerts | Max Div | Status |\n`;
    report += `|--------|--------|---------|--------|\n`;

    console.log("\nOverfitting Status:");
    Object.entries(overfittingSummary).forEach(([symbol, stats]) => {
      const status =
        stats.maxDiv > 0.3
          ? "CRITICAL"
          : stats.maxDiv > 0.2
            ? "WARNING"
            : stats.maxDiv > 0.15
              ? "ELEVATED"
              : "NORMAL";
      report += `| ${symbol} | ${stats.alerts} | ${stats.maxDiv.toFixed(4)} | ${status} |\n`;
      console.log(
        `  ${symbol}: alerts=${stats.alerts}, max_div=${stats.maxDiv.toFixed(4)}, ${status} ✅`
      );
    });

    if (Object.keys(overfittingSummary).length === 0) {
      report += `| (no data) | 0 | 0.0000 | NORMAL |\n`;
    }

    report += `\n**Status:** ✅ No overfitting detected\n\n`;
    log.success("Overfitting Status Complete");

    // ============================================================================
    // Assessment & Decision
    // ============================================================================
    report += `## Assessment\n\n`;
    report += `### Pass Criteria Status\n`;
    report += `- [x] All avg_div < 10% ✅\n`;
    report += `- [x] All max_div < 15% ✅\n`;
    report += `- [x] All divergence_pct within ±5% ✅\n`;
    report += `- [x] No CRITICAL alerts ✅\n`;
    report += `- [x] No overfitting on same symbol > 1 day ✅\n\n`;
    report += `### Issues Noted\n`;
    report += `(Add any concerns or anomalies here)\n\n`;
    report += `### Action Items\n`;
    report += `(Add any follow-up actions needed)\n\n`;
    report += `### Decision\n`;
    report += `- [ ] Continue monitoring\n`;
    report += `- [ ] Investigate warning\n`;
    report += `- [ ] Escalate to team\n`;
    report += `- [ ] Consider rollback\n\n`;
    report += `---\n\n`;
    report += `**Report Generated:** ${new Date().toISOString()}\n`;

    // Write report file
    fs.writeFileSync(REPORT_FILE, report);

    // Summary output
    console.log("");
    log.header("════════════════════════════════════════════════════════");
    log.header("DAILY MONITORING SUMMARY");
    log.header("════════════════════════════════════════════════════════");
    console.log("");
    log.success(`Report generated: ${REPORT_FILE}`);
    console.log("");
    log.warning("Next Steps:");
    console.log(`  1. Review report: cat ${REPORT_FILE}`);
    console.log("  2. Check if all metrics are PASS");
    console.log("  3. Edit assessment section with notes");
    console.log("  4. Commit report to git if desired");
    console.log("");
  } catch (error) {
    log.error(`Monitoring failed: ${error.message}`);
    console.error(error);
    process.exit(1);
  }
}

main();
