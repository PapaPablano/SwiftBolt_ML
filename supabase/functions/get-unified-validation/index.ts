import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

type ValidationType = "backtest" | "walkforward";

const DEFAULT_SCORE = 0.5;
const DEFAULT_SIGNAL = "NEUTRAL" as const;
const TIMEFRAMES: Array<"m15" | "h1" | "d1"> = ["m15", "h1", "d1"];

interface ValidationResponse {
  symbol: string;
  backtest_score: number | null;
  walkforward_score: number | null;
  live_score: number | null;
  m15_signal: string;
  h1_signal: string;
  d1_signal: string;
  timestamp: number;
}

serve(async (req: Request) => {
  try {
    if (req.method !== "GET") {
      return new Response(
        JSON.stringify({ error: "Method not allowed" }),
        { status: 405, headers: { "Content-Type": "application/json" } },
      );
    }

    const url = new URL(req.url);
    const symbolParam = url.searchParams.get("symbol");

    if (!symbolParam) {
      return new Response(
        JSON.stringify({ error: "symbol parameter required" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    const symbol = symbolParam.trim().toUpperCase();
    const supabase = getSupabaseClient();

    const { data: symbolRow, error: symbolError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", symbol)
      .maybeSingle();

    if (symbolError) {
      console.error(
        "[get-unified-validation] symbol lookup error",
        symbolError,
      );
      return new Response(
        JSON.stringify({ error: "Failed to resolve symbol" }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      );
    }

    if (!symbolRow) {
      return new Response(
        JSON.stringify({ error: `Symbol ${symbol} not found` }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      );
    }

    const symbolId = symbolRow.id as string;

    const { data: validationRows, error: validationError } = await supabase
      .from("model_validation_stats")
      .select("validation_type, accuracy, created_at")
      .eq("symbol_id", symbolId)
      .in(
        "validation_type",
        ["backtest", "walkforward"] satisfies ValidationType[],
      )
      .order("created_at", { ascending: false });

    if (validationError) {
      console.error(
        "[get-unified-validation] validation stats error",
        validationError,
      );
      return new Response(
        JSON.stringify({ error: "Failed to fetch validation stats" }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      );
    }

    const validationScores = new Map<ValidationType, number>();
    validationRows?.forEach((row) => {
      const type = row.validation_type as ValidationType;
      if (validationScores.has(type)) return;
      const parsed = parseNumber(row.accuracy);
      if (parsed !== null) {
        validationScores.set(type, parsed);
      }
    });

    const { data: liveRow, error: liveError } = await supabase
      .from("live_predictions")
      .select("accuracy_score, prediction_time")
      .eq("symbol_id", symbolId)
      .order("prediction_time", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (liveError) {
      console.error("[get-unified-validation] live score error", liveError);
      return new Response(
        JSON.stringify({ error: "Failed to fetch live score" }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      );
    }

    const timeframeSignals = new Map<string, string>();
    for (const timeframe of TIMEFRAMES) {
      const { data: tfRow, error: tfError } = await supabase
        .from("live_predictions")
        .select("signal")
        .eq("symbol_id", symbolId)
        .eq("timeframe", timeframe)
        .order("prediction_time", { ascending: false })
        .limit(1)
        .maybeSingle();

      if (tfError) {
        console.error(
          `[get-unified-validation] ${timeframe} signal error`,
          tfError,
        );
        return new Response(
          JSON.stringify({ error: "Failed to fetch timeframe signals" }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      }

      if (tfRow?.signal) {
        timeframeSignals.set(timeframe, tfRow.signal as string);
      }
    }

    const liveScore = parseNumber(liveRow?.accuracy_score);

    const response: ValidationResponse = {
      symbol,
      backtest_score: validationScores.has("backtest")
        ? validationScores.get("backtest") ?? null
        : null,
      walkforward_score: validationScores.has("walkforward")
        ? validationScores.get("walkforward") ?? null
        : null,
      live_score: liveScore,
      m15_signal: timeframeSignals.get("m15") ?? DEFAULT_SIGNAL,
      h1_signal: timeframeSignals.get("h1") ?? DEFAULT_SIGNAL,
      d1_signal: timeframeSignals.get("d1") ?? DEFAULT_SIGNAL,
      timestamp: Date.now(),
    };

    const normalizedResponse = withDefaults(response);

    return new Response(JSON.stringify(normalizedResponse), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("[get-unified-validation] unexpected error", error);
    return new Response(
      JSON.stringify({ error: "Unexpected server error" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
});

function parseNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function withDefaults(response: ValidationResponse): ValidationResponse {
  return {
    ...response,
    backtest_score: response.backtest_score ?? DEFAULT_SCORE,
    walkforward_score: response.walkforward_score ?? DEFAULT_SCORE,
    live_score: response.live_score ?? DEFAULT_SCORE,
  };
}
