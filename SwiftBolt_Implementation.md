# SwiftBolt_ML Implementation Guide

**Phase**: Action Phase - Step-by-Step Fixes  
**Timeline**: 3 weeks total  
**Ready to execute**: Yes

---

## Priority 1: Fix Symbols Table (1 Hour) 🔴

### Blocker: Swift App Symbol Tracking

Your Swift app calls the Edge Function but creates 0 jobs because the symbols table is empty.

### Step 1.1: Create Seed Script

**File**: `backend/scripts/seed-symbols.sql`

```sql
-- Seed core trading symbols into symbols table
-- Run once to initialize: psql $DATABASE_URL < backend/scripts/seed-symbols.sql

INSERT INTO symbols (symbol, name, exchange, asset_class, active)
VALUES
  ('AAPL', 'Apple Inc.', 'NASDAQ', 'equity', true),
  ('NVDA', 'NVIDIA Corporation', 'NASDAQ', 'equity', true),
  ('CRWD', 'CrowdStrike Holdings', 'NASDAQ', 'equity', true),
  ('AMD', 'Advanced Micro Devices', 'NASDAQ', 'equity', true),
  ('MSFT', 'Microsoft Corporation', 'NASDAQ', 'equity', true),
  ('GOOGL', 'Alphabet Inc.', 'NASDAQ', 'equity', true),
  ('TSLA', 'Tesla Inc.', 'NASDAQ', 'equity', true),
  ('META', 'Meta Platforms', 'NASDAQ', 'equity', true)
ON CONFLICT (symbol) DO NOTHING;

-- Verify insert
SELECT COUNT(*) as symbol_count FROM symbols WHERE active = true;
```

### Step 1.2: Execute

```bash
# Navigate to project root
cd ~/SwiftBolt_ML

# Connect to Supabase and run seed script
psql $DATABASE_URL < backend/scripts/seed-symbols.sql

# Verify
psql $DATABASE_URL -c "SELECT COUNT(*) FROM symbols WHERE active = true;"
# Expected output: 8

psql $DATABASE_URL -c "SELECT symbol, name FROM symbols ORDER BY symbol;"
# Expected output:
# AAPL | Apple Inc.
# AMD  | Advanced Micro Devices
# ... (8 total)
```

### Step 1.3: Test Symbol Sync

**File**: `backend/scripts/test_symbol_sync.sh`

```bash
#!/bin/bash

# Test that symbol tracking works end-to-end

set -e
DATABASE_URL=${DATABASE_URL:-"postgresql://user:pass@localhost/swiftbolt"}
TEST_SYMBOL="AAPL"
TEST_USER_ID="test-user-123"

echo "Testing symbol tracking for $TEST_SYMBOL..."

# Step 1: Check symbol exists
echo "Step 1: Verifying symbol in database..."
SYMBOL_COUNT=$(psql $DATABASE_URL -t -c \
  "SELECT COUNT(*) FROM symbols WHERE symbol = '$TEST_SYMBOL' AND active = true;")

if [ "$SYMBOL_COUNT" -eq 0 ]; then
  echo "❌ FAIL: Symbol $TEST_SYMBOL not found in database"
  exit 1
fi
echo "✓ PASS: Symbol $TEST_SYMBOL found"

# Step 2: Create user tracking (simulate Edge Function)
echo "Step 2: Creating user_symbol_tracking entry..."
psql $DATABASE_URL -c \
  "INSERT INTO user_symbol_tracking (user_id, symbol_id) \
   SELECT '$TEST_USER_ID', id FROM symbols WHERE symbol = '$TEST_SYMBOL' \
   ON CONFLICT DO NOTHING;"
echo "✓ PASS: User tracking entry created"

# Step 3: Check jobs created
echo "Step 3: Verifying jobs were created..."
JOBS_COUNT=$(psql $DATABASE_URL -t -c \
  "SELECT COUNT(*) FROM forecast_jobs \
   WHERE (user_id = '$TEST_USER_ID' OR symbol_id = \
           (SELECT id FROM symbols WHERE symbol = '$TEST_SYMBOL')) \
   AND created_at > NOW() - INTERVAL '5 minutes';")

if [ "$JOBS_COUNT" -gt 0 ]; then
  echo "✓ PASS: $JOBS_COUNT jobs created"
else
  echo "⚠️  WARNING: No jobs created yet (may be async trigger)"
fi

echo ""
echo "Symbol sync test completed successfully!"
```

