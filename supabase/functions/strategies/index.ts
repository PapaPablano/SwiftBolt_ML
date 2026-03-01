// Strategy API: CRUD operations for strategies
// GET /strategies - List all strategies for user
// GET /strategies?id=xxx - Get single strategy
// POST /strategies - Create new strategy
// PUT /strategies - Update strategy
// DELETE /strategies?id=xxx - Delete strategy

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface StrategyConfig {
  entry_conditions: Condition[];
  exit_conditions: Condition[];
  filters: Condition[];
  parameters: Record<string, unknown>;
}

interface Condition {
  type: string;
  name: string;
  operator?: string;
  value?: number | string;
  params?: Record<string, unknown>;
}

interface StrategyRow {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  config: StrategyConfig;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  const supabase = getSupabaseClient();

  const authHeader = req.headers.get("Authorization") ?? "";
  const { data: { user }, error: authError } = await supabase.auth.getUser(
    authHeader.replace("Bearer ", ""),
  );
  if (authError || !user) {
    return new Response(JSON.stringify({ error: "Authentication required" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }
  const userId = user.id;

  const url = new URL(req.url);
  const strategyId = url.searchParams.get("id");
  const action = url.searchParams.get("action");

  try {
    switch (req.method) {
      case "GET":
        return await handleGet(supabase, userId, strategyId, url);

      case "POST":
        if (action === "duplicate") {
          return await handleDuplicate(supabase, userId, req);
        }
        return await handleCreate(supabase, userId, req);

      case "PUT":
        return await handleUpdate(supabase, userId, req, strategyId);

      case "DELETE":
        return await handleDelete(supabase, userId, strategyId);

      default:
        return errorResponse("Method not allowed", 405);
    }
  } catch (err) {
    console.error("[strategies] Unexpected error:", err);
    return errorResponse("An internal error occurred", 500);
  }
});

async function handleGet(supabase: ReturnType<typeof getSupabaseClient>, userId: string, id: string | null, url: URL) {
  if (id) {
    const { data, error } = await supabase
      .from("strategy_user_strategies")
      .select("*")
      .eq("id", id)
      .eq("user_id", userId)
      .single();

    if (error || !data) {
      return errorResponse("Strategy not found", 404);
    }
    return jsonResponse({ strategy: data });
  }

  // List strategies with pagination (excludes large config JSONB)
  const offset = parseInt(url.searchParams.get("offset") ?? "0", 10) || 0;
  const { data, error } = await supabase
    .from("strategy_user_strategies")
    .select("id, name, is_active, paper_trading_enabled, created_at, updated_at")
    .eq("user_id", userId)
    .order("updated_at", { ascending: false })
    .range(offset, offset + 49)
    .limit(50);

  if (error) {
    console.error("[strategies] DB error listing strategies:", error);
    return errorResponse("An internal error occurred", 500);
  }

  return jsonResponse({ strategies: data || [] });
}

async function handleCreate(supabase: ReturnType<typeof getSupabaseClient>, userId: string, req: Request) {
  const body = await req.json();
  
  if (!body.name) {
    return errorResponse("Strategy name is required");
  }
  
  const strategy = {
    user_id: userId,
    name: body.name,
    description: body.description || null,
    config: body.config || {
      entry_conditions: [],
      exit_conditions: [],
      filters: [],
      parameters: {}
    },
    is_active: body.is_active ?? true
  };
  
  const { data, error } = await supabase
    .from("strategy_user_strategies")
    .insert(strategy)
    .select()
    .single();

  if (error) {
    console.error("[strategies] DB error creating strategy:", error);
    return errorResponse("An internal error occurred", 500);
  }

  return jsonResponse({ strategy: data }, 201);
}

async function handleUpdate(supabase: ReturnType<typeof getSupabaseClient>, userId: string, req: Request, id: string | null) {
  if (!id) {
    return errorResponse("Strategy ID is required");
  }
  
  const body = await req.json();
  
  const updates: Record<string, unknown> = {};
  if (body.name !== undefined) updates.name = body.name;
  if (body.description !== undefined) updates.description = body.description;
  if (body.config !== undefined) updates.config = body.config;
  if (body.is_active !== undefined) updates.is_active = body.is_active;
  if (body.paper_trading_enabled !== undefined) updates.paper_trading_enabled = body.paper_trading_enabled;
  
  const { data, error } = await supabase
    .from("strategy_user_strategies")
    .update(updates)
    .eq("id", id)
    .eq("user_id", userId)
    .select()
    .single();

  if (error) {
    console.error("[strategies] DB error updating strategy:", error);
    return errorResponse("An internal error occurred", 500);
  }

  if (!data) {
    return errorResponse("Strategy not found", 404);
  }

  return jsonResponse({ strategy: data });
}

async function handleDelete(supabase: ReturnType<typeof getSupabaseClient>, userId: string, id: string | null) {
  if (!id) {
    return errorResponse("Strategy ID is required");
  }
  
  const { error } = await supabase
    .from("strategy_user_strategies")
    .delete()
    .eq("id", id)
    .eq("user_id", userId);

  if (error) {
    console.error("[strategies] DB error deleting strategy:", error);
    return errorResponse("An internal error occurred", 500);
  }

  return jsonResponse({ message: "Strategy deleted" });
}

async function handleDuplicate(supabase: ReturnType<typeof getSupabaseClient>, userId: string, req: Request) {
  const body = await req.json();
  const sourceId = body.source_id;
  
  if (!sourceId) {
    return errorResponse("Source strategy ID is required");
  }
  
  // Get source strategy
  const { data: source, error: fetchError } = await supabase
    .from("strategy_user_strategies")
    .select("*")
    .eq("id", sourceId)
    .eq("user_id", userId)
    .single();
  
  if (fetchError || !source) {
    return errorResponse("Source strategy not found", 404);
  }
  
  // Create duplicate
  const { data, error } = await supabase
    .from("strategy_user_strategies")
    .insert({
      user_id: userId,
      name: `${source.name} (Copy)`,
      description: source.description,
      config: source.config,
      is_active: false,
    })
    .select()
    .single();

  if (error) {
    console.error("[strategies] DB error duplicating strategy:", error);
    return errorResponse("An internal error occurred", 500);
  }

  return jsonResponse({ strategy: data }, 201);
}
