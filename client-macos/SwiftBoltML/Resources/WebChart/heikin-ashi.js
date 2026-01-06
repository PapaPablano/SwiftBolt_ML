/**
 * Heikin-Ashi Candlestick Calculator
 * Transforms standard OHLC data to Heikin-Ashi format for cleaner trend visualization
 * 
 * HA Close = (Open + High + Low + Close) / 4
 * HA Open = (Prev HA Open + Prev HA Close) / 2
 * HA High = max(High, HA Open, HA Close)
 * HA Low = min(Low, HA Open, HA Close)
 */

/**
 * Calculate Heikin-Ashi candles from standard OHLC data
 * @param {Array} bars - Array of {time, open, high, low, close} objects
 * @returns {Array} Heikin-Ashi transformed candles
 */
function calculateHeikinAshi(bars) {
    if (!bars || bars.length === 0) return [];
    
    const haBars = [];
    let prevHaOpen = 0;
    let prevHaClose = 0;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        
        // HA Close = (O+H+L+C)/4
        const haClose = (bar.open + bar.high + bar.low + bar.close) / 4;
        
        // HA Open = (prev HA open + prev HA close) / 2
        // First bar: use regular open
        const haOpen = i === 0 
            ? (bar.open + bar.close) / 2 
            : (prevHaOpen + prevHaClose) / 2;
        
        // HA High = max(H, HA O, HA C)
        const haHigh = Math.max(bar.high, haOpen, haClose);
        
        // HA Low = min(L, HA O, HA C)
        const haLow = Math.min(bar.low, haOpen, haClose);
        
        haBars.push({
            time: bar.time,
            open: haOpen,
            high: haHigh,
            low: haLow,
            close: haClose,
        });
        
        prevHaOpen = haOpen;
        prevHaClose = haClose;
    }
    
    return haBars;
}

/**
 * Validate Heikin-Ashi candle (sanity checks)
 * @param {Object} bar - HA candle to validate
 * @returns {boolean} True if valid
 */
function validateHeikinAshi(bar) {
    return (
        bar.high >= Math.max(bar.open, bar.close) &&
        bar.low <= Math.min(bar.open, bar.close) &&
        bar.high > bar.low &&
        bar.open > 0 &&
        bar.close > 0
    );
}

/**
 * Get Heikin-Ashi trend signal
 * @param {Array} haBars - Recent HA candles (at least 3)
 * @returns {string} 'strong_bullish' | 'bullish' | 'neutral' | 'bearish' | 'strong_bearish'
 */
function getHeikinAshiTrend(haBars) {
    if (haBars.length < 3) return 'neutral';
    
    const recent = haBars.slice(-3);
    const allBullish = recent.every(bar => bar.close > bar.open);
    const allBearish = recent.every(bar => bar.close < bar.open);
    
    // Check for strong trends (no lower wicks for bullish, no upper wicks for bearish)
    const strongBullish = allBullish && recent.every(bar => 
        Math.abs(bar.low - Math.min(bar.open, bar.close)) < 0.01
    );
    const strongBearish = allBearish && recent.every(bar => 
        Math.abs(bar.high - Math.max(bar.open, bar.close)) < 0.01
    );
    
    if (strongBullish) return 'strong_bullish';
    if (strongBearish) return 'strong_bearish';
    if (allBullish) return 'bullish';
    if (allBearish) return 'bearish';
    return 'neutral';
}

// Export for use in chart.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        calculateHeikinAshi,
        validateHeikinAshi,
        getHeikinAshiTrend
    };
}
