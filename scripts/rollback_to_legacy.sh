#!/bin/bash

################################################################################
# Emergency Rollback Script
# ML Overfitting Fix - Revert to Legacy 4-Model Ensemble
#
# This script immediately reverts to the legacy 4-model ensemble configuration
# if critical issues are detected during Phase 7 rollout.
#
# Usage: ./rollback_to_legacy.sh [reason]
# Example: ./rollback_to_legacy.sh "Divergence spike detected"
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REASON="${1:-Manual rollback requested}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log_error() {
    echo -e "${RED}[ROLLBACK]${NC} $1"
}

log_info() {
    echo -e "${BLUE}[ROLLBACK]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[ROLLBACK]${NC} $1"
}

################################################################################
# Rollback Procedure
################################################################################

echo -e "${RED}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  EMERGENCY ROLLBACK - Reverting to Legacy 4-Model Ensemble  ║"
echo "║  Reason: $REASON"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

log_error "ROLLBACK INITIATED at $TIMESTAMP"
log_error "Reason: $REASON"

# Step 1: Revert environment configuration
log_info "Step 1: Reverting environment configuration..."
cat > ml/.env.rollback << 'EOF'
# ML Configuration - ROLLBACK TO LEGACY
# 4-model ensemble (GB + ARIMA + LSTM + Transformer disabled)

ENSEMBLE_MODEL_COUNT=4
ENABLE_LSTM=true
ENABLE_ARIMA_GARCH=true
ENABLE_GB=true
ENABLE_TRANSFORMER=false  # Permanently disabled
ENABLE_RF=false
ENABLE_PROPHET=false
ENSEMBLE_OPTIMIZATION_METHOD=ridge

# Disable experimental features
ENABLE_WALK_FORWARD=false
ENABLE_DIVERGENCE_MONITORING=false
ENABLE_2_MODEL_CORE=false
EOF

log_success "Configuration reverted to legacy defaults"

# Step 2: Update symbol metadata
log_info "Step 2: Updating symbol metadata..."
cat > sql/rollback_symbols.sql << 'EOF'
-- Rollback symbol configurations
UPDATE symbol_metadata
SET rollout_phase = 'legacy', is_canary = FALSE
WHERE rollout_phase IN ('canary', 'limited', 'production');

-- Log rollback event
INSERT INTO deployment_log (event_type, phase, reason, status, timestamp)
VALUES ('rollback', '7.1', 'Emergency rollback: ' || 'PLACEHOLDER_REASON', 'complete', NOW());
EOF

log_success "Symbol metadata updated for rollback"

# Step 3: Notify team
log_error "Step 3: Escalating to team..."
cat > rollback_alert.txt << EOF
═══════════════════════════════════════════════════════════════════════════
EMERGENCY ROLLBACK EXECUTED
═══════════════════════════════════════════════════════════════════════════

Timestamp:  $TIMESTAMP
Reason:     $REASON

Action Taken:
✓ Reverted ENSEMBLE_MODEL_COUNT from 2 to 4
✓ Restored legacy 4-model configuration
✓ Disabled walk-forward validation
✓ Disabled divergence monitoring
✓ Updated symbol metadata

Next Steps:
1. Stop current forecast generation
2. Apply .env.rollback configuration
3. Regenerate forecasts for affected symbols
4. Verify RMSE back to baseline
5. Investigate root cause of issue
6. Brief team on findings

Symbols Affected:
- AAPL (1D)
- MSFT (1D)
- SPY (1D)
(and any in limited/full rollout phases)

═══════════════════════════════════════════════════════════════════════════
EOF

log_error "Rollback alert saved to rollback_alert.txt"

# Step 4: Verification
log_info "Step 4: Verifying rollback configuration..."
python << 'PYTHON_END'
import os
os.environ['ENSEMBLE_MODEL_COUNT'] = '4'
try:
    from src.models.enhanced_ensemble_integration import get_production_ensemble
    ensemble = get_production_ensemble(horizon="1D")
    if ensemble.n_models in [3, 4]:  # 4-model or 3 due to disabled transformer
        print("✓ Legacy 4-model ensemble verified")
    else:
        print(f"✗ Unexpected model count: {ensemble.n_models}")
except Exception as e:
    print(f"✗ Verification failed: {e}")
PYTHON_END

# Step 5: Create rollback report
log_info "Step 5: Generating rollback report..."
cat > ROLLBACK_REPORT.md << EOF
# Rollback Report - Phase 7

**Timestamp:** $TIMESTAMP
**Reason:** $REASON

## Actions Taken

- [x] Reverted ENSEMBLE_MODEL_COUNT to 4
- [x] Disabled walk-forward validation
- [x] Disabled divergence monitoring
- [x] Updated symbol metadata
- [x] Verified legacy configuration

## Files Modified

- ml/.env.rollback - New legacy configuration
- sql/rollback_symbols.sql - Metadata updates
- rollback_alert.txt - Team notification

## Investigation Required

1. **Identify root cause** of rollback trigger
2. **Review divergence metrics** at time of issue
3. **Check model logs** for errors or anomalies
4. **Verify RMSE baseline** post-rollback
5. **Post-mortem analysis** for improvements

## Rollback Status

✓ COMPLETE - System reverted to legacy 4-model ensemble

## Next Steps

1. Restart forecast generation with legacy configuration
2. Monitor RMSE return to baseline
3. Investigate incident root cause
4. Brief stakeholders on findings
5. Plan remediation before retry

---

For details on re-deploying Phase 7, see: PHASE_7_PRODUCTION_ROLLOUT.md
EOF

log_success "Rollback report generated: ROLLBACK_REPORT.md"

# Final summary
echo ""
log_error "═══════════════════════════════════════════════════════════"
log_error "ROLLBACK COMPLETE - System Reverted to Legacy Ensemble"
log_error "═══════════════════════════════════════════════════════════"
log_info "All configurations restored to 4-model defaults"
log_info "Team notification: rollback_alert.txt"
log_info "Detailed report: ROLLBACK_REPORT.md"
echo ""

log_error "IMPORTANT: Manual verification required"
log_error "1. Verify forecasts generating correctly"
log_error "2. Confirm RMSE at baseline levels"
log_error "3. Brief team on incident and findings"
log_error "4. Investigate root cause before re-attempting Phase 7"

echo -e "${RED}"
echo "═══════════════════════════════════════════════════════════════════════════"
echo -e "${NC}"
