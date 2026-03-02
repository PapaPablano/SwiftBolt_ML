import type { Strategy, BacktestResult, Trade, TradeDirection, CloseReason } from '../types/strategyBacktest';
import { isStrategyIdUuid, toChartTime, horizonToTimeframe, createDefaultConfig } from './backtestConstants';
import { strategiesApi } from '../api/strategiesApi';

const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? '';
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL ?? '';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const SUPABASE_FUNCTIONS_URL = `${SUPABASE_URL}/functions/v1`;

export type BacktestJobResult =
  | { success: true; jobId: string; status: string; createdAt: string }
  | { success: false; error: { code: 'network' | 'auth' | 'validation' | 'server' | 'not_found'; message: string } };

export const fetchStrategiesFromSupabase = async (): Promise<Strategy[]> => {
  try {
    const rows: any[] = await strategiesApi.list(SUPABASE_ANON_KEY);
    return rows.map((row: any) => ({
      id: row.id,
      name: row.name,
      description: row.description || '',
      config: row.config || createDefaultConfig(),
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    }));
  } catch {
    return [];
  }
};

export const saveStrategyToSupabase = async (
  strategy: Omit<Strategy, 'createdAt' | 'updatedAt'>
): Promise<BacktestJobResult> => {
  try {
    const data = await strategiesApi.create(
      { name: strategy.name, description: strategy.description, config: strategy.config },
      SUPABASE_ANON_KEY
    );
    if (!data?.id) {
      return { success: false, error: { code: 'server', message: 'Server error, please try again' } };
    }
    return { success: true, jobId: data.id, status: 'created', createdAt: data.created_at ?? new Date().toISOString() };
  } catch (err: any) {
    const status: number | undefined = err?.status;
    if (status === 401) return { success: false, error: { code: 'auth', message: 'Authentication required' } };
    if (status === 400) return { success: false, error: { code: 'validation', message: err?.message ?? 'Validation error' } };
    if (status != null && status >= 500) return { success: false, error: { code: 'server', message: 'Server error, please try again' } };
    return { success: false, error: { code: 'network', message: 'Network error, check connection' } };
  }
};

export const updateStrategyInSupabase = async (strategy: Strategy): Promise<boolean> => {
  if (!isStrategyIdUuid(strategy.id)) return false;
  try {
    await strategiesApi.update(
      strategy.id,
      {
        name: strategy.name,
        description: strategy.description,
        config: strategy.config,
        updated_at: new Date().toISOString(),
      },
      SUPABASE_ANON_KEY
    );
    return true;
  } catch {
    return false;
  }
};

/** Ensure strategy exists in Supabase so we have a strategy_id for backtest.
 *  Default strategies (id='1','2','3') are NOT saved — they use the preset
 *  FastAPI path. Only user-created strategies need a Supabase record. */
export async function ensureStrategyId(strategy: Strategy): Promise<string> {
  if (isStrategyIdUuid(strategy.id)) return strategy.id;
  // Default preset strategies — don't create duplicates in Supabase.
  // Return the original ID so the backtest falls through to the preset path.
  return strategy.id;
}

