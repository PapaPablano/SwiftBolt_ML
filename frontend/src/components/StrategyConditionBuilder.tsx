import React, { useState, useCallback, useMemo } from 'react';
import { ChevronDown, ChevronUp, Plus, Trash2, Copy } from 'lucide-react';
import {
  type Condition,
  type ConditionBuilderProps,
  type ConditionTreeNode,
  COMPARISON_OPERATORS,
  CROSS_OPERATORS,
  RANGE_OPERATORS,
  MAX_CONDITIONS_PER_SIGNAL,
  generateId,
  validateCondition,
  buildConditionTree,
  type ComparisonOperator,
  type CrossOperator,
  type RangeOperator,
} from '../lib/conditionBuilderUtils';

// Re-export Condition so existing test imports keep working.
export type { Condition };

// ============================================================================
// ConditionForm
// ============================================================================

interface ConditionFormProps {
  condition: Condition | null;
  availableIndicators: string[];
  onSave: (condition: Condition) => void;
  onCancel: () => void;
  error: string | null;
}

function ConditionForm({ condition, availableIndicators, onSave, onCancel, error }: ConditionFormProps) {
  const [formData, setFormData] = useState<Condition>(
    condition || {
      id: generateId(),
      indicator: availableIndicators[0] || 'RSI',
      operator: '>',
      value: 50,
      logicalOp: 'AND',
    }
  );

  const handleOperatorChange = (op: string) => {
    let newFormData: Condition;

    if (op === 'cross_up' || op === 'cross_down') {
      newFormData = {
        id: formData.id,
        indicator: formData.indicator,
        operator: op as CrossOperator,
        crossWith: availableIndicators[1] || 'Signal',
        logicalOp: formData.logicalOp,
        parentId: formData.parentId,
      };
    } else if (op === 'touches' || op === 'within_range') {
      newFormData = {
        id: formData.id,
        indicator: formData.indicator,
        operator: op as RangeOperator,
        minValue: 'minValue' in formData ? formData.minValue : 0,
        maxValue: 'maxValue' in formData ? formData.maxValue : 100,
        logicalOp: formData.logicalOp,
        parentId: formData.parentId,
      };
    } else {
      newFormData = {
        id: formData.id,
        indicator: formData.indicator,
        operator: op as ComparisonOperator,
        value: 'value' in formData ? formData.value : 50,
        logicalOp: formData.logicalOp,
        parentId: formData.parentId,
      };
    }

    setFormData(newFormData);
  };

  const operatorType = (() => {
    if (COMPARISON_OPERATORS.includes(formData.operator as ComparisonOperator)) return 'comparison';
    if (CROSS_OPERATORS.includes(formData.operator as CrossOperator)) return 'cross';
    if (RANGE_OPERATORS.includes(formData.operator as RangeOperator)) return 'range';
    return 'comparison';
  })();

  return (
    <div className="p-3 bg-gray-800 rounded-lg border border-gray-700">
      <div className="grid grid-cols-2 gap-2">
        {/* Indicator Selection */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-0.5">Indicator</label>
          <select
            value={formData.indicator}
            onChange={(e) => setFormData({ ...formData, indicator: e.target.value })}
            className="w-full px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {availableIndicators.map((ind) => (
              <option key={ind} value={ind}>
                {ind}
              </option>
            ))}
          </select>
        </div>

        {/* Operator Selection */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-0.5">Condition</label>
          <select
            value={formData.operator}
            onChange={(e) => handleOperatorChange(e.target.value)}
            className="w-full px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <optgroup label="Comparison">
              {COMPARISON_OPERATORS.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </optgroup>
            <optgroup label="Cross">
              {CROSS_OPERATORS.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </optgroup>
            <optgroup label="Range">
              {RANGE_OPERATORS.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </optgroup>
          </select>
        </div>

        {/* Dynamic Value Inputs */}
        {operatorType === 'comparison' && 'value' in formData && (
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-0.5">Value</label>
            <input
              type="number"
              value={formData.value}
              onChange={(e) => setFormData({ ...formData, value: parseFloat(e.target.value) || 0 })}
              className="w-full px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        )}

        {operatorType === 'cross' && 'crossWith' in formData && (
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-0.5">Cross With</label>
            <input
              type="text"
              value={formData.crossWith}
              onChange={(e) => setFormData({ ...formData, crossWith: e.target.value })}
              placeholder="e.g., MACD_Signal"
              className="w-full px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        )}

        {operatorType === 'range' && 'minValue' in formData && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-0.5">Min</label>
              <input
                type="number"
                value={formData.minValue}
                onChange={(e) =>
                  setFormData({ ...formData, minValue: parseFloat(e.target.value) || 0 })
                }
                className="w-full px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-0.5">Max</label>
              <input
                type="number"
                value={formData.maxValue}
                onChange={(e) =>
                  setFormData({ ...formData, maxValue: parseFloat(e.target.value) || 0 })
                }
                className="w-full px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </>
        )}

        {/* Logical Operator */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-0.5">Logic</label>
          <div className="flex gap-3">
            {(['AND', 'OR'] as const).map((op) => (
              <label key={op} className="flex items-center">
                <input
                  type="radio"
                  name="logicalOp"
                  value={op}
                  checked={formData.logicalOp === op}
                  onChange={(e) =>
                    setFormData({ ...formData, logicalOp: e.target.value as 'AND' | 'OR' })
                  }
                  className="mr-1"
                />
                <span className="text-xs text-gray-300">{op}</span>
              </label>
            ))}
          </div>
        </div>

        {error && <div className="col-span-2 text-xs text-red-400 bg-red-900/30 p-1.5 rounded">{error}</div>}

        <div className="col-span-2 flex gap-2 pt-1">
          <button
            onClick={() => onSave(formData)}
            className="flex-1 px-3 py-1.5 bg-blue-600 text-white rounded text-xs font-medium hover:bg-blue-700"
          >
            Save
          </button>
          <button
            onClick={onCancel}
            className="flex-1 px-3 py-1.5 border border-gray-600 text-gray-300 rounded text-xs font-medium hover:bg-gray-700"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// ConditionTreeView
// ============================================================================

interface ConditionTreeViewProps {
  tree: ConditionTreeNode | null;
  onEdit: (condition: Condition) => void;
  onDelete: (conditionId: string) => void;
  onDuplicate: (condition: Condition) => void;
}

function ConditionTreeView({ tree, onEdit, onDelete, onDuplicate }: ConditionTreeViewProps) {
  if (!tree) {
    return (
      <div className="text-center py-4 text-gray-500">
        <p className="text-xs">No conditions added yet</p>
      </div>
    );
  }

  function renderNode(node: ConditionTreeNode, depth: number = 0): React.ReactNode {
    const { condition, children } = node;
    const isComparison = 'value' in condition;
    const isCross = 'crossWith' in condition;

    let conditionLabel = '';
    if (isComparison) {
      conditionLabel = `${condition.indicator} ${condition.operator} ${condition.value}`;
    } else if (isCross) {
      conditionLabel = `${condition.indicator} ${condition.operator} ${condition.crossWith}`;
    } else if ('minValue' in condition) {
      conditionLabel = `${condition.indicator} ${condition.operator} [${condition.minValue}, ${condition.maxValue}]`;
    }

    return (
      <div key={condition.id} className="mb-2">
        <div className="bg-gray-900 border-l-2 border-blue-500 p-2 rounded-r shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <p className="text-xs font-mono text-gray-200 truncate">{conditionLabel}</p>
              <p className="text-[10px] text-gray-500">{condition.logicalOp}</p>
            </div>
            <div className="flex gap-0.5 ml-1 shrink-0">
              <button
                onClick={() => onEdit(condition)}
                className="p-0.5 text-gray-500 hover:text-blue-400 rounded"
                title="Edit"
              >
                ✎
              </button>
              <button
                onClick={() => onDuplicate(condition)}
                className="p-0.5 text-gray-500 hover:text-green-400 rounded"
                title="Duplicate"
              >
                <Copy size={12} />
              </button>
              <button
                onClick={() => onDelete(condition.id)}
                className="p-0.5 text-gray-500 hover:text-red-400 rounded"
                title="Delete"
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        </div>

        {children.length > 0 && (
          <div className="ml-4 mt-1 border-l border-gray-700 pl-3">
            {children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  }

  return <div className="py-2">{renderNode(tree)}</div>;
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const StrategyConditionBuilder: React.FC<ConditionBuilderProps> = ({
  signalType,
  initialConditions,
  onConditionsChange,
  availableIndicators,
}) => {
  const [conditions, setConditions] = useState<Condition[]>(initialConditions);
  const [editingCondition, setEditingCondition] = useState<Condition | null>(null);
  const [expanded, setExpanded] = useState(true);

  const tree = useMemo(() => buildConditionTree(conditions), [conditions]);

  const errors = useMemo(() => {
    const errorMap = new Map<string, string>();
    conditions.forEach((c) => {
      const error = validateCondition(c);
      if (error) errorMap.set(c.id, error);
    });
    return errorMap;
  }, [conditions]);

  const handleAddCondition = useCallback(() => {
    if (conditions.length >= MAX_CONDITIONS_PER_SIGNAL) {
      alert(`Maximum ${MAX_CONDITIONS_PER_SIGNAL} conditions per signal type`);
      return;
    }
    setEditingCondition({
      id: generateId(),
      indicator: availableIndicators[0] || 'RSI',
      operator: '>',
      value: 50,
      logicalOp: 'AND',
    });
  }, [conditions.length, availableIndicators]);

  const handleSaveCondition = useCallback(
    (condition: Condition) => {
      const error = validateCondition(condition);
      if (error) {
        alert(error);
        return;
      }

      if (editingCondition && editingCondition.id === condition.id) {
        setConditions(conditions.map((c) => (c.id === condition.id ? condition : c)));
      } else {
        setConditions([...conditions, condition]);
      }

      setEditingCondition(null);
      onConditionsChange([...conditions, condition]);
    },
    [editingCondition, conditions, onConditionsChange]
  );

  const handleDeleteCondition = useCallback(
    (conditionId: string) => {
      const updated = conditions.filter((c) => c.id !== conditionId);
      setConditions(updated);
      onConditionsChange(updated);
    },
    [conditions, onConditionsChange]
  );

  const handleDuplicateCondition = useCallback(
    (condition: Condition) => {
      if (conditions.length >= MAX_CONDITIONS_PER_SIGNAL) {
        alert(`Maximum ${MAX_CONDITIONS_PER_SIGNAL} conditions per signal type`);
        return;
      }
      const newCondition = { ...condition, id: generateId() };
      const updated = [...conditions, newCondition];
      setConditions(updated);
      onConditionsChange(updated);
    },
    [conditions, onConditionsChange]
  );

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
      <div
        className="px-3 py-2 border-b border-gray-700 bg-gray-800 cursor-pointer hover:bg-gray-750 flex items-center justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <h3 className="text-sm font-semibold text-gray-200 capitalize">{signalType} Conditions</h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 bg-gray-700 px-2 py-0.5 rounded">
            {conditions.length} / {MAX_CONDITIONS_PER_SIGNAL}
          </span>
          {expanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
        </div>
      </div>

      {expanded && (
        <div className="p-3">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div>
              <h4 className="text-xs font-semibold text-gray-300 mb-2">Add/Edit Condition</h4>
              {editingCondition ? (
                <ConditionForm
                  condition={editingCondition}
                  availableIndicators={availableIndicators}
                  onSave={handleSaveCondition}
                  onCancel={() => setEditingCondition(null)}
                  error={errors.get(editingCondition.id) || null}
                />
              ) : (
                <button
                  onClick={handleAddCondition}
                  disabled={conditions.length >= MAX_CONDITIONS_PER_SIGNAL}
                  className={`w-full py-2 rounded border-2 border-dashed flex items-center justify-center gap-1.5 text-xs transition-colors ${
                    conditions.length >= MAX_CONDITIONS_PER_SIGNAL
                      ? 'border-gray-700 text-gray-600 cursor-not-allowed'
                      : 'border-blue-500/40 text-blue-400 hover:bg-blue-900/20'
                  }`}
                >
                  <Plus size={14} />
                  Add Condition
                </button>
              )}
            </div>

            <div>
              <h4 className="text-xs font-semibold text-gray-300 mb-2">Logic Tree</h4>
              <div className="bg-gray-800 rounded p-3 border border-gray-700 max-h-72 overflow-y-auto">
                <ConditionTreeView
                  tree={tree}
                  onEdit={setEditingCondition}
                  onDelete={handleDeleteCondition}
                  onDuplicate={handleDuplicateCondition}
                />
              </div>
            </div>
          </div>

          {errors.size > 0 && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm font-medium text-yellow-800">⚠ Validation Issues:</p>
              <ul className="text-sm text-yellow-700 mt-1 ml-4 list-disc">
                {Array.from(errors.values()).map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
