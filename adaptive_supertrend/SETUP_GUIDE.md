# AdaptiveSuperTrend Setup Guide

**Complete step-by-step setup for SwiftBolt_ML platform**

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Install Dependencies

```bash
cd /Users/ericpeterson/SwiftBolt_ML
pip install -r adaptive_supertrend/requirements.txt
```

### Step 2: Setup Environment Variables

Create `.env` in your SwiftBolt_ML root directory:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Alpaca API (optional, for live trading)
ALPACA_API_KEY=your-alpaca-key
ALPACA_API_SECRET=your-alpaca-secret
ALPACA_BASE_URL=https://api.alpaca.markets

# Polygon.io (optional, for alternative data)
POLYGON_API_KEY=your-polygon-key

# Logging
LOG_LEVEL=INFO
```

### Step 3: Setup Supabase Database

1. **Create Supabase Project** (if not already done)
   - Go to https://supabase.com
   - Create new project
   - Copy URL and service role key
   - Paste into `.env`

2. **Run SQL Setup Script**
   - Open Supabase dashboard
   - Go to SQL Editor
   - Create new query
   - Copy content from `supabase_setup.sql`
   - Execute
   - Verify tables created

### Step 4: Run Basic Test

```bash
cd /Users/ericpeterson/SwiftBolt_ML/adaptive_supertrend
python examples.py
```

You should see output from all 6 examples. 🎉

---

## 🔧 Detailed Setup

### Prerequisites

- Python 3.9+
- pip package manager
- Supabase account (free tier works)
- Alpaca API account (optional, for live data)

### Installation Options

#### Option A: Development Installation (Recommended)

```bash
# Clone/navigate to SwiftBolt_ML
cd /Users/ericpeterson/SwiftBolt_ML

# Install in editable mode
pip install -e adaptive_supertrend/

# Install dependencies
pip install -r adaptive_supertrend/requirements.txt

# Verify installation
python -c "from adaptive_supertrend import AdaptiveSuperTrend; print('✅ Ready!')"
```

#### Option B: Production Installation

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Install with specific versions
pip install --no-deps -r adaptive_supertrend/requirements.txt

# Install each dependency with pinned version
pip install numpy==1.24.3
pip install pandas==2.0.3
pip install ta-lib==0.4.28
# ... etc
```

### Dependency Verification

```bash
# Check all imports work
python -c "
import numpy as np
import pandas as pd
import talib
from supabase import create_client
print('✅ All dependencies OK')
"
```

---

## 🗄️ Supabase Setup Details

### Getting Supabase Credentials

1. Create project at https://supabase.com
2. Go to Project Settings → API
3. Copy:
   - **URL** → `SUPABASE_URL`
   - **Service Role Key** → `SUPABASE_SERVICE_ROLE_KEY`

⚠️ **Important**: Use Service Role Key (not anon key) for backend operations

### Creating Tables

**Method 1: SQL Editor** (Easiest)

```bash
1. Open https://supabase.com/dashboard
2. Select your project
3. SQL Editor → New Query
4. Copy entire content of supabase_setup.sql
5. Click Execute
6. Wait for success message
```

**Method 2: CLI** (Advanced)

```bash
# Install Supabase CLI
brew install supabase/tap/supabase

# Link to project
supabase link --project-ref your-project-ref

# Run migrations
sql -f adaptive_supertrend/supabase_setup.sql
```

### Verify Setup

```bash
# Run verification script
python -c "
import os
from supabase import create_client

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not url or not key:
    print('❌ Missing environment variables')
    exit(1)

try:
    client = create_client(url, key)
    result = client.table('adaptive_supertrend_cache').select('count', count='exact').execute()
    print(f'✅ Supabase connected. Cache table has {result.count} rows')
except Exception as e:
    print(f'❌ Connection error: {e}')
"
```

---

## 📊 First Run

### Example 1: Basic SuperTrend (Fastest)

