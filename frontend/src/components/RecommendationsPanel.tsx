/**
 * RecommendationsPanel
 * ====================
 * ML-driven trading recommendations dashboard.
 * Design direction: "Classified Intelligence Briefing"
 *
 * Displays a featured top pick with SVG conviction gauge, signal bars,
 * and a satellite grid of additional recommendations.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import './RecommendationsPanel.css';

// ── TYPES ────────────────────────────────────────────────────────────────────

export type SignalClass = 'rec-strong-buy' | 'rec-buy' | 'rec-hold' | 'rec-sell';
export type SignalLabel = 'STRONG BUY' | 'BUY' | 'HOLD' | 'SELL';
export type Horizon = '5D' | '10D' | '20D';
export type ModelDirection = 'bull' | 'flat' | 'bear';
export type BarDirection = 'bullish' | 'neutral' | 'bearish';

export interface SignalBreakdown {
  name: string;
  /** 0–1 */
  score: number;
  direction: BarDirection;
}

export interface FeaturedRecommendation {
  ticker: string;
  company: string;
  signal: SignalLabel;
  signalClass: SignalClass;
  /** Signal hex color, e.g. '#00FFAA' */
  color: string;
  /** 0–100 */
  confidence: number;
  change: string;
  changePositive: boolean;
  currentPrice: number;
  targetPrice: number;
  horizon: Horizon;
  /** percentage, can be negative */
  upside: number;
  signals: SignalBreakdown[];
}

export interface Recommendation {
  ticker: string;
  company: string;
  signal: SignalLabel;
  signalClass: SignalClass;
  /** 0–100 */
  confidence: number;
  currentPrice: number;
  targetPrice: number;
  horizon: Horizon;
  upside: number;
  change: string;
  changePositive: boolean;
}

export interface ModelData {
  name: string;
  /** 0–1 */
  score: number;
  /** 0–1, relative contribution weight */
  weight: number;
  direction: ModelDirection;
}

export interface RecommendationsPanelProps {
  featured?: FeaturedRecommendation;
  recommendations?: Recommendation[];
  models?: ModelData[];
}

// ── DEFAULT DATA ──────────────────────────────────────────────────────────────

const DEFAULT_FEATURED: FeaturedRecommendation = {
  ticker: 'NVDA',
  company: 'NVIDIA Corporation',
  signal: 'STRONG BUY',
  signalClass: 'rec-strong-buy',
  color: '#00FFAA',
  confidence: 94,
  change: '+2.34%',
  changePositive: true,
  currentPrice: 875.40,
  targetPrice: 1050.00,
  horizon: '20D',
  upside: 19.9,
  signals: [
    { name: 'LSTM Ensemble',  score: 0.96, direction: 'bullish' },
    { name: 'ARIMA-GARCH',   score: 0.89, direction: 'bullish' },
    { name: 'RSI Momentum',  score: 0.78, direction: 'bullish' },
    { name: 'Volume Profile',score: 0.82, direction: 'bullish' },
    { name: 'Support/Resist',score: 0.71, direction: 'neutral' },
  ],
};

const DEFAULT_RECS: Recommendation[] = [
  { ticker:'AAPL', company:'Apple Inc.',      signal:'BUY',        signalClass:'rec-buy',        confidence:78, currentPrice:189.30, targetPrice:215.00, horizon:'10D', upside:13.6,  change:'+0.87%', changePositive:true  },
  { ticker:'META', company:'Meta Platforms',  signal:'STRONG BUY', signalClass:'rec-strong-buy', confidence:88, currentPrice:485.20, targetPrice:560.00, horizon:'20D', upside:15.4,  change:'+1.92%', changePositive:true  },
  { ticker:'MSFT', company:'Microsoft Corp.', signal:'BUY',        signalClass:'rec-buy',        confidence:82, currentPrice:415.60, targetPrice:470.00, horizon:'20D', upside:13.1,  change:'+0.62%', changePositive:true  },
  { ticker:'TSLA', company:'Tesla Inc.',      signal:'HOLD',       signalClass:'rec-hold',       confidence:61, currentPrice:245.80, targetPrice:255.00, horizon:'5D',  upside:3.7,   change:'-0.44%', changePositive:false },
  { ticker:'AMZN', company:'Amazon.com',      signal:'BUY',        signalClass:'rec-buy',        confidence:75, currentPrice:192.40, targetPrice:218.00, horizon:'10D', upside:13.3,  change:'+1.15%', changePositive:true  },
  { ticker:'INTC', company:'Intel Corp.',     signal:'SELL',       signalClass:'rec-sell',       confidence:72, currentPrice:43.20,  targetPrice:37.00,  horizon:'10D', upside:-14.4, change:'-1.78%', changePositive:false },
];

