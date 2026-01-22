"""Greeks Validation and Alerting System.

Validates API Greeks against Black-Scholes theoretical values to identify
data quality issues and potential mispricing.

Usage:
    from src.monitoring.greeks_validator import GreeksValidator
    
    validator = GreeksValidator()
    
    # Validate all options
    discrepancies = validator.validate_options_greeks(
        symbols=['AAPL', 'MSFT', 'NVDA'],
        min_volume=100
    )
    
    # Generate report
    report = validator.generate_report(discrepancies)
    print(report)

Scheduled Usage:
    # Run daily as cron job
    python -m src.monitoring.greeks_validator --symbols AAPL MSFT NVDA
"""

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd

from src.data.supabase_db import db
from src.models.options_pricing import BlackScholesModel

logger = logging.getLogger(__name__)


@dataclass
class GreeksDiscrepancy:
    """Record of Greeks discrepancy between API and theoretical values.
    
    Attributes:
        ticker: Underlying symbol
        strike: Option strike price
        expiry: Expiration date
        side: 'call' or 'put'
        greek_name: Which Greek has discrepancy
        api_value: Value from API
        theoretical_value: Black-Scholes theoretical value
        difference: Absolute difference
        percent_diff: Percentage difference
        severity: 'low', 'medium', 'high', or 'critical'
    """
    ticker: str
    strike: float
    expiry: str
    side: str
    greek_name: str
    api_value: float
    theoretical_value: float
    difference: float
    percent_diff: float
    severity: str

class GreeksValidator:
    """Validate API Greeks against Black-Scholes theoretical values."""
    
    # Tolerance thresholds (what % difference is acceptable)
    DELTA_TOLERANCE = 0.05  # 5%
    GAMMA_TOLERANCE = 0.10  # 10% (more sensitive to calculation method)
    THETA_TOLERANCE = 0.15  # 15% (varies by conventions)
    VEGA_TOLERANCE = 0.10  # 10%
    
    def __init__(self, risk_free_rate: float = 0.045):
        """Initialize validator with Black-Scholes model.
        
        Args:
            risk_free_rate: Current risk-free rate (default: 4.5%)
        """
        self.db = db
        self.bs_model = BlackScholesModel(risk_free_rate=risk_free_rate)
        self.discrepancies: List[GreeksDiscrepancy] = []
        
        logger.info(f"Initialized GreeksValidator with r={risk_free_rate:.4f}")
    
    def validate_options_greeks(
        self,
        symbols: Optional[List[str]] = None,
        min_volume: int = 50,
        min_dte: int = 7,  # Skip options expiring in < 7 days
        max_dte: int = 365  # Skip LEAPS (> 1 year)
    ) -> pd.DataFrame:
        """Validate Greeks for options meeting liquidity and DTE criteria.
        
        Args:
            symbols: List of underlying symbols (None = all)
            min_volume: Minimum daily volume to include
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
        
        Returns:
            DataFrame of discrepancies (empty if none found)
        """
        logger.info(f"Validating Greeks for {len(symbols) if symbols else 'all'} symbols...")
        
        # Fetch options snapshots from database
        query = (
            self.db.client.table("options_snapshots")
            .select("*, symbols(ticker)")
            .gte("volume", min_volume)
            .gte("days_to_expiry", min_dte)
            .lte("days_to_expiry", max_dte)
        )
        
        if symbols:
            # Need to join with symbols table to filter by ticker
            query = query.in_("symbols.ticker", symbols)
        
        try:
            result = query.execute()
        except Exception as e:
            logger.error(f"Failed to fetch options data: {e}")
            return pd.DataFrame()
        
        if not result.data:
            logger.info("No options data to validate")
            return pd.DataFrame()
        
        df = pd.DataFrame(result.data)
        logger.info(f"Fetched {len(df)} options to validate")
        
        # Reset discrepancies
        self.discrepancies = []
        
        # Validate each option
        for _, row in df.iterrows():
            self._validate_single_option(row)
        
        # Convert to DataFrame
        if not self.discrepancies:
            logger.info("✅ No significant discrepancies found!")
            return pd.DataFrame()
        
        discrepancies_df = pd.DataFrame([vars(d) for d in self.discrepancies])
        
        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        discrepancies_df['severity_num'] = discrepancies_df['severity'].map(severity_order)
        discrepancies_df = discrepancies_df.sort_values('severity_num').drop('severity_num', axis=1)
        
        logger.info(f"Found {len(discrepancies_df)} discrepancies")
        
        return discrepancies_df
    
    def _validate_single_option(self, row: pd.Series):
        """Validate Greeks for a single option contract."""
        try:
            # Extract ticker from nested symbols object
            ticker = row['symbols']['ticker'] if isinstance(row.get('symbols'), dict) else 'UNKNOWN'
            
            # Calculate theoretical Greeks
            theoretical = self.bs_model.calculate_greeks(
                S=row['underlying_price'],
                K=row['strike'],
                T=row['days_to_expiry'] / 365,
                sigma=row['implied_volatility'],
                option_type=row['side']
            )
            
            # Check each Greek
            self._check_greek(row, ticker, 'delta', row['delta'], theoretical.delta, self.DELTA_TOLERANCE)
            self._check_greek(row, ticker, 'gamma', row['gamma'], theoretical.gamma, self.GAMMA_TOLERANCE)
            self._check_greek(row, ticker, 'theta', row['theta'], theoretical.theta, self.THETA_TOLERANCE)
            self._check_greek(row, ticker, 'vega', row['vega'], theoretical.vega, self.VEGA_TOLERANCE)
            
        except Exception as e:
            logger.error(f"Error validating option: {e}")
    
    def _check_greek(
        self,
        row: pd.Series,
        ticker: str,
        greek_name: str,
        api_value: float,
        theoretical_value: float,
        tolerance: float
    ):
        """Check if a Greek value is within tolerance."""
        # Skip if theoretical is very small (avoid division by zero)
        if abs(theoretical_value) < 1e-6:
            return
        
        diff = abs(api_value - theoretical_value)
        percent_diff = diff / abs(theoretical_value)
        
        if percent_diff > tolerance:
            # Determine severity
            if percent_diff > tolerance * 4:
                severity = 'critical'
            elif percent_diff > tolerance * 2:
                severity = 'high'
            elif percent_diff > tolerance * 1.5:
                severity = 'medium'
            else:
                severity = 'low'
            
            discrepancy = GreeksDiscrepancy(
                ticker=ticker,
                strike=row['strike'],
                expiry=row['expiry'],
                side=row['side'],
                greek_name=greek_name,
                api_value=api_value,
                theoretical_value=theoretical_value,
                difference=diff,
                percent_diff=percent_diff,
                severity=severity
            )
            
            self.discrepancies.append(discrepancy)
            
            if severity in ['high', 'critical']:
                logger.warning(
                    f"{severity.upper()}: {ticker} {row['side']} ${row['strike']:.2f} - "
                    f"{greek_name} API={api_value:.4f}, BS={theoretical_value:.4f} "
                    f"({percent_diff:.1%} difference)"
                )
    
    def generate_report(self, discrepancies_df: pd.DataFrame) -> str:
        """Generate human-readable validation report.
        
        Args:
            discrepancies_df: DataFrame from validate_options_greeks()
        
        Returns:
            Formatted text report
        """
        if discrepancies_df.empty:
            return "✅ All Greeks validated successfully. No discrepancies found."
        
        report = []
        report.append("🔍 Greeks Validation Report")
        report.append("=" * 70)
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Discrepancies: {len(discrepancies_df)}")
        
        # Summary by severity
        severity_counts = discrepancies_df['severity'].value_counts()
        report.append("\n📊 By Severity:")
        for severity in ['critical', 'high', 'medium', 'low']:
            count = severity_counts.get(severity, 0)
            if count > 0:
                emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}[severity]
                report.append(f"  {emoji} {severity.upper()}: {count}")
        
        # Summary by Greek
        greek_counts = discrepancies_df['greek_name'].value_counts()
        report.append("\n📈 By Greek:")
        for greek, count in greek_counts.items():
            report.append(f"  {greek}: {count}")
        
        # Summary by symbol
        symbol_counts = discrepancies_df['ticker'].value_counts().head(10)
        report.append(f"\n🔤 By Symbol (Top 10):")
        for symbol, count in symbol_counts.items():
            report.append(f"  {symbol}: {count}")
        
        # Top 10 worst discrepancies
        report.append("\n⚠️  Top 10 Largest Discrepancies:")
        top_10 = discrepancies_df.nlargest(10, 'percent_diff')
        for _, row in top_10.iterrows():
            emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}[row['severity']]
            report.append(
                f"  {emoji} {row['ticker']} {row['side']:4s} ${row['strike']:6.2f} {row['expiry']} - "
                f"{row['greek_name']}: API={row['api_value']:.4f}, "
                f"BS={row['theoretical_value']:.4f} ({row['percent_diff']:.1%})"
            )
        
        report.append("\n" + "=" * 70)
        
        return "\n".join(report)
    
    def save_report(self, discrepancies_df: pd.DataFrame, filename: str = None):
        """Save discrepancies to CSV file.
        
        Args:
            discrepancies_df: DataFrame from validate_options_greeks()
            filename: Output filename (default: greeks_discrepancies_YYYYMMDD.csv)
        """
        if discrepancies_df.empty:
            logger.info("No discrepancies to save")
            return
        
        if filename is None:
            filename = f"greeks_discrepancies_{datetime.now().strftime('%Y%m%d')}.csv"
        
        discrepancies_df.to_csv(filename, index=False)
        logger.info(f"💾 Saved {len(discrepancies_df)} discrepancies to {filename}")


