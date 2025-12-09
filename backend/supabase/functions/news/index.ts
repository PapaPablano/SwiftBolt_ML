// news: Fetch news for a symbol or general market news
// GET /news?symbol=AAPL (company news)
// GET /news (general market news)

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { fetchCompanyNews, fetchMarketNews, type NewsItem } from "../_shared/finnhub-client.ts";

// Cache staleness threshold (15 minutes)
const CACHE_TTL_MS = 15 * 60 * 1000;

interface NewsResponse {
  symbol?: string;
  items: NewsItem[];
}

interface NewsRecord {
  id: string;
  title: string;
  source: string | null;
  url: string | null;
  published_at: string;
  summary: string | null;
}

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow GET requests
  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    // Parse query parameters
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol")?.trim().toUpperCase();

    const supabase = getSupabaseClient();
    let items: NewsItem[] = [];
    let symbolId: string | null = null;

    // If symbol provided, look it up and check cache
    if (symbol) {
      // Look up symbol to get symbol_id for caching
      const { data: symbolData } = await supabase
        .from("symbols")
        .select("id")
        .eq("ticker", symbol)
        .single();

      symbolId = symbolData?.id || null;

      // Check cache if we have a symbol_id
      if (symbolId) {
        const cacheThreshold = new Date(Date.now() - CACHE_TTL_MS).toISOString();

        const { data: cachedNews } = await supabase
          .from("news_items")
          .select("id, title, source, url, published_at, summary")
          .eq("symbol_id", symbolId)
          .gte("fetched_at", cacheThreshold)
          .order("published_at", { ascending: false })
          .limit(20);

        if (cachedNews && cachedNews.length > 0) {
          console.log(`Cache hit for ${symbol} news (${cachedNews.length} items)`);
          items = cachedNews.map((item: NewsRecord) => ({
            id: item.id,
            title: item.title,
            source: item.source || "",
            url: item.url || "",
            publishedAt: item.published_at,
            summary: item.summary || undefined,
          }));

          return jsonResponse({ symbol, items } as NewsResponse);
        }
      }

      // Fetch fresh company news
      console.log(`Cache miss for ${symbol} news, fetching from Finnhub`);
      try {
        items = await fetchCompanyNews(symbol);

        // Cache results if we have a symbol_id
        if (symbolId && items.length > 0) {
          // Delete old cached news for this symbol first
          await supabase
            .from("news_items")
            .delete()
            .eq("symbol_id", symbolId);

          const newsToInsert = items.map((item) => ({
            symbol_id: symbolId,
            title: item.title,
            source: item.source,
            url: item.url,
            summary: item.summary || null,
            published_at: item.publishedAt,
            fetched_at: new Date().toISOString(),
          }));

          const { error: insertError } = await supabase
            .from("news_items")
            .insert(newsToInsert);

          if (insertError) {
            console.error("News cache insert error:", insertError);
          } else {
            console.log(`Cached ${items.length} news items for ${symbol}`);
          }
        }
      } catch (fetchError) {
        console.error("Finnhub news fetch error:", fetchError);
        return errorResponse("Failed to fetch news", 502);
      }

      return jsonResponse({ symbol, items } as NewsResponse);
    }

    // No symbol - fetch general market news
    // Check cache for general news (symbol_id IS NULL)
    const cacheThreshold = new Date(Date.now() - CACHE_TTL_MS).toISOString();

    const { data: cachedNews } = await supabase
      .from("news_items")
      .select("id, title, source, url, published_at, summary")
      .is("symbol_id", null)
      .gte("fetched_at", cacheThreshold)
      .order("published_at", { ascending: false })
      .limit(20);

    if (cachedNews && cachedNews.length > 0) {
      console.log(`Cache hit for market news (${cachedNews.length} items)`);
      items = cachedNews.map((item: NewsRecord) => ({
        id: item.id,
        title: item.title,
        source: item.source || "",
        url: item.url || "",
        publishedAt: item.published_at,
        summary: item.summary || undefined,
      }));

      return jsonResponse({ items } as NewsResponse);
    }

    // Fetch fresh market news
    console.log("Cache miss for market news, fetching from Finnhub");
    try {
      items = await fetchMarketNews("general");

      // Cache results
      if (items.length > 0) {
        // Delete old cached market news first
        await supabase
          .from("news_items")
          .delete()
          .is("symbol_id", null);

        const newsToInsert = items.map((item) => ({
          symbol_id: null,
          title: item.title,
          source: item.source,
          url: item.url,
          summary: item.summary || null,
          published_at: item.publishedAt,
          fetched_at: new Date().toISOString(),
        }));

        const { error: insertError } = await supabase
          .from("news_items")
          .insert(newsToInsert);

        if (insertError) {
          console.error("Market news cache insert error:", insertError);
        } else {
          console.log(`Cached ${items.length} market news items`);
        }
      }
    } catch (fetchError) {
      console.error("Finnhub market news fetch error:", fetchError);
      return errorResponse("Failed to fetch news", 502);
    }

    return jsonResponse({ items } as NewsResponse);
  } catch (err) {
    console.error("Unexpected error:", err);
    return errorResponse("Internal server error", 500);
  }
});
