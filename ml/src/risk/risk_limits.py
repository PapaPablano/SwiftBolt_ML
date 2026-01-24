"""Risk limits and validation for options trading.

Enforces position limits, concentration limits, and Greeks limits
to manage portfolio risk.

Usage:
    from src.risk.risk_limits import RiskLimits, RiskValidator
    
    # Define limits
    limits = RiskLimits(
        max_position_size=10,
        max_portfolio_delta=500,
        max_concentration=0.25
    )
    
    # Validate
    validator = RiskValidator(limits)
    result = validator.validate_trade(trade_info, current_portfolio)
    
    if not result['approved']:
        print(f"Trade rejected: {result['reason']}")
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Define risk limits for portfolio.
    
    Attributes:
        max_position_size: Max contracts per position
        max_portfolio_delta: Max absolute portfolio delta
        max_portfolio_gamma: Max absolute portfolio gamma
        max_portfolio_vega: Max absolute portfolio vega
        max_concentration: Max % of portfolio in single position
        max_daily_loss: Max allowed daily loss ($)
        max_margin_usage: Max margin usage (%)
    """
    max_position_size: int = 10
    max_portfolio_delta: float = 500
    max_portfolio_gamma: float = 50
    max_portfolio_vega: float = 200
    max_concentration: float = 0.25  # 25%
    max_daily_loss: float = 5000
    max_margin_usage: float = 0.80  # 80%


