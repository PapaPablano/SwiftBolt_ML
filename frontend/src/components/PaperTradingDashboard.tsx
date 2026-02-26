import React, { useState, useEffect, useMemo } from 'react';
import { TrendingUp, TrendingDown, DollarSign, Target, AlertCircle, RefreshCw } from 'lucide-react';

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

interface PaperPosition {
  id: string;
  strategy_name: string;
  symbol_id: string;
  entry_price: number;
  current_price: number;
  quantity: number;
  direction: 'long' | 'short';
  entry_time: string;
  stop_loss_price: number;
  take_profit_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

interface PaperTrade {
  id: string;
  strategy_name: string;
  symbol_id: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  direction: 'long' | 'short';
  entry_time: string;
  exit_time: string;
  pnl: number;
  pnl_pct: number;
  duration_hours: number;
  close_reason: string;
}

interface PerformanceMetrics {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  largest_win: number;
  largest_loss: number;
  profit_factor: number;
  total_pnl: number;
  total_pnl_pct: number;
  max_drawdown: number;
  sharpe_ratio: number;
  consecutive_wins: number;
  consecutive_losses: number;
}

interface BacktestComparison {
  backtest_pnl: number;
  paper_trading_pnl: number;
  difference: number;
  backtest_win_rate: number;
  paper_trading_win_rate: number;
  divergence_pct: number;
}

interface PaperTradingDashboardProps {
  strategyId?: string;
  onRefresh?: () => void;
  autoRefreshInterval?: number; // milliseconds
}

// ============================================================================
// PERFORMANCE CALCULATION HELPERS
// ============================================================================

function calculateMetrics(trades: PaperTrade[]): PerformanceMetrics {
  if (trades.length === 0) {
    return {
      total_trades: 0,
      winning_trades: 0,
      losing_trades: 0,
      win_rate: 0,
      avg_win: 0,
      avg_loss: 0,
      largest_win: 0,
      largest_loss: 0,
      profit_factor: 0,
      total_pnl: 0,
      total_pnl_pct: 0,
      max_drawdown: 0,
      sharpe_ratio: 0,
      consecutive_wins: 0,
      consecutive_losses: 0,
    };
  }

  const winningTrades = trades.filter((t) => t.pnl > 0);
  const losingTrades = trades.filter((t) => t.pnl < 0);

  const winRate = (winningTrades.length / trades.length) * 100;
  const avgWin = winningTrades.length > 0 ? winningTrades.reduce((sum, t) => sum + t.pnl, 0) / winningTrades.length : 0;
  const avgLoss = losingTrades.length > 0 ? losingTrades.reduce((sum, t) => sum + t.pnl, 0) / losingTrades.length : 0;
  const largestWin = Math.max(...winningTrades.map((t) => t.pnl), 0);
  const largestLoss = Math.min(...losingTrades.map((t) => t.pnl), 0);
  const profitFactor = avgWin && avgLoss ? Math.abs(avgWin / avgLoss) : 0;
  const totalPnl = trades.reduce((sum, t) => sum + t.pnl, 0);
  const totalPnlPct = (totalPnl / 10000) * 100; // Assuming 10000 starting capital

  // Calculate max drawdown
  let maxDrawdown = 0;
  let peak = 10000;
  let runningBalance = 10000;
  for (const trade of trades) {
    runningBalance += trade.pnl;
    if (runningBalance > peak) {
      peak = runningBalance;
    }
    const drawdown = ((peak - runningBalance) / peak) * 100;
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown;
    }
  }

  // Simplified Sharpe Ratio (ideally would use daily returns)
  const returns = trades.map((t) => t.pnl_pct);
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length;
  const stdDev = Math.sqrt(variance);
  const sharpeRatio = stdDev > 0 ? (avgReturn / stdDev) * Math.sqrt(252) : 0;

  // Consecutive wins/losses
  let consecutiveWins = 0;
  let consecutiveLosses = 0;
  let maxConsecutiveWins = 0;
  let maxConsecutiveLosses = 0;

