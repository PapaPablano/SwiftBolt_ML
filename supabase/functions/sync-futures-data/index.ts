// POST /sync-futures-data
// Syncs futures reference data from Massive API to database
// Should be called daily via cron or on-demand

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  corsResponse,
  getCorsHeaders,
  handlePreflight,
} from "../_shared/cors.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { MassiveClient } from "../_shared/providers/massive-client.ts";
import { MemoryCache } from "../_shared/cache/memory-cache.ts";
import { TokenBucketRateLimiter } from "../_shared/rate-limiter/token-bucket.ts";
import { getRateLimits } from "../_shared/config/rate-limits.ts";

interface SyncRequest {
  roots?: string[]; // Specific roots to sync, or all if empty
  force?: boolean; // Force refresh even if recently synced
}

interface SyncResult {
  root: string;
  contracts_added: number;
  contracts_updated: number;
  errors: string[];
}

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("origin");

  if (req.method === "OPTIONS") {
    return handlePreflight(origin);
  }

  if (req.method !== "POST") {
    return corsResponse({ error: "Method not allowed" }, 405, origin);
  }

  try {
    // Parse request body
    const body: SyncRequest = await req.json().catch(() => ({}));
    const { roots, force = false } = body;

    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    const massiveApiKey = Deno.env.get("MASSIVE_API_KEY");

    if (!supabaseUrl || !supabaseServiceKey) {
      return corsResponse(
        { error: "Missing Supabase credentials" },
        500,
        origin,
      );
    }

    if (!massiveApiKey) {
      return corsResponse(
        { error: "Missing MASSIVE_API_KEY" },
        500,
        origin,
      );
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Initialize Massive client
    const cache = new MemoryCache();
    const rateLimits = getRateLimits();
    const rateLimiter = new TokenBucketRateLimiter({
      massive: { ...rateLimits.massive },
    });
    const massiveClient = new MassiveClient(massiveApiKey, rateLimiter, cache);

    // Determine which roots to sync
    let rootsToSync: string[] = [];
    if (roots && roots.length > 0) {
      rootsToSync = roots.map((r) => r.toUpperCase());
    } else {
      // Get all roots from database
      const { data: rootData } = await supabase
        .from("futures_roots")
        .select("symbol");
      rootsToSync = rootData?.map((r) => r.symbol) || [];
    }

    if (rootsToSync.length === 0) {
      return corsResponse(
        { error: "No futures roots configured" },
        400,
        origin,
      );
    }

    const results: SyncResult[] = [];

    for (const rootSymbol of rootsToSync) {
      console.log(`[sync-futures-data] Syncing root: ${rootSymbol}`);
      const result: SyncResult = {
        root: rootSymbol,
        contracts_added: 0,
        contracts_updated: 0,
        errors: [],
      };

      try {
        // Get root ID from database
        const { data: rootData } = await supabase
          .from("futures_roots")
          .select("id")
          .eq("symbol", rootSymbol)
          .single();

        if (!rootData) {
          result.errors.push("Root not found in database");
          results.push(result);
          continue;
        }

        const rootId = rootData.id;

        // Fetch chain from Massive
        const chain = await massiveClient.getFuturesChain(rootSymbol);

        // Process each contract
        for (const contract of chain.contracts) {
          // Check if contract exists
          const { data: existingContract } = await supabase
            .from("futures_contracts")
            .select("id")
            .eq("symbol", contract.symbol)
            .single();

          if (existingContract) {
            // Update contract
            const { error: updateError } = await supabase
              .from("futures_contracts")
              .update({
                is_active: contract.isActive,
                is_spot: contract.isSpot,
                updated_at: new Date().toISOString(),
              })
              .eq("id", existingContract.id);

            if (updateError) {
              result.errors.push(
                `Update ${contract.symbol}: ${updateError.message}`,
              );
            } else {
              result.contracts_updated++;
              // Also update symbols table
              await upsertFuturesSymbol(supabase, rootSymbol, contract);
            }
          } else {
            // Insert new contract
            const { error: insertError } = await supabase
              .from("futures_contracts")
              .insert({
                root_id: rootId,
                symbol: contract.symbol,
                contract_code: contract.contractCode,
                expiry_month: contract.expiryMonth,
                expiry_year: contract.expiryYear,
                last_trade_date: contract.lastTradeDate,
                is_active: contract.isActive,
                is_spot: contract.isSpot,
              });

            if (insertError) {
              result.errors.push(
                `Insert ${contract.symbol}: ${insertError.message}`,
              );
            } else {
              result.contracts_added++;
            }

            // Also insert/update in symbols table (for both new and existing)
            await upsertFuturesSymbol(supabase, rootSymbol, contract);
          }
        }

        // Also upsert root symbol in symbols table (if not exists)
        await upsertFuturesRootSymbol(supabase, rootSymbol);

        // Update continuous mappings
        for (const mapping of chain.continuousAliases) {
          // Get contract ID
          const { data: contractData } = await supabase
            .from("futures_contracts")
            .select("id")
            .eq("symbol", mapping.contract.symbol)
            .single();

          if (!contractData) {
            result.errors.push(
              `Contract not found for mapping: ${mapping.contract.symbol}`,
            );
            continue;
          }

          // Check for existing active mapping
          const { data: existingMapping } = await supabase
            .from("futures_continuous_map")
            .select("id")
            .eq("root_id", rootId)
            .eq("depth", mapping.depth)
            .eq("is_active", true)
            .single();

          if (existingMapping) {
            // Check if mapping needs to change
            const { data: currentContractMapping } = await supabase
              .from("futures_continuous_map")
              .select("contract_id")
              .eq("id", existingMapping.id)
              .single();

            if (currentContractMapping?.contract_id !== contractData.id) {
              // Expire old mapping
              await supabase
                .from("futures_continuous_map")
                .update({
                  is_active: false,
                  valid_until: new Date().toISOString().split("T")[0],
                  updated_at: new Date().toISOString(),
                })
                .eq("id", existingMapping.id);

              // Create new mapping
              await supabase
                .from("futures_continuous_map")
                .insert({
                  root_id: rootId,
                  depth: mapping.depth,
                  continuous_alias: mapping.alias,
                  contract_id: contractData.id,
                  valid_from: new Date().toISOString().split("T")[0],
                  is_active: true,
                });
            }
          } else {
            // Create new mapping
            await supabase
              .from("futures_continuous_map")
              .insert({
                root_id: rootId,
                depth: mapping.depth,
                continuous_alias: mapping.alias,
                contract_id: contractData.id,
                valid_from: new Date().toISOString().split("T")[0],
                is_active: true,
              });
          }
        }
      } catch (error) {
        console.error(
          `[sync-futures-data] Error syncing ${rootSymbol}:`,
          error,
        );
        result.errors.push(
          error instanceof Error ? error.message : String(error),
        );
      }

      results.push(result);
    }

    return corsResponse(
      {
        success: true,
        timestamp: new Date().toISOString(),
        roots_processed: rootsToSync.length,
        results,
      },
      200,
      origin,
    );
  } catch (error) {
    console.error("[sync-futures-data] Error:", error);
    return corsResponse(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      500,
      origin,
    );
  }
});

