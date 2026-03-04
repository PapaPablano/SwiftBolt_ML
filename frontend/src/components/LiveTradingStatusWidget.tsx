import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { liveTradingApi } from '../api/strategiesApi';

interface LiveStatusData {
  totalTrades: number;
  totalPnl: number;
  connected: boolean;
}

interface LiveTradingStatusWidgetProps {
  onNavigate?: () => void;
}

export const LiveTradingStatusWidget: React.FC<LiveTradingStatusWidgetProps> = ({ onNavigate }) => {
  const { session } = useAuth();
  const [data, setData] = useState<LiveStatusData | null>(null);
  const visibleRef = useRef(true);

  const fetchStatus = useCallback(async () => {
    if (!session?.access_token) return;
    try {
      // #143, #185: Use summary endpoint instead of fetching all positions
      const [summary, broker] = await Promise.all([
        liveTradingApi.summary(session.access_token),
        liveTradingApi.brokerStatus(session.access_token),
      ]);
      setData({
        totalTrades: summary?.total_trades ?? 0,
        totalPnl: summary?.total_pnl ?? 0,
        connected: broker?.connected ?? false,
      });
    } catch {
      // Widget is informational — fail silently
    }
  }, [session?.access_token]);

  useEffect(() => {
    fetchStatus();
    const onVisibility = () => { visibleRef.current = !document.hidden; };
    document.addEventListener('visibilitychange', onVisibility);
    const interval = setInterval(() => {
      if (visibleRef.current) fetchStatus();
    }, 30000);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [fetchStatus]);

  if (!session || !data) return null;

  return (
    <button
      onClick={onNavigate}
      className="w-full flex items-center justify-between px-2 py-1.5 bg-green-900/20 border border-green-800/40 rounded text-[11px] hover:bg-green-900/30 transition-colors"
    >
      <span className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${data.connected ? 'bg-green-400' : 'bg-gray-500'}`} />
        <span className="text-green-300 font-medium">Live Trading</span>
      </span>
      <span className="flex items-center gap-2">
        {data.connected ? (
          <>
            {/* #185: Show realized P&L from summary endpoint */}
            <span className="text-gray-400">{data.totalTrades} trades</span>
            <span className={data.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}>
              {data.totalPnl >= 0 ? '+' : ''}${data.totalPnl.toFixed(0)}
            </span>
          </>
        ) : (
          <span className="text-gray-500">Not connected</span>
        )}
      </span>
    </button>
  );
};

export default LiveTradingStatusWidget;