  for (const trade of trades) {
    if (trade.pnl > 0) {
      consecutiveWins++;
      consecutiveLosses = 0;
      maxConsecutiveWins = Math.max(maxConsecutiveWins, consecutiveWins);
    } else {
      consecutiveLosses++;
      consecutiveWins = 0;
      maxConsecutiveLosses = Math.max(maxConsecutiveLosses, consecutiveLosses);
    }
  }

  return {
    total_trades: trades.length,
    winning_trades: winningTrades.length,
    losing_trades: losingTrades.length,
    win_rate: winRate,
    avg_win: avgWin,
    avg_loss: Math.abs(avgLoss),
    largest_win: largestWin,
    largest_loss: Math.abs(largestLoss),
    profit_factor: profitFactor,
    total_pnl: totalPnl,
    total_pnl_pct: totalPnlPct,
    max_drawdown: maxDrawdown,
    sharpe_ratio: sharpeRatio,
    consecutive_wins: maxConsecutiveWins,
    consecutive_losses: maxConsecutiveLosses,
  };
}

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

interface PositionsTableProps {
  positions: PaperPosition[];
}

function PositionsTable({ positions }: PositionsTableProps) {
  if (positions.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p className="text-sm">No open positions</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="px-4 py-2 text-left text-gray-700 font-medium">Strategy</th>
            <th className="px-4 py-2 text-left text-gray-700 font-medium">Symbol</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">Dir</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">Entry</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">Current</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">Qty</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">P&L</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">SL</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">TP</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {positions.map((pos) => (
            <tr key={pos.id} className="hover:bg-gray-50">
              <td className="px-4 py-2 text-gray-900">{pos.strategy_name}</td>
              <td className="px-4 py-2 font-mono text-gray-700">{pos.symbol_id}</td>
              <td className="px-4 py-2 text-right">
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    pos.direction === 'long'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {pos.direction.toUpperCase()}
                </span>
              </td>
              <td className="px-4 py-2 text-right font-mono text-gray-700">
                ${pos.entry_price.toFixed(2)}
              </td>
              <td className="px-4 py-2 text-right font-mono text-gray-700">
                ${pos.current_price.toFixed(2)}
              </td>
              <td className="px-4 py-2 text-right font-mono text-gray-700">{pos.quantity}</td>
              <td
                className={`px-4 py-2 text-right font-mono font-medium ${
                  pos.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                }`}
              >
                ${pos.unrealized_pnl.toFixed(2)} ({pos.unrealized_pnl_pct.toFixed(2)}%)
              </td>
              <td className="px-4 py-2 text-right font-mono text-gray-700">
                ${pos.stop_loss_price.toFixed(2)}
              </td>
              <td className="px-4 py-2 text-right font-mono text-gray-700">
                ${pos.take_profit_price.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface TradesHistoryProps {
  trades: PaperTrade[];
  limit?: number;
}

function TradesHistory({ trades, limit = 10 }: TradesHistoryProps) {
  const displayTrades = trades.slice(0, limit);

  if (displayTrades.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p className="text-sm">No closed trades yet</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="px-4 py-2 text-left text-gray-700 font-medium">Strategy</th>
            <th className="px-4 py-2 text-left text-gray-700 font-medium">Symbol</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">Dir</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">Entry</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">Exit</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">P&L</th>
            <th className="px-4 py-2 text-left text-gray-700 font-medium">Reason</th>
            <th className="px-4 py-2 text-right text-gray-700 font-medium">Duration</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {displayTrades.map((trade) => (
            <tr key={trade.id} className="hover:bg-gray-50">
              <td className="px-4 py-2 text-gray-900">{trade.strategy_name}</td>
              <td className="px-4 py-2 font-mono text-gray-700">{trade.symbol_id}</td>
              <td className="px-4 py-2 text-right">
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    trade.direction === 'long'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {trade.direction.toUpperCase()}
                </span>
              </td>
              <td className="px-4 py-2 text-right font-mono text-gray-700">
                ${trade.entry_price.toFixed(2)}
              </td>
              <td className="px-4 py-2 text-right font-mono text-gray-700">
                ${trade.exit_price.toFixed(2)}
              </td>
              <td
                className={`px-4 py-2 text-right font-mono font-medium ${
                  trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'
                }`}
              >
                ${trade.pnl.toFixed(2)} ({trade.pnl_pct.toFixed(2)}%)
              </td>
              <td className="px-4 py-2 text-gray-700 text-xs">
                <span
                  className={`px-2 py-1 rounded ${
                    trade.close_reason === 'TP_HIT'
                      ? 'bg-green-100 text-green-800'
                      : trade.close_reason === 'SL_HIT'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-blue-100 text-blue-800'
                  }`}
                >
                  {trade.close_reason}
                </span>
              </td>
              <td className="px-4 py-2 text-right text-gray-700">{trade.duration_hours}h</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface MetricsGridProps {
  metrics: PerformanceMetrics;
}

function MetricsGrid({ metrics }: MetricsGridProps) {
  const metricCards = [
    { label: 'Total Trades', value: metrics.total_trades, format: 'number' },
    { label: 'Win Rate', value: metrics.win_rate, format: 'percent', color: 'blue' },
    { label: 'Total P&L', value: metrics.total_pnl, format: 'currency', color: metrics.total_pnl >= 0 ? 'green' : 'red' },
    { label: 'Max Drawdown', value: -metrics.max_drawdown, format: 'percent', color: 'orange' },
    { label: 'Profit Factor', value: metrics.profit_factor, format: 'decimal', minFractionDigits: 2 },
    { label: 'Sharpe Ratio', value: metrics.sharpe_ratio, format: 'decimal', minFractionDigits: 2 },
    { label: 'Avg Win', value: metrics.avg_win, format: 'currency', color: 'green' },
    { label: 'Avg Loss', value: -metrics.avg_loss, format: 'currency', color: 'red' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {metricCards.map((card) => {
        let displayValue = '';
        if (card.format === 'currency') {
          displayValue = `$${card.value.toFixed(2)}`;
        } else if (card.format === 'percent') {
          displayValue = `${card.value.toFixed(1)}%`;
        } else if (card.format === 'decimal') {
          displayValue = card.value.toFixed(card.minFractionDigits || 2);
        } else {
          displayValue = card.value.toString();
        }

        return (
          <div
            key={card.label}
            className={`p-4 rounded-lg border-2 ${
              card.color === 'green'
                ? 'border-green-200 bg-green-50'
                : card.color === 'red'
                  ? 'border-red-200 bg-red-50'
                  : card.color === 'orange'
                    ? 'border-orange-200 bg-orange-50'
                    : 'border-blue-200 bg-blue-50'
            }`}
          >
            <p className="text-xs text-gray-600 font-medium mb-1">{card.label}</p>
            <p
              className={`text-lg font-bold ${
                card.color === 'green'
                  ? 'text-green-700'
                  : card.color === 'red'
                    ? 'text-red-700'
                    : card.color === 'orange'
                      ? 'text-orange-700'
                      : 'text-blue-700'
              }`}
            >
              {displayValue}
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const PaperTradingDashboard: React.FC<PaperTradingDashboardProps> = ({
  strategyId,
  onRefresh,
  autoRefreshInterval = 60000, // Default: 1 minute
}) => {
  // Mock data for demonstration
  const [positions, setPositions] = useState<PaperPosition[]>([
    {
      id: 'pos_1',
      strategy_name: 'SuperTrend Strategy',
      symbol_id: 'AAPL',
      entry_price: 150,
      current_price: 155,
      quantity: 10,
      direction: 'long',
      entry_time: '2026-02-26T09:30:00Z',
      stop_loss_price: 147,
      take_profit_price: 160,
      unrealized_pnl: 50,
      unrealized_pnl_pct: 3.33,
    },
  ]);

  const [trades, setTrades] = useState<PaperTrade[]>([
    {
      id: 'trade_1',
      strategy_name: 'RSI Oversold',
      symbol_id: 'MSFT',
      entry_price: 300,
      exit_price: 305,
      quantity: 5,
      direction: 'long',
      entry_time: '2026-02-25T10:00:00Z',
      exit_time: '2026-02-25T14:30:00Z',
      pnl: 25,
      pnl_pct: 1.67,
      duration_hours: 4.5,
      close_reason: 'TP_HIT',
    },
    {
      id: 'trade_2',
      strategy_name: 'SuperTrend Strategy',
      symbol_id: 'GOOGL',
      entry_price: 100,
      exit_price: 98,
      quantity: 8,
      direction: 'long',
      entry_time: '2026-02-24T11:00:00Z',
      exit_time: '2026-02-25T09:00:00Z',
      pnl: -16,
      pnl_pct: -2.0,
      duration_hours: 22,
      close_reason: 'SL_HIT',
    },
  ]);

  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [isLoading, setIsLoading] = useState(false);

  // Calculate metrics
  const metrics = useMemo(() => calculateMetrics(trades), [trades]);

  // Auto-refresh effect
  useEffect(() => {
    if (autoRefreshInterval <= 0) return;

    const interval = setInterval(() => {
      handleRefresh();
    }, autoRefreshInterval);

    return () => clearInterval(interval);
  }, [autoRefreshInterval]);

  const handleRefresh = async () => {
    setIsLoading(true);
    try {
      // In production, fetch from API
      // await fetchPositions();
      // await fetchTrades();
      setLastRefresh(new Date());
    } finally {
      setIsLoading(false);
    }

    if (onRefresh) {
      onRefresh();
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <TrendingUp className="text-blue-600" size={28} />
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Paper Trading Dashboard</h2>
            <p className="text-sm text-gray-600">Last refreshed: {lastRefresh.toLocaleTimeString()}</p>
          </div>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isLoading}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
            isLoading
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          <RefreshCw size={18} className={isLoading ? 'animate-spin' : ''} />
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Performance Metrics */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Performance Overview</h3>
        <MetricsGrid metrics={metrics} />
      </div>

      {/* Open Positions */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Target className="text-green-600" size={20} />
          <h3 className="text-lg font-semibold text-gray-900">Open Positions ({positions.length})</h3>
        </div>
        <div className="bg-gray-50 rounded-lg p-4 overflow-hidden">
          <PositionsTable positions={positions} />
        </div>
      </div>

      {/* Trades History */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <DollarSign className="text-blue-600" size={20} />
          <h3 className="text-lg font-semibold text-gray-900">Closed Trades ({trades.length})</h3>
        </div>
        <div className="bg-gray-50 rounded-lg p-4 overflow-hidden">
          <TradesHistory trades={trades} limit={10} />
        </div>
      </div>

      {/* Key Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-gray-200">
        <div className="p-4 bg-gradient-to-br from-green-50 to-green-100 rounded-lg border border-green-200">
          <div className="flex items-start gap-3">
            <TrendingUp className="text-green-600 mt-1" size={20} />
            <div>
              <p className="text-sm text-gray-600 font-medium">Winning Trades</p>
              <p className="text-2xl font-bold text-green-700">{metrics.winning_trades}</p>
              <p className="text-xs text-gray-600 mt-1">
                Largest win: ${metrics.largest_win.toFixed(2)}
              </p>
            </div>
          </div>
        </div>

        <div className="p-4 bg-gradient-to-br from-red-50 to-red-100 rounded-lg border border-red-200">
          <div className="flex items-start gap-3">
            <TrendingDown className="text-red-600 mt-1" size={20} />
            <div>
              <p className="text-sm text-gray-600 font-medium">Losing Trades</p>
              <p className="text-2xl font-bold text-red-700">{metrics.losing_trades}</p>
              <p className="text-xs text-gray-600 mt-1">
                Largest loss: -${metrics.largest_loss.toFixed(2)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Note */}
      <div className="p4 bg-blue-50 border border-blue-200 rounded-lg flex items-start gap-3">
        <AlertCircle className="text-blue-600 mt-0.5 flex-shrink-0" size={18} />
        <div className="text-sm text-blue-700">
          <p className="font-medium">Paper Trading Mode</p>
          <p className="text-xs text-blue-600 mt-1">
            This dashboard shows simulated trading results. No real money is at risk.
          </p>
        </div>
      </div>
    </div>
  );
};

export default PaperTradingDashboard;
