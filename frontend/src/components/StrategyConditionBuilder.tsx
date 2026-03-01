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
    <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
      <div className="grid grid-cols-1 gap-3">
        {/* Indicator Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Indicator</label>
          <select
            value={formData.indicator}
            onChange={(e) => setFormData({ ...formData, indicator: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
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
          <label className="block text-sm font-medium text-gray-700 mb-1">Condition</label>
          <select
            value={formData.operator}
            onChange={(e) => handleOperatorChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
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
            <label className="block text-sm font-medium text-gray-700 mb-1">Value</label>
            <input
              type="number"
              value={formData.value}
              onChange={(e) => setFormData({ ...formData, value: parseFloat(e.target.value) || 0 })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
        )}

        {operatorType === 'cross' && 'crossWith' in formData && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cross With</label>
            <input
              type="text"
              value={formData.crossWith}
              onChange={(e) => setFormData({ ...formData, crossWith: e.target.value })}
              placeholder="e.g., MACD_Signal"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
        )}

        {operatorType === 'range' && 'minValue' in formData && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Min Value</label>
              <input
                type="number"
                value={formData.minValue}
                onChange={(e) =>
                  setFormData({ ...formData, minValue: parseFloat(e.target.value) || 0 })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Value</label>
              <input
                type="number"
                value={formData.maxValue}
                onChange={(e) =>
                  setFormData({ ...formData, maxValue: parseFloat(e.target.value) || 0 })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
            </div>
          </>
        )}

        {/* Logical Operator */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Logic</label>
          <div className="flex gap-2">
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
                  className="mr-2"
                />
                <span className="text-sm">{op}</span>
              </label>
            ))}
          </div>
        </div>

        {error && <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{error}</div>}

        <div className="flex gap-2 pt-2">
          <button
            onClick={() => onSave(formData)}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
          >
            Save
          </button>
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-50"
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
      <div className="text-center py-8 text-gray-500">
        <p className="text-sm">No conditions added yet</p>
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
      <div key={condition.id} className="mb-3">
        <div className="bg-white border-l-4 border-blue-500 p-3 rounded-r-lg shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <p className="text-sm font-mono text-gray-900">{conditionLabel}</p>
              <p className="text-xs text-gray-500 mt-1">Logic: {condition.logicalOp}</p>
            </div>
            <div className="flex gap-1 ml-2">
              <button
                onClick={() => onEdit(condition)}
                className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                title="Edit"
              >
                ✎
              </button>
              <button
                onClick={() => onDuplicate(condition)}
                className="p-1 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded"
                title="Duplicate"
              >
                <Copy size={16} />
              </button>
              <button
                onClick={() => onDelete(condition.id)}
                className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                title="Delete"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        </div>

        {children.length > 0 && (
          <div className="ml-6 mt-2 border-l-2 border-gray-300 pl-4">
            {children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  }

  return <div className="py-4">{renderNode(tree)}</div>;
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
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div
        className="p-4 border-b border-gray-200 bg-gray-50 cursor-pointer hover:bg-gray-100 flex items-center justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <h3 className="text-lg font-semibold text-gray-900 capitalize">{signalType} Conditions</h3>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600 bg-gray-200 px-2 py-1 rounded">
            {conditions.length} / {MAX_CONDITIONS_PER_SIGNAL}
          </span>
          {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </div>
      </div>

      {expanded && (
        <div className="p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-3">Add/Edit Condition</h4>
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
                  className={`w-full py-3 rounded-lg border-2 border-dashed flex items-center justify-center gap-2 transition-colors ${
                    conditions.length >= MAX_CONDITIONS_PER_SIGNAL
                      ? 'border-gray-200 text-gray-400 cursor-not-allowed'
                      : 'border-blue-300 text-blue-600 hover:bg-blue-50'
                  }`}
                >
                  <Plus size={20} />
                  Add Condition
                </button>
              )}
            </div>

            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-3">Logic Tree</h4>
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 max-h-96 overflow-y-auto">
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
