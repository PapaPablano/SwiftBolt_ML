// SPEC-8: On-demand backfill trigger
// Checks coverage and creates/returns backfill job if needed

import { createClient } from "jsr:@supabase/supabase-js@2";
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { corsHeaders } from "../_shared/cors.ts";

interface RequestBody {
  symbol: string;
  timeframe: string;
  fromTs: string;
  toTs: string;
}

interface ResponseBody {
  hasCoverage: boolean;
  jobId?: string;
  coverageFrom?: string | null;
  coverageTo?: string | null;
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const body = (await req.json()) as RequestBody;
    const { symbol, timeframe, fromTs, toTs } = body;

    console.log(`[EnsureCoverage] Request for ${symbol} ${timeframe} from ${fromTs} to ${toTs}`);

    // 1) Check existing coverage
    const { data: cov, error: covErr } = await supabase.rpc("get_coverage", {
      p_symbol: symbol,
      p_timeframe: timeframe,
    });

    if (covErr) {
      console.error("[EnsureCoverage] Coverage check error:", covErr);
      return new Response(JSON.stringify({ error: covErr.message }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Check if we have full coverage
    const hasCoverage =
      cov &&
      cov.from_ts &&
      cov.to_ts &&
      new Date(cov.from_ts) <= new Date(fromTs) &&
      new Date(cov.to_ts) >= new Date(toTs);

    if (hasCoverage) {
      console.log(`[EnsureCoverage] Full coverage exists for ${symbol} ${timeframe}`);
      const response: ResponseBody = {
        hasCoverage: true,
        coverageFrom: cov.from_ts,
        coverageTo: cov.to_ts,
      };
      return new Response(JSON.stringify(response), {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // 2) Create or fetch job (idempotent via unique constraint)
    const { data: job, error: jobErr } = await supabase
      .from("backfill_jobs")
      .upsert(
        {
          symbol,
          timeframe,
          from_ts: fromTs,
          to_ts: toTs,
          status: "pending",
        },
        { onConflict: "symbol,timeframe,from_ts,to_ts" }
      )
      .select()
      .single();

    if (jobErr) {
      console.error("[EnsureCoverage] Job creation error:", jobErr);
      return new Response(JSON.stringify({ error: jobErr.message }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    console.log(`[EnsureCoverage] Job created/fetched: ${job.id}`);

    // 3) Seed chunks by day
    const days = enumerateDays(fromTs, toTs);
    const chunkRows = days.map((d) => ({
      job_id: job.id,
      symbol,
      timeframe,
      day: d,
    }));

    const { error: seedErr } = await supabase
      .from("backfill_chunks")
      .upsert(chunkRows, { onConflict: "job_id,day" });

    if (seedErr) {
      console.error("[EnsureCoverage] Chunk seeding error:", seedErr);
      return new Response(JSON.stringify({ error: seedErr.message }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    console.log(`[EnsureCoverage] Seeded ${days.length} chunks for job ${job.id}`);

    const response: ResponseBody = {
      hasCoverage: false,
      jobId: job.id,
      coverageFrom: cov?.from_ts ?? null,
      coverageTo: cov?.to_ts ?? null,
    };

    return new Response(JSON.stringify(response), {
      status: 202,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("[EnsureCoverage] Unexpected error:", error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : String(error) }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});

function enumerateDays(fromIso: string, toIso: string): string[] {
  const out: string[] = [];
  const start = new Date(fromIso);
  const end = new Date(toIso);
  const d = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate()));

  while (d <= end) {
    out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 1);
  }

  return out;
}
