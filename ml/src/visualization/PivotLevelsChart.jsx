/**
 * React component for interactive pivot levels chart visualization
 *
 * Optimized for:
 * - Real-time data updates via WebSocket
 * - Large datasets (1000+ bars)
 * - Responsive design (mobile, tablet, desktop)
 * - Low memory footprint
 * - Fast re-renders
 */

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { LineChart } from 'recharts';

/**
 * Period configuration with colors and styling
 */
const PERIOD_CONFIG = {
  3: { color: '#A9A9A9', label: 'Ultra Micro', opacity: 0.5 },
  5: { color: '#C0C0C0', label: 'Micro', opacity: 0.6 },
  10: { color: '#4D94FF', label: 'Short-Short', opacity: 0.65 },
  13: { color: '#5CA7FF', label: 'Short-13', opacity: 0.65 },
  25: { color: '#3399FF', label: 'Short', opacity: 0.7 },
  50: { color: '#00CCCC', label: 'Medium', opacity: 0.75 },
  100: { color: '#FFD700', label: 'Long', opacity: 0.8 },
  200: { color: '#FF8C00', label: 'Very Long', opacity: 0.85 },
};

/**
 * Main Pivot Levels Chart Component
 */
const PivotLevelsChart = ({
  data = [],
  pivotLevels = [],
  width = '100%',
  height = 600,
  title = 'Pivot Levels Chart',
  showVolume = true,
  showAnalytics = true,
  theme = 'dark',
  onBarClick = null,
}) => {
  const [selectedPeriods, setSelectedPeriods] = useState(
    Object.keys(PERIOD_CONFIG).map(Number)
  );
  const [hoveredBar, setHoveredBar] = useState(null);
  const chartRef = useRef(null);

  // Filter pivot levels by selected periods
  const filteredPivotLevels = useMemo(() => {
    return pivotLevels.filter((level) => selectedPeriods.includes(level.period));
  }, [pivotLevels, selectedPeriods]);

  // Memoize chart data to prevent unnecessary re-renders
  const chartData = useMemo(() => {
    return data.map((bar, index) => ({
      ...bar,
      timestamp: bar.timestamp || index,
      index,
    }));
  }, [data]);

  // Toggle period visibility
  const togglePeriod = useCallback((period) => {
    setSelectedPeriods((prev) =>
      prev.includes(period) ? prev.filter((p) => p !== period) : [...prev, period]
    );
  }, []);

  // Render reference lines for each pivot level
  const renderPivotLines = useMemo(() => {
    return filteredPivotLevels.map((level, idx) => {
      const config = PERIOD_CONFIG[level.period] || {};
      return (
        <React.Fragment key={`pivot-${level.period}-${idx}`}>
          {level.levelHigh && (
            <ReferenceLine
              y={level.levelHigh}
              stroke={config.color}
              strokeDasharray="5 5"
              opacity={config.opacity}
              label={{
                value: `P${level.period}H`,
                position: 'insideTopLeft',
                offset: -5,
                fill: config.color,
                fontSize: 10,
              }}
            />
          )}
          {level.levelLow && (
            <ReferenceLine
              y={level.levelLow}
              stroke={config.color}
              strokeDasharray="5 5"
              opacity={config.opacity}
              label={{
                value: `P${level.period}L`,
                position: 'insideBottomLeft',
                offset: 5,
                fill: config.color,
                fontSize: 10,
              }}
            />
          )}
        </React.Fragment>
      );
    });
  }, [filteredPivotLevels]);

  // Custom tooltip with pivot level info
  const CustomTooltip = useCallback(
    ({ active, payload, label }) => {
      if (!active || !payload) return null;

      const barData = chartData[label];
      if (!barData) return null;

      return (
        <div className="pivot-tooltip" style={{
          backgroundColor: theme === 'dark' ? '#1e1e1e' : '#f5f5f5',
          border: `1px solid ${theme === 'dark' ? '#444' : '#ccc'}`,
          borderRadius: '4px',
          padding: '8px',
          fontSize: '12px',
          color: theme === 'dark' ? '#fff' : '#000',
        }}>
          <p><strong>{barData.timestamp}</strong></p>
          <p>O: {barData.open?.toFixed(4)}</p>
          <p>H: {barData.high?.toFixed(4)}</p>
          <p>L: {barData.low?.toFixed(4)}</p>
          <p>C: {barData.close?.toFixed(4)}</p>
          {barData.volume && <p>V: {(barData.volume / 1000000).toFixed(2)}M</p>}
        </div>
      );
    },
    [chartData, theme]
  );

  const backgroundColor = theme === 'dark' ? '#131722' : '#ffffff';
  const gridColor = theme === 'dark' ? '#1e222d' : '#e0e0e0';
  const textColor = theme === 'dark' ? '#d1d4dc' : '#131722';

  return (
    <div style={{ width, height, backgroundColor, padding: '16px', borderRadius: '4px' }}>
      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h3 style={{ margin: '0 0 8px 0', color: textColor }}>{title}</h3>

        {/* Period selector */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {Object.entries(PERIOD_CONFIG).map(([period, config]) => (
            <button
              key={period}
              onClick={() => togglePeriod(Number(period))}
              style={{
                padding: '4px 8px',
                fontSize: '11px',
                backgroundColor: selectedPeriods.includes(Number(period))
                  ? config.color
                  : '#444',
                color: selectedPeriods.includes(Number(period)) ? '#000' : '#fff',
                border: 'none',
                borderRadius: '3px',
                cursor: 'pointer',
                opacity: selectedPeriods.includes(Number(period)) ? 1 : 0.5,
              }}
            >
              P{period}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height - 80}>
        <ComposedChart
          data={chartData}
          ref={chartRef}
          margin={{ top: 20, right: 30, left: 60, bottom: 60 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis
            dataKey="timestamp"
            tick={{ fill: textColor, fontSize: 12 }}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis
            tick={{ fill: textColor, fontSize: 12 }}
            label={{ value: 'Price', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Candlestick wicks (approximated with Line) */}
          <Line
            type="monotone"
            dataKey="high"
            stroke="transparent"
            isAnimationActive={false}
          />

          {/* Volume bars */}
          {showVolume && (
            <Bar
              dataKey="volume"
              fill="#6b7280"
              opacity={0.3}
              yAxisId="right"
            />
          )}

          {/* Pivot level lines */}
          {renderPivotLines}

          <Legend
            wrapperStyle={{ color: textColor }}
            onClick={(e) => {
              if (e.dataKey) {
                togglePeriod(Number(e.dataKey.replace('P', '')));
              }
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Analytics panel */}
      {showAnalytics && (
        <div style={{
          marginTop: '12px',
          padding: '8px',
          backgroundColor: theme === 'dark' ? '#1e222d' : '#f5f5f5',
          borderRadius: '3px',
          fontSize: '12px',
          color: textColor,
        }}>
          <span>Data Points: {chartData.length} | </span>
          <span>Pivot Levels: {filteredPivotLevels.length} | </span>
          <span>Periods: {selectedPeriods.length}</span>
        </div>
      )}
    </div>
  );
};

/**
 * Pivot Levels Dashboard - Multi-panel view
 */
const PivotLevelsDashboard = ({
  data = [],
  pivotLevels = [],
  metrics = {},
  theme = 'dark',
}) => {
  const [activePanel, setActivePanel] = useState('chart');

  const backgroundColor = theme === 'dark' ? '#131722' : '#ffffff';
  const textColor = theme === 'dark' ? '#d1d4dc' : '#131722';
  const borderColor = theme === 'dark' ? '#1e222d' : '#e0e0e0';

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 250px',
      gap: '16px',
      padding: '16px',
      backgroundColor,
    }}>
      {/* Main chart */}
      <div style={{
        border: `1px solid ${borderColor}`,
        borderRadius: '4px',
        overflow: 'hidden',
      }}>
        <PivotLevelsChart
          data={data}
          pivotLevels={pivotLevels}
          height={700}
          theme={theme}
          showAnalytics
        />
      </div>

      {/* Sidebar metrics */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}>
        <MetricCard
          title="Overall Strength"
          value={`${(metrics.overall_strength * 100).toFixed(1)}%`}
          theme={theme}
        />
        <MetricCard
          title="Pivot Count"
          value={metrics.pivot_count || 0}
          theme={theme}
        />
        <MetricCard
          title="Confidence"
          value={`${(metrics.confidence * 100).toFixed(1)}%`}
          theme={theme}
        />
        <MetricCard
          title="Top Period"
          value={metrics.top_period || 'N/A'}
          theme={theme}
        />

        {/* Period effectiveness list */}
        <div style={{
          padding: '12px',
          backgroundColor: theme === 'dark' ? '#1e222d' : '#f5f5f5',
          borderRadius: '4px',
          fontSize: '11px',
          color: textColor,
        }}>
          <p style={{ margin: '0 0 8px 0', fontWeight: 'bold' }}>Period Effectiveness</p>
          {metrics.period_effectiveness?.slice(0, 5).map((pe) => (
            <div key={pe.period} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span>P{pe.period}</span>
              <span>{(pe.effectiveness * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

/**
 * Metric card component for sidebar
 */
const MetricCard = ({ title, value, theme }) => {
  const backgroundColor = theme === 'dark' ? '#1e222d' : '#f5f5f5';
  const textColor = theme === 'dark' ? '#d1d4dc' : '#131722';

  return (
    <div style={{
      padding: '12px',
      backgroundColor,
      borderRadius: '4px',
      textAlign: 'center',
    }}>
      <p style={{ margin: '0', fontSize: '11px', color: '#888' }}>{title}</p>
      <p style={{ margin: '4px 0 0 0', fontSize: '18px', fontWeight: 'bold', color: textColor }}>
        {value}
      </p>
    </div>
  );
};

export { PivotLevelsChart, PivotLevelsDashboard, PERIOD_CONFIG };
