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
import axios from 'axios';
import { ChartData, ForecastOverlay } from '../types/chart';
import { useWebSocket } from '../hooks/useWebSocket';
import { SupportResistanceData } from '../hooks/useIndicators';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TradingViewChartProps {
  symbol: string;
  horizon: string;
  daysBack?: number;
  srData?: SupportResistanceData | null;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  symbol,
  horizon,
  daysBack = 7,
  srData = null,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const forecastSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const confidenceBandRef = useRef<ISeriesApi<'Area'> | null>(null);
  const supportLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const resistanceLineRef = useRef<ISeriesApi<'Line'> | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestPrice, setLatestPrice] = useState<number | null>(null);
  const [latestForecast, setLatestForecast] = useState<ForecastOverlay | null>(null);

  // WebSocket for real-time updates
  const { isConnected, lastUpdate, error: wsError } = useWebSocket(symbol, horizon);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#1a1a1a' },
        textColor: '#e0e0e0',
      },
      grid: {
        vertLines: { color: '#2a2a2a' },
        horzLines: { color: '#2a2a2a' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 500,
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

    // Add polynomial support line
    const supportLine = chart.addLineSeries({
      color: '#2962ff',
      lineWidth: 2,
      lineStyle: 0,
      title: 'Polynomial Support',
      priceLineVisible: true,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
    });
    supportLineRef.current = supportLine;

    // Add polynomial resistance line
    const resistanceLine = chart.addLineSeries({
      color: '#f23645',
      lineWidth: 2,
      lineStyle: 0,
      title: 'Polynomial Resistance',
      priceLineVisible: true,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
    });
    resistanceLineRef.current = resistanceLine;

    // Handle window resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Fetch initial chart data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await axios.get<ChartData>(
          `${API_BASE_URL}/api/v1/chart-data/${symbol}/${horizon}`,
          { params: { days_back: daysBack } }
        );

        const data = response.data;
        console.log(`[Chart] Loaded ${data.bars.length} bars, ${data.forecasts.length} forecasts`);

        // Update candle series
        if (candleSeriesRef.current && data.bars.length > 0) {
          candleSeriesRef.current.setData(data.bars);
          setLatestPrice(data.latest_price);
        }

        // Update forecast series
        if (forecastSeriesRef.current && data.forecasts.length > 0) {
          const forecastData = data.forecasts.map((f) => ({
            time: f.time,
            value: f.price,
          }));
          forecastSeriesRef.current.setData(forecastData);
          setLatestForecast(data.latest_forecast);
        }

        // Update confidence band
        if (confidenceBandRef.current && data.forecasts.length > 0) {
          const bandData = data.forecasts.map((f) => ({
            time: f.time,
            value: f.price * (1 + f.confidence * 0.02), // Upper bound (2% * confidence)
          }));
          confidenceBandRef.current.setData(bandData);
        }

        // Fit content to view
        if (chartRef.current) {
          chartRef.current.timeScale().fitContent();
        }

        setLoading(false);
      } catch (err) {
        console.error('[Chart] Error fetching ', err);
        setError('Failed to load chart data');
        setLoading(false);
      }
    };

    fetchData();
  }, [symbol, horizon, daysBack]);

  // Handle real-time WebSocket updates
  useEffect(() => {
    if (lastUpdate && lastUpdate.type === 'new_forecast' && lastUpdate.data) {
      const { data } = lastUpdate;

      console.log(`[Chart] Received real-time update: $${data.price.toFixed(2)} (${data.direction})`);

      // Add new forecast point to line series
      if (forecastSeriesRef.current) {
        forecastSeriesRef.current.update({
          time: data.time,
          value: data.price,
        });
      }

      // Update confidence band
      if (confidenceBandRef.current) {
        confidenceBandRef.current.update({
          time: data.time,
          value: data.price * (1 + data.confidence * 0.02),
        });
      }

      // Update latest forecast state
      setLatestForecast(data);
    }
  }, [lastUpdate]);

  // Update S/R lines when indicator data arrives
  useEffect(() => {
    if (!srData || !supportLineRef.current || !resistanceLineRef.current) return;

    // Get current bars to determine time for S/R levels
    if (candleSeriesRef.current && srData.polynomial_support) {
      // Add support line point at current bar
      const supportData = [
        {
          time: Math.floor(Date.now() / 1000) as any,
          value: srData.polynomial_support.level,
        },
      ];
      supportLineRef.current.setData(supportData);
    }

    if (candleSeriesRef.current && srData.polynomial_resistance) {
      // Add resistance line point at current bar
      const resistanceData = [
        {
          time: Math.floor(Date.now() / 1000) as any,
          value: srData.polynomial_resistance.level,
        },
      ];
      resistanceLineRef.current.setData(resistanceData);
    }

    console.log(
      `[Chart] Updated S/R: Support ${srData.polynomial_support?.level.toFixed(2)}, Resistance ${srData.polynomial_resistance?.level.toFixed(2)}`
    );
  }, [srData]);

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

      {/* Chart container */}
      <div
        ref={chartContainerRef}
        className={`rounded-lg ${loading || error ? 'hidden' : ''}`}
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
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-blue-300 opacity-30 rounded" />
          <span>Confidence Band</span>
        </div>
        {srData?.polynomial_support && (
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 bg-blue-400 rounded" />
            <span>Polynomial Support</span>
          </div>
        )}
        {srData?.polynomial_resistance && (
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 bg-red-400 rounded" />
            <span>Polynomial Resistance</span>
          </div>
        )}
      </div>
    </div>
  );
};
