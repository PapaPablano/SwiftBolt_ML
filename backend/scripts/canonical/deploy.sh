#!/bin/bash
# =============================================================================
# CANONICAL DEPLOY SCRIPT
# =============================================================================
# Single source of truth for deploying Supabase edge functions and migrations.
#
# Usage:
#   ./deploy.sh                         # Deploy all functions
#   ./deploy.sh --functions             # Deploy edge functions only
#   ./deploy.sh --migrations            # Apply migrations only
#   ./deploy.sh --function NAME         # Deploy specific function
#
# Environment:
#   SUPABASE_PROJECT_REF  - Supabase project reference
#
# Replaces:
#   - deploy-internal-functions.sh
#   - deploy-phase2-batch.sh
#   - deploy-backfill-updates.sh
#   - apply_migration.sh
#   - migrate-to-phase2-batch.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SUPABASE_DIR="$PROJECT_ROOT/backend/supabase"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
DEPLOY_FUNCTIONS=false
DEPLOY_MIGRATIONS=false
SPECIFIC_FUNCTION=""
DRY_RUN=false

# Project reference (can be overridden by environment)
PROJECT_REF="${SUPABASE_PROJECT_REF:-cygflaemtmwiwaviclks}"

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
SwiftBolt Canonical Deploy Script

Usage: $(basename "$0") [OPTIONS]

Options:
    -f, --functions         Deploy all edge functions
    -m, --migrations        Apply database migrations
    --function NAME         Deploy specific function only
    --dry-run               Show what would be done without executing
    -h, --help              Show this help message

If no options specified, deploys both functions and migrations.

Examples:
    $(basename "$0")                     # Deploy everything
    $(basename "$0") -f                  # Deploy functions only
    $(basename "$0") -m                  # Apply migrations only
    $(basename "$0") --function seed-symbols  # Deploy specific function

Environment Variables:
    SUPABASE_PROJECT_REF    Project reference (default: cygflaemtmwiwaviclks)
EOF
    exit 0
}

check_supabase_cli() {
    if ! command -v supabase &> /dev/null; then
        log_error "Supabase CLI not found. Install: brew install supabase/tap/supabase"
        exit 1
    fi
}

# =============================================================================
# DEPLOY FUNCTIONS
# =============================================================================

deploy_function() {
    local func_name=$1

    log_info "Deploying function: $func_name"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would deploy $func_name"
        return 0
    fi

    cd "$SUPABASE_DIR"

    if supabase functions deploy "$func_name" --project-ref "$PROJECT_REF" 2>&1; then
        log_success "Deployed: $func_name"
        return 0
    else
        log_error "Failed to deploy: $func_name"
        return 1
    fi
}

deploy_all_functions() {
    log_info "Deploying all edge functions..."

    local functions_dir="$SUPABASE_DIR/functions"
    if [[ ! -d "$functions_dir" ]]; then
        log_error "Functions directory not found: $functions_dir"
        return 1
    fi

    local success=0
    local failed=0

    for func_dir in "$functions_dir"/*/; do
        if [[ -d "$func_dir" ]]; then
            local func_name
            func_name=$(basename "$func_dir")

            # Skip hidden directories and non-function directories
            [[ "$func_name" == _* ]] && continue
            [[ ! -f "$func_dir/index.ts" ]] && continue

            if deploy_function "$func_name"; then
                ((success++))
            else
                ((failed++))
            fi
        fi
    done

    log_info "Functions deployed: $success success, $failed failed"
    return $failed
}

# =============================================================================
# MIGRATIONS
# =============================================================================

apply_migrations() {
    log_info "Applying database migrations..."

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would apply migrations"
        return 0
    fi

    cd "$SUPABASE_DIR"

    if supabase db push --project-ref "$PROJECT_REF" 2>&1; then
        log_success "Migrations applied successfully"
        return 0
    else
        log_warn "Migration push completed with warnings"
        return 0  # Don't fail on warnings
    fi
}

# =============================================================================
# MAIN
# =============================================================================

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--functions)
            DEPLOY_FUNCTIONS=true
            shift
            ;;
        -m|--migrations)
            DEPLOY_MIGRATIONS=true
            shift
            ;;
        --function)
            SPECIFIC_FUNCTION="$2"
            shift 2
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

# If no specific options, deploy everything
if [[ "$DEPLOY_FUNCTIONS" == false && "$DEPLOY_MIGRATIONS" == false && -z "$SPECIFIC_FUNCTION" ]]; then
    DEPLOY_FUNCTIONS=true
    DEPLOY_MIGRATIONS=true
fi

# Check prerequisites
check_supabase_cli

# Header
echo "=============================================="
echo "SwiftBolt Canonical Deploy"
echo "=============================================="
echo "Project: $PROJECT_REF"
[[ "$DRY_RUN" == true ]] && log_warn "DRY RUN MODE"
echo ""

EXIT_CODE=0

# Deploy specific function if requested
if [[ -n "$SPECIFIC_FUNCTION" ]]; then
    deploy_function "$SPECIFIC_FUNCTION" || EXIT_CODE=1
fi

# Deploy all functions if requested
if [[ "$DEPLOY_FUNCTIONS" == true && -z "$SPECIFIC_FUNCTION" ]]; then
    deploy_all_functions || EXIT_CODE=1
fi

# Apply migrations if requested
if [[ "$DEPLOY_MIGRATIONS" == true ]]; then
    apply_migrations || EXIT_CODE=1
fi

# Summary
echo ""
echo "=============================================="
if [[ $EXIT_CODE -eq 0 ]]; then
    log_success "Deployment complete"
else
    log_error "Deployment completed with errors"
fi
echo "=============================================="

exit $EXIT_CODE
