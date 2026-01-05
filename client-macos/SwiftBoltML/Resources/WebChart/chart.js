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
        lastCrosshairData: null,
        theme: 'dark',
        isReady: false
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

            if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
                tooltip.style.display = 'none';
                return;
            }

            // Get candle data
            const candleData = param.seriesData.get(state.series.candles);
            if (!candleData) {
                tooltip.style.display = 'none';
                return;
            }

            const { open, high, low, close } = candleData;
            const change = close - open;
            const changePercent = ((change / open) * 100).toFixed(2);
            const colorClass = change >= 0 ? 'bullish' : 'bearish';

            // Format tooltip
            tooltip.innerHTML = `
                <div>O: <span class="price">${open.toFixed(2)}</span></div>
                <div>H: <span class="price">${high.toFixed(2)}</span></div>
                <div>L: <span class="price">${low.toFixed(2)}</span></div>
                <div>C: <span class="price ${colorClass}">${close.toFixed(2)}</span></div>
                <div class="${colorClass}">${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePercent}%)</div>
            `;

            // Position tooltip
            const container = document.getElementById('chart-container');
            const containerRect = container.getBoundingClientRect();
            let left = param.point.x + 15;
            let top = param.point.y + 15;

            // Keep tooltip within bounds
            if (left + 150 > containerRect.width) {
                left = param.point.x - 160;
            }
            if (top + 100 > containerRect.height) {
                top = param.point.y - 110;
            }

            tooltip.style.left = `${left}px`;
            tooltip.style.top = `${top}px`;
            tooltip.style.display = 'block';

            // Send crosshair data to Swift
            sendToSwift('crosshair', {
                time: param.time,
                price: close,
                open, high, low, close
            });
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
         * Set candlestick data
         */
        setCandles: function(data) {
            if (!state.chart) {
                console.error('[ChartJS] Chart not initialized');
                return;
            }

            if (!state.series.candles) {
                state.series.candles = state.chart.addCandlestickSeries(candlestickOptions);
            }

            // Ensure data is sorted by time
            const sortedData = [...data].sort((a, b) => a.time - b.time);
            state.series.candles.setData(sortedData);

            // Fit content
            state.chart.timeScale().fitContent();

            console.log('[ChartJS] Candles set:', sortedData.length);
        },

        /**
         * Update candles incrementally
         */
        updateCandle: function(candle) {
            if (state.series.candles) {
                state.series.candles.update(candle);
            }
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
                title: options.title || ''
            };

            return series.createPriceLine(priceLineOptions);
        },

        /**
         * Remove a series
         */
        removeSeries: function(id) {
            const series = state.series[id];
            if (series && state.chart) {
                state.chart.removeSeries(series);
                delete state.series[id];

                // Remove legend item
                const legendItem = document.getElementById(`legend-${id}`);
                if (legendItem) legendItem.remove();

                console.log('[ChartJS] Series removed:', id);
            }
        },

        /**
         * Clear all series except candles
         */
        clearIndicators: function() {
            Object.keys(state.series).forEach(id => {
                if (id !== 'candles') {
                    this.removeSeries(id);
                }
            });
            console.log('[ChartJS] Indicators cleared');
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
         * Apply a command object (for batched updates from Swift)
         */
        apply: function(cmd) {
            if (!cmd || !cmd.type) {
                console.error('[ChartJS] Invalid command:', cmd);
                return;
            }

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
                default:
                    console.warn('[ChartJS] Unknown command type:', cmd.type);
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
