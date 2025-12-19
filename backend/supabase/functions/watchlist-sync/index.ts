import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface WatchlistRequest {
  action: "add" | "remove" | "list";
  symbol?: string;
  watchlistId?: string;
}

interface WatchlistItem {
  symbol: string;
  addedAt: string;
  jobStatus?: {
    forecast: string | null;
    ranking: string | null;
  };
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // TEMPORARY: Use service role for development (bypasses auth)
    // TODO: Re-enable authentication for production
    const supabaseClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    // For now, use a fixed user ID for development
    // TODO: Re-enable proper authentication
    const user = { id: "00000000-0000-0000-0000-000000000000" };

    const body: WatchlistRequest = await req.json();

    // Get or create default watchlist for user
    let { data: watchlists, error: watchlistError } = await supabaseClient
      .from("watchlists")
      .select("id")
      .eq("user_id", user.id)
      .limit(1);

    if (watchlistError) throw watchlistError;

    let watchlistId: string;

    if (!watchlists || watchlists.length === 0) {
      // Create default watchlist
      const { data: newWatchlist, error: createError } = await supabaseClient
        .from("watchlists")
        .insert({ user_id: user.id, name: "My Watchlist" })
        .select("id")
        .single();

      if (createError) throw createError;
      watchlistId = newWatchlist.id;
    } else {
      watchlistId = body.watchlistId || watchlists[0].id;
    }

    // Handle actions
    switch (body.action) {
      case "add": {
        if (!body.symbol) {
          return new Response(JSON.stringify({ error: "Symbol required" }), {
            status: 400,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          });
        }

        // Get or create symbol
        let { data: symbol, error: symbolError } = await supabaseClient
          .from("symbols")
          .select("id, ticker")
          .eq("ticker", body.symbol.toUpperCase())
          .single();

        if (symbolError || !symbol) {
          // Create symbol if doesn't exist
          const { data: newSymbol, error: createSymbolError } = await supabaseClient
            .from("symbols")
            .insert({ ticker: body.symbol.toUpperCase() })
            .select("id, ticker")
            .single();

          if (createSymbolError) throw createSymbolError;
          symbol = newSymbol;
        }

        // Add to watchlist (trigger will auto-create jobs)
        const { error: insertError } = await supabaseClient
          .from("watchlist_items")
          .insert({
            watchlist_id: watchlistId,
            symbol_id: symbol.id,
          });

        if (insertError) {
          // Check if already exists
          if (insertError.code === "23505") {
            return new Response(
              JSON.stringify({
                success: true,
                message: "Symbol already in watchlist",
                symbol: symbol.ticker,
              }),
              {
                status: 200,
                headers: { ...corsHeaders, "Content-Type": "application/json" },
              }
            );
          }
          throw insertError;
        }

        // Get job status
        const { data: jobStatus } = await supabaseClient.rpc(
          "get_symbol_job_status",
          { p_symbol: symbol.ticker }
        );

        return new Response(
          JSON.stringify({
            success: true,
            message: "Symbol added to watchlist, jobs queued",
            symbol: symbol.ticker,
            watchlistId,
            jobStatus: jobStatus || [],
          }),
          {
            status: 200,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          }
        );
      }

      case "remove": {
        if (!body.symbol) {
          return new Response(JSON.stringify({ error: "Symbol required" }), {
            status: 400,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          });
        }

        // Get symbol ID
        const { data: symbol } = await supabaseClient
          .from("symbols")
          .select("id")
          .eq("ticker", body.symbol.toUpperCase())
          .single();

        if (!symbol) {
          return new Response(JSON.stringify({ error: "Symbol not found" }), {
            status: 404,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          });
        }

        // Remove from watchlist
        const { error: deleteError } = await supabaseClient
          .from("watchlist_items")
          .delete()
          .eq("watchlist_id", watchlistId)
          .eq("symbol_id", symbol.id);

        if (deleteError) throw deleteError;

        return new Response(
          JSON.stringify({
            success: true,
            message: "Symbol removed from watchlist",
            symbol: body.symbol.toUpperCase(),
          }),
          {
            status: 200,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          }
        );
      }

      case "list": {
        // Get all watchlist items with job status
        const { data: items, error: listError } = await supabaseClient
          .from("watchlist_items")
          .select(`
            symbol_id,
            added_at,
            symbols!inner(ticker)
          `)
          .eq("watchlist_id", watchlistId);

        if (listError) throw listError;

        // Get job status for each symbol
        const watchlistItems: WatchlistItem[] = await Promise.all(
          (items || []).map(async (item) => {
            const { data: jobStatus } = await supabaseClient.rpc(
              "get_symbol_job_status",
              { p_symbol: item.symbols.ticker }
            );

            const forecastJob = jobStatus?.find((j: any) => j.job_type === "forecast");
            const rankingJob = jobStatus?.find((j: any) => j.job_type === "ranking");

            return {
              symbol: item.symbols.ticker,
              addedAt: item.added_at,
              jobStatus: {
                forecast: forecastJob?.status || null,
                ranking: rankingJob?.status || null,
              },
            };
          })
        );

        return new Response(
          JSON.stringify({
            success: true,
            watchlistId,
            items: watchlistItems,
          }),
          {
            status: 200,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          }
        );
      }

      default:
        return new Response(
          JSON.stringify({ error: "Invalid action. Use: add, remove, or list" }),
          {
            status: 400,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          }
        );
    }
  } catch (error) {
    console.error("Error:", error);
    return new Response(
      JSON.stringify({ error: error.message || "Internal server error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
