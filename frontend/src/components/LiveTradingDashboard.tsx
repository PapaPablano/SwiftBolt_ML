import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { TrendingUp, TrendingDown, DollarSign, Target, AlertCircle, RefreshCw, XCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { liveTradingApi } from '../api/strategiesApi';

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

interface LivePosition {
  id: string;
  strategy_id: string;
  symbol_id: string;
  entry_price: number;
  current_price: number | null;
  quantity: number;
  direction: 'long' | 'short';
  entry_time: string;
  stop_loss_price: number;
  take_profit_price: number;
  status: string;
  broker_order_id: string | null;
  asset_type: string;
  contract_multiplier: number;
  pnl: number | null;
  close_reason: string | null;
  exit_price: number | null;
  exit_time: string | null;
  created_at: string;
}

interface LiveTrade {
  id: string;
  strategy_id: string;
  symbol: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  close_reason: string;
  entry_time: string;
  exit_time: string;
  contract_multiplier: number;
  asset_type: string;
  created_at: string;
}

interface BrokerStatus {
  connected: boolean;
  provider: string | null;
  has_futures: boolean;
  expires_at: string | null;
}

interface LiveTradingSummary {
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  winning_trades: number;
  losing_trades: number;
}

interface LiveTradingDashboardProps {
  onBack?: () => void;
}

// ============================================================================
// COMPONENT
// ============================================================================

export const LiveTradingDashboard: React.FC<LiveTradingDashboardProps> = ({ onBack }) => {
  const { session } = useAuth();
  const [positions, setPositions] = useState<LivePosition[]>([]);
  const [trades, setTrades] = useState<LiveTrade[]>([]);
  const [summary, setSummary] = useState<LiveTradingSummary | null>(null);
  const [broker, setBroker] = useState<BrokerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [closingId, setClosingId] = useState<string | null>(null);
  const [tab, setTab] = useState<'positions' | 'trades'>('positions');
  const visibleRef = useRef(true);

  const fetchAll = useCallback(async () => {
    if (!session?.access_token) return;
    try {
      const [pos, trd, sum, brk] = await Promise.all([
        liveTradingApi.positions(session.access_token),
        liveTradingApi.trades(session.access_token),
        liveTradingApi.summary(session.access_token),
        liveTradingApi.brokerStatus(session.access_token),
      ]);
      setPositions(pos ?? []);
      setTrades(trd ?? []);
      setSummary(sum ?? null);
      setBroker(brk ?? null);
    } catch (err) {
      console.error('[LiveTradingDashboard] Fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, [session?.access_token]);

  useEffect(() => {
    fetchAll();
    const onVis = () => { visibleRef.current = !document.hidden; };
    document.addEventListener('visibilitychange', onVis);
    const interval = setInterval(() => {
      if (visibleRef.current) fetchAll();
    }, 15000);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [fetchAll]);

  const openPositions = useMemo(
    () => positions.filter((p) => ['open', 'pending_entry', 'pending_bracket'].includes(p.status)),
    [positions],
  );

  const [closeError, setCloseError] = useState<string | null>(null);

  const handleClose = async (positionId: string) => {
    if (!session?.access_token) return;
    setClosingId(positionId);
    setCloseError(null);
    try {
      const result = await liveTradingApi.closePosition(positionId, session.access_token);
      // #183: Check application-level success, not just HTTP status
      if (result && !result.success) {
        throw new Error(result.error ?? 'Close position failed');
      }
      await fetchAll();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setCloseError(`Failed to close: ${message}`);
      console.error('[LiveTradingDashboard] Close failed:', err);
    } finally {
      setClosingId(null);
    }
  };

  if (!session) {
    return (
      <div className="p-4 text-center text-gray-400 text-sm">
        Sign in to view live trading dashboard.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-4 text-center text-gray-400 text-sm">
        Loading live trading data...
      </div>
    );
  }

  return (
    <div className="space-y-3 text-white p-3 overflow-y-auto max-h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {onBack && (
            <button onClick={onBack} className="text-gray-400 hover:text-white text-xs">
              &larr; Back
            </button>
          )}
          <h2 className="text-sm font-semibold">Live Trading</h2>
          <span className={`w-2 h-2 rounded-full ${broker?.connected ? 'bg-green-400' : 'bg-red-400'}`} />
          <span className="text-[10px] text-gray-500">
            {broker?.connected ? `${broker.provider ?? 'Connected'}` : 'Not connected'}
          </span>
        </div>
        <button
          onClick={fetchAll}
          className="p-1 text-gray-400 hover:text-white rounded"
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Close error banner */}
      {closeError && (
        <div className="flex items-center gap-2 px-2 py-1 bg-red-900/30 border border-red-700 rounded text-[10px] text-red-300">
          <AlertCircle size={12} />
          <span>{closeError}</span>
          <button onClick={() => setCloseError(null)} className="ml-auto text-red-400 hover:text-red-200">
            <XCircle size={12} />
          </button>
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-4 gap-2">
          <div className="bg-gray-800 rounded p-2 border border-gray-700">
            <div className="text-[9px] text-gray-500 uppercase">Today&apos;s P&L</div>
            <div className={`text-sm font-bold ${summary.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {summary.total_pnl >= 0 ? '+' : ''}${summary.total_pnl.toFixed(2)}
            </div>
          </div>
          <div className="bg-gray-800 rounded p-2 border border-gray-700">
            <div className="text-[9px] text-gray-500 uppercase">Win Rate</div>
            <div className="text-sm font-bold text-white">
              {(summary.win_rate * 100).toFixed(1)}%
            </div>
          </div>
          <div className="bg-gray-800 rounded p-2 border border-gray-700">
            <div className="text-[9px] text-gray-500 uppercase">Trades</div>
            <div className="text-sm font-bold text-white">{summary.total_trades}</div>
          </div>
          <div className="bg-gray-800 rounded p-2 border border-gray-700">
            <div className="text-[9px] text-gray-500 uppercase">Open</div>
            <div className="text-sm font-bold text-blue-400">{openPositions.length}</div>
          </div>
        </div>
      )}

      {/* Tab Selector */}
      <div className="flex border-b border-gray-700">
        <button
          onClick={() => setTab('positions')}
          className={`px-3 py-1 text-xs ${tab === 'positions' ? 'text-white border-b-2 border-green-500' : 'text-gray-400'}`}
        >
          Positions ({openPositions.length})
        </button>
        <button
          onClick={() => setTab('trades')}
          className={`px-3 py-1 text-xs ${tab === 'trades' ? 'text-white border-b-2 border-green-500' : 'text-gray-400'}`}
        >
          Trade History ({trades.length})
        </button>
      </div>

      {/* Positions Tab */}
      {tab === 'positions' && (
        <div className="space-y-1.5">
          {openPositions.length === 0 ? (
            <div className="text-center text-gray-500 text-xs py-4">No open positions</div>
          ) : (
            openPositions.map((pos) => {
              const currentPrice = pos.current_price ?? pos.entry_price;
              const mult = pos.contract_multiplier ?? 1;
              const unrealizedPnl = pos.direction === 'long'
                ? (currentPrice - pos.entry_price) * pos.quantity * mult
                : (pos.entry_price - currentPrice) * pos.quantity * mult;
              const pnlPct = ((currentPrice - pos.entry_price) / pos.entry_price) * 100 *
                (pos.direction === 'long' ? 1 : -1);

              return (
                <div key={pos.id} className="bg-gray-800 rounded p-2 border border-gray-700 space-y-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      {pos.direction === 'long' ? (
                        <TrendingUp size={12} className="text-green-400" />
                      ) : (
                        <TrendingDown size={12} className="text-red-400" />
                      )}
                      <span className="text-xs font-medium">{pos.symbol_id}</span>
                      <span className="text-[9px] text-gray-500 uppercase">{pos.direction}</span>
                      <span className="text-[9px] px-1 py-0.5 bg-gray-700 rounded text-gray-400">
                        {pos.status}
                      </span>
                      {pos.asset_type === 'FUTURE' && (
                        <span className="text-[9px] px-1 py-0.5 bg-yellow-900/30 rounded text-yellow-400">
                          FUT
                        </span>
                      )}
                    </div>
                    {pos.status === 'open' && (
                      <button
                        onClick={() => handleClose(pos.id)}
                        disabled={closingId === pos.id}
                        className="px-2 py-0.5 text-[10px] bg-red-600/80 text-white rounded hover:bg-red-500 disabled:opacity-50"
                      >
                        {closingId === pos.id ? '...' : 'Close'}
                      </button>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-gray-400">
                    <span>Qty: {pos.quantity}</span>
                    <span>Entry: ${pos.entry_price.toFixed(2)}</span>
                    <span>Current: ${currentPrice.toFixed(2)}</span>
                    <span>SL: ${pos.stop_loss_price.toFixed(2)}</span>
                    <span>TP: ${pos.take_profit_price.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-gray-500">
                      {new Date(pos.entry_time).toLocaleString()}
                    </span>
                    <span className={`font-medium ${unrealizedPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {unrealizedPnl >= 0 ? '+' : ''}${unrealizedPnl.toFixed(2)} ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Trades Tab */}
      {tab === 'trades' && (
        <div className="space-y-1.5">
          {trades.length === 0 ? (
            <div className="text-center text-gray-500 text-xs py-4">No trade history</div>
          ) : (
            trades.slice(0, 50).map((trade) => (
              <div key={trade.id} className="bg-gray-800 rounded p-2 border border-gray-700">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    {trade.direction === 'long' ? (
                      <TrendingUp size={12} className="text-green-400" />
                    ) : (
                      <TrendingDown size={12} className="text-red-400" />
                    )}
                    <span className="text-xs font-medium">{trade.symbol}</span>
                    <span className="text-[9px] text-gray-500 uppercase">{trade.direction}</span>
                    <span className="text-[9px] px-1 py-0.5 bg-gray-700 rounded text-gray-400">
                      {trade.close_reason}
                    </span>
                  </div>
                  <span className={`text-xs font-medium ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-gray-500 mt-0.5">
                  <span>Qty: {trade.quantity}</span>
                  <span>${trade.entry_price.toFixed(2)} &rarr; ${trade.exit_price.toFixed(2)}</span>
                  <span>{trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct.toFixed(2)}%</span>
                  <span>{new Date(trade.exit_time).toLocaleDateString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Broker disconnect */}
      {broker?.connected && (
        <div className="pt-2 border-t border-gray-700">
          <button
            onClick={async () => {
              if (!session?.access_token) return;
              try {
                const result = await liveTradingApi.disconnectBroker(session.access_token);
                // #186: Server returns 409 if open positions exist
                if (result && !result.success) {
                  setCloseError(result.error ?? 'Cannot disconnect with open positions');
                  return;
                }
                await fetchAll();
              } catch (err) {
                const message = err instanceof Error ? err.message : 'Disconnect failed';
                setCloseError(message);
              }
            }}
            className="text-[10px] text-red-400 hover:text-red-300"
          >
            Disconnect Broker
          </button>
        </div>
      )}
    </div>
  );
};

export default LiveTradingDashboard;
