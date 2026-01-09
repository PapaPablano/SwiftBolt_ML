/**
 * SwiftBolt ML - Lightweight Charts Integration
 *
 * This module provides a Swift-compatible API for TradingView Lightweight Charts.
 * Commands are received from Swift via evaluateJavaScript and events are sent
 * back via WKScriptMessageHandler.
 */

(function() {
    'use strict';

    // Chart state
    const state = {
        chart: null,
        series: {},
        subPanels: {},      // Sub-panel charts for oscillators
        subSeries: {},      // Series within sub-panels
        priceLines: [],     // Track added price lines for cleanup
        lastCrosshairData: null,
        theme: 'dark',
        isReady: false,
        useHeikinAshi: false,
        originalBars: [],   // Store original OHLC data
        heikinAshiBars: []  // Store transformed HA data
    };

    // Sub-panel configurations
    const subPanelConfig = {
        rsi: { id: 'rsi-panel', height: 100, scaleMin: 0, scaleMax: 100 },
        macd: { id: 'macd-panel', height: 120 },
        stochastic: { id: 'stochastic-panel', height: 100, scaleMin: 0, scaleMax: 100 },
        kdj: { id: 'kdj-panel', height: 100, scaleMin: 0, scaleMax: 100 },
        adx: { id: 'adx-panel', height: 100, scaleMin: 0, scaleMax: 100 },
        atr: { id: 'atr-panel', height: 80 },
        volume: { id: 'volume-panel', height: 120 }
    };

    // Color palette (matches ChartColors.swift)
    const colors = {
        // Candlesticks
        bullish: '#33d97a',      // green
        bearish: '#ff4d4d',      // red

        // Moving Averages
        sma20: '#4db8ff',        // sky blue
        sma50: '#ffa600',        // orange
        sma200: '#d966f2',       // purple
        ema9: '#00ffbf',         // teal
        ema21: '#ff80b3',        // pink

        // Forecast
        forecastBullish: '#4de680',
        forecastBearish: '#ff5959',
        forecastNeutral: '#ffbf00',

        // SuperTrend
        superTrendBull: '#00ff80',
        superTrendBear: '#ff4080',

        // Bollinger Bands
        bollingerBand: '#b3b3d9',

        // RSI
        rsi: '#f0b90b',
        rsiOverbought: '#ff5252',
        rsiOversold: '#4caf50',

        // MACD
        macdLine: '#2196f3',
        macdSignal: '#ff9800',
        macdHistoUp: '#4caf50',
        macdHistoDown: '#f44336',

        // Stochastic / KDJ
        stochK: '#2196f3',
        stochD: '#ff9800',
        kdjJ: '#9c27b0',

        // ADX
        adx: '#ffeb3b',
        plusDI: '#4caf50',
        minusDI: '#f44336',

        // ATR
        atr: '#00bcd4',

        // Volume
        volumeUp: '#26a69a80',    // Semi-transparent green
        volumeDown: '#ef535080',  // Semi-transparent red

        // Grid & text
        grid: '#2a2a2a',
        text: '#888888',
        crosshair: '#555555'
    };

    // Chart options for dark theme
    const darkThemeOptions = {
        layout: {
            background: { type: 'solid', color: '#1e1e1e' },
            textColor: colors.text,
            fontSize: 12,
            fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif"
        },
        grid: {
            vertLines: { color: colors.grid },
            horzLines: { color: colors.grid }
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: colors.crosshair,
                width: 1,
                style: LightweightCharts.LineStyle.Dashed,
                labelBackgroundColor: '#2a2a2a'
            },
            horzLine: {
                color: colors.crosshair,
                width: 1,
                style: LightweightCharts.LineStyle.Dashed,
                labelBackgroundColor: '#2a2a2a'
            }
        },
        rightPriceScale: {
            borderColor: '#333',
            scaleMargins: { top: 0.1, bottom: 0.1 }
        },
        timeScale: {
            borderColor: '#333',
            timeVisible: true,
            secondsVisible: false,
            rightOffset: 5,
            barSpacing: 8,
            minBarSpacing: 2
        },
        handleScroll: {
            mouseWheel: true,
            pressedMouseMove: true
        },
        handleScale: {
            axisPressedMouseMove: true,
            mouseWheel: true,
            pinch: true
        }
    };

    // Candlestick series options
    const candlestickOptions = {
        upColor: colors.bullish,
        downColor: colors.bearish,
        borderUpColor: colors.bullish,
        borderDownColor: colors.bearish,
        wickUpColor: colors.bullish,
        wickDownColor: colors.bearish
    };

    /**
     * Send message to Swift via WKScriptMessageHandler
     */
    function sendToSwift(type, data = {}) {
        if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.bridge) {
            window.webkit.messageHandlers.bridge.postMessage({ type, ...data });
        } else {
            console.log('[ChartJS] Swift bridge not available:', type, data);
        }
    }

    /**
     * Update legend display
     */
    function updateLegend(seriesId, name, value, color) {
        const legend = document.getElementById('legend');
        let item = document.getElementById(`legend-${seriesId}`);

        if (!item) {
            item = document.createElement('div');
            item.id = `legend-${seriesId}`;
            item.className = 'legend-item';
            legend.appendChild(item);
        }

        const valueStr = value !== null ? value.toFixed(2) : '--';
        item.innerHTML = `
            <span class="legend-color" style="background-color: ${color}"></span>
            <span>${name}: ${valueStr}</span>
        `;
    }

    /**
     * Handle crosshair move for tooltip
     */
    function setupCrosshairHandler() {
    if (!state.chart) return;

    state.chart.subscribeCrosshairMove((param) => {
        const tooltip = document.getElementById('tooltip');

        // When crosshair is off-canvas or no time, hide
        if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
            if (tooltip) tooltip.style.display = 'none';
            if (window.enhancedTooltip) window.enhancedTooltip.hide();
            return;
        }

        // Get main candle data at the crosshair
        const candleData = param.seriesData.get(state.series.candles);
        if (!candleData) {
            if (tooltip) tooltip.style.display = 'none';
            if (window.enhancedTooltip) window.enhancedTooltip.hide();
            return;
        }

        const { open, high, low, close } = candleData;

        // Try to get volume from a dedicated series if present
        let volume = undefined;
        try {
            if (state.series.volume) {
                const volData = param.seriesData.get(state.series.volume);
                if (volData && typeof volData.value === 'number') volume = volData.value;
                else if (volData && typeof volData.volume === 'number') volume = volData.volume;
            }
        } catch {}

        // Update & show the enhanced tooltip (fallback to hiding if not loaded)
        if (window.enhancedTooltip && typeof window.enhancedTooltip.update === 'function') {
            window.enhancedTooltip.update('main', { time: param.time, open, high, low, close, volume });
            window.enhancedTooltip.show(param.point.x + 12, param.point.y + 12);
        } else {
            if (tooltip) tooltip.style.display = 'none';
        }

        // Sync crosshair by time to sub-panels
        syncCrosshair(param.time);
    });
}

