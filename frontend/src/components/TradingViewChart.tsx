/**
 * TradingView Lightweight Charts Component
 * =========================================
 * 
 * Real-time forecast chart using TradingView Lightweight Charts library.
 * 
 * Features:
 * - OHLC candlestick chart
 * - Forecast target overlay (line series)
 * - Confidence bands (area series)
 * - Polynomial S/R regression curves
 * - Real-time WebSocket updates
 * - Responsive design
 * - Connection status indicator
 * 
 * Props:
 *   - symbol: Stock ticker (e.g., 'AAPL')
 *   - horizon: Timeframe (e.g., '1h', '4h', '1D')
 *   - daysBack: Days of historical data to load
 */

import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ISeriesApi, ColorType } from 'lightweight-charts';
import { createClient } from '@supabase/supabase-js';
import { ForecastOverlay } from '../types/chart';
import { useWebSocket } from '../hooks/useWebSocket';
import { SupportResistanceData } from '../hooks/useIndicators';

const SUPABASE_URL = 'https://cygflaemtmwiwaviclks.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs';
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

interface StrategySignal {
  time: number;
  price: number;
  type: 'buy' | 'sell';
  label?: string;
}

interface TradeMarker {
  id: string;
  entryTime: number;
  entryPrice: number;
  exitTime: number;
  exitPrice: number;
  pnl: number;
  pnlPercent: number;
  isWin: boolean;
}

interface ThresholdLine {
  price: number;
  color: string;
  label: string;
}

interface IndicatorData {
  type: 'rsi' | 'macd' | 'bb' | 'sma' | 'ema';
  data: { time: number; value: number; upper?: number; lower?: number }[];
}

/** Backtest trades with string dates (from StrategyBacktestPanel / App). Shown as markers on the candle series. */
export type BacktestTradeMarker = {
  entryTime: string;
  exitTime: string;
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  pnlPercent: number;
  isWin: boolean;
};

