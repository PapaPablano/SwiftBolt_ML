/**
 * StrategyPlatform — Unified strategy management interface
 * =========================================================
 * Single React route (/strategy-platform) that combines:
 *   • Strategies: CRUD saved strategies, select active
 *   • Builder:    Entry + exit condition editors
 *   • Backtest:   StrategyBacktestPanel with symbol context
 *   • Paper Trading: Live PaperTradingDashboard
 */

import React, { useState, useEffect } from 'react';
import { Plus, Trash2, ChevronRight, RefreshCw, AlertCircle } from 'lucide-react';
import type { Condition } from '../lib/conditionBuilderUtils';
import type { Strategy, StrategyConfig } from '../types/strategyBacktest';
import { StrategyConditionBuilder } from './StrategyConditionBuilder';
import { StrategyBacktestPanel } from './StrategyBacktestPanel';
import { PaperTradingDashboard } from './PaperTradingDashboard';
import type { EntryExitCondition, ConditionType } from '../types/strategyBacktest';
import {
  fetchStrategiesFromSupabase,
  saveStrategyToSupabase,
} from '../lib/backtestService';
import { createDefaultConfig, isStrategyIdUuid, conditionTypes } from '../lib/backtestConstants';
import { strategiesApi } from '../api/strategiesApi';
import { LiveTradingDashboard } from './LiveTradingDashboard';
import { useEmbeddedSymbol } from '../hooks/useEmbeddedSymbol';

const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? '';

/** Full indicator name list driven by the canonical conditionTypes registry. */
const AVAILABLE_INDICATORS = conditionTypes.map((ct) => ct.name);

/** Map indicator display name → ConditionType id for Supabase persistence. */
const INDICATOR_NAME_TO_TYPE: Record<string, ConditionType> = Object.fromEntries(
  conditionTypes.map((ct) => [ct.name, ct.id as ConditionType])
);

/** Convert a UI Condition (conditionBuilderUtils format) to the backend EntryExitCondition. */
function uiConditionToEntryExit(c: import('../lib/conditionBuilderUtils').Condition): EntryExitCondition {
  const type: ConditionType = INDICATOR_NAME_TO_TYPE[c.indicator] ?? 'rsi';
  if ('value' in c) {
    return { type, params: {}, operator: c.operator as EntryExitCondition['operator'], value: c.value };
  }
  if ('minValue' in c) {
    return { type, params: {}, operator: '>' as EntryExitCondition['operator'], value: c.minValue };
  }
  // crossWith — use value 0 as placeholder
  return { type, params: {}, operator: c.operator as EntryExitCondition['operator'], value: 0 };
}

// ---------------------------------------------------------------------------
// Tab types
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'strategies', label: 'Strategies' },
  { id: 'builder', label: 'Builder' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'paper-trading', label: 'Paper Trading' },
  { id: 'live-trading', label: 'Live Trading' },
] as const;

export type PlatformTab = typeof TABS[number]['id'];

/** Narrows a raw URL param string to PlatformTab without unsafe cast. */
export function isPlatformTab(value: string): value is PlatformTab {
  return TABS.some((t) => t.id === value);
}

// ---------------------------------------------------------------------------
// Strategies tab
// ---------------------------------------------------------------------------

interface StrategiesTabProps {
  strategies: Strategy[];
  isLoading: boolean;
  activeStrategy: Strategy | null;
  onSelect: (strategy: Strategy) => void;
  onDelete: (id: string) => void;
  onRefresh: () => void;
  onNavigate: (tab: PlatformTab) => void;
  onCreate: () => void;
}

