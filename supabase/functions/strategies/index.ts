// Strategy API: CRUD operations for strategies
// GET /strategies - List all strategies for user
// GET /strategies?id=xxx - Get single strategy
// POST /strategies - Create new strategy
// PUT /strategies - Update strategy
// DELETE /strategies?id=xxx - Delete strategy

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient, getSupabaseClientWithAuth } from "../_shared/supabase-client.ts";

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

function getUserIdFromRequest(req: Request): string | null {
  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return null;
  
  const token = authHeader.replace("Bearer ", "");
  // Decode JWT manually to get user_id (avoids async auth call)
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload.sub || null;
  } catch {
    return null;
  }
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  const supabase = getSupabaseClient();
  let userId = getUserIdFromRequest(req);
  
  // Demo mode: use a test user ID if no auth provided
  if (!userId) {
    userId = "00000000-0000-0000-0000-000000000001";
  }

  const url = new URL(req.url);
  const strategyId = url.searchParams.get("id");
  const action = url.searchParams.get("action");

  try {
    switch (req.method) {
      case "GET":
        return await handleGet(supabase, userId, strategyId);
      
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
    console.error("Strategy API error:", err);
    return errorResponse(err instanceof Error ? err.message : "Internal error", 500);
  }
});

async function handleGet(supabase: ReturnType<typeof getSupabaseClient>, userId: string, id: string | null) {
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
  
  // List all strategies
  const { data, error } = await supabase
    .from("strategy_user_strategies")
    .select("*")
    .eq("user_id", userId)
    .order("updated_at", { ascending: false });
  
  if (error) {
    return errorResponse(error.message);
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
    return errorResponse(error.message);
  }
  
  return jsonResponse({ strategy: data }, 201);
}

async function handleUpdate(supabase: ReturnType<typeof getSupabaseClient>, userId: string, req: Request, id: string | null) {
  if (!id) {
    return errorResponse("Strategy ID is required");
  }
  
  const body = await req.json();
  
  const updates: Partial<StrategyRow> = {};
  if (body.name !== undefined) updates.name = body.name;
  if (body.description !== undefined) updates.description = body.description;
  if (body.config !== undefined) updates.config = body.config;
  if (body.is_active !== undefined) updates.is_active = body.is_active;
  
  const { data, error } = await supabase
    .from("strategy_user_strategies")
    .update(updates)
    .eq("id", id)
    .eq("user_id", userId)
    .select()
    .single();
  
  if (error) {
    return errorResponse(error.message);
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
    return errorResponse(error.message);
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
      is_active: false
    })
    .select()
    .single();
  
  if (error) {
    return errorResponse(error.message);
  }
  
  return jsonResponse({ strategy: data }, 201);
}
