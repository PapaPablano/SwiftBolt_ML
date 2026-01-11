"""Genetic Algorithm for Options Trading Strategy Optimization.

Optimizes entry/exit timing and parameters to maximize profit from ranked options.
Integrates with OptionsMomentumRanker to learn optimal thresholds for:
1. Best entry points (when to buy based on rank + Greeks)
2. Best exit timing (when Greeks signal to exit)
3. Position sizing and risk management
4. Signal filtering (which signals work best)

Usage:
    from src.options_strategy_ga import OptionsStrategyGA, run_ga_optimization

    # Run optimization for a symbol
    results = run_ga_optimization("AAPL", generations=50)

    # Or use the class directly
    ga = OptionsStrategyGA(population_size=100, generations=50)
    results = ga.evolve(training_data, validation_data)
"""

import logging
import json
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================


class SignalType(Enum):
    """Signal types from OptionsMomentumRanker."""

    BUY = "buy"
    DISCOUNT = "discount"
    RUNNER = "runner"
    GREEKS = "greeks"
    ANY = "any"


@dataclass
class StrategyGenes:
    """Genetic parameters for options trading strategy.

    These parameters control when to enter, exit, and size positions
    based on the OptionsMomentumRanker scoring system.
    """

    # === RANKING THRESHOLDS (when to enter) ===
    min_composite_rank: float  # 50-95: Only buy options ranked above this
    min_momentum_score: float  # 0.3-0.8: Minimum momentum component
    min_value_score: float  # 0.2-0.7: Minimum value component
    signal_filter: str  # Which signal type to require

    # === ENTRY TIMING ===
    entry_hour_min: int  # 9-14: Earliest hour to enter (EST)
    entry_hour_max: int  # 10-15: Latest hour to enter
    min_bar_age_minutes: int  # 5-60: Don't buy on super fresh data

    # === GREEKS THRESHOLDS ===
    delta_exit: float  # 0.1-0.8: Exit if abs(delta) < this
    gamma_exit: float  # 0.01-0.1: Exit if gamma > this
    vega_exit: float  # 0.01-0.3: Exit if vega < this
    theta_min: float  # -0.5 to 0: Don't buy if theta < this
    iv_rank_min: float  # 10-40: Minimum IV rank to enter
    iv_rank_max: float  # 60-99: Maximum IV rank to enter

    # === HOLD TIMING ===
    min_hold_minutes: int  # 5-30: Don't exit too quickly
    max_hold_minutes: int  # 60-480: Force exit after this
    profit_target_pct: float  # 5-50: Take profit at this %
    stop_loss_pct: float  # -2 to -20: Cut loss at this %

    # === POSITION SIZING ===
    position_size_pct: float  # 1-10: % of capital per trade
    max_concurrent_trades: int  # 1-5: Max simultaneous positions

    # === TRADE FREQUENCY ===
    min_trades_per_day: int  # 1-5: Daily trade limit
    max_trades_per_symbol: int  # 1-10: Per-symbol limit

    @classmethod
    def random(cls) -> "StrategyGenes":
        """Generate random strategy within valid ranges."""
        return cls(
            min_composite_rank=np.random.uniform(55, 85),
            min_momentum_score=np.random.uniform(0.35, 0.70),
            min_value_score=np.random.uniform(0.25, 0.60),
            signal_filter=random.choice(["buy", "discount", "runner", "greeks", "any"]),
            entry_hour_min=np.random.randint(9, 12),
            entry_hour_max=np.random.randint(12, 15),
            min_bar_age_minutes=np.random.randint(5, 45),
            delta_exit=np.random.uniform(0.20, 0.60),
            gamma_exit=np.random.uniform(0.02, 0.07),
            vega_exit=np.random.uniform(0.02, 0.20),
            theta_min=np.random.uniform(-0.40, -0.08),
            iv_rank_min=np.random.uniform(15, 35),
            iv_rank_max=np.random.uniform(65, 90),
            min_hold_minutes=np.random.randint(10, 30),
            max_hold_minutes=np.random.randint(90, 360),
            profit_target_pct=np.random.uniform(8, 35),
            stop_loss_pct=np.random.uniform(-15, -3),
            position_size_pct=np.random.uniform(2, 6),
            max_concurrent_trades=np.random.randint(2, 4),
            min_trades_per_day=np.random.randint(1, 3),
            max_trades_per_symbol=np.random.randint(2, 6),
        )

    @classmethod
    def default(cls) -> "StrategyGenes":
        """Create conservative default strategy."""
        return cls(
            min_composite_rank=70.0,
            min_momentum_score=0.50,
            min_value_score=0.40,
            signal_filter="buy",
            entry_hour_min=10,
            entry_hour_max=14,
            min_bar_age_minutes=15,
            delta_exit=0.30,
            gamma_exit=0.05,
            vega_exit=0.05,
            theta_min=-0.20,
            iv_rank_min=20,
            iv_rank_max=75,
            min_hold_minutes=15,
            max_hold_minutes=240,
            profit_target_pct=15.0,
            stop_loss_pct=-8.0,
            position_size_pct=3.0,
            max_concurrent_trades=3,
            min_trades_per_day=2,
            max_trades_per_symbol=4,
        )

    def mutate(self, mutation_rate: float = 0.15) -> "StrategyGenes":
        """Create mutated copy of genes."""
        return StrategyGenes(
            min_composite_rank=self._mutate_float(self.min_composite_rank, 55, 85, mutation_rate),
            min_momentum_score=self._mutate_float(
                self.min_momentum_score, 0.35, 0.70, mutation_rate
            ),
            min_value_score=self._mutate_float(self.min_value_score, 0.25, 0.60, mutation_rate),
            signal_filter=(
                self.signal_filter
                if random.random() > mutation_rate
                else random.choice(["buy", "discount", "runner", "greeks", "any"])
            ),
            entry_hour_min=self._mutate_int(self.entry_hour_min, 9, 12, mutation_rate),
            entry_hour_max=self._mutate_int(self.entry_hour_max, 12, 15, mutation_rate),
            min_bar_age_minutes=self._mutate_int(self.min_bar_age_minutes, 5, 45, mutation_rate),
            delta_exit=self._mutate_float(self.delta_exit, 0.20, 0.60, mutation_rate),
            gamma_exit=self._mutate_float(self.gamma_exit, 0.02, 0.07, mutation_rate),
            vega_exit=self._mutate_float(self.vega_exit, 0.02, 0.20, mutation_rate),
            theta_min=self._mutate_float(self.theta_min, -0.40, -0.08, mutation_rate),
            iv_rank_min=self._mutate_float(self.iv_rank_min, 15, 35, mutation_rate),
            iv_rank_max=self._mutate_float(self.iv_rank_max, 65, 90, mutation_rate),
            min_hold_minutes=self._mutate_int(self.min_hold_minutes, 10, 30, mutation_rate),
            max_hold_minutes=self._mutate_int(self.max_hold_minutes, 90, 360, mutation_rate),
            profit_target_pct=self._mutate_float(self.profit_target_pct, 8, 35, mutation_rate),
            stop_loss_pct=self._mutate_float(self.stop_loss_pct, -15, -3, mutation_rate),
            position_size_pct=self._mutate_float(self.position_size_pct, 2, 6, mutation_rate),
            max_concurrent_trades=self._mutate_int(self.max_concurrent_trades, 2, 4, mutation_rate),
            min_trades_per_day=self._mutate_int(self.min_trades_per_day, 1, 3, mutation_rate),
            max_trades_per_symbol=self._mutate_int(self.max_trades_per_symbol, 2, 6, mutation_rate),
        )

    @staticmethod
    def _mutate_float(value: float, min_val: float, max_val: float, rate: float) -> float:
        if random.random() < rate:
            delta = np.random.normal(0, (max_val - min_val) * 0.12)
            return float(np.clip(value + delta, min_val, max_val))
        return value

    @staticmethod
    def _mutate_int(value: int, min_val: int, max_val: int, rate: float) -> int:
        if random.random() < rate:
            delta = int(np.random.normal(0, max(1, (max_val - min_val) * 0.15)))
            return int(np.clip(value + delta, min_val, max_val))
        return value

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "StrategyGenes":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class OptionTrade:
    """Represents a simulated options trade during backtesting."""

    symbol: str
    contract_symbol: str
    entry_date: str
    entry_price: float
    entry_rank: float
    entry_hour: int
    entry_signal: str

    # Greeks at entry
    delta_entry: float = 0.0
    gamma_entry: float = 0.0
    vega_entry: float = 0.0
    theta_entry: float = 0.0
    iv_rank_entry: float = 50.0

    # Exit info (filled when closed)
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    # Greeks at exit
    delta_exit: float = 0.0
    gamma_exit: float = 0.0
    vega_exit: float = 0.0
    theta_exit: float = 0.0

    # Position sizing
    size_pct: float = 1.0

    @property
    def pnl_pct(self) -> float:
        """Calculate P&L as percentage."""
        if self.exit_price is None or self.entry_price <= 0:
            return 0.0
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100 * self.size_pct

    @property
    def duration_minutes(self) -> int:
        """Calculate hold duration in minutes."""
        if self.exit_date is None:
            return 0
        try:
            entry = datetime.fromisoformat(self.entry_date)
            exit_dt = datetime.fromisoformat(self.exit_date)
            return int((exit_dt - entry).total_seconds() / 60)
        except Exception:
            return 0

    @property
    def is_closed(self) -> bool:
        return self.exit_price is not None