const DEFAULT_MODELS: ModelData[] = [
  { name:'LSTM',        score:0.94, weight:0.35, direction:'bull' },
  { name:'ARIMA-GARCH', score:0.89, weight:0.28, direction:'bull' },
  { name:'XGBoost',     score:0.82, weight:0.20, direction:'bull' },
  { name:'TabPFN',      score:0.76, weight:0.12, direction:'bull' },
  { name:'Ensemble',    score:0.94, weight:1.00, direction:'bull' },
];

// ── ARC MATH ─────────────────────────────────────────────────────────────────

const ARC_CX = 43;
const ARC_CY = 43;
const ARC_R  = 34;
const ARC_START  = 225; // degrees clockwise from top (7-o'clock position)
const ARC_SWEEP  = 270; // total sweep in degrees
// Arc circumference for 270° of radius 34
const ARC_LEN = parseFloat((2 * Math.PI * ARC_R * (ARC_SWEEP / 360)).toFixed(2)); // ≈ 161.3

function polarXY(deg: number): { x: string; y: string } {
  const rad = (deg - 90) * (Math.PI / 180);
  return {
    x: (ARC_CX + ARC_R * Math.cos(rad)).toFixed(2),
    y: (ARC_CY + ARC_R * Math.sin(rad)).toFixed(2),
  };
}