```bash
cd /Users/ericpeterson/SwiftBolt_ML
python -c "
from adaptive_supertrend import AdaptiveSuperTrend, SuperTrendConfig
import numpy as np

# Generate sample data
np.random.seed(42)
close = np.cumsum(np.random.randn(500) * 0.5) + 100
high = close + np.abs(np.random.randn(500) * 0.5)
low = close - np.abs(np.random.randn(500) * 0.5)

# Create AdaptiveSuperTrend
config = SuperTrendConfig(metric_objective='sharpe')
ast = AdaptiveSuperTrend(config=config)

# Get optimal factor
factor, metrics = ast.optimizer.get_optimal_factor_for_period(high, low, close)

print(f'✅ Optimal Factor: {factor:.2f}')
print(f'✅ Sharpe Ratio: {metrics.sharpe_ratio:.2f}')
print(f'✅ Win Rate: {metrics.win_rate:.1%}')
"
```

### Example 2: With Real-ish Data

```bash
cd /Users/ericpeterson/SwiftBolt_ML
python adaptive_supertrend/examples.py
```

---

## 🔌 Integration with Your Code

### Basic Integration

```python
from adaptive_supertrend import AdaptiveSuperTrend, SuperTrendConfig
import numpy as np

# Your existing data loading code
high = load_highs()  # Your existing function
low = load_lows()
close = load_closes()

# Initialize adaptive supertrend
config = SuperTrendConfig(
    atr_period=10,
    metric_objective='sharpe'  # Or 'sortino', 'calmar'
)
ast = AdaptiveSuperTrend(config=config)

# Get optimal factor
factor, metrics = ast.optimizer.get_optimal_factor_for_period(
    high, low, close, lookback=504
)

# Generate signal
signal = ast.generate_signal(
    symbol='AAPL',
    timeframe='1h',
    high=high,
    low=low,
    close=close,
    factor=factor,
    metrics=metrics
)

# Use signal in your trading logic
if signal.trend == 1 and signal.signal_strength > 7:
    print(f"BUY {signal.symbol}")
elif signal.trend == 0 and signal.signal_strength > 7:
    print(f"SELL {signal.symbol}")
```

### Supabase Integration

```python
import asyncio
from supabase_integration import SupabaseAdaptiveSuperTrendSync

async def get_signal_with_caching():
    sync = SupabaseAdaptiveSuperTrendSync(
        supabase_url='your-url',
        supabase_key='your-key'
    )
    
    signal = await sync.process_symbol(
        symbol='AAPL',
        timeframe='1h',
        high=high.tolist(),
        low=low.tolist(),
        close=close.tolist(),
        store_signal=True,
        portfolio_id='my_portfolio'
    )
    
    return signal

# Run
signal = asyncio.run(get_signal_with_caching())
```

### Multi-Timeframe Integration

```python
from swiftbolt_integration import MultiTimeframeAnalyzer, DataProvider

class MyDataProvider(DataProvider):
    async def fetch_bars(self, symbol, timeframe, limit):
        # Your implementation using Alpaca/Polygon/etc
        return await get_bars_from_your_api(symbol, timeframe, limit)

async def analyze():
    analyzer = MultiTimeframeAnalyzer(
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY
    )
    
    signals = await analyzer.analyze_symbol(
        symbol='AAPL',
        data_provider=MyDataProvider(),
        timeframes=['15m', '1h', '4h']
    )
    
    consensus = analyzer.get_consensus_signal(signals)
    print(f"Consensus: {consensus['consensus']}")
    print(f"Confidence: {consensus['confidence']:.1%}")

asyncio.run(analyze())
```

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'talib'"

**Solution**:

```bash
# ta-lib requires compilation
# Option 1: Use conda (easier)
conda install -c conda-forge ta-lib

# Option 2: Install from source (macOS)
brew install ta-lib
pip install ta-lib

# Option 3: Use binary wheels
pip install TA-Lib-Binary
```

### Issue: "Supabase connection refused"

**Check**:

```bash
# 1. Verify environment variables
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_ROLE_KEY

# 2. Test connection
python -c "from supabase import create_client; print('✅ OK')"

# 3. Verify Supabase project exists
# Open https://supabase.com/dashboard and check project
```

### Issue: "Tables don't exist"

**Solution**:

1. Open Supabase dashboard
2. SQL Editor → New Query
3. Copy-paste content from `supabase_setup.sql`
4. Click Execute
5. Verify "SUCCESS" message

### Issue: Slow optimization (>5 seconds)

**Optimization**:

