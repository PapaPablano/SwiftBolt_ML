/**
 * Pivot Levels Analysis Panel
 * ============================
 *
 * Displays multi-period pivot levels with:
 * - Period-aware colors (silver -> gold)
 * - Support/Resistance/Active status indicators
 * - Confluence zone detection
 * - Overall metrics (strength, confidence, pivot count)
 * - Real-time WebSocket status
 */

import React, { useMemo } from 'react';
import { PivotLevelData, PivotMetrics } from '../hooks/usePivotLevels';

interface PivotLevelsPanelProps {
  pivotLevels: PivotLevelData[];
  metrics: PivotMetrics | null;
  loading: boolean;
  error: string | null;
  isConnected?: boolean;
}

// Map status to display text and color
const STATUS_CONFIG = {
  support: { label: '🟢 Support', color: 'text-green-500' },
  resistance: { label: '🔴 Resistance', color: 'text-red-500' },
  active: { label: '🔵 Active', color: 'text-blue-500' },
  inactive: { label: '⚪ Inactive', color: 'text-gray-500' },
};

const getStatusConfig = (status?: string) => {
  return STATUS_CONFIG[status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.inactive;
};

// Format price with 4 decimal places
const formatPrice = (price?: number) => {
  if (!price) return 'N/A';
  return price.toFixed(4);
};

// Strength meter visualization
const StrengthMeter: React.FC<{ strength: number }> = ({ strength }) => {
  const percentage = strength * 100;
  const color = strength >= 0.7 ? 'bg-green-500' : strength >= 0.4 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="w-full">
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all duration-300`} style={{ width: `${percentage}%` }} />
      </div>
      <div className="mt-1 text-xs text-gray-400 text-right">{percentage.toFixed(1)}%</div>
    </div>
  );
};

// Find confluence zones (multiple levels close together)
const findConfluenceZones = (levels: PivotLevelData[], tolerance: number = 0.5) => {
  const zones: { price: number; levels: PivotLevelData[]; strength: number }[] = [];
  const processed = new Set<number>();

  for (let i = 0; i < levels.length; i++) {
    if (processed.has(i)) continue;

    const baseLevels = [levels[i]];
    const basePrice = (levels[i].level_high ?? levels[i].level_low) || 0;

    for (let j = i + 1; j < levels.length; j++) {
      if (processed.has(j)) continue;

      const comparePrice = (levels[j].level_high ?? levels[j].level_low) || 0;
      const percentDiff = Math.abs(comparePrice - basePrice) / basePrice;

      if (percentDiff < tolerance / 100) {
        baseLevels.push(levels[j]);
        processed.add(j);
      }
    }

    if (baseLevels.length > 1) {
      const avgPrice = baseLevels.reduce((sum, l) => sum + ((l.level_high ?? l.level_low) || 0), 0) / baseLevels.length;
      const strength = baseLevels.length / levels.length;

      zones.push({
        price: avgPrice,
        levels: baseLevels,
        strength,
      });
    }

    processed.add(i);
  }

  return zones.sort((a, b) => b.strength - a.strength);
};

export const PivotLevelsPanel: React.FC<PivotLevelsPanelProps> = ({
  pivotLevels,
  metrics,
  loading,
  error,
  isConnected,
}) => {
  // Find confluence zones
  const confluenceZones = useMemo(() => {
    return findConfluenceZones(pivotLevels, 0.5);
  }, [pivotLevels]);

  // Group levels by period
  const levelsByPeriod = useMemo(() => {
    const grouped: Record<number, PivotLevelData[]> = {};

    pivotLevels.forEach((level) => {
      if (!grouped[level.period]) {
        grouped[level.period] = [];
      }
      grouped[level.period].push(level);
    });

    return Object.entries(grouped).sort((a, b) => Number(b[0]) - Number(a[0]));
  }, [pivotLevels]);

  return (
    <div className="space-y-4">
      {/* Status indicator */}
      <div className="flex items-center gap-2 pb-4 border-b border-gray-700">
        <div className={`h-2.5 w-2.5 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'}`} />
        <span className="text-sm text-gray-400">
          {isConnected ? 'Live Updates' : 'Polling (30s)'}
        </span>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="text-center py-4">
          <div className="text-sm text-gray-400">Loading pivot levels...</div>
          <div className="mt-2 h-1 w-full bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 animate-pulse" style={{ width: '60%' }} />
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-900/30 p-3 text-sm text-red-200 border border-red-800">
          ⚠️ {error}
        </div>
      )}

      {/* Metrics summary */}
      {metrics && (
        <div className="space-y-3 pb-4 border-b border-gray-700">
          {/* Overall strength */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-300">Overall Strength</span>
              <span className="text-sm font-bold text-white">{(metrics.overall_strength * 100).toFixed(1)}%</span>
            </div>
            <StrengthMeter strength={metrics.overall_strength} />
          </div>

          {/* Metrics grid */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-800/50 rounded p-2">
              <div className="text-xs text-gray-400">Pivots</div>
              <div className="text-lg font-bold text-white">{metrics.pivot_count}</div>
            </div>
            <div className="bg-gray-800/50 rounded p-2">
              <div className="text-xs text-gray-400">Confidence</div>
              <div className="text-lg font-bold text-blue-400">{(metrics.confidence * 100).toFixed(0)}%</div>
            </div>
            <div className="bg-gray-800/50 rounded p-2">
              <div className="text-xs text-gray-400">High Pivots</div>
              <div className="text-lg font-bold text-green-400">{metrics.high_pivot_count}</div>
            </div>
            <div className="bg-gray-800/50 rounded p-2">
              <div className="text-xs text-gray-400">Low Pivots</div>
              <div className="text-lg font-bold text-red-400">{metrics.low_pivot_count}</div>
            </div>
          </div>
        </div>
      )}

      {/* Confluence zones (if any) */}
      {confluenceZones.length > 0 && (
        <div className="pb-4 border-b border-gray-700">
          <h3 className="text-sm font-semibold text-yellow-400 mb-2">🎯 Confluence Zones</h3>
          <div className="space-y-2">
            {confluenceZones.map((zone, idx) => (
              <div key={idx} className="bg-yellow-900/20 rounded p-2 border border-yellow-800/50">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-yellow-200">${zone.price.toFixed(4)}</span>
                  <span className="text-xs text-yellow-300">⭐ {zone.levels.length} levels</span>
                </div>
                <div className="text-xs text-yellow-400 mt-1">
                  Periods: {zone.levels.map((l) => l.period).join(', ')}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Period-wise pivot levels */}
      {levelsByPeriod.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-300 mb-3">Multi-Period Levels</h3>
          <div className="space-y-3">
            {levelsByPeriod.map(([period, levels]) => (
              <div
                key={period}
                className="rounded-lg bg-gray-800/50 p-3 border border-gray-700"
                style={{ borderLeftColor: levels[0]?.color || '#808080', borderLeftWidth: '3px' }}
              >
                {/* Period header */}
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-white">
                    P{period} <span className="text-xs text-gray-400 ml-1">{levels[0]?.label || `Period ${period}`}</span>
                  </span>
                </div>

                {/* Levels for this period */}
                <div className="space-y-1.5">
                  {levels.map((level, idx) => (
                    <div key={idx} className="text-xs">
                      {level.level_high !== undefined && (
                        <div className="flex items-center justify-between py-1">
                          <div className="flex items-center gap-2">
                            <span className={`${getStatusConfig(level.high_status).color} font-medium`}>
                              {getStatusConfig(level.high_status).label}
                            </span>
                            <span className="text-gray-500">High</span>
                          </div>
                          <span className="font-mono text-gray-300">${formatPrice(level.level_high)}</span>
                        </div>
                      )}

                      {level.level_low !== undefined && (
                        <div className="flex items-center justify-between py-1">
                          <div className="flex items-center gap-2">
                            <span className={`${getStatusConfig(level.low_status).color} font-medium`}>
                              {getStatusConfig(level.low_status).label}
                            </span>
                            <span className="text-gray-500">Low</span>
                          </div>
                          <span className="font-mono text-gray-300">${formatPrice(level.level_low)}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Period effectiveness (if available) */}
      {metrics?.period_effectiveness && metrics.period_effectiveness.length > 0 && (
        <div className="pt-4 border-t border-gray-700">
          <h3 className="text-sm font-semibold text-gray-300 mb-2">Period Effectiveness</h3>
          <div className="space-y-1">
            {metrics.period_effectiveness.slice(0, 3).map((pe) => (
              <div key={pe.period} className="flex items-center justify-between text-xs">
                <span className="text-gray-400">P{pe.period}</span>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500"
                      style={{ width: `${Math.min(pe.effectiveness * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-gray-400 w-10 text-right">{(pe.effectiveness * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && pivotLevels.length === 0 && !error && (
        <div className="text-center py-6 text-gray-400">
          <div className="text-sm">No pivot levels detected</div>
          <div className="text-xs text-gray-500 mt-1">Try a different symbol or timeframe</div>
        </div>
      )}
    </div>
  );
};
