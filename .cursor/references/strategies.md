# Options Strategy Reference

Comprehensive reference for multi-leg options strategies with payoff formulas, risk/reward profiles, and implementation guidelines.

## Strategy Catalog

### Neutral Volatility Strategies

#### Long Straddle

**Structure:**
- Buy 1 ATM Call
- Buy 1 ATM Put
- Same strike, same expiration

**Market View:** Neutral direction, expect large price movement (volatility expansion)

**Payoff Formula:**
```
P/L = max(S - K, 0) + max(K - S, 0) - (C_premium + P_premium)

Where:
  S = Stock price at expiration
  K = Strike price (same for call and put)
  C_premium = Call premium paid
  P_premium = Put premium paid
```

**Key Metrics:**
- **Maximum Profit:** Unlimited (theoretically)
- **Maximum Loss:** Total premium paid = (C_premium + P_premium) × 100
- **Breakeven Points:**
  - Upper: K + Total Premium
  - Lower: K - Total Premium
- **Best Entry:** IV Rank > 50, before earnings or major events

**Greeks Profile:**
- Delta: ~0 (neutral)
- Gamma: Positive (increases with movement)
- Theta: Negative (loses value with time)
- Vega: Positive (benefits from IV expansion)

**Example Trade:**
```
SPY @ $450
Buy 1 SPY 450 Call @ $8.00
Buy 1 SPY 450 Put @ $7.50
Total Cost: $15.50 × 100 = $1,550

Breakevens: $434.50 and $465.50
Max Loss: $1,550
```

---

#### Long Strangle

**Structure:**
- Buy 1 OTM Call (higher strike)
- Buy 1 OTM Put (lower strike)
- Different strikes, same expiration

**Market View:** Neutral direction, expect significant movement, lower cost than straddle

**Payoff Formula:**
```
P/L = max(S - K_call, 0) + max(K_put - S, 0) - (C_premium + P_premium)

Where:
  K_call = Call strike (OTM above current price)
  K_put = Put strike (OTM below current price)
```

**Key Metrics:**
- **Maximum Profit:** Unlimited (theoretically)
- **Maximum Loss:** Total premium paid
- **Breakeven Points:**
  - Upper: K_call + Total Premium
  - Lower: K_put - Total Premium
- **Advantage:** Lower entry cost, wider profit zone
- **Disadvantage:** Requires larger movement to profit

**Greeks Profile:**
- Delta: ~0 (neutral)
- Gamma: Positive
- Theta: Negative (but less than straddle)
- Vega: Positive

**Example Trade:**
```
SPY @ $450
Buy 1 SPY 455 Call @ $4.50
Buy 1 SPY 445 Put @ $4.00
Total Cost: $8.50 × 100 = $850

Breakevens: $436.50 and $463.50
Max Loss: $850
Profit Zone Width: 27 points (vs. 31 points for straddle)
```

---

### Volatility Compression Strategies

#### Iron Butterfly

**Structure:**
- Sell 1 ATM Call
- Sell 1 ATM Put
- Buy 1 OTM Call (wing)
- Buy 1 OTM Put (wing)
- Same expiration, wings equidistant from ATM

**Market View:** Expect minimal price movement, volatility contraction

**Payoff Formula:**
```
P/L = Net_Premium - max(max(S - K_middle, 0) - (K_call_wing - K_middle), 0)
                   - max(max(K_middle - S, 0) - (K_middle - K_put_wing), 0)

Where:
  K_middle = ATM strike (short straddle)
  K_call_wing = OTM call strike (long)
  K_put_wing = OTM put strike (long)
  Net_Premium = Premium received from short straddle - Premium paid for wings
```

**Key Metrics:**
- **Maximum Profit:** Net premium received (at middle strike at expiration)
- **Maximum Loss:** (Wing Width - Net Premium) × 100
- **Breakeven Points:**
  - Upper: K_middle + Net Premium
  - Lower: K_middle - Net Premium
- **Best Entry:** IV Rank > 70, expect range-bound price action

**Greeks Profile:**
- Delta: ~0 (neutral)
- Gamma: Negative (position gets worse with large moves)
- Theta: Positive (profits from time decay)
- Vega: Negative (benefits from IV contraction)

