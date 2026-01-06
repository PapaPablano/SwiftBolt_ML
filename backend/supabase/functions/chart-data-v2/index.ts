/**
 * Chart Data V2 Edge Function
 * Fetches OHLC data from ohlc_bars_v2 with proper layer separation
 * 
 * Returns three distinct layers:
 * - Historical: Polygon data (dates < today)
 * - Intraday: Tradier data (today only)
 * - Forecast: ML predictions (dates > today)
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

interface ChartRequest {
  symbol: string;
  timeframe?: string;
  days?: number;
  includeForecast?: boolean;
  forecastDays?: number;
}

interface ChartBar {
  ts: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  provider: string;
  is_intraday: boolean;
  is_forecast: boolean;
  data_status: string;
  confidence_score?: number;
  upper_band?: number;
  lower_band?: number;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const { symbol, timeframe = 'd1', days = 60, includeForecast = true, forecastDays = 10 } = 
      await req.json() as ChartRequest;

    if (!symbol) {
      return new Response(
        JSON.stringify({ error: 'Symbol is required' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Get symbol_id
    const { data: symbolData, error: symbolError } = await supabase
      .from('symbols')
      .select('id')
      .eq('ticker', symbol.toUpperCase())
      .single();

    if (symbolError || !symbolData) {
      return new Response(
        JSON.stringify({ error: `Symbol ${symbol} not found` }),
        { status: 404, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const symbolId = symbolData.id;

    // Calculate date range
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const startDate = new Date(today);
    startDate.setDate(startDate.getDate() - days);
    
    const endDate = new Date(today);
    if (includeForecast) {
      endDate.setDate(endDate.getDate() + forecastDays);
    }

    // Fetch data using the v2 function
    console.log(`[chart-data-v2] Fetching: symbol_id=${symbolId}, timeframe=${timeframe}, start=${startDate.toISOString()}, end=${endDate.toISOString()}`);
    
    const { data: chartData, error: chartError } = await supabase
      .rpc('get_chart_data_v2', {
        p_symbol_id: symbolId,
        p_timeframe: timeframe,
        p_start_date: startDate.toISOString(),
        p_end_date: endDate.toISOString(),
      });

    if (chartError) {
      console.error('[chart-data-v2] RPC error:', chartError);
      console.error('[chart-data-v2] Error details:', JSON.stringify(chartError, null, 2));
      return new Response(
        JSON.stringify({ 
          error: 'Failed to fetch chart data', 
          details: chartError.message,
          hint: chartError.hint || null,
          code: chartError.code || null
        }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }
    
    console.log(`[chart-data-v2] Success: received ${chartData?.length || 0} bars`);

    // Separate data into layers for client-side rendering
    const historical: ChartBar[] = [];
    const intraday: ChartBar[] = [];
    const forecast: ChartBar[] = [];

    for (const bar of (chartData || [])) {
      if (bar.is_forecast) {
        forecast.push(bar);
      } else if (bar.is_intraday) {
        intraday.push(bar);
      } else {
        historical.push(bar);
      }
    }

    const response = {
      symbol: symbol.toUpperCase(),
      timeframe,
      layers: {
        historical: {
          count: historical.length,
          provider: 'polygon',
          data: historical,
        },
        intraday: {
          count: intraday.length,
          provider: 'tradier',
          data: intraday,
        },
        forecast: {
          count: forecast.length,
          provider: 'ml_forecast',
          data: forecast,
        },
      },
      metadata: {
        total_bars: chartData?.length || 0,
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
        requested_days: days,
        forecast_days: forecastDays,
      },
    };

    return new Response(
      JSON.stringify(response),
      { status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Chart data error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error', details: error.message }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};
