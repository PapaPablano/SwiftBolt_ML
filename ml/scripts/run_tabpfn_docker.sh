#!/bin/bash
# Run TabPFN / hybrid TabPFN+XGBoost jobs in Docker.
#
# Run from anywhere; script cd's to ml/ so build context and .env resolve correctly:
#   From repo root:  ml/scripts/run_tabpfn_docker.sh [SYMBOL] [MODE] [TIMEFRAME]
#   From ml/:       ./scripts/run_tabpfn_docker.sh [SYMBOL] [MODE] [TIMEFRAME]
#
# Modes:
#   single   - TabPFN walk-forward (scripts/tabpfn_job.py), one symbol
#   batch    - TabPFN batch (scripts/tabpfn_batch_job.py), multiple symbols
#   hybrid   - Single-split hybrid TabPFN+XGBoost on AAPL (hybrid_tabpfn_xgb_aapl.py)
#   weekly   - Walk-forward weekly XGBoost+ARIMA+Hybrid (walk_forward_weekly.py), one symbol
#
# Optional TIMEFRAME (for weekly only): d1 (daily, default) or h4 (4h from ohlc_bars_h4_alpaca).
#   Use h4 when 4h data is backfilled (scripts/backfill_ohlc_h4_alpaca.py) for better ML resolution.
#
# Examples:
#   ./scripts/run_tabpfn_docker.sh TSLA single
#   ./scripts/run_tabpfn_docker.sh AAPL weekly
#   ./scripts/run_tabpfn_docker.sh PG weekly h4
#   ./scripts/run_tabpfn_docker.sh "" hybrid
#
# Requires: .env in ml/ (SUPABASE_URL, SUPABASE_KEY).
# Optional: add HF_TOKEN=hf_xxx to ml/.env to use TabPFN 2.5 without passing it every time.
#   Accept terms at https://huggingface.co/Prior-Labs/tabpfn_2_5 then add: HF_TOKEN=hf_...

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SYMBOL="${1:-TSLA}"
MODE="${2:-single}"
TIMEFRAME_ARG="${3:-}"

# Always run from ml/ so docker-compose context (..) and env_file (../.env) resolve to ml/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ML_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ML_DIR"
# Load HF_TOKEN from .env only (avoid sourcing whole file - keys with commas/spaces break)
if [[ -f .env ]]; then
    hf_val=$(grep -m1 '^HF_TOKEN=' .env 2>/dev/null | sed 's/^HF_TOKEN=//')
    [[ -n "$hf_val" ]] && export HF_TOKEN="$hf_val"
fi
if [[ ! -f docker/docker-compose.tabpfn.yml ]]; then
    echo -e "${RED}Error: docker/docker-compose.tabpfn.yml not found (expected in $ML_DIR).${NC}"
    exit 1
fi

echo -e "${GREEN}Starting TabPFN Docker Job${NC}"
echo "Symbol: $SYMBOL"
echo "Mode: $MODE"

if command -v nvidia-smi &>/dev/null; then
    echo -e "${GREEN}NVIDIA GPU detected${NC}"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null || true
else
    echo -e "${YELLOW}No NVIDIA GPU detected; container will use CPU (slow)${NC}"
fi

if ! docker info &>/dev/null; then
    echo -e "${RED}Docker is not running${NC}"
    exit 1
fi

echo -e "${GREEN}Building Docker image...${NC}"
docker-compose -f docker/docker-compose.tabpfn.yml build

case "$MODE" in
  batch)
    echo -e "${GREEN}Running batch job for multiple symbols...${NC}"
    SYMBOLS="${SYMBOLS:-TSLA,NVDA,AAPL,MSFT,META,SPY}" \
        docker-compose -f docker/docker-compose.tabpfn.yml run --rm tabpfn-batch
    ;;
  hybrid)
    echo -e "${GREEN}Running hybrid TabPFN+XGBoost single-split (AAPL)...${NC}"
    docker-compose -f docker/docker-compose.tabpfn.yml run --rm tabpfn-hybrid-aapl
    ;;
  weekly)
    # Optional 3rd arg: h4 = use 4h bars from ohlc_bars_h4_alpaca (alpaca_clone)
    if [[ -n "$TIMEFRAME_ARG" && "$TIMEFRAME_ARG" == "h4" ]]; then
      export TIMEFRAME="${TIMEFRAME:-h4}"
      export H4_SOURCE="${H4_SOURCE:-alpaca_clone}"
      export TRAIN_WINDOW="${TRAIN_WINDOW:-1008}"
      export REFIT_FREQ="${REFIT_FREQ:-42}"
      export HORIZON="${HORIZON:-24}"
      echo -e "${GREEN}Running walk-forward weekly (4h bars, ohlc_bars_h4_alpaca): $SYMBOL${NC}"
    else
      echo -e "${GREEN}Running walk-forward weekly (XGBoost + ARIMA + Hybrid): $SYMBOL${NC}"
    fi
    SYMBOL="$SYMBOL" TIMEFRAME="${TIMEFRAME:-d1}" H4_SOURCE="${H4_SOURCE:-supabase}" \
        HORIZON="${HORIZON:-5}" THRESHOLD="${THRESHOLD:-0.02}" \
        TRAIN_WINDOW="${TRAIN_WINDOW:-252}" REFIT_FREQ="${REFIT_FREQ:-21}" \
        docker-compose -f docker/docker-compose.tabpfn.yml run --rm tabpfn-walk-forward-weekly
    ;;
  single|*)
    echo -e "${GREEN}Running single symbol: $SYMBOL${NC}"
    SYMBOL="$SYMBOL" \
        docker-compose -f docker/docker-compose.tabpfn.yml run --rm tabpfn-walk-forward
    ;;
esac

EXIT_CODE=$?
if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}Job completed successfully${NC}"
else
    echo -e "${RED}Job failed (exit $EXIT_CODE)${NC}"
    exit $EXIT_CODE
fi

if [[ -d results ]]; then
    echo -e "${GREEN}Results in ml/results/${NC}"
    ls -lh results/*walk_forward* 2>/dev/null || true
fi
