// Test function to verify schema exists
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Check if tables exist
    const { data: tables, error: tablesError } = await supabase
      .rpc('exec_sql', {
        query: `
          select table_name, table_type 
          from information_schema.tables 
          where table_schema = 'public' 
            and table_name in ('job_definitions', 'job_runs', 'coverage_status', 'ohlc_bars_v2')
          order by table_name
        `
      });

    if (tablesError) {
      // Try direct query instead
      const { data: jobDefs, error: jobDefsError } = await supabase
        .from("job_definitions")
        .select("count");

      return new Response(
        JSON.stringify({
          rpc_error: tablesError.message,
          direct_query_error: jobDefsError?.message,
          direct_query_data: jobDefs,
          message: "Testing table access"
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    return new Response(
      JSON.stringify({
        tables,
        count: tables?.length || 0,
        message: "Schema check complete"
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
