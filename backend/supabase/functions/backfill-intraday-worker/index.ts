/**
 * Backfill Intraday Worker
 * Processes backfill_chunks to populate intraday_bars with historical data
 * 
 * Features:
 * - Claims chunks using SKIP LOCKED for parallel processing
 * - Fetches historical intraday data from Polygon
 * - Writes to intraday_bars table (1m, 5m, 15m timeframes)
 * - Updates chunk status and progress
 */

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

interface BackfillChunk {
  id: string;
  job_id: string;
  symbol: string;
  symbol_id: string;
  timeframe: string;
  day: string;
  status: string;
}

interface PolygonBar {
  t: number; // timestamp in ms
  o: number; // open
  h: number; // high
  l: number; // low
  c: number; // close
  v: number; // volume
}

serve(async (req: Request): Promise<Response> => {
  const startTime = Date.now();
  
  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const polygonApiKey = Deno.env.get('POLYGON_API_KEY');

    if (!polygonApiKey) {
      console.error('POLYGON_API_KEY not configured');
      return new Response(
        JSON.stringify({ error: 'Polygon API key not configured' }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const supabase = createClient(supabaseUrl, supabaseKey);

    // Claim a pending chunk using SKIP LOCKED for parallel processing
    const { data: chunks, error: claimError } = await supabase
      .rpc('claim_backfill_chunk', { p_limit: 1 });

    if (claimError) {
      console.error('Error claiming chunk:', claimError);
      return new Response(
        JSON.stringify({ error: 'Failed to claim chunk', details: claimError }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }

    if (!chunks || chunks.length === 0) {
      console.log('No pending chunks available');
      return new Response(
        JSON.stringify({ message: 'No pending chunks', processed: 0 }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const chunk: BackfillChunk = chunks[0];
    console.log(`Processing chunk: ${chunk.symbol} ${chunk.timeframe} ${chunk.day}`);

    // Fetch data from Polygon
    const bars = await fetchPolygonIntraday(
      chunk.symbol,
      chunk.timeframe,
      chunk.day,
      polygonApiKey
    );

    if (bars.length === 0) {
      console.warn(`No data returned for ${chunk.symbol} on ${chunk.day}`);
      
      // Mark as completed even if no data (could be holiday/weekend)
      await supabase
        .from('backfill_chunks')
        .update({
          status: 'completed',
          bars_collected: 0,
          completed_at: new Date().toISOString(),
        })
        .eq('id', chunk.id);

      return new Response(
        JSON.stringify({ 
          message: 'No data available for chunk',
          chunk: chunk,
          bars: 0,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Convert timeframe format (h1 -> 1h, m15 -> 15m, etc.)
    const timeframeMap: Record<string, string> = {
      'h1': '1h',
      'h4': '4h',
      'm1': '1m',
      'm5': '5m',
      'm15': '15m',
      'm30': '30m',
    };
    const dbTimeframe = timeframeMap[chunk.timeframe] || chunk.timeframe;

    // Prepare bars for insertion
    const barsToInsert = bars.map(bar => ({
      symbol_id: chunk.symbol_id,
      timeframe: dbTimeframe,
      ts: new Date(bar.t).toISOString(),
      open: bar.o,
      high: bar.h,
      low: bar.l,
      close: bar.c,
      volume: bar.v,
      provider: 'polygon',
      is_forecast: false,
      data_status: 'confirmed',
    }));

    // Insert bars into ohlc_bars_v2
    const { error: insertError } = await supabase
      .from('ohlc_bars_v2')
      .upsert(barsToInsert, {
        onConflict: 'symbol_id,timeframe,ts,provider,is_forecast',
        ignoreDuplicates: false,
      });

    if (insertError) {
      console.error('Error inserting bars:', insertError);
      
      // Mark chunk as error
      await supabase
        .from('backfill_chunks')
        .update({
          status: 'error',
          error_message: insertError.message,
          updated_at: new Date().toISOString(),
        })
        .eq('id', chunk.id);

      return new Response(
        JSON.stringify({ 
          error: 'Failed to insert bars',
          details: insertError,
          chunk: chunk,
        }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Mark chunk as completed
    await supabase
      .from('backfill_chunks')
      .update({
        status: 'completed',
        bars_collected: bars.length,
        completed_at: new Date().toISOString(),
      })
      .eq('id', chunk.id);

    // Update parent job progress
    await updateJobProgress(supabase, chunk.job_id);

    const duration = Date.now() - startTime;
    console.log(`✅ Completed chunk in ${duration}ms: ${bars.length} bars for ${chunk.symbol} ${chunk.day}`);

    return new Response(
      JSON.stringify({
        success: true,
        chunk: chunk,
        bars_inserted: bars.length,
        duration_ms: duration,
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Worker error:', error);
    return new Response(
      JSON.stringify({ 
        error: 'Worker failed',
        message: error instanceof Error ? error.message : String(error),
      }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
});

/**
 * Fetch intraday bars from Polygon for a specific day
 */
async function fetchPolygonIntraday(
  symbol: string,
  timeframe: string,
  day: string,
  apiKey: string
): Promise<PolygonBar[]> {
  // Convert timeframe to Polygon format
  const timeframeMap: Record<string, { multiplier: number; timespan: string }> = {
    'm1': { multiplier: 1, timespan: 'minute' },
    'm5': { multiplier: 5, timespan: 'minute' },
    'm15': { multiplier: 15, timespan: 'minute' },
    'm30': { multiplier: 30, timespan: 'minute' },
    'h1': { multiplier: 1, timespan: 'hour' },
    'h4': { multiplier: 4, timespan: 'hour' },
  };

  const tf = timeframeMap[timeframe];
  if (!tf) {
    console.error(`Unsupported timeframe: ${timeframe}`);
    return [];
  }

  // Polygon expects dates in YYYY-MM-DD format
  const fromDate = day;
  const toDate = day;

  const url = `https://api.polygon.io/v2/aggs/ticker/${symbol}/range/${tf.multiplier}/${tf.timespan}/${fromDate}/${toDate}?adjusted=true&sort=asc&limit=50000&apiKey=${apiKey}`;

  try {
    const response = await fetch(url);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Polygon API error (${response.status}):`, errorText);
      
      // Rate limit handling
      if (response.status === 429) {
        console.warn('Rate limited by Polygon, waiting 60s...');
        await new Promise(resolve => setTimeout(resolve, 60000));
        return fetchPolygonIntraday(symbol, timeframe, day, apiKey);
      }
      
      return [];
    }

    const data = await response.json();
    
    if (data.status !== 'OK' || !data.results) {
      console.warn(`No results from Polygon for ${symbol} on ${day}`);
      return [];
    }

    return data.results as PolygonBar[];
  } catch (error) {
    console.error(`Error fetching from Polygon:`, error);
    return [];
  }
}

/**
 * Update parent job progress
 */
async function updateJobProgress(supabase: any, jobId: string): Promise<void> {
  try {
    // Count completed chunks
    const { data: stats } = await supabase
      .from('backfill_chunks')
      .select('status, bars_collected')
      .eq('job_id', jobId);

    if (!stats) return;

    const total = stats.length;
    const completed = stats.filter((s: any) => s.status === 'completed').length;
    const totalBars = stats.reduce((sum: number, s: any) => sum + (s.bars_collected || 0), 0);

    const allCompleted = completed === total;
    const status = allCompleted ? 'completed' : 'in_progress';

    await supabase
      .from('backfill_jobs')
      .update({
        status: status,
        bars_collected: totalBars,
        updated_at: new Date().toISOString(),
        ...(allCompleted && { completed_at: new Date().toISOString() }),
      })
      .eq('id', jobId);

    console.log(`Job ${jobId} progress: ${completed}/${total} chunks, ${totalBars} bars`);
  } catch (error) {
    console.error('Error updating job progress:', error);
  }
}
