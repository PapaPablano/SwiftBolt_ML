#!/usr/bin/env python3
"""
Verify Model Weights and Calibration System
============================================

This script verifies that the symbol_model_weights table is properly calibrated
and that the intraday calibration system is functioning correctly.

Usage:
    python verify_model_weights.py --symbol AAPL
    python verify_model_weights.py --symbol NVDA --horizon 1D
    python verify_model_weights.py --all  # Check all symbols
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from supabase import Client, create_client

# Add parent directory to path
ml_dir = Path(__file__).parent.parent
sys.path.insert(0, str(ml_dir))

try:
    from config.database import get_supabase_client
except ImportError:
    # Fallback if config not available
    def get_supabase_client() -> Client:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        return create_client(url, key)


class WeightVerifier:
    """Verifies model weights and calibration system."""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        
    def get_symbol_id(self, symbol: str) -> Optional[str]:
        """Get symbol_id from ticker."""
        result = self.supabase.table("symbols").select("id").eq("ticker", symbol.upper()).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]["id"]
        return None
        
    def get_model_weights(self, symbol: str, horizon: str = None) -> List[Dict]:
        """Get current model weights for a symbol."""
        symbol_id = self.get_symbol_id(symbol)
        if not symbol_id:
            print(f"❌ Symbol {symbol} not found")
            return []
            
        query = self.supabase.table("symbol_model_weights").select("*").eq("symbol_id", symbol_id)
        
        if horizon:
            query = query.eq("horizon", horizon)
            
        result = query.execute()
        return result.data
        
    def get_intraday_calibration_stats(self, symbol: str) -> Dict:
        """Get intraday calibration statistics."""
        symbol_id = self.get_symbol_id(symbol)
        if not symbol_id:
            return {}
            
        # Use the function from migration
        result = self.supabase.rpc(
            "get_intraday_calibration_data",
            {"p_symbol_id": symbol_id, "p_lookback_hours": 72}
        ).execute()
        
        return result.data if result.data else []
        
    def get_recent_evaluations(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get recent forecast evaluations."""
        symbol_id = self.get_symbol_id(symbol)
        if not symbol_id:
            return []
            
        result = self.supabase.table("ml_forecast_evaluations_intraday")\
            .select("*")\
            .eq("symbol_id", symbol_id)\
            .order("evaluated_at", desc=True)\
            .limit(limit)\
            .execute()
            
        return result.data
        
    def get_pending_forecasts(self, symbol: str = None) -> List[Dict]:
        """Get pending intraday forecasts waiting for evaluation."""
        result = self.supabase.rpc("get_pending_intraday_evaluations").execute()
        
        if symbol and result.data:
            return [f for f in result.data if f["symbol"] == symbol.upper()]
        return result.data if result.data else []
        
    def verify_weight_structure(self, weights: Dict) -> Dict[str, any]:
        """Verify the structure of synth_weights JSONB."""
        issues = []
        
        synth_weights = weights.get("synth_weights", {})
        
        # Check for layer_weights key
        if "layer_weights" not in synth_weights:
            issues.append("Missing 'layer_weights' in synth_weights")
        else:
            layer_weights = synth_weights["layer_weights"]
            
            # Check for required components
            required_components = ["supertrend_component", "sr_component", "ensemble_component"]
            for component in required_components:
                if component not in layer_weights:
                    issues.append(f"Missing '{component}' in layer_weights")
                else:
                    value = layer_weights[component]
                    if not isinstance(value, (int, float)):
                        issues.append(f"{component} is not numeric: {type(value)}")
                    elif value < 0 or value > 1:
                        issues.append(f"{component} is out of range [0, 1]: {value}")
                        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "synth_weights": synth_weights
        }
        
    def print_weight_summary(self, symbol: str, horizon: str = None):
        """Print detailed weight summary."""
        weights_list = self.get_model_weights(symbol, horizon)
        
        if not weights_list:
            print(f"\n❌ No weights found for {symbol}")
            return
            
        print(f"\n{'='*70}")
        print(f"Model Weights for {symbol.upper()}")
        print(f"{'='*70}\n")
        
        for weights in weights_list:
            print(f"Horizon: {weights['horizon']}")
            print(f"Last Updated: {weights['last_updated']}")
            print(f"Calibration Source: {weights.get('calibration_source', 'N/A')}")
            print(f"Intraday Samples: {weights.get('intraday_sample_count', 0)}")
            print(f"Intraday Accuracy: {weights.get('intraday_accuracy', 'N/A')}")
            
            # Verify structure
            verification = self.verify_weight_structure(weights)
            
            if verification["valid"]:
                print("\n✅ Weight Structure: VALID")
                layer_weights = weights["synth_weights"]["layer_weights"]
                print("\nLayer Weights:")
                print(f"  SuperTrend Component:  {layer_weights['supertrend_component']:.4f}")
                print(f"  S/R Component:         {layer_weights['sr_component']:.4f}")
                print(f"  Ensemble Component:    {layer_weights['ensemble_component']:.4f}")
                
                # Check if weights sum to 1 (or close to it)
                total = sum([
                    layer_weights['supertrend_component'],
                    layer_weights['sr_component'],
                    layer_weights['ensemble_component']
                ])
                print(f"\n  Total Weight Sum:      {total:.4f}")
                if abs(total - 1.0) > 0.01:
                    print(f"  ⚠️  Weights don't sum to 1.0 (difference: {abs(total - 1.0):.4f})")
            else:
                print("\n❌ Weight Structure: INVALID")
                for issue in verification["issues"]:
                    print(f"  - {issue}")
                    
            # RF/GB weights if present
            if weights.get("rf_weight") or weights.get("gb_weight"):
                print("\nTraditional Model Weights:")
                print(f"  Random Forest: {weights.get('rf_weight', 'N/A')}")
                print(f"  Gradient Boost: {weights.get('gb_weight', 'N/A')}")
                
            print(f"\n{'-'*70}\n")
            
    def print_calibration_stats(self, symbol: str):
        """Print intraday calibration statistics."""
        stats = self.get_intraday_calibration_stats(symbol)
        
        if not stats:
            print(f"\n⚠️  No calibration data found for {symbol}")
            return
            
        print(f"\n{'='*70}")
        print(f"Intraday Calibration Statistics for {symbol.upper()}")
        print(f"{'='*70}\n")
        
        for stat in stats:
            print(f"Horizon: {stat['horizon']}")
            print(f"Total Forecasts: {stat['total_forecasts']}")
            print(f"Direction Accuracy: {stat['direction_accuracy']:.2%}")
            print(f"Avg Price Error: {stat['avg_price_error_pct']:.2%}")
            print(f"\nComponent Accuracies:")
            print(f"  SuperTrend: {stat['supertrend_accuracy']:.2%}")
            print(f"  S/R Containment: {stat['sr_containment_rate']:.2%}")
            print(f"  Ensemble: {stat['ensemble_accuracy']:.2%}")
            print(f"\n{'-'*70}\n")
            
    def print_recent_evaluations(self, symbol: str, limit: int = 10):
        """Print recent forecast evaluations."""
        evals = self.get_recent_evaluations(symbol, limit)
        
        if not evals:
            print(f"\n⚠️  No recent evaluations found for {symbol}")
            return
            
        print(f"\n{'='*70}")
        print(f"Recent Evaluations for {symbol.upper()} (Last {len(evals)})")
        print(f"{'='*70}\n")
        
        df = pd.DataFrame(evals)
        
        # Summary stats
        print(f"Direction Accuracy: {df['direction_correct'].mean():.2%}")
        print(f"Avg Price Error: {df['price_error_pct'].abs().mean():.2%}")
        print(f"\nComponent Performance:")
        print(f"  SuperTrend Accuracy: {df['supertrend_direction_correct'].mean():.2%}")
        print(f"  S/R Containment: {df['sr_containment'].mean():.2%}")
        print(f"  Ensemble Accuracy: {df['ensemble_direction_correct'].mean():.2%}")
        
        print(f"\nRecent Evaluations:")
        print(df[['horizon', 'evaluated_at', 'direction_correct', 'price_error_pct']].to_string(index=False))
        print()
        
    def check_system_health(self):
        """Check overall system health."""
        print(f"\n{'='*70}")
        print("System Health Check")
        print(f"{'='*70}\n")
        
        # Check for weights
        result = self.supabase.table("symbol_model_weights").select("count", count="exact").execute()
        weights_count = result.count if hasattr(result, 'count') else 0
        print(f"Total Weight Entries: {weights_count}")
        
        # Check for recent evaluations
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        result = self.supabase.table("ml_forecast_evaluations_intraday")\
            .select("count", count="exact")\
            .gte("evaluated_at", cutoff)\
            .execute()
        recent_evals = result.count if hasattr(result, 'count') else 0
        print(f"Evaluations (Last 24h): {recent_evals}")
        
        # Check for pending forecasts
        pending = self.get_pending_forecasts()
        print(f"Pending Evaluations: {len(pending)}")
        
        # Check for calibration freshness
        result = self.supabase.table("symbol_model_weights")\
            .select("last_updated, calibration_source, intraday_sample_count")\
            .order("last_updated", desc=True)\
            .limit(5)\
            .execute()
            
        if result.data:
            print(f"\nMost Recent Weight Updates:")
            for row in result.data:
                # Parse the timestamp (handle both Z and +00:00 formats)
                last_updated_str = row['last_updated']
                if last_updated_str.endswith('Z'):
                    last_updated_str = last_updated_str.replace('Z', '+00:00')
                last_updated = datetime.fromisoformat(last_updated_str)
                
                # Use timezone-aware now() for comparison
                now = datetime.now(timezone.utc)
                age = now - last_updated
                hours_ago = age.total_seconds() / 3600
                print(f"  - {hours_ago:.1f}h ago | Source: {row['calibration_source']} | Samples: {row['intraday_sample_count']}")
                
        print()
        
    def verify_all_symbols(self):
        """Verify weights for all symbols."""
        result = self.supabase.table("symbol_model_weights")\
            .select("symbol_id, horizon, synth_weights")\
            .execute()
            
        if not result.data:
            print("❌ No weights found in database")
            return
            
        print(f"\n{'='*70}")
        print(f"Verifying {len(result.data)} Weight Entries")
        print(f"{'='*70}\n")
        
        issues_found = 0
        for entry in result.data:
            verification = self.verify_weight_structure(entry)
            if not verification["valid"]:
                issues_found += 1
                print(f"❌ Symbol ID: {entry['symbol_id']}, Horizon: {entry['horizon']}")
                for issue in verification["issues"]:
                    print(f"   - {issue}")
                    
        if issues_found == 0:
            print("✅ All weight entries are structurally valid")
        else:
            print(f"\n⚠️  Found {issues_found} entries with issues")


def main():
    parser = argparse.ArgumentParser(description="Verify model weights and calibration")
    parser.add_argument("--symbol", type=str, help="Symbol to verify (e.g., AAPL)")
    parser.add_argument("--horizon", type=str, help="Horizon to check (e.g., 1D)")
    parser.add_argument("--all", action="store_true", help="Verify all symbols")
    parser.add_argument("--health", action="store_true", help="Show system health")
    parser.add_argument("--evaluations", action="store_true", help="Show recent evaluations")
    parser.add_argument("--calibration", action="store_true", help="Show calibration stats")
    
    args = parser.parse_args()
    
    verifier = WeightVerifier()
    
    try:
        if args.all:
            verifier.verify_all_symbols()
        elif args.health:
            verifier.check_system_health()
        elif args.symbol:
            verifier.print_weight_summary(args.symbol, args.horizon)
            
            if args.calibration:
                verifier.print_calibration_stats(args.symbol)
                
            if args.evaluations:
                verifier.print_recent_evaluations(args.symbol)
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
