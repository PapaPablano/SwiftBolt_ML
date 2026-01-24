#!/bin/bash
# =============================================================================
# CANONICAL VALIDATE SCRIPT
# =============================================================================
# Single source of truth for validating data quality and system health.
#
# Usage:
#   ./validate.sh                       # Run all validations
#   ./validate.sh --data                # Validate data quality only
#   ./validate.sh --functions           # Validate edge functions only
#   ./validate.sh --symbol AAPL         # Validate specific symbol
#
# Environment:
#   SUPABASE_URL          - Supabase project URL
#   SUPABASE_SERVICE_KEY  - Service role key for API calls
#
# Replaces:
#   - validate-phase2.sql
#   - check_data_ingestion.sql
#   - diagnose-intraday-data.sql
#   - diagnose_chart_data_issue.sql
#   - verify_latest_available.sql
#   - check_latest_prices.sql
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
VALIDATE_DATA=false
VALIDATE_FUNCTIONS=false
SYMBOL=""
VERBOSE=false

# Core symbols to validate
CORE_SYMBOLS="AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,META,AMD,CRWD,SPY,QQQ"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1" >&2
}

usage() {
    cat << EOF
SwiftBolt Canonical Validate Script

Usage: $(basename "$0") [OPTIONS]

Options:
    -d, --data              Validate data quality
    -f, --functions         Validate edge functions
    -s, --symbol TICKER     Validate specific symbol
    -v, --verbose           Show detailed output
    -h, --help              Show this help message

If no options specified, runs all validations.

Examples:
    $(basename "$0")                     # Run all validations
    $(basename "$0") -d                  # Data validation only
    $(basename "$0") -s AAPL            # Validate AAPL data
    $(basename "$0") -f -v              # Validate functions with verbose output

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
        if [[ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
            export SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_ROLE_KEY"
        else
            log_error "SUPABASE_SERVICE_KEY is not set"
            exit 1
        fi
    fi
}

# =============================================================================
# DATA VALIDATION
# =============================================================================

validate_symbol_data() {
    local symbol=$1
    local errors=0

    log_info "Validating data for $symbol..."

    # Check OHLC data exists
    local ohlc_response
    ohlc_response=$(curl -sS \
        "${SUPABASE_URL}/rest/v1/ohlc_bars_v2?symbol_id=eq.$(get_symbol_id "$symbol")&limit=1" \
        -H "apikey: ${SUPABASE_SERVICE_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" 2>&1) || {
        log_error "$symbol: Failed to query OHLC data"
        return 1
    }

    local ohlc_count
    ohlc_count=$(echo "$ohlc_response" | jq 'length' 2>/dev/null || echo "0")

    if [[ "$ohlc_count" -gt 0 ]]; then
        log_success "$symbol: OHLC data exists"
    else
        log_warn "$symbol: No OHLC data found"
        ((errors++))
    fi

    # Check symbol exists in symbols table
    local symbol_response
    symbol_response=$(curl -sS \
        "${SUPABASE_URL}/rest/v1/symbols?ticker=eq.$symbol&select=id,ticker" \
        -H "apikey: ${SUPABASE_SERVICE_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" 2>&1) || {
        log_error "$symbol: Failed to query symbols table"
        return 1
    }

    local symbol_exists
    symbol_exists=$(echo "$symbol_response" | jq 'length' 2>/dev/null || echo "0")

    if [[ "$symbol_exists" -gt 0 ]]; then
        log_success "$symbol: Symbol registered"
    else
        log_error "$symbol: Not in symbols table"
        ((errors++))
    fi

    return $errors
}

get_symbol_id() {
    local ticker=$1
    local response
    response=$(curl -sS \
        "${SUPABASE_URL}/rest/v1/symbols?ticker=eq.$ticker&select=id" \
        -H "apikey: ${SUPABASE_SERVICE_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" 2>&1)

    echo "$response" | jq -r '.[0].id // empty'
}

validate_all_data() {
    log_info "Validating data quality..."

    local symbols
    if [[ -n "$SYMBOL" ]]; then
        symbols="$SYMBOL"
    else
        symbols="$CORE_SYMBOLS"
    fi

    local total=0
    local passed=0
    local failed=0

    IFS=',' read -ra SYMBOL_ARRAY <<< "$symbols"
    for sym in "${SYMBOL_ARRAY[@]}"; do
        sym=$(echo "$sym" | tr -d ' ')
        ((total++))
        if validate_symbol_data "$sym"; then
            ((passed++))
        else
            ((failed++))
        fi
    done

    echo ""
    log_info "Data Validation: $passed/$total passed"
    return $failed
}

# =============================================================================
# FUNCTION VALIDATION
# =============================================================================

validate_function() {
    local func_name=$1
    local test_endpoint=$2
    local method=${3:-GET}

    log_info "Testing function: $func_name"

    local response
    local http_code

    if [[ "$method" == "POST" ]]; then
        response=$(curl -sS -w "\n%{http_code}" -X POST \
            "${SUPABASE_URL}/functions/v1/$func_name" \
            -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
            -H "Content-Type: application/json" \
            -d '{}' 2>&1)
    else
        response=$(curl -sS -w "\n%{http_code}" \
            "${SUPABASE_URL}/functions/v1/$func_name$test_endpoint" \
            -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" 2>&1)
    fi

    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | sed '$d')

    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        log_success "$func_name: HTTP $http_code"
        [[ "$VERBOSE" == true ]] && echo "  Response: $(echo "$body" | head -c 200)..."
        return 0
    else
        log_error "$func_name: HTTP $http_code"
        [[ "$VERBOSE" == true ]] && echo "  Response: $body"
        return 1
    fi
}

validate_all_functions() {
    log_info "Validating edge functions..."

    local passed=0
    local failed=0

    # Core functions to test
    local functions=(
        "symbols-search?q=AAPL:GET"
        "seed-symbols:POST"
        "chart-data-v2:POST"
    )

    for func_spec in "${functions[@]}"; do
        local func_name="${func_spec%%:*}"
        local rest="${func_spec#*:}"
        local endpoint=""
        local method="GET"

        if [[ "$func_name" == *"?"* ]]; then
            endpoint="?${func_name#*\?}"
            func_name="${func_name%%\?*}"
        fi

        method="$rest"

        if validate_function "$func_name" "$endpoint" "$method"; then
            ((passed++))
        else
            ((failed++))
        fi
    done

    echo ""
    log_info "Function Validation: $passed/$((passed + failed)) passed"
    return $failed
}

# =============================================================================
# MAIN
# =============================================================================

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--data)
            VALIDATE_DATA=true
            shift
            ;;
        -f|--functions)
            VALIDATE_FUNCTIONS=true
            shift
            ;;
        -s|--symbol)
            SYMBOL="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
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

# If no specific options, run all validations
if [[ "$VALIDATE_DATA" == false && "$VALIDATE_FUNCTIONS" == false ]]; then
    VALIDATE_DATA=true
    VALIDATE_FUNCTIONS=true
fi

# Check environment
check_env

# Header
echo "=============================================="
echo "SwiftBolt Canonical Validation"
echo "=============================================="
echo ""

EXIT_CODE=0

# Run validations
if [[ "$VALIDATE_DATA" == true ]]; then
    validate_all_data || EXIT_CODE=1
    echo ""
fi

if [[ "$VALIDATE_FUNCTIONS" == true ]]; then
    validate_all_functions || EXIT_CODE=1
    echo ""
fi

# Summary
echo "=============================================="
if [[ $EXIT_CODE -eq 0 ]]; then
    log_success "All validations passed"
else
    log_error "Some validations failed"
fi
echo "=============================================="

exit $EXIT_CODE