interface Contract {
  symbol: string;
  contractCode: string;
  expiryMonth: number;
  expiryYear: number;
  isActive: boolean;
  isSpot: boolean;
}

async function upsertFuturesSymbol(
  supabase: any,
  rootSymbol: string,
  contract: Contract,
) {
  try {
    console.log(
      `[sync-futures-data] upsertFuturesSymbol called for ${contract.symbol}`,
    );

    const expiryDate = new Date(
      contract.expiryYear,
      contract.expiryMonth - 1,
      1,
    );
    const monthStr = expiryDate.toLocaleString("en-US", { month: "short" })
      .toUpperCase();

    // Check if symbol already exists
    const { data: existing, error: selectError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", contract.symbol)
      .single();

    console.log(
      `[sync-futures-data] Select result for ${contract.symbol}: data=${!!existing}, error=${
        selectError?.message || "none"
      }`,
    );

    // PGRST116 means no rows found - that's not an error, it means symbol doesn't exist
    const symbolExists = existing !== null && selectError === null;

    const symbolData: any = {
      ticker: contract.symbol,
      asset_type: "future",
      description: `${rootSymbol} ${monthStr} ${contract.expiryYear} (Futures)`,
      is_active: contract.isActive,
      name: contract.symbol,
      updated_at: new Date().toISOString(),
    };

    if (symbolExists) {
      console.log(`[sync-futures-data] Updating symbol ${contract.symbol}`);
      const { error: updateError } = await supabase
        .from("symbols")
        .update(symbolData)
        .eq("ticker", contract.symbol);

      if (updateError) {
        console.error(
          `[sync-futures-data] Error updating symbol ${contract.symbol}:`,
          updateError,
        );
      } else {
        console.log(`[sync-futures-data] Updated symbol ${contract.symbol}`);
      }
    } else {
      console.log(
        `[sync-futures-data] Inserting new symbol ${contract.symbol}`,
      );
      symbolData.created_at = new Date().toISOString();
      const { error: insertError } = await supabase
        .from("symbols")
        .insert(symbolData);

      if (insertError) {
        console.error(
          `[sync-futures-data] Error inserting symbol ${contract.symbol}:`,
          insertError,
        );
      } else {
        console.log(`[sync-futures-data] Inserted symbol ${contract.symbol}`);
      }
    }
  } catch (error) {
    console.error(
      `[sync-futures-data] Error upserting symbol ${contract.symbol}:`,
      error,
    );
  }
}

async function upsertFuturesRootSymbol(supabase: any, rootSymbol: string) {
  try {
    const { data: existing } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", rootSymbol)
      .single();

    if (existing) {
      await supabase
        .from("symbols")
        .update({
          asset_type: "future",
          is_active: true,
          requires_expiry_picker: true,
          root_symbol: rootSymbol,
          updated_at: new Date().toISOString(),
        })
        .eq("ticker", rootSymbol);
    } else {
      await supabase
        .from("symbols")
        .insert({
          ticker: rootSymbol,
          asset_type: "future",
          description: `${rootSymbol} (Futures) [Select Expiry →]`,
          is_active: true,
          requires_expiry_picker: true,
          root_symbol: rootSymbol,
        });
    }
  } catch (error) {
    console.error(
      `[sync-futures-data] Error upserting root symbol ${rootSymbol}:`,
      error,
    );
  }
}
