import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronUp, AlertCircle, Lightbulb, Plus } from 'lucide-react';

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

interface IndicatorInfo {
  name: string;
  symbol?: string; // Short code like 'RSI14', 'MACD(12,26,9)'
  description: string;
  bullishSignal: string;
  bearishSignal: string;
  defaultParams?: Record<string, number>;
  range?: { min: number; max: number }; // e.g., RSI is 0-100
  timescaleRequired?: 'minute' | 'hour' | 'day' | 'any';
  category: 'trend' | 'momentum' | 'volatility' | 'volume' | 'pattern';
}

interface IndicatorCategory {
  name: string;
  description: string;
  emoji: string;
  correlations?: string[]; // Other indicators in same category to watch for redundancy
}

// ============================================================================
// INDICATOR LIBRARY - 38 Total Indicators
// ============================================================================

const INDICATOR_LIBRARY: IndicatorInfo[] = [
  // =========================================================================
  // TREND (10 indicators)
  // =========================================================================
  {
    name: 'SuperTrend',
    symbol: 'ST',
    description: 'Trend reversal indicator combining ATR and moving averages',
    bullishSignal: 'Price crosses above SuperTrend line',
    bearishSignal: 'Price crosses below SuperTrend line',
    defaultParams: { period: 10, multiplier: 3 },
    category: 'trend',
    timescaleRequired: 'any',
  },
  {
    name: 'ADX (Average Directional Index)',
    symbol: 'ADX',
    description: 'Measures trend strength (not direction)',
    bullishSignal: 'ADX > 25 with +DI > -DI',
    bearishSignal: 'ADX > 25 with -DI > +DI',
    defaultParams: { period: 14 },
    range: { min: 0, max: 100 },
    category: 'trend',
  },
  {
    name: 'Moving Average (SMA)',
    symbol: 'SMA',
    description: 'Simple average of price over period',
    bullishSignal: 'Price > SMA',
    bearishSignal: 'Price < SMA',
    defaultParams: { fast: 50, slow: 200 },
    category: 'trend',
  },
  {
    name: 'Exponential Moving Average',
    symbol: 'EMA',
    description: 'Weighted moving average (more recent data weighted higher)',
    bullishSignal: 'Fast EMA > Slow EMA',
    bearishSignal: 'Fast EMA < Slow EMA',
    defaultParams: { fast: 12, slow: 26 },
    category: 'trend',
  },
  {
    name: 'TEMA (Triple Exponential MA)',
    symbol: 'TEMA',
    description: 'Triple smoothed moving average for reduced lag',
    bullishSignal: 'Price > TEMA',
    bearishSignal: 'Price < TEMA',
    defaultParams: { period: 10 },
    category: 'trend',
  },
  {
    name: 'Ichimoku Cloud',
    symbol: 'ICH',
    description: 'Multi-line trend and support/resistance system',
    bullishSignal: 'Price above cloud, Tenkan > Kijun',
    bearishSignal: 'Price below cloud, Tenkan < Kijun',
    defaultParams: { tenkan: 9, kijun: 26, senkou: 52 },
    category: 'trend',
  },
  {
    name: 'Linear Regression',
    symbol: 'LR',
    description: 'Fits trend line through price data',
    bullishSignal: 'Linear regression slope > 0',
    bearishSignal: 'Linear regression slope < 0',
    defaultParams: { period: 20 },
    category: 'trend',
  },
  {
    name: 'Parabolic SAR',
    symbol: 'SAR',
    description: 'Stop and reverse indicator for trend changes',
    bullishSignal: 'SAR flips from below to above price',
    bearishSignal: 'SAR flips from above to below price',
    defaultParams: { acceleration: 0.02, maximum: 0.2 },
    category: 'trend',
  },
  {
    name: 'Vortex Indicator',
    symbol: 'VI',
    description: 'Measures directional movement magnitude',
    bullishSignal: 'Positive VI > Negative VI',
    bearishSignal: 'Negative VI > Positive VI',
    defaultParams: { period: 14 },
    category: 'trend',
  },
  {
    name: 'Donchian Channel',
    symbol: 'DC',
    description: 'Highest high and lowest low over period',
    bullishSignal: 'Price at upper band (breakout)',
    bearishSignal: 'Price at lower band (breakdown)',
    defaultParams: { period: 20 },
    category: 'trend',
  },

  // =========================================================================
  // MOMENTUM (10 indicators)
  // =========================================================================
  {
    name: 'RSI (Relative Strength Index)',
    symbol: 'RSI',
    description: 'Momentum oscillator measuring speed and magnitude of change',
    bullishSignal: 'RSI > 50, ideally > 70 for strong bullish',
    bearishSignal: 'RSI < 50, ideally < 30 for strong bearish',
    defaultParams: { period: 14 },
    range: { min: 0, max: 100 },
    category: 'momentum',
  },
  {
    name: 'MACD',
    symbol: 'MACD',
    description: 'Moving Average Convergence Divergence',
    bullishSignal: 'MACD crosses above signal line',
    bearishSignal: 'MACD crosses below signal line',
    defaultParams: { fast: 12, slow: 26, signal: 9 },
    category: 'momentum',
  },
  {
    name: 'Stochastic Oscillator',
    symbol: 'STOCH',
    description: 'Compares closing price to price range',
    bullishSignal: '%K > 20 (oversold recovery), %K > %D',
    bearishSignal: '%K < 80 (overbought reversal), %K < %D',
    defaultParams: { k: 14, d: 3 },
    range: { min: 0, max: 100 },
    category: 'momentum',
  },
  {
    name: 'CCI (Commodity Channel Index)',
    symbol: 'CCI',
    description: 'Cyclical price movements above/below moving average',
    bullishSignal: 'CCI > 0 and rising above 100',
    bearishSignal: 'CCI < 0 and falling below -100',
    defaultParams: { period: 20 },
    range: { min: -200, max: 200 },
    category: 'momentum',
  },
  {
    name: 'Williams %R',
    symbol: 'WILL%R',
    description: 'Momentum indicator similar to Stochastic',
    bullishSignal: '%R < -80 (oversold)',
    bearishSignal: '%R > -20 (overbought)',
    defaultParams: { period: 14 },
    range: { min: -100, max: 0 },
    category: 'momentum',
  },
  {
    name: 'Rate of Change (ROC)',
    symbol: 'ROC',
    description: 'Price change as percentage over period',
    bullishSignal: 'ROC > 0 and increasing',
    bearishSignal: 'ROC < 0 and decreasing',
    defaultParams: { period: 12 },
    category: 'momentum',
  },
  {
    name: 'Momentum Indicator',
    symbol: 'MOM',
    description: 'Difference between current price and price N periods ago',
    bullishSignal: 'Momentum > 0 and rising',
    bearishSignal: 'Momentum < 0 and falling',
    defaultParams: { period: 10 },
    category: 'momentum',
  },
  {
    name: 'Awesome Oscillator',
    symbol: 'AO',
    description: 'Simple Moving Average histogram',
    bullishSignal: 'Histogram turning positive (bullish cross)',
    bearishSignal: 'Histogram turning negative (bearish cross)',
    defaultParams: { fast: 5, slow: 34 },
    category: 'momentum',
  },
  {
    name: 'Stochastic RSI',
    symbol: 'StochRSI',
    description: 'RSI of RSI - smoothed momentum indicator',
    bullishSignal: 'StochRSI < 0.2 and rising (oversold recovery)',
    bearishSignal: 'StochRSI > 0.8 and falling (overbought reversal)',
    defaultParams: { rsiPeriod: 14, stochPeriod: 14 },
    range: { min: 0, max: 1 },
    category: 'momentum',
  },
  {
    name: 'KDJ Indicator',
    symbol: 'KDJ',
    description: 'Korean version of Stochastic with J line',
    bullishSignal: 'K > D, J < 20',
    bearishSignal: 'K < D, J > 80',
    defaultParams: { period: 9 },
    category: 'momentum',
  },

  // =========================================================================
  // VOLATILITY (8 indicators)
  // =========================================================================
  {
    name: 'Bollinger Bands',
    symbol: 'BB',
    description: 'Upper/lower bands based on standard deviation',
    bullishSignal: 'Price near lower band (mean reversion)',
    bearishSignal: 'Price near upper band (mean reversion)',
    defaultParams: { period: 20, stdDev: 2 },
    category: 'volatility',
  },
  {
    name: 'ATR (Average True Range)',
    symbol: 'ATR',
    description: 'Average volatility measure',
    bullishSignal: 'ATR rising = increased volatility',
    bearishSignal: 'ATR falling = decreased volatility',
    defaultParams: { period: 14 },
    category: 'volatility',
  },
  {
    name: 'Keltner Channels',
    symbol: 'KC',
    description: 'Channels based on EMA and ATR',
    bullishSignal: 'Price above EMA, near upper channel',
    bearishSignal: 'Price below EMA, near lower channel',
    defaultParams: { ema: 20, atrMultiplier: 2 },
    category: 'volatility',
  },
  {
    name: 'Historical Volatility',
    symbol: 'HV',
    description: 'Standard deviation of price changes',
    bullishSignal: 'HV > 20th percentile (normal)',
    bearishSignal: 'HV < 20th percentile (quiet)',
    defaultParams: { period: 20 },
    category: 'volatility',
  },
  {
    name: 'Normalized ATR',
    symbol: 'ATR%',
    description: 'ATR as percentage of price',
    bullishSignal: 'ATR% > 2% (high volatility)',
    bearishSignal: 'ATR% < 1% (low volatility)',
    defaultParams: { period: 14 },
    category: 'volatility',
  },
  {
    name: 'VIX (Volatility Index)',
    symbol: 'VIX',
    description: 'Market fear gauge (30-min implied volatility)',
    bullishSignal: 'VIX < 20 (complacency/buying opportunity)',
    bearishSignal: 'VIX > 30 (fear/selling opportunity)',
    defaultParams: {},
    category: 'volatility',
  },
  {
    name: 'Standard Deviation',
    symbol: 'STDEV',
    description: 'Price dispersion around MA',
    bullishSignal: 'STDEV rising = expansion',
    bearishSignal: 'STDEV low = contraction',
    defaultParams: { period: 20 },
    category: 'volatility',
  },
  {
    name: 'Nadaraya-Watson Envelope',
    symbol: 'NWE',
    description: 'Adaptive moving average channels',
    bullishSignal: 'Price near lower envelope',
    bearishSignal: 'Price near upper envelope',
    defaultParams: { period: 30 },
    category: 'volatility',
  },

  // =========================================================================
  // VOLUME (6 indicators)
  // =========================================================================
  {
    name: 'Volume (Raw)',
    symbol: 'VOL',
    description: 'Number of shares traded per bar',
    bullishSignal: 'Volume > average volume',
    bearishSignal: 'Volume < average volume',
    defaultParams: {},
    category: 'volume',
  },
  {
    name: 'On-Balance Volume (OBV)',
    symbol: 'OBV',
    description: 'Cumulative volume based on price change direction',
    bullishSignal: 'OBV rising (buyers accumulating)',
    bearishSignal: 'OBV falling (sellers distributing)',
    defaultParams: {},
    category: 'volume',
  },
  {
    name: 'Volume Rate of Change',
    symbol: 'VROC',
    description: 'Percentage change in volume',
    bullishSignal: 'VROC > 0 and rising',
    bearishSignal: 'VROC < 0 and falling',
    defaultParams: { period: 14 },
    category: 'volume',
  },
  {
    name: 'Money Flow Index (MFI)',
    symbol: 'MFI',
    description: 'Volume-weighted RSI',
    bullishSignal: 'MFI > 50 and rising',
    bearishSignal: 'MFI < 50 and falling',
    defaultParams: { period: 14 },
    range: { min: 0, max: 100 },
    category: 'volume',
  },
  {
    name: 'Volume-Weighted Average Price',
    symbol: 'VWAP',
    description: 'Average price weighted by volume',
    bullishSignal: 'Price > VWAP',
    bearishSignal: 'Price < VWAP',
    defaultParams: {},
    category: 'volume',
  },
  {
    name: 'Accumulation/Distribution',
    symbol: 'A/D',
    description: 'Volume-weighted accumulation line',
    bullishSignal: 'A/D rising (accumulation)',
    bearishSignal: 'A/D falling (distribution)',
    defaultParams: {},
    category: 'volume',
  },

  // =========================================================================
  // PATTERN (4 indicators)
  // =========================================================================
  {
    name: 'Support & Resistance Levels',
    symbol: 'S&R',
    description: 'Previous highs and lows',
    bullishSignal: 'Price breaks above resistance',
    bearishSignal: 'Price breaks below support',
    defaultParams: { lookback: 50 },
    category: 'pattern',
  },
  {
    name: 'Market Regime',
    symbol: 'REGIME',
    description: 'Uptrend/downtrend/ranging market condition',
    bullishSignal: 'Uptrend regime (series of higher highs/lows)',
    bearishSignal: 'Downtrend regime (series of lower highs/lows)',
    defaultParams: { period: 20 },
    category: 'pattern',
  },
  {
    name: 'Pivot Points',
    symbol: 'PP',
    description: 'Support/resistance based on previous OHLC',
    bullishSignal: 'Price at S1/S2 (support test)',
    bearishSignal: 'Price at R1/R2 (resistance test)',
    defaultParams: {},
    category: 'pattern',
  },
  {
    name: 'Fibonacci Retracement',
    symbol: 'FIB',
    description: 'Price levels at 23.6%, 38.2%, 50%, 61.8%',
    bullishSignal: 'Price bounces at Fib level',
    bearishSignal: 'Price breaks through Fib level',
    defaultParams: {},
    category: 'pattern',
  },
];

