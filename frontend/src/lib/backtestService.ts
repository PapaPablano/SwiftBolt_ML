import type { Strategy, BacktestResult, Trade } from '../types/strategyBacktest';
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

/** Ensure strategy exists in Supabase so we have a strategy_id for backtest. Returns strategy_id. */
export async function ensureStrategyId(strategy: Strategy): Promise<string> {
  if (isStrategyIdUuid(strategy.id)) return strategy.id;
  const result = await saveStrategyToSupabase({
    id: strategy.id,
    name: strategy.name,
    description: strategy.description,
    config: strategy.config,
  });
  return result.success ? result.jobId : strategy.id;
}

/** Queue a backtest job via Supabase Edge Function. Returns a typed result. */
async function queueBacktestJob(
  strategyId: string,
  symbol: string,
  startDate: string,
  endDate: string,
  timeframe: string,
  headers: Record<string, string>
): Promise<BacktestJobResult> {
  try {
    const postRes = await fetch(`${SUPABASE_FUNCTIONS_URL}/backtest-strategy`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ symbol, startDate, endDate, strategy_id: strategyId, initialCapital: 10000, timeframe }),
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
  timeframe: string
): Promise<BacktestResult | null> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
  };
  const queueResult = await queueBacktestJob(strategyId, symbol, startDate, endDate, timeframe, headers);
  if (!queueResult.success) {
    console.error('[Backtest] Supabase queue error:', queueResult.error.message);
    return null;
  }
  const job_id = queueResult.jobId;

  // 20 × 1.5 s = 30 s max wait; then fall through to FastAPI fallback.
  for (let i = 0; i < 20; i++) {
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

export const runBacktestViaAPI = async (
  strategy: Strategy,
  symbol: string,
  startDate: string,
  endDate: string,
  horizon: string
): Promise<BacktestResult | null> => {
  try {
    const timeframe = horizonToTimeframe(horizon);
    const strategyId = await ensureStrategyId(strategy);
    const result = await runBacktestViaSupabase(strategyId, strategy.id, symbol, startDate, endDate, timeframe);
    if (result) return result;

    // Fallback: FastAPI preset (only runs one of 3 presets; used if Supabase fails)
    const strategyType = strategy.config.entryConditions[0]?.type;
    let apiStrategy = 'supertrend_ai';
    if (strategyType === 'sma_cross') apiStrategy = 'sma_crossover';
    else if (
      strategyType === 'price_breakout' ||
      strategyType === 'volume_spike' ||
      strategyType === 'ml_signal'
    )
      apiStrategy = 'buy_and_hold';

    const response = await fetch(`${API_BASE}/api/v1/backtest-strategy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
      body: JSON.stringify({
        symbol,
        strategy: apiStrategy,
        startDate,
        endDate,
        timeframe,
        initialCapital: 10000,
        params: strategy.config.entryConditions[0]?.params || {},
      }),
    });
    if (!response.ok) {
      console.error('[Backtest] FastAPI error:', await response.text());
      return null;
    }
    const data = await response.json();
    if (!data?.symbol) return null;

    const metrics = data.metrics || {};
    const equityCurve = data.equityCurve || [];

    let buyAndHoldReturn = 0;
    try {
      // TODO: route buy-and-hold price data through the chart Edge Function
      // (GET /chart) instead of calling the FastAPI endpoint directly.
      const priceResponse = await fetch(
        `${API_BASE}/api/v1/chart-data/${symbol}/d1?start_date=${startDate}&end_date=${endDate}`,
        { cache: 'no-store' }
      );
      if (priceResponse.ok) {
        const priceData = await priceResponse.json();
        const bars = priceData.bars || [];
        if (bars.length >= 2) {
          buyAndHoldReturn =
            ((bars[bars.length - 1].close - bars[0].close) / bars[0].close) * 100;
        }
      }
    } catch (_) {}

    const rawTrades = data.trades || [];
    const tradesList: Trade[] = [];
    let pendingBuy: { date: string; price: number } | null = null;
    for (const t of rawTrades) {
      const rawDate = t.date ?? t.timestamp ?? t.datetime ?? '';
      const dateMatch = String(rawDate).trim().match(/^(\d{4}-\d{2}-\d{2})/);
      const dateStr = dateMatch ? dateMatch[1] : '';
      const price = Number(t.price ?? 0);
      const action = String(t.action ?? '').toUpperCase();
      if (action === 'BUY') {
        pendingBuy = { date: dateStr, price };
      } else if (action === 'SELL' && pendingBuy) {
        const entryPrice = pendingBuy.price;
        const exitPrice = price;
        const qty = Number(t.quantity ?? 1);
        const apiPnl = t.pnl != null && t.pnl !== '' ? Number(t.pnl) : null;
        const pnl = apiPnl != null ? apiPnl : (exitPrice - entryPrice) * qty;
        const pnlPercent = entryPrice ? ((exitPrice - entryPrice) / entryPrice) * 100 : 0;
        tradesList.push({
          id: `trade-${tradesList.length}`,
          entryTime: pendingBuy.date,
          exitTime: dateStr,
          entryPrice,
          exitPrice,
          quantity: qty,
          pnl,
          pnlPercent,
          isWin: pnl > 0 || pnlPercent > 0,
        });
        pendingBuy = null;
      }
    }

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
    const winningTradesCount = tradesList.filter((t) => t.isWin).length;
    const tradeBasedMaxDrawdownPct =
      tradesList.length > 0
        ? Math.min(...tradesList.map((t) => t.pnlPercent)) / 100
        : undefined;

    return {
      id: Date.now().toString(),
      strategyId: strategy.id,
      symbol: data.symbol,
      period: `${data.period?.start ?? startDate} to ${data.period?.end ?? endDate}`,
      totalTrades: metrics.totalTrades ?? tradesList.length,
      winningTrades: winningTradesCount,
      losingTrades: tradesList.length - winningTradesCount,
      winRate: tradesList.length
        ? winningTradesCount / tradesList.length
        : (metrics.winRate ?? 0) / 100,
      totalReturn: data.totalReturn != null ? Number(data.totalReturn) : 0,
      tradeBasedReturnPct,
      tradeBasedMaxDrawdownPct,
      buyAndHoldReturn,
      maxDrawdown: metrics.maxDrawdown != null ? Number(metrics.maxDrawdown) / 100 : 0,
      sharpeRatio: metrics.sharpeRatio != null ? Number(metrics.sharpeRatio) : 0,
      profitFactor: 0,
      avgWin: 0,
      avgLoss: 0,
      trades: tradesList,
      equityCurve: equityCurve.map((e: { date?: string; value: number }) => ({
        time: toChartTime(e?.date ?? ''),
        value: e.value,
      })),
    };
  } catch (err) {
    console.error('[Backtest] Error:', err);
    return null;
  }
};
