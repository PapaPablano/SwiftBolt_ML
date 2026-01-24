"""Tests for Black-Scholes options pricing model.

Run tests:
    cd ml
    pytest tests/test_options_pricing.py -v
    
    # With coverage
    pytest tests/test_options_pricing.py -v --cov=src/models/options_pricing
"""

import pytest
import numpy as np

from src.models.options_pricing import (
    BlackScholesModel,
    OptionsPricing,
    get_current_risk_free_rate,
)


class TestBlackScholesModel:
    """Test suite for Black-Scholes pricing model."""
    
    @pytest.fixture
    def bs_model(self):
        """Create standard Black-Scholes model fixture."""
        return BlackScholesModel(risk_free_rate=0.05)
    
    def test_initialization(self):
        """Test model initialization with different risk-free rates."""
        bs = BlackScholesModel(risk_free_rate=0.03)
        assert bs.risk_free_rate == 0.03
        
        # Default rate
        bs_default = BlackScholesModel()
        assert bs_default.risk_free_rate == 0.05
    
    def test_call_pricing_atm(self, bs_model):
        """Test ATM call option pricing."""
        price = bs_model.price_call(S=100, K=100, T=1.0, sigma=0.20)
        
        # ATM call with 1 year, 20% vol should be around $10.45
        assert 10.0 < price < 11.0
        
        # More precise check
        assert abs(price - 10.45) < 0.5
    
    def test_put_pricing_atm(self, bs_model):
        """Test ATM put option pricing."""
        price = bs_model.price_put(S=100, K=100, T=1.0, sigma=0.20)
        
        # ATM put with 1 year, 20% vol should be around $5.57
        assert 5.0 < price < 6.5
        
        # More precise check  
        assert abs(price - 5.57) < 0.5
    
    def test_call_pricing_itm(self, bs_model):
        """Test ITM call option pricing."""
        # 10% ITM call (S=110, K=100)
        price = bs_model.price_call(S=110, K=100, T=1.0, sigma=0.20)
        
        # Should be worth at least intrinsic value
        intrinsic = 110 - 100
        assert price >= intrinsic
        
        # Should have time value
        time_value = price - intrinsic
        assert time_value > 0
    
    def test_put_pricing_itm(self, bs_model):
        """Test ITM put option pricing."""
        # 10% ITM put (S=90, K=100)
        price = bs_model.price_put(S=90, K=100, T=1.0, sigma=0.20)
        
        # Should be worth at least intrinsic value
        intrinsic = 100 - 90
        assert price >= intrinsic
        
        # Should have time value
        time_value = price - intrinsic
        assert time_value > 0
    
    def test_pricing_at_expiration(self, bs_model):
        """Test option pricing at expiration (T=0)."""
        # ITM call at expiration
        call_price = bs_model.price_call(S=110, K=100, T=0, sigma=0.20)
        assert call_price == 10.0  # Exactly intrinsic value
        
        # OTM call at expiration
        call_price = bs_model.price_call(S=90, K=100, T=0, sigma=0.20)
        assert call_price == 0.0
        
        # ITM put at expiration
        put_price = bs_model.price_put(S=90, K=100, T=0, sigma=0.20)
        assert put_price == 10.0  # Exactly intrinsic value
        
        # OTM put at expiration
        put_price = bs_model.price_put(S=110, K=100, T=0, sigma=0.20)
        assert put_price == 0.0
    
    def test_put_call_parity(self, bs_model):
        """Test put-call parity: C - P = S - K*e^(-rT)."""
        S, K, T, sigma = 100, 100, 1.0, 0.25
        
        call = bs_model.price_call(S, K, T, sigma)
        put = bs_model.price_put(S, K, T, sigma)
        
        lhs = call - put
        rhs = S - K * np.exp(-bs_model.risk_free_rate * T)
        
        # Should be equal within floating point precision
        assert abs(lhs - rhs) < 0.01
        
        # Use built-in verification method
        assert bs_model.verify_put_call_parity(S, K, T, sigma)
    
    def test_greeks_call_atm(self, bs_model):
        """Test Greeks calculation for ATM call."""
        pricing = bs_model.calculate_greeks(
            S=100, K=100, T=1.0, sigma=0.20, option_type='call'
        )
        
        # Delta: ATM call should be around 0.60-0.65 (slightly > 0.5 due to drift)
        assert 0.60 < pricing.delta < 0.70
        
        # Gamma: Should be positive and moderate
        assert 0.01 < pricing.gamma < 0.05
        
        # Theta: Should be negative (time decay)
        assert pricing.theta < 0
        
        # Vega: Should be positive (benefits from increased vol)
        assert pricing.vega > 0
        
        # Rho: Should be positive for calls
        assert pricing.rho > 0
    
    def test_greeks_put_atm(self, bs_model):
        """Test Greeks calculation for ATM put."""
        pricing = bs_model.calculate_greeks(
            S=100, K=100, T=1.0, sigma=0.20, option_type='put'
        )
        
        # Delta: ATM put should be around -0.35 to -0.40 (call_delta - 1)
        assert -0.40 < pricing.delta < -0.30
        
        # Gamma: Should be positive (same as call)
        assert 0.01 < pricing.gamma < 0.05
        
        # Theta: Should be negative (time decay)
        assert pricing.theta < 0
        
        # Vega: Should be positive (same as call)
        assert pricing.vega > 0
        
        # Rho: Should be negative for puts
        assert pricing.rho < 0
    
    def test_greeks_at_expiration(self, bs_model):
        """Test Greeks at expiration."""
        # ITM call
        pricing = bs_model.calculate_greeks(
            S=110, K=100, T=0, sigma=0.20, option_type='call'
        )
        assert pricing.delta == 1.0
        assert pricing.gamma == 0.0
        assert pricing.theta == 0.0
        assert pricing.vega == 0.0
        
        # OTM call
        pricing = bs_model.calculate_greeks(
            S=90, K=100, T=0, sigma=0.20, option_type='call'
        )
        assert pricing.delta == 0.0
    
    def test_delta_range(self, bs_model):
        """Test delta stays within valid range [-1, 1]."""
        test_cases = [
            {'S': 80, 'K': 100, 'T': 0.5, 'sigma': 0.30, 'type': 'call'},
            {'S': 100, 'K': 100, 'T': 0.5, 'sigma': 0.30, 'type': 'call'},
            {'S': 120, 'K': 100, 'T': 0.5, 'sigma': 0.30, 'type': 'call'},
            {'S': 80, 'K': 100, 'T': 0.5, 'sigma': 0.30, 'type': 'put'},
            {'S': 100, 'K': 100, 'T': 0.5, 'sigma': 0.30, 'type': 'put'},
            {'S': 120, 'K': 100, 'T': 0.5, 'sigma': 0.30, 'type': 'put'},
        ]
        
        for case in test_cases:
            pricing = bs_model.calculate_greeks(
                S=case['S'], K=case['K'], T=case['T'], 
                sigma=case['sigma'], option_type=case['type']
            )
            assert -1.0 <= pricing.delta <= 1.0
    
    def test_implied_volatility_basic(self, bs_model):
        """Test basic implied volatility calculation."""
        # Calculate theoretical price at known volatility
        true_sigma = 0.25
        market_price = bs_model.price_call(S=100, K=100, T=1.0, sigma=true_sigma)
        
        # Recover IV
        calculated_iv = bs_model.calculate_implied_volatility(
            market_price=market_price,
            S=100, K=100, T=1.0,
            option_type='call'
        )
        
        # Should match original volatility
        assert abs(calculated_iv - true_sigma) < 0.001
    
    def test_implied_volatility_put(self, bs_model):
        """Test IV calculation for put options."""
        true_sigma = 0.30
        market_price = bs_model.price_put(S=100, K=100, T=1.0, sigma=true_sigma)
        
        calculated_iv = bs_model.calculate_implied_volatility(
            market_price=market_price,
            S=100, K=100, T=1.0,
            option_type='put'
        )
        
        assert abs(calculated_iv - true_sigma) < 0.001
    
    def test_implied_volatility_itm(self, bs_model):
        """Test IV calculation for ITM options."""
        true_sigma = 0.35
        market_price = bs_model.price_call(S=110, K=100, T=0.5, sigma=true_sigma)
        
        calculated_iv = bs_model.calculate_implied_volatility(
            market_price=market_price,
            S=110, K=100, T=0.5,
            option_type='call'
        )
        
        assert abs(calculated_iv - true_sigma) < 0.001
    
    def test_implied_volatility_invalid_inputs(self, bs_model):
        """Test IV calculation handles invalid inputs."""
        # Negative price
        with pytest.raises(ValueError, match="must be positive"):
            bs_model.calculate_implied_volatility(
                market_price=-5.0,
                S=100, K=100, T=1.0,
                option_type='call'
            )
        
        # Call price > stock price
        with pytest.raises(ValueError, match="cannot exceed stock price"):
            bs_model.calculate_implied_volatility(
                market_price=110.0,
                S=100, K=100, T=1.0,
                option_type='call'
            )
        
        # Put price > strike
        with pytest.raises(ValueError, match="cannot exceed strike"):
            bs_model.calculate_implied_volatility(
                market_price=110.0,
                S=100, K=100, T=1.0,
                option_type='put'
            )
    
    def test_implied_volatility_expired(self, bs_model):
        """Test IV calculation for expired options."""
        iv = bs_model.calculate_implied_volatility(
            market_price=10.0,
            S=110, K=100, T=0,
            option_type='call'
        )
        
        # Should return 0 for expired options
        assert iv == 0.0
    
    def test_volatility_smile(self, bs_model):
        """Test IV calculation across different strikes (volatility smile)."""
        S = 100
        T = 0.25
        true_sigma = 0.25
        
        strikes = [80, 90, 100, 110, 120]
        ivs = []
        
        for K in strikes:
            market_price = bs_model.price_call(S, K, T, true_sigma)
            iv = bs_model.calculate_implied_volatility(
                market_price=market_price,
                S=S, K=K, T=T,
                option_type='call'
            )
            ivs.append(iv)
        
        # All should be close to true_sigma (no smile in BS model)
        for iv in ivs:
            assert abs(iv - true_sigma) < 0.01
    
    def test_price_monotonicity_time(self, bs_model):
        """Test that option prices decrease with time to expiration."""
        times = [1.0, 0.5, 0.25, 0.1]
        prices = []
        
        for T in times:
            price = bs_model.price_call(S=100, K=100, T=T, sigma=0.20)
            prices.append(price)
        
        # Prices should decrease as expiration approaches
        for i in range(len(prices) - 1):
            assert prices[i] > prices[i+1]
    
    def test_price_monotonicity_volatility(self, bs_model):
        """Test that option prices increase with volatility."""
        volatilities = [0.10, 0.20, 0.30, 0.40]
        call_prices = []
        put_prices = []
        
        for sigma in volatilities:
            call_price = bs_model.price_call(S=100, K=100, T=1.0, sigma=sigma)
            put_price = bs_model.price_put(S=100, K=100, T=1.0, sigma=sigma)
            call_prices.append(call_price)
            put_prices.append(put_price)
        
        # Both call and put prices should increase with volatility
        for i in range(len(call_prices) - 1):
            assert call_prices[i] < call_prices[i+1]
            assert put_prices[i] < put_prices[i+1]
    
    def test_string_representation(self, bs_model):
        """Test OptionsPricing string representation."""
        pricing = bs_model.calculate_greeks(
            S=100, K=100, T=1.0, sigma=0.20, option_type='call'
        )
        
        str_repr = str(pricing)
        
        # Should contain all Greeks
        assert "Price:" in str_repr
        assert "Delta:" in str_repr
        assert "Gamma:" in str_repr
        assert "Theta:" in str_repr
        assert "Vega:" in str_repr
        assert "Rho:" in str_repr


