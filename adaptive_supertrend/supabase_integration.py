"""
Supabase integration for AdaptiveSuperTrend
Handles caching, persistence, and real-time factor updates

Author: SwiftBolt_ML
Date: January 2026
"""

import os
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import asdict

from supabase import create_client, Client
from adaptive_supertrend import (
    SuperTrendSignal,
    PerformanceMetrics,
    SuperTrendConfig,
    AdaptiveSuperTrend
)

logger = logging.getLogger(__name__)


class SupabaseFactorCache:
    """Manages adaptive SuperTrend factor caching in Supabase"""
    
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        table_name: str = 'adaptive_supertrend_cache'
    ):
        """
        Initialize Supabase client
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service key
            table_name: Table name for caching
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self.table_name = table_name
    
    async def get_cached_factor(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached optimal factor for symbol/timeframe
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            timeframe: Timeframe (e.g., '1h', '15m')
        
        Returns:
            Cache entry or None if expired/missing
        """
        try:
            result = self.client.table(self.table_name).select(
                '*'
            ).eq('symbol', symbol).eq('timeframe', timeframe).limit(1).execute()
            
            if not result.data:
                logger.debug(f"No cache entry for {symbol} {timeframe}")
                return None
            
            entry = result.data[0]
            
            # Check if expired
            updated_at = datetime.fromisoformat(entry['updated_at'].replace('Z', '+00:00'))
            ttl_hours = entry.get('ttl_hours', 24)
            
            if datetime.utcnow() - updated_at > timedelta(hours=ttl_hours):
                logger.debug(f"Cache expired for {symbol} {timeframe}")
                return None
            
            logger.debug(f"Cache hit for {symbol} {timeframe}: factor={entry['optimal_factor']}")
            return entry
        
        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
            return None
    
    async def set_cached_factor(
        self,
        symbol: str,
        timeframe: str,
        optimal_factor: float,
        metrics: PerformanceMetrics,
        ttl_hours: int = 24
    ) -> bool:
        """
        Store optimal factor in Supabase
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe
            optimal_factor: Best factor found
            metrics: Performance metrics
            ttl_hours: Time to live in hours
        
        Returns:
            Success status
        """
        try:
            cache_entry = {
                'symbol': symbol,
                'timeframe': timeframe,
                'optimal_factor': float(optimal_factor),
                'metrics': json.dumps(asdict(metrics)),
                'sharpe_ratio': metrics.sharpe_ratio,
                'sortino_ratio': metrics.sortino_ratio,
                'calmar_ratio': metrics.calmar_ratio,
                'win_rate': metrics.win_rate,
                'profit_factor': metrics.profit_factor,
                'max_drawdown': metrics.max_drawdown,
                'updated_at': datetime.utcnow().isoformat(),
                'ttl_hours': ttl_hours
            }
            
            # Upsert (insert or update)
            self.client.table(self.table_name).upsert(
                cache_entry,
                on_conflict='symbol,timeframe'
            ).execute()
            
            logger.info(
                f"Cached factor for {symbol} {timeframe}: "
                f"factor={optimal_factor:.2f}, sharpe={metrics.sharpe_ratio:.2f}"
            )
            return True
        
        except Exception as e:
            logger.error(f"Cache storage error: {e}")
            return False
    
    async def get_factor_history(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve historical factor values for analysis
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe
            limit: Max entries to retrieve
        
        Returns:
            List of historical cache entries
        """
        try:
            result = self.client.table(self.table_name).select(
                '*'
            ).eq('symbol', symbol).eq('timeframe', timeframe).order(
                'updated_at',
                desc=True
            ).limit(limit).execute()
            
            return result.data or []
        
        except Exception as e:
            logger.error(f"History retrieval error: {e}")
            return []
    
    async def cleanup_expired(
        self,
        older_than_hours: int = 48
    ) -> int:
        """
        Delete expired cache entries
        
        Args:
            older_than_hours: Delete entries older than this
        
        Returns:
            Number of deleted entries
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=older_than_hours)).isoformat()
            result = self.client.table(self.table_name).delete().lt(
                'updated_at',
                cutoff_time
            ).execute()
            
            logger.info(f"Cleaned up {len(result.data)} expired entries")
            return len(result.data)
        
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            return 0