function StrategiesTab({
  strategies,
  isLoading,
  activeStrategy,
  onSelect,
  onDelete,
  onRefresh,
  onNavigate,
  onCreate,
}: StrategiesTabProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function handleDelete(id: string) {
    if (!isStrategyIdUuid(id)) return;
    setDeletingId(id);
    try {
      await strategiesApi.delete(id, SUPABASE_ANON_KEY);
      onRefresh();
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="p-4 max-w-2xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-white">Saved Strategies</h2>
        <div className="flex gap-2">
          <button
            onClick={onRefresh}
            className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={onCreate}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded bg-blue-600 text-white hover:bg-blue-500 transition-colors"
          >
            <Plus size={12} />
            New Strategy
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-500 text-sm">Loading strategies…</div>
      ) : strategies.length === 0 ? (
        <div className="text-center py-12 text-gray-500 text-sm">
          No strategies yet.{' '}
          <button onClick={onCreate} className="text-blue-400 hover:text-blue-300">
            Create your first strategy
          </button>{' '}
          in the Builder tab.
        </div>
      ) : (
        <div className="space-y-2">
          {strategies.map((strategy) => {
            const isActive = activeStrategy?.id === strategy.id;
            return (
              <div
                key={strategy.id}
                className={`flex items-center gap-3 p-3 rounded-lg border transition-colors cursor-pointer ${
                  isActive
                    ? 'border-blue-600 bg-blue-900/20'
                    : 'border-gray-700 bg-gray-900 hover:border-gray-600'
                }`}
                onClick={() => onSelect(strategy)}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-white truncate">{strategy.name}</div>
                  {strategy.description && (
                    <div className="text-xs text-gray-400 truncate mt-0.5">{strategy.description}</div>
                  )}
                  <div className="text-xs text-gray-600 mt-0.5">
                    {strategy.config.entryConditions.length} entry ·{' '}
                    {strategy.config.exitConditions.length} exit conditions
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  {isActive && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onNavigate('backtest');
                      }}
                      className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-blue-700 text-white hover:bg-blue-600"
                    >
                      Backtest <ChevronRight size={10} />
                    </button>
                  )}
                  {isStrategyIdUuid(strategy.id) && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(strategy.id);
                      }}
                      disabled={deletingId === strategy.id}
                      className="p-1.5 rounded text-gray-500 hover:text-red-400 hover:bg-red-900/20 transition-colors"
                      title="Delete strategy"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Builder tab
// ---------------------------------------------------------------------------

interface BuilderTabProps {
  entryConditions: Condition[];
  exitConditions: Condition[];
  onEntryChange: (c: Condition[]) => void;
  onExitChange: (c: Condition[]) => void;
  strategyName: string;
  onNameChange: (n: string) => void;
  onSave: () => void;
  isSaving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
}

function BuilderTab({
  entryConditions,
  exitConditions,
  onEntryChange,
  onExitChange,
  strategyName,
  onNameChange,
  onSave,
  isSaving,
  saveError,
  saveSuccess,
}: BuilderTabProps) {
  return (
    <div className="dark p-4 max-w-3xl space-y-6">
      {/* Strategy name + save */}
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-400 mb-1">Strategy Name</label>
          <input
            type="text"
            value={strategyName}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="e.g. RSI Mean Reversion"
            className="w-full px-3 py-2 text-sm rounded bg-gray-900 border border-gray-700 text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
          />
        </div>
        <button
          onClick={onSave}
          disabled={isSaving || !strategyName.trim()}
          className="px-4 py-2 text-sm font-medium rounded bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSaving ? 'Saving…' : 'Save Strategy'}
        </button>
      </div>

      {saveError && (
        <div className="flex items-center gap-2 px-3 py-2 rounded bg-red-900/30 border border-red-700 text-red-400 text-sm">
          <AlertCircle size={14} />
          {saveError}
        </div>
      )}
      {saveSuccess && (
        <div className="px-3 py-2 rounded bg-green-900/30 border border-green-700 text-green-400 text-sm">
          Strategy saved successfully.
        </div>
      )}

      {/* Entry conditions */}
      <div>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Entry Conditions
        </h3>
        <StrategyConditionBuilder
          signalType="entry"
          initialConditions={entryConditions}
          onConditionsChange={onEntryChange}
          availableIndicators={AVAILABLE_INDICATORS}
        />
      </div>

      {/* Exit conditions */}
      <div>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Exit Conditions
        </h3>
        <StrategyConditionBuilder
          signalType="exit"
          initialConditions={exitConditions}
          onConditionsChange={onExitChange}
          availableIndicators={AVAILABLE_INDICATORS}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StrategyPlatform root
// ---------------------------------------------------------------------------

interface StrategyPlatformProps {
  symbol?: string;
  initialTab?: PlatformTab;
}

export function StrategyPlatform({ symbol: symbolProp, initialTab }: StrategyPlatformProps = {}) {
  const symbol = useEmbeddedSymbol(symbolProp ?? 'AAPL');
  const [activeTab, setActiveTab] = useState<PlatformTab>(initialTab ?? 'strategies');
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [activeStrategy, setActiveStrategy] = useState<Strategy | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Builder state
  const [entryConditions, setEntryConditions] = useState<Condition[]>([]);
  const [exitConditions, setExitConditions] = useState<Condition[]>([]);
  const [strategyName, setStrategyName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    loadStrategies();
  }, []);

  // Notify native bridge when active strategy changes
  useEffect(() => {
    if (activeStrategy) {
      window.postMessage({ type: 'strategyUpdated', strategyId: activeStrategy.id }, '*');
    }
  }, [activeStrategy]);

  async function loadStrategies() {
    setIsLoading(true);
    const list = await fetchStrategiesFromSupabase();
    setStrategies(list);
    setIsLoading(false);
  }

  function handleSelectStrategy(strategy: Strategy) {
    setActiveStrategy(strategy);
  }

  function handleCreateNew() {
    setActiveStrategy(null);
    setEntryConditions([]);
    setExitConditions([]);
    setStrategyName('');
    setSaveError(null);
    setSaveSuccess(false);
    setActiveTab('builder');
  }

  async function handleSaveStrategy() {
    if (!strategyName.trim()) return;
    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    const base = createDefaultConfig();
    const config: StrategyConfig = {
      ...base,
      entryConditions:
        entryConditions.length > 0
          ? entryConditions.map(uiConditionToEntryExit)
          : base.entryConditions,
      exitConditions:
        exitConditions.length > 0
          ? exitConditions.map(uiConditionToEntryExit)
          : base.exitConditions,
    };
    const result = await saveStrategyToSupabase({
      id: '',
      name: strategyName.trim(),
      description: `Entry: ${entryConditions.length} conditions, Exit: ${exitConditions.length} conditions`,
      config,
    });

    if ('error' in result && !result.success) {
      setSaveError(result.error.message);
    } else {
      setSaveSuccess(true);
      setStrategyName('');
      setEntryConditions([]);
      setExitConditions([]);
      await loadStrategies();
      // Brief success message then clear
      setTimeout(() => setSaveSuccess(false), 3000);
    }
    setIsSaving(false);
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header bar */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-800 bg-gray-950">
        <h1 className="text-sm font-semibold text-white">Strategy Platform</h1>
        {symbol && (
          <span className="px-2 py-0.5 text-xs font-mono text-blue-400 bg-blue-900/30 rounded border border-blue-800">
            {symbol}
          </span>
        )}
        {activeStrategy && (
          <span className="px-2 py-0.5 text-xs text-emerald-400 bg-emerald-900/20 rounded border border-emerald-800 truncate max-w-40">
            {activeStrategy.name}
          </span>
        )}

        {/* Tab navigation */}
        <div className="flex gap-0.5 ml-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'strategies' && (
          <StrategiesTab
            strategies={strategies}
            isLoading={isLoading}
            activeStrategy={activeStrategy}
            onSelect={handleSelectStrategy}
            onDelete={() => loadStrategies()}
            onRefresh={loadStrategies}
            onNavigate={setActiveTab}
            onCreate={handleCreateNew}
          />
        )}

        {activeTab === 'builder' && (
          <BuilderTab
            entryConditions={entryConditions}
            exitConditions={exitConditions}
            onEntryChange={setEntryConditions}
            onExitChange={setExitConditions}
            strategyName={strategyName}
            onNameChange={setStrategyName}
            onSave={handleSaveStrategy}
            isSaving={isSaving}
            saveError={saveError}
            saveSuccess={saveSuccess}
          />
        )}

        {activeTab === 'backtest' && (
          <div className="p-4">
            <StrategyBacktestPanel
              symbol={symbol}
              horizon="1D"
              expanded={true}
            />
          </div>
        )}

        {activeTab === 'paper-trading' && (
          <div className="p-4">
            <PaperTradingDashboard />
          </div>
        )}

        {activeTab === 'live-trading' && (
          <LiveTradingDashboard onBack={() => setActiveTab('strategies')} />
        )}
      </div>
    </div>
  );
}

export default StrategyPlatform;
