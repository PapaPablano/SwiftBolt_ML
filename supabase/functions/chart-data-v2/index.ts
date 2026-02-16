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
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.3';
import type { PostgrestError } from 'https://esm.sh/@supabase/supabase-js@2.39.3';

declare const Deno: {
  env: {
    get(key: string): string | undefined;
  };
};

addEventListener('error', (event) => {
  console.error('[chart-data-v2] Unhandled error:', event?.error?.stack ?? event?.error ?? event?.message);
});

addEventListener('unhandledrejection', (event) => {
  console.error('[chart-data-v2] Unhandled rejection:', event?.reason?.stack ?? event?.reason);
});

interface ChartRequest {
  symbol: string;
  timeframe?: string;
  days?: number;
  includeForecast?: boolean;
  forecastDays?: number;
  forecastSteps?: number;
  includeMLData?: boolean;
}

type DailyBarRow = {
  ts: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
};

type WeeklyBarRow = DailyBarRow;

function normalizeBarTimestamp(ts: string): Date | null {
  if (!ts) return null;
  const normalized = ts.includes('T') ? ts : ts.replace(' ', 'T');
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function weekStartKey(date: Date): string {
  const day = date.getUTCDay();
  const offset = (day + 6) % 7; // Monday-based
  const monday = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  monday.setUTCDate(monday.getUTCDate() - offset);
  return monday.toISOString().split('T')[0];
}

function aggregateWeeklyBars(dailyBars: DailyBarRow[]): WeeklyBarRow[] {
  if (!dailyBars.length) return [];
  const buckets = new Map<string, DailyBarRow[]>();

  for (const bar of dailyBars) {
    const date = normalizeBarTimestamp(bar.ts);
    if (!date) continue;
    const key = weekStartKey(date);
    const existing = buckets.get(key);
    if (existing) {
      existing.push(bar);
    } else {
      buckets.set(key, [bar]);
    }
  }

  const weeklyBars: WeeklyBarRow[] = [];
  for (const [_key, bars] of buckets) {
    bars.sort((a, b) => {
      const aDate = normalizeBarTimestamp(a.ts) ?? new Date(0);
      const bDate = normalizeBarTimestamp(b.ts) ?? new Date(0);
      return aDate.getTime() - bDate.getTime();
    });
    const first = bars[0];
    const last = bars[bars.length - 1];
    const firstDate = normalizeBarTimestamp(first.ts);
    const timeSuffix = firstDate
      ? `T${String(firstDate.getUTCHours()).padStart(2, '0')}:${String(firstDate.getUTCMinutes()).padStart(2, '0')}:00Z`
      : 'T05:00:00Z';
    const ts = `${weekStartKey(firstDate ?? new Date())}${timeSuffix}`;
    const highs = bars.map((b) => b.high ?? Number.NEGATIVE_INFINITY);
    const lows = bars.map((b) => b.low ?? Number.POSITIVE_INFINITY);
    weeklyBars.push({
      ts,
      open: first.open,
      high: Math.max(...highs),
      low: Math.min(...lows),
      close: last.close,
      volume: bars.reduce((sum, b) => sum + (b.volume ?? 0), 0),
    });
  }

  weeklyBars.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  return weeklyBars;
}

function isWeeklyBarCurrent(latestIso: string | null): boolean {
  if (!latestIso) return false;
  const latest = normalizeBarTimestamp(latestIso);
  if (!latest) return false;
  const now = new Date();
  const currentWeekStart = weekStartKey(now);
  const latestWeekStart = weekStartKey(latest);
  return latestWeekStart >= currentWeekStart;
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
  h4: 950,
  d1: 2000,
  w1: 2000,
};
const ALL_TIMEFRAMES: Array<'m15' | 'h1' | 'h4' | 'd1' | 'w1'> = ['m15', 'h1', 'h4', 'd1', 'w1'];
const DEFAULT_MAX_BARS = 950;
const POSTGREST_MAX_ROWS = 1000;
const SOFT_MAX_ROWS = 950;

function alpacaTimeframe(timeframe: string): string | null {
  switch (timeframe) {
    case 'm15':
      return '15Min';
    case 'h1':
      return '1Hour';
    case 'h4':
      return '4Hour';
    case 'd1':
      return '1Day';
    case 'w1':
      return '1Week';
    default:
      return null;
  }
}

function timeframeMaxAgeSeconds(timeframe: string): number {
  switch (timeframe) {
    case 'm15':
      return 25 * 60;
    case 'h1':
      return 2 * 60 * 60;
    case 'h4':
      return 5 * 60 * 60;
    case 'd1':
      return 72 * 60 * 60;
    case 'w1':
      return 10 * 24 * 60 * 60;
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
const DAILY_FORECAST_HORIZONS = ['1D', '1W', '1M'];

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

// Normalize required fields; pass through extended fields (ohlc, indicators, timeframe, step). Normalize 4h_trading → h4 at API boundary.
function normalizeForecastPoint(point: Record<string, unknown>): Record<string, unknown> & { ts: number; value: number; lower: number; upper: number } {
  const out: Record<string, unknown> = {
    ...point,
    ts: toUnixSeconds(point['ts'] ?? point['time']),
    value: Number(point['value'] ?? point['price'] ?? point['mid'] ?? point['midpoint'] ?? 0),
    lower: Number(point['lower'] ?? point['lower_band'] ?? point['min'] ?? point['lower_bound'] ?? point['value'] ?? point['price'] ?? 0),
    upper: Number(point['upper'] ?? point['upper_band'] ?? point['max'] ?? point['upper_bound'] ?? point['value'] ?? point['price'] ?? 0),
  };
  if (out['timeframe'] === '4h_trading') out['timeframe'] = 'h4';
  return out as Record<string, unknown> & { ts: number; value: number; lower: number; upper: number };
}

function normalizeForecastPoints(points: unknown): Array<Record<string, unknown> & { ts: number; value: number; lower: number; upper: number }> {
  if (!Array.isArray(points)) {
    return [];
  }
  return points.map((point) => normalizeForecastPoint(isRecord(point) ? point : {}));
}

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function parseRecord(value: unknown): Record<string, unknown> | null {
  if (isRecord(value)) {
    return value;
  }
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      if (isRecord(parsed)) {
        return parsed;
      }
    } catch {
      return null;
    }
  }
  return null;
}

function buildForecastTargets(
  row: Record<string, unknown>,
  points: Array<{ ts: number; value: number; lower: number; upper: number }>,
): Record<string, number | null> | null {
  const synthesis = parseRecord(row['synthesis_data']) ?? {};
  const tp1 = toNumber(synthesis['tp1'] ?? synthesis['target'] ?? row['target_price']);
  const tp2 = toNumber(synthesis['tp2']);
  const tp3 = toNumber(synthesis['tp3']);
  const stopLoss = toNumber(synthesis['stop_loss'] ?? synthesis['stop'] ?? synthesis['sl']);
  const qualityScore = toNumber(synthesis['quality_score'] ?? row['quality_score']);
  const confluenceScore = toNumber(synthesis['confluence_score']);

  const fallbackTp1 = tp1 ?? (points.length > 0 ? points[points.length - 1].value : null);
  const hasAny = [fallbackTp1, tp2, tp3, stopLoss, qualityScore, confluenceScore]
    .some((value) => typeof value === 'number' && Number.isFinite(value));

  if (!hasAny) {
    return null;
  }

  return {
    tp1: fallbackTp1,
    tp2,
    tp3,
    stop_loss: stopLoss,
    quality_score: qualityScore,
    confluence_score: confluenceScore,
  };
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

function buildForecastBarsFromSummary(summary: unknown): ChartBar[] {
  if (!isRecord(summary) || !Array.isArray(summary['horizons'])) {
    return [];
  }

  const horizons = summary['horizons'] as Array<Record<string, unknown>>;
  const confidence = clampNumber(summary['confidence'], 0.5);
  const todayStr = new Date().toISOString().split('T')[0];
  const bars: ChartBar[] = [];

  const horizonLabels = horizons
    .map((horizon) => String(horizon?.['horizon'] ?? '').toUpperCase())
    .filter((label) => label.length > 0);
  const isDailyMultiHorizon = horizonLabels.length > 1
    && horizonLabels.every((label) => DAILY_FORECAST_HORIZONS.includes(label));

  if (isDailyMultiHorizon) {
    for (const horizon of horizons) {
      const points = normalizeForecastPoints(horizon?.['points']);
      if (points.length === 0) {
        continue;
      }
      const targetPoint = points.reduce((latest, current) => (current.ts > latest.ts ? current : latest), points[0]);
      if (!Number.isFinite(targetPoint.ts)) {
        continue;
      }
      const tsIso = new Date(targetPoint.ts * 1000).toISOString();
      if (tsIso.split('T')[0] <= todayStr) {
        continue;
      }
      bars.push({
        ts: tsIso,
        open: targetPoint.value,
        high: targetPoint.upper,
        low: targetPoint.lower,
        close: targetPoint.value,
        volume: null,
        provider: 'ml_forecast',
        is_intraday: false,
        is_forecast: true,
        data_status: 'forecast',
        confidence_score: confidence,
        upper_band: targetPoint.upper,
        lower_band: targetPoint.lower,
      });
    }

    return bars.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  }

  for (const horizon of horizons) {
    const points = normalizeForecastPoints(horizon?.['points']);
    for (const point of points) {
      if (!Number.isFinite(point.ts)) {
        continue;
      }
      const tsIso = new Date(point.ts * 1000).toISOString();
      if (tsIso.split('T')[0] <= todayStr) {
        continue;
      }
      bars.push({
        ts: tsIso,
        open: point.value,
        high: point.upper,
        low: point.lower,
        close: point.value,
        volume: null,
        provider: 'ml_forecast',
        is_intraday: false,
        is_forecast: true,
        data_status: 'forecast',
        confidence_score: confidence,
        upper_band: point.upper,
        lower_band: point.lower,
      });
    }
  }

  return bars;
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

    // Resolve futures symbols (continuous aliases like GC1! or dated contracts like GCZ25)
    const requestedSymbol = symbol.toUpperCase();
    let resolvedSymbol = requestedSymbol;
    let isContinuousFutures = false;
    let resolutionSource: 'direct' | 'resolved' | 'continuous' = 'direct';
    
    // Check if this is a futures root (just "GC", "ES" without expiry)
    const futuresRootPattern = /^[A-Z]{1,4}$/;
    if (futuresRootPattern.test(requestedSymbol)) {
      // Check if it's actually a futures root in the database
      const { data: rootCheck } = await supabase
        .from('futures_roots')
        .select('symbol')
        .eq('symbol', requestedSymbol)
        .single();
        
      if (rootCheck) {
        return new Response(
          JSON.stringify({ 
            error: `Futures root "${requestedSymbol}" requires expiry selection. Please select a specific contract (e.g., ${requestedSymbol}Z25) or continuous alias (e.g., ${requestedSymbol}1!).`,
            requires_expiry_picker: true,
            root_symbol: requestedSymbol
          }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }
    }
    
    // Check if this is a futures symbol with expiry or continuous alias
    // Pattern: GC1!, GCZ25, ES1!, ESZ25, etc.
    const futuresPattern = /^([A-Z]{1,4})(\d{1,2}!|[FGHJKMNQUVXZ]\d{2})$/;
    if (futuresPattern.test(requestedSymbol)) {
      console.log(`[chart-data-v2] Detected futures symbol: ${requestedSymbol}`);
      
      try {
        // Try to resolve using the SQL function
        const { data: resolved, error: resolveError } = await supabase
          .rpc('resolve_futures_symbol', { 
            p_symbol: requestedSymbol,
            p_as_of: new Date().toISOString().split('T')[0]
          });
        
        if (!resolveError && resolved && resolved.length > 0) {
          const result = resolved[0];
          resolvedSymbol = result.resolved_symbol;
          isContinuousFutures = result.is_continuous;
          resolutionSource = isContinuousFutures ? 'continuous' : 'resolved';
          console.log(`[chart-data-v2] Resolved ${requestedSymbol} → ${resolvedSymbol} (continuous: ${isContinuousFutures})`);
        } else {
          console.log(`[chart-data-v2] Could not resolve futures symbol ${requestedSymbol}, using as-is`);
        }
      } catch (err) {
        console.error(`[chart-data-v2] Error resolving futures symbol:`, err);
      }
    }

    // Get symbol_id using the resolved symbol
    const { data: symbolData, error: symbolError } = await supabase
      .from('symbols')
      .select('id, ticker, asset_type, futures_root_id, is_continuous, expiry_month, expiry_year')
      .eq('ticker', resolvedSymbol)
      .single();

    if (symbolError || !symbolData) {
      return new Response(
        JSON.stringify({ error: `Symbol ${resolvedSymbol} not found` }),
        { status: 404, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const symbolId = symbolData.id;

    // Alpaca refresh: keep all timeframes current when bars are stale.
    const alpacaApiKey = Deno.env.get('ALPACA_API_KEY');
    const alpacaApiSecret = Deno.env.get('ALPACA_API_SECRET');

    if (alpacaApiKey && alpacaApiSecret) {
      const nowIso = new Date().toISOString();
      for (const tf of ALL_TIMEFRAMES) {
        const intervalSec = timeframeToIntervalSeconds(tf) ?? 0;
        const { data: latestBar } = await supabase
          .from('ohlc_bars_v2')
          .select('ts')
          .eq('symbol_id', symbolId)
          .eq('timeframe', tf)
          .eq('provider', 'alpaca')
          .eq('is_forecast', false)
          .order('ts', { ascending: false })
          .limit(1)
          .maybeSingle();

        const latestIso = latestBar?.ts ? new Date(latestBar.ts).toISOString() : null;
        const latestAgeSec = latestIso ? (Date.now() - new Date(latestIso).getTime()) / 1000 : Number.POSITIVE_INFINITY;
        const maxAgeSec = timeframeMaxAgeSeconds(tf);
        const weeklyStale = tf === 'w1' && !isWeeklyBarCurrent(latestIso);

        if (!Number.isFinite(latestAgeSec) || latestAgeSec > maxAgeSec || weeklyStale) {
          try {
            const startIso = latestIso
              ? new Date(new Date(latestIso).getTime() - intervalSec * 1000 * 2).toISOString()
              : new Date(new Date().setUTCFullYear(new Date().getUTCFullYear() - 2)).toISOString();

            const alpacaBars = await fetchAlpacaBars({
              symbol: symbol.toUpperCase(),
              timeframe: tf,
              startIso,
              endIso: nowIso,
              apiKey: alpacaApiKey,
              apiSecret: alpacaApiSecret,
            });

            const newestAlpacaIso = alpacaBars.length > 0
              ? new Date(alpacaBars[alpacaBars.length - 1].t).toISOString()
              : null;
            const isWeeklyStale = tf === 'w1'
              && latestIso
              && (!newestAlpacaIso || new Date(newestAlpacaIso).getTime() <= new Date(latestIso).getTime());

            if (alpacaBars.length > 0 && !isWeeklyStale) {
              const isIntraday = ['m15', 'h1', 'h4'].includes(tf);
              const rows = alpacaBars.map((bar) => ({
                symbol_id: symbolId,
                timeframe: tf,
                ts: bar.t,
                open: bar.o,
                high: bar.h,
                low: bar.l,
                close: bar.c,
                volume: bar.v,
                provider: 'alpaca',
                is_intraday: isIntraday,
                is_forecast: false,
                data_status: isIntraday ? 'live' : 'verified',
                fetched_at: nowIso,
              }));

              const { error: upsertError } = await supabase.from('ohlc_bars_v2').upsert(rows, {
                onConflict: 'symbol_id,timeframe,ts,provider,is_forecast',
              });

              if (upsertError) {
                throw upsertError;
              }
            } else if (tf === 'w1') {
              const weeklyStartIso = latestIso ?? new Date(new Date().setUTCFullYear(new Date().getUTCFullYear() - 2)).toISOString();
              const { data: dailyBars } = await supabase
                .from('ohlc_bars_v2')
                .select('ts, open, high, low, close, volume')
                .eq('symbol_id', symbolId)
                .eq('timeframe', 'd1')
                .eq('provider', 'alpaca')
                .eq('is_forecast', false)
                .gte('ts', weeklyStartIso)
                .order('ts', { ascending: true })
                .limit(2000);

              const weeklyBars = aggregateWeeklyBars((dailyBars ?? []) as DailyBarRow[]);
              if (weeklyBars.length > 0) {
                const rows = weeklyBars.map((bar) => ({
                  symbol_id: symbolId,
                  timeframe: tf,
                  ts: bar.ts,
                  open: bar.open,
                  high: bar.high,
                  low: bar.low,
                  close: bar.close,
                  volume: bar.volume,
                  provider: 'alpaca',
                  is_intraday: false,
                  is_forecast: false,
                  data_status: 'verified',
                  fetched_at: nowIso,
                }));

                const { error: weeklyUpsertError } = await supabase.from('ohlc_bars_v2').upsert(rows, {
                  onConflict: 'symbol_id,timeframe,ts,provider,is_forecast',
                });

                if (weeklyUpsertError) {
                  throw weeklyUpsertError;
                }
              }
            }
          } catch (alpacaErr) {
            console.error(`[chart-data-v2] Alpaca refresh failed for ${tf}:`, alpacaErr);
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
    const maxBars = Math.min(requestedMaxBars, POSTGREST_MAX_ROWS, SOFT_MAX_ROWS);

    const { data: dynamicData, error: chartError } = await supabase
      .rpc('get_chart_data_v2_dynamic', {
        p_symbol_id: symbolId,
        p_timeframe: timeframe,
        p_max_bars: maxBars,
        p_include_forecast: includeForecast,
      });

    let chartData = (!chartError && isValidChartBarArray(dynamicData))
      ? (dynamicData as ChartBar[])
      : null;

    // SPECIAL CASE: For d1 timeframe, also fetch h1 data for today to build intraday layer
    // This ensures we always have today's OHLC data that can be aggregated into a single daily bar
    let intradayHourlyData: ChartBar[] = [];
    if (timeframe === 'd1' && chartData && chartData.length > 0) {
      console.log('[chart-data-v2] d1 timeframe detected - fetching h1 data for intraday layer');

      const { data: h1Data, error: h1Error } = await supabase
        .rpc('get_chart_data_v2_dynamic', {
          p_symbol_id: symbolId,
          p_timeframe: 'h1',
          p_max_bars: 24, // Up to 24 hourly bars for today
          p_include_forecast: false,
        });

      if (!h1Error && isValidChartBarArray(h1Data)) {
        intradayHourlyData = h1Data as ChartBar[];
        console.log(`[chart-data-v2] Fetched ${intradayHourlyData.length} h1 bars for d1 intraday layer`);
      } else {
        console.log('[chart-data-v2] Could not fetch h1 data for d1 intraday layer');
      }
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
    let intraday: ChartBar[] = [];
    const forecast: ChartBar[] = [];

    const todayStr = new Date().toISOString().split('T')[0];

    // For d1 timeframe, use the h1 hourly data as intraday layer (will be aggregated client-side)
    if (timeframe === 'd1' && intradayHourlyData.length > 0) {
      console.log(`[chart-data-v2] Using h1 data (${intradayHourlyData.length} bars) as intraday layer for d1`);
      intraday = intradayHourlyData;

      // All d1 bars go to historical (we'll use h1 for today's aggregation)
      for (const bar of (chartData || [])) {
        if (bar.is_forecast) {
          forecast.push(bar);
        } else {
          historical.push(bar);
        }
      }
    } else {
      // Normal layer separation for other timeframes
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

          // Attach daily horizon targets so they can render on intraday charts
          const { data: dailyForecasts } = await supabase
            .from('ml_forecasts')
            .select('*')
            .eq('symbol_id', symbolId)
            .in('horizon', DAILY_FORECAST_HORIZONS)
            .order('created_at', { ascending: false });

          const latestByHorizon = new Map<string, Record<string, unknown>>();
          if (Array.isArray(dailyForecasts)) {
            for (const row of dailyForecasts) {
              const horizon = typeof row?.horizon === 'string' ? row.horizon : null;
              if (!horizon || latestByHorizon.has(horizon)) {
                continue;
              }
              latestByHorizon.set(horizon, row);
            }
          }

          const dailySeries = DAILY_FORECAST_HORIZONS
            .map((horizon) => {
              const row = latestByHorizon.get(horizon);
              if (!row || !row.points) {
                return null;
              }
              const normalizedPoints = normalizeForecastPoints(row.points);
              const sampledPoints = sampleForecastPoints(normalizedPoints, DAILY_FORECAST_MAX_POINTS);
              if (sampledPoints.length === 0) {
                return null;
              }
              return {
                horizon,
                points: sampledPoints,
                targets: buildForecastTargets(row, sampledPoints),
                row,
              };
            })
            .filter((item): item is {
              horizon: string;
              points: Array<{ ts: number; value: number; lower: number; upper: number }>;
              targets: Record<string, number | null> | null;
              row: Record<string, unknown>;
            } => item !== null);

          if (dailySeries.length > 0) {
            const bestForecast = dailySeries
              .map((item) => item.row)
              .reduce<Record<string, unknown>>((best, current) => {
                const bestConf = clampNumber(best?.confidence, -1);
                const currentConf = clampNumber(current?.confidence, -1);
                if (currentConf > bestConf) {
                  return current;
                }
                return best;
              }, dailySeries[0].row);

            const dailySummary = {
              overallLabel: typeof bestForecast?.overall_label === 'string' ? bestForecast.overall_label : null,
              confidence: clampNumber(bestForecast?.confidence, 0.5),
              horizons: dailySeries.map((item) => ({
                horizon: item.horizon,
                points: item.points,
                targets: item.targets ?? undefined,
              })),
              srLevels: (bestForecast?.sr_levels as Record<string, unknown>) || null,
              srDensity: typeof bestForecast?.sr_density === 'number' ? bestForecast.sr_density : null,
            };

            if (mlSummary) {
              const existing = new Set(
                (mlSummary.horizons || []).map((h: { horizon: string }) => h.horizon.toUpperCase()),
              );
              const mergedHorizons = [...(mlSummary.horizons || [])];
              for (const horizon of dailySummary.horizons) {
                if (!existing.has(horizon.horizon.toUpperCase())) {
                  mergedHorizons.push(horizon);
                }
              }
              mlSummary = {
                ...mlSummary,
                horizons: mergedHorizons,
                overallLabel: mlSummary.overallLabel ?? dailySummary.overallLabel,
                confidence: mlSummary.confidence ?? dailySummary.confidence,
                srLevels: mlSummary.srLevels ?? dailySummary.srLevels,
                srDensity: mlSummary.srDensity ?? dailySummary.srDensity,
              };
            } else {
              mlSummary = dailySummary;
            }
          }
        } else {
          // Fetch daily forecast for daily/weekly timeframes (latest per horizon)
          const { data: dailyForecasts } = await supabase
            .from('ml_forecasts')
            .select('*')
            .eq('symbol_id', symbolId)
            .in('horizon', DAILY_FORECAST_HORIZONS)
            .order('created_at', { ascending: false });

          const latestByHorizon = new Map<string, Record<string, unknown>>();
          if (Array.isArray(dailyForecasts)) {
            for (const row of dailyForecasts) {
              const horizon = typeof row?.horizon === 'string' ? row.horizon : null;
              if (!horizon || latestByHorizon.has(horizon)) {
                continue;
              }
              latestByHorizon.set(horizon, row);
            }
          }

          const horizonSeries = DAILY_FORECAST_HORIZONS
            .map((horizon) => {
              const row = latestByHorizon.get(horizon);
              if (!row || !row.points) {
                return null;
              }
              const normalizedPoints = normalizeForecastPoints(row.points);
              const sampledPoints = sampleForecastPoints(normalizedPoints, DAILY_FORECAST_MAX_POINTS);
          if (sampledPoints.length === 0) {
            return null;
          }
          const targets = buildForecastTargets(row, sampledPoints);
          return {
            horizon,
            points: sampledPoints,
            targets,
            row,
          };
        })
            .filter((item): item is {
              horizon: string;
              points: Array<{ ts: number; value: number; lower: number; upper: number }>;
              targets: Record<string, number | null> | null;
              row: Record<string, unknown>;
            } => item !== null);

          if (horizonSeries.length > 0) {
            const bestForecast = horizonSeries
              .map((item) => item.row)
              .reduce<Record<string, unknown>>((best, current) => {
                const bestConf = clampNumber(best?.confidence, -1);
                const currentConf = clampNumber(current?.confidence, -1);
                if (currentConf > bestConf) {
                  return current;
                }
                return best;
              }, horizonSeries[0].row);

            mlSummary = {
              overallLabel: typeof bestForecast?.overall_label === 'string' ? bestForecast.overall_label : null,
              confidence: clampNumber(bestForecast?.confidence, 0.5),
              horizons: horizonSeries.map((item) => ({
                horizon: item.horizon,
                points: item.points,
                targets: item.targets ?? undefined,
              })),
              srLevels: (bestForecast?.sr_levels as Record<string, unknown>) || null,
              srDensity: typeof bestForecast?.sr_density === 'number' ? bestForecast.sr_density : null,
            };

            indicators = {
              supertrendFactor: typeof bestForecast?.supertrend_factor === 'number' ? bestForecast.supertrend_factor : null,
              supertrendPerformance: typeof bestForecast?.supertrend_performance === 'number' ? bestForecast.supertrend_performance : null,
              supertrendSignal: typeof bestForecast?.supertrend_signal === 'number' ? bestForecast.supertrend_signal : null,
              trendLabel: typeof bestForecast?.trend_label === 'string' ? bestForecast.trend_label : null,
              trendConfidence: typeof bestForecast?.trend_confidence === 'number' ? bestForecast.trend_confidence : null,
              stopLevel: typeof bestForecast?.stop_level === 'number' ? bestForecast.stop_level : null,
              trendDurationBars: typeof bestForecast?.trend_duration_bars === 'number' ? bestForecast.trend_duration_bars : null,
              rsi: typeof bestForecast?.rsi === 'number' ? bestForecast.rsi : null,
              adx: typeof bestForecast?.adx === 'number' ? bestForecast.adx : null,
              macdHistogram: typeof bestForecast?.macd_histogram === 'number' ? bestForecast.macd_histogram : null,
              kdjJ: typeof bestForecast?.kdj_j === 'number' ? bestForecast.kdj_j : null,
            };
          }
        }
      } catch (mlError) {
        console.error('[chart-data-v2] ML enrichment error:', mlError);
        // Continue without ML data
      }
    }

    if (includeForecast && mlSummary) {
      const synthesizedForecast = buildForecastBarsFromSummary(mlSummary);
      if (synthesizedForecast.length > 0) {
        const existingTs = new Set(forecast.map((bar) => bar.ts));
        for (const bar of synthesizedForecast) {
          if (!existingTs.has(bar.ts)) {
            forecast.push(bar);
          }
        }
        forecast.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
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

    // Build futures metadata if applicable
    let futuresMetadata = null;
    if (symbolData?.asset_type === 'future') {
      futuresMetadata = {
        requested_symbol: requestedSymbol,
        resolved_symbol: resolvedSymbol,
        is_continuous: isContinuousFutures,
        resolution_source: resolutionSource,
        root_id: symbolData?.futures_root_id || null,
        is_dated_contract: !isContinuousFutures && symbolData?.expiry_month != null,
        expiry_info: symbolData?.expiry_month ? {
          month: symbolData.expiry_month,
          year: symbolData.expiry_year,
          display: `${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][symbolData.expiry_month - 1]} ${symbolData.expiry_year}`
        } : null
      };
    }

    const response = {
      symbol: resolvedSymbol,
      symbol_id: symbolId,
      asset_type: symbolData?.asset_type || 'unknown',
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
      futures: futuresMetadata,
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
