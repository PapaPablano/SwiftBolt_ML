"""Tests for volatility analysis module.

Run tests:
    cd ml
    pytest tests/test_volatility_analysis.py -v
    
    # With coverage
    pytest tests/test_volatility_analysis.py -v --cov=src/features/volatility_analysis
"""

import pytest
import numpy as np
import pandas as pd

from src.features.volatility_analysis import (
    VolatilityAnalyzer,
    VolatilityMetrics,
)


class TestVolatilityAnalyzer:
    """Test suite for VolatilityAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer fixture."""
        return VolatilityAnalyzer()
    
    @pytest.fixture
    def sample_prices(self):
        """Create sample price series."""
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
        # GBM simulation
        returns = np.random.randn(len(dates)) * 0.01
        prices = 100 * np.exp(np.cumsum(returns))
        return pd.Series(prices, index=dates)
    
    @pytest.fixture
    def sample_iv_history(self):
        """Create sample IV history."""
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
        # Mean-reverting IV
        iv = 0.25 + 0.05 * np.random.randn(len(dates)).cumsum() * 0.1
        iv = np.clip(iv, 0.10, 0.60)
        return pd.Series(iv, index=dates)
    
    def test_historical_volatility_basic(self, analyzer, sample_prices):
        """Test basic HV calculation."""
        hv = analyzer.calculate_historical_volatility(sample_prices, window=20)
        
        # Should be positive
        assert hv > 0
        
        # Should be reasonable (5% to 100%)
        assert 0.05 < hv < 1.0
    
    def test_historical_volatility_different_windows(self, analyzer, sample_prices):
        """Test HV with different lookback windows."""
        hv_10 = analyzer.calculate_historical_volatility(sample_prices, window=10)
        hv_20 = analyzer.calculate_historical_volatility(sample_prices, window=20)
        hv_30 = analyzer.calculate_historical_volatility(sample_prices, window=30)
        
        # All should be positive
        assert hv_10 > 0
        assert hv_20 > 0
        assert hv_30 > 0
        
        # Should be similar magnitudes (within reason)
        assert 0.5 < hv_10 / hv_30 < 2.0
    
    def test_historical_volatility_insufficient_data(self, analyzer):
        """Test HV with insufficient data."""
        # Only 5 data points
        prices = pd.Series([100, 101, 99, 102, 98])
        
        hv = analyzer.calculate_historical_volatility(prices, window=20)
        
        # Should still compute (uses all available)
        assert hv >= 0
    
    def test_historical_volatility_zero_volatility(self, analyzer):
        """Test HV with constant prices."""
        # Flat prices
        prices = pd.Series([100] * 100)
        
        hv = analyzer.calculate_historical_volatility(prices, window=20)
        
        # Should be zero or very close
        assert hv < 0.01
    
    def test_iv_rank_basic(self, analyzer, sample_iv_history):
        """Test basic IV rank calculation."""
        current_iv = 0.30
        
        iv_rank = analyzer.calculate_iv_rank(current_iv, sample_iv_history)
        
        # Should be in [0, 100]
        assert 0 <= iv_rank <= 100
    
    def test_iv_rank_at_extremes(self, analyzer, sample_iv_history):
        """Test IV rank at min and max."""
        min_iv = sample_iv_history.min()
        max_iv = sample_iv_history.max()
        
        # At minimum
        rank_min = analyzer.calculate_iv_rank(min_iv, sample_iv_history)
        assert rank_min == 0.0
        
        # At maximum
        rank_max = analyzer.calculate_iv_rank(max_iv, sample_iv_history)
        assert rank_max == 100.0
        
        # At midpoint
        mid_iv = (min_iv + max_iv) / 2
        rank_mid = analyzer.calculate_iv_rank(mid_iv, sample_iv_history)
        assert 45 < rank_mid < 55  # Should be near 50
    
    def test_iv_rank_outside_range(self, analyzer, sample_iv_history):
        """Test IV rank with values outside historical range."""
        max_iv = sample_iv_history.max()
        
        # Above max (should clip to 100)
        rank_high = analyzer.calculate_iv_rank(max_iv * 1.5, sample_iv_history)
        assert rank_high == 100.0
        
        # Below min (should clip to 0)
        min_iv = sample_iv_history.min()
        rank_low = analyzer.calculate_iv_rank(min_iv * 0.5, sample_iv_history)
        assert rank_low == 0.0
    
    def test_iv_rank_constant_history(self, analyzer):
        """Test IV rank with constant IV history."""
        # All same value
        iv_history = pd.Series([0.25] * 100)
        
        rank = analyzer.calculate_iv_rank(0.25, iv_history)
        
        # Should return 50 (neutral)
        assert rank == 50.0
    
    def test_iv_rank_empty_history(self, analyzer):
        """Test IV rank with empty history."""
        iv_history = pd.Series([], dtype=float)
        
        rank = analyzer.calculate_iv_rank(0.30, iv_history)
        
        # Should return 50 (neutral)
        assert rank == 50.0
    
    def test_iv_percentile_basic(self, analyzer, sample_iv_history):
        """Test basic IV percentile calculation."""
        current_iv = 0.30
        
        percentile = analyzer.calculate_iv_percentile(current_iv, sample_iv_history)
        
        # Should be in [0, 100]
        assert 0 <= percentile <= 100
    
    def test_iv_percentile_at_extremes(self, analyzer, sample_iv_history):
        """Test IV percentile at min and max."""
        min_iv = sample_iv_history.min()
        max_iv = sample_iv_history.max()
        
        # At minimum
        pct_min = analyzer.calculate_iv_percentile(min_iv, sample_iv_history)
        assert pct_min == 0.0
        
        # At maximum (should be very close to 100, may not be exactly due to ties)
        pct_max = analyzer.calculate_iv_percentile(max_iv, sample_iv_history)
        assert pct_max >= 99.0
    
    def test_iv_percentile_vs_rank(self, analyzer, sample_iv_history):
        """Test that percentile and rank are correlated but different."""
        current_iv = 0.30
        
        iv_rank = analyzer.calculate_iv_rank(current_iv, sample_iv_history)
        iv_percentile = analyzer.calculate_iv_percentile(current_iv, sample_iv_history)
        
        # Both should be in same ballpark
        assert abs(iv_rank - iv_percentile) < 30
        
        # But often different due to outliers
        # (Percentile is more robust)
    
    def test_expected_move_basic(self, analyzer):
        """Test basic expected move calculation."""
        move = analyzer.calculate_expected_move(
            stock_price=100,
            implied_vol=0.25,
            days_to_expiration=30
        )
        
        # Should contain all keys
        assert 'expected_move' in move
        assert 'expected_move_pct' in move
        assert 'upper_range' in move
        assert 'lower_range' in move
        assert 'upper_2sd' in move
        assert 'lower_2sd' in move
        
        # Expected move should be positive
        assert move['expected_move'] > 0
        
        # Upper should be above current, lower below
        assert move['upper_range'] > 100
        assert move['lower_range'] < 100
        
        # 2SD should be wider than 1SD
        assert move['upper_2sd'] > move['upper_range']
        assert move['lower_2sd'] < move['lower_range']
    
    def test_expected_move_scaling(self, analyzer):
        """Test that expected move scales correctly."""
        base_move = analyzer.calculate_expected_move(
            stock_price=100,
            implied_vol=0.25,
            days_to_expiration=30
        )
        
        # Double volatility
        double_vol_move = analyzer.calculate_expected_move(
            stock_price=100,
            implied_vol=0.50,
            days_to_expiration=30
        )
        
        # Should roughly double
        ratio = double_vol_move['expected_move'] / base_move['expected_move']
        assert 1.9 < ratio < 2.1
        
        # Double price
        double_price_move = analyzer.calculate_expected_move(
            stock_price=200,
            implied_vol=0.25,
            days_to_expiration=30
        )
        
        # Should roughly double
        ratio = double_price_move['expected_move'] / base_move['expected_move']
        assert 1.9 < ratio < 2.1
    
    def test_expected_move_time_decay(self, analyzer):
        """Test expected move decreases with time."""
        move_30d = analyzer.calculate_expected_move(
            stock_price=100,
            implied_vol=0.25,
            days_to_expiration=30
        )
        
        move_15d = analyzer.calculate_expected_move(
            stock_price=100,
            implied_vol=0.25,
            days_to_expiration=15
        )
        
        move_7d = analyzer.calculate_expected_move(
            stock_price=100,
            implied_vol=0.25,
            days_to_expiration=7
        )
        
        # Should decrease with time
        assert move_30d['expected_move'] > move_15d['expected_move']
        assert move_15d['expected_move'] > move_7d['expected_move']
    
    def test_expected_move_at_expiration(self, analyzer):
        """Test expected move at expiration."""
        move = analyzer.calculate_expected_move(
            stock_price=100,
            implied_vol=0.25,
            days_to_expiration=0
        )
        
        # Should be zero
        assert move['expected_move'] == 0.0
        assert move['upper_range'] == 100
        assert move['lower_range'] == 100
    
    def test_identify_vol_regime_all_levels(self, analyzer):
        """Test vol regime classification at all levels."""
        test_cases = [
            (5, 'extremely_low'),
            (15, 'low'),
            (35, 'normal'),
            (60, 'elevated'),
            (80, 'high'),
            (95, 'extremely_high'),
        ]
        
        for iv_percentile, expected_regime in test_cases:
            regime = analyzer.identify_vol_regime(iv_percentile=iv_percentile)
            assert regime == expected_regime
    
    def test_identify_vol_regime_prefers_percentile(self, analyzer):
        """Test that percentile is preferred over rank."""
        # Conflicting rank and percentile
        regime = analyzer.identify_vol_regime(
            iv_rank=10,  # Low
            iv_percentile=80  # High
        )
        
        # Should use percentile (high)
        assert regime == 'high'
    
    def test_identify_vol_regime_no_data(self, analyzer):
        """Test vol regime with no data."""
        regime = analyzer.identify_vol_regime()
        
        assert regime == 'unknown'
    
    def test_get_strategy_recommendations_all_regimes(self, analyzer):
        """Test strategy recommendations for all regimes."""
        regimes = [
            'extremely_low', 'low', 'normal', 
            'elevated', 'high', 'extremely_high', 'unknown'
        ]
        
        for regime in regimes:
            recs = analyzer.get_strategy_recommendations(regime)
            
            # Should have all required keys
            assert 'preferred' in recs
            assert 'avoid' in recs
            assert 'reasoning' in recs
            
            # Should have non-empty values
            assert len(recs['preferred']) > 0
            assert len(recs['avoid']) > 0
            assert len(recs['reasoning']) > 0
    
    def test_comprehensive_analysis(self, analyzer, sample_prices, sample_iv_history):
        """Test comprehensive volatility analysis."""
        current_iv = 0.30
        stock_price = float(sample_prices.iloc[-1])
        
        metrics = analyzer.analyze_comprehensive(
            current_iv=current_iv,
            prices=sample_prices,
            iv_history=sample_iv_history,
            stock_price=stock_price,
            days_to_expiration=30
        )
        
        # Should return VolatilityMetrics object
        assert isinstance(metrics, VolatilityMetrics)
        
        # All fields should be populated
        assert metrics.current_iv > 0
        assert metrics.historical_vol_20d >= 0
        assert metrics.historical_vol_30d >= 0
        assert 0 <= metrics.iv_rank <= 100
        assert 0 <= metrics.iv_percentile <= 100
        assert metrics.iv_high_52w > 0
        assert metrics.iv_low_52w > 0
        assert metrics.expected_move_1sd > 0
        assert metrics.expected_move_pct > 0
        assert len(metrics.vol_regime) > 0
        
        # High should be higher than low
        assert metrics.iv_high_52w >= metrics.iv_low_52w
    
    def test_volatility_metrics_string_repr(self, analyzer, sample_prices, sample_iv_history):
        """Test VolatilityMetrics string representation."""
        current_iv = 0.30
        stock_price = float(sample_prices.iloc[-1])
        
        metrics = analyzer.analyze_comprehensive(
            current_iv=current_iv,
            prices=sample_prices,
            iv_history=sample_iv_history,
            stock_price=stock_price
        )
        
        str_repr = str(metrics)
        
        # Should contain key metrics
        assert "Current IV:" in str_repr
        assert "HV 20-day:" in str_repr
        assert "IV Rank:" in str_repr
        assert "Expected Move:" in str_repr
        assert "Regime:" in str_repr


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.fixture
    def analyzer(self):
        return VolatilityAnalyzer()
    
    def test_very_high_volatility(self, analyzer):
        """Test with very high volatility."""
        # 200% annualized vol
        move = analyzer.calculate_expected_move(
            stock_price=100,
            implied_vol=2.0,
            days_to_expiration=30
        )
        
        # Should still produce valid result
        assert move['expected_move'] > 0
        assert not np.isnan(move['expected_move'])
    
    def test_very_low_volatility(self, analyzer):
        """Test with very low volatility."""
        # 1% annualized vol
        move = analyzer.calculate_expected_move(
            stock_price=100,
            implied_vol=0.01,
            days_to_expiration=30
        )
        
        # Should be very small but positive
        assert 0 < move['expected_move'] < 1.0
    
    def test_single_price_point(self, analyzer):
        """Test HV with single price."""
        prices = pd.Series([100])
        
        hv = analyzer.calculate_historical_volatility(prices, window=20)
        
        # Should return 0 (no variance)
        assert hv == 0.0
    
    def test_lookback_longer_than_history(self, analyzer):
        """Test with lookback > available history."""
        prices = pd.Series(100 + np.random.randn(50))
        
        # Request 252-day window with only 50 days
        hv = analyzer.calculate_historical_volatility(prices, window=252)
        
        # Should use all available
        assert hv >= 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--cov=src/features/volatility_analysis", "--cov-report=term-missing"])
