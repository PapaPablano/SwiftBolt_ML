import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi } from 'lightweight-charts';
import { dedupeEquityCurve } from '../lib/backtestConstants';

interface EquityCurveChartProps {
  equityCurve: { time: string | number; value: number }[];
  height?: number;
}

const EquityCurveChart: React.FC<EquityCurveChartProps> = ({ equityCurve, height = 160 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    chartInstanceRef.current?.remove();
    chartInstanceRef.current = null;

    if (!equityCurve?.length) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#111827' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#374151' }, horzLines: { color: '#374151' } },
      timeScale: { borderColor: '#374151' },
      height,
    });
    chartInstanceRef.current = chart;

    const lineSeries = chart.addLineSeries({ color: '#3b82f6', lineWidth: 2 });
    const deduped = dedupeEquityCurve(equityCurve);
    lineSeries.setData(
      deduped.map((p) => ({
        time: (typeof p.time === 'string'
          ? Math.floor(new Date(p.time).getTime() / 1000)
          : p.time) as any,
        value: p.value,
      })),
    );
    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartInstanceRef.current = null;
    };
  }, [equityCurve, height]);

  return <div ref={containerRef} className="w-full" />;
};

export default EquityCurveChart;
