// Strategy Builder Web App

const API_BASE = 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1';

// Indicator metadata with defaults and labels
const INDICATOR_DEFAULTS = {
  // SuperTrend AI (Your Library)
  supertrend_ai: { defaultValue: 1, defaultParams: { atr_length: 10, min_mult: 1.0, max_mult: 5.0 }, description: 'SuperTrend AI - Adaptive indicator with factor selection', label: 'Bullish (1) / Bearish (0)' },
  supertrend_trend: { defaultValue: 1, defaultParams: {}, description: 'SuperTrend Trend Direction', label: 'Bullish (1) / Bearish (0)' },
  supertrend_signal: { defaultValue: 1, defaultParams: {}, description: 'SuperTrend Signal', label: 'Buy (1) / Sell (-1) / Hold (0)' },
  supertrend_factor: { defaultValue: 3.0, defaultParams: {}, description: 'SuperTrend Adaptive Factor', label: 'Factor Value' },
  supertrend_strength: { defaultValue: 5, defaultParams: {}, description: 'SuperTrend Signal Strength', label: 'Strength (0-10)' },
  
  // Momentum
  rsi: { defaultValue: 30, defaultParams: { period: 14 }, description: 'Relative Strength Index', label: 'Oversold (<30) / Overbought (>70)' },
  stochastic: { defaultValue: 20, defaultParams: { k_period: 14, d_period: 3 }, description: 'Stochastic Oscillator', label: 'Oversold (<20) / Overbought (>80)' },
  stochastic_k: { defaultValue: 20, defaultParams: { period: 14 }, description: 'Fast %K Line', label: 'Oversold (<20) / Overbought (>80)' },
  stochastic_d: { defaultValue: 20, defaultParams: { period: 14 }, description: 'Slow %D Line', label: 'Oversold (<20) / Overbought (>80)' },
  kdj_k: { defaultValue: 20, defaultParams: { period: 9 }, description: 'K Line - KDJ Indicator', label: 'Oversold (<20) / Overbought (>80)' },
  kdj_d: { defaultValue: 20, defaultParams: { period: 9 }, description: 'D Line - KDJ Indicator', label: 'Oversold (<20) / Overbought (>80)' },
  kdj_j: { defaultValue: 0, defaultParams: { period: 9 }, description: 'J Line - KDJ Indicator', label: 'Oversold (<0) / Overbought (>100)' },
  williams_r: { defaultValue: -80, defaultParams: { period: 14 }, description: 'Williams %R', label: 'Oversold (<-80) / Overbought (>-20)' },
  cci: { defaultValue: -100, defaultParams: { period: 20 }, description: 'Commodity Channel Index', label: 'Oversold (<-100) / Overbought (>100)' },
  momentum: { defaultValue: 0, defaultParams: { period: 10 }, description: 'Momentum Indicator', label: 'Positive (Bullish) / Negative (Bearish)' },
  roc: { defaultValue: 0, defaultParams: { period: 12 }, description: 'Rate of Change', label: 'Positive (%) / Negative (%)' },
  mfi: { defaultValue: 20, defaultParams: { period: 14 }, description: 'Money Flow Index', label: 'Oversold (<20) / Overbought (>80)' },
  vroc: { defaultValue: 0, defaultParams: { period: 14 }, description: 'Volume Rate of Change', label: 'Positive (%) / Negative (%)' },
  
  // Trend
  macd: { defaultValue: 0, defaultParams: { fast: 12, slow: 26, signal: 9 }, description: 'MACD Line', label: 'Positive (Bullish) / Negative (Bearish)' },
  macd_signal: { defaultValue: 0, defaultParams: { fast: 12, slow: 26, signal: 9 }, description: 'MACD Signal Line', label: 'MACD vs Signal' },
  macd_hist: { defaultValue: 0, defaultParams: { fast: 12, slow: 26, signal: 9 }, description: 'MACD Histogram', label: 'Positive / Negative' },
  sma: { defaultValue: 0, defaultParams: { period: 20 }, description: 'Simple Moving Average', label: 'Price Value' },
  ema: { defaultValue: 0, defaultParams: { period: 20 }, description: 'Exponential Moving Average', label: 'Price Value' },
  adx: { defaultValue: 25, defaultParams: { period: 14 }, description: 'ADX - Trend Strength', label: 'Trending (>25) / Weak (<25)' },
  adx_di_plus: { defaultValue: 25, defaultParams: { period: 14 }, description: 'DI+ - Positive Directional', label: 'DI+ Value' },
  adx_di_minus: { defaultValue: 25, defaultParams: { period: 14 }, description: 'DI- - Negative Directional', label: 'DI- Value' },
  parabolic_sar: { defaultValue: 0, defaultParams: { acceleration: 0.02, maximum: 0.2 }, description: 'Parabolic SAR', label: 'Price Value' },
  zigzag: { defaultValue: 0, defaultParams: { threshold: 5 }, description: 'ZigZag Pivot Points', label: 'Pivot Level' },
  
  // Volatility
  bollinger: { defaultValue: 0, defaultParams: { period: 20, std_dev: 2 }, description: 'Bollinger Bands', label: 'Price vs Band' },
  atr: { defaultValue: 0, defaultParams: { period: 14 }, description: 'Average True Range', label: 'ATR Value' },
  bb_width: { defaultValue: 0, defaultParams: { period: 20, std_dev: 2 }, description: 'Bollinger Band Width', label: 'Band Width Value' },
  bb_percent: { defaultValue: 0, defaultParams: { period: 20, std_dev: 2 }, description: 'Bollinger %B', label: 'Below (0) / Above (1) / Middle (0.5)' },
  keltner_upper: { defaultValue: 0, defaultParams: { period: 20, multiplier: 2 }, description: 'Keltner Channel Upper', label: 'Price vs Upper Band' },
  keltner_lower: { defaultValue: 0, defaultParams: { period: 20, multiplier: 2 }, description: 'Keltner Channel Lower', label: 'Price vs Lower Band' },
  atr_percent: { defaultValue: 0, defaultParams: { period: 14 }, description: 'ATR as % of price', label: 'ATR % Value' },
  
  // Volume
  volume: { defaultValue: 1000000, defaultParams: { period: 20 }, description: 'Trading Volume', label: 'Volume Level' },
  volume_sma: { defaultValue: 1000000, defaultParams: { period: 20 }, description: 'Volume SMA', label: 'Volume SMA' },
  vwap: { defaultValue: 0, defaultParams: {}, description: 'Volume Weighted Average Price', label: 'VWAP Value' },
  obv: { defaultValue: 0, defaultParams: {}, description: 'On Balance Volume', label: 'OBV Value' },
  vwap_anchor: { defaultValue: 0, defaultParams: {}, description: 'VWAP (Session Anchored)', label: 'VWAP Value' },
  
  // Price
  price: { defaultValue: 100, defaultParams: {}, description: 'Current Price', label: 'Price Level' },
  price_above_sma: { defaultValue: 1, defaultParams: { period: 20 }, description: 'Price above SMA', label: 'Above (1) / Below (0)' },
  price_above_ema: { defaultValue: 1, defaultParams: { period: 20 }, description: 'Price above EMA', label: 'Above (1) / Below (0)' },
  high: { defaultValue: 0, defaultParams: {}, description: 'High Price', label: 'High Value' },
  low: { defaultValue: 0, defaultParams: {}, description: 'Low Price', label: 'Low Value' },
  close: { defaultValue: 0, defaultParams: {}, description: 'Close Price', label: 'Close Value' },
  open: { defaultValue: 0, defaultParams: {}, description: 'Open Price', label: 'Open Value' },
  
  // Divergence
  rsi_divergence: { defaultValue: 1, defaultParams: { period: 14 }, description: 'RSI Divergence Signal', label: 'Bullish (1) / Bearish (-1) / None (0)' },
  macd_divergence: { defaultValue: 1, defaultParams: { fast: 12, slow: 26 }, description: 'MACD Divergence Signal', label: 'Bullish (1) / Bearish (-1) / None (0)' },
  price_divergence: { defaultValue: 1, defaultParams: {}, description: 'Price Divergence vs Indicator', label: 'Bullish (1) / Bearish (-1) / None (0)' }
};

