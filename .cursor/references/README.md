# Options Trading Strategies Skill

Expert-level framework for designing, modeling, and executing advanced multi-leg options strategies using Alpaca Markets APIs with institutional-grade quantitative analysis and risk management.

## Overview

This skill provides comprehensive capabilities for options trading strategy development, covering:

- **Strategy Design**: Straddles, strangles, butterflies, spreads, iron condors, calendar spreads
- **Quantitative Modeling**: Black-Scholes pricing, Greeks calculation, payoff analysis
- **Risk Management**: Position monitoring, delta hedging, automated stop-loss
- **Execution**: Alpaca API integration for multi-leg order submission
- **Automation**: Backtesting, parameter optimization, strategy deployment
- **Governance**: Compliance, documentation, audit trails

## Quick Start

### Prerequisites

1. **Alpaca Account**
   - Sign up at [Alpaca Markets](https://alpaca.markets/)
   - Generate API keys (recommended: start with paper trading)
   - Note: Options trading requires approval

2. **Python Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install alpaca-trade-api numpy pandas matplotlib scipy yfinance
   ```

3. **API Configuration**
   ```bash
   # Create .env file
   echo "ALPACA_API_KEY=your_key_id" > .env
   echo "ALPACA_SECRET_KEY=your_secret_key" >> .env
   echo "ALPACA_BASE_URL=https://paper-api.alpaca.markets" >> .env
   ```

### Basic Usage Examples

**Connect to Alpaca:**
```python
from alpaca_trade_api import REST
import os
from dotenv import load_dotenv

load_dotenv()

api = REST(
    key_id=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY'),
    base_url=os.getenv('ALPACA_BASE_URL')
)

# Verify connection
account = api.get_account()
print(f"Portfolio Value: ${account.portfolio_value}")
```

**Fetch Options Chain:**
```python
# Get available expiration dates
expirations = api.get_option_expirations('SPY')

# Get options chain for specific expiration
chain = api.get_option_chain('SPY', expiration=expirations[0])
print(f"Calls: {len(chain.calls)}, Puts: {len(chain.puts)}")
```

**Submit Long Straddle:**
```python
# Example: ATM straddle on SPY
symbol = 'SPY'
strike = 450.00
expiry = '250117'  # YYMMDD format

# Build option symbols (OCC format)
call_symbol = f"{symbol}{expiry}C{int(strike*1000):08d}"
put_symbol = f"{symbol}{expiry}P{int(strike*1000):08d}"

# Submit multi-leg order
order = api.submit_order(
    symbol=symbol,
    qty=1,
    side='buy',
    type='market',
    time_in_force='day',
    order_class='oto',
    legs=[
        {'symbol': call_symbol, 'qty': 1, 'side': 'buy'},
        {'symbol': put_symbol, 'qty': 1, 'side': 'buy'}
    ]
)

print(f"Order submitted: {order.id}")
```

## Skill Structure

```
options-strategies/
├── SKILL.md              # Complete skill documentation (36KB)
├── README.md            # This file - quick start guide
├── references/          # Reference materials and formulas
│   ├── greeks.md       # Greeks calculation reference
│   ├── strategies.md   # Strategy payoff formulas
│   ├── volatility.md   # IV analysis and forecasting
│   └── sources.md      # Authoritative source links
└── scripts/            # Python utilities
    ├── option_pricing.py      # Black-Scholes and Greeks
    ├── strategy_builder.py    # Multi-leg strategy construction
    ├── payoff_visualizer.py   # Profit/loss diagrams
    ├── backtester.py          # Strategy backtesting framework
    └── risk_manager.py        # Position monitoring and controls
```

## Core Capabilities

### 1. Strategy Design and Analysis

**Supported Strategies:**
- Long Straddle / Long Strangle (volatility expansion plays)
- Iron Butterfly / Iron Condor (volatility contraction)
- Calendar Spreads (time decay arbitrage)
- Vertical Spreads (directional defined-risk)

**Analysis Tools:**
- Payoff diagram generation
- Breakeven calculation
- Maximum profit/loss determination
- Greeks sensitivity analysis
- Monte Carlo simulation

### 2. Quantitative Modeling

**Option Pricing:**
- Black-Scholes model implementation
- Implied volatility calculation
- Historical vs. implied volatility comparison

**Greeks Calculation:**
- Delta: Directional exposure
- Gamma: Delta acceleration
- Theta: Time decay
- Vega: Volatility sensitivity
- Rho: Interest rate sensitivity

**Visualization:**
- 2D payoff diagrams
- 3D profit surfaces (price vs. IV)
- Greek exposure charts
- Time decay curves

### 3. Risk Management

**Position Monitoring:**
- Aggregate portfolio Greeks
- Real-time P/L tracking
- Delta neutrality checks
- Maximum loss validation

**Automated Controls:**
- Stop-loss execution
- Take-profit orders
- Delta hedging triggers
- Position size limits

### 4. Execution and Automation

**Order Management:**
- Multi-leg order submission
- Order status tracking
- Fill confirmation
- Error handling and retry logic

**Backtesting:**
- Historical data acquisition
- Strategy simulation
- Performance metrics calculation
- Parameter optimization

**Automated Trading:**
- Daily opportunity scanning
- Entry condition checking
- Position management
- Exit rule enforcement

## Learning Path

### Phase 1: Foundations (Week 1)
- Options terminology and mechanics
- Greeks and their interpretation
- Alpaca API setup and authentication
- Basic option chain navigation

**Deliverable**: Execute authenticated API calls, fetch options data

### Phase 2: Neutral Strategies (Week 2)
- Long straddle implementation
- Long strangle construction
- Volatility analysis
- Payoff modeling

**Deliverable**: Build and visualize neutral volatility strategies

### Phase 3: Multi-Leg Structures (Week 3)
- Iron butterfly design
- Calendar spread modeling
- Vertical spread mechanics
- Risk/reward optimization

**Deliverable**: Construct and execute 3-4 leg strategies

### Phase 4: Quantitative Analysis (Week 4)
- Black-Scholes implementation
- Greeks calculation
- Monte Carlo simulation
- 3D payoff surfaces

**Deliverable**: Complete quantitative analysis framework

### Phase 5: Risk Management (Week 5)
- Position monitoring systems
- Delta hedging automation
- Stop-loss implementation
- Performance tracking

**Deliverable**: Operational risk management system

### Phase 6: Automation (Week 6)
- Backtesting framework
- Parameter optimization
- Automated scanning
- Strategy deployment

**Deliverable**: End-to-end automated trading system

## Strategy Selection Matrix

| Market Condition | IV Rank | Strategy | Expected Outcome |
|-----------------|---------|----------|------------------|
| High uncertainty, any direction | High (>70) | Long Straddle | Profit from large move |
| Moderate uncertainty | High (>60) | Long Strangle | Profit from move, lower cost |
| Range-bound, low movement | High (>70) | Iron Butterfly | Profit from IV crush |
| Stable, sideways | High (>60) | Iron Condor | Profit from range-bound |
| Time decay advantage | Medium | Calendar Spread | Profit from theta differential |
| Moderate bullish | Medium | Bull Call Spread | Defined-risk directional |
| Moderate bearish | Medium | Bear Put Spread | Defined-risk directional |

## Risk Warnings

**Critical Considerations:**
- Options trading involves substantial risk of loss
- Multi-leg strategies can result in total loss of premium
- Always start with paper trading to validate strategies
- Understand maximum loss before entering any position
- Monitor positions regularly, especially near expiration
- Be aware of early assignment risk on short positions
- Account for transaction costs in profitability analysis

**Recommended Practices:**
- Never risk more than 2% of capital on single trade
- Maintain 3:1 minimum reward-to-risk ratio
- Use defined-risk strategies for most positions
- Keep position size small while learning
- Document all trades for review and improvement

## Integration with Other Ordinis-1 Skills

**Portfolio Management:**
- Import positions for comprehensive tracking
- Aggregate Greeks with equity portfolio delta
- Include options P/L in overall performance metrics

**Due Diligence:**
- Research underlying companies before trading
- Analyze earnings history and volatility patterns
- Document strategy rationale systematically

**Benchmarking:**
- Compare returns against VIX or CBOE indices
- Evaluate risk-adjusted performance metrics
- Track win rate and profit factor by strategy type

## Authoritative Sources

**Alpaca Resources:**
- [Alpaca API Documentation](https://docs.alpaca.markets/)
- [Alpaca Learn Center](https://alpaca.markets/learn/)
- [Alpaca GitHub](https://github.com/alpacahq)

**Industry Education:**
- [Options Industry Council](https://www.optionseducation.org/)
- [CBOE Education](https://www.cboe.com/education/)

**Quantitative References:**
- "Options, Futures, and Other Derivatives" - John Hull
- "Option Volatility and Pricing" - Sheldon Natenberg

## Installation for Claude

This skill can be imported into Claude for AI-assisted options analysis and strategy development.

**Import Instructions:**
1. The SKILL.md file contains the complete skill definition
2. Copy SKILL.md to your Claude skills directory:
   - For user skills: `C:\Users\[username]\.projects\intelligent-investor\skills\options-strategies\`
3. Claude will automatically detect and load the skill
4. Reference the skill in conversations: "Using the options-strategies skill..."

**Claude Integration Features:**
- Strategy recommendation based on market conditions
- Code generation for strategy implementation
- Payoff analysis and visualization
- Risk assessment and position sizing
- Documentation and trade rationale generation

## Support and Community

**Alpaca Community:**
- [Community Forum](https://forum.alpaca.markets/)
- [Slack Channel](https://alpaca.markets/slack)
- [GitHub Issues](https://github.com/alpacahq/alpaca-trade-api-python/issues)

**Options Communities:**
- r/options (Reddit)
- r/thetagang (Reddit - premium selling strategies)
- Elite Trader forums

## License and Disclaimer

This skill is provided for educational and research purposes only. It is not financial advice. Options trading involves substantial risk and may not be suitable for all investors. Always conduct thorough research and consider consulting with a financial advisor before trading.

All examples use Alpaca's paper trading environment. Live trading requires appropriate risk management, capital allocation, and regulatory compliance.

---

**Version**: 1.0.0
**Last Updated**: December 2024
**Maintainer**: Ordinis-1 Project
**License**: Educational Use
