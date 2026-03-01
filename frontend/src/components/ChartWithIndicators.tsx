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
import { StrategyBacktestPanel } from './StrategyBacktestPanel';
import type { BacktestResult } from '../types/strategyBacktest';
import { useIndicators } from '../hooks/useIndicators';
import { usePivotLevels } from '../hooks/usePivotLevels';

interface ChartWithIndicatorsProps {
  symbol: string;
  horizon: string;
  daysBack?: number;
  /** Chart date range; when set, backtest uses this so results match the chart. */
  startDate?: Date;
  endDate?: Date;
  /** Live backtest result so chart can draw trade markers on price. */
  backtestResult?: BacktestResult | null;
  /** Called when backtest completes so App can show the same result in the bottom section. */
  onBacktestComplete?: (result: BacktestResult | null) => void;
  /** When Strategy panel period is changed, call with new start/end so App can update chart date range. */
  onDateRangeChange?: (start: Date, end: Date) => void;
}

export const ChartWithIndicators: React.FC<ChartWithIndicatorsProps> = ({
  symbol,
  horizon,
  daysBack = 7,
  startDate,
  endDate,
  backtestResult,
  onBacktestComplete,
  onDateRangeChange,
}) => {
  const [activePanel, setActivePanel] = useState<'analysis' | 'pivots' | 'strategy'>('strategy');

  // Fetch support/resistance indicators
  const { data, loading, error } = useIndicators(symbol, horizon);

  // Fetch pivot levels
  const { pivotLevels, metrics, loading: pivotLoading, error: pivotError } = usePivotLevels(
    symbol,
    horizon
  );

  return (
    <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
      {/* Chart (takes 3 columns on xl desktop) */}
      <div className="xl:col-span-3">
        <div className="rounded-lg bg-gray-900 p-4 md:p-6 shadow-xl border border-gray-800">
          <TradingViewChart symbol={symbol} horizon={horizon} daysBack={daysBack} srData={data} backtestTrades={backtestResult?.trades ?? null} />
        </div>
      </div>

      {/* Right Panel - Tabs for Analysis/Pivots/Strategy (wider: 2 cols) */}
      <div className="xl:col-span-2 min-w-0">
        <div className="bg-gray-900 rounded-lg p-4 shadow-xl border border-gray-800 h-full min-h-[400px]">
          <Tabs activeTab={activePanel} onTabChange={setActivePanel} />
          
          {activePanel === 'analysis' && <IndicatorPanel data={data} loading={loading} error={error} />}
          {activePanel === 'pivots' && <PivotLevelsPanel pivotLevels={pivotLevels} metrics={metrics} loading={pivotLoading} error={pivotError} />}
          {activePanel === 'strategy' && (
            <StrategyBacktestPanel
              symbol={symbol}
              horizon={horizon}
              startDate={startDate}
              endDate={endDate}
              onBacktestComplete={onBacktestComplete}
              onDateRangeChange={onDateRangeChange}
            />
          )}
        </div>
      </div>
    </div>
  );
};

// Simple tabs component
const Tabs: React.FC<{ activeTab: 'analysis' | 'pivots' | 'strategy'; onTabChange: (tab: 'analysis' | 'pivots' | 'strategy') => void }> = ({ activeTab, onTabChange }) => (
  <div className="flex gap-2 border-b border-gray-700 pb-2 mb-4">
    {(['analysis', 'pivots', 'strategy'] as const).map(tab => (
      <button
        key={tab}
        onClick={() => onTabChange(tab)}
        className={`px-2 py-1 text-xs font-medium border-b-2 ${
          activeTab === tab ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400'
        }`}
      >
        {tab === 'analysis' ? '📊 Analysis' : tab === 'pivots' ? '🎯 Pivots' : '📋 Strategy'}
      </button>
    ))}
  </div>
);