// State
let currentStrategy = null;
let strategies = [];
let pendingConditionType = null;
let pollInterval = null;
let strategyCanvas = null;

// DOM Elements
const elements = {
  strategyList: document.getElementById('strategy-list'),
  welcomePanel: document.getElementById('welcome-panel'),
  strategyEditor: document.getElementById('strategy-editor'),
  backtestPanel: document.getElementById('backtest-panel'),
  conditionModal: document.getElementById('condition-modal'),
  entryConditions: document.getElementById('entry-conditions'),
  exitConditions: document.getElementById('exit-conditions'),
  backtestStatus: document.getElementById('backtest-status'),
  backtestResults: document.getElementById('backtest-results'),
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  initStrategyCanvas();
  setDefaultDates();
  loadStrategies();
  loadBacktestHistory();
});

function initEventListeners() {
  document.getElementById('new-strategy-btn').addEventListener('click', createNewStrategy);
  document.getElementById('create-first-btn').addEventListener('click', createNewStrategy);
  document.getElementById('save-strategy-btn').addEventListener('click', saveStrategy);
  document.getElementById('delete-strategy-btn').addEventListener('click', deleteStrategy);
  document.getElementById('run-backtest-btn').addEventListener('click', runBacktest);
  document.getElementById('load-history-btn').addEventListener('click', () => {
    const jobId = document.getElementById('backtest-history').value;
    if (jobId) loadBacktestById(jobId);
  });
  
  document.querySelectorAll('.add-condition-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      pendingConditionType = btn.dataset.type;
      showModal();
    });
  });
  
  document.getElementById('cancel-condition-btn').addEventListener('click', hideModal);
  document.getElementById('add-condition-btn').addEventListener('click', addCondition);
  
  // Close modal on outside click
  elements.conditionModal.addEventListener('click', (e) => {
    if (e.target === elements.conditionModal) hideModal();
  });
  
  // Update default value when indicator changes
  document.getElementById('condition-indicator').addEventListener('change', (e) => {
    const indicator = e.target.value;
    const defaults = INDICATOR_DEFAULTS[indicator] || { defaultValue: 0, defaultParams: {}, label: 'Value' };
    document.getElementById('condition-value').value = defaults.defaultValue;
    document.getElementById('condition-params').value = JSON.stringify(defaults.defaultParams);
    document.getElementById('condition-value-label').textContent = defaults.label || 'Value';
  });
}

