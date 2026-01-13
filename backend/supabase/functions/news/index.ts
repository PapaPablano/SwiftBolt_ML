// news: Fetch news for a symbol or general market news via ProviderRouter
// GET /news?symbol=AAPL (company news)
// GET /news?symbols=AAPL,MSFT,NVDA (multi-symbol news)
// GET /news?symbol=AAPL&from=1704067200&to=1704153600 (date range filter)
// GET /news (general market news)
//
// Uses the unified ProviderRouter with rate limiting, caching, and fallback logic.
// DB persistence is used for long-term storage; ProviderRouter handles live fetching.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { getProviderRouter, getAlpacaClient } from "../_shared/providers/factory.ts";

// Cache staleness threshold (15 minutes)
const CACHE_TTL_MS = 15 * 60 * 1000;

interface NewsResponse {
  symbol?: string;
  symbols?: string[];
  count?: number;
  items: {
    id: string;
    title: string;
    source: string;
    url: string;
    publishedAt: string;
    summary?: string;
    sentiment?: "positive" | "negative" | "neutral";
    symbols?: string[];
  }[];
}

type NewsItem = NewsResponse["items"][number];

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
    const symbolsParam = url.searchParams.get("symbols");
    const fromParam = url.searchParams.get("from");
    const toParam = url.searchParams.get("to");
    const limitParam = url.searchParams.get("limit");

    const limit = limitParam ? parseInt(limitParam, 10) : 20;
    const from = fromParam ? parseInt(fromParam, 10) : undefined;
    const to = toParam ? parseInt(toParam, 10) : undefined;

    const supabase = getSupabaseClient();
    let items: NewsItem[] = [];
    let symbolId: string | null = null;

    // Multi-symbol news (direct Alpaca call, no caching)
    if (symbolsParam) {
      const symbols = symbolsParam.split(",").map(s => s.trim().toUpperCase());
      console.log(`Fetching news for ${symbols.length} symbols: ${symbols.join(", ")}`);

      const alpaca = getAlpacaClient();
      if (!alpaca) {
        return errorResponse("Alpaca client not configured for multi-symbol news", 503);
      }

      try {
        const newsItems = await alpaca.getMultiSymbolNews(symbols, limit);
        items = newsItems.map((item) => ({
          id: item.id,
          title: item.headline,
          source: item.source,
          url: item.url,
          publishedAt: new Date(item.publishedAt * 1000).toISOString(),
          summary: item.summary,
          symbols: item.symbols,
          sentiment: item.sentiment,
        }));

        return jsonResponse({
          symbols,
          count: items.length,
          items,
        });
      } catch (fetchError) {
        console.error("Multi-symbol news fetch error:", fetchError);
        return errorResponse(`Failed to fetch news: ${fetchError instanceof Error ? fetchError.message : String(fetchError)}`, 502);
      }
    }

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

      // Fetch fresh company news via ProviderRouter (or Alpaca for date range)
      console.log(`Cache miss for ${symbol} news, fetching via ProviderRouter`);
      try {
        let routerNews;

        // Use Alpaca directly for date range filtering
        if (from || to) {
          const alpaca = getAlpacaClient();
          if (alpaca) {
            routerNews = await alpaca.getNewsAdvanced({ symbol, from, to, limit });
          } else {
            const router = getProviderRouter();
            routerNews = await router.getNews({ symbol, from, to, limit });
          }
        } else {
          const router = getProviderRouter();
          routerNews = await router.getNews({ symbol, limit });
        }

        // Convert router NewsItem format to response format
        items = routerNews.map((item) => ({
          id: item.id,
          title: item.headline,
          source: item.source,
          url: item.url,
          publishedAt: new Date(item.publishedAt * 1000).toISOString(),
          summary: item.summary,
          sentiment: item.sentiment,
        }));

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
        console.error("Provider router news fetch error:", fetchError);
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

    // Fetch fresh market news via ProviderRouter
    console.log("Cache miss for market news, fetching via ProviderRouter");
    try {
      const router = getProviderRouter();
      const routerNews = await router.getNews({ limit: 20 });

      // Convert router NewsItem format to response format
      items = routerNews.map((item) => ({
        id: item.id,
        title: item.headline,
        source: item.source,
        url: item.url,
        publishedAt: new Date(item.publishedAt * 1000).toISOString(),
        summary: item.summary,
        sentiment: item.sentiment,
      }));

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
      console.error("Provider router market news fetch error:", fetchError);
      return errorResponse("Failed to fetch news", 502);
    }

    return jsonResponse({ items } as NewsResponse);
  } catch (err) {
    console.error("Unexpected error:", err);
    return errorResponse("Internal server error", 500);
  }
});