@dataclass
class StrategyFitness:
    """Multi-dimensional fitness metrics for strategy evaluation."""

    total_pnl: float
    pnl_pct: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    num_trades: int
    avg_trade_duration: int
    trades_closed: int

    def score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Calculate composite fitness score (0-1)."""
        if weights is None:
            weights = {
                "win_rate": 0.25,
                "profit_factor": 0.25,
                "sharpe": 0.20,
                "max_dd": 0.15,
                "trade_count": 0.15,
            }

        # Normalize components
        win_component = self.win_rate * weights.get("win_rate", 0.25)
        pf_component = min(self.profit_factor / 2.5, 1.0) * weights.get("profit_factor", 0.25)
        sharpe_component = min(max(self.sharpe_ratio + 1, 0), 3) / 3 * weights.get("sharpe", 0.20)
        dd_component = max(0, 1.0 - self.max_drawdown) * weights.get("max_dd", 0.15)
        trade_component = min(self.num_trades / 30, 1.0) * weights.get("trade_count", 0.15)

        return max(
            0,
            min(
                win_component + pf_component + sharpe_component + dd_component + trade_component,
                1.0,
            ),
        )

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================================
# OPTIONS STRATEGY BACKTESTER
# ============================================================================


class OptionsStrategy:
    """Backtestable options strategy using evolved genes."""

    def __init__(self, genes: StrategyGenes):
        self.genes = genes
        self.trades: List[OptionTrade] = []
        self.fitness: Optional[StrategyFitness] = None

    def backtest(
        self,
        options_data: pd.DataFrame,
        price_data: Optional[pd.DataFrame] = None,
        initial_capital: float = 100000,
    ) -> StrategyFitness:
        """
        Backtest strategy on historical options ranking data.

        Args:
            options_data: Historical rankings with columns:
                - datetime/run_at: timestamp
                - symbol: underlying symbol
                - contract_symbol: option contract identifier
                - composite_rank, momentum_score, value_score, greeks_score
                - signal_buy, signal_discount, signal_runner, signal_greeks
                - mark/last_price: option price
                - delta, gamma, vega, theta: Greeks
                - iv_rank: IV percentile
            price_data: Optional underlying price data for price simulation
            initial_capital: Starting capital for position sizing

        Returns:
            StrategyFitness with performance metrics
        """
        self.trades = []
        capital = initial_capital
        open_positions: Dict[str, OptionTrade] = {}
        daily_trades: Dict = {}
        symbol_trades: Dict[str, int] = {}

        # Sort data by time
        df = options_data.copy()
        time_col = "datetime" if "datetime" in df.columns else "run_at"

        if time_col in df.columns:
            df[time_col] = pd.to_datetime(df[time_col])
            df = df.sort_values(time_col)

        for idx, row in df.iterrows():
            current_time = row.get(time_col, datetime.now())
            if isinstance(current_time, str):
                current_time = datetime.fromisoformat(current_time.replace("Z", "+00:00"))

            symbol = row.get("symbol", row.get("underlying_symbol", "UNKNOWN"))
            hour = current_time.hour if hasattr(current_time, "hour") else 12

            # === CHECK EXITS ===
            positions_to_close = []

            for contract, trade in open_positions.items():
                should_exit, exit_reason = self._check_exit_conditions(trade, row, current_time)
                if should_exit:
                    positions_to_close.append((contract, exit_reason))

            # Close positions
            for contract, exit_reason in positions_to_close:
                trade = open_positions[contract]
                trade.exit_date = (
                    current_time.isoformat()
                    if hasattr(current_time, "isoformat")
                    else str(current_time)
                )
                trade.exit_price = self._get_price(row)
                trade.exit_reason = exit_reason
                trade.delta_exit = row.get("delta", 0)
                trade.gamma_exit = row.get("gamma", 0)
                trade.vega_exit = row.get("vega", 0)
                trade.theta_exit = row.get("theta", 0)

                # Update capital
                pnl = trade.pnl_pct * capital / 100
                capital += pnl

                self.trades.append(trade)
                del open_positions[contract]

            # === CHECK ENTRIES ===
            if len(open_positions) < self.genes.max_concurrent_trades:
                if self._should_enter(row, hour, daily_trades, symbol_trades, symbol, current_time):
                    contract = row.get("contract_symbol", f"{symbol}_{idx}")

                    if contract not in open_positions:
                        trade = OptionTrade(
                            symbol=symbol,
                            contract_symbol=contract,
                            entry_date=(
                                current_time.isoformat()
                                if hasattr(current_time, "isoformat")
                                else str(current_time)
                            ),
                            entry_price=self._get_price(row),
                            entry_rank=row.get("composite_rank", 50),
                            entry_hour=hour,
                            entry_signal=self._get_entry_signal(row),
                            delta_entry=row.get("delta", 0),
                            gamma_entry=row.get("gamma", 0),
                            vega_entry=row.get("vega", 0),
                            theta_entry=row.get("theta", 0),
                            iv_rank_entry=row.get("iv_rank", 50),
                            size_pct=self.genes.position_size_pct / 100,
                        )

                        open_positions[contract] = trade

                        # Track daily trades
                        if hasattr(current_time, "date"):
                            daily_key = current_time.date()
                            daily_trades[daily_key] = daily_trades.get(daily_key, 0) + 1

                        # Track symbol trades
                        symbol_trades[symbol] = symbol_trades.get(symbol, 0) + 1

        # Close remaining positions at end of backtest
        for contract, trade in open_positions.items():
            trade.exit_date = df.iloc[-1].get(time_col, datetime.now())
            if hasattr(trade.exit_date, "isoformat"):
                trade.exit_date = trade.exit_date.isoformat()
            trade.exit_price = self._get_price(df.iloc[-1])
            trade.exit_reason = "END_OF_BACKTEST"
            self.trades.append(trade)

        # Calculate fitness
        self.fitness = self._calculate_fitness(initial_capital, capital)
        return self.fitness

    def _get_price(self, row: pd.Series) -> float:
        """Extract price from row."""
        for col in ["mark", "last_price", "price", "mid"]:
            if col in row and pd.notna(row[col]) and row[col] > 0:
                return float(row[col])
        return 1.0

    def _should_enter(
        self,
        row: pd.Series,
        hour: int,
        daily_trades: Dict,
        symbol_trades: Dict[str, int],
        symbol: str,
        current_time,
    ) -> bool:
        """Check if entry conditions are met."""

        # Hour check
        if hour < self.genes.entry_hour_min or hour > self.genes.entry_hour_max:
            return False

        # Rank check
        composite_rank = row.get("composite_rank", 0)
        if composite_rank < self.genes.min_composite_rank:
            return False

        # Component score checks
        momentum = row.get("momentum_score", 0)
        value = row.get("value_score", 0)

        if momentum < self.genes.min_momentum_score * 100:
            return False
        if value < self.genes.min_value_score * 100:
            return False

        # Signal filter
        if self.genes.signal_filter != "any":
            signal_col = f"signal_{self.genes.signal_filter}"
            if not row.get(signal_col, False):
                return False

        # Greeks checks
        theta = row.get("theta", 0)
        if theta < self.genes.theta_min:
            return False

        iv_rank = row.get("iv_rank", 50)
        if iv_rank < self.genes.iv_rank_min or iv_rank > self.genes.iv_rank_max:
            return False

        # Daily trade limit
        if hasattr(current_time, "date"):
            today = current_time.date()
            if daily_trades.get(today, 0) >= self.genes.min_trades_per_day:
                return False

        # Symbol trade limit
        if symbol_trades.get(symbol, 0) >= self.genes.max_trades_per_symbol:
            return False

        # Price sanity check
        price = self._get_price(row)
        if price <= 0:
            return False

        return True

    def _check_exit_conditions(
        self, trade: OptionTrade, row: pd.Series, current_time
    ) -> Tuple[bool, str]:
        """Check if position should be exited."""

        # Calculate hold time
        try:
            entry_time = datetime.fromisoformat(trade.entry_date.replace("Z", "+00:00"))
            if isinstance(current_time, str):
                current_time = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
            hold_minutes = (current_time - entry_time).total_seconds() / 60
        except Exception:
            hold_minutes = 60

        # Minimum hold time
        if hold_minutes < self.genes.min_hold_minutes:
            return False, ""

        # Maximum hold time
        if hold_minutes > self.genes.max_hold_minutes:
            return True, "MAX_HOLD_TIME"

        # P&L checks
        current_price = self._get_price(row)
        if trade.entry_price > 0 and current_price > 0:
            pnl_pct = ((current_price - trade.entry_price) / trade.entry_price) * 100

            if pnl_pct >= self.genes.profit_target_pct:
                return True, "PROFIT_TARGET"

            if pnl_pct <= self.genes.stop_loss_pct:
                return True, "STOP_LOSS"

        # Greeks-based exits
        delta = abs(row.get("delta", 0.5))
        if delta < self.genes.delta_exit:
            return True, "DELTA_EXIT"

        gamma = row.get("gamma", 0)
        if gamma > self.genes.gamma_exit:
            return True, "GAMMA_EXIT"

        vega = row.get("vega", 0.1)
        if vega < self.genes.vega_exit:
            return True, "VEGA_EXIT"

        return False, ""

    def _get_entry_signal(self, row: pd.Series) -> str:
        """Determine which signal triggered entry."""
        if row.get("signal_buy", False):
            return "BUY"
        elif row.get("signal_discount", False):
            return "DISCOUNT"
        elif row.get("signal_runner", False):
            return "RUNNER"
        elif row.get("signal_greeks", False):
            return "GREEKS"
        return "RANK"

    def _calculate_fitness(self, initial_capital: float, final_capital: float) -> StrategyFitness:
        """Calculate fitness metrics from trades."""

        if not self.trades:
            return StrategyFitness(
                total_pnl=0,
                pnl_pct=0,
                win_rate=0,
                profit_factor=0,
                sharpe_ratio=0,
                max_drawdown=0,
                num_trades=0,
                avg_trade_duration=0,
                trades_closed=0,
            )

        closed_trades = [t for t in self.trades if t.is_closed]
        if not closed_trades:
            return StrategyFitness(
                total_pnl=0,
                pnl_pct=0,
                win_rate=0,
                profit_factor=0,
                sharpe_ratio=0,
                max_drawdown=0,
                num_trades=len(self.trades),
                avg_trade_duration=0,
                trades_closed=0,
            )

        # Calculate returns
        returns = [t.pnl_pct for t in closed_trades]
        wins = sum(1 for r in returns if r > 0)
        win_rate = wins / len(closed_trades)

        # Sharpe ratio (annualized, assuming ~250 trading days)
        avg_ret = np.mean(returns)
        std_ret = np.std(returns) if len(returns) > 1 else 1.0
        sharpe_ratio = (avg_ret / std_ret) * np.sqrt(250) if std_ret > 0 else 0

        # Max drawdown
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / (np.abs(running_max) + 1e-6)
        max_drawdown = abs(np.min(drawdown)) if len(drawdown) > 0 else 0

        # Profit factor
        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = abs(sum(r for r in returns if r < 0))
        profit_factor = (
            gross_profit / gross_loss if gross_loss > 0 else (2.0 if gross_profit > 0 else 0)
        )

        # Average duration
        durations = [t.duration_minutes for t in closed_trades if t.duration_minutes > 0]
        avg_duration = int(np.mean(durations)) if durations else 0

        total_pnl = final_capital - initial_capital
        pnl_pct = (total_pnl / initial_capital) * 100

        return StrategyFitness(
            total_pnl=total_pnl,
            pnl_pct=pnl_pct,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            num_trades=len(self.trades),
            avg_trade_duration=avg_duration,
            trades_closed=len(closed_trades),
        )


# ============================================================================
# GENETIC ALGORITHM
# ============================================================================


class OptionsStrategyGA:
    """Genetic Algorithm for evolving optimal options trading strategies."""

    def __init__(
        self,
        population_size: int = 100,
        generations: int = 50,
        elite_fraction: float = 0.10,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.70,
        tournament_size: int = 3,
    ):
        self.population_size = population_size
        self.generations = generations
        self.elite_fraction = elite_fraction
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.tournament_size = tournament_size

        self.population: List[OptionsStrategy] = []
        self.fitness_history: List[List[float]] = []
        self.best_strategies: List[OptionsStrategy] = []

        # Fitness weights
        self.fitness_weights = {
            "win_rate": 0.25,
            "profit_factor": 0.25,
            "sharpe": 0.20,
            "max_dd": 0.15,
            "trade_count": 0.15,
        }

    def initialize_population(self) -> None:
        """Create initial random population."""
        self.population = []

        # Add default strategy
        self.population.append(OptionsStrategy(StrategyGenes.default()))

        # Fill rest with random strategies
        while len(self.population) < self.population_size:
            self.population.append(OptionsStrategy(StrategyGenes.random()))

        logger.info(f"Initialized GA with {self.population_size} strategies")

    def evolve(
        self,
        training_data: pd.DataFrame,
        validation_data: Optional[pd.DataFrame] = None,
        verbose: bool = True,
    ) -> Dict:
        """
        Run genetic algorithm optimization.

        Args:
            training_data: Historical options ranking data for training
            validation_data: Optional separate data for validation
            verbose: Whether to log progress

        Returns:
            Dictionary with best strategies and metrics
        """
        self.initialize_population()

        best_fitness_overall = 0
        generations_without_improvement = 0

        for generation in range(self.generations):
            # Evaluate all strategies
            fitnesses = []
            for strategy in self.population:
                strategy.backtest(training_data)
                fitness_score = strategy.fitness.score(self.fitness_weights)
                fitnesses.append(fitness_score)

            self.fitness_history.append(fitnesses)

            # Track best
            current_best = max(fitnesses)
            if current_best > best_fitness_overall:
                best_fitness_overall = current_best
                generations_without_improvement = 0
            else:
                generations_without_improvement += 1

            # Early stopping if no improvement
            if generations_without_improvement > 10:
                if verbose:
                    logger.info(f"Early stopping at generation {generation + 1}")
                break

            # Selection - keep elite
            elite_count = max(2, int(self.population_size * self.elite_fraction))
            elite_indices = np.argsort(fitnesses)[-elite_count:]
            elite_strategies = [self.population[i] for i in elite_indices]

            # Create next generation
            new_population = [OptionsStrategy(s.genes) for s in elite_strategies]

            while len(new_population) < self.population_size:
                # Tournament selection
                parent1 = self._tournament_select(fitnesses)
                parent2 = self._tournament_select(fitnesses)

                # Crossover
                if random.random() < self.crossover_rate:
                    child1_genes, child2_genes = self._crossover(parent1.genes, parent2.genes)
                else:
                    child1_genes = parent1.genes
                    child2_genes = parent2.genes

                # Mutation
                if random.random() < self.mutation_rate:
                    child1_genes = child1_genes.mutate(self.mutation_rate)
                if random.random() < self.mutation_rate:
                    child2_genes = child2_genes.mutate(self.mutation_rate)

                new_population.append(OptionsStrategy(child1_genes))
                if len(new_population) < self.population_size:
                    new_population.append(OptionsStrategy(child2_genes))

            self.population = new_population[: self.population_size]

            # Log progress
            if verbose and (generation + 1) % 5 == 0:
                avg_fitness = np.mean(fitnesses)
                logger.info(
                    f"Gen {generation + 1}/{self.generations} | "
                    f"Best: {current_best:.3f} | Avg: {avg_fitness:.3f}"
                )

        # Final evaluation
        final_fitnesses = []
        for strategy in self.population:
            strategy.backtest(training_data)
            final_fitnesses.append(strategy.fitness.score(self.fitness_weights))

        # Get top 5 strategies
        best_indices = np.argsort(final_fitnesses)[-5:][::-1]
        self.best_strategies = [self.population[i] for i in best_indices]

        # Validation
        validation_results = None
        if validation_data is not None and not validation_data.empty:
            validation_results = self._validate_strategies(validation_data)

        return {
            "best_strategies": self.best_strategies,
            "best_genes": [s.genes.to_dict() for s in self.best_strategies],
            "best_fitness": [s.fitness.to_dict() for s in self.best_strategies],
            "training_fitness": [final_fitnesses[i] for i in best_indices],
            "fitness_history": self.fitness_history,
            "validation_results": validation_results,
            "generations_run": len(self.fitness_history),
        }

    def _tournament_select(self, fitnesses: List[float]) -> OptionsStrategy:
        """Tournament selection."""
        indices = np.random.choice(len(self.population), self.tournament_size, replace=False)
        best_idx = indices[np.argmax([fitnesses[i] for i in indices])]
        return self.population[best_idx]

    def _crossover(
        self, genes1: StrategyGenes, genes2: StrategyGenes
    ) -> Tuple[StrategyGenes, StrategyGenes]:
        """Blend crossover between two parents."""
        alpha = random.uniform(0.3, 0.7)

        child1 = StrategyGenes(
            min_composite_rank=alpha * genes1.min_composite_rank
            + (1 - alpha) * genes2.min_composite_rank,
            min_momentum_score=alpha * genes1.min_momentum_score
            + (1 - alpha) * genes2.min_momentum_score,
            min_value_score=alpha * genes1.min_value_score + (1 - alpha) * genes2.min_value_score,
            signal_filter=genes1.signal_filter if random.random() < 0.5 else genes2.signal_filter,
            entry_hour_min=int(alpha * genes1.entry_hour_min + (1 - alpha) * genes2.entry_hour_min),
            entry_hour_max=int(alpha * genes1.entry_hour_max + (1 - alpha) * genes2.entry_hour_max),
            min_bar_age_minutes=int(
                alpha * genes1.min_bar_age_minutes + (1 - alpha) * genes2.min_bar_age_minutes
            ),
            delta_exit=alpha * genes1.delta_exit + (1 - alpha) * genes2.delta_exit,
            gamma_exit=alpha * genes1.gamma_exit + (1 - alpha) * genes2.gamma_exit,
            vega_exit=alpha * genes1.vega_exit + (1 - alpha) * genes2.vega_exit,
            theta_min=alpha * genes1.theta_min + (1 - alpha) * genes2.theta_min,
            iv_rank_min=alpha * genes1.iv_rank_min + (1 - alpha) * genes2.iv_rank_min,
            iv_rank_max=alpha * genes1.iv_rank_max + (1 - alpha) * genes2.iv_rank_max,
            min_hold_minutes=int(
                alpha * genes1.min_hold_minutes + (1 - alpha) * genes2.min_hold_minutes
            ),
            max_hold_minutes=int(
                alpha * genes1.max_hold_minutes + (1 - alpha) * genes2.max_hold_minutes
            ),
            profit_target_pct=alpha * genes1.profit_target_pct
            + (1 - alpha) * genes2.profit_target_pct,
            stop_loss_pct=alpha * genes1.stop_loss_pct + (1 - alpha) * genes2.stop_loss_pct,
            position_size_pct=alpha * genes1.position_size_pct
            + (1 - alpha) * genes2.position_size_pct,
            max_concurrent_trades=int(
                alpha * genes1.max_concurrent_trades + (1 - alpha) * genes2.max_concurrent_trades
            ),
            min_trades_per_day=int(
                alpha * genes1.min_trades_per_day + (1 - alpha) * genes2.min_trades_per_day
            ),
            max_trades_per_symbol=int(
                alpha * genes1.max_trades_per_symbol + (1 - alpha) * genes2.max_trades_per_symbol
            ),
        )

        # Create second child with inverted blend
        child2 = StrategyGenes(
            min_composite_rank=(1 - alpha) * genes1.min_composite_rank
            + alpha * genes2.min_composite_rank,
            min_momentum_score=(1 - alpha) * genes1.min_momentum_score
            + alpha * genes2.min_momentum_score,
            min_value_score=(1 - alpha) * genes1.min_value_score + alpha * genes2.min_value_score,
            signal_filter=genes2.signal_filter if random.random() < 0.5 else genes1.signal_filter,
            entry_hour_min=int((1 - alpha) * genes1.entry_hour_min + alpha * genes2.entry_hour_min),
            entry_hour_max=int((1 - alpha) * genes1.entry_hour_max + alpha * genes2.entry_hour_max),
            min_bar_age_minutes=int(
                (1 - alpha) * genes1.min_bar_age_minutes + alpha * genes2.min_bar_age_minutes
            ),
            delta_exit=(1 - alpha) * genes1.delta_exit + alpha * genes2.delta_exit,
            gamma_exit=(1 - alpha) * genes1.gamma_exit + alpha * genes2.gamma_exit,
            vega_exit=(1 - alpha) * genes1.vega_exit + alpha * genes2.vega_exit,
            theta_min=(1 - alpha) * genes1.theta_min + alpha * genes2.theta_min,
            iv_rank_min=(1 - alpha) * genes1.iv_rank_min + alpha * genes2.iv_rank_min,
            iv_rank_max=(1 - alpha) * genes1.iv_rank_max + alpha * genes2.iv_rank_max,
            min_hold_minutes=int(
                (1 - alpha) * genes1.min_hold_minutes + alpha * genes2.min_hold_minutes
            ),
            max_hold_minutes=int(
                (1 - alpha) * genes1.max_hold_minutes + alpha * genes2.max_hold_minutes
            ),
            profit_target_pct=(1 - alpha) * genes1.profit_target_pct
            + alpha * genes2.profit_target_pct,
            stop_loss_pct=(1 - alpha) * genes1.stop_loss_pct + alpha * genes2.stop_loss_pct,
            position_size_pct=(1 - alpha) * genes1.position_size_pct
            + alpha * genes2.position_size_pct,
            max_concurrent_trades=int(
                (1 - alpha) * genes1.max_concurrent_trades + alpha * genes2.max_concurrent_trades
            ),
            min_trades_per_day=int(
                (1 - alpha) * genes1.min_trades_per_day + alpha * genes2.min_trades_per_day
            ),
            max_trades_per_symbol=int(
                (1 - alpha) * genes1.max_trades_per_symbol + alpha * genes2.max_trades_per_symbol
            ),
        )

        return child1, child2

    def _validate_strategies(self, validation_data: pd.DataFrame) -> List[Dict]:
        """Test best strategies on validation data."""
        results = []

        for i, strategy in enumerate(self.best_strategies):
            strategy.backtest(validation_data)
            results.append(
                {
                    "rank": i + 1,
                    "genes": strategy.genes.to_dict(),
                    "fitness": strategy.fitness.to_dict(),
                    "trades": len(strategy.trades),
                }
            )

        return results

    def save_results(self, output_dir: str = "ga_results") -> str:
        """Save best strategies to JSON files."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for i, strategy in enumerate(self.best_strategies):
            result = {
                "rank": i + 1,
                "timestamp": timestamp,
                "genes": strategy.genes.to_dict(),
                "fitness": strategy.fitness.to_dict() if strategy.fitness else {},
                "sample_trades": [
                    {
                        "symbol": t.symbol,
                        "contract": t.contract_symbol,
                        "entry_price": t.entry_price,
                        "exit_price": t.exit_price,
                        "pnl_pct": t.pnl_pct,
                        "duration_min": t.duration_minutes,
                        "exit_reason": t.exit_reason,
                    }
                    for t in strategy.trades[:15]
                ],
            }

            filepath = output_path / f"strategy_{i+1}_{timestamp}.json"
            with open(filepath, "w") as f:
                json.dump(result, f, indent=2, default=str)

        logger.info(f"Saved {len(self.best_strategies)} strategies to {output_dir}")
        return str(output_path)


