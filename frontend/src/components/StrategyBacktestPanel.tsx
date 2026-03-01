import React, { useState, useEffect } from 'react';
import type {
  Strategy,
  StrategyConfig,
  EntryExitCondition,
  BacktestResult,
  ConditionPreset,
  StrategyBacktestPanelProps,
} from '../types/strategyBacktest';
import {
  conditionTypes,
  operators,
  datePresets,
  isStrategyIdUuid,
  createDefaultConfig,
} from '../lib/backtestConstants';
import {
  fetchStrategiesFromSupabase,
  saveStrategyToSupabase,
  updateStrategyInSupabase,
  runBacktestViaAPI,
} from '../lib/backtestService';
import BacktestResultsPanel from './BacktestResultsPanel';

const defaultStrategies: Strategy[] = [
  {
    id: '1',
    name: 'RSI Mean Reversion',
    description: 'Buy RSI<30, sell RSI>70',
    config: createDefaultConfig(),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: '2',
    name: 'SMA Crossover',
    description: 'Fast SMA crosses slow SMA',
    config: {
      entryConditions: [
        { type: 'sma_cross', params: { fastPeriod: 10, slowPeriod: 50 }, operator: 'cross_up', value: 0 },
      ],
      exitConditions: [
        { type: 'sma_cross', params: { fastPeriod: 10, slowPeriod: 50 }, operator: 'cross_down', value: 0 },
      ],
      positionSizing: { type: 'percent_of_equity', value: 2 },
      riskManagement: { stopLoss: { type: 'percent', value: 2 }, takeProfit: { type: 'percent', value: 5 } },
    },
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: '3',
    name: 'SuperTrend',
    description: 'AI SuperTrend strategy',
    config: {
      entryConditions: [{ type: 'rsi', params: { period: 14 }, operator: '<', value: 50 }],
      exitConditions: [{ type: 'rsi', params: { period: 14 }, operator: '>', value: 50 }],
      positionSizing: { type: 'percent_of_equity', value: 2 },
      riskManagement: { stopLoss: { type: 'percent', value: 3 }, takeProfit: { type: 'percent', value: 6 } },
    },
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

export const StrategyBacktestPanel: React.FC<StrategyBacktestPanelProps> = ({
  symbol,
  horizon,
  expanded = false,
  startDate: parentStartDate,
  endDate: parentEndDate,
  onBacktestComplete,
  onDateRangeChange,
}) => {
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

  useEffect(() => {
    const loadStrategies = async () => {
      const dbStrategies = await fetchStrategiesFromSupabase();
      if (dbStrategies.length > 0) {
        setStrategies([...defaultStrategies, ...dbStrategies]);
        setSelectedStrategy(dbStrategies[0]);
      }
    };
    loadStrategies();
  }, []);

  const getPresetDates = (presetId: string) => {
    const now = new Date();
    const preset = datePresets.find((p) => p.id === presetId);
    if (!preset) return { start: new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000), end: now };
    if ('days' in preset && preset.days)
      return { start: new Date(now.getTime() - preset.days * 24 * 60 * 60 * 1000), end: now };
    if ('startDate' in preset && preset.startDate && preset.endDate)
      return { start: new Date(preset.startDate as string), end: new Date(preset.endDate as string) };
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
    if (savedId) newStrategy.id = savedId;
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
    const cond: EntryExitCondition = { type: 'rsi', params: { period: 14 }, operator: '<', value: 30 };
    if (isEntry) {
      setNewConfig({ ...newConfig, entryConditions: [...newConfig.entryConditions, cond] });
    } else {
      setNewConfig({ ...newConfig, exitConditions: [...newConfig.exitConditions, cond] });
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
      const ct = conditionTypes.find((c) => c.id === value);
      if (ct) {
        const params: Record<string, number> = {};
        ct.params.forEach((p) => (params[p.name] = p.default));
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
    setResult(null);
    onBacktestComplete?.(null);
    setIsRunning(true);
    const startDateStr =
      parentStartDate && parentEndDate
        ? parentStartDate.toISOString().split('T')[0]
        : getPresetDates(selectedPreset).start.toISOString().split('T')[0];
    const endDateStr =
      parentStartDate && parentEndDate
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

  const renderConditionBuilder = (isEntry: boolean) => {
    const conditions = isEntry ? newConfig.entryConditions : newConfig.exitConditions;
    return (
      <div className="flex flex-col flex-1 min-w-0 rounded border border-gray-600 bg-gray-700/40">
        <div className="flex justify-between items-center px-1.5 py-0.5 border-b border-gray-600 shrink-0">
          <span className="text-[11px] font-medium text-gray-400">{isEntry ? 'Entry' : 'Exit'}</span>
          <button
            onClick={() => addCondition(isEntry)}
            className="text-[11px] text-blue-400 hover:text-blue-300 whitespace-nowrap"
          >
            + Add
          </button>
        </div>
        <div className="space-y-0.5 p-1 min-h-0">
          {conditions.map((condition, idx) => {
            const ctConfig = conditionTypes.find((c) => c.id === condition.type);
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
                      {conditionTypes.map((ct) => (
                        <option key={ct.id} value={ct.id}>
                          {ct.name}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => removeCondition(isEntry, idx)}
                      className="shrink-0 p-0.5 text-gray-500 hover:text-red-400"
                      aria-label="Remove"
                    >
                      ✕
                    </button>
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
                      {operators.map((op) => (
                        <option key={op.id} value={op.id}>
                          {op.label}
                        </option>
                      ))}
                    </select>
                    {condition.operator !== 'cross_up' && condition.operator !== 'cross_down' && (
                      <input
                        type="number"
                        value={condition.value}
                        onChange={(e) =>
                          updateCondition(isEntry, idx, 'value', parseFloat(e.target.value))
                        }
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

        {/* Strategy List */}
        <div className="space-y-0.5 max-h-[120px] overflow-y-auto">
          {strategies.length === 0 ? (
            <div className="py-1 text-xs text-gray-500">No strategies - create one</div>
          ) : (
            strategies.map((strategy) => (
              <div
                key={strategy.id}
                className={`py-1 px-2 rounded cursor-pointer text-xs border ${
                  selectedStrategy?.id === strategy.id
                    ? 'border-blue-500 bg-blue-500/10'
                    : 'border-gray-700 bg-gray-800 hover:border-gray-600'
                }`}
                onClick={() => setSelectedStrategy(strategy)}
              >
                <div className="text-white font-medium truncate">{strategy.name}</div>
                <div className="text-gray-500 text-[10px] truncate">{strategy.description}</div>
              </div>
            ))
          )}
        </div>

        {/* Create / Edit Form */}
        {(isCreating || isEditing) && (
          <div className="flex flex-col p-2.5 bg-gray-800 rounded border border-gray-600 space-y-1.5">
            <span className="text-[11px] font-medium text-gray-400">
              {isEditing ? 'Edit strategy' : 'New strategy'}
            </span>
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
            {/* Risk Management */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-2 bg-gray-700/50 rounded border border-gray-600">
              <span className="sm:col-span-2 text-[11px] font-medium text-gray-400">Risk management</span>
              <div className="flex flex-wrap items-center gap-1.5">
                <label className="text-[11px] text-gray-400 shrink-0">Stop loss</label>
                <select
                  value={newConfig.riskManagement.stopLoss.type}
                  onChange={(e) =>
                    setNewConfig({
                      ...newConfig,
                      riskManagement: {
                        ...newConfig.riskManagement,
                        stopLoss: {
                          ...newConfig.riskManagement.stopLoss,
                          type: e.target.value as 'percent' | 'fixed',
                        },
                      },
                    })
                  }
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
                  onChange={(e) =>
                    setNewConfig({
                      ...newConfig,
                      riskManagement: {
                        ...newConfig.riskManagement,
                        stopLoss: {
                          ...newConfig.riskManagement.stopLoss,
                          value: parseFloat(e.target.value) || 0,
                        },
                      },
                    })
                  }
                  className="w-14 px-1.5 py-0.5 bg-gray-800 border border-gray-600 rounded text-white text-[11px] text-right"
                />
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <label className="text-[11px] text-gray-400 shrink-0">Take profit</label>
                <select
                  value={newConfig.riskManagement.takeProfit.type}
                  onChange={(e) =>
                    setNewConfig({
                      ...newConfig,
                      riskManagement: {
                        ...newConfig.riskManagement,
                        takeProfit: {
                          ...newConfig.riskManagement.takeProfit,
                          type: e.target.value as 'percent' | 'fixed',
                        },
                      },
                    })
                  }
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
                  onChange={(e) =>
                    setNewConfig({
                      ...newConfig,
                      riskManagement: {
                        ...newConfig.riskManagement,
                        takeProfit: {
                          ...newConfig.riskManagement.takeProfit,
                          value: parseFloat(e.target.value) || 0,
                        },
                      },
                    })
                  }
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
        {selectedStrategy && (
          <div className="text-xs space-y-0.5">
            <div>
              <span className="text-gray-400">Strategy: </span>
              <span className="text-white font-medium">{selectedStrategy.name}</span>
            </div>
            <div className="text-[11px] text-gray-500">
              Stop loss:{' '}
              {selectedStrategy.config.riskManagement.stopLoss.type === 'percent'
                ? `${selectedStrategy.config.riskManagement.stopLoss.value}%`
                : `$${selectedStrategy.config.riskManagement.stopLoss.value}`}
              {' · '}
              Take profit:{' '}
              {selectedStrategy.config.riskManagement.takeProfit.type === 'percent'
                ? `${selectedStrategy.config.riskManagement.takeProfit.value}%`
                : `$${selectedStrategy.config.riskManagement.takeProfit.value}`}
            </div>
          </div>
        )}

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

      {result && (
        <BacktestResultsPanel
          result={result}
          expanded={expanded}
          showEquityChart={showEquityChart}
          showTrades={showTrades}
          onToggleChart={() => setShowEquityChart(!showEquityChart)}
          onToggleTrades={() => setShowTrades(!showTrades)}
        />
      )}
    </div>
  );
};

export default StrategyBacktestPanel;
