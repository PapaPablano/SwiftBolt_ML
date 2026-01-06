// SPEC-8: Scheduled backfill worker
// Processes pending chunks in parallel with provider throttling

import { createClient } from "jsr:@supabase/supabase-js@2";
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { fetchIntradayForDay, type BackfillBar } from "../_shared/backfill-adapter.ts";

interface BackfillChunk {
  id: string;
  job_id: string;
  symbol: string;
  timeframe: string;
  day: string;
  status: string;
  try_count: number;
}

serve(async () => {
  const startTime = Date.now();
  console.log("[BackfillWorker] Starting worker run");

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // 1) Claim a batch of pending chunks (bounded parallelism)
    const { data: chunks, error: claimErr } = await supabase.rpc("claim_backfill_chunks", {
      p_limit: 4,
    });

    if (claimErr) {
      console.error("[BackfillWorker] Claim error:", claimErr);
      return new Response(JSON.stringify({ error: claimErr.message }), { status: 500 });
    }

    if (!chunks || chunks.length === 0) {
      console.log("[BackfillWorker] No work available");
      return new Response(JSON.stringify({ message: "no work", processed: 0 }), { status: 200 });
    }

    console.log(`[BackfillWorker] Claimed ${chunks.length} chunks`);

    // 2) Process chunks in parallel
    const results = await Promise.allSettled(
      chunks.map((chunk: BackfillChunk) => processChunk(supabase, chunk))
    );

    // 3) Count successes and failures
    const succeeded = results.filter((r) => r.status === "fulfilled").length;
    const failed = results.filter((r) => r.status === "rejected").length;

    console.log(`[BackfillWorker] Processed ${succeeded} succeeded, ${failed} failed`);

    // 4) Update job progress for all affected jobs
    await supabase.rpc("update_job_progress");

    const elapsed = Date.now() - startTime;
    console.log(`[BackfillWorker] Completed in ${elapsed}ms`);

    return new Response(
      JSON.stringify({
        message: "ok",
        processed: chunks.length,
        succeeded,
        failed,
        elapsed,
      }),
      { status: 200 }
    );
  } catch (error) {
    console.error("[BackfillWorker] Unexpected error:", error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : String(error) }),
      { status: 500 }
    );
  }
});

async function processChunk(supabase: any, chunk: BackfillChunk): Promise<void> {
  const { id, symbol, timeframe, day, try_count } = chunk;

  console.log(`[BackfillWorker] Processing chunk ${id}: ${symbol} ${timeframe} ${day}`);

  try {
    // Fetch bars for this day
    const bars = await fetchIntradayForDay({ symbol, timeframe, day });

    if (bars.length === 0) {
      console.warn(`[BackfillWorker] No bars returned for ${symbol} ${timeframe} ${day}`);
    }

    // Upsert bars to database (batched for large datasets)
    await upsertBars(supabase, bars);

    // Mark chunk as done
    await supabase.from("backfill_chunks").update({ status: "done" }).eq("id", id);

    console.log(`[BackfillWorker] Chunk ${id} completed: ${bars.length} bars`);
  } catch (error) {
    console.error(`[BackfillWorker] Chunk ${id} failed:`, error);

    // Determine if we should retry or mark as error
    const newStatus = try_count >= 2 ? "error" : "pending";
    const errorMsg = error instanceof Error ? error.message : String(error);

    await supabase
      .from("backfill_chunks")
      .update({
        status: newStatus,
        try_count: try_count + 1,
        last_error: errorMsg.slice(0, 500),
      })
      .eq("id", id);

    throw error;
  }
}

async function upsertBars(supabase: any, bars: BackfillBar[]): Promise<void> {
  if (!bars || bars.length === 0) return;

  // Batch in 1000-row chunks to avoid payload limits
  const batchSize = 1000;
  for (let i = 0; i < bars.length; i += batchSize) {
    const slice = bars.slice(i, i + batchSize);

    const { error } = await supabase.from("ohlc_bars_v2").upsert(slice, {
      onConflict: "symbol,timeframe,ts",
    });

    if (error) {
      console.error(`[BackfillWorker] Upsert error (batch ${i / batchSize}):`, error);
      throw error;
    }
  }

  console.log(`[BackfillWorker] Upserted ${bars.length} bars`);
}
