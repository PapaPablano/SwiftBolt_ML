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

declare const Deno: {
  env: {
    get(key: string): string | undefined;
  };
};

interface ChartRequest {
  symbol: string;
  timeframe?: string;
  days?: number;
  includeForecast?: boolean;
  forecastDays?: number;
  forecastSteps?: number;
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
  data_status: string | null;
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
const POSTGREST_MAX_ROWS = 1000;

function alpacaTimeframe(timeframe: string): string | null {
  switch (timeframe) {
    case 'm15':
      return '15Min';
    case 'h1':
      return '1Hour';
    case 'h4':
      return '4Hour';
    default:
      return null;
  }
}

function intradayMaxAgeSeconds(timeframe: string): number {
  switch (timeframe) {
    case 'm15':
      return 25 * 60;
    case 'h1':
      return 2 * 60 * 60;
    case 'h4':
      return 5 * 60 * 60;
    default:
      return 60 * 60;
  }
}

type AlpacaBarsResponse = {
  bars?: Record<string, Array<{ t: string; o: number; h: number; l: number; c: number; v: number }>>;
  next_page_token?: string;
};

async function fetchAlpacaBars(params: {
  symbol: string;
  timeframe: string;
  startIso: string;
  endIso: string;
  apiKey: string;
  apiSecret: string;
}): Promise<Array<{ t: string; o: number; h: number; l: number; c: number; v: number }>> {
  const tf = alpacaTimeframe(params.timeframe);
  if (!tf) {
    return [];
  }

  const url = `https://data.alpaca.markets/v2/stocks/bars?` +
    `symbols=${encodeURIComponent(params.symbol)}&` +
    `timeframe=${encodeURIComponent(tf)}&` +
    `start=${encodeURIComponent(params.startIso)}&` +
    `end=${encodeURIComponent(params.endIso)}&` +
    `limit=10000&` +
    `adjustment=raw&` +
    `feed=iex&` +
    `sort=asc`;

  const res = await fetch(url, {
    headers: {
      'APCA-API-KEY-ID': params.apiKey,
      'APCA-API-SECRET-KEY': params.apiSecret,
      Accept: 'application/json',
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Alpaca bars error: ${res.status} ${body}`);
  }

  const data = (await res.json()) as AlpacaBarsResponse;
  const bars = data.bars?.[params.symbol.toUpperCase()] ?? [];
  return Array.isArray(bars) ? bars : [];
}

function timeframeToIntervalSeconds(timeframe: string): number | null {
  switch (timeframe) {
    case 'm15':
      return 15 * 60;
    case 'h1':
      return 60 * 60;
    case 'h4':
      return 4 * 60 * 60;
    case 'd1':
      return 24 * 60 * 60;
    case 'w1':
      return 7 * 24 * 60 * 60;
    default:
      return null;
  }
}

function clampNumber(v: unknown, fallback: number): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : fallback;
}

function buildIntradayForecastPoints(params: {
  baseTsSec: number;
  intervalSec: number;
  steps: number;
  currentPrice: number;
  targetPrice: number;
  confidence: number;
}): Array<{ ts: number; value: number; lower: number; upper: number }> {
  const safeSteps = Math.max(1, Math.min(500, Math.floor(params.steps)));
  const conf = Math.max(0, Math.min(1, params.confidence));
  const bandPct = Math.max(0.005, Math.min(0.04, 0.03 - conf * 0.02));

  const points: Array<{ ts: number; value: number; lower: number; upper: number }> = [];

  for (let i = 1; i <= safeSteps; i += 1) {
    const t = i / safeSteps;
    const value = params.currentPrice + (params.targetPrice - params.currentPrice) * t;
    const lower = value * (1 - bandPct);
    const upper = value * (1 + bandPct);
    points.push({
      ts: params.baseTsSec + params.intervalSec * i,
      value,
      lower,
      upper,
    });
  }
  return points;
}

const DAILY_FORECAST_MAX_POINTS = 6;
const INTRADAY_FORECAST_MAX_POINTS = 6;

const INTRADAY_FORECAST_EXPIRY_GRACE_SECONDS = 2 * 60 * 60;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function toUnixSeconds(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.floor(value);
  }

  if (typeof value === 'string') {
    const parsed = new Date(value);
    const time = parsed.getTime();
    if (!Number.isNaN(time)) {
      return Math.floor(time / 1000);
    }
  }

  return Math.floor(Date.now() / 1000);
}

function normalizeForecastPoint(point: Record<string, unknown>): { ts: number; value: number; lower: number; upper: number } {
  return {
    ...point,
    ts: toUnixSeconds(point['ts'] ?? point['time']),
    value: Number(point['value'] ?? point['mid'] ?? point['midpoint'] ?? 0),
    lower: Number(point['lower'] ?? point['min'] ?? point['lower_bound'] ?? point['value'] ?? 0),
    upper: Number(point['upper'] ?? point['max'] ?? point['upper_bound'] ?? point['value'] ?? 0),
  };
}

function normalizeForecastPoints(points: unknown): Array<{ ts: number; value: number; lower: number; upper: number }> {
  if (!Array.isArray(points)) {
    return [];
  }
  return points.map((point) => normalizeForecastPoint(isRecord(point) ? point : {}));
}

function sampleForecastPoints<T extends { ts: number }>(points: T[], maxPoints: number): T[] {
  if (!Array.isArray(points) || points.length === 0) {
    return [];
  }

  if (!Number.isFinite(maxPoints) || maxPoints <= 0) {
    return points.map((point) => ({ ...point }));
  }

  if (points.length <= maxPoints || maxPoints < 2) {
    return points.map((point) => ({ ...point }));
  }

  const lastIndex = points.length - 1;
  const indices = new Set<number>();

  for (let i = 0; i < maxPoints; i += 1) {
    const ratio = maxPoints === 1 ? 0 : i / (maxPoints - 1);
    const idx = Math.min(Math.round(ratio * lastIndex), lastIndex);
    indices.add(idx);
  }

  // Ensure we always include first and last points
  indices.add(0);
  indices.add(lastIndex);

  return Array.from(indices)
    .sort((a, b) => a - b)
    .map((idx) => ({ ...points[idx] }));
}

function isValidChartBarArray(data: unknown): data is ChartBar[] {
  if (!Array.isArray(data)) return false;
  if (data.length === 0) return true;

  const isNumberOrNull = (v: unknown) => v === null || typeof v === 'number';
  const isStringOrNull = (v: unknown) => v === null || typeof v === 'string';

  return (data as unknown[]).every((item) => {
    if (item === null || typeof item !== 'object') return false;
    const bar = item as Partial<ChartBar>;
    return (
      typeof bar.ts === 'string' &&
      typeof bar.provider === 'string' &&
      isStringOrNull(bar.data_status) &&
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
    name: 'PostgrestError',
    message,
    details: '',
    hint: '',
    code: 'NO_CHART_DATA',
  };
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const { symbol, timeframe = 'd1', days = 60, includeForecast = true, forecastDays = 10, forecastSteps, includeMLData = true } = 
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

    // Intraday refresh: if today's Alpaca bars are missing/stale, fetch from Alpaca and upsert.
    if (['m15', 'h1', 'h4'].includes(timeframe)) {
      const alpacaApiKey = Deno.env.get('ALPACA_API_KEY');
      const alpacaApiSecret = Deno.env.get('ALPACA_API_SECRET');

      if (alpacaApiKey && alpacaApiSecret) {
        const todayStartIso = new Date(new Date().setUTCHours(0, 0, 0, 0)).toISOString();
        const { data: latestToday } = await supabase
          .from('ohlc_bars_v2')
          .select('ts')
          .eq('symbol_id', symbolId)
          .eq('timeframe', timeframe)
          .eq('provider', 'alpaca')
          .eq('is_forecast', false)
          .gte('ts', todayStartIso)
          .order('ts', { ascending: false })
          .limit(1)
          .maybeSingle();

        const latestIso = latestToday?.ts ? new Date(latestToday.ts).toISOString() : null;
        const latestAgeSec = latestIso ? (Date.now() - new Date(latestIso).getTime()) / 1000 : Number.POSITIVE_INFINITY;
        const maxAgeSec = intradayMaxAgeSeconds(timeframe);

        if (!Number.isFinite(latestAgeSec) || latestAgeSec > maxAgeSec) {
          try {
            const nowIso = new Date().toISOString();
            const alpacaBars = await fetchAlpacaBars({
              symbol: symbol.toUpperCase(),
              timeframe,
              startIso: todayStartIso,
              endIso: nowIso,
              apiKey: alpacaApiKey,
              apiSecret: alpacaApiSecret,
            });

            if (alpacaBars.length > 0) {
              const rows = alpacaBars.map((bar) => ({
                symbol_id: symbolId,
                timeframe,
                ts: bar.t,
                open: bar.o,
                high: bar.h,
                low: bar.l,
                close: bar.c,
                volume: bar.v,
                provider: 'alpaca',
                is_intraday: true,
                is_forecast: false,
                data_status: 'live',
                fetched_at: nowIso,
              }));

              const { error: upsertError } = await supabase.from('ohlc_bars_v2').upsert(rows, {
                onConflict: 'symbol_id,timeframe,ts,provider,is_forecast',
              });

              if (upsertError) {
                throw upsertError;
              }
            }
          } catch (alpacaErr) {
            console.error('[chart-data-v2] Intraday Alpaca refresh failed:', alpacaErr);
          }
        }
      }
    }

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
    
    const requestedMaxBars = MAX_BARS_BY_TIMEFRAME[timeframe] ?? DEFAULT_MAX_BARS;
    const maxBars = Math.min(requestedMaxBars, POSTGREST_MAX_ROWS);

    const { data: dynamicData, error: chartError } = await supabase
      .rpc('get_chart_data_v2_dynamic', {
        p_symbol_id: symbolId,
        p_timeframe: timeframe,
        p_max_bars: maxBars,
        p_include_forecast: includeForecast,
      });

    const chartData = (!chartError && isValidChartBarArray(dynamicData))
      ? (dynamicData as ChartBar[])
      : null;

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
    if (chartData === null) {
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
    
    console.log(`[chart-data-v2] Success: received ${chartData.length} bars (maxBars=${maxBars})`);
    
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
    const superTrendAI = null;
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

          const expiryCutoffIso = new Date(
            Date.now() - INTRADAY_FORECAST_EXPIRY_GRACE_SECONDS * 1000,
          ).toISOString();

          const pathHorizon = '7d';
          const { data: intradayPath } = await supabase
            .from('ml_forecast_paths_intraday')
            .select('*')
            .eq('symbol_id', symbolId)
            .eq('timeframe', timeframe)
            .eq('horizon', pathHorizon)
            .gte('expires_at', expiryCutoffIso)
            .order('created_at', { ascending: false })
            .limit(1)
            .single();

          // Fetch latest intraday forecast
          const { data: intradayForecast } = await supabase
            .from('ml_forecasts_intraday')
            .select('*')
            .eq('symbol_id', symbolId)
            .eq('horizon', horizon)
            .gte('expires_at', expiryCutoffIso)
            .order('created_at', { ascending: false })
            .limit(1)
            .single();

          if (intradayForecast && Array.isArray(intradayForecast.points) && intradayForecast.points.length > 0) {
            const conf = clampNumber(intradayForecast.confidence, 0.5);

            const horizons: Array<{ horizon: string; points: Array<{ ts: number; value: number; lower: number; upper: number }> }> = [];

            if (intradayPath && Array.isArray(intradayPath.points) && intradayPath.points.length > 0) {
              const normalizedPathPoints = normalizeForecastPoints(intradayPath.points);
              const sampledPathPoints = sampleForecastPoints(normalizedPathPoints, INTRADAY_FORECAST_MAX_POINTS);
              if (sampledPathPoints.length > 0) {
                horizons.push({
                  horizon: pathHorizon,
                  points: sampledPathPoints,
                });
              }
            }

            const normalizedForecastPoints = normalizeForecastPoints(intradayForecast.points);
            const sampledForecastPoints = sampleForecastPoints(normalizedForecastPoints, INTRADAY_FORECAST_MAX_POINTS);
            if (sampledForecastPoints.length > 0) {
              horizons.push({
                horizon,
                points: sampledForecastPoints,
              });
            }

            mlSummary = {
              overallLabel: intradayForecast.overall_label,
              confidence: conf,
              horizons,
              srLevels: null,
              srDensity: null,
            };

            indicators = {
              supertrendFactor: null,
              supertrendPerformance: null,
              supertrendSignal: intradayForecast?.supertrend_direction === 'BULLISH' ? 1 :
                                 intradayForecast?.supertrend_direction === 'BEARISH' ? -1 : 0,
              trendLabel: intradayPath?.overall_label ?? intradayForecast.overall_label,
              trendConfidence: Math.round(conf * 10),
              stopLevel: null,
              trendDurationBars: null,
              rsi: null,
              adx: null,
              macdHistogram: null,
              kdjJ: null,
            };
          } else if (intradayForecast) {
            const intervalSec = timeframeToIntervalSeconds(timeframe);

            const newestNonForecast = [...historical, ...intraday]
              .filter((b) => !b.is_forecast)
              .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
              .pop();

            const baseTsSec = newestNonForecast
              ? Math.floor(new Date(newestNonForecast.ts).getTime() / 1000)
              : Math.floor(Date.now() / 1000);

            const targetPrice = Number(intradayForecast.target_price);
            if (!Number.isFinite(targetPrice)) {
              throw new Error('[chart-data-v2] intradayForecast.target_price is not a finite number');
            }

            const currentPrice = clampNumber(intradayForecast.current_price, targetPrice);
            const conf = clampNumber(intradayForecast.confidence, 0.5);

            const defaultStepsByTimeframe: Record<string, number> = {
              m15: 40,
              h1: 40,
              h4: 25,
            };

            const steps = typeof forecastSteps === 'number'
              ? Math.floor(forecastSteps)
              : (defaultStepsByTimeframe[timeframe] ?? 40);

            const shortPoints = intervalSec
              ? buildIntradayForecastPoints({
                baseTsSec,
                intervalSec,
                steps,
                currentPrice,
                targetPrice,
                confidence: conf,
              })
              : [{
                ts: Math.floor(new Date(intradayForecast.expires_at).getTime() / 1000),
                value: targetPrice,
                lower: targetPrice * 0.98,
                upper: targetPrice * 1.02,
              }];

            const sampledShortPoints = sampleForecastPoints(shortPoints, INTRADAY_FORECAST_MAX_POINTS);

            if (sampledShortPoints.length > 0) {
              mlSummary = {
                overallLabel: intradayForecast.overall_label,
                confidence: conf,
                horizons: [{
                  horizon,
                  points: sampledShortPoints,
                }],
                srLevels: null,
                srDensity: null,
              };

              indicators = {
                supertrendFactor: null,
                supertrendPerformance: null,
                supertrendSignal: intradayForecast?.supertrend_direction === 'BULLISH' ? 1 :
                                   intradayForecast?.supertrend_direction === 'BEARISH' ? -1 : 0,
                trendLabel: intradayForecast.overall_label,
                trendConfidence: Math.round(conf * 10),
                stopLevel: null,
                trendDurationBars: null,
                rsi: null,
                adx: null,
                macdHistogram: null,
                kdjJ: null,
              };
            }
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
            const normalizedPoints = normalizeForecastPoints(dailyForecast.points);
            const sampledPoints = sampleForecastPoints(normalizedPoints, DAILY_FORECAST_MAX_POINTS);

            mlSummary = {
              overallLabel: dailyForecast.overall_label,
              confidence: dailyForecast.confidence,
              horizons: [{
                horizon: dailyForecast.horizon,
                points: sampledPoints,
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
        forecast_steps: typeof forecastSteps === 'number' ? Math.floor(forecastSteps) : null,
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
    const err = error instanceof Error ? error : new Error(String(error));
    console.error('Chart data error:', err);
    return new Response(
      JSON.stringify({ error: 'Internal server error', details: err.message }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};
