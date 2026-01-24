#!/bin/bash
# =============================================================================
# CANONICAL BACKFILL SCRIPT
# =============================================================================
# Single source of truth for triggering data backfills.
#
# Usage:
#   ./backfill.sh                      # Backfill all core symbols
#   ./backfill.sh --symbol AAPL        # Backfill single symbol
#   ./backfill.sh --timeframe d1       # Backfill specific timeframe
#   ./backfill.sh --days 30            # Limit to last N days
#
# Environment:
#   SUPABASE_URL          - Supabase project URL
#   SUPABASE_SERVICE_KEY  - Service role key for API calls
#
# Replaces:
#   - simple-backfill-trigger.sh
#   - reload_watchlist_alpaca.sh
#   - trigger-alpaca-backfill.sql
#   - fix-intraday-data.sh
# =============================================================================

set -euo pipefail

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
SYMBOL=""
TIMEFRAME=""
DAYS=365
FORCE=false
DRY_RUN=false

# Core symbols to backfill by default
CORE_SYMBOLS="AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,META,AMD,CRWD,SPY,QQQ"

# Valid timeframes
VALID_TIMEFRAMES="m15,h1,h4,d1,w1"

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
SwiftBolt Canonical Backfill Script

Usage: $(basename "$0") [OPTIONS]

Options:
    -s, --symbol TICKER     Single symbol to backfill (default: all core symbols)
    -t, --timeframe TF      Specific timeframe (m15, h1, h4, d1, w1)
    -d, --days N            Number of days to backfill (default: 365)
    -f, --force             Force re-fetch even if data exists
    --dry-run               Show what would be done without executing
    -h, --help              Show this help message

Examples:
    $(basename "$0")                     # Backfill all core symbols, all timeframes
    $(basename "$0") -s AAPL            # Backfill AAPL only
    $(basename "$0") -s AAPL -t d1      # Backfill AAPL daily bars only
    $(basename "$0") -d 30 --force      # Force backfill last 30 days

Environment Variables:
    SUPABASE_URL            Required: Supabase project URL
    SUPABASE_SERVICE_KEY    Required: Service role key
EOF
    exit 0
}

check_env() {
    if [[ -z "${SUPABASE_URL:-}" ]]; then
        log_error "SUPABASE_URL is not set"
        exit 1
    fi
    if [[ -z "${SUPABASE_SERVICE_KEY:-}" ]]; then
        # Try alternate name
        if [[ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
            export SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_ROLE_KEY"
        else
            log_error "SUPABASE_SERVICE_KEY is not set"
            exit 1
        fi
    fi
}

validate_timeframe() {
    local tf=$1
    if [[ ! ",$VALID_TIMEFRAMES," == *",$tf,"* ]]; then
        log_error "Invalid timeframe: $tf (valid: $VALID_TIMEFRAMES)"
        exit 1
    fi
}

# =============================================================================
# BACKFILL FUNCTIONS
# =============================================================================

backfill_symbol() {
    local symbol=$1
    local timeframe=${2:-""}
    local days=$3

    log_info "Backfilling $symbol (timeframe: ${timeframe:-all}, days: $days)"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would call symbol-backfill for $symbol"
        return 0
    fi

    local payload
    if [[ -n "$timeframe" ]]; then
        payload=$(jq -n \
            --arg symbol "$symbol" \
            --arg tf "$timeframe" \
            --argjson force "$FORCE" \
            '{symbol: $symbol, timeframes: [$tf], force: $force}')
    else
        payload=$(jq -n \
            --arg symbol "$symbol" \
            --argjson force "$FORCE" \
            '{symbol: $symbol, force: $force}')
    fi

    local response
    response=$(curl -sS -X POST \
        "${SUPABASE_URL}/functions/v1/symbol-backfill" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>&1) || {
        log_error "Request failed for $symbol"
        return 1
    }

    # Check for success
    if echo "$response" | jq -e '.success' > /dev/null 2>&1; then
        local bars_inserted
        bars_inserted=$(echo "$response" | jq -r '.total_bars // 0')
        log_success "$symbol: $bars_inserted bars inserted"
    else
        local error_msg
        error_msg=$(echo "$response" | jq -r '.error // "Unknown error"')
        log_warn "$symbol: $error_msg"
    fi
}

# =============================================================================
# MAIN
# =============================================================================

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--symbol)
            SYMBOL="$2"
            shift 2
            ;;
        -t|--timeframe)
            TIMEFRAME="$2"
            validate_timeframe "$TIMEFRAME"
            shift 2
            ;;
        -d|--days)
            DAYS="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
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

# Validate environment
check_env

# Header
echo "=============================================="
echo "SwiftBolt Canonical Backfill"
echo "=============================================="
echo ""

# Determine symbols to process
if [[ -n "$SYMBOL" ]]; then
    SYMBOLS="$SYMBOL"
else
    SYMBOLS="$CORE_SYMBOLS"
fi

log_info "Symbols: $SYMBOLS"
log_info "Timeframe: ${TIMEFRAME:-all}"
log_info "Days: $DAYS"
log_info "Force: $FORCE"
[[ "$DRY_RUN" == true ]] && log_warn "DRY RUN MODE - No changes will be made"
echo ""

# Process each symbol
IFS=',' read -ra SYMBOL_ARRAY <<< "$SYMBOLS"
SUCCESS_COUNT=0
FAIL_COUNT=0

for sym in "${SYMBOL_ARRAY[@]}"; do
    sym=$(echo "$sym" | tr -d ' ')
    if backfill_symbol "$sym" "$TIMEFRAME" "$DAYS"; then
        ((SUCCESS_COUNT++))
    else
        ((FAIL_COUNT++))
    fi
done

# Summary
echo ""
echo "=============================================="
echo "Backfill Complete"
echo "=============================================="
echo "Successful: $SUCCESS_COUNT"
echo "Failed: $FAIL_COUNT"
echo "=============================================="

exit $FAIL_COUNT
