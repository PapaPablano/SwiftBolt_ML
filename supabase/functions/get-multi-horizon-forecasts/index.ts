import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

type HorizonMode = "timeframe" | "horizon" | "consensus";

type ForecastDirection = "BULLISH" | "BEARISH" | "NEUTRAL";

type TimeframeForecastRow = {
  timeframe: string;
  horizon: string;
  direction: ForecastDirection;
  confidence: number;
  target_price: number | null;
  upper_band: number | null;
  lower_band: number | null;
  is_base_horizon: boolean;
  handoff_confidence: number | null;
  consensus_weight: number | null;
  key_drivers: Record<string, unknown> | null;
  created_at: string;
};

type ConsensusForecastRow = {
  horizon: string;
  direction: ForecastDirection;
  confidence: number;
  target_price: number | null;
  upper_band: number | null;
  lower_band: number | null;
  contributing_timeframes: string[];
  agreement_score: number | null;
  handoff_quality: number | null;
  created_at: string;
};

type CascadeForecastRow = {
  source: string;
  direction: ForecastDirection;
  confidence: number;
  target_price: number | null;
  upper_band: number | null;
  lower_band: number | null;
  handoff_confidence: number | null;
  is_consensus: boolean;
  created_at: string;
};

type TimeframeGroup = {
  timeframe: string;
  baseHorizon: string | null;
  forecasts: Array<{
    horizon: string;
    direction: ForecastDirection;
    confidence: number;
    target: number | null;
    upper: number | null;
    lower: number | null;
    isBase: boolean;
    handoffConfidence: number | null;
    consensusWeight: number | null;
    keyDrivers: Record<string, unknown> | null;
    createdAt: string;
  }>;
};

type HorizonGroup = {
  horizon: string;
  forecasts: Array<{
    timeframe: string;
    direction: ForecastDirection;
    confidence: number;
    target: number | null;
    upper: number | null;
    lower: number | null;
    handoffConfidence: number | null;
    consensusWeight: number | null;
    keyDrivers: Record<string, unknown> | null;
    createdAt: string;
  }>;
};

type ConsensusGroup = {
  horizon: string;
  direction: ForecastDirection;
  confidence: number;
  target: number | null;
  upper: number | null;
  lower: number | null;
  agreementScore: number | null;
  handoffQuality: number | null;
  contributingTimeframes: string[];
  createdAt: string;
  cascade: Array<{
    source: string;
    direction: ForecastDirection;
    confidence: number;
    target: number | null;
    upper: number | null;
    lower: number | null;
    handoffConfidence: number | null;
    isConsensus: boolean;
    createdAt: string;
  }>;
};

type MultiHorizonResponse = {
  symbol: string;
  asOf: string;
  mode: HorizonMode;
  timeframeGroups?: TimeframeGroup[];
  horizonGroups?: HorizonGroup[];
  consensus?: ConsensusGroup[];
};

type ErrorResponse = { error: string };

const DEFAULT_MODE: HorizonMode = "timeframe";
const TIMEFRAME_ORDER = ["m15", "h1", "h4", "d1", "w1"];