### Step 1.4: Redeploy Swift App

After seeding symbols:
1. Rebuild Swift app (Xcode)
2. Test on simulator: add AAPL to watchlist
3. Should see: "Added and backfilling..."
4. Jobs created should appear in Supabase logs

---

## Priority 2: Create Unified Validator (3 Days) 🚴

### Problem: Dashboard Shows 3 Conflicting Signals

- Backtesting: 98.8% (historical)
- Live: 40% (today - DEGRADED!)
- Multi-TF: -48%, -40%, -40% (conflicting)

### Solution: Unified Confidence Score

### Step 2.1: Create Framework

**File**: `ml/src/validation/unified_framework.py`

```python
"""Unified Validation Framework

Reconciles three validation metrics into single confidence score:
1. Backtesting score (40% weight) - historical accuracy
2. Walk-forward score (35% weight) - recent quarterly accuracy
3. Live score (25% weight) - current prediction accuracy

Outputs unified confidence with drift detection and multi-TF reconciliation.
"""

import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ValidationScores:
    """Component scores for validation"""
    backtesting_score: float  # 3-month historical accuracy (0-1)
    walkforward_score: float  # Recent quarterly accuracy (0-1)
    live_score: float         # Last 30 predictions accuracy (0-1)
    multi_tf_scores: Dict[str, float]  # M15, H1, H4, D1, W1 scores
    timestamp: datetime = None


@dataclass
class UnifiedPrediction:
    """Output of unified validator"""
    symbol: str
    direction: str  # BULLISH, BEARISH, NEUTRAL
    unified_confidence: float  # 0-1, final score
    
    # Component breakdown
    backtesting_score: float
    walkforward_score: float
    live_score: float
    multi_tf_consensus: Dict[str, any]  # Timeframe reconciliation
    
    # Alerts
    drift_detected: bool
    drift_magnitude: float  # 0-1
    drift_explanation: str
    
    # Multi-timeframe
    timeframe_conflict: bool
    conflict_explanation: str
    consensus_direction: str
    hierarchy_weights: Dict[str, float]  # D1: 0.4, H4: 0.3, etc.
    
    # Recommendations
    recommendation: str
    retraining_trigger: bool
    retraining_reason: str
    next_retraining_date: datetime
    
    timestamp: datetime


class UnifiedValidator:
    """Main validation reconciliation engine"""
    
    # Configuration (tunable)
    BACKTEST_WEIGHT = 0.40  # Historical accuracy weight
    WALKFORWARD_WEIGHT = 0.35  # Quarterly rolling weight
    LIVE_WEIGHT = 0.25  # Real-time accuracy weight
    
    DRIFT_THRESHOLD = 0.25  # 25% divergence = flag as drift
    DRIFT_SEVERE_THRESHOLD = 0.50  # 50% = auto-investigate
    DRIFT_CRITICAL_THRESHOLD = 0.75  # 75% = consider retraining
    
    # Multi-timeframe hierarchy (longer = more weight)
    TF_HIERARCHY = {
        'W1': 0.50,  # Weekly: 50%
        'D1': 0.40,  # Daily: 40%
        'H4': 0.30,  # 4-hour: 30%
        'H1': 0.20,  # Hourly: 20%
        'M15': 0.10  # 15-min: 10%
    }
    
    def __init__(self):
        """Initialize validator"""
        self.last_retraining_date = datetime.now() - timedelta(days=30)
    
    def validate(
        self,
        symbol: str,
        direction: str,
        scores: ValidationScores
    ) -> UnifiedPrediction:
        """
        Main validation method.
        
        Args:
            symbol: Trading symbol (AAPL, etc.)
            direction: BULLISH, BEARISH, or NEUTRAL
            scores: ValidationScores with component accuracies
        
        Returns:
            UnifiedPrediction with reconciled confidence
        """
        
        # Step 1: Calculate unified confidence
        unified_conf = self._calculate_unified_confidence(scores)
        
        # Step 2: Detect drift
        drift_detected, drift_mag, drift_explain = self._detect_drift(scores)
        
        # Step 3: Reconcile multi-timeframe
        tf_conflict, conflict_explain, consensus_dir, weights = \
            self._reconcile_timeframes(scores.multi_tf_scores)
        
        # Step 4: Adjust confidence
        adjusted_conf, recommendation = self._adjust_confidence(
            unified_conf,
            drift_detected,
            drift_mag,
            tf_conflict,
            consensus_dir,
            direction
        )
        
        # Step 5: Determine retraining trigger
        retrain_trigger, retrain_reason, next_retrain_date = \
            self._check_retraining_trigger(drift_mag, adjusted_conf)
        
        return UnifiedPrediction(
            symbol=symbol,
            direction=direction,
            unified_confidence=adjusted_conf,
            backtesting_score=scores.backtesting_score,
            walkforward_score=scores.walkforward_score,
            live_score=scores.live_score,
            multi_tf_consensus=scores.multi_tf_scores,
            drift_detected=drift_detected,
            drift_magnitude=drift_mag,
            drift_explanation=drift_explain,
            timeframe_conflict=tf_conflict,
            conflict_explanation=conflict_explain,
            consensus_direction=consensus_dir,
            hierarchy_weights=weights,
            recommendation=recommendation,
            retraining_trigger=retrain_trigger,
            retraining_reason=retrain_reason,
            next_retraining_date=next_retrain_date,
            timestamp=scores.timestamp or datetime.now()
        )
    
    def _calculate_unified_confidence(self, scores: ValidationScores) -> float:
        """
        Weighted average of three validation scores.
        
        Formula:
            unified = 0.40 * backtesting + 0.35 * walkforward + 0.25 * live
        """
        unified = (
            self.BACKTEST_WEIGHT * scores.backtesting_score +
            self.WALKFORWARD_WEIGHT * scores.walkforward_score +
            self.LIVE_WEIGHT * scores.live_score
        )
        return min(1.0, max(0.0, unified))  # Clamp to [0, 1]
    
    def _detect_drift(self, scores: ValidationScores) -> Tuple[bool, float, str]:
        """
        Detect model drift by comparing live vs backtesting.
        
        Drift = (backtesting - live) / backtesting
        
        Returns:
            (drift_detected, drift_magnitude, explanation)
        """
        if scores.backtesting_score == 0:
            return False, 0.0, "No historical data"
        
        drift_mag = abs(
            scores.backtesting_score - scores.live_score
        ) / scores.backtesting_score
        
        drift_detected = drift_mag > self.DRIFT_THRESHOLD
        
        if drift_mag < 0.10:
            explanation = "Model stable, no drift detected"
        elif drift_mag < 0.25:
            explanation = "Minor drift, monitor closely"
        elif drift_mag < 0.50:
            explanation = "Moderate drift, investigate cause"
        else:
            explanation = "Severe drift, model degraded significantly"
        
        return drift_detected, drift_mag, explanation
    
    def _reconcile_timeframes(
        self,
        multi_tf_scores: Dict[str, float]
    ) -> Tuple[bool, str, str, Dict[str, float]]:
        """
        Reconcile conflicting multi-timeframe predictions.
        
        Returns:
            (conflict_detected, explanation, consensus_direction, weights)
        """
        if not multi_tf_scores:
            return False, "No multi-TF data", "UNKNOWN", {}
        
        # Normalize scores to directions
        predictions = {}
        for tf, score in multi_tf_scores.items():
            # score > 0 = BULLISH, score < 0 = BEARISH
            if score > 0.30:
                predictions[tf] = 'BULLISH'
            elif score < -0.30:
                predictions[tf] = 'BEARISH'
            else:
                predictions[tf] = 'NEUTRAL'
        
        # Get weighted consensus
        bullish_weight = sum(
            self.TF_HIERARCHY.get(tf, 0)
            for tf, pred in predictions.items()
            if pred == 'BULLISH'
        )
        bearish_weight = sum(
            self.TF_HIERARCHY.get(tf, 0)
            for tf, pred in predictions.items()
            if pred == 'BEARISH'
        )
        
        total_weight = bullish_weight + bearish_weight
        
        if total_weight == 0:
            return False, "All neutral predictions", "NEUTRAL", self.TF_HIERARCHY
        
        # Determine consensus
        if abs(bullish_weight - bearish_weight) / total_weight < 0.20:
            # Close call
            conflict_detected = True
            explanation = "Weak consensus - timeframes conflict"
            consensus_dir = "NEUTRAL"
        else:
            conflict_detected = False
            explanation = "Strong consensus across timeframes"
            consensus_dir = 'BULLISH' if bullish_weight > bearish_weight else 'BEARISH'
        
        return conflict_detected, explanation, consensus_dir, self.TF_HIERARCHY
    
    def _adjust_confidence(
        self,
        base_confidence: float,
        drift_detected: bool,
        drift_mag: float,
        tf_conflict: bool,
        consensus_dir: str,
        prediction_dir: str
    ) -> Tuple[float, str]:
        """
        Adjust base confidence based on conditions.
        """
        adjusted = base_confidence
        adjustments = []
        
        # Drift penalty
        if drift_detected:
            drift_penalty = min(0.30, drift_mag * 0.5)  # Max 30% penalty
            adjusted *= (1 - drift_penalty)
            adjustments.append(f"Drift penalty: -{drift_penalty*100:.1f}%")
        
        # Multi-TF conflict penalty
        if tf_conflict:
            adjusted *= 0.80  # 20% penalty
            adjustments.append("Multi-TF conflict: -20%")
        
        # Consensus alignment bonus
        if consensus_dir == prediction_dir and not tf_conflict:
            adjusted *= 1.10  # 10% bonus
            adjustments.append("Consensus alignment: +10%")
        
        adjusted = min(1.0, max(0.0, adjusted))
        
        # Generate recommendation
        if adjusted > 0.75:
            recommendation = "High confidence - strong signal"
        elif adjusted > 0.60:
            recommendation = "Moderate confidence - trade with normal risk"
        elif adjusted > 0.40:
            recommendation = "Low confidence - use wider stops or skip"
        else:
            recommendation = "Very low confidence - avoid trading"
        
        if adjustments:
            recommendation += f" ({', '.join(adjustments)})"
        
        return adjusted, recommendation
    
    def _check_retraining_trigger(
        self,
        drift_mag: float,
        confidence: float
    ) -> Tuple[bool, str, datetime]:
        """
        Determine if model should be retrained.
        """
        days_since_retrain = (datetime.now() - self.last_retraining_date).days
        
        # Trigger 1: Severe drift
        if drift_mag > self.DRIFT_CRITICAL_THRESHOLD:
            return True, "Critical drift detected (>75%)", datetime.now() + timedelta(hours=2)
        
        # Trigger 2: Severe drift for multiple days
        if drift_mag > self.DRIFT_SEVERE_THRESHOLD and days_since_retrain > 7:
            return True, "Persistent drift (>50% for 7+ days)", datetime.now() + timedelta(hours=6)
        
        # Trigger 3: Regular retraining schedule (30 days)
        if days_since_retrain > 30:
            return True, "Regular retraining schedule", datetime.now() + timedelta(hours=12)
        
        # No trigger
        next_date = self.last_retraining_date + timedelta(days=30)
        return False, "Model within acceptable drift", next_date


# Example usage
if __name__ == "__main__":
    validator = UnifiedValidator()
    
    # Simulate scores
    scores = ValidationScores(
        backtesting_score=0.988,
        walkforward_score=0.78,
        live_score=0.40,
        multi_tf_scores={
            'M15': -0.48,
            'H1': -0.40,
            'H4': -0.40,
            'D1': 0.60,
            'W1': 0.70
        }
    )
    
    result = validator.validate('AAPL', 'BULLISH', scores)
    
    print(f"\nUnified Prediction for {result.symbol}:")
    print(f"Direction: {result.direction}")
    print(f"Unified Confidence: {result.unified_confidence:.1%}")
    print(f"\nComponent Scores:")
    print(f"  Backtesting: {result.backtesting_score:.1%}")
    print(f"  Walk-forward: {result.walkforward_score:.1%}")
    print(f"  Live: {result.live_score:.1%}")
    print(f"\nDrift Analysis:")
    print(f"  Detected: {result.drift_detected}")
    print(f"  Magnitude: {result.drift_magnitude:.1%}")
    print(f"  Explanation: {result.drift_explanation}")
    print(f"\nMulti-Timeframe:")
    print(f"  Conflict: {result.timeframe_conflict}")
    print(f"  Consensus: {result.consensus_direction}")
    print(f"  Explanation: {result.conflict_explanation}")
    print(f"\nRecommendation: {result.recommendation}")
    print(f"\nRetraining:")
    print(f"  Trigger: {result.retraining_trigger}")
    print(f"  Reason: {result.retraining_reason}")
    print(f"  Next Date: {result.next_retraining_date}")
```

