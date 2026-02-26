import React, { useState, useEffect, useRef } from 'react';
import { createChart, IChartApi } from 'lightweight-charts';
import { createClient, SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://cygflaemtmwiwaviclks.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs';
const supabase: SupabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const SUPABASE_FUNCTIONS_URL = `${SUPABASE_URL}/functions/v1`;

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function isStrategyIdUuid(id: string): boolean {
  return UUID_REGEX.test(id);
}

/** Intraday-aware time for lightweight-charts: Unix (number) when date has time, else business day string to avoid duplicate timestamps. */
function toChartTime(raw: string | number): string | number {
  if (typeof raw === 'number') return raw;
  const s = String(raw ?? '').trim();
  if (!s) return '';
  const hasTime = /^\d{4}-\d{2}-\d{2}[T\s]\d/.test(s);
  if (hasTime) return Math.floor(new Date(s).getTime() / 1000);
  const day = s.match(/^(\d{4}-\d{2}-\d{2})/)?.[1];
  return day ?? s;
}

/** Dedupe equity curve by time (keep last per time) so lightweight-charts never sees prev time === time. */
export function dedupeEquityCurve(
  points: { time: string | number; value: number }[]
): { time: string | number; value: number }[] {
  if (!points.length) return [];
  const key = (t: string | number) => (typeof t === 'number' ? t : t);
  const sorted = [...points].sort((a, b) => {
    const ta = key(a.time);
    const tb = key(b.time);
    return ta < tb ? -1 : ta > tb ? 1 : 0;
  });
  const out: { time: string | number; value: number }[] = [];
  let prev: string | number | undefined;
  for (const p of sorted) {
    if (p.time !== prev) {
      out.push({ time: p.time, value: p.value });
      prev = p.time;
    } else {
      out[out.length - 1] = { time: p.time, value: p.value };
    }
  }
  return out;
}

/** Indicator types aligned with client-macos TechnicalIndicatorsView + ML technical_indicators API */
export type ConditionType =
  | 'rsi'
  | 'macd'
  | 'macd_signal'
  | 'macd_hist'
  | 'stochastic'
  | 'kdj_k'
  | 'kdj_d'
  | 'kdj_j'
  | 'mfi'
  | 'williams_r'
  | 'cci'
  | 'returns_1d'
  | 'returns_5d'
  | 'returns_20d'
  | 'sma'
  | 'ema'
  | 'sma_cross'
  | 'ema_cross'
  | 'adx'
  | 'plus_di'
  | 'minus_di'
  | 'price_above_sma'
  | 'price_above_ema'
  | 'price_vs_sma20'
  | 'price_vs_sma50'
  | 'bb'
  | 'bb_upper'
  | 'bb_lower'
  | 'atr'
  | 'volatility_20d'
  | 'supertrend_factor'
  | 'supertrend_trend'
  | 'supertrend_signal'
  | 'close'
  | 'high'
  | 'low'
  | 'open'
  | 'volume'
  | 'volume_ratio'
  | 'obv'
  | 'price_breakout'
  | 'volume_spike'
  | 'ml_signal';
export type Operator = '>' | '<' | '>=' | '<=' | '==' | 'cross_up' | 'cross_down';

export interface Condition {
  id: string;
  type: ConditionType;
  params: Record<string, number>;
  operator: Operator;
  value: number;
}

export interface EntryExitCondition {
  type: ConditionType;
  params: Record<string, number>;
  operator: Operator;
  value: number;
}

export interface PositionSizing {
  type: 'fixed' | 'percent_of_equity' | 'kelly';
  value: number;
}

export interface RiskManagement {
  stopLoss: { type: 'percent' | 'fixed'; value: number };
  takeProfit: { type: 'percent' | 'fixed'; value: number };
}

export interface StrategyConfig {
  entryConditions: EntryExitCondition[];
  exitConditions: EntryExitCondition[];
  positionSizing: PositionSizing;
  riskManagement: RiskManagement;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  config: StrategyConfig;
  createdAt: string;
  updatedAt: string;
}

export interface Trade {
  id: string;
  entryTime: string;
  exitTime: string;
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  pnl: number;
  pnlPercent: number;
  isWin: boolean;
}

export interface BacktestResult {
  id: string;
  strategyId: string;
  symbol: string;
  period: string;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  totalReturn: number;
  /** When present, use this for display so all panels match Total P&L (first entry → last exit notional). */
  tradeBasedReturnPct?: number;
  /** When present, max drawdown from trade log (worst single-trade return % as decimal, e.g. -0.052 for -5.2%). */
  tradeBasedMaxDrawdownPct?: number;
  buyAndHoldReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
  profitFactor: number;
  avgWin: number;
  avgLoss: number;
  trades: Trade[];
  /** time: business day "yyyy-mm-dd" (daily) or Unix seconds (intraday). Use dedupeEquityCurve before setData. */
  equityCurve: { time: string | number; value: number }[];
}

interface ConditionParam {
  name: string;
  min: number;
  max: number;
  default: number;
  step?: number;
}

/** Preset operator+value from TechnicalIndicatorsModels (bullish/bearish interpretation) */
export interface ConditionPreset {
  label: string;
  operator: Operator;
  value: number;
}

interface ConditionTypeConfig {
  id: ConditionType;
  name: string;
  params: ConditionParam[];
  /** Bullish/bearish presets aligned with Swift IndicatorItem.interpretation */
  presets?: ConditionPreset[];
}

/** Library aligned with TechnicalIndicatorsView (Swift) + ML technical_indicators API keys */
const conditionTypes: ConditionTypeConfig[] = [
  // —— Momentum (per IndicatorCategory.momentum) ——
  { id: 'rsi', name: 'RSI', params: [{ name: 'period', min: 5, max: 30, default: 14 }], presets: [{ label: 'Oversold', operator: '<', value: 30 }, { label: 'Overbought', operator: '>', value: 70 }, { label: 'Bullish', operator: '>', value: 60 }, { label: 'Bearish', operator: '<', value: 40 }] },
  { id: 'macd', name: 'MACD', params: [{ name: 'fastPeriod', min: 5, max: 20, default: 12 }, { name: 'slowPeriod', min: 15, max: 40, default: 26 }, { name: 'signalPeriod', min: 5, max: 15, default: 9 }], presets: [{ label: 'Bullish', operator: '>', value: 0 }, { label: 'Bearish', operator: '<', value: 0 }] },
  { id: 'macd_signal', name: 'MACD Signal', params: [{ name: 'fastPeriod', min: 5, max: 20, default: 12 }, { name: 'slowPeriod', min: 15, max: 40, default: 26 }, { name: 'signalPeriod', min: 5, max: 15, default: 9 }], presets: [{ label: 'Bullish', operator: '>', value: 0 }, { label: 'Bearish', operator: '<', value: 0 }] },
  { id: 'macd_hist', name: 'MACD Histogram', params: [{ name: 'fastPeriod', min: 5, max: 20, default: 12 }, { name: 'slowPeriod', min: 15, max: 40, default: 26 }, { name: 'signalPeriod', min: 5, max: 15, default: 9 }], presets: [{ label: 'Bullish', operator: '>', value: 0 }, { label: 'Bearish', operator: '<', value: 0 }] },
  { id: 'stochastic', name: 'Stochastic %K', params: [{ name: 'kPeriod', min: 5, max: 21, default: 14 }, { name: 'dPeriod', min: 2, max: 5, default: 3 }], presets: [{ label: 'Oversold', operator: '<', value: 20 }, { label: 'Overbought', operator: '>', value: 80 }, { label: 'Bullish', operator: '>', value: 60 }, { label: 'Bearish', operator: '<', value: 40 }] },
  { id: 'kdj_k', name: 'KDJ K', params: [{ name: 'period', min: 5, max: 21, default: 9 }, { name: 'kSmooth', min: 2, max: 9, default: 5 }, { name: 'dSmooth', min: 2, max: 9, default: 5 }], presets: [{ label: 'Oversold', operator: '<', value: 20 }, { label: 'Overbought', operator: '>', value: 80 }] },
  { id: 'kdj_d', name: 'KDJ D', params: [{ name: 'period', min: 5, max: 21, default: 9 }, { name: 'kSmooth', min: 2, max: 9, default: 5 }, { name: 'dSmooth', min: 2, max: 9, default: 5 }], presets: [{ label: 'Oversold', operator: '<', value: 20 }, { label: 'Overbought', operator: '>', value: 80 }] },
  { id: 'kdj_j', name: 'KDJ J', params: [{ name: 'period', min: 5, max: 21, default: 9 }, { name: 'kSmooth', min: 2, max: 9, default: 5 }, { name: 'dSmooth', min: 2, max: 9, default: 5 }], presets: [{ label: 'Oversold', operator: '<', value: 0 }, { label: 'Overbought', operator: '>', value: 100 }, { label: 'Bullish', operator: '>', value: 20 }, { label: 'Bearish', operator: '<', value: 80 }] },
  { id: 'mfi', name: 'MFI', params: [{ name: 'period', min: 5, max: 30, default: 14 }], presets: [{ label: 'Oversold', operator: '<', value: 20 }, { label: 'Overbought', operator: '>', value: 80 }, { label: 'Bullish', operator: '<', value: 30 }, { label: 'Bearish', operator: '>', value: 70 }] },
  { id: 'williams_r', name: 'Williams %R', params: [{ name: 'period', min: 5, max: 28, default: 14 }], presets: [{ label: 'Oversold', operator: '<', value: -80 }, { label: 'Overbought', operator: '>', value: -20 }, { label: 'Bullish', operator: '<', value: -50 }, { label: 'Bearish', operator: '>', value: -50 }] },
  { id: 'cci', name: 'CCI', params: [{ name: 'period', min: 10, max: 40, default: 20 }], presets: [{ label: 'Strong Bullish', operator: '<', value: -200 }, { label: 'Bullish', operator: '<', value: -100 }, { label: 'Bearish', operator: '>', value: 100 }, { label: 'Strong Bearish', operator: '>', value: 200 }] },
  { id: 'returns_1d', name: 'Returns 1D', params: [], presets: [{ label: 'Bullish', operator: '>', value: 0.01 }, { label: 'Strong Bullish', operator: '>', value: 0.03 }, { label: 'Bearish', operator: '<', value: -0.01 }, { label: 'Strong Bearish', operator: '<', value: -0.03 }] },
  { id: 'returns_5d', name: 'Returns 5D', params: [], presets: [{ label: 'Bullish', operator: '>', value: 0.02 }, { label: 'Strong Bullish', operator: '>', value: 0.05 }, { label: 'Bearish', operator: '<', value: -0.02 }, { label: 'Strong Bearish', operator: '<', value: -0.05 }] },
  { id: 'returns_20d', name: 'Returns 20D', params: [], presets: [{ label: 'Bullish', operator: '>', value: 0.05 }, { label: 'Strong Bullish', operator: '>', value: 0.10 }, { label: 'Bearish', operator: '<', value: -0.05 }, { label: 'Strong Bearish', operator: '<', value: -0.10 }] },
  // —— Trend (per IndicatorCategory.trend) ——
  { id: 'sma', name: 'SMA', params: [{ name: 'period', min: 5, max: 200, default: 20 }] },
  { id: 'ema', name: 'EMA', params: [{ name: 'period', min: 5, max: 50, default: 12 }] },
  { id: 'sma_cross', name: 'SMA Crossover', params: [{ name: 'fastPeriod', min: 5, max: 30, default: 10 }, { name: 'slowPeriod', min: 20, max: 100, default: 50 }] },
  { id: 'ema_cross', name: 'EMA Crossover', params: [{ name: 'fastPeriod', min: 5, max: 30, default: 12 }, { name: 'slowPeriod', min: 20, max: 100, default: 26 }] },
  { id: 'adx', name: 'ADX', params: [{ name: 'period', min: 7, max: 28, default: 14 }], presets: [{ label: 'Weak trend', operator: '<', value: 20 }, { label: 'Trend', operator: '>', value: 25 }, { label: 'Strong trend', operator: '>', value: 40 }] },
  { id: 'plus_di', name: '+DI', params: [{ name: 'period', min: 7, max: 28, default: 14 }] },
  { id: 'minus_di', name: '-DI', params: [{ name: 'period', min: 7, max: 28, default: 14 }] },
  { id: 'price_above_sma', name: 'Price Above SMA', params: [{ name: 'period', min: 5, max: 50, default: 20 }] },
  { id: 'price_above_ema', name: 'Price Above EMA', params: [{ name: 'period', min: 5, max: 50, default: 12 }] },
  { id: 'price_vs_sma20', name: 'Price vs SMA20', params: [], presets: [{ label: 'Strong Bullish', operator: '>', value: 0.05 }, { label: 'Bullish', operator: '>', value: 0.02 }, { label: 'Bearish', operator: '<', value: -0.02 }, { label: 'Strong Bearish', operator: '<', value: -0.05 }] },
  { id: 'price_vs_sma50', name: 'Price vs SMA50', params: [], presets: [{ label: 'Strong Bullish', operator: '>', value: 0.05 }, { label: 'Bullish', operator: '>', value: 0.02 }, { label: 'Bearish', operator: '<', value: -0.02 }, { label: 'Strong Bearish', operator: '<', value: -0.05 }] },
  // —— Volatility (per IndicatorCategory.volatility) ——
  { id: 'bb', name: 'Bollinger Bands', params: [{ name: 'period', min: 10, max: 30, default: 20 }, { name: 'stdDev', min: 1, max: 3, step: 0.1, default: 2 }] },
  { id: 'bb_upper', name: 'BB Upper', params: [{ name: 'period', min: 10, max: 30, default: 20 }, { name: 'stdDev', min: 1, max: 3, step: 0.1, default: 2 }] },
  { id: 'bb_lower', name: 'BB Lower', params: [{ name: 'period', min: 10, max: 30, default: 20 }, { name: 'stdDev', min: 1, max: 3, step: 0.1, default: 2 }] },
  { id: 'atr', name: 'ATR', params: [{ name: 'period', min: 7, max: 28, default: 14 }] },
  { id: 'volatility_20d', name: 'Volatility 20D', params: [] },
  { id: 'supertrend_factor', name: 'SuperTrend Factor', params: [{ name: 'factor', min: 1, max: 5, step: 0.5, default: 2 }] },
  { id: 'supertrend_trend', name: 'SuperTrend Trend', params: [], presets: [{ label: 'Bullish', operator: '==', value: 1 }, { label: 'Bearish', operator: '==', value: 0 }] },
  { id: 'supertrend_signal', name: 'SuperTrend Signal', params: [], presets: [{ label: 'Buy', operator: '==', value: 1 }, { label: 'Sell', operator: '==', value: -1 }] },
  // —— Price (per IndicatorCategory.price) ——
  { id: 'close', name: 'Close / Price', params: [] },
  { id: 'high', name: 'High', params: [] },
  { id: 'low', name: 'Low', params: [] },
  { id: 'open', name: 'Open', params: [] },
  { id: 'price_breakout', name: 'Price Breakout', params: [{ name: 'lookback', min: 5, max: 50, default: 20 }] },
  // —— Volume (per IndicatorCategory.volume) ——
  { id: 'volume', name: 'Volume', params: [{ name: 'multiplier', min: 0.5, max: 5, step: 0.5, default: 1 }] },
  { id: 'volume_ratio', name: 'Volume Ratio', params: [], presets: [{ label: 'High', operator: '>', value: 1.5 }, { label: 'Very high', operator: '>', value: 2 }, { label: 'Low', operator: '<', value: 0.5 }] },
  { id: 'obv', name: 'OBV', params: [] },
  { id: 'volume_spike', name: 'Volume Spike', params: [{ name: 'multiplier', min: 1, max: 5, step: 0.5, default: 2 }] },
  // —— Other ——
  { id: 'ml_signal', name: 'ML Signal', params: [{ name: 'confidence', min: 0.5, max: 1, step: 0.05, default: 0.7 }] },
];

const operators: { id: Operator; label: string }[] = [
  { id: '>', label: '>' },
  { id: '<', label: '<' },
  { id: '>=', label: '>=' },
  { id: '<=', label: '<=' },
  { id: '==', label: '==' },
  { id: 'cross_up', label: 'Crosses Above' },
  { id: 'cross_down', label: 'Crosses Below' },
];

const datePresets = [
  { id: 'lastMonth', label: '1M', days: 30 },
  { id: 'last3Months', label: '3M', days: 90 },
  { id: 'last6Months', label: '6M', days: 180 },
  { id: 'lastYear', label: '1Y', days: 365 },
  { id: 'covidCrash', label: 'COVID', startDate: '2020-02-19', endDate: '2020-03-23' },
  { id: 'gfc', label: 'GFC', startDate: '2007-12-01', endDate: '2009-06-01' },
];

interface StrategyBacktestPanelProps {
  symbol: string;
  horizon: string;
  expanded?: boolean;
  /** Use chart date range for backtest so results match the visible chart; when set, presets are ignored for the request. */
  startDate?: Date;
  endDate?: Date;
  /** Called when a backtest completes so parent (e.g. App) can show the same result in the bottom section. */
  onBacktestComplete?: (result: BacktestResult | null) => void;
  /** When period preset is clicked, call with new start/end so parent can update chart date range. */
  onDateRangeChange?: (start: Date, end: Date) => void;
}

const createDefaultConfig = (): StrategyConfig => ({
  entryConditions: [{ type: 'rsi', params: { period: 14 }, operator: '<', value: 30 }],
  exitConditions: [{ type: 'rsi', params: { period: 14 }, operator: '>', value: 70 }],
  positionSizing: { type: 'percent_of_equity', value: 2 },
  riskManagement: { stopLoss: { type: 'percent', value: 2 }, takeProfit: { type: 'percent', value: 5 } },
});

const fetchStrategiesFromSupabase = async (): Promise<Strategy[]> => {
  try {
    const { data, error } = await supabase
      .from('strategy_user_strategies')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(20);
    
    if (error) {
      // Silent - using local strategies
      return [];
    }
    
    return data?.map((row: any) => ({
      id: row.id,
      name: row.name,
      description: row.description || '',
      config: row.config || createDefaultConfig(),
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    })) || [];
  } catch (err) {
      // Silent - using local strategies
    return [];
  }
};

const saveStrategyToSupabase = async (strategy: Omit<Strategy, 'createdAt' | 'updatedAt'>): Promise<string | null> => {
  try {
    const { data, error } = await supabase
      .from('strategy_user_strategies')
      .insert({
        name: strategy.name,
        description: strategy.description,
        config: strategy.config,
      })
      .select('id')
      .single();
    
    if (error) {
      // Silent - local only
      return null;
    }
    return data?.id || null;
  } catch (err) {
      // Silent - local only
    return null;
  }
};

const updateStrategyInSupabase = async (strategy: Strategy): Promise<boolean> => {
  if (!isStrategyIdUuid(strategy.id)) return false;
  try {
    const { error } = await supabase
      .from('strategy_user_strategies')
      .update({
        name: strategy.name,
        description: strategy.description,
        config: strategy.config,
        updated_at: new Date().toISOString(),
      })
      .eq('id', strategy.id);
    return !error;
  } catch {
    return false;
  }
};

/** Ensure strategy exists in Supabase so we have a strategy_id for backtest. Returns strategy_id. */
async function ensureStrategyId(strategy: Strategy): Promise<string> {
  if (isStrategyIdUuid(strategy.id)) return strategy.id;
  const id = await saveStrategyToSupabase({
    id: strategy.id,
    name: strategy.name,
    description: strategy.description,
    config: strategy.config,
  });
  return id || strategy.id;
}

/** Map UI horizon (15m, 1h, 4h, 1D) to API timeframe (m15, h1, h4, d1). */
function horizonToTimeframe(horizon: string): string {
  const map: Record<string, string> = { '15m': 'm15', '1h': 'h1', '4h': 'h4', '1D': 'd1' };
  return map[horizon] || 'd1';
}

/** Run backtest via Supabase (worker runs full strategy config). Poll until completed, then map result. */
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
  const postRes = await fetch(`${SUPABASE_FUNCTIONS_URL}/backtest-strategy`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ symbol, startDate, endDate, strategy_id: strategyId, initialCapital: 10000, timeframe }),
    cache: 'no-store',
  });
  if (!postRes.ok) {
    const err = await postRes.text();
    console.error('[Backtest] Supabase queue error:', err);
    return null;
  }
  const { job_id } = (await postRes.json()) as { job_id: string };
  if (!job_id) return null;

  // 20 × 1.5 s = 30 s max wait; then fall through to FastAPI fallback.
  for (let i = 0; i < 20; i++) {
    await new Promise((r) => setTimeout(r, 1500));
    const getRes = await fetch(`${SUPABASE_FUNCTIONS_URL}/backtest-strategy?id=${job_id}`, { headers, cache: 'no-store' });
    if (!getRes.ok) return null;
    const statusPayload = (await getRes.json()) as {
      status: string;
      result?: { metrics?: Record<string, unknown>; trades?: Record<string, unknown>[]; equity_curve?: { date: string; value: number }[] };
      error?: string;
    };
    if (statusPayload.status === 'failed') {
      console.error('[Backtest] Job failed:', statusPayload.error);
      return null;
    }
    if (statusPayload.status === 'completed' && statusPayload.result) {
      const r = statusPayload.result;
      const metrics = r.metrics || {};
      const trades = r.trades || [];
      const equityCurve = r.equity_curve || [];
      const totalReturn = Number(metrics.total_return_pct ?? 0);
      const finalValue = Number(metrics.final_value ?? 10000);
      const initialCapital = 10000;
      let buyAndHoldReturn = 0;
      try {
        const priceRes = await fetch(
          `${API_BASE}/api/v1/chart-data/${symbol}/d1?start_date=${startDate}&end_date=${endDate}`,
          { cache: 'no-store' }
        );
        if (priceRes.ok) {
          const priceData = await priceRes.json();
          const bars = priceData.bars || [];
          if (bars.length >= 2) {
            const startPrice = bars[0].close;
            const endPrice = bars[bars.length - 1].close;
            buyAndHoldReturn = ((endPrice - startPrice) / startPrice) * 100;
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
      const firstEntryNotional = tradesList.length > 0 ? tradesList[0].entryPrice * tradesList[0].quantity : 0;
      const lastExitNotional = tradesList.length > 0 ? tradesList[tradesList.length - 1].exitPrice * tradesList[tradesList.length - 1].quantity : 0;
      const tradeBasedReturnPct =
        tradesList.length > 0 && firstEntryNotional !== 0
          ? ((lastExitNotional - firstEntryNotional) / firstEntryNotional) * 100
          : undefined;
      const tradeBasedMaxDrawdownPct =
        tradesList.length > 0 ? Math.min(...tradesList.map((t) => t.pnlPercent)) / 100 : undefined;
      return {
        id: Date.now().toString(),
        strategyId: strategyDisplayId,
        symbol,
        period: `${startDate} to ${endDate}`,
        totalTrades: tradesList.length,
        winningTrades: winningTradesCount,
        losingTrades: tradesList.length - winningTradesCount,
        winRate: tradesList.length ? winningTradesCount / tradesList.length : 0,
        totalReturn,
        tradeBasedReturnPct,
        tradeBasedMaxDrawdownPct,
        buyAndHoldReturn,
        maxDrawdown: Number(metrics.max_drawdown_pct ?? 0) / 100,
        sharpeRatio: Number(metrics.sharpe_ratio ?? 0),
        profitFactor: Number(metrics.profit_factor ?? 0),
        avgWin: Number(metrics.avg_win ?? 0),
        avgLoss: Number(metrics.avg_loss ?? 0),
        trades: tradesList,
        equityCurve: equityCurve.map((e) => ({ time: toChartTime((e as { date?: string }).date ?? ''), value: e.value })),
      };
    }
  }
  console.error('[Backtest] Timeout waiting for job');
  return null;
}

const runBacktestViaAPI = async (
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
    else if (strategyType === 'price_breakout' || strategyType === 'volume_spike' || strategyType === 'ml_signal') apiStrategy = 'buy_and_hold';

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
      const priceResponse = await fetch(
        `${API_BASE}/api/v1/chart-data/${symbol}/d1?start_date=${startDate}&end_date=${endDate}`,
        { cache: 'no-store' }
      );
      if (priceResponse.ok) {
        const priceData = await priceResponse.json();
        const bars = priceData.bars || [];
        if (bars.length >= 2) {
          const startPrice = bars[0].close;
          const endPrice = bars[bars.length - 1].close;
          buyAndHoldReturn = ((endPrice - startPrice) / startPrice) * 100;
        }
      }
    } catch (_) {}

    const rawTrades = data.trades || [];
    const tradesList: Trade[] = [];
    let pendingBuy: { date: string; price: number } | null = null;
    for (const t of rawTrades) {
      // Robustly extract yyyy-mm-dd from any date format the API returns
      // (ISO "2024-01-15T…", space-separated "2024-01-15 10:30", plain date, or non-string timestamp).
      const rawDate = t.date ?? t.timestamp ?? t.datetime ?? '';
      const dateMatch = String(rawDate).trim().match(/^(\d{4}-\d{2}-\d{2})/);
      const dateStr = dateMatch ? dateMatch[1] : '';
      const price = Number(t.price ?? 0);
      const action = String(t.action ?? '').toUpperCase();
      if (action === 'BUY') pendingBuy = { date: dateStr, price };
      else if (action === 'SELL' && pendingBuy) {
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
    const firstEntryNotional = tradesList.length > 0 ? tradesList[0].entryPrice * tradesList[0].quantity : 0;
    const lastExitNotional = tradesList.length > 0 ? tradesList[tradesList.length - 1].exitPrice * tradesList[tradesList.length - 1].quantity : 0;
    const tradeBasedReturnPct =
      tradesList.length > 0 && firstEntryNotional !== 0
        ? ((lastExitNotional - firstEntryNotional) / firstEntryNotional) * 100
        : undefined;
    const winningTradesCount = tradesList.filter((t) => t.isWin).length;
    const tradeBasedMaxDrawdownPct =
      tradesList.length > 0 ? Math.min(...tradesList.map((t) => t.pnlPercent)) / 100 : undefined;
    return {
      id: Date.now().toString(),
      strategyId: strategy.id,
      symbol: data.symbol,
      period: `${data.period?.start ?? startDate} to ${data.period?.end ?? endDate}`,
      totalTrades: metrics.totalTrades ?? tradesList.length,
      winningTrades: winningTradesCount,
      losingTrades: tradesList.length - winningTradesCount,
      winRate: tradesList.length ? winningTradesCount / tradesList.length : (metrics.winRate ?? 0) / 100,
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

export const StrategyBacktestPanel: React.FC<StrategyBacktestPanelProps> = ({ symbol, horizon, expanded = false, startDate: parentStartDate, endDate: parentEndDate, onBacktestComplete, onDateRangeChange }) => {
  // Default strategies for user to choose from
  const defaultStrategies: Strategy[] = [
    { id: '1', name: 'RSI Mean Reversion', description: 'Buy RSI<30, sell RSI>70', config: createDefaultConfig(), createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
    { id: '2', name: 'SMA Crossover', description: 'Fast SMA crosses slow SMA', config: { entryConditions: [{ type: 'sma_cross', params: { fastPeriod: 10, slowPeriod: 50 }, operator: 'cross_up', value: 0 }], exitConditions: [{ type: 'sma_cross', params: { fastPeriod: 10, slowPeriod: 50 }, operator: 'cross_down', value: 0 }], positionSizing: { type: 'percent_of_equity', value: 2 }, riskManagement: { stopLoss: { type: 'percent', value: 2 }, takeProfit: { type: 'percent', value: 5 } } }, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
    { id: '3', name: 'SuperTrend', description: 'AI SuperTrend strategy', config: { entryConditions: [{ type: 'rsi', params: { period: 14 }, operator: '<', value: 50 }], exitConditions: [{ type: 'rsi', params: { period: 14 }, operator: '>', value: 50 }], positionSizing: { type: 'percent_of_equity', value: 2 }, riskManagement: { stopLoss: { type: 'percent', value: 3 }, takeProfit: { type: 'percent', value: 6 } } }, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
  ];
  
  const [strategies, setStrategies] = useState<Strategy[]>(defaultStrategies);
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(strategies[0]);
  const [isCreating, setIsCreating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [newStrategyName, setNewStrategyName] = useState('');
  const [newConfig, setNewConfig] = useState<StrategyConfig>(createDefaultConfig());
  
  const [selectedPreset, setSelectedPreset] = useState<string>('lastYear');
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [showEquityChart, setShowEquityChart] = useState(true);
  const [showTrades, setShowTrades] = useState(true);

  const equityChartRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const loadStrategies = async () => {
      const dbStrategies = await fetchStrategiesFromSupabase();
      // Merge database strategies with defaults (database takes precedence)
      if (dbStrategies.length > 0) {
        setStrategies([...defaultStrategies, ...dbStrategies]);
        setSelectedStrategy(dbStrategies[0]);
      }
    };
    loadStrategies();
  }, []);

  const getPresetDates = (presetId: string) => {
    const now = new Date();
    const preset = datePresets.find(p => p.id === presetId);
    if (!preset) return { start: new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000), end: now };
    if ('days' in preset && preset.days) return { start: new Date(now.getTime() - preset.days * 24 * 60 * 60 * 1000), end: now };
    if ('startDate' in preset && preset.startDate && preset.endDate) return { start: new Date(preset.startDate as string), end: new Date(preset.endDate as string) };
    return { start: new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000), end: now };
  };

  const handleCreateStrategy = async () => {
    if (!newStrategyName.trim()) return;
    const newStrategy: Strategy = {
      id: Date.now().toString(),
      name: newStrategyName,
      description: `${newConfig.entryConditions.length} entry, ${newConfig.exitConditions.length} exit conditions`,
      config: { ...newConfig },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    
    const savedId = await saveStrategyToSupabase(newStrategy);
    if (savedId) {
      newStrategy.id = savedId;
    }
    
    setStrategies([...strategies, newStrategy]);
    setSelectedStrategy(newStrategy);
    setIsCreating(false);
    setNewStrategyName('');
    setNewConfig(createDefaultConfig());
  };

  const startEditStrategy = () => {
    if (!selectedStrategy) return;
    setNewStrategyName(selectedStrategy.name);
    setNewConfig({ ...selectedStrategy.config });
    setIsEditing(true);
  };

  const handleSaveStrategy = async () => {
    if (!selectedStrategy || !newStrategyName.trim()) return;
    const updated: Strategy = {
      ...selectedStrategy,
      name: newStrategyName.trim(),
      description: `${newConfig.entryConditions.length} entry, ${newConfig.exitConditions.length} exit conditions`,
      config: { ...newConfig },
      updatedAt: new Date().toISOString(),
    };
    if (isStrategyIdUuid(selectedStrategy.id)) {
      await updateStrategyInSupabase(updated);
    }
    setStrategies(strategies.map((s) => (s.id === selectedStrategy.id ? updated : s)));
    setSelectedStrategy(updated);
    setIsEditing(false);
    setNewStrategyName('');
    setNewConfig(createDefaultConfig());
    // Invalidate previous backtest so UI doesn't show stale results; user can rerun with fresh inputs
    setResult(null);
    onBacktestComplete?.(null);
  };

  const cancelForm = () => {
    setIsCreating(false);
    setIsEditing(false);
    setNewStrategyName('');
    setNewConfig(createDefaultConfig());
  };

  const addCondition = (isEntry: boolean) => {
    const newCondition: EntryExitCondition = { type: 'rsi', params: { period: 14 }, operator: '<', value: 30 };
    if (isEntry) {
      setNewConfig({ ...newConfig, entryConditions: [...newConfig.entryConditions, newCondition] });
    } else {
      setNewConfig({ ...newConfig, exitConditions: [...newConfig.exitConditions, newCondition] });
    }
  };

  const removeCondition = (isEntry: boolean, index: number) => {
    if (isEntry) {
      setNewConfig({ ...newConfig, entryConditions: newConfig.entryConditions.filter((_, i) => i !== index) });
    } else {
      setNewConfig({ ...newConfig, exitConditions: newConfig.exitConditions.filter((_, i) => i !== index) });
    }
  };

  const updateCondition = (isEntry: boolean, index: number, field: keyof EntryExitCondition, value: any) => {
    const conditions = isEntry ? [...newConfig.entryConditions] : [...newConfig.exitConditions];
    if (field === 'type') {
      const ct = conditionTypes.find(c => c.id === value);
      if (ct) {
        const params: Record<string, number> = {};
        ct.params.forEach(p => params[p.name] = p.default);
        conditions[index] = { ...conditions[index], type: value, params };
      }
    } else {
      conditions[index] = { ...conditions[index], [field]: value };
    }
    if (isEntry) {
      setNewConfig({ ...newConfig, entryConditions: conditions });
    } else {
      setNewConfig({ ...newConfig, exitConditions: conditions });
    }
  };

  const applyPresetToCondition = (isEntry: boolean, index: number, preset: ConditionPreset) => {
    const conditions = isEntry ? [...newConfig.entryConditions] : [...newConfig.exitConditions];
    conditions[index] = { ...conditions[index], operator: preset.operator, value: preset.value };
    if (isEntry) {
      setNewConfig({ ...newConfig, entryConditions: conditions });
    } else {
      setNewConfig({ ...newConfig, exitConditions: conditions });
    }
  };

  const handleRunBacktest = async () => {
    if (!selectedStrategy) return;
    // Clear previous result and parent cache so UI shows fresh run for new inputs
    setResult(null);
    onBacktestComplete?.(null);
    setIsRunning(true);
    // Use chart date range when provided so backtest and chart stay in sync; otherwise use preset.
    const startDateStr = parentStartDate && parentEndDate
      ? parentStartDate.toISOString().split('T')[0]
      : getPresetDates(selectedPreset).start.toISOString().split('T')[0];
    const endDateStr = parentStartDate && parentEndDate
      ? parentEndDate.toISOString().split('T')[0]
      : getPresetDates(selectedPreset).end.toISOString().split('T')[0];

    const apiResult = await runBacktestViaAPI(selectedStrategy, symbol, startDateStr, endDateStr, horizon);

    if (apiResult) {
      setResult(apiResult);
      onBacktestComplete?.(apiResult);
    } else {
      setResult(null);
      onBacktestComplete?.(null);
    }

    setIsRunning(false);
  };

  useEffect(() => {
    if (showEquityChart && equityChartRef.current && result) {
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
      equitySeries.setData(deduped.map((p) => ({
        time: p.time as any,
        value: p.value,
      })));
      
      chart.timeScale().fitContent();
      
      return () => {
        if (chartRef.current) {
          chartRef.current.remove();
          chartRef.current = null;
        }
      };
    }
  }, [showEquityChart, result]);

  const renderConditionBuilder = (isEntry: boolean) => {
    const conditions = isEntry ? newConfig.entryConditions : newConfig.exitConditions;
    return (
      <div className="flex flex-col flex-1 min-w-0 rounded border border-gray-600 bg-gray-700/40">
        <div className="flex justify-between items-center px-1.5 py-0.5 border-b border-gray-600 shrink-0">
          <span className="text-[11px] font-medium text-gray-400">{isEntry ? 'Entry' : 'Exit'}</span>
          <button onClick={() => addCondition(isEntry)} className="text-[11px] text-blue-400 hover:text-blue-300 whitespace-nowrap">+ Add</button>
        </div>
        <div className="space-y-0.5 p-1 min-h-0">
          {conditions.map((condition, idx) => {
            const ctConfig = conditionTypes.find(c => c.id === condition.type);
            const presets = ctConfig?.presets;
            return (
              <React.Fragment key={idx}>
              {idx > 0 && (
                <div className="flex items-center gap-1 px-1">
                  <div className="flex-1 border-t border-dashed border-gray-600" />
                  <span className="text-[9px] font-bold text-blue-400 tracking-widest">AND</span>
                  <div className="flex-1 border-t border-dashed border-gray-600" />
                </div>
              )}
              <div className="py-1 px-1.5 bg-gray-700 rounded space-y-0.5 text-[11px]">
                <div className="flex gap-0.5 items-center">
                  <select
                    value={condition.type}
                    onChange={(e) => updateCondition(isEntry, idx, 'type', e.target.value)}
                    className="flex-1 min-w-0 px-1.5 py-0.5 bg-gray-800 border border-gray-600 rounded text-white text-[11px]"
                  >
                    {conditionTypes.map((ct) => (<option key={ct.id} value={ct.id}>{ct.name}</option>))}
                  </select>
                  <button onClick={() => removeCondition(isEntry, idx)} className="shrink-0 p-0.5 text-gray-500 hover:text-red-400" aria-label="Remove">✕</button>
                </div>
                {presets && presets.length > 0 && (
                  <div className="flex flex-wrap gap-0.5">
                    {presets.map((p) => (
                      <button
                        key={p.label}
                        type="button"
                        onClick={() => applyPresetToCondition(isEntry, idx, p)}
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          condition.operator === p.operator && condition.value === p.value
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
                        }`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                )}
                <div className="flex gap-0.5 items-center">
                  <select
                    value={condition.operator}
                    onChange={(e) => updateCondition(isEntry, idx, 'operator', e.target.value)}
                    className="flex-1 min-w-0 px-1.5 py-0.5 bg-gray-800 border border-gray-600 rounded text-white text-[11px]"
                  >
                    {operators.map((op) => (<option key={op.id} value={op.id}>{op.label}</option>))}
                  </select>
                  {condition.operator !== 'cross_up' && condition.operator !== 'cross_down' && (
                    <input
                      type="number"
                      value={condition.value}
                      onChange={(e) => updateCondition(isEntry, idx, 'value', parseFloat(e.target.value))}
                      className="w-12 shrink-0 px-1 py-0.5 bg-gray-800 border border-gray-600 rounded text-white text-[11px] text-center"
                    />
                  )}
                </div>
              </div>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-2 text-white">
      {/* Builder Section */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-gray-400">Strategies</span>
          <div className="flex gap-2">
            {selectedStrategy && !isCreating && !isEditing && (
              <button onClick={startEditStrategy} className="text-xs text-amber-400 hover:text-amber-300">
                Edit
              </button>
            )}
            <button
              onClick={() => (isCreating || isEditing ? cancelForm() : setIsCreating(true))}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              {isCreating || isEditing ? 'Cancel' : '+ New'}
            </button>
          </div>
        </div>

        {/* Strategy List - clickable, compact bars */}
        <div className="space-y-0.5 max-h-[120px] overflow-y-auto">
          {strategies.length === 0 ? (
            <div className="py-1 text-xs text-gray-500">No strategies - create one</div>
          ) : (
            strategies.map((strategy) => (
              <div
                key={strategy.id}
                className={`py-1 px-2 rounded cursor-pointer text-xs border ${
                  selectedStrategy?.id === strategy.id ? 'border-blue-500 bg-blue-500/10' : 'border-gray-700 bg-gray-800 hover:border-gray-600'
                }`}
                onClick={() => setSelectedStrategy(strategy)}
              >
                <div className="text-white font-medium truncate">{strategy.name}</div>
                <div className="text-gray-500 text-[10px] truncate">{strategy.description}</div>
              </div>
            ))
          )}
        </div>

        {/* Create / Edit Form - flexible, no scroll */}
        {(isCreating || isEditing) && (
          <div className="flex flex-col p-2.5 bg-gray-800 rounded border border-gray-600 space-y-1.5">
            <span className="text-[11px] font-medium text-gray-400">{isEditing ? 'Edit strategy' : 'New strategy'}</span>
            <input
              type="text"
              placeholder="Strategy name"
              value={newStrategyName}
              onChange={(e) => setNewStrategyName(e.target.value)}
              className="w-full px-2 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs text-white shrink-0"
            />
            <div className="flex flex-col sm:flex-row gap-3 min-h-0">
              {renderConditionBuilder(true)}
              {renderConditionBuilder(false)}
            </div>
            {/* Risk Management: Stop Loss / Take Profit */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-2 bg-gray-700/50 rounded border border-gray-600">
              <span className="sm:col-span-2 text-[11px] font-medium text-gray-400">Risk management</span>
              <div className="flex flex-wrap items-center gap-1.5">
                <label className="text-[11px] text-gray-400 shrink-0">Stop loss</label>
                <select
                  value={newConfig.riskManagement.stopLoss.type}
                  onChange={(e) => setNewConfig({
                    ...newConfig,
                    riskManagement: {
                      ...newConfig.riskManagement,
                      stopLoss: { ...newConfig.riskManagement.stopLoss, type: e.target.value as 'percent' | 'fixed' },
                    },
                  })}
                  className="px-1.5 py-0.5 bg-gray-800 border border-gray-600 rounded text-white text-[11px]"
                >
                  <option value="percent">%</option>
                  <option value="fixed">$</option>
                </select>
                <input
                  type="number"
                  min={0}
                  step={0.5}
                  value={newConfig.riskManagement.stopLoss.value}
                  onChange={(e) => setNewConfig({
                    ...newConfig,
                    riskManagement: {
                      ...newConfig.riskManagement,
                      stopLoss: { ...newConfig.riskManagement.stopLoss, value: parseFloat(e.target.value) || 0 },
                    },
                  })}
                  className="w-14 px-1.5 py-0.5 bg-gray-800 border border-gray-600 rounded text-white text-[11px] text-right"
                />
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <label className="text-[11px] text-gray-400 shrink-0">Take profit</label>
                <select
                  value={newConfig.riskManagement.takeProfit.type}
                  onChange={(e) => setNewConfig({
                    ...newConfig,
                    riskManagement: {
                      ...newConfig.riskManagement,
                      takeProfit: { ...newConfig.riskManagement.takeProfit, type: e.target.value as 'percent' | 'fixed' },
                    },
                  })}
                  className="px-1.5 py-0.5 bg-gray-800 border border-gray-600 rounded text-white text-[11px]"
                >
                  <option value="percent">%</option>
                  <option value="fixed">$</option>
                </select>
                <input
                  type="number"
                  min={0}
                  step={0.5}
                  value={newConfig.riskManagement.takeProfit.value}
                  onChange={(e) => setNewConfig({
                    ...newConfig,
                    riskManagement: {
                      ...newConfig.riskManagement,
                      takeProfit: { ...newConfig.riskManagement.takeProfit, value: parseFloat(e.target.value) || 0 },
                    },
                  })}
                  className="w-14 px-1.5 py-0.5 bg-gray-800 border border-gray-600 rounded text-white text-[11px] text-right"
                />
              </div>
            </div>
            <div className="shrink-0 pt-0.5 flex gap-1">
              <button
                onClick={isEditing ? handleSaveStrategy : handleCreateStrategy}
                className="flex-1 py-1.5 bg-blue-600 text-white text-xs rounded font-medium"
              >
                {isEditing ? 'Save' : 'Create'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Backtest Controls */}
      <div className="space-y-1.5 pt-2 border-t border-gray-700">
        {/* Selected Strategy Info + Risk */}
        {selectedStrategy && (
          <div className="text-xs space-y-0.5">
            <div>
              <span className="text-gray-400">Strategy: </span>
              <span className="text-white font-medium">{selectedStrategy.name}</span>
            </div>
            <div className="text-[11px] text-gray-500">
              Stop loss: {selectedStrategy.config.riskManagement.stopLoss.type === 'percent' ? `${selectedStrategy.config.riskManagement.stopLoss.value}%` : `$${selectedStrategy.config.riskManagement.stopLoss.value}`}
              {' · '}
              Take profit: {selectedStrategy.config.riskManagement.takeProfit.type === 'percent' ? `${selectedStrategy.config.riskManagement.takeProfit.value}%` : `$${selectedStrategy.config.riskManagement.takeProfit.value}`}
            </div>
          </div>
        )}
        
        {/* Date Presets - show all */}
        <div>
          <span className="text-xs text-gray-400">Period:</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {datePresets.map((preset) => (
              <button
                key={preset.id}
                onClick={() => {
                  setSelectedPreset(preset.id);
                  const { start, end } = getPresetDates(preset.id);
                  onDateRangeChange?.(start, end);
                }}
                className={`px-2 py-0.5 text-xs rounded ${
                  selectedPreset === preset.id ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* Symbol Display */}
        <div className="text-xs text-gray-400">
          Symbol: <span className="text-white">{symbol}</span>
        </div>

        <button
          onClick={handleRunBacktest}
          disabled={isRunning || !selectedStrategy}
          className={`w-full py-1.5 rounded text-xs font-medium ${
            isRunning || !selectedStrategy ? 'bg-gray-600 text-gray-400' : 'bg-green-600 text-white'
          }`}
        >
          {isRunning ? 'Running...' : '▶ Run Backtest'}
        </button>
      </div>

      {/* Results Section - Show when available, render differently if expanded */}
      {result && (
        <div className={`pt-2 border-t border-gray-700 ${expanded ? 'bg-gray-800 rounded-lg p-4' : 'space-y-2'}`}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400">Results</span>
            <div className="flex gap-1">
              <button onClick={() => setShowEquityChart(!showEquityChart)} className={`px-1 py-0.5 text-[10px] rounded ${showEquityChart ? 'bg-blue-600' : 'bg-gray-700'}`}>📈</button>
              <button onClick={() => setShowTrades(!showTrades)} className={`px-1 py-0.5 text-[10px] rounded ${showTrades ? 'bg-blue-600' : 'bg-gray-700'}`}>📋</button>
            </div>
          </div>
          {showEquityChart && (
            <div ref={equityChartRef} className={`rounded overflow-hidden ${expanded ? 'h-[200px]' : 'w-full h-[120px]'}`} />
          )}

          {/* P&L Summary - Uses same Start/End as row below: first entry notional → last exit notional when trades exist */}
          <div className={`${expanded ? 'grid grid-cols-2 gap-4' : 'bg-gray-800 rounded p-2 border border-gray-700'}`}>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-gray-400">Total P&L</span>
              <span className="text-right">
                {(() => {
                  const hasTrades = result.trades.length > 0;
                  const startVal = hasTrades
                    ? result.trades[0].entryPrice * result.trades[0].quantity
                    : (result.equityCurve?.[0]?.value ?? 0);
                  const endVal = hasTrades
                    ? result.trades[result.trades.length - 1].exitPrice * result.trades[result.trades.length - 1].quantity
                    : (result.equityCurve?.[result.equityCurve.length - 1]?.value ?? 0);
                  const pnlDollars = endVal - startVal;
                  const pnlPct = startVal !== 0 ? (pnlDollars / startVal) * 100 : 0;
                  return (
                    <>
                      <span className={`text-sm font-bold ${pnlPct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%
                      </span>
                      <span className={`text-[10px] ml-1.5 ${pnlDollars >= 0 ? 'text-green-400' : 'text-red-400'}`} title="End balance − Start (first entry → last exit)">
                        {' '}({pnlDollars >= 0 ? '+' : ''}${Math.round(pnlDollars).toLocaleString()})
                      </span>
                    </>
                  );
                })()}
              </span>
            </div>
            {/* Equity curve bars - larger when expanded */}
            <div className={`flex items-end gap-px ${expanded ? 'h-16 mb-2' : 'h-8 mb-1'}`}>
              {result.equityCurve && result.equityCurve.length > 0 ? (
                result.equityCurve.slice(0, 30).map((point, idx) => {
                  const values = result.equityCurve.map(p => p.value);
                  const minVal = Math.min(...values);
                  const maxVal = Math.max(...values);
                  const range = maxVal - minVal || 1;
                  const height = Math.max(2, ((point.value - minVal) / range) * 30);
                  return (
                    <div
                      key={idx}
                      className="flex-1 rounded-t bg-blue-500"
                      style={{ height: `${height}px` }}
                      title={`${point.time}: $${point.value.toFixed(0)}`}
                    />
                  );
                })
              ) : (
                <div className="text-[10px] text-gray-500">No equity data</div>
              )}
            </div>
            <div className="flex justify-between text-[10px] text-gray-500">
              <span title={result.totalTrades !== result.trades.length ? `${result.trades.length} round-trips (${result.totalTrades} actions)` : undefined}>
                Trades: {result.trades.length}
                {result.totalTrades !== result.trades.length ? ` (${result.totalTrades} actions)` : ''}
              </span>
              <span title="First trade entry notional (entry price × quantity)">Start: ${(result.trades.length > 0
                ? result.trades[0].entryPrice * result.trades[0].quantity
                : result.equityCurve?.[0]?.value ?? 0).toFixed(0)}</span>
              <span title="Last trade exit notional (exit price × quantity)">End balance: ${(result.trades.length > 0
                ? result.trades[result.trades.length - 1].exitPrice * result.trades[result.trades.length - 1].quantity
                : result.equityCurve?.[result.equityCurve.length - 1]?.value ?? 0).toFixed(0)}</span>
            </div>
          </div>

          {/* Buy & Hold vs Strategy Comparison - same Start/Final/Strategy % as Total P&L when trades exist */}
          {result.equityCurve && result.equityCurve.length > 0 && (() => {
            const bankStart = result.equityCurve[0].value;
            const bankEnd = result.equityCurve[result.equityCurve.length - 1].value;
            const firstTrade = result.trades.length > 0 ? result.trades[0] : null;
            const lastTrade = result.trades.length > 0 ? result.trades[result.trades.length - 1] : null;
            const entryExposure = firstTrade ? firstTrade.entryPrice * firstTrade.quantity : bankStart;
            const finalValue = lastTrade ? lastTrade.exitPrice * lastTrade.quantity : bankEnd;
            const strategyPnL = result.tradeBasedReturnPct != null ? result.tradeBasedReturnPct : ((bankEnd - bankStart) / bankStart) * 100;
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
                    <div className={`text-xs font-medium ${(finalValue - entryExposure) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(finalValue - entryExposure) >= 0 ? '+' : ''}${Math.round(finalValue - entryExposure).toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-gray-900 p-2 rounded border border-yellow-600/30">
                    <div className="text-[9px] text-yellow-500">Buy & Hold</div>
                    <div className={`text-xs font-medium ${buyHold >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {buyHold >= 0 ? '+' : ''}{buyHold.toFixed(1)}%
                    </div>
                  </div>
                  <div className="bg-gray-900 p-2 rounded border border-blue-600/30">
                    <div className="text-[9px] text-blue-400">Strategy</div>
                    <div className={`text-xs font-medium ${strategyPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {strategyPnL >= 0 ? '+' : ''}{strategyPnL.toFixed(1)}%
                    </div>
                  </div>
                </div>
                <div className={`text-[10px] text-center mt-1 ${vsBenchmark >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {vsBenchmark >= 0 ? '+' : ''}{vsBenchmark.toFixed(1)}% vs Buy & Hold
                </div>
              </div>
            );
          })()}

          {/* Metrics Grid - Return matches Total P&L when tradeBasedReturnPct is set */}
          <div className={`${expanded ? 'grid grid-cols-6 gap-2' : 'grid grid-cols-3 gap-1'}`}>
            <div className="bg-gray-900 p-1.5 rounded text-center">
              <div className="text-[10px] text-gray-500">Return</div>
              <div className={`text-xs font-medium ${(result.tradeBasedReturnPct ?? result.totalReturn * 100) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(result.tradeBasedReturnPct ?? result.totalReturn * 100) >= 0 ? '+' : ''}{(result.tradeBasedReturnPct ?? result.totalReturn * 100).toFixed(1)}%
              </div>
            </div>
            <div className="bg-gray-900 p-1.5 rounded text-center">
              <div className="text-[10px] text-gray-500">Sharpe</div>
              <div className="text-xs text-white">{result.sharpeRatio.toFixed(2)}</div>
            </div>
            <div className="bg-gray-900 p-1.5 rounded text-center">
              <div className="text-[10px] text-gray-500">Max DD</div>
              <div className="text-xs text-red-400" title={result.tradeBasedMaxDrawdownPct != null ? 'Worst single-trade return %' : undefined}>
                -{(Math.abs(result.tradeBasedMaxDrawdownPct ?? result.maxDrawdown) * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Trades List - larger when expanded */}
          {showTrades && (
            <div className={`overflow-y-auto ${expanded ? 'max-h-[300px] text-xs' : 'max-h-[150px] text-[10px]'}`}>
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
                    <div key={trade.id} className={`grid grid-cols-5 gap-1 py-0.5 rounded ${trade.isWin ? 'bg-green-900/20' : 'bg-red-900/20'}`}>
                      <span className="text-gray-500">{idx + 1}</span>
                      <span className="text-gray-400" title={`$${trade.entryPrice.toFixed(2)} × ${trade.quantity}`}>${Math.round(entryNotional).toLocaleString()}</span>
                      <span className="text-gray-400" title={`$${trade.exitPrice.toFixed(2)} × ${trade.quantity}`}>${Math.round(exitNotional).toLocaleString()}</span>
                      <span className={trade.isWin ? 'text-green-400' : 'text-red-400'}>
                        {trade.isWin ? '+' : ''}{trade.pnl.toFixed(0)}
                      </span>
                      <span className={trade.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {trade.pnlPercent >= 0 ? '+' : ''}{trade.pnlPercent.toFixed(1)}%
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default StrategyBacktestPanel;
