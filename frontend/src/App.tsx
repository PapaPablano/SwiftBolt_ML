/**
 * Main Application Component
 * ==========================
 * 
 * Root component for SwiftBolt Forecast Charts.
 */

import { useState, useRef, useEffect } from 'react';
import { createChart } from 'lightweight-charts';
import { ChartWithIndicators } from './components/ChartWithIndicators';
import type { BacktestResult } from './components/StrategyBacktestPanel';
import { dedupeEquityCurve } from './components/StrategyBacktestPanel';

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState('AAPL');
  const [selectedHorizon, setSelectedHorizon] = useState('1D');
  const [startDate, setStartDate] = useState<Date>(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 1);
    return d;
  });
  const [endDate, setEndDate] = useState<Date>(new Date());
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const equityChartRef = useRef<HTMLDivElement | null>(null);
  const equityChartInstanceRef = useRef<ReturnType<typeof createChart> | null>(null);

  const symbols = ['AAPL', 'NVDA', 'TSLA', 'CRWD', 'MU', 'PLTR', 'AMD', 'GOOG'];

  // Real equity curve line chart (replaces div-bar sparkline)
  useEffect(() => {
    if (!equityChartRef.current) return;
    equityChartInstanceRef.current?.remove();
    equityChartInstanceRef.current = null;
    if (!backtestResult?.equityCurve?.length) return;
    const el = equityChartRef.current;
    const chart = createChart(el, {
      layout: { background: { color: '#111827' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#374151' }, horzLines: { color: '#374151' } },
      timeScale: { borderColor: '#374151' },
      height: 160,
    });
    equityChartInstanceRef.current = chart;
    const lineSeries = chart.addLineSeries({ color: '#3b82f6', lineWidth: 2 });
    const deduped = dedupeEquityCurve(backtestResult.equityCurve);
    lineSeries.setData(deduped.map((p) => ({ time: p.time, value: p.value })));
    chart.timeScale().fitContent();
    return () => {
      chart.remove();
      equityChartInstanceRef.current = null;
    };
  }, [backtestResult?.equityCurve]);

  const daysFromRange = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));

  return (
    <div className="min-h-screen bg-gray-950 p-4 md:p-8 flex flex-col">
      <div className="mx-auto max-w-7xl flex-grow">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-white">
            SwiftBolt <span className="text-blue-500">Forecast Charts</span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Multi-timeframe analysis with strategy backtesting
          </p>
        </div>

        {/* Controls */}
        <div className="mb-6 flex flex-wrap gap-4 items-end">
          {/* Symbol */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">Symbol</label>
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="rounded bg-gray-800 px-3 py-2 text-white border border-gray-700 text-sm"
            >
              {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {/* Timeframe */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">Timeframe</label>
            <select
              value={selectedHorizon}
              onChange={(e) => setSelectedHorizon(e.target.value)}
              className="rounded bg-gray-800 px-3 py-2 text-white border border-gray-700 text-sm"
            >
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1D">1D</option>
            </select>
          </div>

          {/* Date Range */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">Start Date</label>
            <input
              type="date"
              value={startDate.toISOString().split('T')[0]}
              onChange={(e) => setStartDate(new Date(e.target.value))}
              className="rounded bg-gray-800 px-3 py-2 text-white border border-gray-700 text-sm"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">End Date</label>
            <input
              type="date"
              value={endDate.toISOString().split('T')[0]}
              onChange={(e) => setEndDate(new Date(e.target.value))}
              className="rounded bg-gray-800 px-3 py-2 text-white border border-gray-700 text-sm"
            />
          </div>

          {/* Days info */}
          <div className="text-xs text-gray-500 pb-2">
            {daysFromRange} days
          </div>
        </div>

        {/* Chart with Tabs (Analysis, Pivots, Strategy) */}
        <ChartWithIndicators
          symbol={selectedSymbol}
          horizon={selectedHorizon}
          daysBack={daysFromRange > 0 ? daysFromRange : 30}
          startDate={startDate}
          endDate={endDate}
          backtestResult={backtestResult}
          onBacktestComplete={setBacktestResult}
          onDateRangeChange={(start, end) => {
            setStartDate(start);
            setEndDate(end);
          }}
        />

        {/* Results Section - Live backtest results (same data as Strategy tab) */}
        <div className="mt-6 bg-gray-800 rounded-xl p-6 shadow-lg">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-white">Strategy Performance</h2>
          </div>
          {backtestResult ? (
            <>
              {(() => {
                const displayReturnPct = backtestResult.tradeBasedReturnPct ?? backtestResult.totalReturn * 100;
                return (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Performance Comparison</h3>
                <div className="bg-gray-900 rounded-lg p-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-gray-800 p-4 rounded">
                      <div className="text-gray-400 text-sm">Total Return</div>
                      <div className={`text-2xl font-bold ${displayReturnPct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {displayReturnPct >= 0 ? '+' : ''}{displayReturnPct.toFixed(1)}%
                      </div>
                      <div className="text-xs text-gray-500 mt-1">{backtestResult.period}</div>
                    </div>
                    <div className="bg-gray-800 p-4 rounded">
                      <div className="text-gray-400 text-sm">Strategy vs Buy & Hold</div>
                      <div className={`text-2xl font-bold ${(displayReturnPct - (backtestResult.buyAndHoldReturn ?? 0)) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {(displayReturnPct - (backtestResult.buyAndHoldReturn ?? 0)) >= 0 ? '+' : ''}{(displayReturnPct - (backtestResult.buyAndHoldReturn ?? 0)).toFixed(1)}%
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        Buy & Hold: {(backtestResult.buyAndHoldReturn ?? 0) >= 0 ? '+' : ''}{(backtestResult.buyAndHoldReturn ?? 0).toFixed(1)}%
                      </div>
                    </div>
                    <div className="bg-gray-800 p-4 rounded">
                      <div className="text-gray-400 text-sm">Win Rate</div>
                      <div className="text-2xl font-bold text-blue-400">{(backtestResult.winRate * 100).toFixed(1)}%</div>
                      <div className="text-xs text-gray-500 mt-1">{backtestResult.winningTrades} profitable / {backtestResult.trades.length || backtestResult.totalTrades} trades</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                    <div className="bg-gray-800 p-4 rounded">
                      <div className="text-gray-400 text-sm">Sharpe Ratio</div>
                      <div className="text-2xl font-bold text-yellow-400">{backtestResult.sharpeRatio.toFixed(2)}</div>
                    </div>
                    <div className="bg-gray-800 p-4 rounded">
                      <div className="text-gray-400 text-sm">Max Drawdown</div>
                      <div className="text-2xl font-bold text-red-400" title={backtestResult.tradeBasedMaxDrawdownPct != null ? 'Worst single-trade return %' : undefined}>
                        -{(Math.abs(backtestResult.tradeBasedMaxDrawdownPct ?? backtestResult.maxDrawdown) * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>
                );
              })()}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Equity Curve</h3>
                <div ref={equityChartRef} className="h-40 bg-gray-900 rounded-lg overflow-hidden flex items-center justify-center">
                  {!(backtestResult.equityCurve && backtestResult.equityCurve.length > 0) && (
                    <div className="text-gray-500">No equity data</div>
                  )}
                </div>
              </div>
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Full Trade Log</h3>
                <div className="bg-gray-900 rounded-lg overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="px-4 py-2 text-left text-gray-400">#</th>
                        <th className="px-4 py-2 text-left text-gray-400">Entry</th>
                        <th className="px-4 py-2 text-left text-gray-400">Exit</th>
                        <th className="px-4 py-2 text-left text-gray-400">P&L</th>
                        <th className="px-4 py-2 text-left text-gray-400" title="Trade return (not % of bank)">Return %</th>
                        <th className="px-4 py-2 text-left text-gray-400">Cum. P&L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {backtestResult.trades.length === 0 ? (
                        <tr><td colSpan={6} className="px-4 py-2 text-gray-500">No trade details</td></tr>
                      ) : (
                        (() => {
                          const tradesWithCum: { t: typeof backtestResult.trades[0]; cumPnl: number }[] = [];
                          backtestResult.trades.slice(0, 20).reduce((acc, t) => {
                            const cumPnl = acc + t.pnl;
                            tradesWithCum.push({ t, cumPnl });
                            return cumPnl;
                          }, 0);
                          return tradesWithCum.map(({ t, cumPnl }, idx) => {
                            const entryNotional = t.entryPrice * t.quantity;
                            const exitNotional = t.exitPrice * t.quantity;
                            return (
                              <tr key={t.id} className="border-b border-gray-800 hover:bg-gray-800">
                                <td className="px-4 py-2 text-gray-500">{idx + 1}</td>
                                <td className="px-4 py-2 text-gray-400">${Math.round(entryNotional).toLocaleString()}</td>
                                <td className="px-4 py-2 text-gray-400">${Math.round(exitNotional).toLocaleString()}</td>
                                <td className={`px-4 py-2 ${t.isWin ? 'text-green-400' : 'text-red-400'}`}>{t.isWin ? '+' : ''}{t.pnl.toFixed(0)}</td>
                                <td className={`px-4 py-2 ${t.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>{t.pnlPercent >= 0 ? '+' : ''}{t.pnlPercent.toFixed(1)}%</td>
                                <td className={`px-4 py-2 ${cumPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>{cumPnl >= 0 ? '+' : ''}${Math.round(cumPnl).toLocaleString()}</td>
                              </tr>
                            );
                          });
                        })()
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white mb-3">Strategy Details</h3>
                <div className="bg-gray-900 rounded-lg p-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <div className="text-gray-400 text-sm">Symbol / Period</div>
                      <div className="text-white">{backtestResult.symbol} — {backtestResult.period}</div>
                    </div>
                    <div>
                      <div className="text-gray-400 text-sm">Total Trades</div>
                      <div className="text-white">{backtestResult.totalTrades}</div>
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="text-gray-500 py-8 text-center">
              Run a backtest in the <strong>Strategy</strong> tab (chart date range is used). Results will appear here and update each time you run.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-xs text-gray-600">
          SwiftBolt ML | TradingView Lightweight Charts
        </div>
      </div>
    </div>
  );
}

export default App;
