import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getProviderRouter } from "../_shared/providers/factory.ts";

interface OptionsQuotesRequest {
  symbol?: string;
  contracts?: string[];
  expiration?: number;
}

interface QuotePayload {
  contract_symbol: string;
  bid: number | null;
  ask: number | null;
  mark: number | null;
  last: number | null;
  volume: number | null;
  open_interest: number | null;
  implied_vol: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  rho: number | null;
  updated_at: string;
}

const MAX_CONTRACTS = 120;

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  if (req.method !== "POST" && req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    let payload: OptionsQuotesRequest = {};

    if (req.method === "GET") {
      const url = new URL(req.url);
      payload.symbol = url.searchParams.get("symbol")?.toUpperCase();
      const contractsParam = url.searchParams.get("contracts");
      if (contractsParam) {
        payload.contracts = contractsParam
          .split(",")
          .map((c) => c.trim().toUpperCase())
          .filter((c) => c.length > 0);
      }
      const expirationParam = url.searchParams.get("expiration");
      if (expirationParam) {
        const exp = parseInt(expirationParam, 10);
        if (!Number.isNaN(exp)) {
          payload.expiration = exp;
        }
      }
    } else {
      try {
        payload = await req.json();
        if (payload.symbol) {
          payload.symbol = payload.symbol.toUpperCase();
        }
        if (Array.isArray(payload.contracts)) {
          payload.contracts = payload.contracts
            .map((c) => c.trim().toUpperCase())
            .filter((c) => c.length > 0);
        }
      } catch (_err) {
        return errorResponse("Invalid JSON body", 400);
      }
    }

    const symbol = payload.symbol?.trim();
    const contracts = payload.contracts || [];

    if (!symbol) {
      return errorResponse("Missing required parameter: symbol", 400);
    }

    if (contracts.length === 0) {
      return errorResponse("No contracts specified", 400);
    }

    if (contracts.length > MAX_CONTRACTS) {
      contracts.length = MAX_CONTRACTS;
    }

    const router = getProviderRouter();
    const chain = await router.getOptionsChain({
      underlying: symbol,
      expiration: payload.expiration,
    });

    const chainTimestampIso = new Date(chain.timestamp).toISOString();
    const contractLookup = new Map<string, typeof chain.calls[number]>();

    for (const contract of [...chain.calls, ...chain.puts]) {
      contractLookup.set(contract.symbol.toUpperCase(), contract);
    }

    const quotes: QuotePayload[] = [];

    for (const contractSymbol of contracts) {
      const match = contractLookup.get(contractSymbol);
      if (!match) continue;

      const updatedIso = match.lastTradeTime
        ? new Date(match.lastTradeTime).toISOString()
        : chainTimestampIso;

      quotes.push({
        contract_symbol: contractSymbol,
        bid: typeof match.bid === "number" ? match.bid : null,
        ask: typeof match.ask === "number" ? match.ask : null,
        mark: typeof match.mark === "number" ? match.mark : null,
        last: typeof match.last === "number" ? match.last : null,
        volume: typeof match.volume === "number" ? match.volume : null,
        open_interest: typeof match.openInterest === "number" ? match.openInterest : null,
        implied_vol: typeof match.impliedVolatility === "number" ? match.impliedVolatility : null,
        delta: typeof match.delta === "number" ? match.delta : null,
        gamma: typeof match.gamma === "number" ? match.gamma : null,
        theta: typeof match.theta === "number" ? match.theta : null,
        vega: typeof match.vega === "number" ? match.vega : null,
        rho: typeof match.rho === "number" ? match.rho : null,
        updated_at: updatedIso,
      });
    }

    return jsonResponse({
      symbol,
      timestamp: new Date().toISOString(),
      chain_timestamp: chainTimestampIso,
      total_requested: contracts.length,
      total_returned: quotes.length,
      quotes,
    });
  } catch (error) {
    console.error("[options-quotes] Error:", error);
    const message = error instanceof Error ? error.message : String(error);
    return errorResponse(`Failed to fetch option quotes: ${message}`, 500);
  }
});
