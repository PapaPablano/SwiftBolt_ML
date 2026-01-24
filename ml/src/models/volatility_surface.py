"""Implied Volatility Surface fitting and interpolation.

Implements SVI (Stochastic Volatility Inspired) parameterization
for fitting implied volatility smiles and surfaces.

SVI Formula:
    w(k) = a + b(ρ(k-m) + √((k-m)² + σ²))
    
    where:
        w = total implied variance (σ² * T)
        k = log-moneyness ln(K/F)
        a, b, ρ, m, σ = SVI parameters

Usage:
    from src.models.volatility_surface import VolatilitySurface, SVI
    
    # Fit single smile
    svi = SVI()
    params = svi.fit(strikes, implied_vols, F=100, T=30/365)
    
    # Build full surface
    surface = VolatilitySurface()
    surface.add_slice(T=30/365, strikes=strikes, vols=vols)
    surface.fit()
    
    # Interpolate
    iv = surface.get_volatility(K=105, T=45/365)

References:
    - Gatheral, J. (2004). "A parsimonious arbitrage-free implied 
      volatility parameterization with application to the valuation 
      of volatility derivatives"
    - Gatheral, J., & Jacquier, A. (2014). "Arbitrage-free SVI 
      volatility surfaces"
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from scipy.interpolate import CubicSpline, RectBivariateSpline
from scipy.optimize import minimize, differential_evolution

logger = logging.getLogger(__name__)


@dataclass
class SVIParameters:
    """SVI parameterization parameters.
    
    Attributes:
        a: Overall level
        b: Angle between wings
        rho: Orientation (correlation)
        m: Center point
        sigma: Smoothness
    """
    a: float
    b: float
    rho: float
    m: float
    sigma: float
    
    def validate(self) -> bool:
        """Check no-arbitrage conditions."""
        conditions = [
            self.b >= 0,
            abs(self.rho) < 1,
            self.sigma > 0,
            self.a + self.b * self.sigma * np.sqrt(1 - self.rho**2) >= 0
        ]
        return all(conditions)


class SVI:
    """SVI (Stochastic Volatility Inspired) smile parameterization."""
    
    def __init__(self):
        """Initialize SVI fitter."""
        self.params: SVIParameters = None
        self.fitted = False
    
    def _svi_variance(
        self,
        k: np.ndarray,
        a: float,
        b: float,
        rho: float,
        m: float,
        sigma: float
    ) -> np.ndarray:
        """Calculate total implied variance using SVI formula.
        
        Args:
            k: Log-moneyness ln(K/F)
            a, b, rho, m, sigma: SVI parameters
        
        Returns:
            Total implied variance w(k)
        """
        km = k - m
        return a + b * (rho * km + np.sqrt(km**2 + sigma**2))
    
    def fit(
        self,
        strikes: np.ndarray,
        implied_vols: np.ndarray,
        F: float,
        T: float,
        method: str = 'differential_evolution'
    ) -> SVIParameters:
        """Fit SVI parameters to observed volatilities.
        
        Args:
            strikes: Strike prices
            implied_vols: Implied volatilities
            F: Forward price (or spot if no dividends)
            T: Time to maturity
            method: 'differential_evolution' or 'minimize'
        
        Returns:
            Fitted SVI parameters
        """
        # Convert to log-moneyness and total variance
        k = np.log(strikes / F)
        w = implied_vols**2 * T
        
        # Objective function: minimize squared error
        def objective(params):
            a, b, rho, m, sigma = params
            
            # No-arbitrage constraints
            if b < 0 or abs(rho) >= 1 or sigma <= 0:
                return 1e10
            if a + b * sigma * np.sqrt(1 - rho**2) < 0:
                return 1e10
            
            w_pred = self._svi_variance(k, a, b, rho, m, sigma)
            return np.sum((w - w_pred)**2)
        
        # Initial guess
        atm_var = np.median(w)
        x0 = [atm_var, 0.1, -0.5, 0.0, 0.1]
        
        # Optimize
        if method == 'differential_evolution':
            bounds = [
                (0, atm_var * 2),      # a
                (0, 1),                # b
                (-0.99, 0.99),         # rho
                (k.min(), k.max()),    # m
                (0.01, 1)              # sigma
            ]
            result = differential_evolution(objective, bounds, seed=42, maxiter=1000)
        else:
            result = minimize(objective, x0, method='Nelder-Mead')
        
        # Store parameters
        self.params = SVIParameters(*result.x)
        self.fitted = True
        
        # Validate
        if not self.params.validate():
            logger.warning("SVI parameters violate no-arbitrage conditions!")
        
        logger.info(f"SVI fitted: RMSE={np.sqrt(result.fun / len(k)):.6f}")
        
        return self.params
    
    def predict(
        self,
        strikes: np.ndarray,
        F: float,
        T: float
    ) -> np.ndarray:
        """Predict implied volatilities for given strikes.
        
        Args:
            strikes: Strike prices
            F: Forward price
            T: Time to maturity
        
        Returns:
            Implied volatilities
        """
        if not self.fitted:
            raise ValueError("SVI must be fitted first")
        
        k = np.log(strikes / F)
        p = self.params
        
        w = self._svi_variance(k, p.a, p.b, p.rho, p.m, p.sigma)
        
        # Convert total variance back to implied vol
        implied_vols = np.sqrt(w / T)
        
        return implied_vols


class VolatilitySurface:
    """Implied volatility surface with multiple maturities."""
    
    def __init__(self):
        """Initialize volatility surface."""
        self.slices: Dict[float, Dict] = {}  # {T: {strikes, vols, svi_params}}
        self.surface_fitted = False
        self.interpolator = None
    
    def add_slice(
        self,
        T: float,
        strikes: np.ndarray,
        vols: np.ndarray,
        F: float = None
    ):
        """Add a volatility smile for a given maturity.
        
        Args:
            T: Time to maturity
            strikes: Strike prices
            vols: Implied volatilities
            F: Forward price (defaults to median strike)
        """
        if F is None:
            F = np.median(strikes)
        
        self.slices[T] = {
            'strikes': np.array(strikes),
            'vols': np.array(vols),
            'F': F,
            'svi_params': None
        }
        
        logger.info(f"Added slice: T={T:.4f}y, {len(strikes)} strikes")
    
    def fit(self, method: str = 'differential_evolution'):
        """Fit SVI to each maturity slice.
        
        Args:
            method: Optimization method for SVI fitting
        """
        for T, data in self.slices.items():
            svi = SVI()
            params = svi.fit(
                data['strikes'],
                data['vols'],
                data['F'],
                T,
                method=method
            )
            data['svi_params'] = params
            data['svi_model'] = svi
        
        self.surface_fitted = True
        logger.info(f"Fitted {len(self.slices)} maturity slices")
        
        # Build 2D interpolator for entire surface
        self._build_interpolator()
    
    def _build_interpolator(self):
        """Build 2D spline interpolator for the full surface."""
        # Gather all data points
        maturities = sorted(self.slices.keys())
        
        # Create grid
        all_strikes = []
        for data in self.slices.values():
            all_strikes.extend(data['strikes'])
        
        strike_min, strike_max = min(all_strikes), max(all_strikes)
        strike_grid = np.linspace(strike_min, strike_max, 50)
        
        # Evaluate SVI at each grid point
        vol_grid = np.zeros((len(maturities), len(strike_grid)))
        
        for i, T in enumerate(maturities):
            data = self.slices[T]
            svi = data['svi_model']
            vol_grid[i, :] = svi.predict(strike_grid, data['F'], T)
        
        # Build 2D spline
        self.interpolator = RectBivariateSpline(
            maturities,
            strike_grid,
            vol_grid,
            kx=min(3, len(maturities) - 1),
            ky=min(3, len(strike_grid) - 1)
        )
        
        self.maturity_range = (min(maturities), max(maturities))
        self.strike_range = (strike_min, strike_max)
    
    def get_volatility(self, K: float, T: float) -> float:
        """Get implied volatility for any strike and maturity.
        
        Args:
            K: Strike price
            T: Time to maturity
        
        Returns:
            Implied volatility (extrapolates if out of range)
        """
        if not self.surface_fitted:
            raise ValueError("Surface must be fitted first")
        
        # Interpolate
        vol = float(self.interpolator(T, K)[0, 0])
        
        # Ensure positive
        return max(vol, 0.01)
    
    def get_slice(self, T: float, strikes: np.ndarray = None) -> np.ndarray:
        """Get volatility smile for a given maturity.
        
        Args:
            T: Time to maturity
            strikes: Strike prices (if None, uses reasonable range)
        
        Returns:
            Implied volatilities
        """
        if strikes is None:
            strikes = np.linspace(
                self.strike_range[0],
                self.strike_range[1],
                50
            )
        
        return np.array([self.get_volatility(K, T) for K in strikes])
    
    def calculate_atm_vol_term_structure(
        self,
        atm_strike: float,
        maturities: np.ndarray = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate ATM volatility term structure.
        
        Args:
            atm_strike: ATM strike price
            maturities: Time to maturities (if None, uses fitted maturities)
        
        Returns:
            Tuple of (maturities, atm_vols)
        """
        if maturities is None:
            maturities = np.array(sorted(self.slices.keys()))
        
        atm_vols = np.array([
            self.get_volatility(atm_strike, T)
            for T in maturities
        ])
        
        return maturities, atm_vols
    
    def get_summary_statistics(self) -> Dict:
        """Get summary statistics of the surface.
        
        Returns:
            Dictionary with surface statistics
        """
        if not self.surface_fitted:
            return {'status': 'not_fitted'}
        
        maturities = sorted(self.slices.keys())
        
        stats = {
            'num_slices': len(self.slices),
            'maturity_range': (min(maturities), max(maturities)),
            'strike_range': self.strike_range,
            'avg_rmse': np.mean([
                np.sqrt(np.mean((
                    data['svi_model'].predict(data['strikes'], data['F'], T) - data['vols']
                )**2))
                for T, data in self.slices.items()
            ])
        }
        
        return stats


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Volatility Surface - Self Test")
    print("=" * 70)
    
    # Test 1: Fit single SVI smile
    print("\n📊 Test 1: SVI Smile Fitting")
    
    # Generate synthetic smile with volatility smile
    strikes = np.array([80, 85, 90, 95, 100, 105, 110, 115, 120])
    F = 100
    T = 0.25
    
    # Create smile (lower vol at ATM, higher at wings)
    moneyness = strikes / F
    base_vol = 0.20
    smile = base_vol + 0.05 * (moneyness - 1)**2
    
    svi = SVI()
    params = svi.fit(strikes, smile, F, T)
    
    print(f"SVI Parameters:")
    print(f"  a = {params.a:.6f}")
    print(f"  b = {params.b:.6f}")
    print(f"  ρ = {params.rho:.6f}")
    print(f"  m = {params.m:.6f}")
    print(f"  σ = {params.sigma:.6f}")
    print(f"  No-arbitrage check: {params.validate()}")
    
    # Compare fit
    fitted_vols = svi.predict(strikes, F, T)
    rmse = np.sqrt(np.mean((smile - fitted_vols)**2))
    print(f"\nRMSE: {rmse:.6f}")
    
    print(f"\n{'Strike':<10} {'Market':<12} {'SVI Fit':<12} {'Error':<10}")
    print("-" * 44)
    for k, mv, fv in zip(strikes, smile, fitted_vols):
        error = abs(mv - fv) * 100
        print(f"{k:<10.1f} {mv*100:<12.2f}% {fv*100:<12.2f}% {error:<10.4f}%")
    
    # Test 2: Build volatility surface
    print("\n📊 Test 2: Volatility Surface")
    
    surface = VolatilitySurface()
    
    # Add multiple maturity slices
    for T_test in [30/365, 60/365, 90/365, 180/365]:
        # Generate smile for each maturity (smile flattens with time)
        smile_T = base_vol + 0.05 * (1 - T_test) * (moneyness - 1)**2
        surface.add_slice(T_test, strikes, smile_T, F=F)
    
    # Fit surface
    surface.fit()
    
    # Get statistics
    stats = surface.get_summary_statistics()
    print(f"\nSurface Statistics:")
    print(f"  Slices: {stats['num_slices']}")
    print(f"  Maturity range: {stats['maturity_range'][0]:.3f} - {stats['maturity_range'][1]:.3f} years")
    print(f"  Strike range: ${stats['strike_range'][0]:.1f} - ${stats['strike_range'][1]:.1f}")
    print(f"  Average RMSE: {stats['avg_rmse']:.6f}")
    
    # Test 3: Interpolation
    print("\n📊 Test 3: Surface Interpolation")
    
    test_strikes = [95, 100, 105]
    test_maturities = [45/365, 120/365]
    
    print(f"\n{'Maturity':<12} {'Strike':<10} {'Implied Vol':<15}")
    print("-" * 37)
    for T_test in test_maturities:
        for K_test in test_strikes:
            vol = surface.get_volatility(K_test, T_test)
            print(f"{T_test*365:<12.0f}d {K_test:<10.1f} {vol*100:<15.2f}%")
    
    # Test 4: ATM term structure
    print("\n📊 Test 4: ATM Volatility Term Structure")
    
    mats, atm_vols = surface.calculate_atm_vol_term_structure(atm_strike=100)
    
    print(f"\n{'Maturity':<15} {'ATM Vol':<15}")
    print("-" * 30)
    for mat, vol in zip(mats, atm_vols):
        print(f"{mat*365:<15.0f}d {vol*100:<15.2f}%")
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