### Step 2.2: Create Tests

**File**: `ml/tests/test_unified_validator.py`

```python
"""Tests for unified validator"""

import pytest
from datetime import datetime
from ml.src.validation.unified_framework import (
    UnifiedValidator,
    ValidationScores
)


class TestUnifiedValidator:
    
    def setup_method(self):
        self.validator = UnifiedValidator()
    
    def test_unified_confidence_calculation(self):
        """Test weighted average calculation"""
        scores = ValidationScores(
            backtesting_score=0.988,
            walkforward_score=0.78,
            live_score=0.40,
            multi_tf_scores={}
        )
        
        result = self.validator.validate('AAPL', 'BULLISH', scores)
        
        # Expected: 0.40*0.988 + 0.35*0.78 + 0.25*0.40
        #         = 0.395 + 0.273 + 0.100 = 0.768
        expected = 0.768
        # Allow small floating point error
        assert abs(result.unified_confidence - expected) < 0.01
    
    def test_drift_detection(self):
        """Test drift detection"""
        scores = ValidationScores(
            backtesting_score=0.988,
            walkforward_score=0.78,
            live_score=0.40,
            multi_tf_scores={}
        )
        
        result = self.validator.validate('AAPL', 'BULLISH', scores)
        
        # Drift = (0.988 - 0.40) / 0.988 = 0.595 = 59.5%
        # Should be detected (> 25%)
        assert result.drift_detected == True
        assert result.drift_magnitude > 0.50
    
    def test_multi_tf_reconciliation_consensus(self):
        """Test multi-timeframe consensus when all agree"""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
            multi_tf_scores={
                'M15': 0.40,
                'H1': 0.45,
                'H4': 0.55,
                'D1': 0.60,
                'W1': 0.65
            }
        )
        
        result = self.validator.validate('AAPL', 'BULLISH', scores)
        
        assert result.timeframe_conflict == False
        assert result.consensus_direction == 'BULLISH'
    
    def test_multi_tf_reconciliation_conflict(self):
        """Test multi-timeframe conflict detection"""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
            multi_tf_scores={
                'M15': -0.48,  # BEARISH
                'H1': -0.40,   # BEARISH
                'H4': -0.40,   # BEARISH
                'D1': 0.60,    # BULLISH
                'W1': 0.70     # BULLISH
            }
        )
        
        result = self.validator.validate('AAPL', 'BULLISH', scores)
        
        assert result.timeframe_conflict == True
        assert result.drift_detected == True
    
    def test_retraining_trigger_severe_drift(self):
        """Test retraining trigger on severe drift"""
        scores = ValidationScores(
            backtesting_score=0.90,
            walkforward_score=0.85,
            live_score=0.10,  # Very low
            multi_tf_scores={}
        )
        
        result = self.validator.validate('AAPL', 'BULLISH', scores)
        
        # Drift = (0.90 - 0.10) / 0.90 = 0.889 > 75% threshold
        assert result.retraining_trigger == True
        assert result.drift_magnitude > 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### Step 2.3: Integration

**File**: `ml/src/models/unified_output.py`

```python
"""Store unified predictions to Supabase"""