/**
* Handle visible range changes (for lazy loading)
*/
function setupVisibleRangeHandler() {
if (!state.chart) return;

state.chart.timeScale().subscribeVisibleTimeRangeChange((newRange) => {
if (newRange) {
sendToSwift('visibleRange', {
from: newRange.from,
to: newRange.to
});

// Sync sub-panel time scales
Object.values(state.subPanels).forEach(subChart => {
if (subChart) {
subChart.timeScale().setVisibleRange(newRange);
}
});
}
});
}

/**
* Create or get a sub-panel chart
*/
function getOrCreateSubPanel(panelName) {
// Ensure sub-series bucket exists
if (!state.subSeries[panelName]) {
state.subSeries[panelName] = {};
}

if (state.subPanels[panelName]) {
return state.subPanels[panelName];
}

const config = subPanelConfig[panelName];
if (!config) {
console.error('[ChartJS] Unknown sub-panel:', panelName);
return null;
}

const container = document.getElementById(config.id);
if (!container) {
console.error('[ChartJS] Sub-panel container not found:', config.id);
return null;
}

// Show the panel
container.classList.add('active');

// Create chart with minimal options
const subChart = LightweightCharts.createChart(container, {
...darkThemeOptions,
width: container.clientWidth,
height: config.height,
rightPriceScale: {
borderColor: '#333',
scaleMargins: { 
top: panelName === 'volume' ? 0.05 : 0.1, 
bottom: panelName === 'volume' ? 0.05 : 0.1 
},
autoScale: true,
visible: true,
...(config.scaleMin !== undefined && {
mode: LightweightCharts.PriceScaleMode.Normal
})
},
timeScale: {
visible: false,  // Hide time scale on sub-panels
borderColor: '#333'
},
crosshair: {
mode: LightweightCharts.CrosshairMode.Normal,
vertLine: { visible: true, color: colors.crosshair, width: 1, style: LightweightCharts.LineStyle.Dashed },
horzLine: { color: colors.crosshair, width: 1, style: LightweightCharts.LineStyle.Dashed, labelVisible: true }
}
});

// Handle resize
const resizeObserver = new ResizeObserver(entries => {
for (const entry of entries) {
if (subChart) {
subChart.resize(entry.contentRect.width, config.height);
}
}
});
resizeObserver.observe(container);

state.subPanels[panelName] = subChart;
state.subSeries[panelName] = {};

// Sync initial range
if (state.chart) {
const range = state.chart.timeScale().getVisibleRange();
if (range) subChart.timeScale().setVisibleRange(range);
}

console.log('[ChartJS] Sub-panel created:', panelName);
return subChart;
}

/**
* Hide a sub-panel
*/
function hideSubPanel(panelName) {
const config = subPanelConfig[panelName];
if (!config) return;

const container = document.getElementById(config.id);
if (container) {
container.classList.remove('active');
}

// Remove chart
if (state.subPanels[panelName]) {
state.subPanels[panelName].remove();
delete state.subPanels[panelName];
delete state.subSeries[panelName];
}
}

/**
* Sync crosshair with sub-panels
*/
function syncCrosshair(time) {
Object.values(state.subPanels).forEach(subChart => {
if (subChart) {
subChart.setCrosshairPosition(0, time, subChart.priceScale('right').coordinateToPrice(0));
}
});
}

