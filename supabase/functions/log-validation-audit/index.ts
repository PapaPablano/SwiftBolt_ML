import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface AuditPayload {
  symbol: string;
  confidence: number;
  weights?: Record<string, unknown>;
  timestamp: number;
  user_id?: string;
  client_state?: Record<string, unknown>;
}

serve(async (req: Request) => {
  try {
    if (req.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405);
    }

    let payload: AuditPayload;
    try {
      payload = (await req.json()) as AuditPayload;
    } catch {
      return jsonResponse({ error: "Invalid JSON body" }, 400);
    }

    const validationError = validatePayload(payload);
    if (validationError) {
      return jsonResponse({ error: validationError }, 400);
    }

    const supabase = getSupabaseClient();
    const symbol = payload.symbol.trim().toUpperCase();

    const { data: symbolRow, error: symbolError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", symbol)
      .maybeSingle();

    if (symbolError) {
      console.error("[log-validation-audit] symbol lookup error", symbolError);
      return jsonResponse({ error: "Failed to resolve symbol" }, 500);
    }

    if (!symbolRow) {
      return jsonResponse({ error: `Symbol ${symbol} not found` }, 404);
    }

    const insertPayload = {
      symbol_id: symbolRow.id,
      user_id: payload.user_id ?? null,
      confidence_score: payload.confidence,
      weights_config: payload.weights ?? null,
      client_state: payload.client_state ?? null,
      logged_at: new Date(payload.timestamp * 1000),
    };

    const { error: insertError } = await supabase
      .from("validation_audits")
      .insert(insertPayload);

    if (insertError) {
      console.error("[log-validation-audit] insert error", insertError);
      return jsonResponse({ error: "Failed to record audit" }, 500);
    }

    return jsonResponse({ success: true }, 200);
  } catch (error) {
    console.error("[log-validation-audit] unexpected error", error);
    return jsonResponse({ error: "Unexpected server error" }, 500);
  }
});

function validatePayload(payload: Partial<AuditPayload>): string | null {
  if (!payload.symbol) {
    return "symbol is required";
  }

  if (typeof payload.confidence !== "number" || Number.isNaN(payload.confidence)) {
    return "confidence must be a number";
  }

  if (payload.confidence < 0 || payload.confidence > 1) {
    return "confidence must be between 0 and 1";
  }

  if (typeof payload.timestamp !== "number" || !Number.isFinite(payload.timestamp)) {
    return "timestamp must be a Unix epoch second";
  }

  if (payload.weights && typeof payload.weights !== "object") {
    return "weights must be an object";
  }

  if (payload.client_state && typeof payload.client_state !== "object") {
    return "client_state must be an object";
  }

  return null;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