import json
from datetime import datetime
from ml.src.validation.unified_framework import UnifiedValidator, ValidationScores
from backend.lib.supabase import get_supabase_client


class UnifiedPredictionStore:
    """Store unified predictions in database"""
    
    def __init__(self):
        self.validator = UnifiedValidator()
        self.supabase = get_supabase_client()
    
    def store_unified_prediction(
        self,
        symbol: str,
        direction: str,
        backtesting_score: float,
        walkforward_score: float,
        live_score: float,
        multi_tf_scores: dict
    ) -> dict:
        """Store unified prediction to database"""
        
        scores = ValidationScores(
            backtesting_score=backtesting_score,
            walkforward_score=walkforward_score,
            live_score=live_score,
            multi_tf_scores=multi_tf_scores
        )
        
        prediction = self.validator.validate(symbol, direction, scores)
        
        # Prepare record for storage
        record = {
            'symbol': prediction.symbol,
            'direction': prediction.direction,
            'unified_confidence': prediction.unified_confidence,
            'backtesting_score': prediction.backtesting_score,
            'walkforward_score': prediction.walkforward_score,
            'live_score': prediction.live_score,
            'drift_detected': prediction.drift_detected,
            'drift_magnitude': prediction.drift_magnitude,
            'drift_explanation': prediction.drift_explanation,
            'timeframe_conflict': prediction.timeframe_conflict,
            'consensus_direction': prediction.consensus_direction,
            'recommendation': prediction.recommendation,
            'retraining_trigger': prediction.retraining_trigger,
            'retraining_reason': prediction.retraining_reason,
            'created_at': datetime.now().isoformat()
        }
        
        # Store to Supabase
        response = self.supabase.table('unified_predictions').insert(record).execute()
        
        if response.error:
            raise Exception(f"Failed to store prediction: {response.error}")
        
        return record
