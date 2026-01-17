#!/usr/bin/env bash
set -euo pipefail

VERSIONS=(
  "20260110140000"
  "20260110141000"
)

for version in "${VERSIONS[@]}"; do
  echo "Repairing migration ${version} to applied..."
  supabase --workdir ../.. migration repair "${version}" --status applied --linked
  echo
done

echo "All listed migrations marked as applied. Re-run 'supabase migration list --workdir ../../' to verify."