function buildArcPath(startDeg: number, endDeg: number): string {
  const s = polarXY(startDeg);
  const e = polarXY(endDeg);
  const span = ((endDeg - startDeg) % 360 + 360) % 360;
  const largeArc = span > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${ARC_R} ${ARC_R} 0 ${largeArc} 1 ${e.x} ${e.y}`;
}

const TRACK_PATH = buildArcPath(ARC_START, ARC_START + ARC_SWEEP);

// ── HELPERS ───────────────────────────────────────────────────────────────────

function upsideClass(upside: number): string {
  if (upside > 12) return 'hi';
  if (upside > 0)  return 'mid';
  return 'neg';
}

function formatPrice(p: number): string {
  return p.toFixed(2);
}

function formatUpside(u: number): string {
  return `${u > 0 ? '+' : ''}${u.toFixed(1)}%`;
}

// ── SUBCOMPONENTS ─────────────────────────────────────────────────────────────

interface ConvictionGaugeProps {
  confidence: number;
  color: string;
  arcRef: React.RefObject<SVGPathElement>;
}

const ConvictionGauge: React.FC<ConvictionGaugeProps> = ({ confidence, color, arcRef }) => (
  <div className="rec-gauge-wrap">
    <svg viewBox="0 0 86 86" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <filter id="rp-arc-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <path className="rec-arc-track" d={TRACK_PATH} />
      <path
        ref={arcRef}
        className="rec-arc-fill"
        d={TRACK_PATH}
        stroke={color}
        strokeDasharray={ARC_LEN}
        strokeDashoffset={ARC_LEN}
        filter="url(#rp-arc-glow)"
      />
    </svg>
    <div className="rec-gauge-num" style={{ color }}>
      {confidence}<span className="rec-gauge-unit">%</span>
    </div>
  </div>
);

// ── MAIN COMPONENT ────────────────────────────────────────────────────────────

export function RecommendationsPanel({
  featured = DEFAULT_FEATURED,
  recommendations = DEFAULT_RECS,
  models = DEFAULT_MODELS,
}: RecommendationsPanelProps): React.ReactElement {
  const [time, setTime] = useState('--:--:-- EST');
  const arcRef = useRef<SVGPathElement>(null);
  const sigFillsRef = useRef<HTMLDivElement[]>([]);
  const confFillsRef = useRef<HTMLDivElement[]>([]);
  const modelFillsRef = useRef<HTMLDivElement[]>([]);

  // Live clock
  useEffect(() => {
    const tick = () => {
      const t = new Date().toLocaleTimeString('en-US', {
        timeZone: 'America/New_York',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      setTime(`${t} EST`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Animate arc
  useEffect(() => {
    const arc = arcRef.current;
    if (!arc) return;
    const targetOffset = parseFloat((ARC_LEN * (1 - featured.confidence / 100)).toFixed(2));
    const id = setTimeout(() => {
      arc.style.transition = 'stroke-dashoffset 1.7s cubic-bezier(.16,1,.3,1)';
      arc.style.strokeDashoffset = String(targetOffset);
    }, 280);
    return () => clearTimeout(id);
  }, [featured.confidence]);

  // Animate signal bars (featured)
  const registerSigFill = useCallback((i: number) => (el: HTMLDivElement | null) => {
    if (el) sigFillsRef.current[i] = el;
  }, []);

  // Animate confidence fills (grid cards)
  const registerConfFill = useCallback((i: number) => (el: HTMLDivElement | null) => {
    if (el) confFillsRef.current[i] = el;
  }, []);

  // Animate model bars
  const registerModelFill = useCallback((i: number) => (el: HTMLDivElement | null) => {
    if (el) modelFillsRef.current[i] = el;
  }, []);

  useEffect(() => {
    const id = setTimeout(() => {
      sigFillsRef.current.forEach((el, i) => {
        if (el) {
          el.style.transitionDelay = `${i * 0.06}s`;
          el.style.transform = `scaleX(${featured.signals[i]?.score ?? 0})`;
        }
      });
      confFillsRef.current.forEach((el, i) => {
        if (el) {
          el.style.transitionDelay = `${0.1 + i * 0.04}s`;
          el.style.transform = `scaleX(${(recommendations[i]?.confidence ?? 0) / 100})`;
        }
      });
      modelFillsRef.current.forEach((el, i) => {
        if (el) {
          el.style.transition = `transform 1.2s ${0.12 + i * 0.07}s cubic-bezier(.16,1,.3,1)`;
          el.style.transform = 'scaleY(1)';
        }
      });
    }, 120);
    return () => clearTimeout(id);
  }, [featured.signals, recommendations]);

  const dateStr = new Date().toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div className="rec-panel">
      {/* ── HEADER ── */}
      <header className="rec-header">
        <div className="rec-logo-group">
          <span className="rec-logo-name">SwiftBolt ML</span>
          <span className="rec-logo-section">Signal Intelligence</span>
        </div>
        <div className="rec-header-meta">
          <div className="rec-live-badge">
            <div className="rec-live-dot" />
            MARKET OPEN
          </div>
          <div className="rec-clock">{time}</div>
          <div className="rec-tag">LSTM · ARIMA-GARCH</div>
        </div>
      </header>

      {/* ── MAIN GRID ── */}
      <div className="rec-main-grid">

        {/* Featured Card */}
        <div className={`rec-featured ${featured.signalClass}`}>
          <div className="rec-feat-eyebrow">
            <span className="rec-feat-eyebrow-label">Top Signal · {dateStr}</span>
            <span className={`rec-feat-chg ${featured.changePositive ? 'pos' : 'neg'}`}>
              {featured.change}
            </span>
          </div>

          <div className="rec-feat-ticker">{featured.ticker}</div>
          <div className="rec-feat-company">{featured.company}</div>
          <div className={`rec-sig-badge ${featured.signalClass}`}>{featured.signal}</div>

          <div className="rec-conviction-section">
            <div className="rec-section-label">ML Conviction</div>
            <div className="rec-conviction-row">
              <ConvictionGauge
                confidence={featured.confidence}
                color={featured.color}
                arcRef={arcRef}
              />
              <div className="rec-sigs-list">
                {featured.signals.map((sig, i) => (
                  <div key={sig.name} className="rec-sig-row">
                    <span className="rec-sig-name">{sig.name}</span>
                    <div className="rec-sig-track">
                      <div
                        ref={registerSigFill(i)}
                        className={`rec-sig-fill ${sig.direction}`}
                      />
                    </div>
                    <span className="rec-sig-pct">{Math.round(sig.score * 100)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="rec-price-grid">
            <div className="rec-price-cell">
              <div className="rec-price-label">Current</div>
              <div className="rec-price-val">${formatPrice(featured.currentPrice)}</div>
            </div>
            <div className="rec-price-cell">
              <div className="rec-price-label">Target · {featured.horizon}</div>
              <div className="rec-price-val accent" style={{ color: featured.color }}>
                ${formatPrice(featured.targetPrice)}
              </div>
            </div>
            <div className="rec-price-cell">
              <div className="rec-price-label">Upside</div>
              <div className="rec-price-val up">{formatUpside(featured.upside)}</div>
            </div>
          </div>
        </div>

        {/* Recommendations Grid */}
        <div className="rec-cards-grid">
          {recommendations.map((rec, i) => (
            <div key={rec.ticker} className={`rec-card ${rec.signalClass}`}>
              <div className="rec-card-top">
                <div className="rec-card-ticker">{rec.ticker}</div>
                <div className={`rec-card-chg ${rec.changePositive ? 'pos' : 'neg'}`}>
                  {rec.change}
                </div>
              </div>

              <div className="rec-card-co">{rec.company}</div>

              <div className="rec-card-badge-row">
                <div className={`rec-mini-badge ${rec.signalClass}`}>{rec.signal}</div>
                <span className="rec-card-conf-label">
                  {rec.confidence}% · {rec.horizon}
                </span>
              </div>

              <div className="rec-conf-track">
                <div
                  ref={registerConfFill(i)}
                  className={`rec-conf-fill ${rec.signalClass}`}
                />
              </div>

              <div className="rec-card-prices">
                <div>
                  <div className="rec-card-cur">${formatPrice(rec.currentPrice)}</div>
                  <div className="rec-card-tgt">→ ${formatPrice(rec.targetPrice)}</div>
                </div>
                <div className={`rec-card-upside ${upsideClass(rec.upside)}`}>
                  {formatUpside(rec.upside)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── BOTTOM PANEL: MODEL ENSEMBLE ── */}
      <div className="rec-bottom-panel">
        <div className="rec-bottom-header">
          <div>
            <div className="rec-bottom-title">
              Model Ensemble · {featured.ticker} · {featured.horizon} Horizon
            </div>
            <div className="rec-bottom-sub">Weighted contribution to conviction score</div>
          </div>
          <div className="rec-tag">WALK-FORWARD VALIDATED</div>
        </div>

        <div className="rec-models-row">
          {models.map((model, i) => (
            <div
              key={model.name}
              className="rec-model-col"
              style={{ animation: `rp-fade-up .5s ${0.42 + i * 0.06}s cubic-bezier(.16,1,.3,1) both` }}
            >
              <div className="rec-model-head">
                <span className="rec-model-name">{model.name}</span>
                <span className="rec-model-score">{Math.round(model.score * 100)}%</span>
              </div>
              <div className="rec-model-track">
                <div
                  ref={registerModelFill(i)}
                  className="rec-model-fill"
                  style={{ height: `${model.weight * 100}%` }}
                />
              </div>
              <div className={`rec-model-dir ${model.direction}`}>
                {model.direction === 'bull' ? 'BULLISH' : model.direction === 'bear' ? 'BEARISH' : 'NEUTRAL'}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default RecommendationsPanel;
