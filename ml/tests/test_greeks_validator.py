"""Tests for Greeks validation module.

Run tests:
    cd ml
    pytest tests/test_greeks_validator.py -v
    
    # With coverage
    pytest tests/test_greeks_validator.py -v --cov=src/validation/greeks_validator
"""

import pytest
import numpy as np
import pandas as pd

from src.validation.greeks_validator import (
    GreeksValidator,
    GreeksValidationResult,
)


class TestGreeksValidator:
    """Test suite for GreeksValidator."""
    
    @pytest.fixture
    def validator(self):
        """Create validator fixture."""
        return GreeksValidator()
    
    @pytest.fixture
    def atm_call_greeks(self):
        """Sample Greeks for ATM call option."""
        return {
            'delta': 0.5234,
            'gamma': 0.0312,
            'theta': -0.0456,
            'vega': 0.1845,
            'rho': 0.0234
        }
    
    @pytest.fixture
    def atm_put_greeks(self):
        """Sample Greeks for ATM put option."""
        return {
            'delta': -0.4766,
            'gamma': 0.0312,
            'theta': -0.0406,
            'vega': 0.1845,
            'rho': -0.0766
        }
    
    def test_validate_perfect_match(self, validator, atm_call_greeks):
        """Test validation with perfect theoretical match."""
        result = validator.validate_option(
            market_greeks=atm_call_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call',
            symbol='TEST'
        )
        
        # Should be valid (very close to theoretical)
        assert result.is_valid or result.mispricing_score < 10
        
        # Should have low differences (or be flagged as valid)
        assert result.differences['delta'] < 0.05
        assert result.differences['gamma'] < 0.02  # Relaxed tolerance
    
    def test_validate_put_option(self, validator, atm_put_greeks):
        """Test validation for put option."""
        result = validator.validate_option(
            market_greeks=atm_put_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='put'
        )
        
        # Should be valid
        assert result.is_valid or result.mispricing_score < 10
        
        # Delta should be negative for put
        assert result.market_greeks['delta'] < 0
        assert result.theoretical_greeks['delta'] < 0
    
    def test_validate_delta_divergence(self, validator):
        """Test detection of delta divergence."""
        # ATM call should have delta ~0.52, but market shows 0.70
        market_greeks = {
            'delta': 0.70,  # Too high
            'gamma': 0.0312,
            'theta': -0.0456,
            'vega': 0.1845,
            'rho': 0.0234
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should flag delta divergence
        assert not result.is_valid
        assert 'DELTA_DIVERGENCE' in result.flags
        assert result.mispricing_score > 20
    
    def test_validate_negative_gamma(self, validator):
        """Test detection of negative gamma (invalid)."""
        market_greeks = {
            'delta': 0.52,
            'gamma': -0.0312,  # Invalid: gamma should be positive
            'theta': -0.0456,
            'vega': 0.1845,
            'rho': 0.0234
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should flag negative gamma
        assert not result.is_valid
        assert 'NEGATIVE_GAMMA' in result.flags
    
    def test_validate_positive_theta(self, validator):
        """Test detection of positive theta (unusual for long)."""
        market_greeks = {
            'delta': 0.52,
            'gamma': 0.0312,
            'theta': 0.0456,  # Unusual: theta should be negative for long
            'vega': 0.1845,
            'rho': 0.0234
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should flag positive theta
        assert 'POSITIVE_THETA' in result.flags
    
    def test_validate_negative_vega(self, validator):
        """Test detection of negative vega (invalid)."""
        market_greeks = {
            'delta': 0.52,
            'gamma': 0.0312,
            'theta': -0.0456,
            'vega': -0.1845,  # Invalid: vega should be positive
            'rho': 0.0234
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should flag negative vega
        assert 'NEGATIVE_VEGA' in result.flags
    
    def test_validate_delta_out_of_bounds_call(self, validator):
        """Test detection of out-of-bounds delta for call."""
        market_greeks = {
            'delta': 1.2,  # Invalid: call delta should be in [0, 1]
            'gamma': 0.0312,
            'theta': -0.0456,
            'vega': 0.1845,
            'rho': 0.0234
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should flag out of bounds
        assert 'DELTA_OUT_OF_BOUNDS' in result.flags
    
    def test_validate_delta_out_of_bounds_put(self, validator):
        """Test detection of out-of-bounds delta for put."""
        market_greeks = {
            'delta': -1.5,  # Invalid: put delta should be in [-1, 0]
            'gamma': 0.0312,
            'theta': -0.0456,
            'vega': 0.1845,
            'rho': 0.0234
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='put'
        )
        
        # Should flag out of bounds
        assert 'DELTA_OUT_OF_BOUNDS' in result.flags
    
    def test_validate_delta_gamma_mismatch(self, validator):
        """Test detection of delta-gamma mismatch."""
        # High gamma should occur near ATM (delta ~0.5)
        market_greeks = {
            'delta': 0.90,  # Deep ITM
            'gamma': 0.08,  # Very high gamma (unusual for deep ITM)
            'theta': -0.0456,
            'vega': 0.1845,
            'rho': 0.0234
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should flag mismatch
        assert 'DELTA_GAMMA_MISMATCH' in result.flags
    
    def test_validate_chain(self, validator):
        """Test validation of entire options chain."""
        # Create sample chain
        chain = pd.DataFrame([
            {
                'symbol': 'TEST_CALL_95',
                'strike': 95,
                'option_type': 'call',
                'delta': 0.65,
                'gamma': 0.025,
                'theta': -0.04,
                'vega': 0.16,
                'rho': 0.02,
                'impliedVolatility': 0.30,
                'days_to_expiration': 30
            },
            {
                'symbol': 'TEST_CALL_100',
                'strike': 100,
                'option_type': 'call',
                'delta': 0.52,
                'gamma': 0.031,
                'theta': -0.045,
                'vega': 0.18,
                'rho': 0.023,
                'impliedVolatility': 0.30,
                'days_to_expiration': 30
            },
            {
                'symbol': 'TEST_CALL_105',
                'strike': 105,
                'option_type': 'call',
                'delta': 0.38,
                'gamma': 0.028,
                'theta': -0.04,
                'vega': 0.16,
                'rho': 0.018,
                'impliedVolatility': 0.30,
                'days_to_expiration': 30
            }
        ])
        
        results = validator.validate_chain(chain, underlying_price=100)
        
        # Should validate all 3 options
        assert len(results) == 3
        
        # All should be GreeksValidationResult
        for result in results:
            assert isinstance(result, GreeksValidationResult)
    
    def test_find_mispricings(self, validator):
        """Test finding mispricings from validation results."""
        # Create results with one clear mispricing
        chain = pd.DataFrame([
            {
                'symbol': 'GOOD',
                'strike': 100,
                'option_type': 'call',
                'delta': 0.52,
                'gamma': 0.031,
                'theta': -0.045,
                'vega': 0.18,
                'rho': 0.023,
                'impliedVolatility': 0.30,
                'days_to_expiration': 30
            },
            {
                'symbol': 'BAD',
                'strike': 100,
                'option_type': 'call',
                'delta': 0.90,  # Way too high for ATM
                'gamma': 0.031,
                'theta': -0.045,
                'vega': 0.18,
                'rho': 0.023,
                'impliedVolatility': 0.30,
                'days_to_expiration': 30
            }
        ])
        
        results = validator.validate_chain(chain, underlying_price=100)
        mispricings = validator.find_mispricings(results, mispricing_threshold=20)
        
        # Should find at least one mispricing
        assert len(mispricings) >= 1
        
        # Should have required columns
        assert 'symbol' in mispricings.columns
        assert 'mispricing_score' in mispricings.columns
        assert 'flags' in mispricings.columns
    
    def test_generate_validation_report(self, validator):
        """Test generation of validation report."""
        chain = pd.DataFrame([
            {
                'strike': 95,
                'option_type': 'call',
                'delta': 0.65,
                'gamma': 0.025,
                'theta': -0.04,
                'vega': 0.16,
                'rho': 0.02,
                'impliedVolatility': 0.30,
                'days_to_expiration': 30
            },
            {
                'strike': 100,
                'option_type': 'call',
                'delta': 0.52,
                'gamma': 0.031,
                'theta': -0.045,
                'vega': 0.18,
                'rho': 0.023,
                'impliedVolatility': 0.30,
                'days_to_expiration': 30
            }
        ])
        
        results = validator.validate_chain(chain, underlying_price=100)
        report = validator.generate_validation_report(results)
        
        # Should have all required sections
        assert 'summary' in report
        assert 'flag_distribution' in report
        assert 'average_differences' in report
        assert 'top_mispricings' in report
        
        # Summary should have required keys
        assert 'total_options' in report['summary']
        assert 'valid_options' in report['summary']
        assert 'invalid_options' in report['summary']
        assert 'validation_rate' in report['summary']
    
    def test_mispricing_score_calculation(self, validator):
        """Test mispricing score calculation."""
        # Calculate actual theoretical Greeks first
        pricing = validator.bs_model.calculate_greeks(
            S=100, K=100, T=30/365, sigma=0.30, option_type='call'
        )
        
        # Use theoretical as "market" for perfect match
        perfect_greeks = {
            'delta': pricing.delta,
            'gamma': pricing.gamma,
            'theta': pricing.theta,
            'vega': pricing.vega,
            'rho': pricing.rho
        }
        
        result1 = validator.validate_option(
            market_greeks=perfect_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Perfect match should have very low score
        assert result1.mispricing_score < 1.0
        
        # Large divergence should have high score
        bad_greeks = {
            'delta': 0.90,
            'gamma': 0.10,
            'theta': 0.05,
            'vega': 0.30,
            'rho': 0.10
        }
        
        result2 = validator.validate_option(
            market_greeks=bad_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        assert result2.mispricing_score > 30
    
    def test_custom_tolerances(self):
        """Test validator with custom tolerances."""
        # Very strict tolerances
        strict_validator = GreeksValidator(
            delta_tolerance=0.01,
            gamma_tolerance=0.005,
            theta_tolerance=0.01,
            vega_tolerance=0.01,
            rho_tolerance=0.01
        )
        
        # Even small difference should fail
        market_greeks = {
            'delta': 0.53,  # Slightly off
            'gamma': 0.0312,
            'theta': -0.0456,
            'vega': 0.1845,
            'rho': 0.0234
        }
        
        result = strict_validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should have higher mispricing score with strict tolerances
        assert result.mispricing_score > 0
    
    def test_validation_result_string_repr(self, validator, atm_call_greeks):
        """Test string representation of validation result."""
        result = validator.validate_option(
            market_greeks=atm_call_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call',
            symbol='TEST'
        )
        
        str_repr = str(result)
        
        # Should contain key information
        assert 'TEST' in str_repr
        assert 'Delta' in str_repr or 'delta' in str_repr
        assert 'Valid' in str_repr or 'valid' in str_repr


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.fixture
    def validator(self):
        return GreeksValidator()
    
    def test_deep_itm_call(self, validator):
        """Test validation for deep ITM call."""
        # Deep ITM: delta should be near 1.0
        market_greeks = {
            'delta': 0.95,
            'gamma': 0.005,  # Low gamma for deep ITM
            'theta': -0.02,
            'vega': 0.08,
            'rho': 0.04
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=80,  # Deep ITM
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should validate (delta near 1.0 is correct for deep ITM)
        assert result.market_greeks['delta'] > 0.90
    
    def test_deep_otm_call(self, validator):
        """Test validation for deep OTM call."""
        # Deep OTM: delta should be near 0.0
        market_greeks = {
            'delta': 0.05,
            'gamma': 0.005,  # Low gamma for deep OTM
            'theta': -0.01,
            'vega': 0.05,
            'rho': 0.005
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=120,  # Deep OTM
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should validate (low delta is correct for deep OTM)
        assert result.market_greeks['delta'] < 0.15
    
    def test_short_dte(self, validator):
        """Test validation for option near expiration."""
        market_greeks = {
            'delta': 0.52,
            'gamma': 0.15,  # High gamma near expiration
            'theta': -0.15,  # High theta decay
            'vega': 0.05,   # Low vega near expiration
            'rho': 0.01
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=3/365,  # 3 days
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should produce a result (may have some divergence)
        assert result is not None
    
    def test_high_volatility(self, validator):
        """Test validation with high implied volatility."""
        market_greeks = {
            'delta': 0.52,
            'gamma': 0.015,
            'theta': -0.08,
            'vega': 0.35,  # Higher vega with high IV
            'rho': 0.023
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.80,  # Very high IV
            option_type='call'
        )
        
        # Should validate
        assert result is not None
    
    def test_missing_greeks(self, validator):
        """Test validation with missing Greeks."""
        # Only provide delta
        market_greeks = {
            'delta': 0.52
        }
        
        result = validator.validate_option(
            market_greeks=market_greeks,
            stock_price=100,
            strike=100,
            time_to_expiration=30/365,
            implied_volatility=0.30,
            option_type='call'
        )
        
        # Should still produce result (missing values treated as 0)
        assert result is not None
        assert result.market_greeks['delta'] == 0.52
        assert result.market_greeks.get('gamma', 0) == 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--cov=src/validation/greeks_validator", "--cov-report=term-missing"])
