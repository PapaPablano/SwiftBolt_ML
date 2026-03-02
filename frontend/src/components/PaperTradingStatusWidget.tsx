import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';

const SUPABASE_FUNCTIONS_URL = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1`;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? '';

interface StatusData {
  openPositions: number;
  totalPnl: number;
}

interface PaperTradingStatusWidgetProps {
  onNavigate?: () => void;
}

export const PaperTradingStatusWidget: React.FC<PaperTradingStatusWidgetProps> = ({ onNavigate }) => {
  const { session } = useAuth();
  const [data, setData] = useState<StatusData | null>(null);
  const visibleRef = useRef(true);

  const fetchSummary = useCallback(async () => {
    if (!session?.access_token) return;
    try {
      const res = await fetch(
        `${SUPABASE_FUNCTIONS_URL}/paper-trading-executor?action=positions`,
        {
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'apikey': SUPABASE_ANON_KEY,
          },
        },
      );
      if (!res.ok) return;
      const json = await res.json();
      const positions = json.positions ?? [];
      const totalPnl = positions.reduce((sum: number, p: { current_price?: number; entry_price: number; quantity: number; direction: string }) => {
        const current = p.current_price ?? p.entry_price;
        const raw = p.direction === 'long'
          ? (current - p.entry_price) * p.quantity
          : (p.entry_price - current) * p.quantity;
        return sum + raw;
      }, 0);
      setData({ openPositions: positions.length, totalPnl });
    } catch {
      // Silently fail — widget is informational
    }
  }, [session?.access_token]);

  useEffect(() => {
    fetchSummary();
    const onVisibility = () => { visibleRef.current = !document.hidden; };
    document.addEventListener('visibilitychange', onVisibility);
    const interval = setInterval(() => {
      if (visibleRef.current) fetchSummary();
    }, 30000);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [fetchSummary]);

  if (!session || !data) return null;

  return (
    <button
      onClick={onNavigate}
      className="w-full flex items-center justify-between px-2 py-1.5 bg-purple-900/20 border border-purple-800/40 rounded text-[11px] hover:bg-purple-900/30 transition-colors"
    >
      <span className="text-purple-300 font-medium">Paper Trading</span>
      <span className="flex items-center gap-2">
        <span className="text-gray-400">{data.openPositions} pos</span>
        <span className={data.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}>
          {data.totalPnl >= 0 ? '+' : ''}${data.totalPnl.toFixed(0)}
        </span>
      </span>
    </button>
  );
};

export default PaperTradingStatusWidget;
