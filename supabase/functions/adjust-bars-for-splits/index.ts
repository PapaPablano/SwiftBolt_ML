import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

interface Split {
  symbol: string;
  date: string;
  ratio?: number;
  metadata?: any;
}

serve(async (req) => {
  try {
    const { splits } = await req.json() as { splits: Split[] };

    if (!splits || splits.length === 0) {
      return new Response(
        JSON.stringify({ success: true, message: "No splits to process" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const results = [];

    for (const split of splits) {
      console.log(
        `[adjust-bars] Processing ${split.symbol} split on ${split.date} (${split.ratio}:1)`,
      );

      // Get the corporate action ID
      const { data: corporateAction, error: caError } = await supabase
        .from("corporate_actions")
        .select("id, ratio")
        .eq("symbol", split.symbol)
        .eq("ex_date", split.date)
        .in("action_type", ["stock_split", "reverse_split"])
        .single();

      if (caError || !corporateAction) {
        console.error(
          `[adjust-bars] Corporate action not found for ${split.symbol}:`,
          caError,
        );
        continue;
      }

      const adjustmentRatio = corporateAction.ratio || split.ratio;
      if (!adjustmentRatio) {
        console.error(`[adjust-bars] No ratio found for ${split.symbol}`);
        continue;
      }

      // Get symbol_id
      const { data: symbolData, error: symbolError } = await supabase
        .from("symbols")
        .select("id")
        .eq("ticker", split.symbol)
        .single();

      if (symbolError || !symbolData) {
        console.error(
          `[adjust-bars] Symbol not found: ${split.symbol}`,
          symbolError,
        );
        continue;
      }

      // Get all bars BEFORE split date that haven't been adjusted
      const { data: bars, error: barsError } = await supabase
        .from("ohlc_bars_v2")
        .select("*")
        .eq("symbol_id", symbolData.id)
        .lt("ts", split.date)
        .is("adjusted_for", null);

      if (barsError) {
        console.error(
          `[adjust-bars] Error fetching bars for ${split.symbol}:`,
          barsError,
        );
        continue;
      }

      if (!bars || bars.length === 0) {
        console.log(
          `[adjust-bars] No unadjusted bars found for ${split.symbol}`,
        );

        // Mark corporate action as processed even if no bars to adjust
        await supabase
          .from("corporate_actions")
          .update({
            bars_adjusted: true,
            adjusted_at: new Date().toISOString(),
          })
          .eq("id", corporateAction.id);

        results.push({
          symbol: split.symbol,
          bars_adjusted: 0,
          status: "no_bars_to_adjust",
        });
        continue;
      }

      console.log(
        `[adjust-bars] Adjusting ${bars.length} bars for ${split.symbol} with ratio ${adjustmentRatio}`,
      );

      // Apply split adjustment
      const adjustedBars = bars.map((bar) => ({
        ...bar,
        open: bar.open / adjustmentRatio,
        high: bar.high / adjustmentRatio,
        low: bar.low / adjustmentRatio,
        close: bar.close / adjustmentRatio,
        volume: bar.volume * adjustmentRatio,
        adjusted_for: corporateAction.id,
        updated_at: new Date().toISOString(),
      }));

      // Batch update in chunks of 1000
      const chunkSize = 1000;
      for (let i = 0; i < adjustedBars.length; i += chunkSize) {
        const chunk = adjustedBars.slice(i, i + chunkSize);
        const { error: updateError } = await supabase
          .from("ohlc_bars_v2")
          .upsert(chunk);

        if (updateError) {
          console.error(
            `[adjust-bars] Error updating bars chunk ${i}-${i + chunk.length}:`,
            updateError,
          );
        }
      }

      // Mark corporate action as processed
      await supabase
        .from("corporate_actions")
        .update({
          bars_adjusted: true,
          adjusted_at: new Date().toISOString(),
        })
        .eq("id", corporateAction.id);

      console.log(
        `[adjust-bars] Successfully adjusted ${bars.length} bars for ${split.symbol}`,
      );

      results.push({
        symbol: split.symbol,
        bars_adjusted: bars.length,
        ratio: adjustmentRatio,
        status: "success",
      });
    }

    return new Response(
      JSON.stringify({
        success: true,
        results,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  } catch (error) {
    console.error("[adjust-bars] Error:", error);
    return new Response(
      JSON.stringify({
        error: error instanceof Error ? error.message : "Unknown error",
      }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
});
