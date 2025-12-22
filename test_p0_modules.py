"""
Unit tests for P0 modules
"""

import unittest
import pandas as pd
import numpy as np
from pop_calculator import ProbabilityOfProfitCalculator
from earnings_analyzer import EarningsIVAnalyzer
from extrinsic_calculator import ExtrinsicIntrinsicCalculator
from pcr_analyzer import PutCallRatioAnalyzer


class TestPoPCalculator(unittest.TestCase):
    
    def setUp(self):
        self.calc = ProbabilityOfProfitCalculator()
    
    def test_pop_itm_call(self):
        """Test ITM call has high PoP"""
        pop = self.calc.calculate_pop(
            underlying_price=250, strike=245, side='call',
            bid=5.0, ask=5.5, delta=0.65, days_to_expiry=30
        )
        self.assertGreater(pop['pop_long'], 0.6)
    
    def test_pop_otm_call(self):
        """Test OTM call has low PoP"""
        pop = self.calc.calculate_pop(
            underlying_price=250, strike=260, side='call',
            bid=0.5, ask=0.7, delta=0.25, days_to_expiry=30
        )
        self.assertLess(pop['pop_long'], 0.4)
    
    def test_rr_ratio(self):
        """Test Risk/Reward calculation"""
        rr = self.calc.calculate_risk_reward_ratio(
            strike=250, underlying_price=250,
            bid=3.0, ask=3.2, side='call'
        )
        self.assertTrue(rr['favorable'])
        self.assertGreater(rr['risk_reward_ratio'], 1.5)


class TestEarningsAnalyzer(unittest.TestCase):
    
    def setUp(self):
        self.analyzer = EarningsIVAnalyzer()
    
    def test_pre_earnings_peak(self):
        """Test earnings IV detection"""
        earnings_data = self.analyzer.calculate_earnings_impact_on_iv(
            current_iv=0.45, historical_iv=0.28,
            days_to_earnings=3, days_to_expiry=7
        )
        self.assertEqual(earnings_data['iv_regime'], 'pre_earnings_peak')
        self.assertGreater(earnings_data['iv_crush_opportunity'], 0)
    
    def test_earnings_score(self):
        """Test earnings strategy scoring"""
        earnings_data = self.analyzer.calculate_earnings_impact_on_iv(
            current_iv=0.45, historical_iv=0.28,
            days_to_earnings=3, days_to_expiry=7
        )
        score = self.analyzer.score_earnings_strategy(
            earnings_data, side='call', expiration='2025-01-17',
            underlying_price=250, strike=250, strategy_type='sell_premium'
        )
        self.assertGreater(score, 0.7)


class TestExtrinsicCalculator(unittest.TestCase):
    
    def setUp(self):
        self.calc = ExtrinsicIntrinsicCalculator()
    
    def test_time_value_rich(self):
        """Test OTM call is time value rich"""
        ext_data = self.calc.calculate_extrinsic_intrinsic_ratio(
            strike=255, underlying_price=250, side='call',
            bid=2.0, ask=2.2, days_to_expiry=30
        )
        self.assertGreater(ext_data['extrinsic_ratio'], 0.9)
        self.assertEqual(ext_data['character'], 'time_value_rich')
    
    def test_intrinsic_rich(self):
        """Test deep ITM call is intrinsic rich"""
        ext_data = self.calc.calculate_extrinsic_intrinsic_ratio(
            strike=240, underlying_price=250, side='call',
            bid=9.8, ask=10.2, days_to_expiry=30
        )
        self.assertLess(ext_data['extrinsic_ratio'], 0.3)
        self.assertEqual(ext_data['character'], 'intrinsic_rich')


class TestPCRAnalyzer(unittest.TestCase):
    
    def setUp(self):
        self.analyzer = PutCallRatioAnalyzer()
    
    def test_pcr_analysis(self):
        """Test PCR calculation"""
        test_data = pd.DataFrame({
            'side': ['call'] * 5 + ['put'] * 8,
            'volume': [100] * 5 + [150, 120, 100, 80, 60, 50, 40, 30],
            'openInterest': [500] * 5 + [700, 600, 500, 400, 300, 200, 150, 100],
            'strike': [240, 245, 250, 255, 260] + [240, 245, 250, 255, 260, 265, 270, 275]
        })
        pcr_data = self.analyzer.analyze_put_call_ratio(test_data)
        self.assertGreater(pcr_data['pcr_composite'], 0)
        self.assertIn(pcr_data['sentiment'], [
            'extremely_bearish', 'bearish', 'slightly_bearish',
            'slightly_bullish', 'bullish', 'extremely_bullish'
        ])


if __name__ == '__main__':
    unittest.main()