function setDefaultDates() {
  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
  
  document.getElementById('backtest-start').value = formatDate(thirtyDaysAgo);
  document.getElementById('backtest-end').value = formatDate(today);
}

function formatDate(date) {
  return date.toISOString().split('T')[0];
}

// API Functions
async function loadStrategies() {
  try {
    const response = await fetch(`${API_BASE}/strategies`, {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      // For demo, show empty state
      renderStrategyList([]);
      return;
    }
    
    const data = await response.json();
    strategies = data.strategies || [];
    renderStrategyList(strategies);
  } catch (error) {
    console.error('Failed to load strategies:', error);
    renderStrategyList([]);
  }
}

async function loadBacktestHistory() {
  try {
    const response = await fetch(`${API_BASE}/strategy-backtest?limit=20`, {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) return;
    
    const data = await response.json();
    const jobs = data.jobs || [];
    
    const select = document.getElementById('backtest-history');
    select.innerHTML = '<option value="">-- Select Previous Backtest --</option>';
    
    jobs.forEach(job => {
      const option = document.createElement('option');
      option.value = job.id;
      const date = new Date(job.created_at).toLocaleDateString();
      const status = job.status === 'completed' ? '✓' : job.status === 'failed' ? '✗' : '...';
      option.textContent = `${job.strategies?.name || 'Strategy'} - ${job.symbol} - ${date} ${status}`;
      select.appendChild(option);
    });
  } catch (error) {
    console.error('Failed to load backtest history:', error);
  }
}

async function loadBacktestById(jobId) {
  try {
    const response = await fetch(`${API_BASE}/strategy-backtest?id=${jobId}`, {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) return;
    
    const data = await response.json();
    if (data.job?.status === 'completed' && data.result) {
      elements.backtestResults.classList.remove('hidden');
      elements.backtestStatus.classList.add('hidden');
      renderBacktestResults(data.result);
    }
  } catch (error) {
    console.error('Failed to load backtest:', error);
  }
}

async function saveStrategy() {
  const name = document.getElementById('strategy-name').value.trim();
  if (!name) {
    alert('Please enter a strategy name');
    return;
  }
  
  const config = buildStrategyConfig();
  
  const payload = {
    name,
    description: document.getElementById('strategy-description').value,
    config
  };
  
  try {
    const url = currentStrategy?.id 
      ? `${API_BASE}/strategies?id=${currentStrategy.id}`
      : `${API_BASE}/strategies`;
    
    const method = currentStrategy?.id ? 'PUT' : 'POST';
    
    const response = await fetch(url, {
      method,
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    console.log('Save response status:', response.status);
    
    if (!response.ok) {
      const errText = await response.text();
      console.error('Save failed:', errText);
      alert('Failed to save strategy: ' + errText);
      return;
    }
    
    const data = await response.json();
    currentStrategy = data.strategy;
    loadStrategies();
    alert('Strategy saved!');
  } catch (error) {
    console.error('Save failed:', error);
    alert('Failed to save strategy');
  }
}

async function deleteStrategy() {
  if (!currentStrategy?.id) return;
  
  if (!confirm('Are you sure you want to delete this strategy?')) return;
  
  try {
    const response = await fetch(`${API_BASE}/strategies?id=${currentStrategy.id}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
    
    if (response.ok) {
      currentStrategy = null;
      showWelcome();
      loadStrategies();
    } else {
      alert('Failed to delete strategy');
    }
  } catch (error) {
    console.error('Delete failed:', error);
    alert('Failed to delete strategy');
  }
}

async function runBacktest() {
  if (!currentStrategy?.id) {
    alert('Please save the strategy first');
    return;
  }
  
  const symbol = document.getElementById('backtest-symbol').value;
  const startDate = document.getElementById('backtest-start').value;
  const endDate = document.getElementById('backtest-end').value;
  
  const params = {
    strategy_id: currentStrategy.id,
    symbol,
    start_date: startDate,
    end_date: endDate,
    parameters: {
      initial_capital: 10000,
      position_size: 100,
      stop_loss_pct: parseFloat(document.getElementById('param-stop-loss').value) || 2,
      take_profit_pct: parseFloat(document.getElementById('param-take-profit').value) || 4
    }
  };
  
  elements.backtestStatus.classList.remove('hidden');
  elements.backtestResults.classList.add('hidden');
  
  try {
    const response = await fetch(`${API_BASE}/strategy-backtest`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(params)
    });
    
    if (!response.ok) {
      alert('Failed to queue backtest');
      return;
    }
    
    const data = await response.json();
    const jobId = data.job?.id;
    
    if (jobId) {
      pollJobStatus(jobId);
    }
  } catch (error) {
    console.error('Backtest failed:', error);
    alert('Failed to run backtest');
    elements.backtestStatus.classList.add('hidden');
  }
}

async function pollJobStatus(jobId) {
  pollInterval = setInterval(async () => {
    try {
      const response = await fetch(`${API_BASE}/strategy-backtest?id=${jobId}`, {
        headers: getAuthHeaders()
      });
      
      if (!response.ok) return;
      
      const data = await response.json();
      const status = data.job?.status;
      
      if (status === 'completed') {
        clearInterval(pollInterval);
        elements.backtestStatus.classList.add('hidden');
        elements.backtestResults.classList.remove('hidden');
        renderBacktestResults(data.result);
      } else if (status === 'failed') {
        clearInterval(pollInterval);
        elements.backtestStatus.classList.add('hidden');
        alert('Backtest failed: ' + (data.job?.error_message || 'Unknown error'));
      }
    } catch (error) {
      console.error('Poll error:', error);
    }
  }, 2000);
  
  // Timeout after 2 minutes
  setTimeout(() => {
    if (pollInterval) {
      clearInterval(pollInterval);
      elements.backtestStatus.classList.add('hidden');
    }
  }, 120000);
}

function renderBacktestResults(result) {
  if (!result?.metrics) return;
  
  const m = result.metrics;
  const trades = result.trades || [];
  
  // Basic metrics
  document.getElementById('metric-trades').textContent = m.total_trades || 0;
  document.getElementById('metric-winrate').textContent = (m.win_rate || 0).toFixed(1) + '%';
  
  const returnEl = document.getElementById('metric-return');
  returnEl.textContent = (m.total_return_pct || 0).toFixed(2) + '%';
  returnEl.className = 'metric-value ' + ((m.total_return_pct || 0) >= 0 ? 'positive' : 'negative');
  
  const ddEl = document.getElementById('metric-drawdown');
  ddEl.textContent = (m.max_drawdown_pct || 0).toFixed(2) + '%';
  ddEl.className = 'metric-value negative';
  
  document.getElementById('metric-profit-factor').textContent = (m.profit_factor || 0).toFixed(2);
  document.getElementById('metric-avg-win').textContent = '$' + (m.avg_win || 0).toFixed(2);
  document.getElementById('metric-avg-loss').textContent = '$' + (Math.abs(m.avg_loss) || 0).toFixed(2);
  
  // Calculate additional metrics
  const winning = trades.filter(t => t.pnl > 0);
  const losing = trades.filter(t => t.pnl <= 0);
  const avgWin = winning.length ? winning.reduce((sum, t) => sum + t.pnl, 0) / winning.length : 0;
  const avgLoss = losing.length ? Math.abs(losing.reduce((sum, t) => sum + t.pnl, 0) / losing.length) : 0;
  const winRate = trades.length ? winning.length / trades.length : 0;
  const expectancy = (winRate * avgWin) - ((1 - winRate) * avgLoss);
  
  // Sharpe Ratio (simplified)
  const returns = [];
  let prevValue = result.equity_curve?.[0]?.value || 10000;
  result.equity_curve?.forEach(eq => {
    returns.push((eq.value - prevValue) / prevValue);
    prevValue = eq.value;
  });
  const avgReturn = returns.length ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
  const stdReturn = returns.length ? Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length) : 1;
  const sharpe = stdReturn ? (avgReturn / stdReturn) * Math.sqrt(252) : 0;
  
  // Sortino Ratio (downside deviation)
  const negReturns = returns.filter(r => r < 0);
  const downStd = negReturns.length ? Math.sqrt(negReturns.reduce((sum, r) => sum + r * r, 0) / negReturns.length) : 1;
  const sortino = downStd ? (avgReturn / downStd) * Math.sqrt(252) : 0;
  
  // Calmar Ratio (return / max drawdown)
  const calmar = Math.abs(m.max_drawdown_pct || 1) ? (m.total_return_pct || 0) / Math.abs(m.max_drawdown_pct || 1) : 0;
  
  // Recovery Factor
  const recovery = Math.abs(m.max_drawdown_pct || 1) ? (m.total_return_pct || 0) / Math.abs(m.max_drawdown_pct || 1) : 0;
  
  document.getElementById('metric-sharpe').textContent = sharpe.toFixed(2);
  document.getElementById('metric-sortino').textContent = sortino.toFixed(2);
  document.getElementById('metric-calmar').textContent = calmar.toFixed(2);
  document.getElementById('metric-expectancy').textContent = '$' + expectancy.toFixed(2);
  document.getElementById('metric-recovery').textContent = recovery.toFixed(2);
  
  // Render equity curve with drawdown
  if (result.equity_curve?.length) {
    renderEquityCurve(result.equity_curve);
    renderDrawdownCurve(result.equity_curve);
    renderWinLossChart(trades);
    renderDurationChart(trades);
    renderMonthlyChart(trades);
  }
  
  // Render trades table
  const tradesContainer = document.querySelector('.trades-list');
  tradesContainer.innerHTML = `
    <h3>Trade History (${trades.length} trades)</h3>
    <table id="trades-table">
      <thead>
        <tr>
          <th>Entry Date</th>
          <th>Exit Date</th>
          <th>Duration</th>
          <th>Entry Price</th>
          <th>Exit Price</th>
          <th>P&L</th>
          <th>P&L %</th>
        </tr>
      </thead>
      <tbody>
        ${trades.map(trade => {
          const pnlClass = trade.pnl >= 0 ? 'positive' : 'negative';
          const duration = getTradeDuration(trade.entry_date, trade.exit_date);
          return `
            <tr>
              <td>${trade.entry_date}</td>
              <td>${trade.exit_date}</td>
              <td class="${getDurationClass(duration)}">${duration}</td>
              <td>$${trade.entry_price.toFixed(2)}</td>
              <td>$${trade.exit_price.toFixed(2)}</td>
              <td class="${pnlClass}">$${trade.pnl.toFixed(2)}</td>
              <td class="${pnlClass}">${trade.pnl_pct.toFixed(2)}%</td>
            </tr>
          `;
        }).join('')}
      </tbody>
    </table>
  `;
}

function getTradeDuration(entryDate, exitDate) {
  const entry = new Date(entryDate);
  const exit = new Date(exitDate);
  const days = Math.ceil((exit - entry) / (1000 * 60 * 60 * 24));
  if (days === 1) return '1 day';
  if (days < 7) return `${days} days`;
  if (days < 30) return `${Math.floor(days / 7)}w`;
  return `${Math.floor(days / 30)}mo`;
}

function getDurationClass(duration) {
  if (duration.includes('day') && parseInt(duration) <= 3) return 'trade-duration-short';
  if (duration.includes('w') && parseInt(duration) <= 2) return 'trade-duration-medium';
  return 'trade-duration-long';
}

function renderEquityCurve(data) {
  const canvas = document.getElementById('equity-chart');
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  
  ctx.clearRect(0, 0, width, height);
  
  if (!data.length) return;
  
  const values = data.map(d => d.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;
  
  ctx.beginPath();
  ctx.strokeStyle = '#007aff';
  ctx.lineWidth = 2;
  
  data.forEach((d, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((d.value - minVal) / range) * height;
    
    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  
  ctx.stroke();
}

function renderDrawdownCurve(data) {
  // Drawdown is already visible in the equity curve below the zero line
  // This function calculates and can be used for overlay
}

function renderWinLossChart(trades) {
  const canvas = document.getElementById('winloss-chart');
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  
  ctx.clearRect(0, 0, width, height);
  
  if (!trades.length) return;
  
  const winning = trades.filter(t => t.pnl > 0).length;
  const losing = trades.length - winning;
  
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 2 - 10;
  
  // Draw pie chart
  const total = winning + losing;
  let startAngle = -Math.PI / 2;
  
  // Winning (green)
  if (winning > 0) {
    const winAngle = (winning / total) * 2 * Math.PI;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.arc(centerX, centerY, radius, startAngle, startAngle + winAngle);
    ctx.fillStyle = '#34c759';
    ctx.fill();
    startAngle += winAngle;
  }
  
  // Losing (red)
  if (losing > 0) {
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.arc(centerX, centerY, radius, startAngle, startAngle + 2 * Math.PI);
    ctx.fillStyle = '#ff3b30';
    ctx.fill();
  }
  
  // Center text
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 14px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(winning + '/' + losing, centerX, centerY);
}

function renderDurationChart(trades) {
  const canvas = document.getElementById('duration-chart');
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  
  ctx.clearRect(0, 0, width, height);
  
  if (!trades.length) return;
  
  // Categorize by duration
  let short = 0, medium = 0, long = 0;
  trades.forEach(t => {
    const days = Math.ceil((new Date(t.exit_date) - new Date(t.entry_date)) / (1000 * 60 * 60 * 24));
    if (days <= 3) short++;
    else if (days <= 14) medium++;
    else long++;
  });
  
  const maxVal = Math.max(short, medium, long, 1);
  const barWidth = width / 3 - 10;
  
  // Short
  ctx.fillStyle = '#34c759';
  ctx.fillRect(5, height - (short / maxVal) * (height - 20), barWidth, (short / maxVal) * (height - 20));
  // Medium
  ctx.fillStyle = '#007aff';
  ctx.fillRect(5 + barWidth + 5, height - (medium / maxVal) * (height - 20), barWidth, (medium / maxVal) * (height - 20));
  // Long
  ctx.fillStyle = '#ff3b30';
  ctx.fillRect(5 + (barWidth + 5) * 2, height - (long / maxVal) * (height - 20), barWidth, (long / maxVal) * (height - 20));
}

function renderMonthlyChart(trades) {
  const canvas = document.getElementById('monthly-chart');
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  
  ctx.clearRect(0, 0, width, height);
  
  if (!trades.length) return;
  
  // Group by month
  const monthly = {};
  trades.forEach(t => {
    const month = t.exit_date.substring(0, 7);
    monthly[month] = (monthly[month] || 0) + t.pnl;
  });
  
  const months = Object.keys(monthly).sort().slice(-6);
  if (!months.length) return;
  
  const values = months.map(m => monthly[m]);
  const maxVal = Math.max(...values.map(Math.abs), 1);
  const barWidth = width / months.length - 4;
  
  months.forEach((month, i) => {
    const val = monthly[month];
    const barHeight = (Math.abs(val) / maxVal) * (height - 20);
    const x = i * (barWidth + 4);
    const y = val >= 0 ? height - barHeight : height / 2;
    
    ctx.fillStyle = val >= 0 ? '#34c759' : '#ff3b30';
    ctx.fillRect(x, y, barWidth, barHeight);
  });
}

// UI Functions
function buildStrategyConfig() {
  return {
    entry_conditions: getConditionsFromUI('entry'),
    exit_conditions: getConditionsFromUI('exit'),
    filters: [],
    parameters: {
      position_size_pct: parseFloat(document.getElementById('param-position-size').value) || 10,
      stop_loss_pct: parseFloat(document.getElementById('param-stop-loss').value) || 2,
      take_profit_pct: parseFloat(document.getElementById('param-take-profit').value) || 4
    }
  };
}

function getConditionsFromUI(type) {
  const container = type === 'entry' ? elements.entryConditions : elements.exitConditions;
  const cards = container.querySelectorAll('.condition-card');
  
  return Array.from(cards).map(card => ({
    type: 'indicator',
    name: card.dataset.name,
    operator: card.dataset.operator,
    value: parseFloat(card.dataset.value),
    params: card.dataset.params ? JSON.parse(card.dataset.params) : {}
  }));
}

function renderConditions(container, conditions) {
  container.innerHTML = '';
  
  conditions.forEach((cond, index) => {
    const card = document.createElement('div');
    card.className = 'condition-card';
    card.dataset.name = cond.name;
    card.dataset.operator = cond.operator;
    card.dataset.value = cond.value;
    card.dataset.params = JSON.stringify(cond.params || {});
    
    card.innerHTML = `
      <div class="condition-info">
        <span class="condition-indicator">${cond.name.toUpperCase()}</span>
        <span class="condition-operator">${formatOperator(cond.operator)}</span>
        <span class="condition-value">${cond.value}</span>
      </div>
      <button class="condition-remove" data-index="${index}">&times;</button>
    `;
    
    card.querySelector('.condition-remove').addEventListener('click', () => {
      card.remove();
      updateStrategySummary();
      syncCanvasWithConditions();
    });
    
    container.appendChild(card);
  });
  
  updateStrategySummary();
  syncCanvasWithConditions();
}

function updateStrategySummary() {
  const entryConditions = getConditionsFromUI('entry');
  const exitConditions = getConditionsFromUI('exit');
  const summaryEl = document.getElementById('strategy-summary');
  
  if (!entryConditions.length && !exitConditions.length) {
    summaryEl.innerHTML = '<div class="summary-empty">No conditions defined yet</div>';
    return;
  }
  
  let html = '';
  
  if (entryConditions.length) {
    html += '<div class="summary-section">';
    html += '<div class="summary-section-title">Entry Conditions (Buy when ALL met)</div>';
    html += '<div class="summary-conditions">';
    entryConditions.forEach(c => {
      html += `<div class="summary-condition">${c.name.toUpperCase()} ${formatOperator(c.operator)} ${c.value}</div>`;
    });
    html += '</div></div>';
  }
  
  if (exitConditions.length) {
    html += '<div class="summary-section">';
    html += '<div class="summary-section-title">Exit Conditions (Sell when ANY met)</div>';
    html += '<div class="summary-conditions">';
    exitConditions.forEach(c => {
      html += `<div class="summary-condition exit">${c.name.toUpperCase()} ${formatOperator(c.operator)} ${c.value}</div>`;
    });
    html += '</div></div>';
  }
  
  html += '<div class="summary-section">';
  html += '<div class="summary-section-title">Parameters</div>';
  html += '<div class="summary-params">';
  html += `<div class="summary-param"><div class="summary-param-label">Position</div><div class="summary-param-value">${document.getElementById('param-position-size').value}%</div></div>`;
  html += `<div class="summary-param"><div class="summary-param-label">Stop Loss</div><div class="summary-param-value">${document.getElementById('param-stop-loss').value}%</div></div>`;
  html += `<div class="summary-param"><div class="summary-param-label">Take Profit</div><div class="summary-param-value">${document.getElementById('param-take-profit').value}%</div></div>`;
  html += '</div></div>';
  
  summaryEl.innerHTML = html;
}

function formatOperator(op) {
  const map = {
    'above': '>',
    'below': '<',
    'crosses_above': 'crosses above',
    'crosses_below': 'crosses below'
  };
  return map[op] || op;
}

function addCondition() {
  const indicator = document.getElementById('condition-indicator').value;
  const operator = document.getElementById('condition-operator').value;
  const value = parseFloat(document.getElementById('condition-value').value);
  const paramsStr = document.getElementById('condition-params').value;
  
  // Use defaults if not provided
  const defaults = INDICATOR_DEFAULTS[indicator] || { defaultValue: 0, defaultParams: {} };
  const finalValue = isNaN(value) ? defaults.defaultValue : value;
  const finalParams = paramsStr ? JSON.parse(paramsStr) : defaults.defaultParams;
  
  const condition = {
    type: 'indicator',
    name: indicator,
    operator,
    value: finalValue,
    params: finalParams
  };
  
  const container = pendingConditionType === 'entry' 
    ? elements.entryConditions 
    : elements.exitConditions;
  
  renderConditions(container, [...getConditionsFromUI(pendingConditionType), condition]);
  hideModal();
}

function showModal() {
  elements.conditionModal.classList.remove('hidden');
  
  // Reset to first indicator with its defaults
  const select = document.getElementById('condition-indicator');
  const firstIndicator = select.options[0]?.value;
  if (firstIndicator) {
    select.value = firstIndicator;
    const defaults = INDICATOR_DEFAULTS[firstIndicator] || { defaultValue: 0, defaultParams: {}, label: 'Value' };
    document.getElementById('condition-value').value = defaults.defaultValue;
    document.getElementById('condition-params').value = JSON.stringify(defaults.defaultParams);
    document.getElementById('condition-value-label').textContent = defaults.label || 'Value';
  }
}

function hideModal() {
  elements.conditionModal.classList.add('hidden');
}

function createNewStrategy() {
  currentStrategy = null;
  document.getElementById('strategy-name').value = '';
  document.getElementById('strategy-description').value = '';
  renderConditions(elements.entryConditions, []);
  renderConditions(elements.exitConditions, []);
  
  elements.welcomePanel.classList.add('hidden');
  elements.strategyEditor.classList.remove('hidden');
  elements.backtestPanel.classList.add('hidden');
}

function showWelcome() {
  elements.welcomePanel.classList.remove('hidden');
  elements.strategyEditor.classList.add('hidden');
  elements.backtestPanel.classList.add('hidden');
}

function showEditor(strategy) {
  currentStrategy = strategy;
  
  document.getElementById('strategy-name').value = strategy.name || '';
  document.getElementById('strategy-description').value = strategy.description || '';
  
  const config = strategy.config || {};
  renderConditions(elements.entryConditions, config.entry_conditions || []);
  renderConditions(elements.exitConditions, config.exit_conditions || []);
  
  if (config.parameters) {
    document.getElementById('param-position-size').value = config.parameters.position_size_pct || 10;
    document.getElementById('param-stop-loss').value = config.parameters.stop_loss_pct || 2;
    document.getElementById('param-take-profit').value = config.parameters.take_profit_pct || 4;
  }
  
  elements.welcomePanel.classList.add('hidden');
  elements.strategyEditor.classList.remove('hidden');
  elements.backtestPanel.classList.remove('hidden');
}

function renderStrategyList(list) {
  elements.strategyList.innerHTML = '';
  
  if (!list.length) {
    elements.strategyList.innerHTML = '<p class="empty-state">No strategies yet</p>';
    return;
  }
  
  list.forEach(strategy => {
    const item = document.createElement('div');
    item.className = 'strategy-item' + (currentStrategy?.id === strategy.id ? ' active' : '');
    item.innerHTML = `
      <div class="strategy-item-name">${strategy.name}</div>
      <div class="strategy-item-date">${formatDateStr(strategy.updated_at)}</div>
    `;
    
    item.addEventListener('click', () => {
      document.querySelectorAll('.strategy-item').forEach(el => el.classList.remove('active'));
      item.classList.add('active');
      showEditor(strategy);
    });
    
    elements.strategyList.appendChild(item);
  });
}

function formatDateStr(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString();
}

function getAuthHeaders() {
  // Demo mode - use anon key
  return {
    'apikey': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdHdpd2F2aWNrcyIsInJvbGUiOiJhbmlvbiIsImlhdCI6MTY0MjU0Njk5OSwiZXhwIjoxOTU4MTIyOTk5fQ.sN0z2oR6VupMzN-Y9z4Yz3p4Qp5FvQ0q5x6RzW3xX8M'
  };
}

function getToken() {
  // Check for token in URL (for testing) or localStorage
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('token') || localStorage.getItem('sb_token') || '';
}

// Canvas Node Editor Integration
function initStrategyCanvas() {
  const canvasEl = document.getElementById('strategy-canvas');
  if (!canvasEl) return;
  
  strategyCanvas = new NodeCanvas('strategy-canvas', {
    nodeWidth: 160,
    nodeHeight: 55,
    gridSize: 20
  });
  
  strategyCanvas.onNodeMove = function(node) {
    console.log('Node moved:', node.condition.name);
  };
  
  strategyCanvas.onNodeDoubleClick = function(node) {
    pendingConditionType = node.conditionType;
    const condition = node.condition;
    
    document.getElementById('condition-indicator').value = condition.name;
    document.getElementById('condition-operator').value = condition.operator;
    document.getElementById('condition-value').value = condition.value;
    document.getElementById('condition-params').value = JSON.stringify(condition.params || {});
    
    showModal();
  };
  
  strategyCanvas.onNodeRemove = function(node) {
    const conditionType = node.conditionType;
    const nodeId = node.id;
    
    const container = document.getElementById(`${conditionType}-conditions`);
    const cards = container.querySelectorAll('.condition-card');
    
    const index = parseInt(nodeId.split('_')[1]);
    if (!isNaN(index) && cards[index]) {
      cards[index].remove();
      updateStrategySummary();
      syncCanvasWithConditions();
    }
  };
}

function syncCanvasWithConditions() {
  if (!strategyCanvas) return;
  
  strategyCanvas.clearNodes();
  
  const entryConditions = getConditionsFromUI('entry').map((c, i) => ({
    ...c,
    id: `entry_${i}`,
    indicator: c.name
  }));
  
  const exitConditions = getConditionsFromUI('exit').map((c, i) => ({
    ...c,
    id: `exit_${i}`,
    indicator: c.name
  }));
  
  entryConditions.forEach((cond, i) => {
    strategyCanvas.addNode(cond, 'entry');
  });
  
  exitConditions.forEach((cond, i) => {
    strategyCanvas.addNode(cond, 'exit');
  });
  
  if (entryConditions.length || exitConditions.length) {
    strategyCanvas.autoLayout('entry');
    strategyCanvas.autoLayout('exit');
  }
}

function updateCanvasConditions(type, conditions) {
  if (!strategyCanvas) return;
  
  conditions.forEach((condition, index) => {
    const nodeData = {
      ...condition,
      id: `${type}_${index}`,
      indicator: condition.name
    };
    strategyCanvas.addNode(nodeData, type);
  });
}


