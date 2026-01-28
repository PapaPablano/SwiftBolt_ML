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
        subCharts: {},      // Sub-panel charts for oscillators
        subSeries: {},      // Series within sub-panels
        priceLines: [],     // Track added price lines for cleanup
        lastCrosshairData: null,
        theme: 'dark',
        isReady: false,
        useHeikinAshi: false,
        originalBars: [],   // Store original OHLC data
        heikinAshiBars: [],  // Store transformed HA data
        indicatorConfig: null,
        hasFitContentOnce: false
    };

    const getSourceBars = () => {
        return (state.useHeikinAshi && state.heikinAshiBars && state.heikinAshiBars.length > 0)
            ? state.heikinAshiBars
            : state.originalBars;
    };

    const rma = (data, period) => {
        if (!data || period <= 0 || data.length < period) {
            return new Array(data ? data.length : 0).fill(null);
        }

        const out = new Array(data.length).fill(null);
        let sum = 0;
        for (let i = 0; i < period; i++) sum += data[i];
        let prev = sum / period;
        out[period - 1] = prev;

        for (let i = period; i < data.length; i++) {
            prev = (prev * (period - 1) + data[i]) / period;
            out[i] = prev;
        }
        return out;
    };

    const ema = (data, period) => {
        if (!data || period <= 0 || data.length < period) {
            return new Array(data ? data.length : 0).fill(null);
        }
        const out = new Array(data.length).fill(null);
        const k = 2 / (period + 1);
        let sum = 0;
        for (let i = 0; i < period; i++) sum += data[i];
        let prev = sum / period;
        out[period - 1] = prev;
        for (let i = period; i < data.length; i++) {
            prev = (data[i] - prev) * k + prev;
            out[i] = prev;
        }
        return out;
    };

    const computeTR = (bars) => {
        const tr = new Array(bars.length);
        for (let i = 0; i < bars.length; i++) {
            if (i === 0) {
                tr[i] = bars[i].high - bars[i].low;
            } else {
                const prevClose = bars[i - 1].close;
                tr[i] = Math.max(
                    bars[i].high - bars[i].low,
                    Math.abs(bars[i].high - prevClose),
                    Math.abs(bars[i].low - prevClose)
                );
            }
        }
        return tr;
    };

    const computeATR = (bars, length = 14) => {
        if (!bars || bars.length === 0) return [];
        const tr = computeTR(bars);
        const atrRaw = rma(tr, length);
        return atrRaw.map(v => (v == null ? 0 : v));
    };

    const computeSuperTrend = (bars, period, multiplier) => {
        if (!bars || bars.length === 0) {
            return { st: [], trend: [], strength: [] };
        }
        const tr = computeTR(bars);
        const atr = rma(tr, period);

        const finalUpper = [];
        const finalLower = [];
        const trend = new Array(bars.length).fill(0);
        const st = new Array(bars.length).fill(null);

        for (let i = 0; i < bars.length; i++) {
            const hl2 = (bars[i].high + bars[i].low) / 2;
            const a = atr[i];
            if (a == null) {
                finalUpper.push(hl2);
                finalLower.push(hl2);
                continue;
            }
            const basicUpper = hl2 + multiplier * a;
            const basicLower = hl2 - multiplier * a;

            if (i === 0) {
                finalUpper.push(basicUpper);
                finalLower.push(basicLower);
                trend[i] = 1;
                st[i] = basicLower;
                continue;
            }

            const prevClose = bars[i - 1].close;
            const prevTrend = trend[i - 1];

            const prevFinalUpper = finalUpper[i - 1];
            const prevFinalLower = finalLower[i - 1];

            const newUpper = (basicUpper < prevFinalUpper || prevClose > prevFinalUpper) ? basicUpper : prevFinalUpper;
            const newLower = (basicLower > prevFinalLower || prevClose < prevFinalLower) ? basicLower : prevFinalLower;

            finalUpper.push(newUpper);
            finalLower.push(newLower);

            // TradingView-style trend flip uses previous final bands
            const close = bars[i].close;
            let curTrend = prevTrend;
            if (close > prevFinalUpper) {
                curTrend = 1;
            } else if (close < prevFinalLower) {
                curTrend = -1;
            } else if (curTrend === 0) {
                curTrend = 1;
            }
            trend[i] = curTrend;
            st[i] = curTrend === 1 ? newLower : newUpper;
        }

        const strength = new Array(bars.length).fill(null);
        for (let i = 0; i < bars.length; i++) {
            const a = atr[i];
            const v = st[i];
            if (a == null || v == null || a <= 0) continue;
            const dist = Math.abs(bars[i].close - v);
            strength[i] = Math.min(100, (dist / a) * 50);
        }

        return { st, trend, strength };
    };

    const computeSuperTrendAIClustering = (bars, length, minMult, maxMult, step, perfAlpha, fromCluster) => {
        if (!bars || bars.length === 0) {
            return { ts: [], os: [], perfIdx: [], perfAma: [], factor: [], upper: [], lower: [] };
        }

        // Build factor list
        const factors = [];
        if (step <= 0) step = 0.5;
        for (let f = minMult; f <= maxMult + 1e-9; f += step) {
            factors.push(+f.toFixed(10));
        }
        if (factors.length === 0) factors.push(3.0);

        const tr = computeTR(bars);
        const atr = rma(tr, length);

        // For each factor: track upper/lower/output/trend/perf
        const inst = factors.map((factor) => ({
            factor,
            upper: (bars[0].high + bars[0].low) / 2,
            lower: (bars[0].high + bars[0].low) / 2,
            output: null,
            trend: 0,
            perf: 0
        }));

        // Output arrays for selected cluster
        const ts = new Array(bars.length).fill(null);
        const os = new Array(bars.length).fill(0);
        const perfIdx = new Array(bars.length).fill(null);
        const perfAma = new Array(bars.length).fill(null);
        const selectedFactorArr = new Array(bars.length).fill(null);

        // Denominator: EMA(abs(close-close[1]), perfAlpha)
        const absDelta = new Array(bars.length).fill(null);
        for (let i = 1; i < bars.length; i++) {
            absDelta[i] = Math.abs(bars[i].close - bars[i - 1].close);
        }
        const den = ema(absDelta.map(v => v ?? 0), Math.max(2, Math.floor(perfAlpha)));

        const alphaEma = 2 / (perfAlpha + 1);
        const chooseClusterIndex = (fromClusterStr) => {
            const s = (fromClusterStr || 'Best').toLowerCase();
            if (s === 'average') return 1;
            if (s === 'worst') return 0;
            return 2;
        };
        const targetClusterIdx = chooseClusterIndex(fromCluster);

        // Helper: percentiles 25/50/75
        const percentile = (arr, p) => {
            if (!arr.length) return 0;
            const sorted = [...arr].sort((a, b) => a - b);
            const idx = (sorted.length - 1) * p;
            const lo = Math.floor(idx);
            const hi = Math.ceil(idx);
            if (lo === hi) return sorted[lo];
            const w = idx - lo;
            return sorted[lo] * (1 - w) + sorted[hi] * w;
        };

        // K-means 1D (k=3)
        const kmeans1d = (data, factorArray, maxIter) => {
            if (!data.length) return null;
            let c0 = percentile(data, 0.25);
            let c1 = percentile(data, 0.50);
            let c2 = percentile(data, 0.75);

            for (let iter = 0; iter < maxIter; iter++) {
                const perfClusters = [[], [], []];
                const factorClusters = [[], [], []];
                for (let i = 0; i < data.length; i++) {
                    const v = data[i];
                    const d0 = Math.abs(v - c0);
                    const d1 = Math.abs(v - c1);
                    const d2 = Math.abs(v - c2);
                    let idx = 0;
                    if (d1 < d0) idx = 1;
                    if (d2 < (idx === 0 ? d0 : d1)) idx = 2;
                    perfClusters[idx].push(v);
                    factorClusters[idx].push(factorArray[i]);
                }
                const nc0 = perfClusters[0].length ? perfClusters[0].reduce((a, b) => a + b, 0) / perfClusters[0].length : c0;
                const nc1 = perfClusters[1].length ? perfClusters[1].reduce((a, b) => a + b, 0) / perfClusters[1].length : c1;
                const nc2 = perfClusters[2].length ? perfClusters[2].reduce((a, b) => a + b, 0) / perfClusters[2].length : c2;
                if (nc0 === c0 && nc1 === c1 && nc2 === c2) {
                    return { centroids: [c0, c1, c2], perfClusters, factorClusters };
                }
                c0 = nc0; c1 = nc1; c2 = nc2;
            }
            // final
            return { centroids: [c0, c1, c2], perfClusters: [[], [], []], factorClusters: [[], [], []] };
        };

        let targetFactor = null;
        let lastPerfAma = null;
        let upper = (bars[0].high + bars[0].low) / 2;
        let lower = (bars[0].high + bars[0].low) / 2;
        let lastOs = 0;

        for (let i = 0; i < bars.length; i++) {
            const a = atr[i];
            if (a == null) continue;
            const hl2 = (bars[i].high + bars[i].low) / 2;
            const close = bars[i].close;
            const prevClose = i > 0 ? bars[i - 1].close : close;

            // Update each instance
            for (let k = 0; k < inst.length; k++) {
                const it = inst[k];
                const up = hl2 + a * it.factor;
                const dn = hl2 - a * it.factor;

                // trend update uses previous upper/lower
                it.trend = close > it.upper ? 1 : close < it.lower ? 0 : it.trend;

                it.upper = (i > 0 && prevClose < it.upper) ? Math.min(up, it.upper) : up;
                it.lower = (i > 0 && prevClose > it.lower) ? Math.max(dn, it.lower) : dn;

                const diff = i > 0 ? Math.sign(prevClose - (it.output ?? prevClose)) : 0;
                const dClose = i > 0 ? (close - prevClose) : 0;
                it.perf = it.perf + alphaEma * ((dClose * (diff || 0)) - it.perf);
                it.output = (it.trend === 1) ? it.lower : it.upper;
            }

            // Cluster performances and choose target factor
            const perfData = inst.map(x => x.perf);
            const facData = inst.map(x => x.factor);
            const clusters = kmeans1d(perfData, facData, Math.max(1, Math.floor(state.indicatorConfig?.superTrendAIMaxIterations || 1000)));
            if (clusters && clusters.factorClusters) {
                const targetFactors = clusters.factorClusters[targetClusterIdx];
                const targetPerfs = clusters.perfClusters[targetClusterIdx];
                if (targetFactors && targetFactors.length) {
                    targetFactor = targetFactors.reduce((a, b) => a + b, 0) / targetFactors.length;
                }
                const avgPerf = targetPerfs && targetPerfs.length ? (targetPerfs.reduce((a, b) => a + b, 0) / targetPerfs.length) : 0;
                const d = den[i];
                perfIdx[i] = (d != null && d > 0) ? (Math.max(avgPerf, 0) / d) : 0;
            }

            if (targetFactor == null || !isFinite(targetFactor)) {
                targetFactor = factors[Math.floor(factors.length / 2)] || 3.0;
            }
            selectedFactorArr[i] = targetFactor;

            // Compute trailing stop using target factor (os 0/1)
            const upT = hl2 + a * targetFactor;
            const dnT = hl2 - a * targetFactor;

            upper = (i > 0 && prevClose < upper) ? Math.min(upT, upper) : upT;
            lower = (i > 0 && prevClose > lower) ? Math.max(dnT, lower) : dnT;

            if (close > upper) lastOs = 1;
            else if (close < lower) lastOs = 0;
            os[i] = lastOs;
            ts[i] = lastOs ? lower : upper;

            // Adaptive MA: perf_ama += perf_idx * (ts - perf_ama)
            if (i === 0 || perfAma[i - 1] == null) {
                lastPerfAma = ts[i];
            } else {
                const piRaw = perfIdx[i] ?? 0;
                const pi = Math.max(0, Math.min(1, piRaw));
                lastPerfAma = lastPerfAma + pi * (ts[i] - lastPerfAma);
            }
            perfAma[i] = lastPerfAma;
        }

        return { ts, os, perfIdx, perfAma, factor: selectedFactorArr };
    };

    const computeRSI = (bars, period = 14) => {
        if (!bars || bars.length === 0) return [];
        const closes = bars.map(b => b.close);
        if (closes.length <= period) return new Array(closes.length).fill(null);

        const gains = [];
        const losses = [];
        for (let i = 1; i < closes.length; i++) {
            const change = closes[i] - closes[i - 1];
            gains.push(change > 0 ? change : 0);
            losses.push(change < 0 ? Math.abs(change) : 0);
        }

        const out = new Array(closes.length).fill(null);
        let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
        let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;

        const rs0 = avgLoss === 0 ? 100 : avgGain / avgLoss;
        out[period] = 100 - (100 / (1 + rs0));

        for (let i = period; i < gains.length; i++) {
            avgGain = (avgGain * (period - 1) + gains[i]) / period;
            avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
            const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
            out[i + 1] = 100 - (100 / (1 + rs));
        }
        return out;
    };

    const computeMACD = (bars, fast = 12, slow = 26, signal = 9) => {
        const closes = bars.map(b => b.close);
        const fastEma = ema(closes, fast);
        const slowEma = ema(closes, slow);
        const macd = closes.map((_, i) => (fastEma[i] != null && slowEma[i] != null) ? (fastEma[i] - slowEma[i]) : null);
        const macdVals = macd.filter(v => v != null);
        const sigEmaCompact = ema(macdVals, signal);

        const sigLine = new Array(closes.length).fill(null);
        let idx = 0;
        for (let i = 0; i < macd.length; i++) {
            if (macd[i] != null) {
                sigLine[i] = sigEmaCompact[idx] ?? null;
                idx++;
            }
        }

        const hist = macd.map((v, i) => (v != null && sigLine[i] != null) ? (v - sigLine[i]) : null);
        return { macd, signal: sigLine, histogram: hist };
    };

    const computeKDJ = (bars, period = 9) => {
        if (bars.length < period) {
            return {
                k: new Array(bars.length).fill(null),
                d: new Array(bars.length).fill(null),
                j: new Array(bars.length).fill(null)
            };
        }

        const k = new Array(bars.length).fill(null);
        const d = new Array(bars.length).fill(null);
        const j = new Array(bars.length).fill(null);

        let prevK = 50.0;
        let prevD = 50.0;

        for (let i = period - 1; i < bars.length; i++) {
            const window = bars.slice(i - period + 1, i + 1);
            const highestHigh = Math.max(...window.map(b => b.high));
            const lowestLow = Math.min(...window.map(b => b.low));
            const close = bars[i].close;
            const range = highestHigh - lowestLow;
            const rsv = range === 0 ? 50.0 : ((close - lowestLow) / range) * 100.0;

            const curK = (2 / 3) * prevK + (1 / 3) * rsv;
            const curD = (2 / 3) * prevD + (1 / 3) * curK;
            const curJ = 3 * curK - 2 * curD;

            k[i] = curK;
            d[i] = curD;
            j[i] = curJ;

            prevK = curK;
            prevD = curD;
        }

        return { k, d, j };
    };

    const detectMostRecentPivot = (bars, period) => {
        if (bars.length <= period * 2) return { high: null, low: null };
        let high = null;
        let low = null;
        for (let i = period; i < bars.length - period; i++) {
            const b = bars[i];

            let isHigh = true;
            for (let j = i - period; j < i; j++) {
                if (bars[j].high > b.high) { isHigh = false; break; }
            }
            if (isHigh) {
                for (let j = i + 1; j <= i + period; j++) {
                    if (bars[j].high > b.high) { isHigh = false; break; }
                }
            }
            if (isHigh) high = b.high;

            let isLow = true;
            for (let j = i - period; j < i; j++) {
                if (bars[j].low < b.low) { isLow = false; break; }
            }
            if (isLow) {
                for (let j = i + 1; j <= i + period; j++) {
                    if (bars[j].low < b.low) { isLow = false; break; }
                }
            }
            if (isLow) low = b.low;
        }
        return { high, low };
    };

    const computeAtrThreshold = (bars, period = 200, multiplier = 1.5) => {
        if (!bars || bars.length === 0) return 0;
        const trueRanges = new Array(bars.length).fill(0);
        for (let i = 0; i < bars.length; i++) {
            const bar = bars[i];
            if (i === 0) {
                trueRanges[i] = bar.high - bar.low;
            } else {
                const prev = bars[i - 1];
                const tr = Math.max(
                    bar.high - bar.low,
                    Math.abs(bar.high - prev.close),
                    Math.abs(bar.low - prev.close)
                );
                trueRanges[i] = tr;
            }
        }

        const window = Math.min(period, bars.length);
        if (window === 0) return 0;

        let atr = 0;
        for (let i = 0; i < window; i++) atr += trueRanges[i];
        atr /= window;

        for (let i = window; i < trueRanges.length; i++) {
            atr = ((atr * (window - 1)) + trueRanges[i]) / window;
        }

        return atr * multiplier;
    };

    const detectMostRecentPivotDetailed = (bars, period) => {
        if (!bars || bars.length <= period * 2) {
            return { high: null, highIndex: null, low: null, lowIndex: null };
        }

        let recentHigh = null;
        let recentHighIndex = null;
        let recentLow = null;
        let recentLowIndex = null;

        for (let i = period; i < bars.length - period; i++) {
            const bar = bars[i];

            let isHigh = true;
            for (let j = i - period; j < i; j++) {
                if (bars[j].high > bar.high) { isHigh = false; break; }
            }
            if (isHigh) {
                for (let j = i + 1; j <= i + period; j++) {
                    if (bars[j].high > bar.high) { isHigh = false; break; }
                }
            }
            if (isHigh) {
                recentHigh = bar.high;
                recentHighIndex = i;
            }

            let isLow = true;
            for (let j = i - period; j < i; j++) {
                if (bars[j].low < bar.low) { isLow = false; break; }
            }
            if (isLow) {
                for (let j = i + 1; j <= i + period; j++) {
                    if (bars[j].low < bar.low) { isLow = false; break; }
                }
            }
            if (isLow) {
                recentLow = bar.low;
                recentLowIndex = i;
            }
        }

        return { high: recentHigh, highIndex: recentHighIndex, low: recentLow, lowIndex: recentLowIndex };
    };

    const determinePivotStatus = (levelPrice, lastBar, atrThreshold) => {
        if (levelPrice == null || !lastBar) return 'inactive';
        if (levelPrice <= 0) return 'inactive';

        if (lastBar.low > levelPrice + atrThreshold) {
            return 'support';
        }
        if (lastBar.high < levelPrice - atrThreshold) {
            return 'resistance';
        }
        return 'active';
    };

    const pivotConfigs = [
        { length: 5, lineWidth: 1, lineStyle: 2 },
        { length: 25, lineWidth: 2, lineStyle: 0 },
        { length: 50, lineWidth: 3, lineStyle: 0 },
        { length: 100, lineWidth: 4, lineStyle: 0 }
    ];

    const computePivotLevels = (bars) => {
        if (!bars || bars.length < 10) return [];

        const atrThreshold = computeAtrThreshold(bars, 200, 1.5);
        const lastBar = bars[bars.length - 1];
        const levels = [];

        for (const cfg of pivotConfigs) {
            const piv = detectMostRecentPivotDetailed(bars, cfg.length);
            if (piv.high != null) {
                const status = determinePivotStatus(piv.high, lastBar, atrThreshold);
                const color = status === 'support' ? colors.pivotSupport
                    : status === 'resistance' ? colors.pivotResistance
                    : colors.pivotActive;
                const title = status === 'support' ? `P${cfg.length} Sup`
                    : status === 'resistance' ? `P${cfg.length} Res`
                    : `P${cfg.length}`;

                levels.push({
                    price: piv.high,
                    color,
                    title,
                    lineWidth: cfg.lineWidth,
                    lineStyle: cfg.lineStyle,
                    category: 'pivot'
                });
            }

            if (piv.low != null) {
                const status = determinePivotStatus(piv.low, lastBar, atrThreshold);
                const color = status === 'support' ? colors.pivotSupport
                    : status === 'resistance' ? colors.pivotResistance
                    : colors.pivotActive;
                const title = status === 'support' ? `P${cfg.length} Sup`
                    : status === 'resistance' ? `P${cfg.length} Res`
                    : `P${cfg.length}`;

                levels.push({
                    price: piv.low,
                    color,
                    title,
                    lineWidth: cfg.lineWidth,
                    lineStyle: cfg.lineStyle,
                    category: 'pivot'
                });
            }
        }

        return levels;
    };

    const detectPivots = (bars, left, right, type) => {
        if (!bars || bars.length === 0) return [];
        const pivots = [];
        for (let i = left; i < bars.length - right; i++) {
            let isPivot = true;
            if (type === 'high') {
                const price = bars[i].high;
                for (let j = i - left; j < i && isPivot; j++) {
                    if (bars[j].high > price) isPivot = false;
                }
                for (let j = i + 1; j <= i + right && isPivot; j++) {
                    if (bars[j].high > price) isPivot = false;
                }
                if (isPivot) pivots.push({ index: i, price });
            } else {
                const price = bars[i].low;
                for (let j = i - left; j < i && isPivot; j++) {
                    if (bars[j].low < price) isPivot = false;
                }
                for (let j = i + 1; j <= i + right && isPivot; j++) {
                    if (bars[j].low < price) isPivot = false;
                }
                if (isPivot) pivots.push({ index: i, price });
            }
        }
        return pivots;
    };

    const fitPolynomialNormalized = (xVals, yVals, degree) => {
        if (xVals.length !== yVals.length || xVals.length < 2) return null;
        const maxDegree = Math.min(degree, xVals.length - 1);
        const degrees = [];
        for (let d = 0; d <= maxDegree; d++) degrees.push(d);
        const xMin = Math.min(...xVals);
        const xMax = Math.max(...xVals);
        const range = xMax - xMin;
        const normalized = range > 0
            ? xVals.map(x => (x - xMin) / range)
            : xVals.map(() => 0.5);

        const rows = normalized.length;
        const cols = degrees.length;
        const matrix = Array.from({ length: rows }, () => new Array(cols).fill(0));
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                matrix[r][c] = Math.pow(normalized[r], degrees[c]);
            }
        }

        const ata = Array.from({ length: cols }, () => new Array(cols).fill(0));
        for (let i = 0; i < cols; i++) {
            for (let j = 0; j < cols; j++) {
                let sum = 0;
                for (let k = 0; k < rows; k++) {
                    sum += matrix[k][i] * matrix[k][j];
                }
                ata[i][j] = sum;
            }
        }

        const atb = new Array(cols).fill(0);
        for (let i = 0; i < cols; i++) {
            let sum = 0;
            for (let k = 0; k < rows; k++) {
                sum += matrix[k][i] * yVals[k];
            }
            atb[i] = sum;
        }

        const coeffs = gaussianSolve(ata, atb);
        if (!coeffs) return null;

        return { coeffs, xMin, xMax, range: range === 0 ? 1 : range };
    };

    const gaussianSolve = (a, b) => {
        const n = a.length;
        const matrix = a.map(row => row.slice());
        const rhs = b.slice();

        for (let i = 0; i < n; i++) {
            let maxRow = i;
            for (let k = i + 1; k < n; k++) {
                if (Math.abs(matrix[k][i]) > Math.abs(matrix[maxRow][i])) {
                    maxRow = k;
                }
            }
            if (Math.abs(matrix[maxRow][i]) < 1e-10) return null;
            if (maxRow !== i) {
                [matrix[i], matrix[maxRow]] = [matrix[maxRow], matrix[i]];
                [rhs[i], rhs[maxRow]] = [rhs[maxRow], rhs[i]];
            }

            for (let k = i + 1; k < n; k++) {
                const factor = matrix[k][i] / matrix[i][i];
                for (let j = i; j < n; j++) {
                    matrix[k][j] -= factor * matrix[i][j];
                }
                rhs[k] -= factor * rhs[i];
            }
        }

        const solution = new Array(n).fill(0);
        for (let i = n - 1; i >= 0; i--) {
            let sum = rhs[i];
            for (let j = i + 1; j < n; j++) {
                sum -= matrix[i][j] * solution[j];
            }
            solution[i] = sum / matrix[i][i];
        }
        return solution;
    };

    const polynomialPredict = (fit, x) => {
        if (!fit) return null;
        const normalized = fit.range === 0 ? 0.5 : (x - fit.xMin) / fit.range;
        let value = 0;
        for (let i = 0; i < fit.coeffs.length; i++) {
            value += fit.coeffs[i] * Math.pow(normalized, i);
        }
        return value;
    };

    const buildPolynomialSeries = (bars, fit, lastIndex, oldestIndex) => {
        if (!fit) return [];
        const start = Math.max(0, oldestIndex);
        const out = [];
        for (let idx = start; idx <= lastIndex; idx++) {
            const x = lastIndex - idx;
            const val = polynomialPredict(fit, x);
            if (val == null || !isFinite(val)) continue;
            out.push({ time: bars[idx].time, value: val });
        }
        return out;
    };

    const computePolynomialSR = (bars) => {
        if (!bars || bars.length < 30) return { resistance: [], support: [] };

        const lastIndex = bars.length - 1;
        const lookback = 150;
        const pivotLeft = 5;
        const pivotRight = 5;
        const extend = 0; // JS version only plots existing bars

        const highs = detectPivots(bars, pivotLeft, pivotRight, 'high')
            .filter(p => p.index >= Math.max(0, lastIndex - lookback));
        const lows = detectPivots(bars, pivotLeft, pivotRight, 'low')
            .filter(p => p.index >= Math.max(0, lastIndex - lookback));

        const makeSeries = (pivots) => {
            if (!pivots.length) return [];
            const xVals = pivots.map(p => lastIndex - p.index);
            const yVals = pivots.map(p => p.price);
            let degree = 1;
            if (pivots.length >= 4) degree = 3;
            else if (pivots.length >= 3) degree = 2;
            const fit = fitPolynomialNormalized(xVals, yVals, degree);
            if (!fit) return [];

            const oldestIdx = Math.min(...pivots.map(p => p.index));
            return buildPolynomialSeries(bars, fit, lastIndex + extend, oldestIdx);
        };

        return {
            resistance: makeSeries(highs),
            support: makeSeries(lows)
        };
    };

    const LOGISTIC_LEARNING_RATE = 0.008;

    const logisticSigmoid = (bias, rsiWeight, bodyWeight, x1, x2) => {
        const exponent = -(bias + rsiWeight * x1 + bodyWeight * x2);
        return 1 / (1 + Math.exp(exponent));
    };

    const logisticLoss = (y, prediction) => {
        const clipped = Math.max(0.0001, Math.min(0.9999, prediction));
        return -y * Math.log(clipped) - (1 - y) * Math.log(1 - clipped);
    };

    const logisticPredict = (isSupport, rsi, bodySize, levels, targetRespects) => {
        const sameType = levels.filter(level => level.isSupport === isSupport);
        if (!sameType.length) return 0;

        const baseBias = 1;
        let rsiWeight = 1;
        let bodyWeight = 1;
        let result = 0;

        for (const level of sameType) {
            const label = level.timesRespected >= targetRespects ? 1 : -1;
            const p = logisticSigmoid(baseBias, rsiWeight, bodyWeight, level.detectedRSI, level.detectedBodySize);
            const loss = logisticLoss(label, p);
            rsiWeight -= LOGISTIC_LEARNING_RATE * (p + loss) * level.detectedRSI;
            bodyWeight -= LOGISTIC_LEARNING_RATE * (p + loss) * level.detectedBodySize;
            result = logisticSigmoid(baseBias, rsiWeight, bodyWeight, rsi, bodySize);
        }

        return result;
    };

    const computeLogisticSR = (bars) => {
        if (!bars || bars.length < 40) return [];

        const settings = {
            pivotLength: 14,
            targetRespects: 3,
            probabilityThreshold: 0.7,
            hideFarLines: true,
            retestCooldown: 3,
            maxAtrMultiple: 7
        };

        const rsiValues = computeRSI(bars, settings.pivotLength).map(v => (v == null ? 50 : v));
        const bodySizes = bars.map(b => Math.abs(b.close - b.open));
        const atrValuesRaw = computeATR(bars, settings.pivotLength);
        const atrValues = atrValuesRaw.map(v => (v == null ? 0 : v));

        const levels = [];
        const detectedLevels = [];

        const updateExistingLevels = (currentBar, currentIndex) => {
            for (const level of levels) {
                if (level.endIndex != null) continue;
                if (currentIndex <= level.startIndex + settings.pivotLength) continue;

                if (level.isSupport) {
                    if (currentBar.low < level.level) {
                        if (currentBar.close > level.level) {
                            level.timesRespected += 1;
                            if (currentIndex > level.latestRetestIndex + settings.retestCooldown) {
                                level.latestRetestIndex = currentIndex;
                            }
                        } else {
                            level.endIndex = currentIndex;
                        }
                    }
                } else {
                    if (currentBar.high > level.level) {
                        if (currentBar.close < level.level) {
                            level.timesRespected += 1;
                            if (currentIndex > level.latestRetestIndex + settings.retestCooldown) {
                                level.latestRetestIndex = currentIndex;
                            }
                        } else {
                            level.endIndex = currentIndex;
                        }
                    }
                }
            }
        };

        const createLevel = (isSupport, levelPrice, pivotIndex) => {
            const rsi = rsiValues[pivotIndex] ?? 50;
            const body = bodySizes[pivotIndex] ?? 0;
            const atr = atrValues[pivotIndex] ?? 0;

            const rsiSigned = rsi > 50 ? 1 : -1;
            const bodySigned = atr > 0 && body > atr ? 1 : -1;

            const level = {
                isSupport,
                level: levelPrice,
                startIndex: pivotIndex,
                endIndex: null,
                timesRespected: 0,
                latestRetestIndex: pivotIndex,
                detectedRSI: rsiSigned,
                detectedBodySize: bodySigned,
                detectedByRegression: false,
                detectedPrediction: 0
            };

            levels.push(level);

            const prediction = logisticPredict(isSupport, rsiSigned, bodySigned, levels, settings.targetRespects);
            if (prediction >= settings.probabilityThreshold) {
                level.detectedByRegression = true;
                level.detectedPrediction = prediction;
                detectedLevels.push(level);
            }
        };

        const detectPivotAt = (pivotIndex) => {
            const bar = bars[pivotIndex];
            let isHigh = true;
            for (let offset = 1; offset <= settings.pivotLength && isHigh; offset++) {
                const leftIdx = pivotIndex - offset;
                const rightIdx = pivotIndex + offset;
                if (leftIdx >= 0 && bars[leftIdx].high > bar.high) isHigh = false;
                if (rightIdx < bars.length && bars[rightIdx].high > bar.high) isHigh = false;
            }
            if (isHigh) {
                createLevel(false, bar.high, pivotIndex);
            }

            let isLow = true;
            for (let offset = 1; offset <= settings.pivotLength && isLow; offset++) {
                const leftIdx = pivotIndex - offset;
                const rightIdx = pivotIndex + offset;
                if (leftIdx >= 0 && bars[leftIdx].low < bar.low) isLow = false;
                if (rightIdx < bars.length && bars[rightIdx].low < bar.low) isLow = false;
            }
            if (isLow) {
                createLevel(true, bar.low, pivotIndex);
            }
        };

        for (let currentIndex = settings.pivotLength * 2; currentIndex < bars.length; currentIndex++) {
            const currentBar = bars[currentIndex];
            updateExistingLevels(currentBar, currentIndex);

            const pivotIndex = currentIndex - settings.pivotLength;
            if (pivotIndex >= settings.pivotLength) {
                detectPivotAt(pivotIndex);
            }
        }

        const lastBar = bars[bars.length - 1];
        const lastAtr = atrValues[bars.length - 1] || atrValues[Math.max(0, atrValues.length - 1)] || 0;
        const maxDistance = settings.hideFarLines && lastAtr > 0 ? lastAtr * settings.maxAtrMultiple : Infinity;

        const output = detectedLevels
            .filter(level => level.detectedByRegression && level.endIndex == null)
            .filter(level => maxDistance === Infinity || Math.abs(lastBar.close - level.level) <= maxDistance)
            .map(level => ({
                price: level.level,
                color: level.isSupport ? colors.logisticSupport : colors.logisticResistance,
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                title: level.isSupport
                    ? `ML Sup ${Math.round(level.detectedPrediction * 100)}%`
                    : `ML Res ${Math.round(level.detectedPrediction * 100)}%`,
                category: 'logistic'
            }));

        return output;
    };

    const toLineSeries = (bars, values) => {
        const out = [];
        const n = Math.min(bars.length, values.length);
        for (let i = 0; i < n; i++) {
            const v = values[i];
            if (v == null) continue;
            out.push({ time: bars[i].time, value: v });
        }
        return out;
    };

    const toLineSeriesFilteredByMask = (bars, values, maskValues) => {
        const out = [];
        const n = Math.min(bars.length, values.length, maskValues.length);
        for (let i = 0; i < n; i++) {
            if (maskValues[i] == null) continue;
            const v = values[i];
            if (v == null) continue;
            out.push({ time: bars[i].time, value: v });
        }
        return out;
    };

    const toValueSeriesFilteredByMask = (bars, values, maskValues) => {
        const out = [];
        const n = Math.min(bars.length, values.length, maskValues.length);
        for (let i = 0; i < n; i++) {
            if (maskValues[i] == null) continue;
            out.push({ time: bars[i].time, value: values[i] });
        }
        return out;
    };

    const buildSuperTrendMarkers = (bars, trend, stValues, factor) => {
        const markers = [];
        const n = Math.min(bars.length, trend.length, stValues.length);
        let last = null;
        for (let i = 0; i < n; i++) {
            if (stValues[i] == null) continue;
            const t = trend[i];
            if (t === 0) continue;
            if (last === null) {
                last = t;
                continue;
            }
            if (t !== last) {
                const isBuy = t > last;
                const f = (typeof factor === 'number' && isFinite(factor)) ? factor : null;
                const anchorIndex = isBuy ? i : Math.min(i + 1, n - 1);
                const anchorBar = bars[anchorIndex] || bars[i];
                const label = (() => {
                    if (f == null) return isBuy ? 'BUY' : 'SELL';
                    if (isBuy) return `BUY ${f.toFixed(1)}x`;
                    return `S ${f.toFixed(0)}x`;
                })();
                markers.push({
                    time: anchorBar.time,
                    type: isBuy ? 'buy' : 'sell',
                    position: isBuy ? 'belowBar' : 'aboveBar',
                    color: isBuy ? colors.superTrendBull : colors.superTrendBear,
                    shape: isBuy ? 'arrowUp' : 'arrowDown',
                    text: label,
                    size: 1
                });
                last = t;
            }
        }
        return markers;
    };

    const recalcIndicators = () => {
        const cfg = state.indicatorConfig;
        if (!cfg) return;
        const bars = getSourceBars();
        if (!bars || bars.length === 0) return;

        if (cfg.showSuperTrend) {
            if (cfg.useSuperTrendAI) {
                const ai = computeSuperTrendAIClustering(
                    bars,
                    cfg.superTrendPeriod || 10,
                    cfg.superTrendAIFactorMin ?? 1.0,
                    cfg.superTrendAIFactorMax ?? 5.0,
                    cfg.superTrendAIFactorStep ?? 0.5,
                    cfg.superTrendAIPerfAlpha ?? 10.0,
                    cfg.superTrendAIFromCluster ?? 'Best'
                );

                const stData = toLineSeries(bars, ai.ts);
                const trendData = toValueSeriesFilteredByMask(bars, ai.os.map(v => (v ? 1 : -1)), ai.ts);
                const strengthData = toLineSeriesFilteredByMask(bars, ai.perfIdx.map(v => (v == null ? null : Math.min(1, Math.max(0, v)) * 100)), ai.ts);
                window.chartApi.setSuperTrend(stData, trendData, strengthData);

                if (cfg.showAdaptiveMA) {
                    const amaData = toLineSeries(bars, ai.perfAma);
                    window.chartApi.setLine('supertrend_ai_ama', amaData, {
                        color: 'rgba(77, 230, 128, 0.5)',
                        lineWidth: 2,
                        lineStyle: LightweightCharts.LineStyle.Solid,
                        name: 'ST AMA',
                        autoscaleInfoProvider: () => null
                    });
                } else {
                    window.chartApi.removeSeries('supertrend_ai_ama');
                }

                if (cfg.showSignalMarkers) {
                    const markers = [];
                    for (let i = 1; i < bars.length; i++) {
                        if (ai.ts[i] == null || ai.ts[i - 1] == null) continue;
                        if (ai.os[i] > ai.os[i - 1]) {
                            const p = Math.max(0, Math.min(1, ai.perfIdx[i] ?? 0));
                            markers.push({
                                time: bars[i].time,
                                type: 'buy',
                                position: 'belowBar',
                                color: colors.superTrendBull,
                                shape: 'arrowUp',
                                text: `${Math.floor(p * 10)}`,
                                size: 1
                            });
                        } else if (ai.os[i] < ai.os[i - 1]) {
                            const p = Math.max(0, Math.min(1, ai.perfIdx[i] ?? 0));
                            const anchorIndex = Math.min(i + 1, bars.length - 1);
                            markers.push({
                                time: bars[anchorIndex].time,
                                type: 'sell',
                                position: 'aboveBar',
                                color: colors.superTrendBear,
                                shape: 'arrowDown',
                                text: `${Math.floor(p * 10)}`,
                                size: 1
                            });
                        }
                    }
                    window.chartApi.setMarkers('supertrend', markers);
                } else {
                    window.chartApi.setMarkers('supertrend', []);
                }
            } else {
                const stRes = computeSuperTrend(bars, cfg.superTrendPeriod || 10, cfg.superTrendMultiplier || 3.0);
                // IMPORTANT: keep all SuperTrend-related arrays aligned by filtering on stRes.st
                const stData = toLineSeries(bars, stRes.st);
                const trendData = toValueSeriesFilteredByMask(bars, stRes.trend, stRes.st);
                const strengthData = toLineSeriesFilteredByMask(bars, stRes.strength, stRes.st);
                window.chartApi.setSuperTrend(stData, trendData, strengthData);

                const markers = buildSuperTrendMarkers(bars, stRes.trend, stRes.st, cfg.superTrendMultiplier || 3.0);
                window.chartApi.setMarkers('supertrend', markers);
                window.chartApi.removeSeries('supertrend_ai_ama');
            }
        } else {
            window.chartApi.removeSeries('supertrend');
            if (state.series.supertrend_segments) {
                state.series.supertrend_segments.forEach(s => state.chart.removeSeries(s));
                state.series.supertrend_segments = [];
            }

            if (state.series.supertrend) {
                try { state.chart.removeSeries(state.series.supertrend); } catch (e) {}
                delete state.series.supertrend;
            }

            window.chartApi.setMarkers('supertrend', []);
        }

        if (cfg.showRSI) {
            const rsiVals = computeRSI(bars, 14);
            const rsiData = toLineSeries(bars, rsiVals);
            window.chartApi.setRSI(rsiData);
        } else {
            window.chartApi.hidePanel('rsi');
        }

        if (cfg.showMACD) {
            const res = computeMACD(bars, 12, 26, 9);
            window.chartApi.setMACD(
                toLineSeries(bars, res.macd),
                toLineSeries(bars, res.signal),
                toLineSeries(bars, res.histogram)
            );
        } else {
            window.chartApi.hidePanel('macd');
        }

        if (cfg.showKDJ) {
            const kdj = computeKDJ(bars, 9);
            window.chartApi.setKDJ(
                toLineSeries(bars, kdj.k),
                toLineSeries(bars, kdj.d),
                toLineSeries(bars, kdj.j)
            );
        } else {
            window.chartApi.hidePanel('kdj');
        }

        if (cfg.showPivotLevels) {
            window.chartApi.removePriceLines('pivot');
            window.chartApi.setPivotLevels(computePivotLevels(bars));
        } else {
            window.chartApi.removePriceLines('pivot');
        }

        if (cfg.showPolynomialSR) {
            const poly = computePolynomialSR(bars);
            if (poly.resistance.length > 0) {
                window.chartApi.setLine('poly-res', poly.resistance, {
                    color: colors.polynomialResistance,
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    autoscaleInfoProvider: () => null
                });
            } else {
                window.chartApi.removeSeries('poly-res');
            }

            if (poly.support.length > 0) {
                window.chartApi.setLine('poly-sup', poly.support, {
                    color: colors.polynomialSupport,
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    autoscaleInfoProvider: () => null
                });
            } else {
                window.chartApi.removeSeries('poly-sup');
            }
        } else {
            window.chartApi.removeSeries('poly-res');
            window.chartApi.removeSeries('poly-sup');
        }

        if (cfg.showLogisticSR) {
            const logistic = computeLogisticSR(bars);
            window.chartApi.removePriceLines('logistic');
            window.chartApi.setLogisticSR(logistic);
        } else {
            window.chartApi.removePriceLines('logistic');
        }
    };

    let _indicatorKickToken = 0;
    const scheduleIndicatorRefresh = () => {
        const token = ++_indicatorKickToken;

        const run = () => {
            if (token !== _indicatorKickToken) return;
            try { recalcIndicators(); } catch (e) {}

            try {
                if (!state.chart) return;
                const container = document.getElementById('chart-container');
                if (container) {
                    const w = container.clientWidth;
                    const h = container.clientHeight;
                    if (w > 0 && h > 0) {
                        try { state.chart.resize(w, h); } catch (e) {}
                    }
                }
                const range = state.chart.timeScale().getVisibleRange();
                if (range) {
                    try { state.chart.timeScale().setVisibleRange(range); } catch (e) {}
                }
            } catch (e) {}
        };

        requestAnimationFrame(() => {
            run();
            requestAnimationFrame(() => {
                run();
            });
        });

        setTimeout(() => {
            run();
        }, 80);
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

        // Pivot Levels
        pivotSupport: '#1ED67D',
        pivotResistance: '#EB7C14',
        pivotActive: '#1B85FF',

        // Polynomial Support/Resistance
        polynomialSupport: '#16C784',
        polynomialResistance: '#FF6F61',

        // Logistic Regression Support/Resistance
        logisticSupport: '#089981',
        logisticResistance: '#F23645',

        // Volume
        volumeUp: '#26a69a80',    // Semi-transparent green
        volumeDown: '#ef535080',  // Semi-transparent red

        // Grid & text
        grid: '#2a2a2a',
        text: '#888888',
        crosshair: '#555555'
    };

    const toRgba = (hex, alpha = 1) => {
        const value = hex.replace('#', '');
        if (value.length !== 6) return hex;
        const intVal = parseInt(value, 16);
        const r = (intVal >> 16) & 255;
        const g = (intVal >> 8) & 255;
        const b = intVal & 255;
        const a = Math.max(0, Math.min(1, alpha));
        return `rgba(${r},${g},${b},${a})`;
    };

    const getCandleTimeRange = () => {
        const bars = (state.useHeikinAshi && state.heikinAshiBars && state.heikinAshiBars.length > 0)
            ? state.heikinAshiBars
            : state.originalBars;

        if (!bars || bars.length === 0) return null;

        let minTime = bars[0].time;
        let maxTime = bars[0].time;
        for (let i = 1; i < bars.length; i++) {
            const t = bars[i].time;
            if (t < minTime) minTime = t;
            if (t > maxTime) maxTime = t;
        }

        if (typeof minTime !== 'number' || typeof maxTime !== 'number') return null;
        return { from: minTime, to: maxTime };
    };

    const median = (arr) => {
        if (!arr || arr.length === 0) return null;
        const sorted = [...arr].sort((a, b) => a - b);
        const mid = Math.floor(sorted.length / 2);
        return sorted.length % 2 === 0
            ? (sorted[mid - 1] + sorted[mid]) / 2
            : sorted[mid];
    };

    const inferBarIntervalSeconds = (bars) => {
        if (!bars || bars.length < 3) return null;
        const diffs = [];
        for (let i = 1; i < bars.length; i++) {
            const d = bars[i].time - bars[i - 1].time;
            if (!isFinite(d) || d <= 0) continue;
            // Ignore large gaps (weekends/holidays) when inferring interval
            if (d > 60 * 60 * 12) continue;
            diffs.push(d);
        }
        return median(diffs);
    };

    const applyAutoTimeScaleOptions = (bars) => {
        if (!state.chart || !bars || bars.length < 2) return;

        const interval = inferBarIntervalSeconds(bars);
        // Defaults tuned for compressed (uniform) distribution
        let barSpacing = 20;
        let minBarSpacing = 5;
        let rightOffset = 20;

        if (interval != null) {
            if (interval <= 60) {
                barSpacing = 16;
                minBarSpacing = 4;
                rightOffset = 16;
            } else if (interval <= 60 * 5) {
                barSpacing = 17;
                minBarSpacing = 4;
                rightOffset = 16;
            } else if (interval <= 60 * 60) {
                barSpacing = 18;
                minBarSpacing = 5;
                rightOffset = 18;
            } else if (interval <= 60 * 60 * 4) {
                barSpacing = 19;
                minBarSpacing = 5;
                rightOffset = 18;
            } else if (interval <= 60 * 60 * 24) {
                barSpacing = 20;
                minBarSpacing = 5;
                rightOffset = 20;
            } else {
                barSpacing = 22;
                minBarSpacing = 6;
                rightOffset = 20;
            }
        }

        state.chart.applyOptions({
            timeScale: {
                rightOffset,
                barSpacing,
                minBarSpacing,
                uniformDistribution: true
            }
        });
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
            rightOffset: 10,
            barSpacing: 8,
            minBarSpacing: 2,
            fixLeftEdge: false,
            fixRightEdge: false,
            uniformDistribution: true  // Force equal spacing between bars (ignore time gaps)
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
                Object.values(state.subCharts).forEach(subChart => {
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

        if (state.subCharts[panelName]) {
            return state.subCharts[panelName];
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

        // IMPORTANT: sub-panels are collapsed via CSS height:0 (not display:none)
        // Set height before createChart so WKWebView has stable layout.
        container.style.height = `${config.height}px`;

        // Force reflow so width/height are measurable after toggling display
        // (WKWebView can report 0px width on the first frame otherwise)
        void container.offsetHeight;

        const wrapper = document.getElementById('charts-wrapper');
        const fallbackWidth = wrapper ? wrapper.clientWidth : (document.body ? document.body.clientWidth : window.innerWidth);
        const initialWidth = (container.clientWidth && container.clientWidth > 0) ? container.clientWidth : fallbackWidth;

        // Create chart with minimal options
        const subChart = LightweightCharts.createChart(container, {
            ...darkThemeOptions,
            width: initialWidth,
            height: config.height,
            rightPriceScale: {
                borderColor: '#333',
                scaleMargins: { top: panelName === 'volume' ? 0.05 : 0.1, bottom: panelName === 'volume' ? 0.05 : 0.1 },
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

        state.subCharts[panelName] = subChart;
        state.subSeries[panelName] = {};

        // Sync initial range
        if (state.chart) {
            const range = state.chart.timeScale().getVisibleRange();
            if (range) subChart.timeScale().setVisibleRange(range);
        }

        // Next-frame resize + range sync to avoid first-panel blank render
        const syncAndResize = () => {
            const w = (container.clientWidth && container.clientWidth > 0) ? container.clientWidth : initialWidth;
            try { subChart.resize(w, config.height); } catch (e) {}
            try {
                if (state.chart) {
                    const range = state.chart.timeScale().getVisibleRange();
                    if (range) subChart.timeScale().setVisibleRange(range);
                }
            } catch (e) {}
        };

        // Multi-frame resize is a known WKWebView/WebKit workaround for canvas charts.
        requestAnimationFrame(() => {
            syncAndResize();
            requestAnimationFrame(() => {
                syncAndResize();
                requestAnimationFrame(() => {
                    syncAndResize();
                });
            });
        });

        console.log('[ChartJS] Sub-panel created:', panelName);
        return subChart;
    }

    function kickSubPanelRender(panelName, chart) {
        if (!chart) return;
        const config = subPanelConfig[panelName];
        if (!config) return;
        const container = document.getElementById(config.id);
        if (!container) return;

        const run = () => {
            const w = container.clientWidth;
            const h = config.height;
            if (w > 0 && h > 0) {
                try { chart.resize(w, h); } catch (e) {}
            }
            try {
                if (state.chart) {
                    const range = state.chart.timeScale().getVisibleRange();
                    if (range) {
                        chart.timeScale().setVisibleRange(range);
                    } else {
                        chart.timeScale().fitContent();
                    }
                } else {
                    chart.timeScale().fitContent();
                }
            } catch (e) {}
        };

        // WebKit sometimes needs multiple frames to paint the canvas.
        requestAnimationFrame(() => {
            run();
            requestAnimationFrame(() => {
                run();
                requestAnimationFrame(() => {
                    run();
                });
            });
        });
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
            container.style.height = '0px';
        }

        // Remove chart
        if (state.subCharts[panelName]) {
            state.subCharts[panelName].remove();
            delete state.subCharts[panelName];
            delete state.subSeries[panelName];
        }
    }

    /**
     * Sync crosshair with sub-panels
     */
    function syncCrosshair(time) {
        Object.values(state.subCharts).forEach(subChart => {
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
            state.priceLines.push({ series: series, line: line, category: priceLineOptions.category });
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

            // Auto-tune time scale for the inferred timeframe (compressed gaps)
            if (!state.hasFitContentOnce) {
                applyAutoTimeScaleOptions(sortedData);
            }

            // Set the data
            state.series.candles.setData(displayData);

            console.log('[ChartJS] Candles set:', sortedData.length, 'bars, HA:', state.useHeikinAshi);

            scheduleIndicatorRefresh();

            // Only fit once per chart load so we don't reset user zoom during updates/lazy-load.
            if (!state.hasFitContentOnce) {
                try { state.chart.timeScale().fitContent(); } catch (e) {}
                state.hasFitContentOnce = true;
            }
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
            const displayCandle = state.useHeikinAshi ? calculateHeikinAshi(state.originalBars).slice(-1)[0] : candle;

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
                try { state.chart.removeSeries(series); } catch (e) {
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
            const bandColor = options.bandColor || toRgba(color, 0.2);

            const lowerMap = new Map(lowerData.map(p => [p.time, p.value]));
            const missingLower = upperData.filter(p => !lowerMap.has(p.time)).length;
            if (missingLower > 0) {
                console.warn(`[ChartJS] Forecast band missing lower points for ${missingLower} timestamps`);
            }
            const bandCandles = upperData.reduce((acc, p) => {
                const lower = lowerMap.get(p.time);
                if (lower === undefined) { return acc; }
                const top = Math.max(p.value, lower);
                const bottom = Math.min(p.value, lower);
                acc.push({
                    time: p.time,
                    open: top,
                    high: top,
                    low: bottom,
                    close: bottom
                });
                return acc;
            }, []);

            if (bandCandles.length > 0) {
                if (!state.series['forecast-band']) {
                    state.series['forecast-band'] = state.chart.addCandlestickSeries({
                        upColor: bandColor,
                        downColor: bandColor,
                        borderUpColor: 'transparent',
                        borderDownColor: 'transparent',
                        wickUpColor: 'transparent',
                        wickDownColor: 'transparent',
                        priceLineVisible: false,
                        lastValueVisible: false,
                        autoscaleInfoProvider: () => null
                    });
                }

                const sortedBand = bandCandles.sort((a, b) => a.time - b.time);
                state.series['forecast-band'].setData(sortedBand);
            } else {
                this.removeSeries('forecast-band');
            }

            // Mid line (main forecast)
            this.setLine('forecast-mid', midData, {
                color: color,
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                pointMarkersVisible: true,
                pointMarkersRadius: 3,
                name: 'Forecast',
                autoscaleInfoProvider: () => null
            });

            // Upper bound
            this.setLine('forecast-upper', upperData, {
                color: bandColor,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                autoscaleInfoProvider: () => null
            });

            // Lower bound
            this.setLine('forecast-lower', lowerData, {
                color: bandColor,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                autoscaleInfoProvider: () => null
            });

            console.log('[ChartJS] Forecast set');
        },

        /**
         * Set forecast as overlay candlestick series (intraday-specific)
         */
        setForecastCandles: function(data, direction) {
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
                    lastValueVisible: true,
                    autoscaleInfoProvider: () => null
                });
            }

            const sortedData = [...data].sort((a, b) => a.time - b.time);
            const forecastDirection = (direction || '').toLowerCase();
            const derivedDirection = sortedData.length
                ? (sortedData[sortedData.length - 1].close >= sortedData[0].close ? 'bullish' : 'bearish')
                : '';
            const resolvedDirection = forecastDirection || derivedDirection;
            const isBullish = resolvedDirection === 'bullish';
            const isBearish = resolvedDirection === 'bearish';

            const currentPrice = state.originalBars?.length
                ? state.originalBars[state.originalBars.length - 1].close
                : (sortedData.length ? sortedData[0].close : null);

            // Apply transparency based on trend direction + current price
            const styledData = sortedData.map(candle => {
                if (!Number.isFinite(currentPrice) || (!isBullish && !isBearish)) {
                    return candle;
                }

                const hide = isBullish
                    ? candle.low < currentPrice
                    : candle.high > currentPrice;

                if (!hide) {
                    return candle;
                }

                return {
                    ...candle,
                    color: 'rgba(0,0,0,0)',
                    borderColor: 'rgba(0,0,0,0)',
                    wickColor: 'rgba(0,0,0,0)'
                };
            });

            state.series.forecast_candles.setData(styledData);

            console.log('[ChartJS] Forecast candles set:', styledData.length);
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

            // Remove SuperTrend segments (stored as an array, not a single series)
            if (state.series.supertrend_segments && Array.isArray(state.series.supertrend_segments) && state.chart) {
                state.series.supertrend_segments.forEach(s => {
                    try { state.chart.removeSeries(s); } catch (e) {}
                });
                state.series.supertrend_segments = [];
            }

            // Remove hidden supertrend marker host series
            if (state.series.supertrend && state.chart) {
                try { state.chart.removeSeries(state.series.supertrend); } catch (e) {}
                delete state.series.supertrend;
            }

            // Remove all remaining indicator series (only remove actual series objects)
            Object.keys(state.series).forEach(id => {
                if (id === 'candles') return;
                if (id === 'supertrend_segments') return;
                if (id === 'supertrend') return;

                const s = state.series[id];
                // Defensive: skip non-series values
                if (!s || typeof s.setData !== 'function') {
                    return;
                }
                this.removeSeries(id);
            });

            // Clear markers associated with indicator host series
            try {
                if (state.series.candles) state.series.candles.setMarkers([]);
            } catch (e) {}
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

            kickSubPanelRender('rsi', chart);

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

            kickSubPanelRender('macd', chart);

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

            kickSubPanelRender('stochastic', chart);

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

            kickSubPanelRender('kdj', chart);

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

            kickSubPanelRender('adx', chart);

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

            kickSubPanelRender('atr', chart);

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

            kickSubPanelRender('volume', chart);

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
            if (state.series.supertrend_segments && Array.isArray(state.series.supertrend_segments)) {
                state.series.supertrend_segments.forEach(s => {
                    try { state.chart.removeSeries(s); } catch (e) {}
                });
            }
            state.series.supertrend_segments = [];

            // Remove previous hidden marker host series (otherwise these accumulate)
            if (state.series.supertrend) {
                try { state.chart.removeSeries(state.series.supertrend); } catch (e) {}
                delete state.series.supertrend;
            }

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
                const range = getCandleTimeRange();
                if (range) {
                    state.chart.timeScale().setVisibleRange(range);
                } else {
                    state.chart.timeScale().fitContent();
                }
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

            recalcIndicators();
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
            const displayBar = state.useHeikinAshi ? calculateHeikinAshi(state.originalBars).slice(-1)[0] : newBar;

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
                        this.setForecastCandles(cmd.data, cmd.direction);
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
                    case 'setIndicatorConfig':
                        this.setIndicatorConfig(cmd.config);
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
                    lineWidth: level.lineWidth,
                    lineStyle: level.lineStyle,
                    title: level.title,
                    category: 'pivot'
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
                    lineWidth: level.lineWidth,
                    lineStyle: level.lineStyle,
                    title: level.title,
                    category: 'logistic'
                });
            });
            console.log('[ChartJS] Logistic SR set:', levels.length);
        },

        /**
         * Export current JS-computed S/R payloads for validation
         */
        exportSRState: function() {
            const bars = getSourceBars();
            if (!bars || bars.length === 0) {
                console.warn('[ChartJS] exportSRState: no bars loaded');
                return { error: 'no-bars' };
            }

            const snapshot = {
                generatedAt: Date.now(),
                lastBarTime: bars[bars.length - 1].time,
                indicatorConfig: state.indicatorConfig
            };

            try {
                const poly = computePolynomialSR(bars);
                snapshot.polynomial = {
                    resistance: poly.resistance.map(pt => ({ time: pt.time, value: pt.value })),
                    support: poly.support.map(pt => ({ time: pt.time, value: pt.value }))
                };
            } catch (err) {
                console.error('[ChartJS] exportSRState polynomial failed', err);
                snapshot.polynomial = { error: err?.message ?? 'unknown' };
            }

            try {
                const logistic = computeLogisticSR(bars);
                snapshot.logistic = logistic.map(level => ({
                    price: level.price,
                    color: level.color,
                    lineWidth: level.lineWidth,
                    lineStyle: level.lineStyle,
                    title: level.title,
                    category: level.category
                }));
            } catch (err) {
                console.error('[ChartJS] exportSRState logistic failed', err);
                snapshot.logistic = { error: err?.message ?? 'unknown' };
            }

            try {
                const pivots = computePivotLevels(bars);
                snapshot.pivots = pivots.map(level => ({
                    price: level.price,
                    color: level.color,
                    lineWidth: level.lineWidth,
                    lineStyle: level.lineStyle,
                    title: level.title,
                    category: level.category
                }));
            } catch (err) {
                console.error('[ChartJS] exportSRState pivots failed', err);
                snapshot.pivots = { error: err?.message ?? 'unknown' };
            }

            console.log('[ChartJS] exportSRState snapshot', snapshot);
            return snapshot;
        },

        /**
         * Download the current SR snapshot as a JSON file
         */
        downloadSRState: function(filename = 'sr_snapshot.json') {
            const snapshot = this.exportSRState();
            if (!snapshot || snapshot.error) {
                console.warn('[ChartJS] downloadSRState: snapshot unavailable', snapshot?.error);
                return snapshot;
            }

            try {
                const json = JSON.stringify(snapshot, null, 2);
                const blob = new Blob([json], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
                console.log('[ChartJS] downloadSRState: saved', filename);
            } catch (err) {
                console.error('[ChartJS] downloadSRState failed', err);
            }

            return snapshot;
        },

        /**
         * Set indicator configuration
         */
        setIndicatorConfig: function(config) {
            state.indicatorConfig = config;
            scheduleIndicatorRefresh();
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
                state.hasFitContentOnce = false;
                // Hide sub-panels
                Object.keys(subPanelConfig).forEach(name => hideSubPanel(name));
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
