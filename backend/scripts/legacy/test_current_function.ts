#!/usr/bin/env -S deno run --allow-net --allow-env

// Test what the current database function returns
// This will show us if the fix is applied or not

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') || 'https://cygflaemtmwiwaviclks.supabase.co';
const SUPABASE_KEY = Deno.env.get('SUPABASE_ANON_KEY');

if (!SUPABASE_KEY) {
  console.error('❌ SUPABASE_ANON_KEY not set');
  Deno.exit(1);
}

console.log('🔍 Testing current database function...\n');

// Get AAPL symbol_id
const symbolResp = await fetch(`${SUPABASE_URL}/rest/v1/symbols?ticker=eq.AAPL&select=id`, {
  headers: {
    'apikey': SUPABASE_KEY,
    'Authorization': `Bearer ${SUPABASE_KEY}`
  }
});

const symbols = await symbolResp.json();
if (!symbols || symbols.length === 0) {
  console.error('❌ Could not find AAPL symbol');
  Deno.exit(1);
}

const symbolId = symbols[0].id;
console.log(`✅ Found AAPL: ${symbolId}\n`);

// Test the function
console.log('📊 Calling get_chart_data_v2_dynamic for d1 timeframe...');
const funcResp = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_chart_data_v2_dynamic`, {
  method: 'POST',
  headers: {
    'apikey': SUPABASE_KEY,
    'Authorization': `Bearer ${SUPABASE_KEY}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    p_symbol_id: symbolId,
    p_timeframe: 'd1',
    p_max_bars: 10,
    p_include_forecast: false
  })
});

const data = await funcResp.json();

if (data.error) {
  console.error('❌ Function error:', data.error);
  Deno.exit(1);
}

console.log(`\n✅ Function returned ${data.length} bars\n`);

if (data.length > 0) {
  const newest = data[data.length - 1];
  const oldest = data[0];
  
  console.log(`Oldest bar: ${oldest.ts}`);
  console.log(`Newest bar: ${newest.ts}`);
  
  const newestDate = new Date(newest.ts);
  const now = new Date();
  const ageDays = (now.getTime() - newestDate.getTime()) / (1000 * 60 * 60 * 24);
  
  console.log(`\nAge of newest bar: ${ageDays.toFixed(1)} days`);
  
  if (ageDays > 180) {
    console.log('\n❌ DATA IS STALE - Fix NOT applied');
    console.log('   The database function is still using the old WHERE clause');
  } else if (ageDays > 7) {
    console.log('\n⚠️  DATA IS OLD - Fix may be applied but data ingestion issue');
  } else {
    console.log('\n✅ DATA IS FRESH - Fix appears to be working');
  }
}
