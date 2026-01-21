#!/usr/bin/env bash
# Smoke test for get-unified-validation edge function.
# Usage: ./get_unified_validation.sh SYMBOL [PROJECT_REF]
# Requires the Supabase CLI to be logged in. Falls back to repo's default project if PROJECT_REF not supplied.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 SYMBOL [PROJECT_REF]" >&2
  exit 1
fi

SYMBOL="$1"
PROJECT_REF="${2:-${SUPABASE_PROJECT_REF:-cygflaemtmwiwaviclks}}"

if [ -z "${PROJECT_REF}" ]; then
  echo "Supabase project ref not provided. Pass as second argument or set SUPABASE_PROJECT_REF." >&2
  exit 1
fi

echo "Invoking get-unified-validation for ${SYMBOL} on project ${PROJECT_REF}..." >&2

supabase functions invoke get-unified-validation \
  --project-ref "${PROJECT_REF}" \
  --path "?symbol=${SYMBOL}" \
  --debug
