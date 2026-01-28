/**
 * Main Application Component
 * ==========================
 * 
 * Root component for SwiftBolt Forecast Charts.
 * 
 * Features:
 * - Symbol selector (AAPL, NVDA, TSLA, etc.)
 * - Horizon/timeframe selector (15m, 1h, 4h, 1D)
 * - TradingView chart integration
 * - Responsive layout
 */

import React, { useState } from 'react';
import { TradingViewChart } from './components/TradingViewChart';

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState('AAPL');
  const [selectedHorizon, setSelectedHorizon] = useState('1h');

  // Your stock universe (from SwiftBolt ML pipeline)
  const symbols = [
    'AAPL',
    'NVDA',
    'TSLA',
    'CRWD',
    'MU',
    'PLTR',
    'AMD',
    'GOOG',
  ];

  const horizons = [
    { value: '15m', label: '15 Minutes', days: 1 },
    { value: '1h', label: '1 Hour', days: 3 },
    { value: '4h', label: '4 Hours', days: 7 },
    { value: '1D', label: '1 Day', days: 30 },
  ];

  const selectedHorizonData = horizons.find((h) => h.value === selectedHorizon);

  return (
    <div className="min-h-screen bg-gray-950 p-4 md:p-8">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-white">
            SwiftBolt <span className="text-blue-500">Forecast Charts</span>
          </h1>
          <p className="mt-2 text-gray-400">
            Real-time multi-timeframe forecast visualization powered by TradingView
          </p>
        </div>

        {/* Controls */}
        <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:gap-6">
          {/* Symbol selector */}
          <div className="flex-1">
            <label className="mb-2 block text-sm font-medium text-gray-300">
              Symbol
            </label>
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="w-full rounded-lg bg-gray-800 px-4 py-2.5 text-white border border-gray-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            >
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </div>

          {/* Horizon selector */}
          <div className="flex-1">
            <label className="mb-2 block text-sm font-medium text-gray-300">
              Timeframe
            </label>
            <select
              value={selectedHorizon}
              onChange={(e) => setSelectedHorizon(e.target.value)}
              className="w-full rounded-lg bg-gray-800 px-4 py-2.5 text-white border border-gray-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            >
              {horizons.map((h) => (
                <option key={h.value} value={h.value}>
                  {h.label}
                </option>
              ))}
            </select>
          </div>

          {/* Quick info */}
          <div className="hidden md:block text-sm text-gray-400">
            <div className="font-medium">Data Range</div>
            <div>{selectedHorizonData?.days || 7} days</div>
          </div>
        </div>

        {/* Chart */}
        <div className="rounded-lg bg-gray-900 p-4 md:p-6 shadow-xl">
          <TradingViewChart
            symbol={selectedSymbol}
            horizon={selectedHorizon}
            daysBack={selectedHorizonData?.days || 7}
          />
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>
            Powered by{' '}
            <span className="font-semibold text-gray-400">SwiftBolt ML</span> |
            Real-time forecasts with{' '}
            <span className="font-semibold text-gray-400">
              TradingView Lightweight Charts
            </span>
          </p>
          <p className="mt-1">
            Data updates automatically via WebSocket connection
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;
