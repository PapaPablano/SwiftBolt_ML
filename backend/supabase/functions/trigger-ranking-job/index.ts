// trigger-ranking-job: Queue an ML ranking job for a symbol
// POST /trigger-ranking-job
// Body: { "symbol": "AAPL", "priority": 0 }
//
// This function adds a ranking job to the database queue.
// A worker process (Python script or separate service) polls the queue
// and processes jobs asynchronously.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface TriggerRankingRequest {
  symbol: string;
  priority?: number; // Optional: higher priority jobs processed first
}

interface TriggerRankingResponse {
  message: string;
  symbol: string;
  jobId: string;
  estimatedCompletionSeconds: number;
  queuePosition?: number;
}

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow POST requests
  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    // Parse request body
    const body: TriggerRankingRequest = await req.json();
    const { symbol, priority = 0 } = body;

    if (!symbol || typeof symbol !== "string") {
      return errorResponse("Missing or invalid 'symbol' field in request body", 400);
    }

    const upperSymbol = symbol.toUpperCase().trim();

    console.log(`[Trigger Ranking Job] Received request for symbol: ${upperSymbol} (priority: ${priority})`);

    const supabase = getSupabaseClient();

    // Resolve symbol_id (options backfill queue uses symbol_id)
    const { data: symbolRow, error: symbolError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", upperSymbol)
      .single();

    if (symbolError || !symbolRow) {
      return errorResponse(`Symbol not found: ${upperSymbol}`, 404);
    }

    const symbolId = symbolRow.id;

    // Check if there's already a pending/processing options backfill job
    const { data: existingJobs, error: checkError } = await supabase
      .from("options_backfill_jobs")
      .select("id, status, created_at")
      .eq("symbol_id", symbolId)
      .in("status", ["pending", "processing"])
      .order("created_at", { ascending: false })
      .limit(1);

    if (checkError) {
      console.error("[Trigger Ranking Job] Error checking existing jobs:", checkError);
      return errorResponse(`Database error: ${checkError.message}`, 500);
    }

    if (existingJobs && existingJobs.length > 0) {
      const existingJob = existingJobs[0];
      return jsonResponse({
        message: `Options backfill job for ${upperSymbol} is already ${existingJob.status}`,
        symbol: upperSymbol,
        jobId: existingJob.id,
        estimatedCompletionSeconds: 30,
      });
    }

    // Insert new job into options backfill queue
    const { data: newJob, error: insertError } = await supabase
      .from("options_backfill_jobs")
      .insert({
        symbol_id: symbolId,
        ticker: upperSymbol,
        status: "pending",
      })
      .select("id, created_at")
      .single();

    if (insertError || !newJob) {
      console.error("[Trigger Ranking Job] Error inserting job:", insertError);
      return errorResponse(
        `Failed to create job: ${insertError?.message || "Unknown error"}`,
        500
      );
    }

    // Count pending jobs ahead in queue (best-effort estimate)
    const { count: queuePosition } = await supabase
      .from("options_backfill_jobs")
      .select("id", { count: "exact", head: true })
      .eq("status", "pending")
      .lt("created_at", newJob.created_at);

    const response: TriggerRankingResponse = {
      message: `Options backfill job queued for ${upperSymbol}`,
      symbol: upperSymbol,
      jobId: newJob.id,
      estimatedCompletionSeconds: 30 + (queuePosition || 0) * 10,
      queuePosition: queuePosition || 0,
    };

    console.log(
      `[Trigger Ranking Job] Options job queued: ${newJob.id}, position: ${queuePosition || 0}`
    );
    return jsonResponse(response);
  } catch (err) {
    console.error("[Trigger Ranking Job] Unexpected error:", err);
    return errorResponse(
      `Internal server error: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