# ============================================================================
# DATABASE INTEGRATION
# ============================================================================


def fetch_training_data(symbol: str, days: int = 30, db_client=None) -> pd.DataFrame:
    """
    Fetch historical options ranking data for GA training.

    Args:
        symbol: Underlying symbol
        days: Number of days of history
        db_client: Supabase client (if None, creates new)

    Returns:
        DataFrame with ranking history
    """
    if db_client is None:
        from src.data.supabase_db import db

        db_client = db.client

    start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

    try:
        # Fetch from options_ranks table
        response = (
            db_client.table("options_ranks")
            .select(
                "contract_symbol, run_at, composite_rank, momentum_score, value_score, greeks_score, "
                "signal_buy, signal_discount, signal_runner, signal_greeks, "
                "mark, last_price, delta, gamma, theta, vega, iv_rank, "
                "underlying_symbol_id(ticker)"
            )
            .gte("run_at", start_date)
            .execute()
        )

        if response.data:
            df = pd.DataFrame(response.data)
            # Flatten nested symbol
            if "underlying_symbol_id" in df.columns:
                df["symbol"] = df["underlying_symbol_id"].apply(
                    lambda x: x.get("ticker", symbol) if isinstance(x, dict) else symbol
                )
            else:
                df["symbol"] = symbol

            df["datetime"] = pd.to_datetime(df["run_at"])
            return df
    except Exception as e:
        logger.error(f"Error fetching training data: {e}")

    return pd.DataFrame()