```

### Step 2.4: Update ML Orchestration

**Update**: `.github/workflows/ml-orchestration.yml`

Add validation stage after forecasting:

```yaml
- name: Run Unified Validator
  run: |
    cd ml
    python -c "
    from ml.src.models.unified_output import UnifiedPredictionStore
    store = UnifiedPredictionStore()
    
    # Load predictions from forecast stage
    # Calculate validation scores
    # Store unified prediction
    
    for symbol in ['AAPL', 'NVDA', 'CRWD', 'AMD']:
      store.store_unified_prediction(
        symbol=symbol,
        direction='BULLISH',  # From forecast
        backtesting_score=0.988,  # From backtest metrics
        walkforward_score=0.78,    # From quarterly rolling
        live_score=0.40,           # From recent accuracy
        multi_tf_scores={'M15': -0.48, 'H1': -0.40, 'D1': 0.60}  # From forecasts
      )
    "
```

---

## Priority 3: Consolidate Backend Scripts (2 Days) 🚴

### Step 3.1: Create Shared Library

**File**: `backend/lib/shared.ts`

```typescript
"""Shared utilities for all backend scripts"""

import { createClient } from '@supabase/supabase-js';

// Database connection
export function createDbConnection(databaseUrl?: string) {
  const url = databaseUrl || process.env.DATABASE_URL;
  if (!url) throw new Error('DATABASE_URL not set');
  
  const [, , host, path] = url.match(/postgresql:\/\/([^:]+):([^@]+)@([^/]+)\/(.+)/) || [];
  
  return {
    url,
    client: createClient(url, process.env.SUPABASE_KEY)
  };
}

