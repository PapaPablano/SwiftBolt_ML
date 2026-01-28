/**
 * Technical Indicators Analysis Panel
 * ===================================
 *
 * Displays:
 * - Polynomial Support/Resistance with slopes
 * - Pivot Levels
 * - Multi-timeframe analysis
 * - S/R bias indication
 * - Forecast data
 *
 * Styled to match TradingView aesthetic
 */

import React, { useState } from 'react';
import { SupportResistanceData, PolynomialSRData } from '../hooks/useIndicators';

interface IndicatorPanelProps {
  data: SupportResistanceData | null;
  loading: boolean;
  error: string | null;
}

const TrendBadge: React.FC<{ trend: string; slope: number }> = ({ trend, slope }) => {
  const colors = {
    rising: 'bg-green-900/30 text-green-400 border-green-700/50',
    falling: 'bg-red-900/30 text-red-400 border-red-700/50',
    flat: 'bg-gray-800 text-gray-400 border-gray-700/50',
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium border ${colors[trend as keyof typeof colors] || colors.flat}`}>
      {trend} ({slope > 0 ? '+' : ''}{slope.toFixed(4)})
    </span>
  );
};

const PolynomialSRDisplay: React.FC<{
  label: string;
  data: PolynomialSRData;
  isPrimary: boolean;
}> = ({ label, data, isPrimary }) => {
  if (!data) return null;

  const bgColor = isPrimary
    ? label.includes('Support')
      ? 'bg-blue-900/20'
      : 'bg-red-900/20'
    : 'bg-gray-800/30';

  return (
    <div className={`${bgColor} rounded-lg p-3 border border-gray-700/50`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-400 uppercase">{label}</span>
        <TrendBadge trend={data.trend} slope={data.slope} />
      </div>

      <div className="space-y-1">
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-500">Price Level</span>
          <span className="font-mono text-sm font-medium text-white">
            ${data.level.toFixed(2)}
          </span>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-500">Slope (Price/Bar)</span>
          <span
            className={`font-mono text-xs ${
              data.slope > 0 ? 'text-green-400' : data.slope < 0 ? 'text-red-400' : 'text-gray-400'
            }`}
          >
            {data.slope > 0 ? '+' : ''}{data.slope.toFixed(6)}
          </span>
        </div>

        {data.forecast && data.forecast.length > 0 && (
          <div className="flex justify-between items-center pt-2 border-t border-gray-700/30">
            <span className="text-xs text-gray-500">Next 5 Bars Forecast</span>
            <span className="font-mono text-xs text-gray-300">
              {data.forecast.slice(0, 5).map((v, i) => (
                <span key={i} className="ml-1">
                  ${v.toFixed(2)}
                </span>
              ))}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export const IndicatorPanel: React.FC<IndicatorPanelProps> = ({ data, loading, error }) => {
  const [expandedSection, setExpandedSection] = useState<string>('polynomial');

  if (loading) {
    return (
      <div className="rounded-lg bg-gray-900 p-4 border border-gray-800">
        <div className="text-center py-4">
          <div className="inline-block animate-spin">
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full" />
          </div>
          <p className="mt-2 text-sm text-gray-400">Loading indicators...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-gray-900 p-4 border border-red-900/50">
        <p className="text-sm text-red-400">⚠️ Error loading indicators</p>
        <p className="text-xs text-gray-400 mt-1">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-lg bg-gray-900 p-4 border border-gray-800">
        <p className="text-sm text-gray-400">No data available</p>
      </div>
    );
  }

  const supportColor =
    (data.support_distance_pct || 0) < (data.resistance_distance_pct || 100) ? 'text-blue-400' : 'text-gray-400';
  const resistanceColor =
    (data.resistance_distance_pct || 0) < (data.support_distance_pct || 100) ? 'text-red-400' : 'text-gray-400';

  return (
    <div className="space-y-3">
      {/* Polynomial Support & Resistance */}
      <div className="rounded-lg bg-gray-900 border border-gray-800 overflow-hidden">
        <button
          onClick={() => setExpandedSection(expandedSection === 'polynomial' ? '' : 'polynomial')}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800/50 transition-colors"
        >
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <span className="text-blue-400">📈</span> Polynomial Regression S/R
          </h3>
          <span className={`text-gray-400 transition-transform ${expandedSection === 'polynomial' ? 'rotate-180' : ''}`}>
            ▼
          </span>
        </button>

        {expandedSection === 'polynomial' && (
          <div className="px-4 py-3 space-y-3 border-t border-gray-800 bg-gray-800/30">
            {data.polynomial_support && (
              <PolynomialSRDisplay label="Support (Polynomial)" data={data.polynomial_support} isPrimary={true} />
            )}

            {data.polynomial_resistance && (
              <PolynomialSRDisplay
                label="Resistance (Polynomial)"
                data={data.polynomial_resistance}
                isPrimary={true}
              />
            )}

            {!data.polynomial_support && !data.polynomial_resistance && (
              <p className="text-xs text-gray-500 py-2">Insufficient data for polynomial regression</p>
            )}
          </div>
        )}
      </div>

      {/* Support & Resistance Summary */}
      <div className="rounded-lg bg-gray-900 border border-gray-800 overflow-hidden">
        <button
          onClick={() => setExpandedSection(expandedSection === 'summary' ? '' : 'summary')}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800/50 transition-colors"
        >
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <span className="text-purple-400">🎯</span> Support & Resistance
          </h3>
          <span className={`text-gray-400 transition-transform ${expandedSection === 'summary' ? 'rotate-180' : ''}`}>
            ▼
          </span>
        </button>

        {expandedSection === 'summary' && (
          <div className="px-4 py-3 space-y-3 border-t border-gray-800 bg-gray-800/30">
            <div className="grid grid-cols-3 gap-2">
              {/* Current Price */}
              <div className="rounded-lg bg-gray-700/30 p-2 border border-gray-700/50">
                <div className="text-xs font-semibold text-gray-400 uppercase mb-1">Price</div>
                <div className="font-mono text-sm font-bold text-white">${data.current_price.toFixed(2)}</div>
              </div>

              {/* Nearest Support */}
              <div className={`rounded-lg bg-blue-900/20 p-2 border border-blue-700/30`}>
                <div className="text-xs font-semibold text-blue-400 uppercase mb-1">Support</div>
                <div className="font-mono text-sm font-bold text-blue-300">
                  {data.nearest_support ? `$${data.nearest_support.toFixed(2)}` : 'N/A'}
                </div>
                {data.support_distance_pct !== undefined && (
                  <div className="text-xs text-blue-400 mt-0.5">{data.support_distance_pct.toFixed(1)}% below</div>
                )}
              </div>

              {/* Nearest Resistance */}
              <div className={`rounded-lg bg-red-900/20 p-2 border border-red-700/30`}>
                <div className="text-xs font-semibold text-red-400 uppercase mb-1">Resistance</div>
                <div className="font-mono text-sm font-bold text-red-300">
                  {data.nearest_resistance ? `$${data.nearest_resistance.toFixed(2)}` : 'N/A'}
                </div>
                {data.resistance_distance_pct !== undefined && (
                  <div className="text-xs text-red-400 mt-0.5">{data.resistance_distance_pct.toFixed(1)}% above</div>
                )}
              </div>
            </div>

            {/* Bias Indicator */}
            {data.bias && (
              <div
                className={`rounded-lg p-2 border text-center ${
                  data.bias === 'bullish'
                    ? 'bg-green-900/20 border-green-700/30'
                    : data.bias === 'bearish'
                      ? 'bg-red-900/20 border-red-700/30'
                      : 'bg-gray-800/30 border-gray-700/30'
                }`}
              >
                <div className={`text-xs font-semibold uppercase ${
                  data.bias === 'bullish'
                    ? 'text-green-400'
                    : data.bias === 'bearish'
                      ? 'text-red-400'
                      : 'text-gray-400'
                }`}>
                  S/R Bias: {data.bias}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Pivot Levels */}
      {data.pivot_levels && data.pivot_levels.length > 0 && (
        <div className="rounded-lg bg-gray-900 border border-gray-800 overflow-hidden">
          <button
            onClick={() => setExpandedSection(expandedSection === 'pivots' ? '' : 'pivots')}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800/50 transition-colors"
          >
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="text-amber-400">⭐</span> Pivot Levels ({data.pivot_levels.length})
            </h3>
            <span className={`text-gray-400 transition-transform ${expandedSection === 'pivots' ? 'rotate-180' : ''}`}>
              ▼
            </span>
          </button>

          {expandedSection === 'pivots' && (
            <div className="px-4 py-3 space-y-2 border-t border-gray-800 bg-gray-800/30 max-h-48 overflow-y-auto">
              {data.pivot_levels.map((pivot, idx) => (
                <div key={idx} className="flex items-center justify-between text-xs bg-gray-700/20 rounded p-2">
                  <span className="text-gray-400">Period {pivot.period}</span>
                  <div className="font-mono space-x-3">
                    {pivot.level_low && (
                      <span className="text-blue-400">
                        Low: <span className="font-semibold">${pivot.level_low.toFixed(2)}</span>
                      </span>
                    )}
                    {pivot.level_high && (
                      <span className="text-red-400">
                        High: <span className="font-semibold">${pivot.level_high.toFixed(2)}</span>
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Last Updated */}
      {data.last_updated && (
        <div className="text-xs text-gray-500 text-center py-2">
          Last updated: {new Date(data.last_updated).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
};
