// ga-strategy: Return GA-optimized trading parameters for a symbol
// GET /ga-strategy?symbol=AAPL - Get active parameters
// POST /ga-strategy - Trigger GA optimization run
//
// Returns optimized entry/exit thresholds from genetic algorithm

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  errorResponse,
  handleCorsOptions,
  jsonResponse,
} from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

// Strategy genes from GA optimization
interface StrategyGenes {
  // Ranking thresholds
  minCompositeRank: number;
  minMomentumScore: number;
  minValueScore: number;
  signalFilter: "buy" | "discount" | "runner" | "greeks" | "any";

  // Entry timing
  entryHourMin: number;
  entryHourMax: number;
  minBarAgeMinutes: number;

  // Greeks thresholds
  deltaExit: number;
  gammaExit: number;
  vegaExit: number;
  thetaMin: number;
  ivRankMin: number;
  ivRankMax: number;

  // Hold timing
  minHoldMinutes: number;
  maxHoldMinutes: number;
  profitTargetPct: number;
  stopLossPct: number;

  // Position sizing
  positionSizePct: number;
  maxConcurrentTrades: number;

  // Trade frequency
  minTradesPerDay: number;
  maxTradesPerSymbol: number;
}

interface StrategyFitness {
  totalPnl: number;
  pnlPct: number;
  winRate: number;
  profitFactor: number;
  sharpeRatio: number;
  maxDrawdown: number;
  numTrades: number;
  avgTradeDuration: number;
  tradesClosed: number;
}

interface GAStrategyResponse {
  symbol: string;
  hasStrategy: boolean;
  strategy?: {
    id: string;
    genes: StrategyGenes;
    fitness: StrategyFitness;
    createdAt: string;
    trainingDays: number;
    trainingSamples: number;
    generationsRun: number;
  };
  recommendation?: {
    entryConditions: string[];
    exitConditions: string[];
    riskManagement: string[];
  };
}

interface TriggerOptimizationResponse {
  success: boolean;
  message: string;
  runId?: string;
  estimatedMinutes?: number;
}

// Convert snake_case DB columns to camelCase for response
function snakeToCamel(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(
      /_([a-z])/g,
      (_, letter) => letter.toUpperCase(),
    );
    result[camelKey] = value;
  }
  return result;
}