/** Queue a backtest job via Supabase Edge Function. Returns a typed result. */
async function queueBacktestJob(
  strategyId: string,
  symbol: string,
  startDate: string,
  endDate: string,
  timeframe: string,
  headers: Record<string, string>,
  strategyConfig?: Record<string, unknown>
): Promise<BacktestJobResult> {
  try {
    const body: Record<string, unknown> = { symbol, startDate, endDate, initialCapital: 10000, timeframe };
    if (isStrategyIdUuid(strategyId)) {
      body.strategy_id = strategyId;
    }
    // Always send inline config so the worker uses the exact conditions the user sees
    if (strategyConfig) {
      body.strategy_config = strategyConfig;
    }
    const postRes = await fetch(`${SUPABASE_FUNCTIONS_URL}/backtest-strategy`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    if (postRes.status === 401) {
      return { success: false, error: { code: 'auth', message: 'Authentication required' } };
    }
    if (postRes.status === 400) {
      return { success: false, error: { code: 'validation', message: await postRes.text() } };
    }
    if (postRes.status >= 500) {
      return { success: false, error: { code: 'server', message: 'Server error, please try again' } };
    }
    if (!postRes.ok) {
      return { success: false, error: { code: 'server', message: await postRes.text() } };
    }
    const payload = (await postRes.json()) as { job_id?: string; status?: string; created_at?: string };
    if (!payload.job_id) {
      return { success: false, error: { code: 'server', message: 'Server error, please try again' } };
    }
    return {
      success: true,
      jobId: payload.job_id,
      status: payload.status ?? 'queued',
      createdAt: payload.created_at ?? new Date().toISOString(),
    };
  } catch {
    return { success: false, error: { code: 'network', message: 'Network error, check connection' } };
  }
}

/** Poll a queued backtest job by id. Returns a typed result. */
async function pollBacktestJob(
  jobId: string,
  headers: Record<string, string>
): Promise<BacktestJobResult> {
  try {
    const getRes = await fetch(`${SUPABASE_FUNCTIONS_URL}/backtest-strategy?id=${jobId}`, {
      headers,
      cache: 'no-store',
    });
    if (getRes.status === 401) {
      return { success: false, error: { code: 'auth', message: 'Authentication required' } };
    }
    if (getRes.status === 404) {
      return { success: false, error: { code: 'not_found', message: 'Job not found' } };
    }
    if (getRes.status >= 500) {
      return { success: false, error: { code: 'server', message: 'Server error, please try again' } };
    }
    if (!getRes.ok) {
      return { success: false, error: { code: 'server', message: await getRes.text() } };
    }
    const payload = (await getRes.json()) as { status?: string; job_id?: string; created_at?: string };
    return {
      success: true,
      jobId: payload.job_id ?? jobId,
      status: payload.status ?? 'pending',
      createdAt: payload.created_at ?? new Date().toISOString(),
    };
  } catch {
    return { success: false, error: { code: 'network', message: 'Network error, check connection' } };
  }
}

/** Run backtest via Supabase (worker runs full strategy config). Polls until completed then maps result. */
async function runBacktestViaSupabase(
  strategyId: string,
  strategyDisplayId: string,
  symbol: string,
  startDate: string,
  endDate: string,
  timeframe: string,
  token?: string,
  onJobQueued?: (jobId: string) => void,
  strategyConfig?: Record<string, unknown>
): Promise<BacktestResult | null> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    apikey: SUPABASE_ANON_KEY,
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const queueResult = await queueBacktestJob(strategyId, symbol, startDate, endDate, timeframe, headers, strategyConfig);
  if (!queueResult.success) {
    console.error('[Backtest] Supabase queue error:', queueResult.error.message);
    return null;
  }
  const job_id = queueResult.jobId;
  onJobQueued?.(job_id);

  // 120 × 1.5 s = 180 s max wait. No fallback for custom strategies.
  for (let i = 0; i < 120; i++) {
    await new Promise((r) => setTimeout(r, 1500));
    const pollResult = await pollBacktestJob(job_id, headers);
    if (!pollResult.success) {
      console.error('[Backtest] Poll error:', pollResult.error.message);
      return null;
    }
    if (pollResult.status === 'failed') {
      console.error('[Backtest] Job failed');
      return null;
    }
    if (pollResult.status === 'cancelled') {
      console.log('[Backtest] Job was cancelled');
      return null;
    }
    if (pollResult.status !== 'completed') continue;

    // Fetch the full completed payload (includes result, metrics, trades).
    const completedRes = await fetch(`${SUPABASE_FUNCTIONS_URL}/backtest-strategy?id=${job_id}`, {
      headers,
      cache: 'no-store',
    });
    if (!completedRes.ok) return null;
    const statusPayload = (await completedRes.json()) as {
      status: string;
      result?: {
        metrics?: Record<string, unknown>;
        trades?: Record<string, unknown>[];
        equity_curve?: { date: string; value: number }[];
      };
      error?: string;
    };
    if (statusPayload.status === 'completed' && statusPayload.result) {
      const r = statusPayload.result;
      const metrics = r.metrics || {};
      const trades = r.trades || [];
      const equityCurve = r.equity_curve || [];

      let buyAndHoldReturn = 0;
      try {
        // TODO: route buy-and-hold price data through the chart Edge Function
        // (GET /chart) instead of calling the FastAPI endpoint directly.
        const priceRes = await fetch(
          `${API_BASE}/api/v1/chart-data/${symbol}/d1?start_date=${startDate}&end_date=${endDate}`,
          { cache: 'no-store' }
        );
        if (priceRes.ok) {
          const priceData = await priceRes.json();
          const bars = priceData.bars || [];
          if (bars.length >= 2) {
            buyAndHoldReturn =
              ((bars[bars.length - 1].close - bars[0].close) / bars[0].close) * 100;
          }
        }
      } catch (_) {}

      const tradesList: Trade[] = [];
      for (const t of trades) {
        const entryDate = String(t.entry_date ?? '').split('T')[0];
        const exitDate = String(t.exit_date ?? '').split('T')[0];
        const entryPrice = Number(t.entry_price ?? 0);
        const exitPrice = Number(t.exit_price ?? 0);
        const pnl = Number(t.pnl ?? 0);
        const qty =
          entryPrice !== exitPrice && entryPrice > 0
            ? Math.round(pnl / (exitPrice - entryPrice))
            : Number(t.quantity ?? 1);
        const pnlPercent = entryPrice ? ((exitPrice - entryPrice) / entryPrice) * 100 : 0;
        tradesList.push({
          id: `trade-${tradesList.length}`,
          entryTime: entryDate,
          exitTime: exitDate,
          entryPrice,
          exitPrice,
          quantity: qty,
          pnl,
          pnlPercent,
          isWin: pnl > 0 || pnlPercent > 0,
          direction: (t.direction as TradeDirection) ?? 'long',
          closeReason: (t.close_reason as CloseReason) ?? 'unknown',
        });
      }

      const winningTradesCount = tradesList.filter((t) => t.isWin).length;
      const firstEntryNotional =
        tradesList.length > 0 ? tradesList[0].entryPrice * tradesList[0].quantity : 0;
      const lastExitNotional =
        tradesList.length > 0
          ? tradesList[tradesList.length - 1].exitPrice * tradesList[tradesList.length - 1].quantity
          : 0;
      const tradeBasedReturnPct =
        tradesList.length > 0 && firstEntryNotional !== 0
          ? ((lastExitNotional - firstEntryNotional) / firstEntryNotional) * 100
          : undefined;
      const tradeBasedMaxDrawdownPct =
        tradesList.length > 0
          ? Math.min(...tradesList.map((t) => t.pnlPercent)) / 100
          : undefined;

      return {
        id: Date.now().toString(),
        strategyId: strategyDisplayId,
        symbol,
        period: `${startDate} to ${endDate}`,
        totalTrades: tradesList.length,
        winningTrades: winningTradesCount,
        losingTrades: tradesList.length - winningTradesCount,
        winRate: tradesList.length ? winningTradesCount / tradesList.length : 0,
        totalReturn: Number(metrics.total_return_pct ?? 0),
        tradeBasedReturnPct,
        tradeBasedMaxDrawdownPct,
        buyAndHoldReturn,
        maxDrawdown: Number(metrics.max_drawdown_pct ?? 0) / 100,
        sharpeRatio: Number(metrics.sharpe_ratio ?? 0),
        profitFactor: Number(metrics.profit_factor ?? 0),
        avgWin: Number(metrics.avg_win ?? 0),
        avgLoss: Number(metrics.avg_loss ?? 0),
        trades: tradesList,
        equityCurve: equityCurve.map((e) => ({
          time: toChartTime((e as { date?: string }).date ?? ''),
          value: e.value,
        })),
      };
    }
  }
  console.error('[Backtest] Timeout waiting for job');
  return null;
}

