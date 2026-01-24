#!/usr/bin/env bash
# Smoke test for log-validation-audit edge function.
# Usage: ./log_validation_audit.sh SYMBOL CONFIDENCE [PROJECT_REF]
# Example: ./log_validation_audit.sh AAPL 0.72

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 SYMBOL CONFIDENCE [PROJECT_REF]" >&2
  exit 1
fi

SYMBOL="$1"
CONFIDENCE="$2"
PROJECT_REF="${3:-${SUPABASE_PROJECT_REF:-cygflaemtmwiwaviclks}}"

if ! [[ "${CONFIDENCE}" =~ ^[0-1](\.[0-9]+)?$ ]]; then
  echo "Confidence must be between 0 and 1" >&2
  exit 1
fi

if [ -z "${PROJECT_REF}" ]; then
  echo "Supabase project ref not provided. Pass as third argument or set SUPABASE_PROJECT_REF." >&2
  exit 1
fi

TIMESTAMP="$(date +%s)"

cat <<EOF | supabase functions invoke log-validation-audit \
  --project-ref "${PROJECT_REF}" \
  --body @- \
  --debug
{
  "symbol": "${SYMBOL}",
  "confidence": ${CONFIDENCE},
  "timestamp": ${TIMESTAMP},
  "weights": {"backtest": 0.4, "walkforward": 0.35, "live": 0.25},
  "client_state": {"source": "smoke-test"}
}
EOF
