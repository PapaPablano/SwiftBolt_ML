// scanner-watchlist: Scan watchlist symbols for alerts and ML signals
// POST /scanner-watchlist
// Body: { "symbols": ["AAPL", "MSFT", "NVDA"] }
//
// Returns watchlist items with ML labels, alert counts, and recent alerts

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface WatchlistItemResponse {
  symbol: string;
  assetType: string;
  mlLabel?: "Bullish" | "Neutral" | "Bearish";
  mlConfidence?: number;
  unreadAlertCount: number;
  hasCriticalAlert: boolean;
  lastPrice?: number;
  priceChange?: number;
  priceChangePercent?: number;
}

interface ScannerAlert {
  id: string;
  symbol: string;
  triggeredAt: string;
  conditionLabel: string;
  conditionType?: "technical" | "ml" | "volume" | "price";
  severity: "info" | "warning" | "critical";
  details?: Record<string, any>;
  isRead: boolean;
}

interface ScannerWatchlistResponse {
  watchlist: WatchlistItemResponse[];
  alerts: ScannerAlert[];
  scannedAt: string;
}

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow POST requests
  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    // Parse request body
    const body = await req.json();
    const symbols: string[] = body.symbols || [];

    if (!symbols || symbols.length === 0) {
      return errorResponse("Missing or empty symbols array", 400);
    }

    const supabase = getSupabaseClient();
    const watchlistItems: WatchlistItemResponse[] = [];
    const allAlerts: ScannerAlert[] = [];

    // Process each symbol
    for (const symbol of symbols) {
      const ticker = symbol.trim().toUpperCase();

      // Get symbol info
      const { data: symbolData } = await supabase
        .from("symbols")
        .select("id, ticker, asset_type, description")
        .eq("ticker", ticker)
        .single();

      if (!symbolData) {
        console.warn(`[Scanner] Symbol not found: ${ticker}`);
        continue;
      }

      const symbolId = symbolData.id;

      // Get ML forecast (latest)
      const { data: forecastData } = await supabase
        .from("ml_forecasts")
        .select("overall_label, confidence")
        .eq("symbol_id", symbolId)
        .order("run_at", { ascending: false })
        .limit(1)
        .single();

      // Get alerts for this symbol (last 7 days)
      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

      const { data: alertsData } = await supabase
        .from("scanner_alerts")
        .select("*")
        .eq("symbol_id", symbolId)
        .gte("triggered_at", sevenDaysAgo.toISOString())
        .order("triggered_at", { ascending: false });

      // Count unread alerts
      const unreadAlerts = (alertsData || []).filter(
        (alert: any) => !alert.dismissed && !alert.is_read
      );
      const hasCritical = unreadAlerts.some((alert: any) => alert.severity === "critical");

      // Get latest quote (simplified - would use quotes table in production)
      const { data: latestBar } = await supabase
        .from("ohlc_bars")
        .select("close, ts")
        .eq("symbol_id", symbolId)
        .eq("timeframe", "d1")
        .order("ts", { ascending: false })
        .limit(2);

      let lastPrice: number | undefined;
      let priceChange: number | undefined;
      let priceChangePercent: number | undefined;

      if (latestBar && latestBar.length >= 2) {
        lastPrice = latestBar[0].close;
        const prevClose = latestBar[1].close;
        priceChange = lastPrice - prevClose;
        priceChangePercent = (priceChange / prevClose) * 100;
      }

      // Build watchlist item
      watchlistItems.push({
        symbol: ticker,
        assetType: symbolData.asset_type,
        mlLabel: forecastData?.overall_label,
        mlConfidence: forecastData?.confidence,
        unreadAlertCount: unreadAlerts.length,
        hasCriticalAlert: hasCritical,
        lastPrice,
        priceChange,
        priceChangePercent,
      });

      // Add alerts to response
      if (alertsData && alertsData.length > 0) {
        for (const alert of alertsData) {
          allAlerts.push({
            id: alert.id,
            symbol: ticker,
            triggeredAt: alert.triggered_at,
            conditionLabel: alert.condition_label,
            conditionType: alert.condition_type,
            severity: alert.severity,
            details: alert.details,
            isRead: alert.dismissed || alert.is_read || false,
          });
        }
      }
    }

    const response: ScannerWatchlistResponse = {
      watchlist: watchlistItems,
      alerts: allAlerts,
      scannedAt: new Date().toISOString(),
    };

    console.log(
      `[Scanner] Scanned ${watchlistItems.length} symbols, ` +
        `found ${allAlerts.length} alerts`
    );

    return jsonResponse(response);
  } catch (err) {
    console.error("[Scanner] Unexpected error:", err);
    return errorResponse(
      `Internal server error: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
