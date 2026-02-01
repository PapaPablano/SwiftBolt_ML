#!/usr/bin/env python3
"""Analyze feature importances from trained models."""

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def load_model_and_show_importance(model_path: str) -> None:
    """Load a trained model and display feature importances."""
    print(f"\nLoading model: {model_path.split('/')[-1]}")
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
    
    # If it's a dictionary with ensemble structure
    if isinstance(model_data, dict):
        print(f"\nModel structure: {model_data.get('symbol', 'N/A')} - {model_data.get('timeframe', 'N/A')}")
        
        # Check if it has the ensemble format we expect
        if 'models' in model_data and 'feature_names' in model_data:
            models = model_data['models']
            feature_names = model_data['feature_names']
            weights = model_data.get('weights', {})
            
            print(f"Number of features: {model_data.get('n_features', len(feature_names))}")
            print(f"Ensemble models: {list(models.keys())}")
            print(f"Model weights: {weights}")
            
            if 'performances' in model_data:
                perfs = model_data['performances']
                print("\nModel performances:")
                for model_name, perf_dict in perfs.items():
                    train_acc = perf_dict.get('train_accuracy', perf_dict.get('train_acc', 'N/A'))
                    val_acc = perf_dict.get('val_accuracy', perf_dict.get('val_acc', 'N/A'))
                    if isinstance(train_acc, (int, float)) and isinstance(val_acc, (int, float)):
                        print(f"  {model_name}: train={train_acc:.3f}, val={val_acc:.3f}")
                    else:
                        print(f"  {model_name}: {perf_dict}")
            
            # Extract feature importances from each model and combine
            all_importances = {}
            
            for model_name, model_obj in models.items():
                if hasattr(model_obj, 'feature_importances_'):
                    importances = model_obj.feature_importances_
                    model_weight = weights.get(model_name, 1.0 / len(models))
                    
                    # Weight the importances by model weight
                    weighted_importances = importances * model_weight
                    
                    if model_name not in all_importances:
                        all_importances[model_name] = weighted_importances
            
            # Combine importances (average across models, weighted by their ensemble weights)
            if all_importances:
                combined_importances = np.zeros(len(feature_names))
                for model_name, importances in all_importances.items():
                    combined_importances += importances
                
                # Create dataframe and sort
                importance_df = pd.DataFrame({
                    'feature': feature_names,
                    'importance': combined_importances
                }).sort_values('importance', ascending=False)
                
                print(f"\n{'='*70}")
                print("TOP 15 FEATURE IMPORTANCES (Weighted Ensemble Average)")
                print(f"{'='*70}")
                print(f"{'Rank':>4}  {'Feature':<40} {'Importance':>10} {'%':>7}")
                print(f"{'-'*70}")
                
                total_importance = importance_df['importance'].sum()
                for i, (idx, row) in enumerate(importance_df.head(15).iterrows(), 1):
                    pct = (row['importance'] / total_importance * 100) if total_importance > 0 else 0
                    print(f"{i:>4}. {row['feature']:<40} {row['importance']:>10.6f} {pct:>6.2f}%")
                
                print(f"{'='*70}")
                
                # Show importances by model separately for comparison
                print("\n" + "="*70)
                print("Feature Importances by Individual Model")
                print("="*70)
                for model_name, model_obj in models.items():
                    if hasattr(model_obj, 'feature_importances_'):
                        importances = model_obj.feature_importances_
                        model_df = pd.DataFrame({
                            'feature': feature_names,
                            'importance': importances
                        }).sort_values('importance', ascending=False)
                        
                        print(f"\n{model_name.upper()} (weight={weights.get(model_name, 1.0):.2f}) - Top 5:")
                        for i, (idx, row) in enumerate(model_df.head(5).iterrows(), 1):
                            print(f"  {i}. {row['feature']:<35} {row['importance']:.6f}")
                
                return
        
        # Fallback: show what we have
        print("\nCouldn't parse ensemble structure. Keys available:")
        print(f"{list(model_data.keys())}")
        return
    
    # If it's not a dict, try other formats
    print(f"\nUnexpected model format: {type(model_data)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze feature importances from trained models.")
    parser.add_argument(
        "--models",
        nargs="+",
        metavar="PATH",
        help="Paths to .pkl model files. If omitted, use 3 most recent in ml/trained_models/.",
    )
    args = parser.parse_args()

    if args.models:
        model_files = [Path(p) for p in args.models]
        for p in model_files:
            if not p.exists():
                print(f"Error: file not found: {p}")
                sys.exit(1)
        print(f"Analyzing {len(model_files)} model(s)\n")
    else:
        model_dir = Path(__file__).parent / "trained_models"
        model_files = sorted(
            model_dir.glob("*.pkl"), key=lambda x: x.stat().st_mtime, reverse=True
        )
        if not model_files:
            print("No trained models found!")
            sys.exit(1)
        model_files = model_files[:3]
        print(f"Found {len(model_files)} trained models (3 most recent)\n")

    print("=" * 80)
    for model_path in model_files:
        try:
            load_model_and_show_importance(str(model_path))
            print("\n" + "=" * 80 + "\n")
        except Exception as e:
            print(f"Error loading {model_path.name}: {e}")
            import traceback
            traceback.print_exc()
            continue
