#!/bin/bash
# Quick diagnostic script to analyze threshold settings for problematic models

echo "========================================"
echo "Running Threshold Diagnostics"
echo "========================================"
echo ""

cd /Users/ericpeterson/SwiftBolt_ML

export PYTHONPATH=/Users/ericpeterson/SwiftBolt_ML/ml

echo "Analyzing SPY daily..."
echo "----------------------------------------"
python -m src.training.diagnose_threshold \
    --symbol SPY \
    --timeframe d1 \
    --current-threshold 0.015 \
    --bars 500 \
    --horizon 5 \
    --target-neutral 40

echo ""
echo ""
echo "Analyzing NVDA daily..."
echo "----------------------------------------"
python -m src.training.diagnose_threshold \
    --symbol NVDA \
    --timeframe d1 \
    --current-threshold 0.015 \
    --bars 500 \
    --horizon 5 \
    --target-neutral 40

echo ""
echo ""
echo "========================================"
echo "Diagnostics Complete!"
echo "========================================"
echo ""
echo "To generate plots, add --plot flag:"
echo "  python -m src.training.diagnose_threshold --symbol SPY --timeframe d1 --current-threshold 0.015 --plot"
echo ""
