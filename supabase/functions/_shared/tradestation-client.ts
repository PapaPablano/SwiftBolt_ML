/**
 * TradeStation API Client
 *
 * Wraps all HTTP calls to TradeStation's v3 API.
 * Read-only operations (balance, order status) live here.
 * Write operations (placeMarketOrder, placeBracketOrders) are co-located
 * with the live-trading-executor to limit blast radius.
 *
 * Token refresh uses optimistic locking (P1 #086) to prevent
 * concurrent refresh race conditions.
 */

import type { SupabaseClient } from "@supabase/supabase-js";
import {
  FUTURES_MULTIPLIERS,
  type FuturesMultiplier,
} from "./futures-calendar.ts";

type Db = SupabaseClient;

// ============================================================================
// CONFIGURATION
// ============================================================================

const TS_BASE_URL = "https://api.tradestation.com/v3";
const TS_SIM_BASE_URL = "https://sim-api.tradestation.com/v3";
const TS_AUTH_URL = "https://signin.tradestation.com/oauth/token";

/** Use sim API when TRADESTATION_USE_SIM env is set */
function getBaseUrl(): string {
  return Deno.env.get("TRADESTATION_USE_SIM") === "true"
    ? TS_SIM_BASE_URL
    : TS_BASE_URL;
}

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

export interface BrokerToken {
  id: string;
  user_id: string;
  provider: "tradestation";
  access_token: string;
  refresh_token: string;
  expires_at: string;
  account_id: string;
  futures_account_id: string | null;
  revoked_at: string | null;
}

export interface AccountBalance {
  equity: number;
  buyingPower: number;
  cashBalance: number;
}

// #125, #161: Known TradeStation order status codes
type KnownOrderStatus =
  | "FLL" // Fully filled
  | "FPR" // Partial fill (#161: NOT "FLP")
  | "OPN" // Open/working
  | "CAN" // Cancelled
  | "REJ" // Rejected
  | "EXP" // Expired
  | "Filled" // English alias
  | "Partial Fill" // English alias
  | "Canceled" // English alias
  | "Rejected"; // English alias

export interface OrderFillResult {
  filledQuantity: number;
  fillPrice: number;
  status: KnownOrderStatus | string; // | string: broker may send undocumented codes
}

export interface BracketOrderResult {
  entryOrderId: string;
  slOrderId: string;
  tpOrderId: string;
}

export interface NormalizedSymbol {
  tsSymbol: string;
  isFutures: boolean;
  multiplier: FuturesMultiplier | 1;
}

/** Discriminated union for execution errors */
export type LiveExecutionError =
  | { type: "broker_auth_failed"; reason: string }
  | { type: "broker_unavailable"; statusCode: number }
  | { type: "order_rejected"; code: string }
  | { type: "order_not_filled"; orderId: string }
  | {
    type: "circuit_breaker";
    rule: "market_hours" | "daily_loss" | "max_positions" | "position_size_cap";
  }
  | { type: "position_locked"; reason: "concurrent_close_detected" }
  | { type: "database_error"; reason: string }
  | { type: "bracket_placement_failed"; orderId: string; reason: string }
  | { type: "validation_error"; reason: string };

/** Discriminated union for circuit breaker results */
export type CircuitBreakerResult =
  | { allowed: true }
  | {
    allowed: false;
    reason: string;
    rule: "market_hours" | "daily_loss" | "max_positions" | "position_size_cap";
  };

// ============================================================================
// SYMBOL VALIDATION & NORMALIZATION
// ============================================================================

/** Allowed equity symbols pattern (1-5 uppercase letters) */
const EQUITY_SYMBOL_PATTERN = /^[A-Z]{1,5}$/;

/** Allowed futures root symbols */
const ALLOWED_FUTURES_ROOTS = new Set(Object.keys(FUTURES_MULTIPLIERS));

/** Allowed timeframes */
const ALLOWED_TIMEFRAMES = new Set([
  "1m",
  "5m",
  "15m",
  "30m",
  "1h",
  "4h",
  "1D",
]);

/**
 * Validate symbol against allowlist.
 * Prevents injection into TradeStation API URL paths (P1 #091).
 */
export function validateSymbol(symbol: string): boolean {
  if (!symbol || symbol.length > 10) return false;
  // Check if it's a futures symbol
  const normalized = symbol.startsWith("/")
    ? `@${symbol.slice(1)}`
    : symbol.startsWith("@")
    ? symbol
    : symbol;
  if (normalized.startsWith("@")) {
    return ALLOWED_FUTURES_ROOTS.has(normalized);
  }
  return EQUITY_SYMBOL_PATTERN.test(symbol);
}