class SupabaseSignalStorage:
    """Store and retrieve SuperTrend signals in Supabase"""
    
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        table_name: str = 'supertrend_signals'
    ):
        self.client: Client = create_client(supabase_url, supabase_key)
        self.table_name = table_name
    
    async def store_signal(
        self,
        signal: SuperTrendSignal,
        portfolio_id: Optional[str] = None
    ) -> bool:
        """
        Store a generated signal to Supabase
        
        Args:
            signal: SuperTrendSignal to store
            portfolio_id: Optional portfolio identifier
        
        Returns:
            Success status
        """
        try:
            signal_record = {
                'timestamp': signal.timestamp.isoformat(),
                'symbol': signal.symbol,
                'timeframe': signal.timeframe,
                'trend': signal.trend,
                'supertrend_value': signal.supertrend_value,
                'factor': signal.factor,
                'signal_strength': signal.signal_strength,
                'confidence': signal.confidence,
                'distance_pct': signal.distance_pct,
                'trend_duration': signal.trend_duration,
                'performance_index': signal.performance_index,
                'portfolio_id': portfolio_id
            }
            
            # Add metrics if available
            if signal.metrics:
                signal_record['metrics'] = json.dumps(asdict(signal.metrics))
            
            self.client.table(self.table_name).insert(signal_record).execute()
            
            logger.debug(f"Stored signal for {signal.symbol} {signal.timeframe}")
            return True
        
        except Exception as e:
            logger.error(f"Signal storage error: {e}")
            return False
    
    async def get_latest_signals(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retrieve latest signals
        
        Args:
            symbol: Filter by symbol (optional)
            timeframe: Filter by timeframe (optional)
            limit: Max results
        
        Returns:
            List of signal records
        """
        try:
            query = self.client.table(self.table_name).select('*')
            
            if symbol:
                query = query.eq('symbol', symbol)
            if timeframe:
                query = query.eq('timeframe', timeframe)
            
            result = query.order('timestamp', desc=True).limit(limit).execute()
            return result.data or []
        
        except Exception as e:
            logger.error(f"Signal retrieval error: {e}")
            return []
    
    async def get_signal_stats(
        self,
        symbol: str,
        timeframe: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get statistics on recent signals
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe
            hours: Look back hours
        
        Returns:
            Statistics dict
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            result = self.client.table(self.table_name).select(
                '*'
            ).eq('symbol', symbol).eq('timeframe', timeframe).gte(
                'timestamp',
                cutoff_time
            ).execute()
            
            signals = result.data or []
            
            if not signals:
                return {'count': 0, 'avg_strength': 0, 'trend_changes': 0}
            
            # Calculate stats
            strengths = [s['signal_strength'] for s in signals]
            trends = [s['trend'] for s in signals]
            trend_changes = sum(1 for i in range(1, len(trends)) if trends[i] != trends[i-1])
            
            return {
                'count': len(signals),
                'avg_strength': sum(strengths) / len(strengths),
                'max_strength': max(strengths),
                'min_strength': min(strengths),
                'trend_changes': trend_changes,
                'current_trend': trends[-1] if trends else None,
                'avg_confidence': sum(s['confidence'] for s in signals) / len(signals)
            }
        
        except Exception as e:
            logger.error(f"Stats calculation error: {e}")
            return {}


class SupabaseAdaptiveSuperTrendSync:
    """Complete integration of AdaptiveSuperTrend with Supabase"""
    
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        config: Optional[SuperTrendConfig] = None
    ):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.cache = SupabaseFactorCache(supabase_url, supabase_key)
        self.signal_storage = SupabaseSignalStorage(supabase_url, supabase_key)
        self.adaptive_st = AdaptiveSuperTrend(config=config)
    
    async def process_symbol(
        self,
        symbol: str,
        timeframe: str,
        high: List[float],
        low: List[float],
        close: List[float],
        store_signal: bool = True,
        portfolio_id: Optional[str] = None
    ) -> Optional[SuperTrendSignal]:
        """
        Complete pipeline: optimize factor, generate signal, store results
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe
            high, low, close: Price data
            store_signal: Whether to store in Supabase
            portfolio_id: Portfolio identifier
        
        Returns:
            Generated signal or None on error
        """
        import numpy as np
        
        try:
            # Convert to numpy arrays
            high_arr = np.array(high)
            low_arr = np.array(low)
            close_arr = np.array(close)
            
            # Generate signal with optimization
            signal = await self.adaptive_st.generate_signal_with_optimization(
                symbol=symbol,
                timeframe=timeframe,
                high=high_arr,
                low=low_arr,
                close=close_arr
            )
            
            # Cache the optimal factor
            if signal.metrics:
                await self.cache.set_cached_factor(
                    symbol=symbol,
                    timeframe=timeframe,
                    optimal_factor=signal.factor,
                    metrics=signal.metrics
                )
            
            # Store signal
            if store_signal:
                await self.signal_storage.store_signal(signal, portfolio_id)
            
            return signal
        
        except Exception as e:
            logger.error(f"Error processing {symbol} {timeframe}: {e}")
            return None
    
    async def process_portfolio(
        self,
        portfolio_data: Dict[str, Dict[str, Any]],
        portfolio_id: Optional[str] = None,
        store_signals: bool = True
    ) -> Dict[str, Optional[SuperTrendSignal]]:
        """
        Process multiple symbols in portfolio
        
        Args:
            portfolio_data {
                'AAPL': {'timeframe': '1h', 'high': [...], 'low': [...], 'close': [...]},
                ...
            }
            portfolio_id: Portfolio identifier
            store_signals: Whether to store in Supabase
        
        Returns:
            Dict of symbol -> signal
        """
        tasks = [
            self.process_symbol(
                symbol=symbol,
                timeframe=data['timeframe'],
                high=data['high'],
                low=data['low'],
                close=data['close'],
                store_signal=store_signals,
                portfolio_id=portfolio_id
            )
            for symbol, data in portfolio_data.items()
        ]
        
        results = await asyncio.gather(*tasks)
        return {symbol: signal for symbol, signal in zip(portfolio_data.keys(), results)}
    
    async def get_factor_trend(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Analyze trend in optimal factors over time
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe
            limit: Number of historical entries
        
        Returns:
            Analysis of factor evolution
        """
        try:
            history = await self.cache.get_factor_history(symbol, timeframe, limit)
            
            if not history:
                return {'error': 'No history available'}
            
            factors = [h['optimal_factor'] for h in history]
            sharpes = [h['sharpe_ratio'] for h in history]
            timestamps = [h['updated_at'] for h in history]
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'num_observations': len(factors),
                'current_factor': factors[0],  # Most recent
                'avg_factor': sum(factors) / len(factors),
                'factor_std': np.std(factors),
                'factor_trend': factors[0] - factors[-1],  # Recent vs oldest
                'avg_sharpe': sum(sharpes) / len(sharpes),
                'best_sharpe': max(sharpes),
                'factor_history': list(zip(timestamps, factors, sharpes))
            }
        
        except Exception as e:
            logger.error(f"Factor trend analysis error: {e}")
            return {'error': str(e)}


if __name__ == "__main__":
    import numpy as np
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load from environment
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables")
        exit(1)
    
    # Create sample data
    n_bars = 1000
    np.random.seed(42)
    close = np.cumsum(np.random.randn(n_bars) * 0.5) + 100
    high = close + np.abs(np.random.randn(n_bars) * 0.5)
    low = close - np.abs(np.random.randn(n_bars) * 0.5)
    
    # Initialize sync
    sync = SupabaseAdaptiveSuperTrendSync(SUPABASE_URL, SUPABASE_KEY)
    
    # Process single symbol
    async def main():
        signal = await sync.process_symbol(
            symbol='AAPL',
            timeframe='1h',
            high=high.tolist(),
            low=low.tolist(),
            close=close.tolist(),
            store_signal=True
        )
        
        if signal:
            print(f"Generated signal: {signal}")
            print(f"Factor: {signal.factor:.2f}")
            print(f"Strength: {signal.signal_strength:.1f}/10")
    
    asyncio.run(main())
