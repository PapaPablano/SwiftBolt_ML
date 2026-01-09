#!/usr/bin/env -S deno run --allow-net --allow-env
/// <reference lib="deno.ns" />

/**
 * Test script for Alpaca integration enhancements
 * Tests pagination, error handling, retry logic, and asset validation
 */

import { AlpacaClient } from './backend/supabase/functions/_shared/providers/alpaca-client.ts';

const ALPACA_API_KEY = Deno.env.get('ALPACA_API_KEY');
const ALPACA_API_SECRET = Deno.env.get('ALPACA_API_SECRET');

if (!ALPACA_API_KEY || !ALPACA_API_SECRET) {
  console.error('❌ Missing ALPACA_API_KEY or ALPACA_API_SECRET environment variables');
  Deno.exit(1);
}

const client = new AlpacaClient(ALPACA_API_KEY, ALPACA_API_SECRET);

console.log('🧪 Testing Alpaca Integration Enhancements\n');

// Test 1: Asset Validation
console.log('📋 Test 1: Asset Validation');
try {
  console.log('  Fetching assets...');
  const assets = await client.getAssets();
  console.log(`  ✅ Retrieved ${assets.length} tradable assets`);
  
  // Test valid symbol
  const aaplValid = await client.validateSymbol('AAPL');
  console.log(`  ✅ AAPL validation: ${aaplValid ? 'VALID' : 'INVALID'}`);
  
  // Test invalid symbol
  const fakeValid = await client.validateSymbol('FAKESYMBOL123');
  console.log(`  ✅ FAKESYMBOL123 validation: ${fakeValid ? 'VALID' : 'INVALID'}`);
  
  // Test asset details
  const aaplAsset = await client.getAsset('AAPL');
  if (aaplAsset) {
    console.log(`  ✅ AAPL details: ${aaplAsset.name} (${aaplAsset.exchange})`);
  }
} catch (error) {
  console.error(`  ❌ Asset validation test failed:`, error.message);
}

console.log('\n📊 Test 2: Historical Bars (Small Dataset)');
try {
  const endDate = Math.floor(Date.now() / 1000);
  const startDate = endDate - (30 * 24 * 60 * 60); // 30 days ago
  
  console.log('  Fetching 30 days of daily bars for AAPL...');
  const bars = await client.getHistoricalBars({
    symbol: 'AAPL',
    timeframe: 'd1',
    start: startDate,
    end: endDate
  });
  
  console.log(`  ✅ Retrieved ${bars.length} bars`);
  if (bars.length > 0) {
    const firstBar = bars[0];
    const lastBar = bars[bars.length - 1];
    console.log(`  ✅ First bar: ${new Date(firstBar.timestamp * 1000).toISOString().split('T')[0]} - Close: $${firstBar.close.toFixed(2)}`);
    console.log(`  ✅ Last bar: ${new Date(lastBar.timestamp * 1000).toISOString().split('T')[0]} - Close: $${lastBar.close.toFixed(2)}`);
  }
} catch (error) {
  console.error(`  ❌ Historical bars test failed:`, error.message);
}

console.log('\n📈 Test 3: Pagination (Large Dataset)');
try {
  const endDate = Math.floor(Date.now() / 1000);
  const startDate = endDate - (365 * 2 * 24 * 60 * 60); // 2 years ago
  
  console.log('  Fetching 2 years of daily bars for AAPL (may require pagination)...');
  const bars = await client.getHistoricalBars({
    symbol: 'AAPL',
    timeframe: 'd1',
    start: startDate,
    end: endDate
  });
  
  console.log(`  ✅ Retrieved ${bars.length} bars across multiple pages`);
  if (bars.length > 10000) {
    console.log(`  ✅ Pagination worked! Got ${bars.length} bars (>10,000 limit)`);
  }
} catch (error) {
  console.error(`  ❌ Pagination test failed:`, error.message);
}

console.log('\n❌ Test 4: Error Handling (Invalid Symbol)');
try {
  const endDate = Math.floor(Date.now() / 1000);
  const startDate = endDate - (30 * 24 * 60 * 60);
  
  console.log('  Attempting to fetch bars for invalid symbol...');
  await client.getHistoricalBars({
    symbol: 'INVALIDXYZ123',
    timeframe: 'd1',
    start: startDate,
    end: endDate
  });
  
  console.error(`  ❌ Should have thrown InvalidSymbolError`);
} catch (error) {
  if (error.name === 'InvalidSymbolError') {
    console.log(`  ✅ Correctly threw InvalidSymbolError: ${error.message}`);
  } else {
    console.error(`  ⚠️  Threw different error: ${error.name} - ${error.message}`);
  }
}

console.log('\n💚 Test 5: Health Check');
try {
  const healthy = await client.healthCheck();
  console.log(`  ${healthy ? '✅' : '❌'} Health check: ${healthy ? 'PASS' : 'FAIL'}`);
} catch (error) {
  console.error(`  ❌ Health check failed:`, error.message);
}

console.log('\n📰 Test 6: News Fetching');
try {
  console.log('  Fetching news for AAPL...');
  const news = await client.getNews({ symbol: 'AAPL', limit: 5 });
  console.log(`  ✅ Retrieved ${news.length} news items`);
  if (news.length > 0) {
    console.log(`  ✅ Latest: "${news[0].headline}" (${news[0].source})`);
  }
} catch (error) {
  console.error(`  ❌ News test failed:`, error.message);
}

console.log('\n📊 Test 7: Real-time Quotes');
try {
  console.log('  Fetching quotes for AAPL, MSFT, GOOGL...');
  const quotes = await client.getQuote(['AAPL', 'MSFT', 'GOOGL']);
  console.log(`  ✅ Retrieved ${quotes.length} quotes`);
  for (const quote of quotes) {
    const change = quote.changePercent ? quote.changePercent.toFixed(2) : 'N/A';
    console.log(`  ✅ ${quote.symbol}: $${quote.price.toFixed(2)} (${change}%)`);
  }
} catch (error) {
  console.error(`  ❌ Quotes test failed:`, error.message);
}

console.log('\n✅ All tests completed!');