**Example Trade:**
```
SPY @ $450
Sell 1 SPY 450 Call @ $8.00
Sell 1 SPY 450 Put @ $7.50
Buy 1 SPY 455 Call @ $4.00
Buy 1 SPY 445 Put @ $3.50
Net Credit: ($8.00 + $7.50) - ($4.00 + $3.50) = $8.00 × 100 = $800

Wing Width: $5.00
Max Profit: $800 (at $450 at expiration)
Max Loss: ($5.00 - $8.00) × 100 = -$300 Wait, this is wrong. Let me recalculate.
Max Loss: ($5.00 × 100) - $800 = $500 - $800... No.

Actually: Wing Width = $5, Net Credit = $8
If we bought wings for total $7.50 and sold middle for $15.50, net credit = $8
Max Loss = (Wing Width - Net Credit) × 100 = ($5 - $8) × 100

Wait, if net credit is $8 and wing width is $5, then:
Max Loss should be = $5 (wing width) - $8 (credit) = -$3, which means profit.

Let me recalculate properly:
Premiums received: $8.00 + $7.50 = $15.50
Premiums paid: $4.00 + $3.50 = $7.50
Net Credit: $8.00

Wing Width: $5.00
Max Loss if stock moves to wing: $5.00 - $8.00 = -$3.00 (profit still!)

This doesn't make sense. Let me think about the actual loss scenario:
- If SPY moves to $455 (upper wing):
  - Short 450 Call: -$5.00
  - Long 455 Call: $0.00
  - Short 450 Put: $0.00
  - Long 445 Put: $0.00
  - Loss on spread: $5.00
  - Net with credit: $5.00 - $8.00 = -$3.00 loss

Actually, I had the signs wrong. At the wing:
Max Loss = Wing Width - Net Credit = $5.00 - $8.00 = -$3.00
But loss should be positive, so the formula should be:
Max Loss = (Wing Width × 100) - (Net Credit × 100)

If Wing Width = $5 and Net Credit = $8, then Max Loss would be negative, meaning this is actually a net credit that's larger than the wing width, which would be unusual.

Let me use realistic numbers:
Sell 1 SPY 450 Call @ $5.00
Sell 1 SPY 450 Put @ $4.50
Buy 1 SPY 455 Call @ $2.00
Buy 1 SPY 445 Put @ $1.50

Net Credit: ($5.00 + $4.50) - ($2.00 + $1.50) = $6.00

At expiration:
- If SPY = $450: All options expire worthless, keep $600 profit
- If SPY = $455: Lose $5 on call spread, keep $4.50 on put side = -$0.50 total
  Plus initial credit of $6.00 = $5.50 profit still

Hmm, I need to recalculate more carefully.

Actually for an iron butterfly:
Max Profit = Net Credit Received
Max Loss = Strike Width - Net Credit Received

So with $5 strike width and $6 credit:
Max Loss = $5 - $6 = -$1 (which would mean this is always profitable - not realistic)

The issue is the premiums I chose don't make sense for an iron butterfly.

Let me use more realistic numbers:
Sell 1 SPY 450 Call @ $5.00
Sell 1 SPY 450 Put @ $4.50
Buy 1 SPY 455 Call @ $1.00
Buy 1 SPY 445 Put @ $0.75

Net Credit: ($5.00 + $4.50) - ($1.00 + $0.75) = $7.75

Max Profit: $7.75 × 100 = $775
Max Loss: ($5.00 - $7.75) × 100 = -$275

Still profitable at the wings, which seems wrong. The standard iron butterfly should have:
Max Loss = (Wing Width - Net Credit) × 100

Let me use real iron butterfly numbers where it makes sense:
Sell 1 SPY 450 Call @ $3.00
Sell 1 SPY 450 Put @ $2.80
Buy 1 SPY 460 Call @ $0.50
Buy 1 SPY 440 Put @ $0.30

Net Credit: ($3.00 + $2.80) - ($0.50 + $0.30) = $5.00
Wing Width: $10.00

Max Profit: $5.00 × 100 = $500 (at $450)
Max Loss: ($10.00 - $5.00) × 100 = $500 (at $460 or $440 or beyond)
Breakevens: $445 and $455
```

---

#### Iron Condor

**Structure:**
- Sell 1 OTM Put (lower middle strike)
- Buy 1 OTM Put (lower wing)
- Sell 1 OTM Call (upper middle strike)
- Buy 1 OTM Call (upper wing)
- Same expiration, creates range

**Market View:** Expect price to stay within range, volatility contraction

**Payoff Formula:**
```
P/L = Net_Premium
      - max(max(S - K_call_short, 0) - (K_call_long - K_call_short), 0)
      - max(max(K_put_short - S, 0) - (K_put_short - K_put_long), 0)
```

**Key Metrics:**
- **Maximum Profit:** Net premium received
- **Maximum Loss:** (Wing Width - Net Premium) × 100
- **Breakeven Points:**
  - Upper: Call short strike + Net Premium
  - Lower: Put short strike - Net Premium
- **Best Entry:** IV Rank > 60, wide expected range

**Example Trade:**
```
SPY @ $450
Buy 1 SPY 440 Put @ $0.50
Sell 1 SPY 445 Put @ $1.50
Sell 1 SPY 455 Call @ $1.60
Buy 1 SPY 460 Call @ $0.60

Net Credit: ($1.50 + $1.60) - ($0.50 + $0.60) = $2.00 × 100 = $200

Wing Width: $5.00
Max Profit: $200 (if SPY between $445-$455 at expiration)
Max Loss: ($5.00 - $2.00) × 100 = $300
Breakevens: $443 and $457
Profit Range: $443 to $457 (14 points wide)
```

