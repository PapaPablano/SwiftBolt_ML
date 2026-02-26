import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const TRADESTATION_BASE_URL = "https://api.tradestation.com/v3";
const TRADESTATION_SIM_URL = "https://sim-api.tradestation.com/v3";

interface TradeStationCredential {
  access_token: string;
  refresh_token: string;
  token_expires_at: string;
}

interface StrategyCondition {
  id: string;
  indicator_id: string;
  threshold: number;
  operator: string;
  logical_operator: string;
  position: number;
  indicators?: {
    name: string;
    parameters: Record<string, unknown>;
  };
}

interface TradingAction {
  id: string;
  action_type: string;
  parameters: Record<string, unknown>;
  priority: number;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, supabaseKey);

  try {
    // Auth check
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return new Response(JSON.stringify({ error: "Missing authorization" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { data: { user }, error: authError } = await supabase.auth.getUser(
      authHeader.replace("Bearer ", ""),
    );
    if (authError || !user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const url = new URL(req.url);
    const path = url.pathname.replace("/ts-strategies", "");
    const method = req.method;

    // Route handling
    if (path === "" || path === "/") {
      return handleStrategies(req, supabase, user.id, method);
    } else if (path === "/execute") {
      return handleExecute(req, supabase, user.id);
    } else if (path === "/auth") {
      return handleAuth(req, supabase, user.id);
    } else if (path.match(/^\/[\w-]+$/)) {
      const strategyId = path.slice(1);
      return handleStrategyById(req, supabase, user.id, strategyId, method);
    }

    return new Response(JSON.stringify({ error: "Not found" }), {
      status: 404,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});

async function handleStrategies(
  req: Request,
  supabase: any,
  userId: string,
  method: string,
) {
  if (method === "GET") {
    const { data, error } = await supabase
      .from("ts_strategies")
      .select(
        "*, ts_strategy_conditions(*, ts_indicators(*)), ts_trading_actions(*)",
      )
      .eq("user_id", userId)
      .order("created_at", { ascending: false });

    if (error) throw error;
    return new Response(JSON.stringify(data), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  if (method === "POST") {
    const body = await req.json();
    const { data, error } = await supabase
      .from("ts_strategies")
      .insert([{ ...body, user_id: userId }])
      .select()
      .single();

    if (error) throw error;
    return new Response(JSON.stringify(data), {
      status: 201,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ error: "Method not allowed" }), {
    status: 405,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function handleStrategyById(
  req: Request,
  supabase: any,
  userId: string,
  strategyId: string,
  method: string,
) {
  if (method === "GET") {
    const { data, error } = await supabase
      .from("ts_strategies")
      .select(
        "*, ts_strategy_conditions(*, ts_indicators(*)), ts_trading_actions(*)",
      )
      .eq("id", strategyId)
      .eq("user_id", userId)
      .single();

    if (error) throw error;
    return new Response(JSON.stringify(data), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  if (method === "PUT" || method === "PATCH") {
    const body = await req.json();
    const { data, error } = await supabase
      .from("ts_strategies")
      .update({ ...body, updated_at: new Date().toISOString() })
      .eq("id", strategyId)
      .eq("user_id", userId)
      .select()
      .single();

    if (error) throw error;
    return new Response(JSON.stringify(data), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  if (method === "DELETE") {
    const { error } = await supabase
      .from("ts_strategies")
      .delete()
      .eq("id", strategyId)
      .eq("user_id", userId);

    if (error) throw error;
    return new Response(JSON.stringify({ success: true }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ error: "Method not allowed" }), {
    status: 405,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function handleAuth(req: Request, supabase: any, userId: string) {
  const method = req.method;

  if (method === "POST") {
    const body = await req.json();
    const { action, code, codeVerifier, accessToken, refreshToken } = body;

    if (action === "exchange") {
      // Exchange authorization code for tokens
      const clientId = Deno.env.get("TRADESTATION_CLIENT_ID") ||
        "x3IYfpnSYevmXREQuW34LJUyeXaHBK";

      const tokenResponse = await fetch(
        "https://signin.tradestation.com/oauth/token",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            grant_type: "authorization_code",
            code: code,
            redirect_uri: "swiftbolt://oauth/callback",
            client_id: clientId,
            code_verifier: codeVerifier,
          }),
        },
      );

      const tokens = await tokenResponse.json();

      if (tokens.error) {
        return new Response(
          JSON.stringify({ error: tokens.error_description }),
          {
            status: 400,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          },
        );
      }

      // Store tokens
      const expiresAt = new Date(Date.now() + tokens.expires_in * 1000)
        .toISOString();
      const { error } = await supabase
        .from("ts_credentials")
        .upsert([{
          user_id: userId,
          access_token: tokens.access_token,
          refresh_token: tokens.refresh_token,
          token_expires_at: expiresAt,
          updated_at: new Date().toISOString(),
        }], { onConflict: "user_id" });

      if (error) throw error;

      return new Response(
        JSON.stringify({ success: true, expires_in: tokens.expires_in }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    if (action === "refresh") {
      // Refresh access token
      const { data: creds } = await supabase
        .from("ts_credentials")
        .select("refresh_token")
        .eq("user_id", userId)
        .single();

      if (!creds?.refresh_token) {
        return new Response(JSON.stringify({ error: "No refresh token" }), {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }

      const clientId = Deno.env.get("TRADESTATION_CLIENT_ID") ||
        "x3IYfpnSYevmXREQuW34LJUyeXaHBK";

      const refreshResponse = await fetch(
        "https://signin.tradestation.com/oauth/token",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            grant_type: "refresh_token",
            refresh_token: creds.refresh_token,
            client_id: clientId,
          }),
        },
      );

      const tokens = await refreshResponse.json();

      if (tokens.error) {
        return new Response(
          JSON.stringify({ error: tokens.error_description }),
          {
            status: 400,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          },
        );
      }

      const expiresAt = new Date(Date.now() + tokens.expires_in * 1000)
        .toISOString();
      await supabase
        .from("ts_credentials")
        .update({
          access_token: tokens.access_token,
          refresh_token: tokens.refresh_token || creds.refresh_token,
          token_expires_at: expiresAt,
          updated_at: new Date().toISOString(),
        })
        .eq("user_id", userId);

      return new Response(
        JSON.stringify({ success: true, expires_in: tokens.expires_in }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    if (action === "status") {
      const { data: creds } = await supabase
        .from("ts_credentials")
        .select("token_expires_at")
        .eq("user_id", userId)
        .single();

      const isConnected = !!creds?.token_expires_at;
      const isExpired = creds?.token_expires_at
        ? new Date(creds.token_expires_at) < new Date()
        : true;

      return new Response(
        JSON.stringify({ connected: isConnected, expired: isExpired }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }
  }

  return new Response(JSON.stringify({ error: "Invalid action" }), {
    status: 400,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function handleExecute(req: Request, supabase: any, userId: string) {
  const body = await req.json();
  const { strategy_id, symbol, use_sim = true } = body;

  // Get credentials
  const { data: creds } = await supabase
    .from("ts_credentials")
    .select("*")
    .eq("user_id", userId)
    .single();

  if (!creds?.access_token) {
    return new Response(
      JSON.stringify({ error: "Not authenticated with TradeStation" }),
      {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }

  // Check if token expired, refresh if needed
  let accessToken = creds.access_token;
  if (new Date(creds.token_expires_at) < new Date()) {
    const refreshResponse = await fetch(
      "https://signin.tradestation.com/oauth/token",
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "refresh_token",
          refresh_token: creds.refresh_token,
          client_id: Deno.env.get("TRADESTATION_CLIENT_ID") ||
            "x3IYfpnSYevmXREQuW34LJUyeXaHBK",
        }),
      },
    );
    const tokens = await refreshResponse.json();
    accessToken = tokens.access_token;

    await supabase
      .from("ts_credentials")
      .update({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token || creds.refresh_token,
        token_expires_at: new Date(Date.now() + tokens.expires_in * 1000)
          .toISOString(),
      })
      .eq("user_id", userId);
  }

  const baseUrl = use_sim ? TRADESTATION_SIM_URL : TRADESTATION_BASE_URL;

  // Get strategy with conditions and actions
  const { data: strategy } = await supabase
    .from("ts_strategies")
    .select(
      "*, ts_strategy_conditions(*, ts_indicators(*)), ts_trading_actions(*)",
    )
    .eq("id", strategy_id)
    .eq("user_id", userId)
    .single();

  if (!strategy) {
    return new Response(JSON.stringify({ error: "Strategy not found" }), {
      status: 404,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // Fetch current market data for the symbol
  const quoteResponse = await fetch(`${baseUrl}/quotes/${symbol}`, {
    headers: { "Authorization": `Bearer ${accessToken}` },
  });

  if (!quoteResponse.ok) {
    const error = await quoteResponse.text();
    return new Response(
      JSON.stringify({ error: "Failed to fetch quote", details: error }),
      {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }

  const quote = await quoteResponse.json();

  // Evaluate conditions (simplified - would need actual indicator calculations)
  const conditions = strategy.ts_strategy_conditions as StrategyCondition[];
  let conditionsMet = true;

  for (const condition of conditions) {
    // This is a placeholder - real implementation would calculate indicators
    // from real-time data and compare against thresholds
    const indicatorValue = quote[condition.indicators?.name?.toLowerCase()] ||
      0;
    const threshold = condition.threshold;

    switch (condition.operator) {
      case ">":
        conditionsMet = conditionsMet && indicatorValue > threshold;
        break;
      case "<":
        conditionsMet = conditionsMet && indicatorValue < threshold;
        break;
      case ">=":
        conditionsMet = conditionsMet && indicatorValue >= threshold;
        break;
      case "<=":
        conditionsMet = conditionsMet && indicatorValue <= threshold;
        break;
      case "=":
        conditionsMet = conditionsMet && indicatorValue === threshold;
        break;
    }
  }

  if (!conditionsMet) {
    return new Response(
      JSON.stringify({
        executed: false,
        reason: "Conditions not met",
        quote: quote,
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }

  // Execute actions
  const actions = strategy.ts_trading_actions as TradingAction[];
  const sortedActions = actions.sort((a, b) => a.priority - b.priority);
  const results = [];

  for (const action of sortedActions) {
    if (action.action_type === "BUY" || action.action_type === "SELL") {
      const quantity = action.parameters.quantity || 100;
      const orderType = action.parameters.order_type || "Market";

      const orderResponse = await fetch(`${baseUrl}/orders`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          Symbol: symbol,
          Quantity: quantity,
          OrderType: orderType,
          Side: action.action_type,
          TimeInForce: action.parameters.time_in_force || "Day",
        }),
      });

      const orderResult = await orderResponse.json();

      // Log execution
      await supabase.from("ts_execution_log").insert([{
        strategy_id,
        action_id: action.id,
        symbol,
        action_type: action.action_type,
        status: orderResponse.ok ? "FILLED" : "REJECTED",
        quantity,
        raw_response: orderResult,
        filled_at: orderResponse.ok ? new Date().toISOString() : null,
      }]);

      results.push({ action: action.action_type, result: orderResult });
    }
  }

  return new Response(JSON.stringify({ executed: true, results }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
