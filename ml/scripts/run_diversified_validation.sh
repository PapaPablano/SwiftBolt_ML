#!/bin/bash
# Quick launcher for diversified stock validation

set -e

cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd)"

echo "=========================================="
echo "Blind Walk-Forward Validation"
echo "Diversified Stock Set"
echo "=========================================="
echo ""
echo "Testing across:"
echo "  - Low volatility: PG, KO, JNJ"
echo "  - Medium volatility: MSFT, AMGN"
echo "  - High volatility: NVDA, MU, ALB"
echo ""
echo "This detects overfitting to specific:"
echo "  - Sectors (Tech, Healthcare, Materials, etc.)"
echo "  - Volatility regimes (calm vs wild markets)"
echo "  - Market caps (mega-cap vs mid-cap)"
echo ""
echo "=========================================="
echo ""

python scripts/blind_walk_forward_validation.py \
  --symbols PG,KO,JNJ,MSFT,AMGN,NVDA,MU,ALB \
  --holdout-start 2025-10-15 \
  --holdout-end 2026-02-03 \
  --horizons 1D,5D,10D,20D \
  --model-type baseline \
  --output-dir validation_results/diversified

echo ""
echo "=========================================="
echo "Validation Complete!"
echo "=========================================="
echo ""
echo "Check results in: validation_results/diversified/"
echo ""
echo "Next steps:"
echo "  1. Review validation_report_*.json"
echo "  2. Check for sector-specific performance gaps"
echo "  3. If accuracy > 55% across all groups: Deploy!"
echo "  4. If one sector/volatility dominates: Investigate overfitting"
echo ""
