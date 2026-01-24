#!/usr/bin/env -S deno run --allow-net --allow-env

/**
 * Test script to diagnose why charts show old data
 * Tests the actual database query that the chart-data-v2 function uses
 */

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const supabase = createClient(supabaseUrl, supabaseKey);

async function testChartQuery(symbol: string, timeframe: string) {
  console.log(`\n${'='.repeat(80)}`);
  console.log(`Testing ${symbol} - ${timeframe}`);
  console.log('='.repeat(80));

  // Get symbol_id
  const { data: symbolData, error: symbolError } = await supabase
    .from('symbols')
    .select('id')
    .eq('ticker', symbol)
    .single();

  if (symbolError || !symbolData) {
    console.error(`❌ Symbol ${symbol} not found`);
    return;
  }

  const symbolId = symbolData.id;
  console.log(`✅ Symbol ID: ${symbolId}`);

  // 1. Check what data exists in database
  console.log('\n1️⃣ Checking raw database data...');
  const { data: rawData, error: rawError } = await supabase
    .from('ohlc_bars_v2')
    .select('ts, close, provider, is_intraday, is_forecast')
    .eq('symbol_id', symbolId)
    .eq('timeframe', timeframe)
    .eq('is_forecast', false)
    .order('ts', { ascending: false })
    .limit(10);

  if (rawError) {
    console.error('❌ Error fetching raw data:', rawError);
  } else {
    console.log(`   Total bars in last 10: ${rawData?.length || 0}`);
    if (rawData && rawData.length > 0) {
      console.log(`   Newest bar: ${rawData[0].ts} (${rawData[0].provider})`);
      console.log(`   Close: $${rawData[0].close}`);
      console.log(`   Is intraday: ${rawData[0].is_intraday}`);
    }
  }

  // 2. Test get_chart_data_v2_dynamic function
  console.log('\n2️⃣ Testing get_chart_data_v2_dynamic function...');
  const { data: functionData, error: functionError } = await supabase
    .rpc('get_chart_data_v2_dynamic', {
      p_symbol_id: symbolId,
      p_timeframe: timeframe,
      p_max_bars: 1000,
      p_include_forecast: false
    });

  if (functionError) {
    console.error('❌ Function error:', functionError);
  } else {
    console.log(`   Bars returned: ${functionData?.length || 0}`);
    if (functionData && functionData.length > 0) {
      // Data is returned in ASC order (oldest to newest)
      const newest = functionData[functionData.length - 1];
      const oldest = functionData[0];
      console.log(`   Oldest bar: ${oldest.ts}`);
      console.log(`   Newest bar: ${newest.ts} (${newest.provider})`);
      console.log(`   Close: $${newest.close}`);
      
      // Check age of newest bar
      const newestDate = new Date(newest.ts);
      const now = new Date();
      const ageHours = (now.getTime() - newestDate.getTime()) / (1000 * 60 * 60);
      const ageDays = ageHours / 24;
      
      if (ageDays > 7) {
        console.log(`   ⚠️ STALE: Newest bar is ${ageDays.toFixed(1)} days old!`);
      } else if (ageDays > 1) {
        console.log(`   ⚠️ OLD: Newest bar is ${ageDays.toFixed(1)} days old`);
      } else {
        console.log(`   ✅ FRESH: Newest bar is ${ageHours.toFixed(1)} hours old`);
      }
    }
  }

  // 3. Test get_chart_data_v2 wrapper function
  console.log('\n3️⃣ Testing get_chart_data_v2 wrapper function...');
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - 60);
  const endDate = new Date();

  const { data: wrapperData, error: wrapperError } = await supabase
    .rpc('get_chart_data_v2', {
      p_symbol_id: symbolId,
      p_timeframe: timeframe,
      p_start_date: startDate.toISOString(),
      p_end_date: endDate.toISOString()
    });

  if (wrapperError) {
    console.error('❌ Wrapper function error:', wrapperError);
  } else {
    console.log(`   Bars returned: ${wrapperData?.length || 0}`);
    if (wrapperData && wrapperData.length > 0) {
      const newest = wrapperData[wrapperData.length - 1];
      console.log(`   Newest bar: ${newest.ts} (${newest.provider})`);
      console.log(`   Close: $${newest.close}`);
    }
  }

  // 4. Check WHERE clause filtering
  console.log('\n4️⃣ Checking WHERE clause filtering...');
  const today = new Date().toISOString().split('T')[0];
  
  const { data: todayData } = await supabase
    .from('ohlc_bars_v2')
    .select('ts, close, provider, is_intraday')
    .eq('symbol_id', symbolId)
    .eq('timeframe', timeframe)
    .eq('is_forecast', false)
    .gte('ts', today)
    .order('ts', { ascending: false });

  console.log(`   Bars with today's date: ${todayData?.length || 0}`);
  if (todayData && todayData.length > 0) {
    console.log(`   Latest today: ${todayData[0].ts} (${todayData[0].provider}, intraday=${todayData[0].is_intraday})`);
  }

  const { data: historicalData } = await supabase
    .from('ohlc_bars_v2')
    .select('ts, close, provider')
    .eq('symbol_id', symbolId)
    .eq('timeframe', timeframe)
    .eq('is_forecast', false)
    .lt('ts', today)
    .order('ts', { ascending: false })
    .limit(1);

  console.log(`   Latest historical (before today): ${historicalData?.[0]?.ts || 'none'}`);
}

// Test both timeframes that showed issues in screenshots
console.log('🔍 Diagnosing Chart Data Issue\n');

await testChartQuery('AAPL', 'h1');
await testChartQuery('AAPL', 'd1');

console.log('\n' + '='.repeat(80));
console.log('✅ Diagnostic complete');
console.log('='.repeat(80));