// Generate human-readable recommendations from genes
function generateRecommendations(
  genes: StrategyGenes,
): GAStrategyResponse["recommendation"] {
  const entry: string[] = [];
  const exit: string[] = [];
  const risk: string[] = [];

  // Entry conditions
  entry.push(`Require composite rank ≥ ${genes.minCompositeRank.toFixed(0)}`);
  entry.push(
    `Trade only between ${genes.entryHourMin}:00 - ${genes.entryHourMax}:00 EST`,
  );
  if (genes.signalFilter !== "any") {
    entry.push(`Filter for ${genes.signalFilter.toUpperCase()} signal only`);
  }
  entry.push(
    `IV Rank between ${genes.ivRankMin.toFixed(0)}-${
      genes.ivRankMax.toFixed(0)
    }`,
  );
  entry.push(`Theta must be ≥ ${genes.thetaMin.toFixed(2)}`);

  // Exit conditions
  exit.push(`Take profit at +${genes.profitTargetPct.toFixed(1)}%`);
  exit.push(`Stop loss at ${genes.stopLossPct.toFixed(1)}%`);
  exit.push(`Exit if |delta| < ${genes.deltaExit.toFixed(2)}`);
  exit.push(`Exit if gamma > ${genes.gammaExit.toFixed(3)}`);
  exit.push(`Max hold time: ${genes.maxHoldMinutes} minutes`);

  // Risk management
  risk.push(`Position size: ${genes.positionSizePct.toFixed(1)}% per trade`);
  risk.push(`Max ${genes.maxConcurrentTrades} concurrent positions`);
  risk.push(`Max ${genes.maxTradesPerSymbol} trades per symbol`);
  risk.push(`Min hold time: ${genes.minHoldMinutes} minutes`);

  return {
    entryConditions: entry,
    exitConditions: exit,
    riskManagement: risk,
  };
}

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  const supabase = getSupabaseClient();

  try {
    // GET: Fetch active GA parameters for a symbol
    if (req.method === "GET") {
      const url = new URL(req.url);
      const symbol = url.searchParams.get("symbol")?.trim().toUpperCase();

      if (!symbol) {
        return errorResponse("Missing required parameter: symbol", 400);
      }

      // Query active GA parameters
      const { data, error } = await supabase
        .from("ga_strategy_params")
        .select("*")
        .eq("symbol", symbol)
        .eq("is_active", true)
        .order("created_at", { ascending: false })
        .limit(1);

      if (error) {
        console.error("[GA Strategy] Database error:", error);
        return errorResponse("Failed to fetch GA strategy", 500);
      }

      if (!data || data.length === 0) {
        // No strategy found - return default
        const defaultGenes: StrategyGenes = {
          minCompositeRank: 70,
          minMomentumScore: 0.5,
          minValueScore: 0.4,
          signalFilter: "buy",
          entryHourMin: 10,
          entryHourMax: 14,
          minBarAgeMinutes: 15,
          deltaExit: 0.3,
          gammaExit: 0.05,
          vegaExit: 0.05,
          thetaMin: -0.2,
          ivRankMin: 20,
          ivRankMax: 75,
          minHoldMinutes: 15,
          maxHoldMinutes: 240,
          profitTargetPct: 15,
          stopLossPct: -8,
          positionSizePct: 3,
          maxConcurrentTrades: 3,
          minTradesPerDay: 2,
          maxTradesPerSymbol: 4,
        };

        const response: GAStrategyResponse = {
          symbol,
          hasStrategy: false,
          strategy: {
            id: "default",
            genes: defaultGenes,
            fitness: {
              totalPnl: 0,
              pnlPct: 0,
              winRate: 0.5,
              profitFactor: 1,
              sharpeRatio: 0,
              maxDrawdown: 0,
              numTrades: 0,
              avgTradeDuration: 0,
              tradesClosed: 0,
            },
            createdAt: new Date().toISOString(),
            trainingDays: 0,
            trainingSamples: 0,
            generationsRun: 0,
          },
          recommendation: generateRecommendations(defaultGenes),
        };

        return jsonResponse(response);
      }

      // Parse stored genes and fitness
      const row = data[0];
      const genes = snakeToCamel(row.genes || {}) as unknown as StrategyGenes;
      const fitness = snakeToCamel(
        row.fitness || {},
      ) as unknown as StrategyFitness;

      const response: GAStrategyResponse = {
        symbol,
        hasStrategy: true,
        strategy: {
          id: row.id,
          genes,
          fitness,
          createdAt: row.created_at,
          trainingDays: row.training_days || 30,
          trainingSamples: row.training_samples || 0,
          generationsRun: row.generations_run || 0,
        },
        recommendation: generateRecommendations(genes),
      };

      console.log(`[GA Strategy] Returned strategy for ${symbol}`);
      return jsonResponse(response);
    }

    // POST: Trigger GA optimization run
    if (req.method === "POST") {
      const body = await req.json();
      const symbol = body.symbol?.trim().toUpperCase();
      const generations = body.generations || 50;
      const populationSize = body.populationSize || 100;
      const trainingDays = body.trainingDays || 30;

      if (!symbol) {
        return errorResponse("Missing required field: symbol", 400);
      }

      // Create optimization run record
      const { data: runData, error: runError } = await supabase
        .from("ga_optimization_runs")
        .insert({
          symbol,
          generations,
          population_size: populationSize,
          training_days: trainingDays,
          status: "queued",
        })
        .select()
        .single();

      if (runError) {
        console.error("[GA Strategy] Failed to create run:", runError);
        return errorResponse("Failed to queue optimization", 500);
      }

      // Estimate completion time (roughly 1 min per 10 generations)
      const estimatedMinutes = Math.ceil(generations / 10) + 2;

      const response: TriggerOptimizationResponse = {
        success: true,
        message: `GA optimization queued for ${symbol}`,
        runId: runData.id,
        estimatedMinutes,
      };

      console.log(
        `[GA Strategy] Queued optimization for ${symbol}: ${runData.id}`,
      );
      return jsonResponse(response);
    }

    return errorResponse("Method not allowed", 405);
  } catch (err) {
    console.error("[GA Strategy] Unexpected error:", err);
    return errorResponse(
      `Internal server error: ${
        err instanceof Error ? err.message : String(err)
      }`,
      500,
    );
  }
});
