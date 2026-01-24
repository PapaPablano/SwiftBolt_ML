#!/bin/bash
# =============================================================================
# CANONICAL SEED SCRIPT
# =============================================================================
# Single source of truth for seeding the database with initial data.
#
# Usage:
#   ./seed.sh                           # Seed all core symbols
#   ./seed.sh --symbols                 # Seed symbols table only
#   ./seed.sh --verify                  # Verify seeded data
#
# Environment:
#   SUPABASE_URL          - Supabase project URL
#   SUPABASE_SERVICE_KEY  - Service role key for API calls
#
# Replaces:
#   - seed-symbols.sql
#   - seed-symbols.ts
#   - seed-and-verify-symbols.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
SEED_SYMBOLS=false
VERIFY_ONLY=false

# Supabase configuration
PROJECT_REF="${SUPABASE_PROJECT_REF:-cygflaemtmwiwaviclks}"
SUPABASE_URL="${SUPABASE_URL:-https://${PROJECT_REF}.supabase.co}"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

usage() {
    cat << EOF
SwiftBolt Canonical Seed Script

Usage: $(basename "$0") [OPTIONS]

Options:
    -s, --symbols           Seed symbols table
    --verify                Verify seeded data only (no seeding)
    -h, --help              Show this help message

If no options specified, seeds symbols and verifies.

Examples:
    $(basename "$0")                     # Seed and verify
    $(basename "$0") --verify           # Just verify existing data

Environment Variables:
    SUPABASE_URL            Supabase project URL
    SUPABASE_SERVICE_KEY    Service role key (optional, uses anon for read)
EOF
    exit 0
}

get_auth_key() {
    # Use service key if available, otherwise anon key
    if [[ -n "${SUPABASE_SERVICE_KEY:-}" ]]; then
        echo "$SUPABASE_SERVICE_KEY"
    elif [[ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
        echo "$SUPABASE_SERVICE_ROLE_KEY"
    elif [[ -n "${SUPABASE_ANON_KEY:-}" ]]; then
        echo "$SUPABASE_ANON_KEY"
    else
        # Default anon key for the project
        echo "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"
    fi
}

# =============================================================================
# SEED FUNCTIONS
# =============================================================================

seed_symbols() {
    log_info "Seeding symbols via edge function..."

    local auth_key
    auth_key=$(get_auth_key)

    local response
    response=$(curl -sS -X POST \
        "${SUPABASE_URL}/functions/v1/seed-symbols" \
        -H "Authorization: Bearer ${auth_key}" \
        -H "Content-Type: application/json" \
        -d '{}' 2>&1) || {
        log_error "Failed to call seed-symbols function"
        return 1
    }

    # Check response
    if echo "$response" | jq -e '.success' > /dev/null 2>&1; then
        local count
        count=$(echo "$response" | jq -r '.results | length')
        log_success "Seeded $count symbols"

        # Show results
        echo "$response" | jq -r '.results[] | "  - \(.ticker): \(.status)"'
        return 0
    else
        local error
        error=$(echo "$response" | jq -r '.error // "Unknown error"')
        log_error "Seed failed: $error"
        return 1
    fi
}

# =============================================================================
# VERIFY FUNCTIONS
# =============================================================================

verify_symbols() {
    log_info "Verifying symbols..."

    local auth_key
    auth_key=$(get_auth_key)

    # Check a few core symbols
    local symbols=("AAPL" "NVDA" "SPY")
    local found=0

    for sym in "${symbols[@]}"; do
        local response
        response=$(curl -sS \
            "${SUPABASE_URL}/functions/v1/symbols-search?q=$sym" \
            -H "Authorization: Bearer ${auth_key}" 2>&1)

        if echo "$response" | jq -e '.[0].ticker' > /dev/null 2>&1; then
            local ticker
            ticker=$(echo "$response" | jq -r '.[0].ticker')
            log_success "Found: $ticker"
            ((found++))
        else
            log_warn "Not found: $sym"
        fi
    done

    echo ""
    log_info "Verified $found/${#symbols[@]} core symbols"

    if [[ $found -eq ${#symbols[@]} ]]; then
        return 0
    else
        return 1
    fi
}

verify_sync() {
    log_info "Testing symbol sync (job creation)..."

    local auth_key
    auth_key=$(get_auth_key)

    local response
    response=$(curl -sS -X POST \
        "${SUPABASE_URL}/functions/v1/sync-user-symbols" \
        -H "Authorization: Bearer ${auth_key}" \
        -H "Content-Type: application/json" \
        -d '{
            "symbols": ["AAPL"],
            "source": "watchlist",
            "timeframes": ["m15", "h1", "h4"]
        }' 2>&1) || {
        log_error "Failed to call sync-user-symbols"
        return 1
    }

    local jobs_updated
    jobs_updated=$(echo "$response" | jq -r '.jobs_updated // 0')

    if [[ "$jobs_updated" -gt 0 ]]; then
        log_success "Sync working: $jobs_updated jobs created"
        return 0
    else
        log_warn "Sync returned 0 jobs"
        echo "Response: $response"
        return 1
    fi
}

# =============================================================================
# MAIN
# =============================================================================

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--symbols)
            SEED_SYMBOLS=true
            shift
            ;;
        --verify)
            VERIFY_ONLY=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# If no specific options, seed and verify
if [[ "$SEED_SYMBOLS" == false && "$VERIFY_ONLY" == false ]]; then
    SEED_SYMBOLS=true
fi

# Header
echo "=============================================="
echo "SwiftBolt Canonical Seed"
echo "=============================================="
echo "Project: $PROJECT_REF"
echo ""

EXIT_CODE=0

# Seed symbols
if [[ "$SEED_SYMBOLS" == true && "$VERIFY_ONLY" == false ]]; then
    seed_symbols || EXIT_CODE=1
    echo ""
fi

# Verify
verify_symbols || EXIT_CODE=1
echo ""

verify_sync || EXIT_CODE=1
echo ""

# Summary
echo "=============================================="
if [[ $EXIT_CODE -eq 0 ]]; then
    log_success "Seed complete - all checks passed"
else
    log_error "Some checks failed"
fi
echo "=============================================="

exit $EXIT_CODE
