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
import type { PostgrestError } from 'https://esm.sh/@supabase/supabase-js@2';

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

const MAX_BARS_BY_TIMEFRAME: Record<string, number> = {
  m15: 2000,
  h1: 1500,
  h4: 1000,
  d1: 2000,
  w1: 2000,
};
const DEFAULT_MAX_BARS = 1000;

function isValidChartBarArray(data: unknown): data is ChartBar[] {
  if (!Array.isArray(data)) return false;
  if (data.length === 0) return true;

  const isNumberOrNull = (v: unknown) => v === null || typeof v === 'number';

  return (data as unknown[]).every((item) => {
    if (item === null || typeof item !== 'object') return false;
    const bar = item as Partial<ChartBar>;
    return (
      typeof bar.ts === 'string' &&
      typeof bar.provider === 'string' &&
      typeof bar.data_status === 'string' &&
      typeof bar.is_intraday === 'boolean' &&
      typeof bar.is_forecast === 'boolean' &&
      isNumberOrNull(bar.open) &&
      isNumberOrNull(bar.high) &&
      isNumberOrNull(bar.low) &&
      isNumberOrNull(bar.close) &&
      isNumberOrNull(bar.volume)
    );
  });
}

function buildChartError(message: string): PostgrestError {
  return {
    message,
    details: null,
    hint: null,
    code: 'NO_CHART_DATA',
  };
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
    
    // Use dynamic query first to guarantee newest bars (orders DESC, no date filters)
    const maxBars = MAX_BARS_BY_TIMEFRAME[timeframe] ?? DEFAULT_MAX_BARS;

    let chartData: ChartBar[] | null = null;
    let chartError: PostgrestError | null = null;
    let dataSource = 'dynamic';

    const { data: dynamicData, error: dynamicError } = await supabase
      .rpc('get_chart_data_v2_dynamic', {
        p_symbol_id: symbolId,
        p_timeframe: timeframe,
        p_max_bars: maxBars,
        p_include_forecast: includeForecast,
      });

    if (!dynamicError && isValidChartBarArray(dynamicData)) {
      chartData = dynamicData as ChartBar[];
    } else {
      console.warn('[chart-data-v2] Dynamic RPC failed, falling back to legacy query', dynamicError);
      dataSource = 'legacy';

      // Legacy RPC always includes forecasts (p_include_forecast=true in SQL); we filter manually when includeForecast is false
      const { data: legacyData, error: legacyError } = await supabase
        .rpc('get_chart_data_v2', {
          p_symbol_id: symbolId,
          p_timeframe: timeframe,
        });

      if (!legacyError && legacyData) {
        if (includeForecast) {
          chartData = legacyData.slice(-maxBars); // take most recent maxBars entries
        } else {
          chartData = legacyData
            .filter((bar) => !bar.is_forecast)
            .slice(-maxBars); // take most recent maxBars entries
        }
      }
      chartError = legacyError;
    }

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

    // Guard against empty/invalid results when no explicit error was returned
    if (!chartError && chartData === null) {
      const fallbackError = buildChartError('No chart data returned from either dynamic or legacy RPC');
      console.error('[chart-data-v2] No data from dynamic or legacy RPC');
      return new Response(
        JSON.stringify({ 
          error: 'Failed to fetch chart data', 
          details: fallbackError.message,
          hint: fallbackError.hint,
          code: fallbackError.code
        }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }
    
    console.log(`[chart-data-v2] Success: received ${chartData?.length || 0} bars (source=${dataSource})`);
    
    // DEBUG: Log the newest and oldest bars to diagnose staleness
    if (chartData && chartData.length > 0) {
      const oldest = chartData[0];
      const newest = chartData[chartData.length - 1];
      console.log(`[chart-data-v2] DEBUG: Oldest bar: ${oldest.ts} (${oldest.provider})`);
      console.log(`[chart-data-v2] DEBUG: Newest bar: ${newest.ts} (${newest.provider})`);
      
      const newestDate = new Date(newest.ts);
      const now = new Date();
      const ageHours = (now.getTime() - newestDate.getTime()) / (1000 * 60 * 60);
      console.log(`[chart-data-v2] DEBUG: Newest bar age: ${ageHours.toFixed(1)} hours`);
      
      if (ageHours > 24) {
        console.warn(`[chart-data-v2] ⚠️ WARNING: Newest bar is ${(ageHours / 24).toFixed(1)} days old!`);
      }
    }

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

    // Calculate data quality metrics
    const newestBar = chartData && chartData.length > 0 ? chartData[chartData.length - 1] : null;
    const oldestBar = chartData && chartData.length > 0 ? chartData[0] : null;
    
    const dataQuality = {
      dataAgeHours: newestBar ? 
        Math.round((new Date().getTime() - new Date(newestBar.ts).getTime()) / (1000 * 60 * 60)) : null,
      isStale: newestBar ? 
        (new Date().getTime() - new Date(newestBar.ts).getTime()) > (24 * 60 * 60 * 1000) : true,
      hasRecentData: newestBar ? 
        (new Date().getTime() - new Date(newestBar.ts).getTime()) < (4 * 60 * 60 * 1000) : false,
      historicalDepthDays: (oldestBar && newestBar) ?
        Math.round((new Date(newestBar.ts).getTime() - new Date(oldestBar.ts).getTime()) / (1000 * 60 * 60 * 24)) : 0,
      sufficientForML: (chartData?.length || 0) >= 250, // ~1 year of trading days
      barCount: chartData?.length || 0,
    };

    const response = {
      symbol: symbol.toUpperCase(),
      timeframe,
      layers: {
        historical: {
          count: historical.length,
          provider: historicalProvider,
          data: historical,
          oldestBar: historical.length > 0 ? historical[0].ts : null,
          newestBar: historical.length > 0 ? historical[historical.length - 1].ts : null,
        },
        intraday: {
          count: intraday.length,
          provider: intradayProvider,
          data: intraday,
          oldestBar: intraday.length > 0 ? intraday[0].ts : null,
          newestBar: intraday.length > 0 ? intraday[intraday.length - 1].ts : null,
        },
        forecast: {
          count: forecast.length,
          provider: 'ml_forecast',
          data: forecast,
          oldestBar: forecast.length > 0 ? forecast[0].ts : null,
          newestBar: forecast.length > 0 ? forecast[forecast.length - 1].ts : null,
        },
      },
      metadata: {
        total_bars: chartData?.length || 0,
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
        requested_days: days,
        forecast_days: forecastDays,
      },
      dataQuality,
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
