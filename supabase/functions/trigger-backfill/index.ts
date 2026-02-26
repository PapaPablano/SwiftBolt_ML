// Simple trigger endpoint for backfill worker
// Call this from an external cron service (GitHub Actions, cron-job.org, etc.)
// No authentication required since it just triggers the worker

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const gatewayKey = Deno.env.get("SB_GATEWAY_KEY") ??
      Deno.env.get("ANON_KEY") ??
      Deno.env.get("SUPABASE_ANON_KEY") ??
      supabaseServiceKey;

    const expectedCallerKey = Deno.env.get("SB_GATEWAY_KEY") ?? gatewayKey;
    const authHeader = req.headers.get("authorization");
    const apikeyHeader = req.headers.get("apikey");
    const bearer = authHeader?.toLowerCase().startsWith("bearer ")
      ? authHeader.slice("bearer ".length)
      : null;

    if (apikeyHeader !== expectedCallerKey && bearer !== expectedCallerKey) {
      return new Response(
        JSON.stringify({ success: false, error: "Unauthorized" }),
        {
          status: 401,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    console.log("[TriggerBackfill] Calling run-backfill-worker...");

    // Call the backfill worker (verify_jwt=false; auth via X-SB-Gateway-Key)
    const response = await fetch(
      `${supabaseUrl}/functions/v1/run-backfill-worker`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${gatewayKey}`,
          "apikey": gatewayKey,
          "X-SB-Gateway-Key": gatewayKey,
        },
        body: "{}",
      },
    );

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
      },
    );
  } catch (error: unknown) {
    console.error("[TriggerBackfill] Error:", error);
    const message = error instanceof Error ? error.message : String(error);
    return new Response(
      JSON.stringify({
        success: false,
        error: message,
        timestamp: new Date().toISOString(),
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
});