/**
 * Validate timeframe against allowlist.
 */
export function validateTimeframe(timeframe: string): boolean {
  return ALLOWED_TIMEFRAMES.has(timeframe);
}

/**
 * Normalize user-input symbol to TradeStation format.
 * /ES → @ES, /NQ → @NQ, AAPL → AAPL
 * Returns multiplier from FUTURES_MULTIPLIERS (never 0).
 */
export function normalizeSymbol(symbol: string): NormalizedSymbol {
  let tsSymbol = symbol;

  // Convert /ES notation to @ES (TradeStation continuous front-month)
  if (symbol.startsWith("/")) {
    tsSymbol = `@${symbol.slice(1)}`;
  }

  const isFutures = tsSymbol.startsWith("@");
  const multiplier = isFutures
    ? (FUTURES_MULTIPLIERS[tsSymbol] as FuturesMultiplier) ?? 1
    : 1;

  return {
    tsSymbol,
    isFutures,
    multiplier: multiplier as FuturesMultiplier | 1,
  };
}

// ============================================================================
// ACCOUNT URL BUILDER (SSRF protection)
// ============================================================================

/**
 * Build a safe account URL. Validates account ID format before use
 * to prevent path traversal / SSRF (P1 #091, P2 #104).
 */
function buildAccountUrl(accountId: string, path: string): string {
  if (!/^[A-Z0-9]{4,15}$/.test(accountId)) {
    throw new Error("Invalid account ID format");
  }
  return `${getBaseUrl()}/brokerage/accounts/${
    encodeURIComponent(accountId)
  }${path}`;
}

// ============================================================================
// TOKEN MANAGEMENT
// ============================================================================

/**
 * Refresh an expired access token via TradeStation's OAuth endpoint.
 */
export async function refreshAccessToken(
  clientId: string,
  clientSecret: string,
  refreshToken: string,
): Promise<
  { access_token: string; refresh_token: string; expires_in: number }
> {
  const response = await fetch(TS_AUTH_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: refreshToken,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(
      `Token refresh failed (${response.status}): ${sanitizeBrokerError(body)}`,
    );
  }

  return await response.json();
}

/**
 * Ensure the broker token is fresh. Uses optimistic locking to prevent
 * concurrent refresh race conditions (P1 #086).
 *
 * If the token expires within 5 minutes, refresh it with a conditional
 * UPDATE (WHERE expires_at = $old). If another invocation already refreshed,
 * re-read and return the fresh token.
 */
export async function ensureFreshToken(
  supabase: Db,
  userId: string,
): Promise<BrokerToken> {
  // Read current token (via auth client — respects RLS)
  const { data: token, error } = await supabase
    .from("broker_tokens")
    .select("*")
    .eq("user_id", userId)
    .eq("provider", "tradestation")
    .is("revoked_at", null)
    .single();

  if (error || !token) {
    throw Object.assign(new Error("broker_not_connected"), { status: 401 });
  }

  const expiresAt = new Date(token.expires_at).getTime();
  const fiveMinFromNow = Date.now() + 5 * 60 * 1000;

  if (expiresAt > fiveMinFromNow) {
    return token as BrokerToken;
  }

  // Token expiring soon — refresh
  const clientId = Deno.env.get("TRADESTATION_CLIENT_ID");
  const clientSecret = Deno.env.get("TRADESTATION_CLIENT_SECRET");
  if (!clientId || !clientSecret) {
    throw new Error(
      "Missing TRADESTATION_CLIENT_ID or TRADESTATION_CLIENT_SECRET",
    );
  }

  const refreshed = await refreshAccessToken(
    clientId,
    clientSecret,
    token.refresh_token,
  );

  const newExpiresAt = new Date(
    Date.now() + refreshed.expires_in * 1000,
  ).toISOString();

  // Optimistic lock: only update if expires_at hasn't changed (another invocation didn't already refresh)
  const { data: updated } = await supabase
    .from("broker_tokens")
    .update({
      access_token: refreshed.access_token,
      refresh_token: refreshed.refresh_token,
      expires_at: newExpiresAt,
      updated_at: new Date().toISOString(),
    })
    .eq("user_id", userId)
    .eq("provider", "tradestation")
    .eq("expires_at", token.expires_at) // optimistic lock condition
    .select()
    .maybeSingle();

  if (!updated) {
    // Another invocation already refreshed — re-read the fresh token
    const { data: freshToken } = await supabase
      .from("broker_tokens")
      .select("*")
      .eq("user_id", userId)
      .eq("provider", "tradestation")
      .is("revoked_at", null)
      .single();

    // #111: Null-guard — token may have been revoked between update and re-read
    if (!freshToken) {
      throw Object.assign(new Error("broker_not_connected"), { status: 401 });
    }
    return freshToken as BrokerToken;
  }

  return updated as BrokerToken;
}