```python
# Reduce factor range
config = SuperTrendConfig(
    factor_step=1.0,  # Test fewer: 1.0, 2.0, 3.0, 4.0, 5.0
    lookback_window=252,  # Reduce to 1 year
    metric_objective='sharpe'  # Fastest metric
)

# Or use cached factor
factor = await sync.cache.get_cached_factor('AAPL', '1h')
if factor:
    print(f"Using cached factor: {factor['optimal_factor']}")
```

---

## 📈 Performance Tuning

### For Speed

```python
config = SuperTrendConfig(
    atr_period=10,
    factor_min=2.0,        # Narrow range
    factor_max=4.0,
    factor_step=1.0,       # Larger steps
    lookback_window=252,   # 1 year only
    cache_enabled=True,    # Use caching
    cache_ttl_hours=48     # Longer TTL
)
```

### For Accuracy

```python
config = SuperTrendConfig(
    atr_period=14,         # Longer ATR
    factor_min=1.0,        # Full range
    factor_max=5.0,
    factor_step=0.25,      # Finer resolution
    lookback_window=1008,  # 4 years
    metric_objective='sortino'  # Risk-adjusted
)
```

### For Memory

```python
# Use only necessary timeframes
timeframes = ['1h']  # Instead of ['15m', '1h', '4h']

# Reduce lookback
config = SuperTrendConfig(
    lookback_window=252  # 1 year minimum
)
```

---

## 🚀 Production Deployment

### Cloud Deployment Checklist

- [ ] Environment variables set in cloud provider (AWS/Heroku/etc)
- [ ] Supabase backup enabled
- [ ] Error logging configured
- [ ] Rate limiting implemented
- [ ] Cache TTL optimized
- [ ] Monitoring alerts set up
- [ ] Daily factor optimization scheduled
- [ ] Portfolio analysis runs hourly

### Example: AWS Lambda

```python
# lambda_handler.py
import asyncio
from supabase_integration import SupabaseAdaptiveSuperTrendSync

def lambda_handler(event, context):
    sync = SupabaseAdaptiveSuperTrendSync(
        supabase_url=os.getenv('SUPABASE_URL'),
        supabase_key=os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    )
    
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
    
    async def process():
        for symbol in symbols:
            await sync.process_symbol(
                symbol=symbol,
                timeframe='1h',
                high=get_data(symbol)['high'],
                low=get_data(symbol)['low'],
                close=get_data(symbol)['close']
            )
    
    asyncio.run(process())
    return {'statusCode': 200, 'body': 'Success'}
```

---

## 📚 Next Steps

1. **Read README.md** - Full documentation
2. **Run examples.py** - See all features
3. **Check unit tests** - Understanding implementation
4. **Integrate with your ML pipeline** - Add to models
5. **Deploy to production** - Real-time signals

---

## 💡 Tips & Tricks

### Tip 1: Cache Warm-Up

```python
# Pre-calculate factors during off-hours
import asyncio

async def warm_cache():
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']
    
    for symbol in symbols:
        data = await fetch_historical_data(symbol, '1h', 504)
        await sync.process_symbol(
            symbol=symbol,
            timeframe='1h',
            high=data['high'],
            low=data['low'],
            close=data['close']
        )
        print(f"✅ Cached {symbol}")

# Run before market open
asyncio.run(warm_cache())
```

### Tip 2: Factor Evolution Tracking

```python
# Monitor how factors change over time
history = await sync.cache.get_factor_history('AAPL', '1h', limit=30)

factors = [h['optimal_factor'] for h in history]
print(f"Factor trend: {factors[0]:.2f} → {factors[-1]:.2f}")
print(f"Stability: {np.std(factors):.3f} std dev")
```

### Tip 3: Combined with Other Indicators

```python
# Use AdaptiveSuperTrend as ensemble member
features = MLFeatureExtractor.extract_features(signals, consensus)

# Add other indicators
features['rsi_14'] = calculate_rsi(close, 14)
features['macd_12_26'] = calculate_macd(close)
features['bb_upper'] = calculate_bollinger(close)[0]

# Train combined model
model.fit(features, y_train)
```

---

## 📞 Support

For issues or questions:
1. Check README.md FAQ section
2. Review examples.py for working code
3. Check unit tests for edge cases
4. Review docstrings in source code

---

**Happy trading! 🚀📈**
