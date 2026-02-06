# SwiftBolt ML Pipeline

Machine learning forecasting pipeline for SwiftBolt stock analysis platform.

## Overview

Phase 4 implementation that generates ML-powered price forecasts and stores them in the database for consumption by the `/chart` API.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   ML Pipeline (Python)                   │
│                                                           │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Data Layer │→ │ Feature Eng  │→ │ Forecast Model  │ │
│  │ (Postgres) │  │ (Indicators) │  │ (Random Forest) │ │
│  └────────────┘  └──────────────┘  └─────────────────┘ │
│         ↓                                     ↓          │
│  ┌────────────────────────────────────────────────────┐ │
│  │          ml_forecasts table (Postgres)             │ │
│  │  - symbol_id, horizon, overall_label,              │ │
│  │  - confidence, points[], run_at                    │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│          /chart Edge Function (TypeScript)               │
│   Queries ml_forecasts and returns mlSummary            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│         SwiftUI macOS App (Swift)                        │
│   Displays forecast overlay + ML report card            │
└─────────────────────────────────────────────────────────┘
```

## Features

- **Data Layer**: Direct Postgres access to `ohlc_bars` table
- **Feature Engineering**: 20+ technical indicators (SMA, EMA, MACD, RSI, Bollinger Bands, ATR, etc.)
- **Baseline Model**: Random Forest classifier for 3-class prediction (Bullish/Neutral/Bearish)
- **Multi-Horizon Forecasts**: 1D and 1W predictions
- **Confidence Scoring**: Model probability scores for prediction confidence
- **Forecast Points**: Time series of future price projections with upper/lower bands

## Setup

### 1. Install Dependencies

```bash
cd ml
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

### 3. Run Database Migration

```bash
cd ../backend
supabase db push
```

This creates the `ml_forecasts` table.

## Usage

### Run Forecasting Job

```bash
cd ml
source venv/bin/activate
python src/forecast_job.py
```

This will:
1. Fetch OHLC data for configured symbols
2. Calculate technical indicators
3. Train Random Forest models
4. Generate forecasts for each horizon (1D, 1W)
5. Store results in `ml_forecasts` table

### Run the API (FastAPI on port 8000)

Start the server **from the `ml` directory** with `PYTHONPATH=.` so all routers (including binary forecast) load:

```bash
cd ml
PYTHONPATH=. uvicorn api.main:app --reload --port 8000
```

Or use the helper script:

```bash
cd ml
./run_api.sh
```

If something else is already on port 8000 (e.g. Docker or an older uvicorn), that process may not have the same routes. Either stop it and run the above, or use a different port: `./run_api.sh 8002` then call `http://localhost:8002/api/v1/forecast/binary`. When using Docker (`./start-backend.sh` from repo root), rebuild after adding routes: `docker-compose build && docker-compose up -d`.

### Configuration

Edit `config/settings.py` or set environment variables:

- `SYMBOLS_TO_PROCESS`: List of stock tickers to process
- `FORECAST_HORIZONS`: List of forecast horizons ("1D", "1W")
- `MIN_BARS_FOR_TRAINING`: Minimum historical bars required (default: 100)
- `CONFIDENCE_THRESHOLD`: Minimum confidence to consider prediction valid (default: 0.6)

### XGBoost Performance (optional)

Set these to enable GPU acceleration when available:

```bash
export XGBOOST_TREE_METHOD=gpu_hist
export XGBOOST_PREDICTOR=gpu_predictor
export XGBOOST_N_JOBS=-1
```

### Model Quantization (optional, no new deps)

Quantization can reduce model size and speed up inference without adding
new dependencies. Keep changes low-risk by using existing libraries and
opt-in env flags.

**XGBoost (no new deps):**
- Prefer histogram-based training/inference for faster CPU execution.
- Lower `max_bin` to shrink the histogram (minor accuracy risk).

```bash
export XGBOOST_TREE_METHOD=hist
export XGBOOST_PREDICTOR=cpu_predictor
export XGBOOST_N_JOBS=-1
export XGBOOST_MAX_BIN=256
```

**Manual weight-only quantization (NN / LSTM):**
- Use TensorFlow built-ins if TF is already installed.
- Convert weights to float16 for inference-only runs (no retraining).

```python
# Manual float16 weight cast (post-training, inference only)
for w in model.weights:
    w.assign(w.value().astype("float16"))
```

