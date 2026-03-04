// supabase/functions/_shared/chart-types.ts
// Shared TypeScript types for the unified /chart Edge Function response.

export interface OHLCBar {
  ts: string; // ISO 8601 timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_forecast?: boolean;
  provider?: string;
}

export interface ForecastPoint {
  ts: number; // Unix ms timestamp
  value: number;
  lower?: number;
  upper?: number;
}

export interface HorizonForecast {
  horizon: string;
  points: ForecastPoint[];
  targets?: Record<string, number | null>;
}

export interface MLSummary {
  overallLabel: string | null;
  confidence: number;
  horizons: HorizonForecast[];
  srLevels: Record<string, unknown> | null;
  srDensity: number | null;
}

export interface ChartIndicators {
  supertrendFactor: number | null;
  supertrendSignal: number | null; // -1 | 0 | 1
  trendLabel: string | null;
  trendConfidence: number | null;
  stopLevel: number | null;
  trendDurationBars: number | null;
  rsi: number | null;
  adx: number | null;
  macdHistogram: number | null;
  kdjJ: number | null;
}

export interface ChartMeta {
  lastBarTs: string | null;
  dataStatus: "fresh" | "stale" | "refreshing";
  isMarketOpen: boolean;
  totalBars: number;
  requestedRange: { start: string; end: string };
  latestForecastRunAt: string | null;
  hasPendingSplits: boolean;
}

export interface DataQuality {
  dataAgeHours: number | null;
  isStale: boolean;
  slaHours: number;
  sufficientForML: boolean;
  barCount: number;
}

export interface Freshness {
  ageMinutes: number | null;
  slaMinutes: number;
  isWithinSla: boolean;
}

export interface FuturesMetadata {
  requested_symbol: string;
  resolved_symbol: string;
  is_continuous: boolean;
  root_id: string | null;
  expiry_info: { month: number; year: number; display: string } | null;
}

export interface ChartLayers {
  historical: { count: number; data: OHLCBar[] };
  intraday: { count: number; data: OHLCBar[] };
  forecast: { count: number; data: OHLCBar[] };
}

export interface UnifiedChartResponse {
  symbol: string;
  symbol_id: string;
  timeframe: string;
  asset_type: string;
  bars: OHLCBar[];
  layers?: ChartLayers;
  optionsRanks: unknown[];
  mlSummary: MLSummary | null;
  indicators: ChartIndicators | null;
  meta: ChartMeta;
  dataQuality: DataQuality;
  freshness: Freshness;
  futures: FuturesMetadata | null;
}
