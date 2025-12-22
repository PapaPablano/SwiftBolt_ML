"""
Probability of Profit (PoP) and Risk/Reward Ratio Calculator
=========================================================

Calculates the likelihood of an options contract finishing profitable,
combined with the risk/reward ratio to identify high-probability trades.

P0 Module for Enhanced Options Ranker.
"""

import logging
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)


class ProbabilityOfProfitCalculator:
    """
    Calculates probability of profit and risk/reward metrics for options.
    
    Key metrics:
    - PoP (Probability of Profit): Likelihood of profitable trade at expiry
    - Risk/Reward Ratio: Potential gain vs maximum loss
    - Breakeven price: Price underlying must reach for profit
    """
    
    @staticmethod
    def calculate_pop(
        underlying_price: float,
        strike: float,
        side: str,
        bid: float,
        ask: float,
        delta: float,
        days_to_expiry: int = 30,
        risk_free_rate: float = 0.05
    ) -> Dict:
        """
        Calculate probability of profit using delta approximation.
        
        Delta approximates the probability that the option expires ITM.
        We adjust for bid-ask spread cost which reduces effective PoP.
        
        Args:
            underlying_price: Current stock price
            strike: Option strike price
            side: 'call' or 'put'
            bid: Bid price
            ask: Ask price
            delta: Option delta
            days_to_expiry: Days until expiration
            risk_free_rate: Risk-free interest rate
            
        Returns:
            Dict with PoP metrics
        """
        mid_price = (bid + ask) / 2.0
        spread = ask - bid
        
        # Base PoP from delta
        if side == 'call':
            pop_long = abs(delta)
            breakeven_price = strike + mid_price
        elif side == 'put':
            pop_long = 1.0 - abs(delta)
            breakeven_price = strike - mid_price
        else:
            raise ValueError(f"Invalid side: {side}")
        
        # Adjust for bid-ask spread cost (wider spread = lower effective PoP)
        spread_penalty = (spread / (mid_price + 1e-6)) * 0.3
        adjusted_pop = max(pop_long - spread_penalty, 0.01)
        
        pop_short = 1.0 - adjusted_pop
        
        return {
            'underlying_price': underlying_price,
            'strike': strike,
            'side': side,
            'pop_long': pop_long,
            'pop_short': pop_short,
            'pop_long_adjusted': adjusted_pop,
            'pop_short_adjusted': 1.0 - adjusted_pop,
            'breakeven_price': breakeven_price,
            'probability_profitable': max(adjusted_pop, pop_short),
            'spread_cost_factor': spread_penalty,
            'bid_ask_spread': spread,
            'mid_price': mid_price
        }
    
    @staticmethod
    def calculate_risk_reward_ratio(
        strike: float,
        underlying_price: float,
        bid: float,
        ask: float,
        side: str,
        stop_loss_percent: float = 0.02,
        take_profit_multiplier: float = 2.0
    ) -> Dict:
        """
        Calculate risk/reward ratio for position sizing and trade worthiness.
        
        For long options:
        - Max loss = premium paid
        - Max gain = theoretically unlimited (calls) or strike (puts)
        
        Args:
            strike: Option strike price
            underlying_price: Current stock price
            bid: Bid price
            ask: Ask price
            side: 'call' or 'put'
            stop_loss_percent: Stop loss as % of underlying
            take_profit_multiplier: Target profit as multiple of premium
            
        Returns:
            Dict with risk/reward metrics
        """
        mid_price = (bid + ask) / 2.0
        
        if side == 'call':
            max_loss = mid_price
            max_gain = underlying_price * 100  # Theoretical max
            stop_loss_price = underlying_price * (1.0 - stop_loss_percent)
        elif side == 'put':
            max_loss = mid_price
            max_gain = strike * 100  # Max if stock goes to 0
            stop_loss_price = underlying_price * (1.0 + stop_loss_percent)
        else:
            raise ValueError(f"Invalid side: {side}")
        
        risk_amount = mid_price
        potential_gain = max_gain - mid_price
        
        risk_reward = potential_gain / (risk_amount + 1e-6)
        
        profit_target_price = mid_price * take_profit_multiplier
        profit_at_target = profit_target_price - mid_price
        rr_with_target = profit_at_target / risk_amount if risk_amount > 0 else 0
        
        return {
            'mid_price': mid_price,
            'max_loss': max_loss,
            'max_gain': max_gain,
            'risk_reward_ratio': risk_reward,
            'risk_reward_with_target': rr_with_target,
            'favorable': risk_reward > 1.5,
            'excellent': risk_reward > 2.5,
            'stop_loss_price': stop_loss_price,
            'potential_profit_multiple': take_profit_multiplier,
        }
    
    @staticmethod
    def score_pop_and_rr(
        pop_metrics: Dict,
        rr_metrics: Dict,
        min_pop: float = 0.45,
        min_rr: float = 1.5
    ) -> float:
        """
        Composite score: combines PoP and R/R into single 0-1 score.
        
        Scoring logic:
        - 60% weight on PoP (probability matters most)
        - 40% weight on R/R (reward potential)
        - Penalties for below-threshold values
        - Bonus for exceptional combinations
        
        Args:
            pop_metrics: Dict from calculate_pop()
            rr_metrics: Dict from calculate_risk_reward_ratio()
            min_pop: Minimum acceptable PoP
            min_rr: Minimum acceptable R/R ratio
            
        Returns:
            Score from 0-1
        """
        pop_adj = pop_metrics['pop_long_adjusted']
        rr = rr_metrics['risk_reward_ratio']
        
        # Normalize components
        pop_component = min(pop_adj / 0.65, 1.0)
        rr_component = min(rr / 3.0, 1.0)
        
        # Weighted composite
        composite_score = (pop_component * 0.6) + (rr_component * 0.4)
        
        # Penalties for below-threshold values
        if pop_adj < min_pop:
            composite_score *= 0.5
        if rr < min_rr:
            composite_score *= 0.5
        
        # Bonus for exceptional combinations (high PoP + high R/R)
        if pop_adj > 0.55 and rr > 2.5:
            composite_score = min(composite_score * 1.15, 1.0)
        
        return composite_score