**Manual calibration steps (PTQ, no new deps):**
1. Collect a small calibration batch (typical inputs).
2. Record per-tensor min/max ranges.
3. Quantize weights (round-to-nearest) with scale + zero-point.
4. Validate accuracy on a holdout set (<1% drop target).

Helper script (no deps) for min/max calibration:

```bash
python src/scripts/quantization_calibration.py \
  --input path/to/features.npy \
  --output path/to/calibration_stats.npz
```

XGBoost inference benchmark (baseline vs max_bin):

```bash
python src/scripts/xgboost_inference_benchmark.py \
  --rows 5000 --features 40
```

PTQ accuracy check (baseline vs quantized inputs):

```bash
python src/scripts/ptq_accuracy_check.py \
  --rows 5000 --features 40
```

Interpretation targets (rough guidance):
- `prediction_change_rate` < 0.01
- `mean_abs_prob_delta` < 0.005

Auto-disable thresholds:

```bash
python src/scripts/ptq_accuracy_check.py \
  --rows 5000 --features 40 \
  --max-change 0.01 \
  --max-prob-delta 0.005
```

PTQ policy file (defaults):

```bash
cat ml/config/ptq_policy.json
```

Override the policy path if needed:

```bash
python src/scripts/ptq_accuracy_check.py \
  --rows 5000 --features 40 \
  --policy path/to/ptq_policy.json
```

If you need ONNX Runtime or TFLite, install them explicitly and follow
their quantization guides (higher speedup, more tooling).

## Data Flow

1. **Input**: OHLC bars from `ohlc_bars` table
2. **Feature Engineering**: Calculate 20+ technical indicators
3. **Training**: Train Random Forest on labeled historical data
4. **Prediction**: Generate forecast for most recent data
5. **Output**: Write to `ml_forecasts` table with format:

```json
{
  "symbol_id": "uuid",
  "horizon": "1D",
  "overall_label": "Bullish",
  "confidence": 0.78,
  "points": [
    {
      "ts": 1734220800,
      "value": 248.50,
      "lower": 246.25,
      "upper": 250.75
    }
  ],
  "run_at": "2025-12-15T12:00:00Z"
}
```

## Model Details

### Baseline Forecaster

- **Algorithm**: Random Forest Classifier (100 trees)
- **Target**: 3-class classification (Bullish/Neutral/Bearish)
- **Thresholds**: ±2% for Bullish/Bearish, otherwise Neutral
- **Features**: Technical indicators (SMA, EMA, MACD, RSI, BB, ATR, volume, volatility)
- **Training Window**: Last 500 daily bars
- **Feature Scaling**: StandardScaler normalization

### Technical Indicators

| Category | Indicators |
|----------|-----------|
| **Returns** | 1D, 5D, 20D percentage changes |
| **Moving Averages** | SMA(5, 20, 50), EMA(12, 26) |
| **Momentum** | MACD, MACD Signal, MACD Histogram, RSI(14) |
| **Volatility** | Bollinger Bands (20, 2σ), 20D rolling volatility, ATR(14) |
| **Volume** | SMA(20), Volume ratio |
| **Relative Position** | Price vs SMA(20, 50) |

## Scheduling

To run forecasts every 10 minutes, set up a cron job:

```bash
*/10 * * * * cd /path/to/ml && ./venv/bin/python src/forecast_job.py >> logs/forecast_job.log 2>&1
```

Or use a task scheduler like systemd, Docker cron, or Supabase Edge Functions with pg_cron.

## Testing

```bash
pytest tests/
```

## Linting & Formatting

```bash
# Linting
ruff check src/

# Formatting
black src/

# Type checking
mypy src/
```

## Next Steps (Phase 5)

1. Update `/chart` Edge Function to query `ml_forecasts` and include in response
2. Add Swift models for `MLSummary`, `ForecastPoint`, etc.
3. Render forecast overlay on charts
4. Display ML report card with label/confidence
5. Gate ML features by user plan (free vs. premium)

## Troubleshooting

### Insufficient Training Data

If you see "Insufficient data" warnings, you need to backfill more historical OHLC bars. Run the backfill script (Phase 3.3 - TODO).

### Database Connection Issues

Ensure your `DATABASE_URL` is correct and includes the direct Postgres connection string (not the Supabase URL).

### Import Errors

Make sure you're running from the `ml/` directory and have activated the virtual environment.

## License

Proprietary - SwiftBolt Platform
