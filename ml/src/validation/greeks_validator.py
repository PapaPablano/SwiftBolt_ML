"""Greeks Validation Against Theoretical Black-Scholes Values.

Validates market-reported Greeks (from Alpaca/market data) against theoretical
Black-Scholes Greeks to identify:
- Data quality issues
- Potential mispricings
- Arbitrage opportunities
- Model risk

Usage:
    from src.validation.greeks_validator import GreeksValidator
    
    validator = GreeksValidator()
    
    # Validate single option
    result = validator.validate_option(
        market_greeks={'delta': 0.52, 'gamma': 0.03, 'theta': -0.25, 'vega': 0.18},
        stock_price=100,
        strike=105,
        time_to_expiration=30/365,
        risk_free_rate=0.05,
        implied_volatility=0.30,
        option_type='call'
    )
    
    # Validate entire chain
    results = validator.validate_chain(options_df, underlying_price)
    
    # Identify mispricings
    mispricings = validator.find_mispricings(results, threshold=0.20)

References:
    - Hull, J. (2021). "Options, Futures, and Other Derivatives" (11th ed.)
    - Haug, E. (2007). "The Complete Guide to Option Pricing Formulas"
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..models.options_pricing import BlackScholesModel

logger = logging.getLogger(__name__)


@dataclass
class GreeksValidationResult:
    """Results of Greeks validation for a single option.
    
    Attributes:
        symbol: Option symbol
        strike: Strike price
        expiration: Expiration date
        option_type: 'call' or 'put'
        market_greeks: Greeks from market data
        theoretical_greeks: Greeks from Black-Scholes
        differences: Absolute differences
        percent_differences: Percentage differences
        is_valid: Whether Greeks pass validation
        flags: List of issues detected
        mispricing_score: 0-100, higher = more likely mispriced
    """
    symbol: str
    strike: float
    expiration: str
    option_type: str
    market_greeks: Dict[str, float]
    theoretical_greeks: Dict[str, float]
    differences: Dict[str, float]
    percent_differences: Dict[str, float]
    is_valid: bool
    flags: List[str]
    mispricing_score: float
    
    def __str__(self) -> str:
        """Human-readable representation."""
        flags_str = ", ".join(self.flags) if self.flags else "None"
        return (
            f"GreeksValidation({self.symbol}):\n"
            f"  Strike: {self.strike}, Type: {self.option_type}\n"
            f"  Valid: {self.is_valid}, Mispricing Score: {self.mispricing_score:.1f}\n"
            f"  Delta: Market={self.market_greeks.get('delta', 0):.3f}, "
            f"Theoretical={self.theoretical_greeks.get('delta', 0):.3f}, "
            f"Diff={self.differences.get('delta', 0):.3f}\n"
            f"  Flags: {flags_str}"
        )


class GreeksValidator:
    """Validate market Greeks against theoretical Black-Scholes values.
    
    Identifies data quality issues, potential mispricings, and model risk.
    """
    
    def __init__(
        self,
        delta_tolerance: float = 0.10,
        gamma_tolerance: float = 0.05,
        theta_tolerance: float = 0.15,
        vega_tolerance: float = 0.15,
        rho_tolerance: float = 0.20,
        risk_free_rate: float = 0.05
    ):
        """Initialize Greeks validator.
        
        Args:
            delta_tolerance: Max acceptable delta difference (e.g., 0.10 = 10%)
            gamma_tolerance: Max acceptable gamma difference
            theta_tolerance: Max acceptable theta difference
            vega_tolerance: Max acceptable vega difference
            rho_tolerance: Max acceptable rho difference
            risk_free_rate: Risk-free rate for Black-Scholes (default: 5%)
        """
        self.bs_model = BlackScholesModel(risk_free_rate=risk_free_rate)
        self.tolerances = {
            'delta': delta_tolerance,
            'gamma': gamma_tolerance,
            'theta': theta_tolerance,
            'vega': vega_tolerance,
            'rho': rho_tolerance
        }
    
    def validate_option(
        self,
        market_greeks: Dict[str, float],
        stock_price: float,
        strike: float,
        time_to_expiration: float,
        implied_volatility: float,
        option_type: str,
        symbol: str = "",
        expiration: str = ""
    ) -> GreeksValidationResult:
        """Validate Greeks for a single option.
        
        Args:
            market_greeks: Greeks from market data (delta, gamma, theta, vega, rho)
            stock_price: Current underlying price
            strike: Option strike price
            time_to_expiration: Time to expiration (years)
            implied_volatility: Implied volatility (annualized)
            option_type: 'call' or 'put'
            symbol: Option symbol (optional, for reporting)
            expiration: Expiration date (optional, for reporting)
        
        Returns:
            GreeksValidationResult with comparison details
        """
        # Calculate theoretical Greeks using stored risk_free_rate
        pricing = self.bs_model.calculate_greeks(
            S=stock_price,
            K=strike,
            T=time_to_expiration,
            sigma=implied_volatility,
            option_type=option_type
        )
        
        # Convert OptionsPricing to dict for comparison
        theoretical_greeks = {
            'delta': pricing.delta,
            'gamma': pricing.gamma,
            'theta': pricing.theta,
            'vega': pricing.vega,
            'rho': pricing.rho
        }
        
        # Calculate differences
        differences = {}
        percent_differences = {}
        flags = []
        
        for greek in ['delta', 'gamma', 'theta', 'vega', 'rho']:
            market_val = market_greeks.get(greek, 0)
            theo_val = theoretical_greeks.get(greek, 0)
            
            # Absolute difference
            diff = abs(market_val - theo_val)
            differences[greek] = diff
            
            # Percentage difference (use larger value as denominator)
            denom = max(abs(theo_val), abs(market_val), 1e-6)
            pct_diff = (diff / denom) * 100
            percent_differences[greek] = pct_diff
            
            # Check tolerance
            if diff > self.tolerances[greek]:
                flags.append(f"{greek.upper()}_DIVERGENCE")
        
        # Special checks
        
        # 1. Delta bounds check
        market_delta = market_greeks.get('delta', 0)
        if option_type == 'call' and not (0 <= market_delta <= 1):
            flags.append("DELTA_OUT_OF_BOUNDS")
        elif option_type == 'put' and not (-1 <= market_delta <= 0):
            flags.append("DELTA_OUT_OF_BOUNDS")
        
        # 2. Gamma should be positive
        market_gamma = market_greeks.get('gamma', 0)
        if market_gamma < 0:
            flags.append("NEGATIVE_GAMMA")
        
        # 3. Theta should be negative for long positions
        market_theta = market_greeks.get('theta', 0)
        if market_theta > 0:
            flags.append("POSITIVE_THETA")
        
        # 4. Vega should be positive
        market_vega = market_greeks.get('vega', 0)
        if market_vega < 0:
            flags.append("NEGATIVE_VEGA")
        
        # 5. Delta-gamma relationship
        # High gamma should correspond to ATM options (delta ~0.5 for calls, ~-0.5 for puts)
        if market_gamma > 0.05:  # High gamma
            expected_delta = 0.5 if option_type == 'call' else -0.5
            if abs(market_delta - expected_delta) > 0.30:
                flags.append("DELTA_GAMMA_MISMATCH")
        
        # Calculate mispricing score (0-100)
        # Weighted by Greek importance for pricing
        weights = {'delta': 0.30, 'gamma': 0.20, 'theta': 0.20, 'vega': 0.20, 'rho': 0.10}
        mispricing_score = sum(
            min(percent_differences.get(greek, 0) / self.tolerances[greek] * 100, 100) * weights[greek]
            for greek in weights
        )
        mispricing_score = min(mispricing_score, 100)
        
        # Determine if valid
        is_valid = len(flags) == 0
        
        return GreeksValidationResult(
            symbol=symbol,
            strike=strike,
            expiration=expiration,
            option_type=option_type,
            market_greeks=market_greeks,
            theoretical_greeks=theoretical_greeks,
            differences=differences,
            percent_differences=percent_differences,
            is_valid=is_valid,
            flags=flags,
            mispricing_score=mispricing_score
        )
    
    def validate_chain(
        self,
        options_df: pd.DataFrame,
        underlying_price: float
    ) -> List[GreeksValidationResult]:
        """Validate Greeks for entire options chain.
        
        Args:
            options_df: Options chain with columns:
                - strike, expiration, option_type
                - delta, gamma, theta, vega, rho (market Greeks)
                - impliedVolatility
            underlying_price: Current underlying price
        
        Returns:
            List of GreeksValidationResult objects
        """
        results = []
        
        for _, row in options_df.iterrows():
            # Calculate time to expiration
            if 'days_to_expiration' in row:
                time_to_expiration = row['days_to_expiration'] / 365
            elif 'expiration' in row:
                # Parse expiration date
                try:
                    exp_date = pd.to_datetime(row['expiration'])
                    today = pd.Timestamp.now()
                    time_to_expiration = (exp_date - today).days / 365
                except Exception as e:
                    logger.warning(f"Could not parse expiration date: {e}")
                    time_to_expiration = 30 / 365  # Default to 30 days
            else:
                time_to_expiration = 30 / 365
            
            # Skip if expired
            if time_to_expiration <= 0:
                continue
            
            # Extract market Greeks
            market_greeks = {
                'delta': row.get('delta', 0),
                'gamma': row.get('gamma', 0),
                'theta': row.get('theta', 0),
                'vega': row.get('vega', 0),
                'rho': row.get('rho', 0)
            }
            
            # Validate
            try:
                result = self.validate_option(
                    market_greeks=market_greeks,
                    stock_price=underlying_price,
                    strike=row['strike'],
                    time_to_expiration=time_to_expiration,
                    implied_volatility=row.get('impliedVolatility', 0.30),
                    option_type=row.get('option_type', 'call'),
                    symbol=row.get('symbol', ''),
                    expiration=str(row.get('expiration', ''))
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"Could not validate option {row.get('symbol', 'unknown')}: {e}")
        
        return results
    
    def find_mispricings(
        self,
        validation_results: List[GreeksValidationResult],
        mispricing_threshold: float = 30.0,
        min_flags: int = 1
    ) -> pd.DataFrame:
        """Identify potential mispricings from validation results.
        
        Args:
            validation_results: List of GreeksValidationResult objects
            mispricing_threshold: Min mispricing score to flag (0-100)
            min_flags: Minimum number of flags to consider
        
        Returns:
            DataFrame with potential mispricings, sorted by score
        """
        mispricings = []
        
        for result in validation_results:
            if result.mispricing_score >= mispricing_threshold or len(result.flags) >= min_flags:
                mispricings.append({
                    'symbol': result.symbol,
                    'strike': result.strike,
                    'expiration': result.expiration,
                    'option_type': result.option_type,
                    'mispricing_score': result.mispricing_score,
                    'flags': ', '.join(result.flags),
                    'delta_diff': result.differences.get('delta', 0),
                    'gamma_diff': result.differences.get('gamma', 0),
                    'theta_diff': result.differences.get('theta', 0),
                    'vega_diff': result.differences.get('vega', 0),
                    'market_delta': result.market_greeks.get('delta', 0),
                    'theo_delta': result.theoretical_greeks.get('delta', 0),
                })
        
        df = pd.DataFrame(mispricings)
        
        if not df.empty:
            df = df.sort_values('mispricing_score', ascending=False)
        
        return df
    
    def generate_validation_report(
        self,
        validation_results: List[GreeksValidationResult]
    ) -> Dict[str, any]:
        """Generate comprehensive validation report.
        
        Args:
            validation_results: List of GreeksValidationResult objects
        
        Returns:
            Dictionary with summary statistics and findings
        """
        if not validation_results:
            return {'error': 'No validation results provided'}
        
        total_options = len(validation_results)
        valid_options = sum(1 for r in validation_results if r.is_valid)
        invalid_options = total_options - valid_options
        
        # Collect all flags
        all_flags = []
        for result in validation_results:
            all_flags.extend(result.flags)
        
        # Count flag occurrences
        flag_counts = {}
        for flag in set(all_flags):
            flag_counts[flag] = all_flags.count(flag)
        
        # Average differences by Greek
        avg_differences = {}
        for greek in ['delta', 'gamma', 'theta', 'vega', 'rho']:
            diffs = [r.differences.get(greek, 0) for r in validation_results]
            avg_differences[greek] = np.mean(diffs)
        
        # Average mispricing score
        avg_mispricing_score = np.mean([r.mispricing_score for r in validation_results])
        
        # Top mispricings
        sorted_results = sorted(validation_results, key=lambda r: r.mispricing_score, reverse=True)
        top_mispricings = sorted_results[:10]
        
        return {
            'summary': {
                'total_options': total_options,
                'valid_options': valid_options,
                'invalid_options': invalid_options,
                'validation_rate': (valid_options / total_options * 100) if total_options > 0 else 0,
                'avg_mispricing_score': avg_mispricing_score
            },
            'flag_distribution': flag_counts,
            'average_differences': avg_differences,
            'top_mispricings': [
                {
                    'symbol': r.symbol,
                    'strike': r.strike,
                    'mispricing_score': r.mispricing_score,
                    'flags': r.flags
                }
                for r in top_mispricings
            ]
        }


if __name__ == "__main__":
    # Example usage and self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Greeks Validator - Self Test")
    print("=" * 70)
    
    validator = GreeksValidator()
    
    # Test 1: Validate perfect match
    print("\n📊 Test 1: Perfect Match (Theoretical = Market)")
    market_greeks = {
        'delta': 0.5234,
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
        risk_free_rate=0.05,
        implied_volatility=0.30,
        option_type='call',
        symbol='TEST_CALL_100'
    )
    
    print(f"Valid: {result.is_valid}")
    print(f"Mispricing Score: {result.mispricing_score:.1f}")
    print(f"Flags: {result.flags if result.flags else 'None'}")
    
    # Test 2: Validate with divergence
    print("\n📊 Test 2: Greeks Divergence")
    market_greeks_bad = {
        'delta': 0.70,  # Too high for ATM
        'gamma': 0.0312,
        'theta': -0.0456,
        'vega': 0.1845,
        'rho': 0.0234
    }
    
    result2 = validator.validate_option(
        market_greeks=market_greeks_bad,
        stock_price=100,
        strike=100,
        time_to_expiration=30/365,
        risk_free_rate=0.05,
        implied_volatility=0.30,
        option_type='call',
        symbol='TEST_CALL_100_BAD'
    )
    
    print(f"Valid: {result2.is_valid}")
    print(f"Mispricing Score: {result2.mispricing_score:.1f}")
    print(f"Flags: {result2.flags}")
    print(f"Delta Difference: {result2.differences['delta']:.3f}")
    
    # Test 3: Validate chain
    print("\n📊 Test 3: Validate Options Chain")
    
    # Create sample options chain
    options_chain = pd.DataFrame([
        {
            'symbol': 'TEST_CALL_95',
            'strike': 95,
            'expiration': '2024-02-15',
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
            'expiration': '2024-02-15',
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
            'expiration': '2024-02-15',
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
    
    chain_results = validator.validate_chain(options_chain, underlying_price=100)
    
    print(f"Validated {len(chain_results)} options")
    valid_count = sum(1 for r in chain_results if r.is_valid)
    print(f"Valid: {valid_count}/{len(chain_results)}")
    
    # Test 4: Find mispricings
    print("\n📊 Test 4: Find Mispricings")
    mispricings = validator.find_mispricings(chain_results, mispricing_threshold=20)
    
    if not mispricings.empty:
        print(f"\nFound {len(mispricings)} potential mispricings:")
        print(mispricings[['symbol', 'strike', 'mispricing_score', 'flags']].to_string())
    else:
        print("No significant mispricings detected")
    
    # Test 5: Generate report
    print("\n📊 Test 5: Validation Report")
    report = validator.generate_validation_report(chain_results)
    
    print(f"\nSummary:")
    print(f"  Total Options: {report['summary']['total_options']}")
    print(f"  Valid: {report['summary']['valid_options']}")
    print(f"  Invalid: {report['summary']['invalid_options']}")
    print(f"  Validation Rate: {report['summary']['validation_rate']:.1f}%")
    print(f"  Avg Mispricing Score: {report['summary']['avg_mispricing_score']:.1f}")
    
    if report['flag_distribution']:
        print(f"\nFlag Distribution:")
        for flag, count in report['flag_distribution'].items():
            print(f"  {flag}: {count}")
    
    print("\n" + "=" * 70)
    print("✅ All tests completed!")
    print("=" * 70)