class TestRiskFreeRate:
    """Test risk-free rate utilities."""
    
    def test_get_current_risk_free_rate(self):
        """Test current risk-free rate retrieval."""
        rate = get_current_risk_free_rate()
        
        # Should be a reasonable positive number (0.5% to 10%)
        assert 0.005 < rate < 0.10
        
        # Should be float
        assert isinstance(rate, float)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_very_high_volatility(self):
        """Test pricing with very high volatility."""
        bs = BlackScholesModel()
        
        # 200% volatility (extreme but possible)
        price = bs.price_call(S=100, K=100, T=1.0, sigma=2.0)
        
        # Should still produce valid result
        assert price > 0
        assert not np.isnan(price)
        assert not np.isinf(price)
    
    def test_very_low_volatility(self):
        """Test pricing with very low volatility."""
        bs = BlackScholesModel()
        
        # 1% volatility
        price = bs.price_call(S=100, K=100, T=1.0, sigma=0.01)
        
        # Should be close to intrinsic value
        assert price > 0
        assert not np.isnan(price)
    
    def test_very_short_expiration(self):
        """Test pricing with very short time to expiration."""
        bs = BlackScholesModel()
        
        # 1 day to expiration
        price = bs.price_call(S=100, K=100, T=1/365, sigma=0.20)
        
        # Should be small but positive
        assert 0 < price < 1
    
    def test_deep_itm_call(self):
        """Test deep ITM call option."""
        bs = BlackScholesModel()
        
        # Very deep ITM (S=150, K=100)
        price = bs.price_call(S=150, K=100, T=1.0, sigma=0.20)
        
        # Price should be close to S - K*e^(-rT)
        expected = 150 - 100 * np.exp(-0.05 * 1.0)
        assert abs(price - expected) < 1.0
        
        # Delta should be close to 1.0
        pricing = bs.calculate_greeks(S=150, K=100, T=1.0, sigma=0.20, option_type='call')
        assert pricing.delta > 0.95
    
    def test_deep_otm_call(self):
        """Test deep OTM call option."""
        bs = BlackScholesModel()
        
        # Very deep OTM (S=100, K=150)
        price = bs.price_call(S=100, K=150, T=1.0, sigma=0.20)
        
        # Price should be very small
        assert 0 < price < 1.0
        
        # Delta should be close to 0
        pricing = bs.calculate_greeks(S=100, K=150, T=1.0, sigma=0.20, option_type='call')
        assert pricing.delta < 0.10


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--cov=src/models/options_pricing", "--cov-report=term-missing"])