serve(async (req) => {
  try {
    if (req.method !== "GET") {
      return jsonResponse({ error: "Method not allowed" }, 405);
    }

    const url = new URL(req.url);
    const symbolParam = url.searchParams.get("symbol");
    const modeParam = url.searchParams.get("mode") as HorizonMode | null;
    const timeframeParam = url.searchParams.get("timeframe");
    const horizonParam = url.searchParams.get("horizon");

    if (!symbolParam) {
      return jsonResponse({ error: "symbol parameter is required" }, 400);
    }

    const symbol = symbolParam.trim().toUpperCase();
    const mode = modeParam ?? DEFAULT_MODE;

    if (mode === "timeframe" && horizonParam) {
      return jsonResponse({ error: "horizon parameter is not valid for timeframe mode" }, 400);
    }

    if (mode === "horizon" && timeframeParam) {
      return jsonResponse({ error: "timeframe parameter is not valid for horizon mode" }, 400);
    }

    const supabase = getSupabaseClient();

    let timeframeRows: TimeframeForecastRow[] = [];
    if (!(mode === "consensus" && !timeframeParam)) {
      const { data, error } = await supabase.rpc("get_multi_horizon_forecasts", {
        p_symbol: symbol,
        p_timeframe: timeframeParam,
      });

      if (error) {
        console.error("[get-multi-horizon-forecasts] timeframe query failed", error);
        return jsonResponse({ error: "Failed to load timeframe forecasts" }, 500);
      }

      timeframeRows = (data ?? []) as TimeframeForecastRow[];
    }

    let consensusRows: ConsensusForecastRow[] = [];
    if (mode !== "timeframe") {
      const { data, error } = await supabase.rpc("get_consensus_forecasts", {
        p_symbol: symbol,
      });

      if (error) {
        console.error("[get-multi-horizon-forecasts] consensus query failed", error);
        return jsonResponse({ error: "Failed to load consensus forecasts" }, 500);
      }
      consensusRows = (data ?? []) as ConsensusForecastRow[];
    }

    const cascadeRows = await loadCascadeRows(
      supabase,
      symbol,
      mode,
      horizonParam,
      consensusRows,
    );
    if (cascadeRows.error) {
      console.error("[get-multi-horizon-forecasts] cascade query failed", cascadeRows.error);
      return jsonResponse({ error: "Failed to load forecast cascade" }, 500);
    }
    const cascades = cascadeRows.data;

    if (timeframeRows.length === 0 && consensusRows.length === 0) {
      return jsonResponse({ error: `No multi-horizon data available for ${symbol}` }, 404);
    }

    const latestTimestamp = getLatestTimestamp(timeframeRows, consensusRows, cascades);

    const response: MultiHorizonResponse = {
      symbol,
      asOf: latestTimestamp,
      mode,
    };

    if (mode === "timeframe") {
      response.timeframeGroups = buildTimeframeGroups(timeframeRows);
    } else if (mode === "horizon") {
      response.horizonGroups = buildHorizonGroups(timeframeRows);
      response.consensus = buildConsensusGroups(consensusRows, cascades);
    } else {
      response.consensus = buildConsensusGroups(consensusRows, cascades);
    }

    return jsonResponse(response, 200);
  } catch (error) {
    console.error("[get-multi-horizon-forecasts] unexpected error", error);
    return jsonResponse({ error: "Unexpected server error" }, 500);
  }
});

function buildTimeframeGroups(rows: TimeframeForecastRow[]): TimeframeGroup[] {
  const grouped = new Map<string, TimeframeGroup>();

  for (const row of rows) {
    const tfKey = row.timeframe ?? "unknown";
    if (!grouped.has(tfKey)) {
      grouped.set(tfKey, {
        timeframe: tfKey,
        baseHorizon: null,
        forecasts: [],
      });
    }

    const group = grouped.get(tfKey)!;
    if (row.is_base_horizon) {
      group.baseHorizon = row.horizon;
    }

    group.forecasts.push({
      horizon: row.horizon,
      direction: row.direction,
      confidence: row.confidence,
      target: row.target_price,
      upper: row.upper_band,
      lower: row.lower_band,
      isBase: row.is_base_horizon,
      handoffConfidence: row.handoff_confidence,
      consensusWeight: row.consensus_weight,
      keyDrivers: row.key_drivers ?? null,
      createdAt: row.created_at,
    });
  }

  const sorted = Array.from(grouped.values());
  sorted.sort((a, b) => timeframeIndex(a.timeframe) - timeframeIndex(b.timeframe));

  for (const group of sorted) {
    group.forecasts.sort((a, b) => compareHorizon(a.horizon, b.horizon));
  }

  return sorted;
}

function buildHorizonGroups(rows: TimeframeForecastRow[]): HorizonGroup[] {
  const grouped = new Map<string, HorizonGroup>();

  for (const row of rows) {
    if (!grouped.has(row.horizon)) {
      grouped.set(row.horizon, {
        horizon: row.horizon,
        forecasts: [],
      });
    }

    const group = grouped.get(row.horizon)!;
    group.forecasts.push({
      timeframe: row.timeframe ?? "unknown",
      direction: row.direction,
      confidence: row.confidence,
      target: row.target_price,
      upper: row.upper_band,
      lower: row.lower_band,
      handoffConfidence: row.handoff_confidence,
      consensusWeight: row.consensus_weight,
      keyDrivers: row.key_drivers ?? null,
      createdAt: row.created_at,
    });
  }

  const sorted = Array.from(grouped.values());
  sorted.sort((a, b) => compareHorizon(a.horizon, b.horizon));

  for (const group of sorted) {
    group.forecasts.sort((a, b) => timeframeIndex(a.timeframe) - timeframeIndex(b.timeframe));
  }

  return sorted;
}

