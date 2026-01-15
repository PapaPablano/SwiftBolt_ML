// Batch Bars Fetcher - Phase 2 Optimization
// Fetches OHLC bars for multiple symbols in a single API call
// 50x more efficient than individual symbol requests

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";

type AlpacaBar = {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
};

type AlpacaBarsResponse = {
  bars?: Record<string, AlpacaBar[]>;
};

type NormalizedBar = {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

interface BatchFetchRequest {
  job_run_ids: string[]; // Array of job run IDs (one per symbol)
  symbols: string[];      // Array of symbols to fetch
  timeframe: string;
  from: string;
  to: string;
}

interface BatchFetchResponse {
  total_symbols: number;
  total_bars: number;
  symbols_processed: string[];
  duration_ms: number;
  api_calls: number; // Should be 1 for batch vs symbols.length for individual
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  try {
    return JSON.stringify(error);
  } catch {
    return "Unknown error";
  }
}

const TIMEFRAME_MAP: Record<string, string> = {
  "15m": "m15",
  "1h": "h1",
  "4h": "h4",
  "d1": "d1",
  "w1": "w1",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const startTime = Date.now();

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const alpacaApiKey = Deno.env.get("ALPACA_API_KEY")!;
    const alpacaApiSecret = Deno.env.get("ALPACA_API_SECRET")!;

    const supabase = createClient(supabaseUrl, supabaseKey);

    // Parse request
    const request: BatchFetchRequest = await req.json();
    const { job_run_ids, symbols, timeframe, from, to } = request;

    console.log(`[fetch-bars-batch] Starting batch: ${symbols.length} symbols, ${timeframe}`);

    // Validate
    if (!symbols || symbols.length === 0) {
      throw new Error("No symbols provided");
    }

    if (symbols.length > 50) {
      throw new Error("Maximum 50 symbols per batch");
    }

    if (job_run_ids.length !== symbols.length) {
      throw new Error("job_run_ids and symbols arrays must have same length");
    }

    // Update all job statuses to running
    for (const jobId of job_run_ids) {
      await supabase
        .from("job_runs")
        .update({
          status: "running",
          started_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .eq("id", jobId);
    }

    // Map timeframe to Alpaca format
    const timeframeMap: Record<string, string> = {
      m1: "1Min",
      m5: "5Min",
      m15: "15Min",
      m30: "30Min",
      h1: "1Hour",
      h4: "4Hour",
      d1: "1Day",
      w1: "1Week",
    };

    const providerTimeframe = TIMEFRAME_MAP[timeframe] || timeframe;
    const alpacaTimeframe = timeframeMap[providerTimeframe] || "1Day";

    // Fetch bars for all symbols in ONE API call using Alpaca batch endpoint
    const fromDate = new Date(from);
    const toDate = new Date(to);
    const symbolsParam = symbols.join(",");

    const alpacaFeed = (Deno.env.get("ALPACA_DATA_FEED") ?? "iex").toLowerCase() === "sip"
      ? "sip"
      : "iex";

    const url = `https://data.alpaca.markets/v2/stocks/bars?` +
      `symbols=${symbolsParam}&` +
      `timeframe=${alpacaTimeframe}&` +
      `start=${fromDate.toISOString()}&` +
      `end=${toDate.toISOString()}&` +
      `limit=10000&` +
      `adjustment=raw&` +
      `feed=${alpacaFeed}&` +
      `sort=asc`;

    console.log(`[fetch-bars-batch] Calling Alpaca API: ${symbols.length} symbols`);

    const response = await fetch(url, {
      headers: {
        "APCA-API-KEY-ID": alpacaApiKey,
        "APCA-API-SECRET-KEY": alpacaApiSecret,
        "Accept": "application/json",
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Alpaca API error (${response.status}): ${errorText}`);
    }

    const data = (await response.json()) as AlpacaBarsResponse;
    const barsMap = new Map<string, NormalizedBar[]>();

    for (const symbol of symbols) {
      const alpacaBars = data.bars?.[symbol] ?? [];
      const bars = alpacaBars.map((bar) => ({
        timestamp: Math.floor(new Date(bar.t).getTime() / 1000),
        open: bar.o,
        high: bar.h,
        low: bar.l,
        close: bar.c,
        volume: bar.v,
      }));
      barsMap.set(symbol, bars);
    }

    console.log(`[fetch-bars-batch] Received data for ${barsMap.size} symbols`);

    // Process each symbol's bars
    let totalBars = 0;
    const symbolsProcessed: string[] = [];

    for (let i = 0; i < symbols.length; i++) {
      const symbol = symbols[i];
      const jobId = job_run_ids[i];
      const bars = barsMap.get(symbol) || [];

      console.log(`[fetch-bars-batch] Processing ${symbol}: ${bars.length} bars`);

      try {
        // Get symbol_id
        const { data: symbolData, error: symbolError } = await supabase
          .from("symbols")
          .select("id")
          .eq("ticker", symbol)
          .single();

        if (symbolError || !symbolData) {
          console.warn(`[fetch-bars-batch] Symbol not found: ${symbol}`);
          await supabase
            .from("job_runs")
            .update({
              status: "failed",
              error_message: `Symbol not found: ${symbol}`,
              finished_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            })
            .eq("id", jobId);
          continue;
        }

        const symbol_id = symbolData.id;

        // Prepare bars for insertion
        if (bars.length > 0) {
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          const todayStr = today.toISOString().split('T')[0];

          const barsToInsert = bars
            .filter((bar) => {
              const year = new Date(bar.timestamp * 1000).getFullYear();
              return year >= 1970 && year <= 2100;
            })
            .map((bar) => {
              const barDate = new Date(bar.timestamp * 1000);
              const barDateStr = barDate.toISOString().split('T')[0];
              // is_intraday = true ONLY if bar is for TODAY AND timeframe is intraday
              const isToday = barDateStr === todayStr;
              const isIntradayTimeframe = ["m15", "h1", "h4"].includes(providerTimeframe);

              return {
                symbol_id,
                timeframe: providerTimeframe,
                ts: barDate.toISOString(),
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close,
                volume: bar.volume,
                provider: "alpaca",
                // Only mark as intraday if it's today's data AND intraday timeframe
                is_intraday: isToday && isIntradayTimeframe,
                is_forecast: false,
              };
            });

          const dedupedBarsToInsert = (() => {
            const map = new Map<string, typeof barsToInsert[number]>();
            for (const row of barsToInsert) {
              const key = `${row.symbol_id}|${row.timeframe}|${row.ts}|${row.provider}|${row.is_forecast}`;
              map.set(key, row);
            }
            return Array.from(map.values());
          })();

          // Batch upsert
          const batchSize = 1000;
          let rowsWritten = 0;

          for (let j = 0; j < dedupedBarsToInsert.length; j += batchSize) {
            const batch = dedupedBarsToInsert.slice(j, j + batchSize);

            const { error: upsertError } = await supabase
              .from("ohlc_bars_v2")
              .upsert(batch, {
                onConflict: "symbol_id,timeframe,ts,provider,is_forecast",
                ignoreDuplicates: false,
              });

            if (upsertError) {
              console.error(`[fetch-bars-batch] Upsert error for ${symbol}:`, upsertError);
              throw upsertError;
            }

            rowsWritten += batch.length;
          }

          totalBars += rowsWritten;

          // Update job status to success
          await supabase
            .from("job_runs")
            .update({
              status: "success",
              rows_written: rowsWritten,
              provider: "alpaca",
              progress_percent: 100,
              actual_cost: 1 / symbols.length, // Share the cost across all symbols
              finished_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            })
            .eq("id", jobId);

          symbolsProcessed.push(symbol);
        } else {
          // No data returned
          await supabase
            .from("job_runs")
            .update({
              status: "success",
              rows_written: 0,
              provider: "alpaca",
              progress_percent: 100,
              actual_cost: 1 / symbols.length,
              finished_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            })
            .eq("id", jobId);
        }
      } catch (error) {
        const errorMessage = getErrorMessage(error);
        console.error(`[fetch-bars-batch] Error processing ${symbol}:`, errorMessage);
        await supabase
          .from("job_runs")
          .update({
            status: "failed",
            error_message: errorMessage,
            finished_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          })
          .eq("id", jobId);
      }
    }

    const duration = Date.now() - startTime;
    const batchResponse: BatchFetchResponse = {
      total_symbols: symbols.length,
      total_bars: totalBars,
      symbols_processed: symbolsProcessed,
      duration_ms: duration,
      api_calls: 1, // Only 1 API call for all symbols!
    };

    console.log(`[fetch-bars-batch] Batch complete:`, batchResponse);
    console.log(`[fetch-bars-batch] Efficiency: 1 API call for ${symbols.length} symbols (${symbols.length}x savings!)`);

    return new Response(
      JSON.stringify(batchResponse),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    const errorMessage = getErrorMessage(error);
    console.error("[fetch-bars-batch] Error:", errorMessage);

    const duration = Date.now() - startTime;

    return new Response(
      JSON.stringify({
        error: errorMessage,
        duration_ms: duration,
      }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