const CATEGORY_INFO: Record<string, IndicatorCategory> = {
  trend: {
    name: 'Trend Indicators',
    description: 'Identify direction and strength of trends',
    emoji: '📈',
    correlations: ['ADX', 'SuperTrend', 'Moving Average', 'Ichimoku Cloud'],
  },
  momentum: {
    name: 'Momentum Indicators',
    description: 'Measure speed and magnitude of price change',
    emoji: '⚡',
    correlations: ['RSI', 'MACD', 'Stochastic', 'CCI'],
  },
  volatility: {
    name: 'Volatility Indicators',
    description: 'Measure price dispersion and risk',
    emoji: '📊',
    correlations: ['Bollinger Bands', 'ATR', 'Keltner Channels'],
  },
  volume: {
    name: 'Volume Indicators',
    description: 'Confirm price trends with volume analysis',
    emoji: '📦',
    correlations: ['OBV', 'MFI', 'Volume'],
  },
  pattern: {
    name: 'Pattern/Structural Indicators',
    description: 'Support, resistance, and market regimes',
    emoji: '🎯',
    correlations: ['Support & Resistance', 'Pivot Points'],
  },
};

// ============================================================================
// COMPONENTS
// ============================================================================

interface IndicatorMenuProps {
  onIndicatorSelect?: (indicator: IndicatorInfo) => void;
  selectedIndicators?: string[];
}