// ============================================================================
// READ-ONLY API CALLS
// ============================================================================

/**
 * Get account balance (equity, buying power, cash).
 */
export async function getAccountBalance(
  accessToken: string,
  accountId: string,
): Promise<AccountBalance> {
  const url = buildAccountUrl(accountId, "/balances");
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    const status = response.status;
    if (status === 401) {
      throw Object.assign(new Error("broker_auth_expired"), { status: 401 });
    }
    throw Object.assign(
      new Error(`Balance fetch failed (${status})`),
      { status },
    );
  }

  const data = await response.json();
  const balances = data.Balances?.[0] ?? data;

  return {
    equity: parseFloat(balances.Equity ?? balances.equity ?? "0"),
    buyingPower: parseFloat(
      balances.BuyingPower ?? balances.buyingPower ?? "0",
    ),
    cashBalance: parseFloat(
      balances.CashBalance ?? balances.cashBalance ?? "0",
    ),
  };
}

/**
 * Get the status of a single order.
 */
export async function getOrderStatus(
  accessToken: string,
  accountId: string,
  orderId: string,
): Promise<OrderFillResult> {
  const url = buildAccountUrl(
    accountId,
    `/orders/${encodeURIComponent(orderId)}`,
  );
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    throw new Error(`Order status fetch failed (${response.status})`);
  }

  const data = await response.json();
  const order = data.Orders?.[0] ?? data;

  return {
    filledQuantity: parseInt(order.FilledQuantity ?? "0", 10),
    fillPrice: parseFloat(order.FilledPrice ?? order.AveragePrice ?? "0"),
    status: order.StatusDescription ?? order.Status ?? "UNKNOWN",
  };
}

/**
 * Batch-fetch order statuses for multiple order IDs.
 * Reduces N+1 API calls for bracket fill monitoring.
 */
export async function getBatchOrderStatus(
  accessToken: string,
  accountId: string,
  orderIds: string[],
): Promise<Map<string, OrderFillResult>> {
  // #146: Limit order history to last 48h to prevent unbounded payload
  const since = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
  const url = buildAccountUrl(
    accountId,
    `/orders?since=${encodeURIComponent(since)}`,
  );
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    throw new Error(`Batch order status failed (${response.status})`);
  }

  const data = await response.json();
  const orders = data.Orders ?? [];
  const results = new Map<string, OrderFillResult>();
  const orderIdSet = new Set(orderIds);

  for (const order of orders) {
    const id = order.OrderID ?? order.orderId;
    if (orderIdSet.has(id)) {
      results.set(id, {
        filledQuantity: parseInt(order.FilledQuantity ?? "0", 10),
        fillPrice: parseFloat(
          order.FilledPrice ?? order.AveragePrice ?? "0",
        ),
        status: order.StatusDescription ?? order.Status ?? "UNKNOWN",
      });
    }
  }

  return results;
}

// ============================================================================
// BROKER ERROR SANITIZATION
// ============================================================================

/**
 * Map raw broker errors to internal codes.
 * Never expose raw TradeStation messages containing account balances,
 * internal codes, or account IDs to the client (P3 #106).
 */
export function sanitizeBrokerError(tsError: string): string {
  const lower = tsError.toLowerCase();
  if (lower.includes("buying power") || lower.includes("margin")) {
    return "insufficient_funds";
  }
  if (lower.includes("market hours") || lower.includes("closed")) {
    return "market_closed";
  }
  if (lower.includes("invalid symbol") || lower.includes("not found")) {
    return "invalid_symbol";
  }
  if (lower.includes("rate limit") || lower.includes("too many")) {
    return "rate_limited";
  }
  return "order_rejected";
}

// ============================================================================
// RE-EXPORTS
// ============================================================================

export {
  FUTURES_MULTIPLIERS,
  FUTURES_TICK_SIZES,
  MAX_FUTURES_CONTRACTS,
} from "./futures-calendar.ts";
export type { FuturesMultiplier } from "./futures-calendar.ts";
