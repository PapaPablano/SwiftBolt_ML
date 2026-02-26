import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { corsHeaders } from "../_shared/cors.ts";

serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Fetch all public templates and system templates
    const { data: templates, error } = await supabase
      .from("options_strategy_templates")
      .select("*")
      .or("is_public.eq.true,is_system_template.eq.true")
      .order("strategy_type", { ascending: true })
      .order("name", { ascending: true });

    if (error) {
      console.error("Error fetching templates:", error);
      return new Response(
        JSON.stringify({ error: "Failed to fetch templates" }),
        {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    // Transform snake_case to camelCase for API response
    const transformedTemplates = templates.map((t) => ({
      id: t.id,
      name: t.name,
      strategyType: t.strategy_type,
      legConfig: t.leg_config,
      typicalMaxRisk: t.typical_max_risk,
      typicalMaxReward: t.typical_max_reward,
      typicalCostPct: t.typical_cost_pct,
      description: t.description,
      bestFor: t.best_for,
      marketCondition: t.market_condition,
      createdBy: t.created_by,
      createdAt: t.created_at,
      updatedAt: t.updated_at,
      isSystemTemplate: t.is_system_template,
      isPublic: t.is_public,
    }));

    return new Response(
      JSON.stringify({ templates: transformedTemplates }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  } catch (error) {
    console.error("Unexpected error:", error);
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
});