interface CategorySectionProps {
  category: string;
  indicators: IndicatorInfo[];
  isExpanded: boolean;
  onToggle: () => void;
  onSelect: (indicator: IndicatorInfo) => void;
  selectedIndicators: string[];
  correlationWarnings: Set<string>;
}

function CategorySection({
  category,
  indicators,
  isExpanded,
  onToggle,
  onSelect,
  selectedIndicators,
  correlationWarnings,
}: CategorySectionProps) {
  const catInfo = CATEGORY_INFO[category];

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden mb-4">
      {/* Header */}
      <div
        onClick={onToggle}
        className="p-4 bg-gradient-to-r from-blue-50 to-blue-100 cursor-pointer hover:from-blue-100 hover:to-blue-200 flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">{catInfo.emoji}</span>
          <div>
            <h3 className="font-semibold text-gray-900">{catInfo.name}</h3>
            <p className="text-sm text-gray-600">{catInfo.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-600 bg-white px-2 py-1 rounded">
            {indicators.length}
          </span>
          {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </div>
      </div>

      {/* Indicators List */}
      {isExpanded && (
        <div className="p-4 bg-white">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {indicators.map((indicator) => {
              const isSelected = selectedIndicators.includes(indicator.name);
              const hasCorrelation = correlationWarnings.has(indicator.name);

              return (
                <div
                  key={indicator.name}
                  className={`p-3 rounded-lg border-2 cursor-pointer transition-all ${
                    isSelected
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50'
                  } ${hasCorrelation ? 'ring-2 ring-yellow-300' : ''}`}
                  onClick={() => onSelect(indicator)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-900">{indicator.name}</h4>
                      {indicator.symbol && (
                        <p className="text-xs text-gray-500">{indicator.symbol}</p>
                      )}
                      <p className="text-sm text-gray-600 mt-1">{indicator.description}</p>

                      {/* Signal Info */}
                      <div className="mt-2 text-xs space-y-1">
                        <p className="text-green-700">
                          <strong>↑ Bullish:</strong> {indicator.bullishSignal}
                        </p>
                        <p className="text-red-700">
                          <strong>↓ Bearish:</strong> {indicator.bearishSignal}
                        </p>
                      </div>

                      {/* Range Info */}
                      {indicator.range && (
                        <p className="text-xs text-gray-500 mt-1">
                          Range: {indicator.range.min} - {indicator.range.max}
                        </p>
                      )}
                    </div>

                    {/* Select Button */}
                    {isSelected && (
                      <div className="ml-2 text-blue-600">
                        <Plus size={20} fill="currentColor" />
                      </div>
                    )}
                  </div>

                  {/* Correlation Warning */}
                  {hasCorrelation && (
                    <div className="mt-2 p-2 bg-yellow-50 rounded flex items-start gap-2">
                      <AlertCircle size={14} className="text-yellow-600 mt-0.5 flex-shrink-0" />
                      <span className="text-xs text-yellow-700">
                        Correlated with other selected indicators
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const IndicatorMenu: React.FC<IndicatorMenuProps> = ({
  onIndicatorSelect,
  selectedIndicators = [],
}) => {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(['trend', 'momentum'])
  );
  const [searchTerm, setSearchTerm] = useState('');

  // Calculate correlation warnings
  const correlationWarnings = useMemo(() => {
    const warnings = new Set<string>();

    selectedIndicators.forEach((selectedName) => {
      const indicator = INDICATOR_LIBRARY.find((i) => i.name === selectedName);
      if (!indicator) return;

      const categoryInfo = CATEGORY_INFO[indicator.category];
      if (categoryInfo?.correlations) {
        categoryInfo.correlations.forEach((correlated) => {
          if (selectedIndicators.includes(correlated) && correlated !== selectedName) {
            warnings.add(selectedName);
          }
        });
      }
    });

    return warnings;
  }, [selectedIndicators]);

  // Filter and group indicators
  const filteredIndicators = useMemo(() => {
    const filtered = INDICATOR_LIBRARY.filter((ind) =>
      ind.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ind.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (ind.symbol && ind.symbol.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    const grouped: Record<string, IndicatorInfo[]> = {};
    filtered.forEach((ind) => {
      if (!grouped[ind.category]) {
        grouped[ind.category] = [];
      }
      grouped[ind.category].push(ind);
    });

    return grouped;
  }, [searchTerm]);

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(category)) {
      newExpanded.delete(category);
    } else {
      newExpanded.add(category);
    }
    setExpandedCategories(newExpanded);
  };

  const handleIndicatorSelect = (indicator: IndicatorInfo) => {
    onIndicatorSelect?.(indicator);
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-4">
          <Lightbulb className="text-yellow-500" size={24} />
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Technical Indicators Library</h2>
            <p className="text-gray-600">
              {INDICATOR_LIBRARY.length} indicators across 5 categories
            </p>
          </div>
        </div>

        {/* Search Bar */}
        <input
          type="text"
          placeholder="Search indicators... (name, description, or symbol)"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Selected Indicators Summary */}
      {selectedIndicators.length > 0 && (
        <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <p className="text-sm font-medium text-gray-900 mb-2">
            Selected Indicators ({selectedIndicators.length}):
          </p>
          <div className="flex flex-wrap gap-2">
            {selectedIndicators.map((name) => (
              <span
                key={name}
                className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium"
              >
                {name}
              </span>
            ))}
          </div>

          {/* Correlation Warnings */}
          {correlationWarnings.size > 0 && (
            <div className="mt-3 p-2 bg-yellow-50 rounded flex items-start gap-2">
              <AlertCircle size={16} className="text-yellow-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-yellow-700">
                <p className="font-medium">⚠ Correlation Warning</p>
                <p>
                  Some selected indicators are highly correlated. Consider using only one from each
                  group to avoid redundant signals.
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Indicator Categories */}
      <div className="space-y-4">
        {Object.entries(filteredIndicators).map(([category, indicators]) => (
          <CategorySection
            key={category}
            category={category}
            indicators={indicators}
            isExpanded={expandedCategories.has(category)}
            onToggle={() => toggleCategory(category)}
            onSelect={handleIndicatorSelect}
            selectedIndicators={selectedIndicators}
            correlationWarnings={correlationWarnings}
          />
        ))}

        {/* No Results */}
        {Object.keys(filteredIndicators).length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">No indicators found matching "{searchTerm}"</p>
            <p className="text-gray-400 text-sm mt-1">Try searching with different keywords</p>
          </div>
        )}
      </div>

      {/* Footer Tips */}
      <div className="mt-8 p-4 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-sm font-medium text-gray-900 mb-2">💡 Tips for indicator selection:</p>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>✓ Mix indicators from different categories for better signal confirmation</li>
          <li>✓ Use 2-3 indicators maximum to avoid over-optimization</li>
          <li>✓ Yellow ring = correlated with other selected indicators</li>
          <li>✓ Check the bullish/bearish signal ranges for your timeframe</li>
        </ul>
      </div>
    </div>
  );
};

export default IndicatorMenu;
