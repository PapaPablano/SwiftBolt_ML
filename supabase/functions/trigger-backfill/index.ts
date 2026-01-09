// Simple trigger endpoint for backfill worker
// Call this from an external cron service (GitHub Actions, cron-job.org, etc.)
// No authentication required since it just triggers the worker

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    console.log("[TriggerBackfill] Calling run-backfill-worker...");

    // Call the backfill worker
    const response = await fetch(`${supabaseUrl}/functions/v1/run-backfill-worker`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${supabaseServiceKey}`,
      },
      body: "{}",
    });

    const result = await response.json();

    console.log("[TriggerBackfill] Worker response:", result);

    return new Response(
      JSON.stringify({
        success: response.ok,
        worker_response: result,
        timestamp: new Date().toISOString(),
      }),
      {
        status: response.ok ? 200 : 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("[TriggerBackfill] Error:", error);
    return new Response(
      JSON.stringify({
        success: false,
        error: error instanceof Error ? error.message : String(error),
        timestamp: new Date().toISOString(),
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
