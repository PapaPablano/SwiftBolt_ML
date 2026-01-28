/**
 * TradingView Chart with Indicators
 * =================================
 *
 * Combines TradingViewChart with IndicatorPanel and PivotLevelsPanel for complete analysis.
 * Displays:
 * - Polynomial S/R curves on chart
 * - Support/Resistance metrics in indicator panel
 * - Multi-period pivot levels in pivot panel
 */

import React, { useState } from 'react';
import { TradingViewChart } from './TradingViewChart';
import { IndicatorPanel } from './IndicatorPanel';
import { PivotLevelsPanel } from './PivotLevelsPanel';
import { useIndicators } from '../hooks/useIndicators';
import { usePivotLevels } from '../hooks/usePivotLevels';

interface ChartWithIndicatorsProps {
  symbol: string;
  horizon: string;
  daysBack?: number;
}

export const ChartWithIndicators: React.FC<ChartWithIndicatorsProps> = ({
  symbol,
  horizon,
  daysBack = 7,
}) => {
  const [activePanel, setActivePanel] = useState<'analysis' | 'pivots'>('analysis');

  // Fetch support/resistance indicators
  const { data, loading, error } = useIndicators(symbol, horizon);

  // Fetch pivot levels
  const { pivotLevels, metrics, loading: pivotLoading, error: pivotError, isConnected } = usePivotLevels(
    symbol,
    horizon
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Chart (takes 2 columns on desktop) */}
      <div className="lg:col-span-2">
        <div className="rounded-lg bg-gray-900 p-4 md:p-6 shadow-xl border border-gray-800">
          <TradingViewChart symbol={symbol} horizon={horizon} daysBack={daysBack} srData={data} />
        </div>
      </div>

      {/* Side Panels (takes 1 column on desktop, full width on mobile) */}
      <div className="lg:col-span-1">
        {/* Panel Tabs */}
        <div className="mb-4 flex gap-2 border-b border-gray-700">
          <button
            onClick={() => setActivePanel('analysis')}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              activePanel === 'analysis'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
          >
            📊 Analysis
          </button>
          <button
            onClick={() => setActivePanel('pivots')}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              activePanel === 'pivots'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
          >
            🎯 Pivots
          </button>
        </div>

        {/* Analysis Panel */}
        {activePanel === 'analysis' && (
          <div className="rounded-lg bg-gray-900 p-4 md:p-6 shadow-xl border border-gray-800">
            <h2 className="text-lg font-bold text-white mb-4">Support & Resistance</h2>
            <IndicatorPanel data={data} loading={loading} error={error} />
          </div>
        )}

        {/* Pivot Levels Panel */}
        {activePanel === 'pivots' && (
          <div className="rounded-lg bg-gray-900 p-4 md:p-6 shadow-xl border border-gray-800">
            <h2 className="text-lg font-bold text-white mb-4">Pivot Levels</h2>
            <PivotLevelsPanel
              pivotLevels={pivotLevels}
              metrics={metrics}
              loading={pivotLoading}
              error={pivotError}
              isConnected={isConnected}
            />
          </div>
        )}
      </div>
    </div>
  );
};
