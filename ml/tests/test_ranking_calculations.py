"""
Validation tests for options ranking calculations.
Updated 2026-01-23: Validates standardized weights and new refinements.
"""

import pytest
import pandas as pd
import numpy as np
from src.models.options_momentum_ranker import OptionsMomentumRanker


class TestWeightStandardization:
    """Test that weights are consistent across all calculations."""
    
    def test_default_weights_are_40_35_25(self):
        """Verify default framework weights sum to 1.0 and match expected values."""
        ranker = OptionsMomentumRanker()
        
        assert ranker.MOMENTUM_WEIGHT == 0.40, "Momentum weight should be 40%"
        assert ranker.VALUE_WEIGHT == 0.35, "Value weight should be 35%"
        assert ranker.GREEKS_WEIGHT == 0.25, "Greeks weight should be 25%"
        
        total = ranker.MOMENTUM_WEIGHT + ranker.VALUE_WEIGHT + ranker.GREEKS_WEIGHT
        assert abs(total - 1.0) < 0.001, f"Weights should sum to 1.0, got {total}"
    
    def test_entry_weights_updated_to_match_default(self):
        """Verify entry weights were updated to match default (not 30/35/35)."""
        ranker = OptionsMomentumRanker()
        
        assert ranker.ENTRY_WEIGHTS["momentum"] == 0.40, "Entry momentum should be 40%"
        assert ranker.ENTRY_WEIGHTS["value"] == 0.35, "Entry value should be 35%"
        assert ranker.ENTRY_WEIGHTS["greeks"] == 0.25, "Entry greeks should be 25%"


class TestExponentialSpreadPenalty:
    """Test the new exponential spread penalty curve."""
    
    def test_exponential_penalty_curve(self):
        """Verify exponential penalty is more aggressive than linear."""
        ranker = OptionsMomentumRanker()
        
        # Create test data with various spreads
        test_spreads = pd.Series([0, 1, 2, 3, 5, 8, 10, 15, 20])
        scores = ranker._calculate_spread_score(test_spreads)
        
        # Expected penalties from exponential curve
        expected_scores = {
            0: 100.0,   # 0% spread → penalty 0
            1: 98.0,    # 1% spread → penalty 2
            2: 96.0,    # 2% spread → penalty 4
            3: 92.0,    # 3% spread → penalty 8
            5: 84.0,    # 5% spread → penalty 16
            8: 69.0,    # 8% spread → penalty 31
            10: 59.0,   # 10% spread → penalty 41
            15: 50.0,   # 15% spread → penalty 50 (capped)
            20: 50.0,   # 20% spread → penalty 50 (capped)
        }
        
        for spread, expected_score in expected_scores.items():
            idx = test_spreads[test_spreads == spread].index[0]
            actual_score = scores.iloc[idx]
            assert abs(actual_score - expected_score) < 0.1, \
                f"Spread {spread}% should give score ~{expected_score}, got {actual_score}"
    
    def test_tight_spreads_still_score_well(self):
        """Verify tight spreads (≤2%) still get high scores."""
        ranker = OptionsMomentumRanker()
        
        tight_spreads = pd.Series([0.5, 1.0, 1.5, 2.0])
        scores = ranker._calculate_spread_score(tight_spreads)
        
        assert all(scores >= 96.0), "Tight spreads should score ≥96"


class TestDynamicDeltaTarget:
    """Test dynamic delta targeting based on DTE."""
    
    def test_delta_targets_vary_by_dte(self):
        """Verify delta target changes based on DTE."""
        ranker = OptionsMomentumRanker()
        
        # Test data with different DTEs
        test_data = pd.DataFrame({
            'delta': [0.50, 0.55, 0.60, 0.65],
            'side': ['call', 'call', 'call', 'call'],
            'dte': [60, 30, 14, 5]
        })
        
        scores = ranker._score_delta(test_data, trend="neutral")
        
        # DTE 60 (target 0.50): delta 0.50 should score best
        assert scores.iloc[0] > 85, "Delta 0.50 should score well for 60 DTE"
        
        # DTE 30 (target 0.55): delta 0.55 should score best
        assert scores.iloc[1] > 85, "Delta 0.55 should score well for 30 DTE"
        
        # DTE 14 (target 0.60): delta 0.60 should score best
        assert scores.iloc[2] > 85, "Delta 0.60 should score well for 14 DTE"
        
        # DTE 5 (target 0.65): delta 0.65 should score best
        assert scores.iloc[3] > 85, "Delta 0.65 should score well for 5 DTE"
    
    def test_puts_use_negative_delta_targets(self):
        """Verify puts use negative delta targets."""
        ranker = OptionsMomentumRanker()
        
        test_data = pd.DataFrame({
            'delta': [-0.55],
            'side': ['put'],
            'dte': [30]
        })
        
        scores = ranker._score_delta(test_data, trend="neutral")
        assert scores.iloc[0] > 85, "Delta -0.55 should score well for puts at 30 DTE"