---

### Time Decay Strategies

#### Calendar Spread (Time Spread)

**Structure:**
- Sell 1 near-term option (same strike)
- Buy 1 longer-term option (same strike)
- Same strike, different expirations

**Market View:** Minimal movement short-term, theta decay advantage

**Payoff Formula:**
```
P/L = (Long_Option_Value - Long_Premium_Paid)
      - (Short_Option_Value - Short_Premium_Received)

Note: Short option theta > Long option theta
```

**Key Metrics:**
- **Maximum Profit:** Occurs when short expires at strike, long retains value
- **Maximum Loss:** Net debit paid (if large move against position)
- **Profit Zone:** Near the strike at near-term expiration
- **Best Entry:** Low short-term IV, anticipate medium-term volatility

**Time Decay Comparison:**
```
30-day ATM option: Theta = -$0.05/day
60-day ATM option: Theta = -$0.03/day
Net theta capture: $0.02/day = $6/month potential
```

**Greeks Profile:**
- Delta: Near 0 at strike
- Gamma: Negative near expiration
- Theta: Positive (short-term decay faster)
- Vega: Positive (long-term more vega exposure)

**Example Trade:**
```
SPY @ $450
Sell 1 SPY Jan 450 Call @ $5.00 (30 days)
Buy 1 SPY Feb 450 Call @ $7.50 (60 days)
Net Debit: $2.50 × 100 = $250

At Jan expiration (if SPY = $450):
- Short Jan call expires worthless: Keep $500
- Long Feb call worth ~$5.00 = $500 value
- Total value: $1,000
- Net profit: $1,000 - $250 = $750

Risk: If SPY moves significantly away from $450, both options lose value
```

---

### Directional Defined-Risk Strategies

#### Bull Call Spread

**Structure:**
- Buy 1 lower strike call
- Sell 1 higher strike call
- Same expiration

**Market View:** Moderately bullish, defined risk

**Payoff Formula:**
```
P/L = min(max(S - K_long, 0), K_short - K_long) - Net_Debit

Where:
  K_long = Lower strike (bought)
  K_short = Higher strike (sold)
  Net_Debit = Long_Premium - Short_Premium
```

**Key Metrics:**
- **Maximum Profit:** (Strike Difference - Net Debit) × 100
- **Maximum Loss:** Net debit paid
- **Breakeven:** Lower strike + Net Debit
- **Best Entry:** Moderate bullish outlook, reduce capital requirement

**Example Trade:**
```
SPY @ $445
Buy 1 SPY 445 Call @ $6.00
Sell 1 SPY 455 Call @ $2.00
Net Debit: $4.00 × 100 = $400

Strike Difference: $10.00
Max Profit: ($10.00 - $4.00) × 100 = $600
Max Loss: $400
Breakeven: $449
Return on Risk: $600 / $400 = 150%
```

---

#### Bear Put Spread

**Structure:**
- Buy 1 higher strike put
- Sell 1 lower strike put
- Same expiration

**Market View:** Moderately bearish, defined risk

**Payoff Formula:**
```
P/L = min(max(K_long - S, 0), K_long - K_short) - Net_Debit

Where:
  K_long = Higher strike (bought)
  K_short = Lower strike (sold)
```

**Key Metrics:**
- **Maximum Profit:** (Strike Difference - Net Debit) × 100
- **Maximum Loss:** Net debit paid
- **Breakeven:** Higher strike - Net Debit
- **Best Entry:** Moderate bearish outlook

**Example Trade:**
```
SPY @ $455
Buy 1 SPY 455 Put @ $6.50
Sell 1 SPY 445 Put @ $2.50
Net Debit: $4.00 × 100 = $400

Max Profit: ($10.00 - $4.00) × 100 = $600
Max Loss: $400
Breakeven: $451
```

---

## Strategy Comparison Matrix

| Strategy | Delta | Gamma | Theta | Vega | Best IV Rank | Capital Required |
|----------|-------|-------|-------|------|--------------|------------------|
| Long Straddle | 0 | + | - | + | >50 | High |
| Long Strangle | 0 | + | - | + | >50 | Medium |
| Iron Butterfly | 0 | - | + | - | >70 | Low (credit) |
| Iron Condor | 0 | - | + | - | >60 | Low (credit) |
| Calendar Spread | ~0 | - | + | + | Variable | Medium |
| Bull Call Spread | + | Variable | - | + | <50 | Low |
| Bear Put Spread | - | Variable | - | + | <50 | Low |

## Greek Symbols Reference

- **Δ (Delta)**: Rate of change in option price per $1 move in underlying
- **Γ (Gamma)**: Rate of change in delta per $1 move in underlying
- **Θ (Theta)**: Rate of change in option price per 1 day passing
- **ν (Vega)**: Rate of change in option price per 1% change in IV
- **ρ (Rho)**: Rate of change in option price per 1% change in interest rates

---

*This reference is based on Alpaca Markets documentation and CBOE educational materials.*