class RiskValidator:
    """Validate trades against risk limits."""
    
    def __init__(self, limits: RiskLimits):
        """Initialize risk validator.
        
        Args:
            limits: RiskLimits object
        """
        self.limits = limits
    
    def validate_trade(
        self,
        trade: Dict,
        current_portfolio: Dict,
        verbose: bool = True
    ) -> Dict:
        """Validate trade against risk limits.
        
        Args:
            trade: Trade dictionary with keys: symbol, quantity, greeks, value
            current_portfolio: Current portfolio state
            verbose: Log validation details
        
        Returns:
            Dictionary with 'approved' (bool) and 'reason' (str)
        """
        violations = []
        
        # 1. Position size limit
        position_size = abs(trade.get('quantity', 0))
        if position_size > self.limits.max_position_size:
            violations.append(
                f"Position size {position_size} exceeds limit {self.limits.max_position_size}"
            )
        
        # 2. Portfolio delta limit
        new_delta = current_portfolio.get('delta', 0) + trade.get('delta', 0)
        if abs(new_delta) > self.limits.max_portfolio_delta:
            violations.append(
                f"Portfolio delta {new_delta:.0f} exceeds limit {self.limits.max_portfolio_delta}"
            )
        
        # 3. Portfolio gamma limit
        new_gamma = current_portfolio.get('gamma', 0) + trade.get('gamma', 0)
        if abs(new_gamma) > self.limits.max_portfolio_gamma:
            violations.append(
                f"Portfolio gamma {new_gamma:.2f} exceeds limit {self.limits.max_portfolio_gamma}"
            )
        
        # 4. Portfolio vega limit
        new_vega = current_portfolio.get('vega', 0) + trade.get('vega', 0)
        if abs(new_vega) > self.limits.max_portfolio_vega:
            violations.append(
                f"Portfolio vega {new_vega:.2f} exceeds limit {self.limits.max_portfolio_vega}"
            )
        
        # 5. Concentration limit
        if current_portfolio.get('total_value', 0) > 0:
            trade_value = abs(trade.get('value', 0))
            new_total = current_portfolio['total_value'] + trade_value
            concentration = trade_value / new_total if new_total > 0 else 0
            
            if concentration > self.limits.max_concentration:
                violations.append(
                    f"Concentration {concentration:.1%} exceeds limit {self.limits.max_concentration:.1%}"
                )
        
        # 6. Daily loss limit
        current_loss = abs(min(current_portfolio.get('daily_pnl', 0), 0))
        if current_loss >= self.limits.max_daily_loss:
            violations.append(
                f"Daily loss ${current_loss:.2f} exceeds limit ${self.limits.max_daily_loss:.2f}"
            )
        
        # 7. Margin usage limit
        if current_portfolio.get('total_margin', 0) > 0:
            current_usage = current_portfolio.get('margin_used', 0) / current_portfolio['total_margin']
            trade_margin = trade.get('margin_required', 0)
            new_usage = (current_portfolio['margin_used'] + trade_margin) / current_portfolio['total_margin']
            
            if new_usage > self.limits.max_margin_usage:
                violations.append(
                    f"Margin usage {new_usage:.1%} exceeds limit {self.limits.max_margin_usage:.1%}"
                )
        
        # Result
        approved = len(violations) == 0
        
        if verbose:
            if approved:
                logger.info(f"Trade approved: {trade.get('symbol', 'Unknown')}")
            else:
                logger.warning(f"Trade rejected: {violations[0]}")
        
        return {
            'approved': approved,
            'violations': violations,
            'reason': violations[0] if violations else 'Approved'
        }
    
    def check_portfolio_health(
        self,
        portfolio: Dict,
        verbose: bool = True
    ) -> Dict:
        """Check overall portfolio health against limits.
        
        Args:
            portfolio: Portfolio dictionary with Greeks and positions
            verbose: Log health check details
        
        Returns:
            Dictionary with health status
        """
        issues = []
        warnings = []
        
        # Check Greeks
        delta = abs(portfolio.get('delta', 0))
        gamma = abs(portfolio.get('gamma', 0))
        vega = abs(portfolio.get('vega', 0))
        
        if delta > self.limits.max_portfolio_delta:
            issues.append(f"Delta {delta:.0f} exceeds limit")
        elif delta > self.limits.max_portfolio_delta * 0.8:
            warnings.append(f"Delta {delta:.0f} near limit")
        
        if gamma > self.limits.max_portfolio_gamma:
            issues.append(f"Gamma {gamma:.2f} exceeds limit")
        elif gamma > self.limits.max_portfolio_gamma * 0.8:
            warnings.append(f"Gamma {gamma:.2f} near limit")
        
        if vega > self.limits.max_portfolio_vega:
            issues.append(f"Vega {vega:.2f} exceeds limit")
        elif vega > self.limits.max_portfolio_vega * 0.8:
            warnings.append(f"Vega {vega:.2f} near limit")
        
        # Check daily loss
        daily_pnl = portfolio.get('daily_pnl', 0)
        if daily_pnl < -self.limits.max_daily_loss:
            issues.append(f"Daily loss ${abs(daily_pnl):.2f} exceeds limit")
        
        # Check margin
        if portfolio.get('total_margin', 0) > 0:
            margin_usage = portfolio['margin_used'] / portfolio['total_margin']
            if margin_usage > self.limits.max_margin_usage:
                issues.append(f"Margin usage {margin_usage:.1%} exceeds limit")
            elif margin_usage > self.limits.max_margin_usage * 0.9:
                warnings.append(f"Margin usage {margin_usage:.1%} near limit")
        
        # Determine health status
        if issues:
            status = "CRITICAL"
        elif warnings:
            status = "WARNING"
        else:
            status = "HEALTHY"
        
        if verbose:
            logger.info(f"Portfolio health: {status}")
            if issues:
                for issue in issues:
                    logger.warning(f"  ISSUE: {issue}")
            if warnings:
                for warning in warnings:
                    logger.info(f"  WARNING: {warning}")
        
        return {
            'status': status,
            'issues': issues,
            'warnings': warnings,
            'healthy': status == "HEALTHY"
        }


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Risk Validator - Self Test")
    print("=" * 70)
    
    # Define limits
    limits = RiskLimits(
        max_position_size=10,
        max_portfolio_delta=500,
        max_portfolio_gamma=50,
        max_portfolio_vega=200,
        max_concentration=0.25,
        max_daily_loss=5000,
        max_margin_usage=0.80
    )
    
    validator = RiskValidator(limits)
    
    # Test 1: Valid trade
    print("\n📊 Test 1: Valid Trade")
    trade1 = {
        'symbol': 'AAPL_CALL_150',
        'quantity': 5,
        'delta': 260,  # 5 contracts × 52 delta × 100
        'gamma': 15,
        'vega': 90,
        'value': 2500,
        'margin_required': 2500
    }
    
    portfolio1 = {
        'delta': 100,
        'gamma': 10,
        'vega': 50,
        'total_value': 10000,
        'daily_pnl': -500,
        'margin_used': 5000,
        'total_margin': 10000
    }
    
    result1 = validator.validate_trade(trade1, portfolio1)
    print(f"Approved: {result1['approved']}")
    print(f"Reason: {result1['reason']}")
    
    # Test 2: Exceeds delta limit
    print("\n📊 Test 2: Delta Limit Exceeded")
    trade2 = {
        'symbol': 'AAPL_CALL_150',
        'quantity': 10,
        'delta': 520,  # Would push total to 620
        'gamma': 30,
        'vega': 180,
        'value': 5000,
        'margin_required': 5000
    }
    
    result2 = validator.validate_trade(trade2, portfolio1)
    print(f"Approved: {result2['approved']}")
    print(f"Reason: {result2['reason']}")
    
    # Test 3: Portfolio health check
    print("\n📊 Test 3: Portfolio Health Check")
    
    healthy_portfolio = {
        'delta': 200,
        'gamma': 20,
        'vega': 100,
        'daily_pnl': -1000,
        'margin_used': 6000,
        'total_margin': 10000
    }
    
    health1 = validator.check_portfolio_health(healthy_portfolio)
    print(f"Status: {health1['status']}")
    print(f"Issues: {health1['issues'] if health1['issues'] else 'None'}")
    print(f"Warnings: {health1['warnings'] if health1['warnings'] else 'None'}")
    
    # Test 4: Unhealthy portfolio
    print("\n📊 Test 4: Unhealthy Portfolio")
    
    unhealthy_portfolio = {
        'delta': 600,  # Exceeds limit
        'gamma': 60,   # Exceeds limit
        'vega': 250,   # Exceeds limit
        'daily_pnl': -6000,  # Exceeds loss limit
        'margin_used': 9000,
        'total_margin': 10000
    }
    
    health2 = validator.check_portfolio_health(unhealthy_portfolio)
    print(f"Status: {health2['status']}")
    print(f"Issues: {health2['issues']}")
    
    print("\n" + "=" * 70)
    print("✅ Risk validator test complete!")
    print("=" * 70)