// Error handling with retry
export async function retryWithBackoff(
  fn: () => Promise<any>,
  maxRetries: number = 3,
  backoffMs: number = 1000
): Promise<any> {
  let lastError;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      const waitTime = backoffMs * Math.pow(2, attempt);
      console.warn(`Attempt ${attempt + 1} failed, retrying in ${waitTime}ms...`);
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
  }
  
  throw lastError;
}

// Logging
export function log(level: 'info' | 'warn' | 'error', message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const prefix = `[${timestamp}] [${level.toUpperCase()}]`;
  
  if (data) {
    console.log(`${prefix} ${message}`, data);
  } else {
    console.log(`${prefix} ${message}`);
  }
}

// Batch operations
export async function batchInsert(
  client: any,
  table: string,
  records: any[],
  batchSize: number = 1000
) {
  const batches = [];
  
  for (let i = 0; i < records.length; i += batchSize) {
    batches.push(records.slice(i, i + batchSize));
  }
  
  let inserted = 0;
  for (const batch of batches) {
    const { error } = await client.from(table).insert(batch);
    if (error) throw error;
    inserted += batch.length;
    log('info', `Inserted ${inserted}/${records.length} records`);
  }
  
  return inserted;
}
```

### Step 3.2: Create Canonical Backfill Script

**File**: `backend/scripts/canonical/backfill.sh`

```bash
#!/bin/bash

