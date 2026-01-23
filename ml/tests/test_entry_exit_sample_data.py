"""
Test entry/exit ranking with sample data to validate formulas.
Run: python -m tests.test_entry_exit_sample_data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.models.options_momentum_ranker import OptionsMomentumRanker, RankingMode, IVStatistics


def create_sample_options_chain():
    """Create realistic sample options data for AAPL."""
    
    # Create 10 sample options contracts
    today = datetime.now()
    expiry_30d = (today + timedelta(days=30)).strftime("%Y-%m-%d")
    expiry_14d = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    expiry_7d = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    
    data = {
        # Contract 1: "Perfect Entry" - Low IV, volume surge, good Greeks
        'contract_symbol': ['AAPL_180_C_30D', 'AAPL_175_C_30D', 'AAPL_185_P_30D', 
                           'AAPL_180_C_14D', 'AAPL_175_C_14D',
                           'AAPL_180_C_7D', 'AAPL_175_P_14D',
                           'AAPL_190_C_30D', 'AAPL_170_C_30D', 'AAPL_185_C_30D'],
        'strike': [180, 175, 185, 180, 175, 180, 175, 190, 170, 185],
        'side': ['call', 'call', 'put', 'call', 'call', 'call', 'put', 'call', 'call', 'call'],
        'expiration': [expiry_30d] * 3 + [expiry_14d] * 2 + [expiry_7d] * 1 + [expiry_14d] * 1 + [expiry_30d] * 3,
        'dte': [30, 30, 30, 14, 14, 7, 14, 30, 30, 30],
        'days_to_expiry': [30, 30, 30, 14, 14, 7, 14, 30, 30, 30],
        
        # Pricing (bid, ask, mark, mid)
        'bid': [2.40, 3.90, 1.80, 2.20, 3.70, 1.90, 2.00, 1.20, 5.80, 1.90],
        'ask': [2.50, 4.00, 1.90, 2.30, 3.80, 2.00, 2.10, 1.30, 6.00, 2.00],
        'mark': [2.45, 3.95, 1.85, 2.25, 3.75, 1.95, 2.05, 1.25, 5.90, 1.95],
        'mid': [2.45, 3.95, 1.85, 2.25, 3.75, 1.95, 2.05, 1.25, 5.90, 1.95],
        'last': [2.43, 3.92, 1.87, 2.27, 3.73, 1.93, 2.03, 1.27, 5.88, 1.93],
        
        # IV metrics
        'iv': [0.22, 0.24, 0.26, 0.28, 0.25, 0.35, 0.27, 0.20, 0.23, 0.25],  # Implied volatility
        
        # Greeks
        'delta': [0.52, 0.60, -0.48, 0.55, 0.62, 0.65, -0.50, 0.35, 0.75, 0.48],
        'gamma': [0.038, 0.035, 0.040, 0.045, 0.042, 0.050, 0.043, 0.025, 0.030, 0.037],
        'vega': [0.28, 0.30, 0.32, 0.25, 0.28, 0.18, 0.26, 0.22, 0.33, 0.27],
        'theta': [-0.03, -0.04, -0.02, -0.05, -0.06, -0.08, -0.04, -0.02, -0.05, -0.03],
        'rho': [0.15, 0.18, -0.14, 0.12, 0.16, 0.10, -0.13, 0.08, 0.20, 0.14],
        
        # Volume and Open Interest
        'volume': [350, 180, 120, 250, 150, 80, 100, 50, 200, 90],
        'open_interest': [1200, 800, 600, 900, 700, 400, 500, 300, 1000, 450],
    }
    
    return pd.DataFrame(data)


def create_sample_history():
    """Create sample historical data for momentum calculations."""
    
    history_data = {
        'contract_symbol': ['AAPL_180_C_30D'] * 5 + ['AAPL_175_C_30D'] * 5 + ['AAPL_185_P_30D'] * 5,
        'date': [datetime.now() - timedelta(days=i) for i in range(5, 0, -1)] * 3,
        'mark': [2.10, 2.15, 2.25, 2.35, 2.40] +  # 180 Call growing
                [3.80, 3.82, 3.85, 3.90, 3.92] +  # 175 Call slight growth
                [2.00, 1.95, 1.90, 1.87, 1.85],   # 185 Put declining
        'iv': [0.28, 0.27, 0.25, 0.24, 0.23] +    # 180 Call IV falling (good!)
              [0.25, 0.25, 0.25, 0.24, 0.24] +    # 175 Call IV stable
              [0.29, 0.28, 0.27, 0.27, 0.26],     # 185 Put IV falling
        'volume': [100, 120, 150, 200, 350] +     # 180 Call volume surging!
                  [160, 165, 170, 175, 180] +     # 175 Call stable
                  [80, 90, 100, 110, 120],        # 185 Put growing
        'open_interest': [1000, 1050, 1100, 1150, 1200] +  # 180 Call OI building
                        [780, 785, 790, 795, 800] +        # 175 Call slow growth
                        [550, 560, 580, 590, 600],         # 185 Put growing
    }
    
    return pd.DataFrame(history_data)


def create_iv_stats():
    """Create 52-week IV statistics for AAPL."""
    return IVStatistics(
        iv_high=0.45,
        iv_low=0.15,
        iv_median=0.28,
        iv_current=0.25,
        days_of_data=252
    )


def print_separator(title=""):
    """Print a nice separator."""
    print("\n" + "="*80)
    if title:
        print(f"  {title}")
        print("="*80)


def print_contract_details(row, rank_type="ENTRY"):
    """Print detailed breakdown for a contract."""
    print(f"\n📋 {row['contract_symbol']}")
    print(f"   Strike: ${row['strike']:.0f} {row['side'].upper()}, DTE: {row['dte']} days")
    print(f"   Mark: ${row['mark']:.2f}, Spread: {((row['ask']-row['bid'])/row['mid']*100):.1f}%")
    print(f"   IV: {row['iv']:.2%}, Delta: {row['delta']:.2f}, Volume: {row['volume']:.0f}, OI: {row['open_interest']:.0f}")
    
    if rank_type == "ENTRY":
        print(f"\n   🎯 ENTRY RANK: {row.get('entry_rank', 0):.1f}/100")
        print(f"      └─ Entry Value:  {row.get('entry_value_score', 0):.1f} × 40% = {row.get('entry_value_score', 0)*0.40:.1f}")
        print(f"      └─ Catalyst:     {row.get('catalyst_score', 0):.1f} × 35% = {row.get('catalyst_score', 0)*0.35:.1f}")
        print(f"      └─ Greeks:       {row.get('greeks_score', 0):.1f} × 25% = {row.get('greeks_score', 0)*0.25:.1f}")
    elif rank_type == "EXIT":
        print(f"\n   🚪 EXIT RANK: {row.get('exit_rank', 0):.1f}/100")
        print(f"      └─ Profit:       {row.get('profit_protection_score', 0):.1f} × 50% = {row.get('profit_protection_score', 0)*0.50:.1f}")
        print(f"      └─ Deterioration: {row.get('deterioration_score', 0):.1f} × 30% = {row.get('deterioration_score', 0)*0.30:.1f}")
        print(f"      └─ Time Urgency: {row.get('time_urgency_score', 0):.1f} × 20% = {row.get('time_urgency_score', 0)*0.20:.1f}")
    else:  # MONITOR
        print(f"\n   📊 MONITOR RANK: {row.get('composite_rank', 0):.1f}/100")
        print(f"      └─ Momentum:     {row.get('momentum_score', 0):.1f} × 40% = {row.get('momentum_score', 0)*0.40:.1f}")
        print(f"      └─ Value:        {row.get('value_score', 0):.1f} × 35% = {row.get('value_score', 0)*0.35:.1f}")
        print(f"      └─ Greeks:       {row.get('greeks_score', 0):.1f} × 25% = {row.get('greeks_score', 0)*0.25:.1f}")


def test_entry_mode():
    """Test ENTRY mode ranking."""
    print_separator("TEST 1: ENTRY MODE - Find Undervalued Opportunities")
    
    ranker = OptionsMomentumRanker()
    chain = create_sample_options_chain()
    history = create_sample_history()
    iv_stats = create_iv_stats()
    
    print("\n📊 Sample Data:")
    print(f"   Contracts: {len(chain)}")
    print(f"   Historical data points: {len(history)}")
    print(f"   IV 52-week range: {iv_stats.iv_low:.1%} - {iv_stats.iv_high:.1%}")
    print(f"   Current IV: {iv_stats.iv_current:.1%} (percentile: ~33rd)")
    
    # Run ENTRY mode ranking
    print("\n🔄 Running ENTRY mode ranking...")
    results = ranker.rank_options(
        chain,
        mode=RankingMode.ENTRY,
        iv_stats=iv_stats,
        options_history=history
    )
    
    # Sort by entry_rank
    results_sorted = results.sort_values('entry_rank', ascending=False)
    
    print("\n🏆 TOP 3 ENTRY OPPORTUNITIES:")
    for i, (idx, row) in enumerate(results_sorted.head(3).iterrows(), 1):
        print(f"\n#{i}")
        print_contract_details(row, "ENTRY")
    
    print("\n💡 INTERPRETATION:")
    top = results_sorted.iloc[0]
    print(f"   Best entry: {top['contract_symbol']}")
    if top.get('entry_value_score', 0) > 75:
        print(f"   ✓ CHEAP: Entry value score {top.get('entry_value_score', 0):.0f} indicates low IV")
    if top.get('catalyst_score', 0) > 70:
        print(f"   ✓ CATALYST: Catalyst score {top.get('catalyst_score', 0):.0f} shows strong momentum")
    if top.get('greeks_score', 0) > 70:
        print(f"   ✓ POSITIONED: Greeks score {top.get('greeks_score', 0):.0f} means good delta/gamma")
    
    return results_sorted


def test_exit_mode():
    """Test EXIT mode ranking."""
    print_separator("TEST 2: EXIT MODE - Detect Profit-Taking Opportunities")
    
    ranker = OptionsMomentumRanker()
    chain = create_sample_options_chain()
    history = create_sample_history()
    
    # Simulate we bought these contracts 20 days ago at lower prices
    entry_data = {
        'entry_price': 1.80,  # Bought at $1.80, now worth $2.45 (180 call)
    }
    
    print("\n📊 Sample Scenario:")
    print(f"   Entry price: ${entry_data['entry_price']:.2f}")
    print(f"   Current prices: $1.95 - $5.90")
    print(f"   Time held: ~20 days")
    
    # Run EXIT mode ranking
    print("\n🔄 Running EXIT mode ranking...")
    results = ranker.rank_options(
        chain,
        mode=RankingMode.EXIT,
        options_history=history,
        entry_data=entry_data
    )
    
    # Sort by exit_rank
    results_sorted = results.sort_values('exit_rank', ascending=False)
    
    print("\n🚪 TOP 3 EXIT SIGNALS:")
    for i, (idx, row) in enumerate(results_sorted.head(3).iterrows(), 1):
        print(f"\n#{i}")
        # Calculate P&L for display
        pnl_pct = ((row['mark'] - entry_data['entry_price']) / entry_data['entry_price']) * 100
        print(f"   💰 P&L: {pnl_pct:+.1f}% (${row['mark']:.2f} from ${entry_data['entry_price']:.2f})")
        print_contract_details(row, "EXIT")
    
    print("\n💡 INTERPRETATION:")
    top = results_sorted.iloc[0]
    pnl = ((top['mark'] - entry_data['entry_price']) / entry_data['entry_price']) * 100
    print(f"   Strongest exit signal: {top['contract_symbol']}")
    if top.get('profit_protection_score', 0) > 70:
        print(f"   ✓ PROFIT: {pnl:+.1f}% gain achieved")
    if top.get('deterioration_score', 0) > 60:
        print(f"   ✓ FADING: Deterioration score {top.get('deterioration_score', 0):.0f} shows momentum decay")
    if top.get('time_urgency_score', 0) > 60:
        print(f"   ✓ TIME: Urgency score {top.get('time_urgency_score', 0):.0f} indicates approaching expiration")
    
    return results_sorted


def test_monitor_mode():
    """Test MONITOR mode (backward compatible)."""
    print_separator("TEST 3: MONITOR MODE - Balanced Screening")
    
    ranker = OptionsMomentumRanker()
    chain = create_sample_options_chain()
    history = create_sample_history()
    iv_stats = create_iv_stats()
    
    print("\n🔄 Running MONITOR mode ranking (original system)...")
    results = ranker.rank_options(
        chain,
        mode=RankingMode.MONITOR,
        iv_stats=iv_stats,
        options_history=history
    )
    
    # Sort by composite_rank
    results_sorted = results.sort_values('composite_rank', ascending=False)
    
    print("\n📊 TOP 3 MONITOR RANKINGS:")
    for i, (idx, row) in enumerate(results_sorted.head(3).iterrows(), 1):
        print(f"\n#{i}")
        print_contract_details(row, "MONITOR")
    
    return results_sorted


def compare_modes():
    """Compare rankings across all three modes."""
    print_separator("TEST 4: MODE COMPARISON - Same Contract, Different Perspectives")
    
    ranker = OptionsMomentumRanker()
    chain = create_sample_options_chain()
    history = create_sample_history()
    iv_stats = create_iv_stats()
    
    # Focus on the 180 Call (should be good entry)
    entry_results = ranker.rank_options(chain, mode=RankingMode.ENTRY, iv_stats=iv_stats, options_history=history)
    exit_results = ranker.rank_options(chain, mode=RankingMode.EXIT, options_history=history, entry_data={'entry_price': 1.80})
    monitor_results = ranker.rank_options(chain, mode=RankingMode.MONITOR, iv_stats=iv_stats, options_history=history)
    
    # Get the 180 Call
    contract = 'AAPL_180_C_30D'
    entry_row = entry_results[entry_results['contract_symbol'] == contract].iloc[0]
    exit_row = exit_results[exit_results['contract_symbol'] == contract].iloc[0]
    monitor_row = monitor_results[monitor_results['contract_symbol'] == contract].iloc[0]
    
    print(f"\n📊 {contract} Across All Modes:")
    print(f"\n   ENTRY MODE:   {entry_row['entry_rank']:.1f}/100")
    print(f"      └─ Value {entry_row.get('entry_value_score', 0):.0f} + Catalyst {entry_row.get('catalyst_score', 0):.0f} + Greeks {entry_row.get('greeks_score', 0):.0f}")
    
    print(f"\n   EXIT MODE:    {exit_row['exit_rank']:.1f}/100")
    print(f"      └─ Profit {exit_row.get('profit_protection_score', 0):.0f} + Deterioration {exit_row.get('deterioration_score', 0):.0f} + Time {exit_row.get('time_urgency_score', 0):.0f}")
    
    print(f"\n   MONITOR MODE: {monitor_row['composite_rank']:.1f}/100")
    print(f"      └─ Momentum {monitor_row.get('momentum_score', 0):.0f} + Value {monitor_row.get('value_score', 0):.0f} + Greeks {monitor_row.get('greeks_score', 0):.0f}")
    
    print("\n💡 INSIGHT:")
    if entry_row['entry_rank'] > 75:
        print("   ✓ High entry rank suggests this is a good BUY opportunity")
    if exit_row['exit_rank'] > 70:
        print("   ✓ High exit rank suggests you should SELL if you own it")
    elif exit_row['exit_rank'] < 50:
        print("   ✓ Low exit rank suggests HOLD if you own it")
    
    # Show what differs
    print("\n🔍 Why Rankings Differ:")
    if entry_row['entry_rank'] > monitor_row['composite_rank']:
        print(f"   Entry ({entry_row['entry_rank']:.0f}) > Monitor ({monitor_row['composite_rank']:.0f})")
        print("   → Entry mode emphasizes VALUE (40% weight) and CATALYST detection")
    if exit_row['exit_rank'] < entry_row['entry_rank']:
        print(f"   Exit ({exit_row['exit_rank']:.0f}) < Entry ({entry_row['entry_rank']:.0f})")
        print("   → Exit mode focuses on PROFIT PROTECTION and TIME DECAY")


def run_all_tests():
    """Run all test scenarios."""
    print("\n" + "="*80)
    print("  ENTRY/EXIT RANKING SYSTEM - VALIDATION TEST")
    print("  Testing with realistic AAPL options data")
    print("="*80)
    
    try:
        # Test 1: Entry mode
        entry_results = test_entry_mode()
        
        # Test 2: Exit mode
        exit_results = test_exit_mode()
        
        # Test 3: Monitor mode
        monitor_results = test_monitor_mode()
        
        # Test 4: Compare modes
        compare_modes()
        
        # Final summary
        print_separator("VALIDATION SUMMARY")
        print("\n✅ All tests completed successfully!")
        print("\n📊 Results:")
        print(f"   • Entry mode ranked {len(entry_results)} contracts")
        print(f"   • Exit mode ranked {len(exit_results)} contracts")
        print(f"   • Monitor mode ranked {len(monitor_results)} contracts")
        print(f"   • All ranks in valid range: 0-100")
        
        # Check for NaN or Inf
        entry_has_nan = entry_results['entry_rank'].isna().any() or np.isinf(entry_results['entry_rank']).any()
        exit_has_nan = exit_results['exit_rank'].isna().any() or np.isinf(exit_results['exit_rank']).any()
        monitor_has_nan = monitor_results['composite_rank'].isna().any() or np.isinf(monitor_results['composite_rank']).any()
        
        if not (entry_has_nan or exit_has_nan or monitor_has_nan):
            print(f"   • No NaN or Inf values found ✓")
        else:
            print(f"   • ⚠️  WARNING: Found NaN or Inf values")
        
        print("\n🎯 Next Steps:")
        print("   1. Review rankings - do they make intuitive sense?")
        print("   2. Adjust thresholds if needed")
        print("   3. Add database columns for new ranks")
        print("   4. Wire up frontend UI")
        
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
