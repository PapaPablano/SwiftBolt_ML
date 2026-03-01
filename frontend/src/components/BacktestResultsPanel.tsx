import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi } from 'lightweight-charts';
import type { BacktestResult } from '../types/strategyBacktest';
import { dedupeEquityCurve } from '../lib/backtestConstants';

interface BacktestResultsPanelProps {
  result: BacktestResult;
  expanded?: boolean;
  showEquityChart: boolean;
  showTrades: boolean;
  onToggleChart: () => void;
  onToggleTrades: () => void;
}

const BacktestResultsPanel: React.FC<BacktestResultsPanelProps> = ({
  result,
  expanded = false,
  showEquityChart,
  showTrades,
  onToggleChart,
  onToggleTrades,
}) => {
  const equityChartRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!showEquityChart || !equityChartRef.current) return;

    if (chartRef.current) {
      chartRef.current.remove();
    }

    const chart = createChart(equityChartRef.current, {
      layout: { background: { type: 0 as any, color: '#1f2937' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#374151' }, horzLines: { color: '#374151' } },
      width: equityChartRef.current.clientWidth,
      height: 200,
      timeScale: { borderColor: '#4b5563' },
      rightPriceScale: { borderColor: '#4b5563' },
    });

    chartRef.current = chart;

    const equitySeries = chart.addAreaSeries({
      topColor: 'rgba(34, 197, 94, 0.4)',
      bottomColor: 'rgba(34, 197, 94, 0.1)',
      lineColor: '#22c55e',
      lineWidth: 2,
    });

    const deduped = dedupeEquityCurve(result.equityCurve);
    equitySeries.setData(deduped.map((p) => ({ time: p.time as any, value: p.value })));
    chart.timeScale().fitContent();

    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [showEquityChart, result]);

  const hasTrades = result.trades.length > 0;
  const startVal = hasTrades
    ? result.trades[0].entryPrice * result.trades[0].quantity
    : (result.equityCurve?.[0]?.value ?? 0);
  const endVal = hasTrades
    ? result.trades[result.trades.length - 1].exitPrice *
      result.trades[result.trades.length - 1].quantity
    : (result.equityCurve?.[result.equityCurve.length - 1]?.value ?? 0);
  const pnlDollars = endVal - startVal;
  const pnlPct = startVal !== 0 ? (pnlDollars / startVal) * 100 : 0;

  return (
    <div className={`pt-2 border-t border-gray-700 ${expanded ? 'bg-gray-800 rounded-lg p-4' : 'space-y-2'}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-400">Results</span>
        <div className="flex gap-1">
          <button
            onClick={onToggleChart}
            className={`px-1 py-0.5 text-[10px] rounded ${showEquityChart ? 'bg-blue-600' : 'bg-gray-700'}`}
          >
            📈
          </button>
          <button
            onClick={onToggleTrades}
            className={`px-1 py-0.5 text-[10px] rounded ${showTrades ? 'bg-blue-600' : 'bg-gray-700'}`}
          >
            📋
          </button>
        </div>
      </div>

      {showEquityChart && (
        <div
          ref={equityChartRef}
          className={`rounded overflow-hidden ${expanded ? 'h-[200px]' : 'w-full h-[120px]'}`}
        />
      )}

      {/* P&L Summary */}
      <div
        className={`${expanded ? 'grid grid-cols-2 gap-4' : 'bg-gray-800 rounded p-2 border border-gray-700'}`}
      >
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-gray-400">Total P&L</span>
          <span className="text-right">
            <span
              className={`text-sm font-bold ${pnlPct >= 0 ? 'text-green-400' : 'text-red-400'}`}
            >
              {pnlPct >= 0 ? '+' : ''}
              {pnlPct.toFixed(1)}%
            </span>
            <span
              className={`text-[10px] ml-1.5 ${pnlDollars >= 0 ? 'text-green-400' : 'text-red-400'}`}
              title="End balance − Start (first entry → last exit)"
            >
              {' '}
              ({pnlDollars >= 0 ? '+' : ''}${Math.round(pnlDollars).toLocaleString()})
            </span>
          </span>
        </div>

        {/* Equity curve bars */}
        <div className={`flex items-end gap-px ${expanded ? 'h-16 mb-2' : 'h-8 mb-1'}`}>
          {result.equityCurve && result.equityCurve.length > 0 ? (
            (() => {
              const values = result.equityCurve.map((p) => p.value);
              const minVal = Math.min(...values);
              const maxVal = Math.max(...values);
              const range = maxVal - minVal || 1;
              return result.equityCurve.slice(0, 30).map((point, idx) => {
                const height = Math.max(2, ((point.value - minVal) / range) * 30);
                return (
                  <div
                    key={idx}
                    className="flex-1 rounded-t bg-blue-500"
                    style={{ height: `${height}px` }}
                    title={`${point.time}: $${point.value.toFixed(0)}`}
                  />
                );
              });
            })()
          ) : (
            <div className="text-[10px] text-gray-500">No equity data</div>
          )}
        </div>

        <div className="flex justify-between text-[10px] text-gray-500">
          <span
            title={
              result.totalTrades !== result.trades.length
                ? `${result.trades.length} round-trips (${result.totalTrades} actions)`
                : undefined
            }
          >
            Trades: {result.trades.length}
            {result.totalTrades !== result.trades.length
              ? ` (${result.totalTrades} actions)`
              : ''}
          </span>
          <span title="First trade entry notional (entry price × quantity)">
            Start: ${startVal.toFixed(0)}
          </span>
          <span title="Last trade exit notional (exit price × quantity)">
            End balance: ${endVal.toFixed(0)}
          </span>
        </div>
      </div>

      {/* Buy & Hold vs Strategy Comparison */}
      {result.equityCurve && result.equityCurve.length > 0 &&
        (() => {
          const bankStart = result.equityCurve[0].value;
          const bankEnd = result.equityCurve[result.equityCurve.length - 1].value;
          const firstTrade = result.trades.length > 0 ? result.trades[0] : null;
          const lastTrade = result.trades.length > 0 ? result.trades[result.trades.length - 1] : null;
          const entryExposure = firstTrade ? firstTrade.entryPrice * firstTrade.quantity : bankStart;
          const finalValue = lastTrade ? lastTrade.exitPrice * lastTrade.quantity : bankEnd;
          const strategyPnL =
            result.tradeBasedReturnPct != null
              ? result.tradeBasedReturnPct
              : ((bankEnd - bankStart) / bankStart) * 100;
          const buyHold = result.buyAndHoldReturn || 0;
          const vsBenchmark = strategyPnL - buyHold;
          return (
            <div className="bg-gray-800 rounded p-2 border border-gray-700">
              <div className="text-[10px] text-gray-400 mb-2">Strategy vs Buy & Hold</div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-gray-900 p-2 rounded">
                  <div className="text-[9px] text-gray-500">Entry exposure</div>
                  <div className="text-xs text-white">${entryExposure.toFixed(0)}</div>
                </div>
                <div className="bg-gray-900 p-2 rounded">
                  <div className="text-[9px] text-gray-500">Final Profit</div>
                  <div
                    className={`text-xs font-medium ${
                      finalValue - entryExposure >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {finalValue - entryExposure >= 0 ? '+' : ''}$
                    {Math.round(finalValue - entryExposure).toLocaleString()}
                  </div>
                </div>
                <div className="bg-gray-900 p-2 rounded border border-yellow-600/30">
                  <div className="text-[9px] text-yellow-500">Buy & Hold</div>
                  <div
                    className={`text-xs font-medium ${buyHold >= 0 ? 'text-green-400' : 'text-red-400'}`}
                  >
                    {buyHold >= 0 ? '+' : ''}
                    {buyHold.toFixed(1)}%
                  </div>
                </div>
                <div className="bg-gray-900 p-2 rounded border border-blue-600/30">
                  <div className="text-[9px] text-blue-400">Strategy</div>
                  <div
                    className={`text-xs font-medium ${
                      strategyPnL >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {strategyPnL >= 0 ? '+' : ''}
                    {strategyPnL.toFixed(1)}%
                  </div>
                </div>
              </div>
              <div
                className={`text-[10px] text-center mt-1 ${
                  vsBenchmark >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {vsBenchmark >= 0 ? '+' : ''}
                {vsBenchmark.toFixed(1)}% vs Buy & Hold
              </div>
            </div>
          );
        })()}

      {/* Metrics Grid */}
      <div className={`${expanded ? 'grid grid-cols-6 gap-2' : 'grid grid-cols-3 gap-1'}`}>
        <div className="bg-gray-900 p-1.5 rounded text-center">
          <div className="text-[10px] text-gray-500">Return</div>
          <div
            className={`text-xs font-medium ${
              (result.tradeBasedReturnPct ?? result.totalReturn * 100) >= 0
                ? 'text-green-400'
                : 'text-red-400'
            }`}
          >
            {(result.tradeBasedReturnPct ?? result.totalReturn * 100) >= 0 ? '+' : ''}
            {(result.tradeBasedReturnPct ?? result.totalReturn * 100).toFixed(1)}%
          </div>
        </div>
        <div className="bg-gray-900 p-1.5 rounded text-center">
          <div className="text-[10px] text-gray-500">Sharpe</div>
          <div className="text-xs text-white">{result.sharpeRatio.toFixed(2)}</div>
        </div>
        <div className="bg-gray-900 p-1.5 rounded text-center">
          <div className="text-[10px] text-gray-500">Max DD</div>
          <div
            className="text-xs text-red-400"
            title={
              result.tradeBasedMaxDrawdownPct != null
                ? 'Worst single-trade return %'
                : undefined
            }
          >
            -{(Math.abs(result.tradeBasedMaxDrawdownPct ?? result.maxDrawdown) * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Trades List */}
      {showTrades && (
        <div
          className={`overflow-y-auto ${expanded ? 'max-h-[300px] text-xs' : 'max-h-[150px] text-[10px]'}`}
        >
          <div className="grid grid-cols-5 gap-1 text-gray-500 sticky top-0 bg-gray-800 py-1">
            <span>#</span>
            <span>Entry</span>
            <span>Exit</span>
            <span>P&L</span>
            <span title="Trade return (not % of bank)">Return %</span>
          </div>
          {result.trades.length === 0 ? (
            <div className="text-center text-gray-500 py-2">No trade details available</div>
          ) : (
            result.trades.slice(0, 15).map((trade, idx) => {
              const entryNotional = trade.entryPrice * trade.quantity;
              const exitNotional = trade.exitPrice * trade.quantity;
              return (
                <div
                  key={trade.id}
                  className={`grid grid-cols-5 gap-1 py-0.5 rounded ${
                    trade.isWin ? 'bg-green-900/20' : 'bg-red-900/20'
                  }`}
                >
                  <span className="text-gray-500">{idx + 1}</span>
                  <span
                    className="text-gray-400"
                    title={`$${trade.entryPrice.toFixed(2)} × ${trade.quantity}`}
                  >
                    ${Math.round(entryNotional).toLocaleString()}
                  </span>
                  <span
                    className="text-gray-400"
                    title={`$${trade.exitPrice.toFixed(2)} × ${trade.quantity}`}
                  >
                    ${Math.round(exitNotional).toLocaleString()}
                  </span>
                  <span className={trade.isWin ? 'text-green-400' : 'text-red-400'}>
                    {trade.isWin ? '+' : ''}
                    {trade.pnl.toFixed(0)}
                  </span>
                  <span
                    className={trade.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}
                  >
                    {trade.pnlPercent >= 0 ? '+' : ''}
                    {trade.pnlPercent.toFixed(1)}%
                  </span>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};

export default BacktestResultsPanel;
