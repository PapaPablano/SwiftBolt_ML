// Diagnostic script to check AAPL data in database
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://cygflaemtmwiwaviclks.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTIxMTMzNiwiZXhwIjoyMDgwNzg3MzM2fQ.YajeNHOQ63uBDDZhJ2YYHK7L-BKmnZAviDqrlk2TQxU';
const supabase = createClient(supabaseUrl, supabaseKey);

async function diagnose() {
  try {
    // 1. Get AAPL symbol ID
    console.log('=== AAPL SYMBOL INFO ===');
    const { data: symbolData, error: symbolError } = await supabase
      .from('symbols')
      .select('id, ticker, asset_type')
      .eq('ticker', 'AAPL')
      .single();

    if (symbolError) {
      console.error('Error fetching symbol:', symbolError);
      return;
    }

    console.log('AAPL Symbol:', symbolData);
    const symbolId = symbolData.id;

    // 2. Check data in ohlc_bars_v2
    console.log('\n=== AAPL DATA IN OHLC_BARS_V2 (d1) ===');
    const { data: v2Data, error: v2Error } = await supabase
      .from('ohlc_bars_v2')
      .select('provider, is_forecast, is_intraday, ts')
      .eq('symbol_id', symbolId)
      .eq('timeframe', 'd1')
      .order('ts', { ascending: true });

    if (v2Error) {
      console.error('Error fetching v2 data:', v2Error);
    } else {
      console.log(`Total bars in ohlc_bars_v2: ${v2Data.length}`);

      // Group by provider
      const byProvider = {};
      v2Data.forEach(row => {
        const key = `${row.provider}_forecast:${row.is_forecast}`;
        if (!byProvider[key]) {
          byProvider[key] = { count: 0, first: null, last: null };
        }
        byProvider[key].count++;
        if (!byProvider[key].first) byProvider[key].first = row.ts;
        byProvider[key].last = row.ts;
      });

      console.log('\nBreakdown by provider:');
      Object.entries(byProvider).forEach(([key, stats]) => {
        console.log(`  ${key}: ${stats.count} bars, ${stats.first} to ${stats.last}`);
      });

      // Check for gaps in 2024-2025
      const bars2024_2025 = v2Data.filter(row => {
        const date = new Date(row.ts);
        return date >= new Date('2024-01-01') && date <= new Date('2025-12-31');
      });

      console.log(`\nBars in 2024-2025 range: ${bars2024_2025.length}`);
      if (bars2024_2025.length > 0) {
        console.log(`First: ${bars2024_2025[0].ts} (${bars2024_2025[0].provider})`);
        console.log(`Last: ${bars2024_2025[bars2024_2025.length - 1].ts} (${bars2024_2025[bars2024_2025.length - 1].provider})`);
      }
    }

    // 3. Check data in old ohlc_bars table
    console.log('\n=== AAPL DATA IN OLD OHLC_BARS (d1) ===');
    const { data: oldData, error: oldError } = await supabase
      .from('ohlc_bars')
      .select('ts, provider')
      .eq('symbol_id', symbolId)
      .eq('timeframe', 'd1')
      .order('ts', { ascending: true });

    if (oldError) {
      console.error('Error fetching old data:', oldError);
    } else {
      console.log(`Total bars in old ohlc_bars: ${oldData.length}`);
      if (oldData.length > 0) {
        console.log(`First: ${oldData[0].ts}`);
        console.log(`Last: ${oldData[oldData.length - 1].ts}`);
      }
    }

    // 4. Sample a few bars from 2024 to see exact data
    console.log('\n=== SAMPLE BARS FROM JAN 2024 ===');
    const { data: sampleData, error: sampleError } = await supabase
      .from('ohlc_bars_v2')
      .select('ts, provider, open, close, is_forecast')
      .eq('symbol_id', symbolId)
      .eq('timeframe', 'd1')
      .gte('ts', '2024-01-01T00:00:00Z')
      .lte('ts', '2024-01-31T00:00:00Z')
      .order('ts', { ascending: true })
      .limit(10);

    if (sampleError) {
      console.error('Error fetching sample:', sampleError);
    } else {
      sampleData.forEach(bar => {
        console.log(`  ${bar.ts} | ${bar.provider} | O:${bar.open} C:${bar.close} | forecast:${bar.is_forecast}`);
      });
    }

  } catch (err) {
    console.error('Unexpected error:', err);
  }
}

diagnose();
