/**
 * Intraday Service V2
 * Handles real-time intraday data updates to ohlc_bars_v2 with strict layer separation
 * 
 * Features:
 * - Writes only to TODAY with provider='tradier'
 * - Aggregates 5-min bars to daily OHLC
 * - Locks writes 5 minutes after market close (4:05 PM ET)
 * - Marks data as 'live' during market hours, 'verified' after close
 */

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { dataValidator, OHLCBarWrite } from './data-validation.ts';

interface IntradayBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface DailyAggregate {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  barCount: number;
}

export class IntradayServiceV2 {
  private supabaseUrl: string;
  private supabaseKey: string;
  private tradierToken: string;

  constructor(supabaseUrl: string, supabaseKey: string, tradierToken: string) {
    this.supabaseUrl = supabaseUrl;
    this.supabaseKey = supabaseKey;
    this.tradierToken = tradierToken;
  }

  /**
   * Check if market is currently open
   */
  private async isMarketOpen(): Promise<boolean> {
    try {
      const response = await fetch(
        'https://api.tradier.com/v1/markets/clock',
        {
          headers: {
            'Authorization': `Bearer ${this.tradierToken}`,
            'Accept': 'application/json',
          },
        }
      );

      if (!response.ok) {
        console.error('Failed to get market status:', response.statusText);
        return false;
      }

      const data = await response.json();
      return data?.clock?.state === 'open';
    } catch (error) {
      console.error('Error checking market status:', error);
      return false;
    }
  }

  /**
   * Check if intraday writes are locked (5 min after market close)
   */
  private isIntradayLocked(): boolean {
    const now = new Date();
    
    // Convert to ET (approximate - use proper timezone library in production)
    const etOffset = now.getTimezoneOffset() === 240 ? -4 : -5; // EDT vs EST
    const etHours = now.getUTCHours() + etOffset;
    const etMinutes = now.getUTCMinutes();
    
    // Market closes at 4:00 PM ET, lock at 4:05 PM ET
    const lockHour = 16;
    const lockMinute = 5;
    
    if (etHours > lockHour || (etHours === lockHour && etMinutes >= lockMinute)) {
      return true;
    }
    
    return false;
  }

  /**
   * Fetch intraday bars from Tradier (5-min intervals)
   */
  private async fetchTradierBars(
    symbol: string,
    interval: string = '5min'
  ): Promise<IntradayBar[]> {
    const today = new Date().toISOString().split('T')[0];
    
    try {
      const response = await fetch(
        `https://api.tradier.com/v1/markets/timesales?symbol=${symbol}&interval=${interval}&start=${today}&end=${today}`,
        {
          headers: {
            'Authorization': `Bearer ${this.tradierToken}`,
            'Accept': 'application/json',
          },
        }
      );

      if (!response.ok) {
        console.error(`Tradier API error for ${symbol}:`, response.statusText);
        return [];
      }

      const data = await response.json();
      const series = data?.series?.data || [];

      if (!series.length) {
        console.warn(`No intraday data for ${symbol}`);
        return [];
      }

      return series.map((bar: any) => ({
        time: bar.time,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume,
      }));
    } catch (error) {
      console.error(`Error fetching Tradier bars for ${symbol}:`, error);
      return [];
    }
  }

  /**
   * Aggregate 5-min bars to daily OHLC
   */
  private aggregateToDaily(bars: IntradayBar[]): DailyAggregate | null {
    if (!bars.length) return null;

    const sorted = [...bars].sort((a, b) => 
      new Date(a.time).getTime() - new Date(b.time).getTime()
    );

    return {
      open: sorted[0].open,
      high: Math.max(...sorted.map(b => b.high)),
      low: Math.min(...sorted.map(b => b.low)),
      close: sorted[sorted.length - 1].close,
      volume: sorted.reduce((sum, b) => sum + b.volume, 0),
      barCount: sorted.length,
    };
  }

