/**
 * Enhanced Tooltip System for WebChart
 * Provides detailed information for main chart and all sub-panels
 */

(function() {
    'use strict';

    // Tooltip state
    const tooltipState = {
        activePanel: 'main',
        currentData: null,
        isVisible: false
    };

    /**
     * Format timestamp to readable date/time
     */
    function formatTimestamp(timestamp) {
        const date = new Date(timestamp * 1000);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * Format volume with K/M/B suffixes
     */
    function formatVolume(volume) {
        if (volume >= 1e9) return (volume / 1e9).toFixed(2) + 'B';
        if (volume >= 1e6) return (volume / 1e6).toFixed(2) + 'M';
        if (volume >= 1e3) return (volume / 1e3).toFixed(2) + 'K';
        return volume.toFixed(0);
    }

    /**
     * Build tooltip content for main chart panel
     */
    function buildMainTooltip(data) {
        const { time, open, high, low, close, volume, stLine, trend } = data;
        const change = close - open;
        const changePercent = ((change / open) * 100).toFixed(2);
        const colorClass = change >= 0 ? 'bullish' : 'bearish';
        const isHA = window.chartState?.useHeikinAshi || false;

        return `
            <div class="tooltip-header">
                <span class="tooltip-time">${formatTimestamp(time)}</span>
                ${isHA ? '<span class="tooltip-badge ha">HA</span>' : ''}
            </div>
            <div class="tooltip-ohlc">
                <div class="tooltip-row">
                    <span class="label">Open:</span>
                    <span class="value">$${open.toFixed(2)}</span>
                </div>
                <div class="tooltip-row">
                    <span class="label">High:</span>
                    <span class="value">$${high.toFixed(2)}</span>
                </div>
                <div class="tooltip-row">
                    <span class="label">Low:</span>
                    <span class="value">$${low.toFixed(2)}</span>
                </div>
                <div class="tooltip-row">
                    <span class="label">Close:</span>
                    <span class="value ${colorClass}">$${close.toFixed(2)}</span>
                </div>
            </div>
            <div class="tooltip-change ${colorClass}">
                ${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePercent}%)
            </div>
            ${volume ? `<div class="tooltip-volume">Vol: ${formatVolume(volume)}</div>` : ''}
            ${typeof stLine === 'number' ? `
                <div class="tooltip-row">
                    <span class="label">SuperTrend:</span>
                    <span class="value ${trend === 1 ? 'bullish' : 'bearish'}">$${stLine.toFixed(2)} (${trend === 1 ? 'Uptrend' : 'Downtrend'})</span>
                </div>
            ` : ''}
        `;
    }

    /**
     * Build tooltip content for RSI panel
     */
    function buildRSITooltip(rsiValue) {
        let status = 'Normal';
        let statusClass = 'neutral';
        
        if (rsiValue > 70) {
            status = 'Overbought';
            statusClass = 'bearish';
        } else if (rsiValue < 30) {
            status = 'Oversold';
            statusClass = 'bullish';
        }

        return `
            <div class="tooltip-indicator">
                <div class="tooltip-row">
                    <span class="label">RSI (14):</span>
                    <span class="value">${rsiValue.toFixed(2)}</span>
                </div>
                <div class="tooltip-status ${statusClass}">
                    ${status}
                </div>
            </div>
        `;
    }

    /**
     * Build tooltip content for MACD panel
     */
    function buildMACDTooltip(macdLine, signal, histogram) {
        const momentum = histogram > 0 ? 'Bullish' : 'Bearish';
        const momentumClass = histogram > 0 ? 'bullish' : 'bearish';

        return `
            <div class="tooltip-indicator">
                <div class="tooltip-row">
                    <span class="label">MACD:</span>
                    <span class="value">${macdLine.toFixed(3)}</span>
                </div>
                <div class="tooltip-row">
                    <span class="label">Signal:</span>
                    <span class="value">${signal.toFixed(3)}</span>
                </div>
                <div class="tooltip-row">
                    <span class="label">Histogram:</span>
                    <span class="value ${momentumClass}">${histogram.toFixed(3)}</span>
                </div>
                <div class="tooltip-status ${momentumClass}">
                    Momentum: ${momentum}
                </div>
            </div>
        `;
    }

    /**
     * Build tooltip content for Volume panel
     */
    function buildVolumeTooltip(volume, volumeMA) {
        const percentOfAvg = volumeMA ? ((volume / volumeMA) * 100).toFixed(0) : null;
        const volumeClass = percentOfAvg && percentOfAvg > 150 ? 'bullish' : 
                           percentOfAvg && percentOfAvg < 50 ? 'bearish' : 'neutral';

        return `
            <div class="tooltip-indicator">
                <div class="tooltip-row">
                    <span class="label">Volume:</span>
                    <span class="value">${formatVolume(volume)}</span>
                </div>
                ${volumeMA ? `
                    <div class="tooltip-row">
                        <span class="label">Avg Volume:</span>
                        <span class="value">${formatVolume(volumeMA)}</span>
                    </div>
                    <div class="tooltip-status ${volumeClass}">
                        ${percentOfAvg}% of average
                    </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Build tooltip content for SuperTrend panel
     */
    function buildSuperTrendTooltip(stLine, trend, aiFactor) {
        const trendText = trend === 1 ? 'Uptrend' : 'Downtrend';
        const trendClass = trend === 1 ? 'bullish' : 'bearish';
        const factorText = aiFactor ? `${aiFactor.toFixed(1)}x` : 'N/A';

        return `
            <div class="tooltip-indicator">
                <div class="tooltip-row">
                    <span class="label">SuperTrend:</span>
                    <span class="value">$${stLine.toFixed(2)}</span>
                </div>
                <div class="tooltip-row">
                    <span class="label">Trend:</span>
                    <span class="value ${trendClass}">${trendText}</span>
                </div>
                ${aiFactor ? `
                    <div class="tooltip-row">
                        <span class="label">AI Factor:</span>
                        <span class="value">${factorText}</span>
                    </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Build tooltip content for Stochastic panel
     */
    function buildStochasticTooltip(kValue, dValue) {
        let status = 'Normal';
        let statusClass = 'neutral';
        
        if (kValue > 80) {
            status = 'Overbought';
            statusClass = 'bearish';
        } else if (kValue < 20) {
            status = 'Oversold';
            statusClass = 'bullish';
        }

        const crossSignal = kValue > dValue ? 'K > D (Bullish)' : 'K < D (Bearish)';
        const crossClass = kValue > dValue ? 'bullish' : 'bearish';

        return `
            <div class="tooltip-indicator">
                <div class="tooltip-row">
                    <span class="label">%K:</span>
                    <span class="value">${kValue.toFixed(2)}</span>
                </div>
                <div class="tooltip-row">
                    <span class="label">%D:</span>
                    <span class="value">${dValue.toFixed(2)}</span>
                </div>
                <div class="tooltip-status ${statusClass}">
                    ${status}
                </div>
                <div class="tooltip-signal ${crossClass}">
                    ${crossSignal}
                </div>
            </div>
        `;
    }

    /**
     * Update tooltip content based on panel and data
     */
    function updateTooltipContent(panel, data) {
        const tooltip = document.getElementById('tooltip');
        if (!tooltip) return;

        let content = '';

        switch (panel) {
            case 'main':
                content = buildMainTooltip(data);
                break;
            case 'rsi':
                content = buildRSITooltip(data.rsi);
                break;
            case 'macd':
                content = buildMACDTooltip(data.macdLine, data.signal, data.histogram);
                break;
            case 'volume':
                content = buildVolumeTooltip(data.volume, data.volumeMA);
                break;
            case 'supertrend':
                content = buildSuperTrendTooltip(data.stLine, data.trend, data.aiFactor);
                break;
            case 'stochastic':
                content = buildStochasticTooltip(data.kValue, data.dValue);
                break;
            default:
                content = '<div class="tooltip-indicator">No data</div>';
        }

        tooltip.innerHTML = content;
    }

    /**
     * Show tooltip at position
     */
    function showTooltip(x, y) {
        const tooltip = document.getElementById('tooltip');
        if (!tooltip) return;

        tooltip.style.display = 'block';
        tooltip.style.left = `${x + 15}px`;
        tooltip.style.top = `${y + 15}px`;
        tooltipState.isVisible = true;
    }

    /**
     * Hide tooltip
     */
    function hideTooltip() {
        const tooltip = document.getElementById('tooltip');
        if (!tooltip) return;

        tooltip.style.display = 'none';
        tooltipState.isVisible = false;
    }

    // Export to global scope
    window.enhancedTooltip = {
        update: updateTooltipContent,
        show: showTooltip,
        hide: hideTooltip,
        setState: (panel, data) => {
            tooltipState.activePanel = panel;
            tooltipState.currentData = data;
        }
    };

    console.log('[EnhancedTooltip] Initialized');

})();