def main():
    """CLI entry point for Greeks validation."""
    parser = argparse.ArgumentParser(
        description="Validate API Greeks against Black-Scholes theoretical values"
    )
    
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Symbols to validate (e.g., AAPL MSFT). If not provided, validates all.'
    )
    
    parser.add_argument(
        '--min-volume',
        type=int,
        default=50,
        help='Minimum daily volume (default: 50)'
    )
    
    parser.add_argument(
        '--save',
        action='store_true',
        help='Save discrepancies to CSV file'
    )
    
    parser.add_argument(
        '--risk-free-rate',
        type=float,
        default=0.045,
        help='Risk-free rate (default: 0.045 = 4.5%%)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("=" * 70)
    logger.info("Greeks Validation Job")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 70)
    
    # Create validator
    validator = GreeksValidator(risk_free_rate=args.risk_free_rate)
    
    # Validate
    discrepancies = validator.validate_options_greeks(
        symbols=args.symbols,
        min_volume=args.min_volume
    )
    
    # Generate report
    report = validator.generate_report(discrepancies)
    print("\n" + report)
    
    # Save if requested
    if args.save and not discrepancies.empty:
        validator.save_report(discrepancies)
    
    logger.info("=" * 70)
    logger.info("Validation Complete")
    logger.info("=" * 70)
    
    # Return exit code based on severity
    if not discrepancies.empty:
        critical = len(discrepancies[discrepancies['severity'] == 'critical'])
        high = len(discrepancies[discrepancies['severity'] == 'high'])
        
        if critical > 0:
            logger.error(f"🔴 {critical} CRITICAL discrepancies found!")
            return 2
        elif high > 5:  # More than 5 high-severity issues
            logger.warning(f"🟠 {high} HIGH severity discrepancies found")
            return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