function buildConsensusGroups(
  consensusRows: ConsensusForecastRow[],
  cascadeRows: CascadeForecastRow[],
): ConsensusGroup[] {
  if (consensusRows.length === 0) {
    return [];
  }

  return consensusRows.map((row) => {
    const contributing = Array.isArray(row.contributing_timeframes)
      ? row.contributing_timeframes
      : [];

    const cascade = cascadeRows
      .filter((c) => c.is_consensus || c.source === row.horizon)
      .map((c) => ({
        source: c.source,
        direction: c.direction,
        confidence: c.confidence,
        target: c.target_price,
        upper: c.upper_band,
        lower: c.lower_band,
        handoffConfidence: c.handoff_confidence,
        isConsensus: c.is_consensus,
        createdAt: c.created_at,
      }));

    return {
      horizon: row.horizon,
      direction: row.direction,
      confidence: row.confidence,
      target: row.target_price,
      upper: row.upper_band,
      lower: row.lower_band,
      agreementScore: row.agreement_score,
      handoffQuality: row.handoff_quality,
      contributingTimeframes: contributing,
      createdAt: row.created_at,
      cascade,
    };
  });
}

function getLatestTimestamp(
  timeframeRows: TimeframeForecastRow[],
  consensusRows: ConsensusForecastRow[],
  cascadeRows: CascadeForecastRow[],
): string {
  const timestamps = [
    ...timeframeRows.map((row) => row.created_at),
    ...consensusRows.map((row) => row.created_at),
    ...cascadeRows.map((row) => row.created_at),
  ].filter(Boolean);

  if (timestamps.length === 0) {
    return new Date().toISOString();
  }

  return timestamps.sort().reverse()[0];
}

function timeframeIndex(tf: string | null | undefined): number {
  if (!tf) return TIMEFRAME_ORDER.length;
  const idx = TIMEFRAME_ORDER.indexOf(tf);
  return idx === -1 ? TIMEFRAME_ORDER.length : idx;
}

function compareHorizon(a: string, b: string): number {
  return parseHorizonDays(a) - parseHorizonDays(b);
}

function parseHorizonDays(horizon: string): number {
  const match = horizon.match(/([0-9.]+)([a-zA-Z]+)/);
  if (!match) return Number.POSITIVE_INFINITY;

  const value = Number(match[1]);
  const unit = match[2].toLowerCase();

  switch (unit) {
    case "h":
      return value / 24;
    case "d":
      return value;
    case "w":
      return value * 7;
    case "m":
      return value * 30;
    case "y":
      return value * 365;
    default:
      return Number.POSITIVE_INFINITY;
  }
}

function jsonResponse<T>(body: T | ErrorResponse, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=60",
    },
  });
}

type CascadeLoadResult = {
  data: CascadeForecastRow[];
  error: unknown | null;
};

async function loadCascadeRows(
  supabase: ReturnType<typeof getSupabaseClient>,
  symbol: string,
  mode: HorizonMode,
  horizonParam: string | null,
  consensusRows: ConsensusForecastRow[],
): Promise<CascadeLoadResult> {
  if (mode === "timeframe") {
    return { data: [], error: null };
  }

  const horizons = horizonParam
    ? [horizonParam]
    : consensusRows.map((row) => row.horizon);

  const collected: CascadeForecastRow[] = [];
  for (const horizon of horizons) {
    const { data, error } = await supabase.rpc("get_forecast_cascade", {
      p_symbol: symbol,
      p_horizon: horizon,
    });

    if (error) {
      return { data: [], error };
    }

    const rows = (data ?? []) as CascadeForecastRow[];
    rows.forEach((row) => {
      collected.push({
        ...row,
        source: row.is_consensus ? "consensus" : row.source,
      });
    });
  }

  return { data: collected, error: null };
}
