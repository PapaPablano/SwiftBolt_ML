/**
 * Chart Data V2 Edge Function
 * Fetches OHLC data from ohlc_bars_v2 with proper layer separation
 * 
 * Returns three distinct layers (Alpaca-only strategy):
 * - Historical: Alpaca data (dates < today)
 * - Intraday: Alpaca data (today only)
 * - Forecast: ML predictions (dates > today)
 * 
 * Legacy providers (Polygon, Tradier) available as read-only fallback
 * 
 * Enhanced with ML enrichment:
 * - Intraday forecasts (15m, 1h horizons)
 * - SuperTrend AI indicators
 * - Support/Resistance levels
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

interface ChartRequest {
  symbol: string;
  timeframe?: string;
  days?: number;
  includeForecast?: boolean;
  forecastDays?: number;
  includeMLData?: boolean;
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
    const { symbol, timeframe = 'd1', days = 60, includeForecast = true, forecastDays = 10, includeMLData = true } = 
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
    // Use DATE comparison instead of is_intraday flag (flag may be incorrect for historical data)
    const historical: ChartBar[] = [];
    const intraday: ChartBar[] = [];
    const forecast: ChartBar[] = [];

    const todayStr = new Date().toISOString().split('T')[0];

    for (const bar of (chartData || [])) {
      const barDate = bar.ts.split('T')[0];

      if (bar.is_forecast) {
        forecast.push(bar);
      } else if (barDate === todayStr) {
        // Today's data goes to intraday
        intraday.push(bar);
      } else if (barDate < todayStr) {
        // Past data goes to historical
        historical.push(bar);
      } else {
        // Future non-forecast data (shouldn't happen, but handle gracefully)
        forecast.push(bar);
      }
    }

    // Fetch ML enrichment data if requested
    let mlSummary = null;
    let superTrendAI = null;
    let indicators = null;

    if (includeMLData) {
      try {
        // Fetch intraday forecast if timeframe is intraday
        const isIntraday = ['m15', 'h1', 'h4'].includes(timeframe);
        
        if (isIntraday) {
          // Map timeframe to horizon
          const horizonMap: Record<string, string> = {
            'm15': '15m',
            'h1': '1h',
            'h4': '1h', // Use 1h forecast for 4h charts
          };
          const horizon = horizonMap[timeframe] || '1h';

          // Fetch latest intraday forecast
          const { data: intradayForecast } = await supabase
            .from('ml_forecasts_intraday')
            .select('*')
            .eq('symbol_id', symbolId)
            .eq('horizon', horizon)
            .gte('expires_at', new Date().toISOString())
            .order('created_at', { ascending: false })
            .limit(1)
            .single();

          if (intradayForecast) {
            mlSummary = {
              overallLabel: intradayForecast.overall_label,
              confidence: intradayForecast.confidence,
              horizons: [{
                horizon: horizon,
                points: [{
                  ts: Math.floor(new Date(intradayForecast.expires_at).getTime() / 1000),
                  value: intradayForecast.target_price,
                  lower: intradayForecast.target_price * 0.98,
                  upper: intradayForecast.target_price * 1.02,
                }]
              }],
              srLevels: null,
              srDensity: null,
            };

            indicators = {
              supertrendFactor: null,
              supertrendPerformance: null,
              supertrendSignal: intradayForecast.supertrend_direction === 'BULLISH' ? 1 : 
                                 intradayForecast.supertrend_direction === 'BEARISH' ? -1 : 0,
              trendLabel: intradayForecast.overall_label,
              trendConfidence: Math.round(intradayForecast.confidence * 10),
              stopLevel: null,
              trendDurationBars: null,
              rsi: null,
              adx: null,
              macdHistogram: null,
              kdjJ: null,
            };
          }
        } else {
          // Fetch daily forecast for daily/weekly timeframes
          const { data: dailyForecast } = await supabase
            .from('ml_forecasts')
            .select('*')
            .eq('symbol_id', symbolId)
            .order('created_at', { ascending: false })
            .limit(1)
            .single();

          if (dailyForecast && dailyForecast.points) {
            mlSummary = {
              overallLabel: dailyForecast.overall_label,
              confidence: dailyForecast.confidence,
              horizons: [{
                horizon: dailyForecast.horizon,
                points: dailyForecast.points,
              }],
              srLevels: dailyForecast.sr_levels || null,
              srDensity: dailyForecast.sr_density || null,
            };

            indicators = {
              supertrendFactor: dailyForecast.supertrend_factor,
              supertrendPerformance: dailyForecast.supertrend_performance,
              supertrendSignal: dailyForecast.supertrend_signal,
              trendLabel: dailyForecast.trend_label,
              trendConfidence: dailyForecast.trend_confidence,
              stopLevel: dailyForecast.stop_level,
              trendDurationBars: dailyForecast.trend_duration_bars,
              rsi: dailyForecast.rsi,
              adx: dailyForecast.adx,
              macdHistogram: dailyForecast.macd_histogram,
              kdjJ: dailyForecast.kdj_j,
            };
          }
        }
      } catch (mlError) {
        console.error('[chart-data-v2] ML enrichment error:', mlError);
        // Continue without ML data
      }
    }

    // Determine actual providers from most recent bar
    const historicalProvider = historical.length > 0 
      ? historical[historical.length - 1].provider
      : 'none';
    
    const intradayProvider = intraday.length > 0
      ? intraday[intraday.length - 1].provider
      : 'none';

    const response = {
      symbol: symbol.toUpperCase(),
      timeframe,
      layers: {
        historical: {
          count: historical.length,
          provider: historicalProvider,
          data: historical,
        },
        intraday: {
          count: intraday.length,
          provider: intradayProvider,
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
      mlSummary,
      indicators,
      superTrendAI: superTrendAI,
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