interface TradingViewChartProps {
  symbol: string;
  horizon: string;
  daysBack?: number;
  srData?: SupportResistanceData | null;
  strategySignals?: StrategySignal[];
  indicators?: IndicatorData[];
  trades?: TradeMarker[];
  /** Trades from backtest result (string dates). Markers are drawn on the candle series. */
  backtestTrades?: BacktestTradeMarker[] | null;
  thresholds?: ThresholdLine[];
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  symbol,
  horizon,
  daysBack = 7,
  srData = null,
  strategySignals = [],
  indicators = [],
  trades = [],
  backtestTrades = null,
  thresholds = [],
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const forecastSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const confidenceBandRef = useRef<ISeriesApi<'Area'> | null>(null);
  const indicatorSeriesRefs = useRef<Map<string, ISeriesApi<any>>>(new Map());
  const signalSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestPrice, setLatestPrice] = useState<number | null>(null);
  const [latestForecast, setLatestForecast] = useState<ForecastOverlay | null>(null);

  // WebSocket for real-time updates
  const { isConnected, lastUpdate, error: wsError } = useWebSocket(symbol, horizon);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Wait for container to have dimensions
    const container = chartContainerRef.current;
    const initialWidth = container.clientWidth || 800;
    const initialHeight = container.clientHeight || 500;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: '#1a1a1a' },
        textColor: '#e0e0e0',
      },
      grid: {
        vertLines: { color: '#2a2a2a' },
        horzLines: { color: '#2a2a2a' },
      },
      width: initialWidth,
      height: initialHeight || 500,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#3a3a3a',
      },
      rightPriceScale: {
        borderColor: '#3a3a3a',
        scaleMargins: {
          top: 0.1,
          bottom: 0.2,
        },
      },
      crosshair: {
        mode: 1, // Normal crosshair
        vertLine: {
          color: '#6a6a6a',
          width: 1,
          style: 2, // Dashed
        },
        horzLine: {
          color: '#6a6a6a',
          width: 1,
          style: 2,
        },
      },
    });

    chartRef.current = chart;

    // Add candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00c853',
      downColor: '#ff5252',
      borderUpColor: '#00c853',
      borderDownColor: '#ff5252',
      wickUpColor: '#00c853',
      wickDownColor: '#ff5252',
    });
    candleSeriesRef.current = candleSeries;

    // Add forecast target line
    const forecastSeries = chart.addLineSeries({
      color: '#0088cc',
      lineWidth: 3,
      title: 'Target Price',
      priceLineVisible: true,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 6,
    });
    forecastSeriesRef.current = forecastSeries;

    // Add confidence band (area series)
    const confidenceBand = chart.addAreaSeries({
      topColor: 'rgba(0, 136, 204, 0.3)',
      bottomColor: 'rgba(0, 136, 204, 0.05)',
      lineColor: 'rgba(0, 136, 204, 0.5)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    confidenceBandRef.current = confidenceBand;

    // Add strategy signal line series placeholder
    const signalSeries = chart.addLineSeries({
      color: 'transparent',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    signalSeriesRef.current = signalSeries;

    // Handle resize with ResizeObserver for better responsiveness
    const resizeObserver = new ResizeObserver((entries) => {
      if (chartRef.current && entries[0]) {
        const { width, height } = entries[0].contentRect;
        chartRef.current.applyOptions({
          width: width || 800,
          height: height || 500,
        });
      }
    });
    resizeObserver.observe(container);

    // Handle window resize as fallback
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth || 800,
          height: chartContainerRef.current.clientHeight || 500,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Fetch initial chart data from Supabase
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      // Map horizon to timeframe
      const timeframeMap: Record<string, string> = {
        '15m': 'm15',
        '1h': 'h1',
        '4h': 'h4',
        '1D': 'd1'
      };
      const timeframe = timeframeMap[horizon] || 'd1';

      try {
        // Get symbol ID first
        const { data: symbolData } = await supabase
          .from('symbols')
          .select('id')
          .eq('ticker', symbol.toUpperCase())
          .single();
        
        if (!symbolData) {
          console.log('[Chart] Symbol not in Supabase, using mock data');
          throw new Error('Symbol not found');
        }

        const symbolId = symbolData.id;
        
        // Calculate date range
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - daysBack);

        console.log(`[Chart] Fetching ${symbol}/${timeframe} from Supabase, daysBack: ${daysBack}`);

        // Fetch OHLC bars from Supabase with proper filters
        const { data: bars, error: barsError } = await supabase
          .from('ohlc_bars_v2')
          .select('ts, open, high, low, close, volume')
          .eq('symbol_id', symbolId)
          .eq('timeframe', timeframe)
          .eq('is_forecast', false)
          .gte('ts', startDate.toISOString())
          .lte('ts', endDate.toISOString())
          .order('ts', { ascending: true });

        if (barsError) {
          console.log('[Chart] Supabase query error:', barsError);
          throw barsError;
        }

        console.log(`[Chart] Loaded ${bars?.length || 0} bars from Supabase`);

        // Format bars for TradingView
        const formattedBars = bars?.map((bar: any) => ({
          time: Math.floor(new Date(bar.ts).getTime() / 1000) as any,
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
        })) || [];

        // Update candle series
        if (candleSeriesRef.current && formattedBars.length > 0) {
          candleSeriesRef.current.setData(formattedBars);
          const lastBar = formattedBars[formattedBars.length - 1];
          setLatestPrice(lastBar.close);
        } else {
          console.log('[Chart] No bars returned from Supabase, using mock data');
          throw new Error('No bars returned');
        }

        // Fit content to view
        if (chartRef.current) {
          chartRef.current.timeScale().fitContent();
        }

        setLoading(false);
      } catch (err) {
        console.log('[Chart] Supabase unavailable/empty, loading mock data:', err);
        // Load mock data when Supabase unavailable or empty
        const mockBars = generateMockData(symbol, daysBack);
        if (candleSeriesRef.current && mockBars.length > 0) {
          candleSeriesRef.current.setData(mockBars as any);
          if (chartRef.current) {
            chartRef.current.timeScale().fitContent();
          }
        }
        setLoading(false);
      }
    };

    fetchData();
  }, [symbol, horizon, daysBack]);

  // Generate mock data for demo
  const generateMockData = (sym: string, days: number) => {
    const bars = [];
    const now = Date.now() / 1000;
    const daySeconds = 86400;
    let basePrice = sym === 'AAPL' ? 180 : sym === 'NVDA' ? 500 : 100;
    
    for (let i = days; i >= 0; i--) {
      const time = now - (i * daySeconds);
      const volatility = 0.02;
      const change = (Math.random() - 0.5) * volatility;
      const open = basePrice * (1 + change * 0.5);
      const close = basePrice * (1 + change);
      const high = Math.max(open, close) * (1 + Math.random() * 0.01);
      const low = Math.min(open, close) * (1 - Math.random() * 0.01);
      
      bars.push({ time, open, high, low, close });
      basePrice = close;
    }
    return bars;
  };

  // Handle real-time WebSocket updates
  useEffect(() => {
    if (lastUpdate && lastUpdate.type === 'new_forecast' && lastUpdate.data) {
      const { data } = lastUpdate;

      console.log(`[Chart] Received real-time update: $${data.price.toFixed(2)} (${data.direction})`);

      // Add new forecast point to line series
      if (forecastSeriesRef.current) {
        forecastSeriesRef.current.update({
          time: data.time as any,
          value: data.price,
        });
      }

      // Update confidence band
      if (confidenceBandRef.current) {
        confidenceBandRef.current.update({
          time: data.time as any,
          value: data.price * (1 + data.confidence * 0.02),
        });
      }

      // Update latest forecast state
      setLatestForecast(data);
    }
  }, [lastUpdate]);

  // Handle strategy signals overlay
  useEffect(() => {
    if (!chartRef.current || strategySignals.length === 0) return;

    const series = chartRef.current.addLineSeries({
      color: 'transparent',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 8,
    });
    
    series.setMarkers(strategySignals.map(sig => ({
      time: sig.time as any,
      position: sig.type === 'buy' ? 'belowBar' : 'aboveBar',
      color: sig.type === 'buy' ? '#22c55e' : '#ef4444',
      shape: sig.type === 'buy' ? 'arrowUp' : 'arrowDown',
      text: sig.label || sig.type.toUpperCase(),
    })));

    signalSeriesRef.current = series;
  }, [strategySignals]);

  // Handle indicator overlays
  useEffect(() => {
    if (!chartRef.current || indicators.length === 0) return;

    indicators.forEach(ind => {
      if (ind.type === 'sma' || ind.type === 'ema') {
        const existingSeries = indicatorSeriesRefs.current.get(ind.type);
        if (existingSeries) {
          existingSeries.setData(ind.data as any);
        } else {
          const series = chartRef.current!.addLineSeries({
            color: ind.type === 'sma' ? '#f59e0b' : '#8b5cf6',
            lineWidth: 2,
            title: ind.type.toUpperCase(),
            priceLineVisible: false,
            lastValueVisible: true,
          });
          series.setData(ind.data as any);
          indicatorSeriesRefs.current.set(ind.type, series);
        }
      } else if (ind.type === 'bb') {
        const upperSeries = indicatorSeriesRefs.current.get('bb_upper');
        const lowerSeries = indicatorSeriesRefs.current.get('bb_lower');
        
        if (upperSeries && lowerSeries) {
          upperSeries.setData(ind.data.map(d => ({ time: d.time, value: d.upper || 0 })) as any);
          lowerSeries.setData(ind.data.map(d => ({ time: d.time, value: d.lower || 0 })) as any);
        } else {
          const upper = chartRef.current!.addLineSeries({
            color: '#a855f7',
            lineWidth: 1,
            lineStyle: 2,
            title: 'BB Upper',
            priceLineVisible: false,
          });
          const lower = chartRef.current!.addLineSeries({
            color: '#a855f7',
            lineWidth: 1,
            lineStyle: 2,
            title: 'BB Lower',
            priceLineVisible: false,
          });
          upper.setData(ind.data.map(d => ({ time: d.time, value: d.upper || 0 })) as any);
          lower.setData(ind.data.map(d => ({ time: d.time, value: d.lower || 0 })) as any);
          indicatorSeriesRefs.current.set('bb_upper', upper);
          indicatorSeriesRefs.current.set('bb_lower', lower);
        }
      }
    });
  }, [indicators]);

  // Handle trade markers (entry/exit points) — prefer backtest trades on candle series
  useEffect(() => {
    if (!chartRef.current || trades.length === 0) return;
    if (backtestTrades && backtestTrades.length > 0) return; // use candle-series markers instead

    const series = chartRef.current.addLineSeries({
      color: 'transparent',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 6,
    });

    const markers: any[] = [];
    trades.forEach(trade => {
      markers.push({
        time: trade.entryTime as any,
        position: 'belowBar',
        color: trade.isWin ? '#22c55e' : '#ef4444',
        shape: 'arrowUp',
        text: `ENTRY $${trade.entryPrice.toFixed(2)}`,
      });
      markers.push({
        time: trade.exitTime as any,
        position: 'aboveBar',
        color: trade.isWin ? '#22c55e' : '#ef4444',
        shape: 'arrowDown',
        text: `EXIT $${trade.exitPrice.toFixed(2)} (${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(0)})`,
      });
    });

    series.setMarkers(markers);
  }, [trades, backtestTrades]);

  // Backtest trade markers on the price (candle) chart — setMarkers on candle series
  // Defer one frame so markers apply after the render cycle that paints candle data (avoids race with loading → setData).
  useEffect(() => {
    if (!candleSeriesRef.current || !backtestTrades?.length) {
      if (candleSeriesRef.current) candleSeriesRef.current.setMarkers([]);
      return;
    }
    // Handles ISO (2024-01-15T…), space-separated (2024-01-15 10:30:00), plain date, or empty/null.
    const toBusinessDay = (raw: string | number | null | undefined): string | null => {
      if (raw == null) return null;
      const m = String(raw).trim().match(/^(\d{4}-\d{2}-\d{2})/);
      return m ? m[1] : null;
    };
    const rawMarkers = backtestTrades.flatMap(trade => [
      { time: toBusinessDay(trade.entryTime), position: 'belowBar' as const, color: '#22c55e', shape: 'arrowUp' as const, text: `BUY $${trade.entryPrice.toFixed(2)}` },
      { time: toBusinessDay(trade.exitTime), position: 'aboveBar' as const, color: '#ef4444', shape: 'arrowDown' as const, text: `SELL $${trade.exitPrice.toFixed(2)} (${trade.pnlPercent >= 0 ? '+' : ''}${trade.pnlPercent.toFixed(1)}%)` },
    ]);
    const markers = rawMarkers.filter((m): m is typeof m & { time: string } => m.time != null && m.time !== '');
    markers.sort((a, b) => (a.time > b.time ? 1 : a.time < b.time ? -1 : 0));

    const rafId = requestAnimationFrame(() => {
      if (candleSeriesRef.current) candleSeriesRef.current.setMarkers(markers);
    });
    return () => {
      cancelAnimationFrame(rafId);
      try { candleSeriesRef.current?.setMarkers([]); } catch { /* chart may already be disposed on unmount/HMR */ }
    };
  }, [backtestTrades, symbol, loading]);

  // Handle threshold lines (e.g., RSI overbought/oversold levels)
  useEffect(() => {
    if (!chartRef.current || thresholds.length === 0 || trades.length === 0) return;

    const minTime = Math.min(...trades.map(t => Math.min(t.entryTime, t.exitTime)));
    const maxTime = Math.max(...trades.map(t => Math.max(t.entryTime, t.exitTime)));

    thresholds.forEach(threshold => {
      chartRef.current!.addLineSeries({
        color: threshold.color,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: true,
        lastValueVisible: true,
        title: threshold.label,
      }).setData([
        { time: minTime as any, value: threshold.price },
        { time: maxTime as any, value: threshold.price }
      ]);
    });
  }, [thresholds, trades]);

  // Format direction emoji
  const getDirectionEmoji = (direction?: string) => {
    switch (direction) {
      case 'bullish':
        return '📈';
      case 'bearish':
        return '📉';
      default:
        return '➡️';
    }
  };

  // Format direction color
  const getDirectionColor = (direction?: string) => {
    switch (direction) {
      case 'bullish':
        return 'text-green-500';
      case 'bearish':
        return 'text-red-500';
      default:
        return 'text-yellow-500';
    }
  };

  return (
    <div className="relative w-full">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">
            {symbol} <span className="text-gray-400">| {horizon}</span>
          </h2>
          {latestPrice && (
            <div className="mt-1 text-sm text-gray-400">
              Latest Price: <span className="font-mono text-white">${latestPrice.toFixed(2)}</span>
            </div>
          )}
        </div>

        <div className="flex flex-col items-end gap-2">
          {/* Connection status */}
          <div className="flex items-center gap-2">
            <div
              className={`h-2 w-2 rounded-full ${
                isConnected ? 'animate-pulse bg-green-500' : 'bg-red-500'
              }`}
            />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Live' : 'Disconnected'}
            </span>
          </div>

          {/* Latest forecast */}
          {latestForecast && (
            <div className="text-right text-sm">
              <div className={`font-semibold ${getDirectionColor(latestForecast.direction)}`}>
                {getDirectionEmoji(latestForecast.direction)} Target: $
                {latestForecast.price.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400">
                Confidence: {(latestForecast.confidence * 100).toFixed(0)}%
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex h-[500px] items-center justify-center bg-gray-900 rounded-lg">
          <div className="text-center">
            <div className="mb-2 text-gray-400">Loading chart...</div>
            <div className="h-1 w-48 bg-gray-700 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 animate-pulse" style={{ width: '60%' }} />
            </div>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="flex h-[500px] items-center justify-center bg-gray-900 rounded-lg">
          <div className="text-center">
            <div className="text-red-500 text-lg mb-2">⚠️ {error}</div>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* WebSocket error */}
      {wsError && (
        <div className="mb-2 rounded bg-yellow-900/50 p-2 text-sm text-yellow-200">
          ⚠️ WebSocket: {wsError}
        </div>
      )}

      {/* Chart container - always rendered but hidden when loading */}
      <div
        ref={chartContainerRef}
        className={`rounded-lg ${loading || error ? 'invisible' : 'visible'}`}
        style={{ height: '400px', width: '100%', minHeight: '400px' }}
      />

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 text-sm text-gray-400">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-green-500 rounded" />
          <span>Price Up</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-red-500 rounded" />
          <span>Price Down</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-blue-500 rounded" />
          <span>Forecast Target</span>
        </div>
        {strategySignals.length > 0 && (
          <>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 bg-green-500 rounded" />
              <span>Buy Signal ({strategySignals.filter(s => s.type === 'buy').length})</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 bg-red-500 rounded" />
              <span>Sell Signal ({strategySignals.filter(s => s.type === 'sell').length})</span>
            </div>
          </>
        )}
        {indicators.map(ind => (
          <div key={ind.type} className="flex items-center gap-2">
            <div className={`h-3 w-3 rounded ${
              ind.type === 'sma' ? 'bg-amber-500' : 
              ind.type === 'ema' ? 'bg-purple-500' : 
              ind.type === 'bb' ? 'bg-fuchsia-500' : 'bg-gray-500'
            }`} />
            <span>{ind.type.toUpperCase()}</span>
          </div>
        ))}
        {trades.length > 0 && (
          <>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 bg-green-500 rounded" />
              <span>Win ({trades.filter(t => t.isWin).length})</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 bg-red-500 rounded" />
              <span>Loss ({trades.filter(t => !t.isWin).length})</span>
            </div>
          </>
        )}
        {thresholds.map((t, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="h-3 w-3 rounded" style={{ backgroundColor: t.color }} />
            <span>{t.label} ({t.price})</span>
          </div>
        ))}
      </div>
    </div>
  );
};
