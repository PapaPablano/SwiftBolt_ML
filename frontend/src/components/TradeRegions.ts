/**
 * TradeRegions — Draw shaded entry→exit regions on a TradingView chart.
 *
 * Uses line series with area fills to show trade duration and P&L visually.
 * Each trade gets a green (win) or red (loss) shaded region between
 * entry and exit prices/dates.
 */
import type { IChartApi, ISeriesApi } from 'lightweight-charts';

export interface TradeRegionData {
  entryTime: string;
  exitTime: string;
  entryPrice: number;
  exitPrice: number;
  isWin: boolean;
}

const WIN_COLOR = 'rgba(34, 197, 94, 0.12)';   // green-500 @ 12%
const LOSS_COLOR = 'rgba(239, 68, 68, 0.12)';   // red-500 @ 12%
const WIN_LINE = 'rgba(34, 197, 94, 0.5)';
const LOSS_LINE = 'rgba(239, 68, 68, 0.5)';

/** Manages trade region overlays on a chart. Call `update()` to set trades, `clear()` to remove. */
export class TradeRegionManager {
  private chart: IChartApi;
  private series: ISeriesApi<'Line'>[] = [];

  constructor(chart: IChartApi) {
    this.chart = chart;
  }

  /** Remove all trade region series from the chart. */
  clear() {
    for (const s of this.series) {
      try {
        this.chart.removeSeries(s);
      } catch {
        // Series may already be removed on chart disposal
      }
    }
    this.series = [];
  }

  /**
   * Draw trade regions for the given trades.
   * Viewport culling: only draws trades that overlap the visible time range.
   */
  update(trades: TradeRegionData[], visibleRange?: { from: string; to: string } | null) {
    this.clear();

    if (!trades.length) return;

    // Viewport culling — skip trades entirely outside visible range
    const filtered = visibleRange
      ? trades.filter(
          (t) => t.exitTime >= visibleRange.from && t.entryTime <= visibleRange.to,
        )
      : trades;

    for (const trade of filtered) {
      const color = trade.isWin ? WIN_LINE : LOSS_LINE;
      const areaColor = trade.isWin ? WIN_COLOR : LOSS_COLOR;

      try {
        const lineSeries = this.chart.addLineSeries({
          color,
          lineWidth: 1,
          lineStyle: 2, // Dashed
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });

        // Draw a line from entry to exit, with area fill to the entry price baseline
        lineSeries.setData([
          { time: trade.entryTime as any, value: trade.entryPrice },
          { time: trade.exitTime as any, value: trade.exitPrice },
        ]);

        // Apply area fill using series options
        lineSeries.applyOptions({
          lineVisible: true,
          topColor: areaColor,
          bottomColor: 'transparent',
        } as any);

        this.series.push(lineSeries);
      } catch {
        // Skip invalid trades (e.g., dates that can't be parsed)
      }
    }
  }

  /** Dispose all resources. */
  dispose() {
    this.clear();
  }
}