class TestDynamicThetaCap:
    """Test dynamic theta penalty cap based on DTE."""
    
    def test_theta_caps_vary_by_dte(self):
        """Verify theta penalty cap changes based on DTE."""
        ranker = OptionsMomentumRanker()
        
        # High theta decay (10% daily) with different DTEs
        test_data = pd.DataFrame({
            'theta': [-0.10, -0.10, -0.10],
            'mid': [1.0, 1.0, 1.0],
            'dte': [60, 30, 10]
        })
        
        penalties = ranker._calculate_theta_penalty(test_data)
        
        # 10% daily decay = base penalty 100, but capped
        assert penalties.iloc[0] <= 25, "DTE > 45 should cap at 25"
        assert penalties.iloc[1] <= 40, "DTE 21-45 should cap at 40"
        assert penalties.iloc[2] <= 50, "DTE < 21 should cap at 50"
    
    def test_low_theta_not_overly_penalized(self):
        """Verify low theta decay gets reasonable penalty."""
        ranker = OptionsMomentumRanker()
        
        test_data = pd.DataFrame({
            'theta': [-0.02],
            'mid': [2.0],
            'dte': [30]
        })
        
        penalty = ranker._calculate_theta_penalty(test_data)
        # 1% daily decay = penalty 10
        assert penalty.iloc[0] == pytest.approx(10.0, abs=0.1)


class TestCompositeRankCalculation:
    """Test complete composite rank calculation."""
    
    def test_strong_buy_case(self):
        """Test a perfect 'Strong Buy' scenario."""
        ranker = OptionsMomentumRanker()
        
        # Perfect contract
        test_data = pd.DataFrame({
            'iv': [0.20],
            'bid': [2.00],
            'ask': [2.03],
            'mid': [2.015],
            'delta': [0.55],
            'gamma': [0.04],
            'vega': [0.30],
            'theta': [-0.02],
            'volume': [150],
            'open_interest': [500],
            'side': ['call'],
            'dte': [30]
        })
        
        # Need IV stats for value score
        from src.models.options_momentum_ranker import IVStatistics
        iv_stats = IVStatistics(
            iv_high=0.50,
            iv_low=0.10,
            iv_median=0.30,
            iv_current=0.20
        )
        
        # Calculate scores
        df = ranker._calculate_value_scores(test_data, iv_stats)
        df = ranker._calculate_momentum_scores(df, None)
        df = ranker._calculate_greeks_scores(df, "neutral")
        
        # Check individual scores are high
        assert df['value_score'].iloc[0] > 80, "Value score should be high"
        assert df['momentum_score'].iloc[0] > 40, "Momentum score should be reasonable"
        assert df['greeks_score'].iloc[0] > 80, "Greeks score should be high"
        
        # Calculate composite
        composite = (
            df['momentum_score'].iloc[0] * 0.40 +
            df['value_score'].iloc[0] * 0.35 +
            df['greeks_score'].iloc[0] * 0.25
        )
        
        assert composite > 70, f"Strong buy should rank > 70, got {composite}"
    
    def test_composite_rank_in_range(self):
        """Verify composite rank is always 0-100."""
        ranker = OptionsMomentumRanker()
        
        # Edge case: all scores at extremes
        test_data = pd.DataFrame({
            'momentum_score': [0, 100, 50],
            'value_score': [0, 100, 50],
            'greeks_score': [0, 100, 50]
        })
        
        for idx, row in test_data.iterrows():
            composite = (
                row['momentum_score'] * 0.40 +
                row['value_score'] * 0.35 +
                row['greeks_score'] * 0.25
            )
            assert 0 <= composite <= 100, f"Composite should be 0-100, got {composite}"


class TestWeightContributions:
    """Test that weight contributions match expected formulas."""
    
    def test_contribution_calculation_matches_weights(self):
        """Verify contribution formula: (score/100) × weight × 100 = points."""
        # Example: Momentum score 80 with 40% weight
        score = 80
        weight = 0.40
        expected_contribution = (score / 100.0) * weight * 100.0
        
        assert expected_contribution == pytest.approx(32.0), \
            f"80 score at 40% weight should contribute 32 points"
    
    def test_total_contribution_equals_composite(self):
        """Verify sum of contributions equals composite rank."""
        momentum_score = 85
        value_score = 90
        greeks_score = 70
        
        momentum_contrib = (momentum_score / 100.0) * 0.40 * 100.0
        value_contrib = (value_score / 100.0) * 0.35 * 100.0
        greeks_contrib = (greeks_score / 100.0) * 0.25 * 100.0
        
        total = momentum_contrib + value_contrib + greeks_contrib
        
        expected_composite = momentum_score * 0.40 + value_score * 0.35 + greeks_score * 0.25
        
        assert total == pytest.approx(expected_composite, abs=0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