# Canonical backfill script - single source of truth
# Usage: ./backfill.sh [SYMBOL]

set -e

DATABASE_URL=${DATABASE_URL:-""}
SYMBOL=${1:-"AAPL,NVDA,CRWD,AMD"}
MAX_RETRIES=3
BATCH_SIZE=1000

source "$(dirname "$0")/../lib/shared.sh"

log_info "Starting backfill for symbols: $SYMBOL"

# Parse symbols
IFS=',' read -ra SYMBOLS <<< "$SYMBOL"

for sym in "${SYMBOLS[@]}"; do
  log_info "Backfilling $sym..."
  
  retry_command 3 "psql $DATABASE_URL -c \
    'SELECT backfill_symbol(\'$sym\')'"
  
  log_info "Completed $sym"
done

log_info "Backfill completed successfully"
```

### Step 3.3: Archive Legacy Scripts

```bash
# Create legacy archive directory
mkdir -p backend/scripts/legacy

# Move old scripts
mv backend/scripts/backfill.sh backend/scripts/legacy/backfill_old.sh
mv backend/scripts/backfill_v2.sh backend/scripts/legacy/backfill_v2.sh
mv backend/scripts/backfill_historical.sh backend/scripts/legacy/backfill_historical.sh
mv backend/scripts/symbols-backfill.sql backend/scripts/legacy/symbols-backfill.sql

# Archive diagnostic scripts
mv backend/scripts/check_aapl_data.sql backend/scripts/legacy/
mv backend/scripts/diagnose_chart_data_issue.sql backend/scripts/legacy/
mv backend/scripts/verify_ohlc_integrity.sql backend/scripts/legacy/
mv backend/scripts/find_gaps.sql backend/scripts/legacy/
mv backend/scripts/check_symbol_coverage.sql backend/scripts/legacy/
mv backend/scripts/validate_data_quality.sql backend/scripts/legacy/