def save_ga_parameters(
    symbol: str, genes: StrategyGenes, fitness: StrategyFitness, db_client=None
) -> bool:
    """
    Save GA-optimized parameters to database.

    Args:
        symbol: Underlying symbol
        genes: Optimized strategy genes
        fitness: Fitness metrics from backtesting
        db_client: Supabase client

    Returns:
        Success status
    """
    if db_client is None:
        from src.data.supabase_db import db

        db_client = db.client

    try:
        record = {
            "symbol": symbol,
            "genes": genes.to_dict(),
            "fitness": fitness.to_dict(),
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True,
        }

        # Deactivate old parameters
        db_client.table("ga_strategy_params").update({"is_active": False}).eq(
            "symbol", symbol
        ).execute()

        # Insert new
        db_client.table("ga_strategy_params").insert(record).execute()

        logger.info(f"Saved GA parameters for {symbol}")
        return True
    except Exception as e:
        logger.error(f"Error saving GA parameters: {e}")
        return False


def load_ga_parameters(symbol: str, db_client=None) -> Optional[StrategyGenes]:
    """
    Load active GA parameters for a symbol.

    Args:
        symbol: Underlying symbol
        db_client: Supabase client

    Returns:
        StrategyGenes if found, None otherwise
    """
    if db_client is None:
        from src.data.supabase_db import db

        db_client = db.client

    try:
        response = (
            db_client.table("ga_strategy_params")
            .select("genes")
            .eq("symbol", symbol)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            genes_dict = response.data[0].get("genes", {})
            return StrategyGenes.from_dict(genes_dict)
    except Exception as e:
        logger.error(f"Error loading GA parameters: {e}")

    return None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def run_ga_optimization(
    symbol: str,
    generations: int = 50,
    population_size: int = 100,
    training_days: int = 30,
    validation_split: float = 0.2,
    save_to_db: bool = True,
) -> Dict:
    """
    Run full GA optimization for a symbol.

    Args:
        symbol: Underlying symbol to optimize
        generations: Number of GA generations
        population_size: Size of GA population
        training_days: Days of historical data
        validation_split: Fraction for validation
        save_to_db: Whether to save results to database

    Returns:
        Optimization results dictionary
    """
    logger.info(f"Starting GA optimization for {symbol}")

    # Fetch data
    data = fetch_training_data(symbol, days=training_days)

    if data.empty:
        logger.error(f"No training data found for {symbol}")
        return {"error": "No training data"}

    logger.info(f"Loaded {len(data)} ranking records for training")

    # Split data
    split_idx = int(len(data) * (1 - validation_split))
    training_data = data.iloc[:split_idx]
    validation_data = data.iloc[split_idx:] if validation_split > 0 else None

    # Run GA
    ga = OptionsStrategyGA(population_size=population_size, generations=generations)

    results = ga.evolve(training_data, validation_data)

    # Save to database
    if save_to_db and results.get("best_strategies"):
        best = results["best_strategies"][0]
        save_ga_parameters(symbol, best.genes, best.fitness)

    # Save to files
    ga.save_results(f"ga_results/{symbol}")

    return results


def analyze_strategy(strategy: OptionsStrategy) -> Dict:
    """Generate insights from strategy performance."""
    trades = strategy.trades
    closed_trades = [t for t in trades if t.is_closed]

    if not closed_trades:
        return {"error": "No closed trades"}

    analysis = {
        "total_trades": len(trades),
        "closed_trades": len(closed_trades),
        "win_rate": strategy.fitness.win_rate if strategy.fitness else 0,
        "profit_factor": strategy.fitness.profit_factor if strategy.fitness else 0,
        "avg_pnl_pct": np.mean([t.pnl_pct for t in closed_trades]),
        "signal_breakdown": {},
        "exit_reason_breakdown": {},
        "best_hour": None,
    }

    # Signal analysis
    for signal in set(t.entry_signal for t in closed_trades):
        signal_trades = [t for t in closed_trades if t.entry_signal == signal]
        wins = sum(1 for t in signal_trades if t.pnl_pct > 0)
        analysis["signal_breakdown"][signal] = {
            "count": len(signal_trades),
            "win_rate": wins / len(signal_trades) if signal_trades else 0,
            "avg_pnl": np.mean([t.pnl_pct for t in signal_trades]),
        }

    # Exit reason analysis
    for reason in set(t.exit_reason for t in closed_trades if t.exit_reason):
        reason_trades = [t for t in closed_trades if t.exit_reason == reason]
        wins = sum(1 for t in reason_trades if t.pnl_pct > 0)
        analysis["exit_reason_breakdown"][reason] = {
            "count": len(reason_trades),
            "win_rate": wins / len(reason_trades) if reason_trades else 0,
            "avg_pnl": np.mean([t.pnl_pct for t in reason_trades]),
        }

    # Hour analysis
    hour_pnl = {}
    for t in closed_trades:
        if t.entry_hour not in hour_pnl:
            hour_pnl[t.entry_hour] = []
        hour_pnl[t.entry_hour].append(t.pnl_pct)

    if hour_pnl:
        analysis["best_hour"] = max(hour_pnl.items(), key=lambda x: np.mean(x[1]))[0]

    return analysis


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="Options Strategy GA Optimization")
    parser.add_argument("--symbol", type=str, default="AAPL", help="Symbol to optimize")
    parser.add_argument("--generations", type=int, default=50, help="Number of generations")
    parser.add_argument("--population", type=int, default=100, help="Population size")
    parser.add_argument("--days", type=int, default=30, help="Training data days")
    parser.add_argument("--no-save", action="store_true", help="Don't save to database")

    args = parser.parse_args()

    results = run_ga_optimization(
        symbol=args.symbol.upper(),
        generations=args.generations,
        population_size=args.population,
        training_days=args.days,
        save_to_db=not args.no_save,
    )

    if "error" not in results:
        print("\n" + "=" * 60)
        print("GA OPTIMIZATION COMPLETE")
        print("=" * 60)

        best = results["best_strategies"][0]
        print(f"\nBest Strategy Fitness:")
        print(f"  Win Rate: {best.fitness.win_rate:.1%}")
        print(f"  Profit Factor: {best.fitness.profit_factor:.2f}")
        print(f"  Sharpe Ratio: {best.fitness.sharpe_ratio:.2f}")
        print(f"  Max Drawdown: {best.fitness.max_drawdown:.1%}")
        print(f"  Total Trades: {best.fitness.num_trades}")

        print(f"\nOptimized Parameters:")
        genes = best.genes
        print(f"  Min Composite Rank: {genes.min_composite_rank:.1f}")
        print(f"  Signal Filter: {genes.signal_filter}")
        print(f"  Entry Hours: {genes.entry_hour_min}-{genes.entry_hour_max}")
        print(f"  Profit Target: {genes.profit_target_pct:.1f}%")
        print(f"  Stop Loss: {genes.stop_loss_pct:.1f}%")
        print(f"  IV Rank Range: {genes.iv_rank_min:.0f}-{genes.iv_rank_max:.0f}")
    else:
        print(f"Error: {results['error']}")