/** Cancel a running backtest job via PATCH. Requires auth. */
export async function cancelBacktestJob(
  jobId: string,
  token: string
): Promise<boolean> {
  try {
    const res = await fetch(`${SUPABASE_FUNCTIONS_URL}/backtest-strategy`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        apikey: SUPABASE_ANON_KEY,
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ job_id: jobId, status: 'cancelled' }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Enable paper trading for a strategy. Requires a valid session token and UUID strategy id. */
export async function deployToPaperTrading(
  strategyId: string,
  token: string
): Promise<{ success: boolean; error?: string }> {
  if (!isStrategyIdUuid(strategyId)) {
    return { success: false, error: 'Strategy must be saved before deploying' };
  }
  try {
    await strategiesApi.update(strategyId, { paper_trading_enabled: true }, token);
    return { success: true };
  } catch (err: any) {
    return { success: false, error: err?.message ?? 'Failed to enable paper trading' };
  }
}

export const runBacktestViaAPI = async (
  strategy: Strategy,
  symbol: string,
  startDate: string,
  endDate: string,
  horizon: string,
  token?: string,
  onJobQueued?: (jobId: string) => void
): Promise<BacktestResult | null> => {
  try {
    const timeframe = horizonToTimeframe(horizon);

    // Always use the Supabase worker for backtesting — it evaluates the full strategy config.
    // Send the config inline so the worker uses exactly what the user sees in the form.
    const result = await runBacktestViaSupabase(
      strategy.id, strategy.id, symbol, startDate, endDate, timeframe, token, onJobQueued,
      strategy.config as unknown as Record<string, unknown>
    );
    if (result) return result;
    throw new Error('Backtest timed out. This may be due to a cold start — click Retry to try again.');
  } catch (err) {
    console.error('[Backtest] Error:', err);
    if (err instanceof Error && err.message.includes('timed out')) throw err;
    return null;
  }
};