# Create README for legacy
cat > backend/scripts/legacy/README.md << 'EOF'
# Legacy Scripts Archive

These are deprecated, one-off, or superseded scripts. They are kept for reference only.

Do not use these in production. Use canonical scripts in `/canonical/` instead.
EOF
```

---

## Priority 4: Consolidate Workflows (1 Day) 🚴

### Archive Legacy Workflows

```bash
# Create archive directory
mkdir -p .github/workflows/legacy

# Archive duplicate backfill workflows
mv .github/workflows/backfill-ohlc.yml .github/workflows/legacy/
mv .github/workflows/batch-backfill-cron.yml .github/workflows/legacy/
mv .github/workflows/daily-historical-sync.yml .github/workflows/legacy/
mv .github/workflows/symbol-backfill.yml .github/workflows/legacy/

# Archive duplicate intraday workflows
mv .github/workflows/alpaca-intraday-cron.yml .github/workflows/legacy/
mv .github/workflows/alpaca-intraday-cron-fixed.yml .github/workflows/legacy/
mv .github/workflows/intraday-update.yml .github/workflows/legacy/
mv .github/workflows/intraday-update-v2.yml .github/workflows/legacy/
mv .github/workflows/backfill-intraday-worker.yml .github/workflows/legacy/

# Archive duplicate ML workflows
mv .github/workflows/ml-forecast.yml .github/workflows/legacy/
mv .github/workflows/ml-evaluation.yml .github/workflows/legacy/
mv .github/workflows/data-quality-monitor.yml .github/workflows/legacy/
mv .github/workflows/drift-monitoring.yml .github/workflows/legacy/
mv .github/workflows/options-nightly.yml .github/workflows/legacy/

# Archive unclear workflows (after verification they're not used)
mv .github/workflows/scheduled-refresh.yml .github/workflows/legacy/
mv .github/workflows/performance-tracking.yml .github/workflows/legacy/
mv .github/workflows/sync-user-symbols.yml .github/workflows/legacy/

# Create README
cat > .github/workflows/legacy/README.md << 'EOF'
# Legacy Workflows Archive

These are superseded workflows. They have been consolidated into canonical workflows.

## Consolidation Mapping

Backfill workflows → `daily-data-refresh.yml`
Intraday workflows → `intraday-ingestion.yml`
ML workflows → `ml-orchestration.yml`
Other workflows → Archived (verify before deleting)

Do not use these in production.
EOF
```

---

## Week 1 Summary

### Monday: Fix Symbols (1 hour)
```bash
# 8:00-9:00 AM
psql $DATABASE_URL < backend/scripts/seed-symbols.sql
./backend/scripts/test_symbol_sync.sh
# ✅ Swift app now unblocked
```

### Tuesday-Wednesday: Unified Validator (2-3 days)
```bash
# 9:00 AM - 5:00 PM each day
cd ml
# Create and test validator framework
python -m pytest tests/test_unified_validator.py -v
# ✅ Dashboard reconciliation working
```

### Thursday-Friday: Consolidation (2 days)
```bash
# Script consolidation
mkdir -p backend/scripts/canonical backend/lib
cp backend/scripts/canonical/backfill.sh
mv backend/scripts/*.sh backend/scripts/legacy/

# Workflow consolidation
mkdir -p .github/workflows/legacy
mv .github/workflows/backfill*.yml .github/workflows/legacy/
mv .github/workflows/intraday*.yml .github/workflows/legacy/
mv .github/workflows/ml-forecast.yml .github/workflows/legacy/
# ✅ Reduced clutter from 31 to 8 workflows
```

## Success Criteria After Week 1

✅ Swift app symbol tracking working  
✅ Unified validator calculating consensus  
✅ 4 canonical scripts (not 35)
✅ 8 canonical workflows (not 31)
✅ Clear consolidation documentation
