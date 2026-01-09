#!/usr/bin/env -S deno run --allow-net --allow-env

/**
 * Alpaca API Connection Test Script
 * Tests authentication and basic API connectivity
 * 
 * Usage: deno run --allow-net --allow-env test_alpaca_connection.ts
 */

// IMPORTANT: Replace these with your actual credentials
// For security, use environment variables in production
const ALPACA_API_KEY = Deno.env.get("ALPACA_API_KEY") || "";
const ALPACA_API_SECRET = Deno.env.get("ALPACA_API_SECRET") || "";

// Auto-detect live vs paper trading based on key prefix
const isLiveTrading = ALPACA_API_KEY.startsWith("AK");
const BASE_URL = isLiveTrading ? "https://api.alpaca.markets/v2" : "https://paper-api.alpaca.markets/v2";
const DATA_URL = "https://data.alpaca.markets/v2";

// Create Basic Auth header
function createAuthHeader(key: string, secret: string): string {
  const credentials = `${key}:${secret}`;
  const encoded = btoa(credentials);
  return `Basic ${encoded}`;
}

// Test 1: Account Info (Trading API)
async function testAccountInfo() {
  console.log("\n🔍 Test 1: Account Information");
  console.log("=" .repeat(50));
  
  try {
    const response = await fetch(`${BASE_URL}/account`, {
      headers: {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
      },
    });

    if (response.ok) {
      const data = await response.json();
      console.log("✅ Account API: Connected");
      console.log(`   Account ID: ${data.id}`);
      console.log(`   Status: ${data.status}`);
      console.log(`   Currency: ${data.currency}`);
      return true;
    } else {
      const error = await response.text();
      console.log(`❌ Account API: Failed (${response.status})`);
      console.log(`   Error: ${error}`);
      return false;
    }
  } catch (error) {
    console.log(`❌ Account API: Error - ${error.message}`);
    return false;
  }
}

// Test 2: Market Data - Historical Bars
async function testHistoricalBars() {
  console.log("\n🔍 Test 2: Historical Market Data (Bars)");
  console.log("=" .repeat(50));
  
  try {
    const symbol = "AAPL";
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 7); // Last 7 days
    
    const url = `${DATA_URL}/stocks/${symbol}/bars?` +
      `timeframe=1Day&` +
      `start=${startDate.toISOString()}&` +
      `end=${new Date().toISOString()}&` +
      `limit=10&` +
      `feed=iex`;

    const response = await fetch(url, {
      headers: {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        "Accept": "application/json",
      },
    });

    if (response.ok) {
      const data = await response.json();
      const bars = data.bars?.[symbol] || [];
      console.log(`✅ Market Data API: Connected`);
      console.log(`   Symbol: ${symbol}`);
      console.log(`   Bars Retrieved: ${bars.length}`);
      if (bars.length > 0) {
        const latest = bars[bars.length - 1];
        console.log(`   Latest Bar: ${latest.t}`);
        console.log(`   Close: $${latest.c}`);
        console.log(`   Volume: ${latest.v.toLocaleString()}`);
      }
      return true;
    } else {
      const error = await response.text();
      console.log(`❌ Market Data API: Failed (${response.status})`);
      console.log(`   Error: ${error}`);
      return false;
    }
  } catch (error) {
    console.log(`❌ Market Data API: Error - ${error.message}`);
    return false;
  }
}

// Test 3: Real-time Quote (Snapshot)
async function testSnapshot() {
  console.log("\n🔍 Test 3: Real-time Quote (Snapshot)");
  console.log("=" .repeat(50));
  
  try {
    const symbols = "AAPL,MSFT";
    
    const url = `${DATA_URL}/stocks/snapshots?symbols=${symbols}&feed=iex`;

    const response = await fetch(url, {
      headers: {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        "Accept": "application/json",
      },
    });

    if (response.ok) {
      const data = await response.json();
      console.log(`✅ Snapshot API: Connected`);
      
      for (const [symbol, snapshot] of Object.entries(data)) {
        const snap = snapshot as any;
        if (snap.latestTrade) {
          console.log(`   ${symbol}: $${snap.latestTrade.p} (${snap.latestTrade.t})`);
        }
      }
      return true;
    } else {
      const error = await response.text();
      console.log(`❌ Snapshot API: Failed (${response.status})`);
      console.log(`   Error: ${error}`);
      return false;
    }
  } catch (error) {
    console.log(`❌ Snapshot API: Error - ${error.message}`);
    return false;
  }
}

// Test 4: News Feed
async function testNews() {
  console.log("\n🔍 Test 4: News Feed");
  console.log("=" .repeat(50));
  
  try {
    const url = `${DATA_URL}/news?symbols=AAPL&limit=5&sort=desc`;

    const response = await fetch(url, {
      headers: {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        "Accept": "application/json",
      },
    });

    if (response.ok) {
      const data = await response.json();
      const news = data.news || [];
      console.log(`✅ News API: Connected`);
      console.log(`   Articles Retrieved: ${news.length}`);
      if (news.length > 0) {
        console.log(`   Latest: ${news[0].headline.substring(0, 60)}...`);
      }
      return true;
    } else {
      const error = await response.text();
      console.log(`❌ News API: Failed (${response.status})`);
      console.log(`   Error: ${error}`);
      return false;
    }
  } catch (error) {
    console.log(`❌ News API: Error - ${error.message}`);
    return false;
  }
}

// Main test runner
async function main() {
  console.log("\n" + "=".repeat(50));
  console.log("🚀 Alpaca API Connection Test");
  console.log("=".repeat(50));
  console.log(`Account Type: ${isLiveTrading ? 'LIVE TRADING' : 'PAPER TRADING'}`);
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Data URL: ${DATA_URL}`);
  console.log(`API Key: ${ALPACA_API_KEY.substring(0, 8)}...`);
  
  if (!ALPACA_API_SECRET) {
    console.log("\n⚠️  WARNING: ALPACA_API_SECRET not set!");
    console.log("Please set it via environment variable or update the script.");
    console.log("\nUsage:");
    console.log("  export ALPACA_API_KEY=your-key");
    console.log("  export ALPACA_API_SECRET=your-secret");
    console.log("  deno run --allow-net --allow-env test_alpaca_connection.ts");
    Deno.exit(1);
  }

  const results = {
    account: await testAccountInfo(),
    historicalBars: await testHistoricalBars(),
    snapshot: await testSnapshot(),
    news: await testNews(),
  };

  // Summary
  console.log("\n" + "=".repeat(50));
  console.log("📊 Test Summary");
  console.log("=".repeat(50));
  
  const passed = Object.values(results).filter(r => r).length;
  const total = Object.keys(results).length;
  
  console.log(`Account API:        ${results.account ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`Historical Bars:    ${results.historicalBars ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`Real-time Snapshot: ${results.snapshot ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`News Feed:          ${results.news ? '✅ PASS' : '❌ FAIL'}`);
  console.log("\n" + "=".repeat(50));
  console.log(`Result: ${passed}/${total} tests passed`);
  
  if (passed === total) {
    console.log("🎉 All tests passed! Alpaca integration is ready.");
    Deno.exit(0);
  } else {
    console.log("⚠️  Some tests failed. Check your credentials and API access.");
    Deno.exit(1);
  }
}

// Run tests
if (import.meta.main) {
  main();
}