/**
* Chart API - called from Swift via evaluateJavaScript
*/
window.chartApi = {
/**
* Initialize the chart
*/
init: function(options = {}) {
const container = document.getElementById('chart-container');
container.classList.remove('loading');
container.innerHTML = '';

const mergedOptions = {
...darkThemeOptions,
width: container.clientWidth,
height: container.clientHeight,
...options
};

state.chart = LightweightCharts.createChart(container, mergedOptions);

// Handle resize
const resizeObserver = new ResizeObserver(entries => {
for (const entry of entries) {
if (state.chart) {
state.chart.resize(entry.contentRect.width, entry.contentRect.height);
}
}
});
resizeObserver.observe(container);

setupCrosshairHandler();
setupVisibleRangeHandler();

state.isReady = true;
console.log('[ChartJS] Chart initialized');
},

/**
* Add a horizontal price line
*/
addPriceLine: function(seriesId, price, options = {}) {
const series = state.series[seriesId] || state.series.candles;
if (!series) return null;

const priceLineOptions = {
price: price,
color: options.color || '#888',
lineWidth: options.lineWidth || 1,
lineStyle: options.lineStyle || LightweightCharts.LineStyle.Dashed,
axisLabelVisible: options.showLabel !== false,
title: options.title || '',
category: options.category || 'general'
};

const line = series.createPriceLine(priceLineOptions);
// Store category for selective removal
state.priceLines.push({ 
series: series, 
line: line,
category: priceLineOptions.category
});
return line;
},

/**
* Remove all price lines
*/
clearPriceLines: function() {
state.priceLines.forEach(item => {
try {
item.series.removePriceLine(item.line);
} catch (e) {
console.warn('[ChartJS] Failed to remove price line', e);
}
});
state.priceLines = [];
console.log('[ChartJS] Price lines cleared');
},

/**
* Remove price lines by category
*/
removePriceLines: function(category) {
if (!category) {
this.clearPriceLines();
return;
}

const remainingLines = [];
state.priceLines.forEach(item => {
if (item.category === category) {
try {
item.series.removePriceLine(item.line);
} catch (e) {
console.warn('[ChartJS] Failed to remove price line', e);
}
} else {
remainingLines.push(item);
}
});

state.priceLines = remainingLines;
console.log('[ChartJS] Price lines removed for category:', category);
},

/**
* Set candlestick data
*/
setCandles: function(data) {
    if (!state.chart) {
        console.error('[ChartJS] Chart not initialized');
        return;
    }

    // Sort data by time and keep originalBars sorted
    const sortedData = [...data].sort((a, b) => a.time - b.time);
    state.originalBars = sortedData;

    // Create candlestick series if it doesn't exist
    if (!state.series.candles) {
        state.series.candles = state.chart.addCandlestickSeries(candlestickOptions);
        console.log('[ChartJS] Candlestick series created');
    }

    // Apply Heikin-Ashi transformation if enabled
    const displayData = state.useHeikinAshi ? calculateHeikinAshi(sortedData) : sortedData;
    if (state.useHeikinAshi) {
        state.heikinAshiBars = displayData;
    }

    // Set the data
    state.series.candles.setData(displayData);
    
    // Fit content to ensure data is visible
    state.chart.timeScale().fitContent();

    console.log('[ChartJS] Candles set:', sortedData.length, 'bars, HA:', state.useHeikinAshi);
},

/**
* Update a single candlestick (for live updates)
*/
updateCandle: function(candle) {
    if (!state.series.candles) {
        console.warn('[ChartJS] No candle series to update');
        return;
    }

    // Update original bars
    if (state.originalBars.length > 0) {
        state.originalBars[state.originalBars.length - 1] = candle;
    }

    // Apply HA transformation if enabled
    const displayCandle = state.useHeikinAshi ? 
        calculateHeikinAshi(state.originalBars).slice(-1)[0] : 
        candle;

    state.series.candles.update(displayCandle);
    console.log('[ChartJS] Candle updated');
},

/**
* Add a line series (for indicators, forecasts)
*/
addLine: function(id, options = {}) {
    if (!state.chart) return;

    const defaultOptions = {
        color: colors.sma20,
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4
    };

    const series = state.chart.addLineSeries({ ...defaultOptions, ...options });
    state.series[id] = series;

    console.log('[ChartJS] Line series added:', id);
    return series;
},

/**
* Remove a series by id
*/
removeSeries: function(id) {
    const series = state.series[id];
    if (series && state.chart) {
        try { 
            state.chart.removeSeries(series); 
        } catch (e) {
            console.warn('[ChartJS] removeSeries failed', id, e);
        }
        delete state.series[id];
    }
},

        /**
         * Set data for a line series
         */
        setLine: function(id, data, options = {}) {
    if (!state.chart) return;

    let series = state.series[id];
    if (!series) {
        series = this.addLine(id, options);
    }

    const sortedData = [...data].sort((a, b) => a.time - b.time);
    series.setData(sortedData);

    // Update legend if name provided
    if (options.name && sortedData.length > 0) {
        const lastValue = sortedData[sortedData.length - 1].value;
        updateLegend(id, options.name, lastValue, options.color || colors.sma20);
    }

    console.log('[ChartJS] Line data set:', id, sortedData.length);
},

        /**
         * Add forecast overlay with confidence bands
         */
        setForecast: function(midData, upperData, lowerData, options = {}) {
            const color = options.color || colors.forecastBullish;
            const bandColor = options.bandColor || `${color}33`;  // 20% opacity

            // Mid line (main forecast)
            this.setLine('forecast-mid', midData, {
                color: color,
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                name: 'Forecast'
            });

            // Upper bound
            this.setLine('forecast-upper', upperData, {
                color: bandColor,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted
            });

            // Lower bound
            this.setLine('forecast-lower', lowerData, {
                color: bandColor,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted
            });

            console.log('[ChartJS] Forecast set');
        },

        /**
         * Set forecast as overlay candlestick series (intraday-specific)
         */
        setForecastCandles: function(data) {
            if (!state.chart) {
                console.error('[ChartJS] Chart not initialized');
                return;
            }

            // Create forecast candle series if it doesn't exist
            if (!state.series.forecast_candles) {
                state.series.forecast_candles = state.chart.addCandlestickSeries({
                    upColor: '#4de68080',
                    downColor: '#ff595980',
                    borderUpColor: '#4de680',
                    borderDownColor: '#ff5959',
                    wickUpColor: '#4de680',
                    wickDownColor: '#ff5959',
                    priceLineVisible: false,
                    lastValueVisible: true
                });
            }

            // Sort data by time and apply
            const sortedData = [...data].sort((a, b) => a.time - b.time);
            state.series.forecast_candles.setData(sortedData);

            console.log('[ChartJS] Forecast candles set:', sortedData.length);
        },

        /**
         * Add markers (buy/sell signals)
         */
        setMarkers: function(seriesId, markers) {
            const series = state.series[seriesId];
            if (!series) {
                console.error('[ChartJS] Series not found:', seriesId);
                return;
            }

            // Format markers for Lightweight Charts
            const formattedMarkers = markers.map(m => ({
                time: m.time,
                position: m.position || (m.type === 'buy' ? 'belowBar' : 'aboveBar'),
                color: m.color || (m.type === 'buy' ? colors.bullish : colors.bearish),
                shape: m.shape || (m.type === 'buy' ? 'arrowUp' : 'arrowDown'),
                text: m.text || (m.type === 'buy' ? 'BUY' : 'SELL'),
                size: m.size || 1
            }));

            series.setMarkers(formattedMarkers);
            console.log('[ChartJS] Markers set:', formattedMarkers.length);
        },

        /**
         * Clear all series except candles
         */
        clearIndicators: function() {
            // Clear price lines first
            this.clearPriceLines();

            Object.keys(state.series).forEach(id => {
                if (id !== 'candles') {
                    this.removeSeries(id);
                }
            });
            console.log('[ChartJS] Indicators cleared');
        },

        /**
         * Remove volume profile overlay
         */
        removeVolumeProfile: function() {
            if (state.series.volumeProfile && state.chart) {
                state.chart.removeSeries(state.series.volumeProfile);
                delete state.series.volumeProfile;
                console.log('[ChartJS] Volume profile removed');
            }
        },

        /**
         * Set RSI data
         */
        setRSI: function(data) {
            const chart = getOrCreateSubPanel('rsi');
            if (!chart) return;

            if (!state.subSeries.rsi) state.subSeries.rsi = {};

            // Add overbought/oversold lines
            if (!state.subSeries.rsi.overbought) {
                const overbought = chart.addLineSeries({
                    color: colors.rsiOverbought,
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    priceLineVisible: false,
                    lastValueVisible: false
                });
                overbought.setData(data.map(d => ({ time: d.time, value: 70 })));
                state.subSeries.rsi.overbought = overbought;

                const oversold = chart.addLineSeries({
                    color: colors.rsiOversold,
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    priceLineVisible: false,
                    lastValueVisible: false
                });
                oversold.setData(data.map(d => ({ time: d.time, value: 30 })));
                state.subSeries.rsi.oversold = oversold;
            }

            // RSI line
            if (!state.subSeries.rsi.line) {
                state.subSeries.rsi.line = chart.addLineSeries({
                    color: colors.rsi,
                    lineWidth: 2,
                    priceLineVisible: true,
                    lastValueVisible: true
                });
            }
            state.subSeries.rsi.line.setData(data);

            // Sync time scale
            if (state.chart) {
                const range = state.chart.timeScale().getVisibleRange();
                if (range) chart.timeScale().setVisibleRange(range);
            }

            console.log('[ChartJS] RSI set:', data.length);
        },

        /**
         * Set MACD data (line, signal, histogram)
         */
        setMACD: function(line, signal, histogram) {
            const chart = getOrCreateSubPanel('macd');
            if (!chart) return;
            if (!state.subSeries.macd) state.subSeries.macd = {};

            // Histogram (must be added first for proper layering)
            if (!state.subSeries.macd.histogram) {
                state.subSeries.macd.histogram = chart.addHistogramSeries({
                    priceLineVisible: false,
                    lastValueVisible: false
                });
            }
            // Color histogram based on direction
            const histData = histogram.map(h => ({
                time: h.time,
                value: h.value,
                color: h.value >= 0 ? colors.macdHistoUp : colors.macdHistoDown
            }));
            state.subSeries.macd.histogram.setData(histData);

            // Signal line
            if (!state.subSeries.macd.signal) {
                state.subSeries.macd.signal = chart.addLineSeries({
                    color: colors.macdSignal,
                    lineWidth: 1,
                    priceLineVisible: false,
                    lastValueVisible: true
                });
            }
            state.subSeries.macd.signal.setData(signal);

            // MACD line
            if (!state.subSeries.macd.line) {
                state.subSeries.macd.line = chart.addLineSeries({
                    color: colors.macdLine,
                    lineWidth: 2,
                    priceLineVisible: true,
                    lastValueVisible: true
                });
            }
            state.subSeries.macd.line.setData(line);

            // Sync time scale
            if (state.chart) {
                const range = state.chart.timeScale().getVisibleRange();
                if (range) chart.timeScale().setVisibleRange(range);
            }

            console.log('[ChartJS] MACD set:', line.length);
        },

        /**
         * Set Stochastic data (K and D lines)
         */
        setStochastic: function(kData, dData) {
            const chart = getOrCreateSubPanel('stochastic');
            if (!chart) return;
            if (!state.subSeries.stochastic) state.subSeries.stochastic = {};

            // Add overbought/oversold lines
            if (!state.subSeries.stochastic.overbought) {
                const overbought = chart.addLineSeries({
                    color: '#666',
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    priceLineVisible: false,
                    lastValueVisible: false
                });
                overbought.setData(kData.map(d => ({ time: d.time, value: 80 })));
                state.subSeries.stochastic.overbought = overbought;

                const oversold = chart.addLineSeries({
                    color: '#666',
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    priceLineVisible: false,
                    lastValueVisible: false
                });
                oversold.setData(kData.map(d => ({ time: d.time, value: 20 })));
                state.subSeries.stochastic.oversold = oversold;
            }

            // D line
            if (!state.subSeries.stochastic.d) {
                state.subSeries.stochastic.d = chart.addLineSeries({
                    color: colors.stochD,
                    lineWidth: 1,
                    priceLineVisible: false,
                    lastValueVisible: true
                });
            }
            state.subSeries.stochastic.d.setData(dData);

            // K line
            if (!state.subSeries.stochastic.k) {
                state.subSeries.stochastic.k = chart.addLineSeries({
                    color: colors.stochK,
                    lineWidth: 2,
                    priceLineVisible: true,
                    lastValueVisible: true
                });
            }
            state.subSeries.stochastic.k.setData(kData);

            // Sync time scale
            if (state.chart) {
                const range = state.chart.timeScale().getVisibleRange();
                if (range) chart.timeScale().setVisibleRange(range);
            }

            console.log('[ChartJS] Stochastic set:', kData.length);
        },

        /**
         * Set KDJ data (K, D, and J lines)
         */
        setKDJ: function(kData, dData, jData) {
            const chart = getOrCreateSubPanel('kdj');
            if (!chart) return;
            if (!state.subSeries.kdj) state.subSeries.kdj = {};

            // J line (most volatile)
            if (!state.subSeries.kdj.j) {
                state.subSeries.kdj.j = chart.addLineSeries({
                    color: colors.kdjJ,
                    lineWidth: 1,
                    priceLineVisible: false,
                    lastValueVisible: true
                });
            }
            state.subSeries.kdj.j.setData(jData);

            // D line
            if (!state.subSeries.kdj.d) {
                state.subSeries.kdj.d = chart.addLineSeries({
                    color: colors.stochD,
                    lineWidth: 1,
                    priceLineVisible: false,
                    lastValueVisible: true
                });
            }
            state.subSeries.kdj.d.setData(dData);

            // K line
            if (!state.subSeries.kdj.k) {
                state.subSeries.kdj.k = chart.addLineSeries({
                    color: colors.stochK,
                    lineWidth: 2,
                    priceLineVisible: true,
                    lastValueVisible: true
                });
            }
            state.subSeries.kdj.k.setData(kData);

            // Sync time scale
            if (state.chart) {
                const range = state.chart.timeScale().getVisibleRange();
                if (range) chart.timeScale().setVisibleRange(range);
            }

            console.log('[ChartJS] KDJ set:', kData.length);
        },

        /**
         * Set ADX data (ADX, +DI, -DI)
         */
        setADX: function(adxData, plusDI, minusDI) {
            const chart = getOrCreateSubPanel('adx');
            if (!chart) return;
            if (!state.subSeries.adx) state.subSeries.adx = {};

            // +DI
            if (!state.subSeries.adx.plusDI) {
                state.subSeries.adx.plusDI = chart.addLineSeries({
                    color: colors.plusDI,
                    lineWidth: 1,
                    priceLineVisible: false,
                    lastValueVisible: true
                });
            }
            state.subSeries.adx.plusDI.setData(plusDI);

            // -DI
            if (!state.subSeries.adx.minusDI) {
                state.subSeries.adx.minusDI = chart.addLineSeries({
                    color: colors.minusDI,
                    lineWidth: 1,
                    priceLineVisible: false,
                    lastValueVisible: true
                });
            }
            state.subSeries.adx.minusDI.setData(minusDI);

            // ADX line
            if (!state.subSeries.adx.line) {
                state.subSeries.adx.line = chart.addLineSeries({
                    color: colors.adx,
                    lineWidth: 2,
                    priceLineVisible: true,
                    lastValueVisible: true
                });
            }
            state.subSeries.adx.line.setData(adxData);

            // Sync time scale
            if (state.chart) {
                const range = state.chart.timeScale().getVisibleRange();
                if (range) chart.timeScale().setVisibleRange(range);
            }

            console.log('[ChartJS] ADX set:', adxData.length);
        },

        /**
         * Set ATR data
         */
        setATR: function(data) {
            const chart = getOrCreateSubPanel('atr');
            if (!chart) return;
            if (!state.subSeries.atr) state.subSeries.atr = {};

            if (!state.subSeries.atr.line) {
                state.subSeries.atr.line = chart.addLineSeries({
                    color: colors.atr,
                    lineWidth: 2,
                    priceLineVisible: true,
                    lastValueVisible: true
                });
            }
            state.subSeries.atr.line.setData(data);

            // Sync time scale
            if (state.chart) {
                const range = state.chart.timeScale().getVisibleRange();
                if (range) chart.timeScale().setVisibleRange(range);
            }

            console.log('[ChartJS] ATR set:', data.length);
        },

        /**
         * Set Volume data with color based on price direction
         */
        setVolume: function(data) {
            const chart = getOrCreateSubPanel('volume');
            if (!chart) return;

            // Initialize subSeries.volume if needed
            if (!state.subSeries.volume) {
                state.subSeries.volume = {};
            }

            if (!state.subSeries.volume.histogram) {
                state.subSeries.volume.histogram = chart.addHistogramSeries({
                    priceLineVisible: false,
                    lastValueVisible: true,
                    priceFormat: {
                        type: 'volume'
                    },
                    priceScaleId: 'right'
                });
                
                // Configure price scale for volume
                chart.priceScale('right').applyOptions({
                    scaleMargins: {
                        top: 0.1,
                        bottom: 0.0
                    },
                    autoScale: true
                });
            }

            // Color volume bars based on price direction (green=up, red=down)
            const coloredData = data.map(v => ({
                time: v.time,
                value: v.value,
                color: v.color || (v.direction === 'up' ? colors.volumeUp : colors.volumeDown)
            }));

            state.subSeries.volume.histogram.setData(coloredData);

            // Sync time scale
            if (state.chart) {
                const range = state.chart.timeScale().getVisibleRange();
                if (range) chart.timeScale().setVisibleRange(range);
            }

            console.log('[ChartJS] Volume set:', data.length);
        },

        /**
         * Set SuperTrend with dynamic coloring based on trend
         * Creates separate line segments that disconnect at trend changes
         * Adds BUY/SELL markers at signal points
         */
        setSuperTrend: function(data, trendData, strengthData) {
            console.log('[ChartJS] setSuperTrend called, points:', data.length);

            if (!state.chart) {
                console.error('[ChartJS] Chart not initialized');
                return;
            }

            // Remove existing SuperTrend series
            if (state.series.supertrend_segments) {
                state.series.supertrend_segments.forEach(s => state.chart.removeSeries(s));
            }
            state.series.supertrend_segments = [];

            // Build segments - each segment is a continuous line of same trend
            // Disconnect at trend changes (no connecting line between segments)
            // Note: Signal markers are handled separately via setSignals()
            const segments = [];
            let currentSegment = null;
            let lastTrend = null;

            for (let i = 0; i < data.length; i++) {
                const point = data[i];
                const trend = trendData && trendData[i] ? trendData[i].value : 0;
                // Trend is 1 for bullish, -1 for bearish (or 0/1 in some cases)
                const isBullish = trend === 1 || trend > 0;

                // Detect trend change
                if (lastTrend !== null && lastTrend !== isBullish) {
                    // End current segment
                    if (currentSegment && currentSegment.points.length > 0) {
                        segments.push(currentSegment);
                    }
                    // Start new segment
                    currentSegment = {
                        isBullish: isBullish,
                        points: [{ time: point.time, value: point.value }]
                    };
                } else {
                    // Continue current segment or start first one
                    if (!currentSegment) {
                        currentSegment = {
                            isBullish: isBullish,
                            points: []
                        };
                    }
                    currentSegment.points.push({ time: point.time, value: point.value });
                }

                lastTrend = isBullish;
            }

            // Push final segment
            if (currentSegment && currentSegment.points.length > 0) {
                segments.push(currentSegment);
            }

            console.log('[ChartJS] SuperTrend segments:', segments.length);

            // Create a line series for each segment
            segments.forEach((seg, idx) => {
                if (seg.points.length > 0) {
                    const series = state.chart.addLineSeries({
                        color: seg.isBullish ? colors.superTrendBull : colors.superTrendBear,
                        lineWidth: 2,
                        priceLineVisible: false,
                        crosshairMarkerVisible: false,
                        lastValueVisible: idx === segments.length - 1
                    });
                    series.setData(seg.points);
                    state.series.supertrend_segments.push(series);
                }
            });
            
            // Create a hidden "supertrend" series for markers
            // This allows setMarkers('supertrend', ...) to work and position markers on the line
            const fullSeries = state.chart.addLineSeries({
                color: 'transparent',
                lineWidth: 0,
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: true // Enable crosshair for this one so we can see value
            });
            fullSeries.setData(data);
            state.series.supertrend = fullSeries;
            
            console.log('[ChartJS] SuperTrend rendering complete');
        },

        /**
         * Hide a sub-panel
         */
        hidePanel: function(panelName) {
            hideSubPanel(panelName);
            console.log('[ChartJS] Panel hidden:', panelName);
        },

        /**
         * Set time scale visible range
         */
        setVisibleRange: function(from, to) {
            if (state.chart) {
                state.chart.timeScale().setVisibleRange({ from, to });
            }
        },

        /**
         * Scroll to most recent data
         */
        scrollToRealTime: function() {
            if (state.chart) {
                state.chart.timeScale().scrollToRealTime();
            }
        },

        /**
         * Fit all data in view
         */
        fitContent: function() {
            if (state.chart) {
                state.chart.timeScale().fitContent();
            }
        },

        /**
         * Toggle Heikin-Ashi candlesticks
         */
        toggleHeikinAshi: function(enabled) {
            state.useHeikinAshi = enabled;
            
            if (!state.series.candles || state.originalBars.length === 0) {
                console.log('[ChartJS] No candle data to transform');
                return;
            }
            
            // Apply transformation and update display
            const displayData = enabled ? calculateHeikinAshi(state.originalBars) : state.originalBars;
            if (enabled) {
                state.heikinAshiBars = displayData;
            }
            
            state.series.candles.setData(displayData);
            
            // Update candle colors for HA mode
            if (enabled) {
                state.series.candles.applyOptions({
                    upColor: '#32CD32',
                    downColor: '#FF6B6B',
                    borderUpColor: '#32CD32',
                    borderDownColor: '#FF6B6B',
                    wickUpColor: '#32CD32',
                    wickDownColor: '#FF6B6B'
                });
            } else {
                state.series.candles.applyOptions(candlestickOptions);
            }
            
            console.log('[ChartJS] Heikin-Ashi toggled:', enabled);
        },

        /**
         * Set volume profile data (right-side histogram)
         */
        setVolumeProfile: function(profileData) {
            if (!state.chart) {
                console.error('[ChartJS] Chart not initialized');
                return;
            }
            
            // Create volume profile series if not exists
            if (!state.series.volumeProfile) {
                state.series.volumeProfile = state.chart.addHistogramSeries({
                    color: '#26a69a',
                    priceFormat: {
                        type: 'volume',
                    },
                    priceScaleId: 'volume-profile',
                    overlay: true
                });
            }
            
            // Convert profile data to histogram format
            const currentTime = Math.floor(Date.now() / 1000);
            const histData = profileData.map(item => ({
                time: currentTime,
                value: item.volumePercentage || item.volume,
                color: item.pointOfControl ? '#FF6B6B' : '#26a69a'
            }));
            
            state.series.volumeProfile.setData(histData);
            console.log('[ChartJS] Volume profile set:', profileData.length, 'levels');
        },

        /**
         * Update live bar with animation
         */
        updateLiveBar: function(newBar, duration = 500) {
            if (!state.series.candles || state.originalBars.length === 0) return;
            
            // Update the last bar in original data
            state.originalBars[state.originalBars.length - 1] = newBar;
            
            // Apply HA transformation if enabled
            const displayBar = state.useHeikinAshi ? 
                calculateHeikinAshi(state.originalBars).slice(-1)[0] : 
                newBar;
            
            // Animate the update (simple version - just update)
            state.series.candles.update(displayBar);
            
            console.log('[ChartJS] Live bar updated');
        },

        /**
         * Apply a command object (for batched updates from Swift)
         */
        apply: function(cmd) {
            if (!cmd || !cmd.type) {
                console.error('[ChartJS] Invalid command:', cmd);
                return;
            }

            try {
                switch (cmd.type) {
                    case 'init':
                        this.init(cmd.options);
                        break;
                    case 'setCandles':
                        this.setCandles(cmd.data);
                        break;
                    case 'updateCandle':
                        this.updateCandle(cmd.candle);
                        break;
                    case 'setLine':
                        this.setLine(cmd.id, cmd.data, cmd.options || {});
                        break;
                    case 'setForecast':
                        this.setForecast(cmd.midData, cmd.upperData, cmd.lowerData, cmd.options || {});
                        break;
                    case 'setForecastCandles':
                        this.setForecastCandles(cmd.data);
                        break;
                    case 'setMarkers':
                        this.setMarkers(cmd.seriesId, cmd.markers);
                        break;
                    case 'addPriceLine':
                        this.addPriceLine(cmd.seriesId, cmd.price, cmd.options || {});
                        break;
                    case 'removeSeries':
                        this.removeSeries(cmd.id);
                        break;
                    case 'clearIndicators':
                        this.clearIndicators();
                        break;
                    case 'setVisibleRange':
                        this.setVisibleRange(cmd.from, cmd.to);
                        break;
                    case 'scrollToRealTime':
                        this.scrollToRealTime();
                        break;
                    case 'fitContent':
                        this.fitContent();
                        break;
                    case 'setRSI':
                        this.setRSI(cmd.data);
                        break;
                    case 'setMACD':
                        this.setMACD(cmd.line, cmd.signal, cmd.histogram);
                        break;
                    case 'setStochastic':
                        this.setStochastic(cmd.kData, cmd.dData);
                        break;
                    case 'setKDJ':
                        this.setKDJ(cmd.kData, cmd.dData, cmd.jData);
                        break;
                    case 'setADX':
                        this.setADX(cmd.adxData, cmd.plusDI, cmd.minusDI);
                        break;
                    case 'setATR':
                        this.setATR(cmd.data);
                        break;
                    case 'setVolume':
                        this.setVolume(cmd.data);
                        break;
                    case 'setSuperTrend':
                        this.setSuperTrend(cmd.data, cmd.trendData, cmd.strengthData);
                        break;
                    case 'setPolynomialSR':
                        this.setPolynomialSR(cmd.resistance, cmd.support);
                        break;
                    case 'setPivotLevels':
                        this.setPivotLevels(cmd.levels);
                        break;
                    case 'setLogisticSR':
                        this.setLogisticSR(cmd.levels);
                        break;
                    case 'hidePanel':
                        this.hidePanel(cmd.panel);
                        break;
                    case 'toggleHeikinAshi':
                        this.toggleHeikinAshi(cmd.enabled);
                        break;
                    case 'setVolumeProfile':
                        this.setVolumeProfile(cmd.data);
                        break;
                    case 'updateLiveBar':
                        this.updateLiveBar(cmd.bar, cmd.duration);
                        break;
                    case 'removeVolumeProfile':
                        this.removeVolumeProfile();
                        break;
                    case 'removePriceLines':
                        this.removePriceLines(cmd.category);
                        break;
                    case 'clearAll':
                        this.clearAll();
                        break;
                    default:
                        console.warn('[ChartJS] Unknown command type:', cmd.type);
                }
            } catch (err) {
                console.error('[ChartJS] Command error:', cmd.type, err);
                sendToSwift('jsError', {
                    message: err.message,
                    type: cmd.type,
                    stack: err.stack
                });
            }
        },

        /**
         * Set Polynomial Regression S&R lines
         */
        setPolynomialSR: function(resistance, support) {
            if (resistance && resistance.length > 0) {
                this.setLine('poly-res', resistance, {
                    color: '#FF5252',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    name: 'Poly Res'
                });
            }
            if (support && support.length > 0) {
                this.setLine('poly-sup', support, {
                    color: '#4CAF50',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    name: 'Poly Sup'
                });
            }
            console.log('[ChartJS] Polynomial SR set');
        },

        /**
         * Set Pivot Levels as price lines
         */
        setPivotLevels: function(levels) {
            levels.forEach(level => {
                this.addPriceLine('candles', level.price, {
                    color: level.color,
                    lineWidth: level.lineWidth || 1,
                    lineStyle: level.lineStyle || LightweightCharts.LineStyle.Dashed,
                    title: level.title,
                    showLabel: true,
                    category: 'pivots'
                });
            });
            console.log('[ChartJS] Pivot levels set:', levels.length);
        },

        /**
         * Set Logistic Regression S&R levels as price lines
         */
        setLogisticSR: function(levels) {
            levels.forEach(level => {
                this.addPriceLine('candles', level.price, {
                    color: level.color,
                    lineWidth: level.lineWidth || 2,
                    lineStyle: level.lineStyle || LightweightCharts.LineStyle.Solid,
                    title: level.title,
                    showLabel: true,
                    category: 'logistic'
                });
            });
            console.log('[ChartJS] Logistic SR set:', levels.length);
        },
        
        /**
         * Clear all series, price lines, and sub-panels
         */
        clearAll: function() {
            try {
                // Remove all series
                Object.keys(state.series).forEach(id => {
                    try {
                        if (state.series[id] && state.chart) state.chart.removeSeries(state.series[id]);
                    } catch (e) {}
                });
                state.series = {};
                // Clear price lines
                this.clearPriceLines();
                // Reset cached bars
                state.originalBars = [];
                state.heikinAshiBars = [];
                // Hide sub-panels
                Object.keys(state.subPanels).forEach(name => hideSubPanel(name));
                console.log('[ChartJS] Cleared all');
            } catch (e) {
                console.warn('[ChartJS] clearAll failed', e);
            }
        }
    };

    // Initialize chart when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        // Auto-initialize with default options
        window.chartApi.init();

        // Signal to Swift that we're ready
        sendToSwift('ready');
        console.log('[ChartJS] Ready signal sent to Swift');
    });

})();