  /**
   * Update intraday data for a symbol
   */
  async updateIntraday(symbol: string): Promise<{
    success: boolean;
    message: string;
    data?: any;
  }> {
    // Check if writes are locked
    if (this.isIntradayLocked()) {
      return {
        success: false,
        message: "Intraday writes locked after 4:05 PM ET",
      };
    }

    // Get market status
    const marketOpen = await this.isMarketOpen();
    const dataStatus = marketOpen ? 'live' : 'verified';

    // Fetch intraday bars
    const bars = await this.fetchTradierBars(symbol);
    if (!bars.length) {
      return {
        success: false,
        message: `No intraday data available for ${symbol}`,
      };
    }

    // Aggregate to daily
    const dailyAgg = this.aggregateToDaily(bars);
    if (!dailyAgg) {
      return {
        success: false,
        message: `Failed to aggregate intraday data for ${symbol}`,
      };
    }

    // Get symbol_id from database
    const supabase = createClient(this.supabaseUrl, this.supabaseKey);
    
    const { data: symbolData, error: symbolError } = await supabase
      .from('symbols')
      .select('id')
      .eq('ticker', symbol.toUpperCase())
      .single();

    if (symbolError || !symbolData) {
      return {
        success: false,
        message: `Symbol ${symbol} not found in database`,
      };
    }

    const symbolId = symbolData.id;
    const today = new Date().toISOString().split('T')[0] + 'T00:00:00Z';

    // Write raw 5-minute bars to intraday_bars table
    const intradayBarsToInsert = bars.map(bar => ({
      symbol_id: symbolId,
      timeframe: '5m',
      ts: new Date(bar.time).toISOString(),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
      provider: 'tradier',
    }));

    if (intradayBarsToInsert.length > 0) {
      const { error: intradayError } = await supabase
        .from('intraday_bars')
        .upsert(intradayBarsToInsert, {
          onConflict: 'symbol_id,timeframe,ts',
          ignoreDuplicates: false,
        });

      if (intradayError) {
        console.error('Error upserting intraday bars:', intradayError);
        // Don't fail completely, continue with daily aggregate
      } else {
        console.log(`Inserted ${intradayBarsToInsert.length} intraday bars for ${symbol}`);
      }
    }

    // Prepare bar for v2 table (daily aggregate)
    const bar: OHLCBarWrite = {
      symbol_id: symbolId,
      timeframe: 'd1',
      ts: new Date(today),
      open: dailyAgg.open,
      high: dailyAgg.high,
      low: dailyAgg.low,
      close: dailyAgg.close,
      volume: dailyAgg.volume,
      provider: 'tradier',
      is_intraday: true,
      is_forecast: false,
      data_status: dataStatus,
    };

    // Validate before writing
    const validation = dataValidator.validateWrite(bar);
    if (!validation.valid) {
      return {
        success: false,
        message: `Validation failed: ${validation.reason}`,
      };
    }

    // Upsert to ohlc_bars_v2
    const { error: upsertError } = await supabase
      .from('ohlc_bars_v2')
      .upsert([{
        ...bar,
        ts: today,
        fetched_at: new Date().toISOString(),
      }], {
        onConflict: 'symbol_id,timeframe,ts,provider,is_forecast',
      });

    if (upsertError) {
      console.error('Error upserting intraday data:', upsertError);
      return {
        success: false,
        message: `Database error: ${upsertError.message}`,
      };
    }

    return {
      success: true,
      message: `Updated intraday data for ${symbol} (${dailyAgg.barCount} bars aggregated)`,
      data: {
        symbol,
        date: today,
        ohlc: dailyAgg,
        status: dataStatus,
        marketOpen,
      },
    };
  }

  /**
   * Batch update intraday data for multiple symbols
   */
  async updateBatch(symbols: string[]): Promise<{
    successful: string[];
    failed: Array<{ symbol: string; reason: string }>;
  }> {
    const successful: string[] = [];
    const failed: Array<{ symbol: string; reason: string }> = [];

    for (const symbol of symbols) {
      const result = await this.updateIntraday(symbol);
      
      if (result.success) {
        successful.push(symbol);
        console.log(`✅ ${symbol}: ${result.message}`);
      } else {
        failed.push({ symbol, reason: result.message });
        console.warn(`❌ ${symbol}: ${result.message}`);
      }

      // Rate limiting: 120 req/min for Tradier
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    return { successful, failed };
  }
}

/**
 * Helper: Get watchlist symbols for intraday updates
 */
export async function getWatchlistSymbols(
  supabaseUrl: string,
  supabaseKey: string,
  limit: number = 100
): Promise<string[]> {
  const supabase = createClient(supabaseUrl, supabaseKey);
  
  try {
    const { data, error } = await supabase.rpc('get_all_watchlist_symbols', {
      p_limit: limit,
    });

    if (error) {
      console.error('Error fetching watchlist:', error);
      return [];
    }

    return data?.map((row: any) => row.ticker) || [];
  } catch (error) {
    console.error('Error fetching watchlist:', error);
    return [];
  }
}
