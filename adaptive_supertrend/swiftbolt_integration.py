"""
SwiftBolt_ML platform integration for AdaptiveSuperTrend
Connects to your existing ML pipeline, Alpaca API, and real-time data streams

Author: SwiftBolt_ML
Date: January 2026
"""

import logging
import numpy as np
import pandas as pd
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import asdict
import json

from adaptive_supertrend import (
    AdaptiveSuperTrend,
    SuperTrendConfig,
    SuperTrendSignal,
    PerformanceMetrics
)
from supabase_integration import SupabaseAdaptiveSuperTrendSync

logger = logging.getLogger(__name__)


class TimeframeConfig:
    """Configuration for multiple timeframe analysis"""
    
    TIMEFRAMES = {
        '15m': 15,
        '1h': 60,
        '4h': 240,
        '1d': 1440
    }
    
    @staticmethod
    def get_bars_per_lookback(timeframe: str, days: int = 2) -> int:
        """
        Calculate number of bars needed for lookback period
        
        Args:
            timeframe: Timeframe string ('15m', '1h', etc.)
            days: Number of days to look back
        
        Returns:
            Number of bars
        """
        minutes_per_day = 24 * 60
        total_minutes = minutes_per_day * days
        tf_minutes = TimeframeConfig.TIMEFRAMES.get(timeframe, 60)
        return int(total_minutes / tf_minutes)


class MultiTimeframeAnalyzer:
    """Analyzes SuperTrend signals across multiple timeframes"""
    
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        config: Optional[SuperTrendConfig] = None
    ):
        self.sync = SupabaseAdaptiveSuperTrendSync(supabase_url, supabase_key, config)
        self.config = config or SuperTrendConfig()
    
    async def analyze_symbol(
        self,
        symbol: str,
        data_provider: 'DataProvider',  # Your data source (Alpaca, Polygon, etc.)
        timeframes: List[str] = ['15m', '1h', '4h']
    ) -> Dict[str, SuperTrendSignal]:
        """
        Generate SuperTrend signals across multiple timeframes
        
        Args:
            symbol: Stock symbol
            data_provider: Data fetching interface
            timeframes: List of timeframes to analyze
        
        Returns:
            Dict of timeframe -> signal
        """
        results = {}
        
        for timeframe in timeframes:
            try:
                # Fetch data for this timeframe
                n_bars = TimeframeConfig.get_bars_per_lookback(timeframe)
                data = await data_provider.fetch_bars(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=n_bars
                )
                
                if data is None or len(data) < 100:
                    logger.warning(f"Insufficient data for {symbol} {timeframe}")
                    continue
                
                # Extract OHLCV
                high = np.array([bar['h'] for bar in data])
                low = np.array([bar['l'] for bar in data])
                close = np.array([bar['c'] for bar in data])
                
                # Generate signal
                signal = await self.sync.process_symbol(
                    symbol=symbol,
                    timeframe=timeframe,
                    high=high.tolist(),
                    low=low.tolist(),
                    close=close.tolist(),
                    store_signal=True
                )
                
                if signal:
                    results[timeframe] = signal
                    logger.info(
                        f"{symbol} {timeframe}: trend={'📈' if signal.trend == 1 else '📉'}, "
                        f"strength={signal.signal_strength:.1f}/10, factor={signal.factor:.2f}"
                    )
            
            except Exception as e:
                logger.error(f"Error analyzing {symbol} {timeframe}: {e}")
        
        return results
    
    def get_consensus_signal(
        self,
        signals: Dict[str, SuperTrendSignal],
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Synthesize signals from multiple timeframes into consensus
        
        Args:
            signals: Dict of timeframe -> signal
            weights: Custom weights (default: 15m=0.3, 1h=0.4, 4h=0.3)
        
        Returns:
            Consensus analysis dict
        """
        if not signals:
            return {'consensus': 'UNKNOWN', 'confidence': 0}
        
        # Default weights favor 1h timeframe
        if weights is None:
            weights = {
                '15m': 0.25,
                '1h': 0.50,
                '4h': 0.25
            }
        
        # Calculate weighted consensus
        bullish_score = 0
        total_weight = 0
        
        for timeframe, signal in signals.items():
            weight = weights.get(timeframe, 0.25)
            if weight == 0:
                continue
            
            # Score: trend (1 or 0) * strength (0-1) * weight
            score = signal.trend * (signal.signal_strength / 10.0) * weight
            bullish_score += score
            total_weight += weight
        
        # Normalize
        avg_score = bullish_score / total_weight if total_weight > 0 else 0
        
        # Determine consensus
        if avg_score > 0.6:
            consensus = 'STRONG_BUY'
        elif avg_score > 0.3:
            consensus = 'BUY'
        elif avg_score > -0.3:
            consensus = 'NEUTRAL'
        elif avg_score > -0.6:
            consensus = 'SELL'
        else:
            consensus = 'STRONG_SELL'
        
        # Agreement across timeframes (how aligned they are)
        trends = [s.trend for s in signals.values()]
        agreement = max(trends.count(1), trends.count(0)) / len(trends) if trends else 0
        
        return {
            'consensus': consensus,
            'bullish_score': avg_score,
            'confidence': agreement,
            'num_timeframes': len(signals),
            'timeframe_signals': {tf: {'trend': s.trend, 'strength': s.signal_strength} 
                                 for tf, s in signals.items()},
            'recommendation': f"{'BUY' if avg_score > 0 else 'SELL'} with {agreement*100:.0f}% confidence"
        }


class MLFeatureExtractor:
    """Extracts adaptive SuperTrend features for ML models"""
    
    @staticmethod
    def extract_features(
        signals: Dict[str, SuperTrendSignal],
        consensus: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Extract features for feeding into RandomForest/XGBoost models
        
        Args:
            signals: MultiTimeframe signals
            consensus: Consensus analysis
        
        Returns:
            Feature dict for ML models
        """
        features = {}
        
        # Primary timeframe features (usually 1h)
        if '1h' in signals:
            s1h = signals['1h']
            features['ast_1h_trend'] = float(s1h.trend)
            features['ast_1h_strength'] = s1h.signal_strength / 10.0
            features['ast_1h_confidence'] = s1h.confidence
            features['ast_1h_distance'] = s1h.distance_pct
            features['ast_1h_factor'] = s1h.factor
            features['ast_1h_performance_index'] = s1h.performance_index
        
        # Secondary timeframe features (15m)
        if '15m' in signals:
            s15m = signals['15m']
            features['ast_15m_trend'] = float(s15m.trend)
            features['ast_15m_strength'] = s15m.signal_strength / 10.0
            features['ast_15m_confidence'] = s15m.confidence
        
        # Macro timeframe features (4h)
        if '4h' in signals:
            s4h = signals['4h']
            features['ast_4h_trend'] = float(s4h.trend)
            features['ast_4h_strength'] = s4h.signal_strength / 10.0
            features['ast_4h_confidence'] = s4h.confidence
        
        # Consensus features
        features['ast_consensus_bullish_score'] = consensus.get('bullish_score', 0.0)
        features['ast_consensus_confidence'] = consensus.get('confidence', 0.0)
        features['ast_trend_agreement'] = float(consensus.get('confidence', 0))
        
        # Trend alignment (do all timeframes agree?)
        trends = [s.trend for s in signals.values()]
        features['ast_aligned_bullish'] = float(all(t == 1 for t in trends))
        features['ast_aligned_bearish'] = float(all(t == 0 for t in trends))
        features['ast_conflict'] = float(len(set(trends)) > 1)
        
        return features


class PortfolioAdapter:
    """Adapts AdaptiveSuperTrend for portfolio-level analysis"""
    
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        portfolio_id: str
    ):
        self.sync = SupabaseAdaptiveSuperTrendSync(supabase_url, supabase_key)
        self.mta = MultiTimeframeAnalyzer(supabase_url, supabase_key)
        self.portfolio_id = portfolio_id
    
    async def analyze_portfolio(
        self,
        symbols: List[str],
        data_provider: 'DataProvider',
        timeframes: List[str] = ['15m', '1h', '4h']
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze all symbols in portfolio
        
        Args:
            symbols: List of stock symbols
            data_provider: Data source
            timeframes: Timeframes to analyze
        
        Returns:
            Dict of symbol -> {signals, consensus, features}
        """
        results = {}
        
        for symbol in symbols:
            try:
                # Multi-timeframe analysis
                signals = await self.mta.analyze_symbol(
                    symbol=symbol,
                    data_provider=data_provider,
                    timeframes=timeframes
                )
                
                # Get consensus
                consensus = self.mta.get_consensus_signal(signals)
                
                # Extract ML features
                features = MLFeatureExtractor.extract_features(signals, consensus)
                
                results[symbol] = {
                    'signals': signals,
                    'consensus': consensus,
                    'features': features,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            except Exception as e:
                logger.error(f"Portfolio analysis error for {symbol}: {e}")
                results[symbol] = {'error': str(e)}
        
        return results
    
    async def generate_trading_signals(
        self,
        portfolio_analysis: Dict[str, Dict[str, Any]],
        min_confidence: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Generate actionable trading signals from portfolio analysis
        
        Args:
            portfolio_analysis: Output from analyze_portfolio
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of trading signal recommendations
        """
        signals = []
        
        for symbol, analysis in portfolio_analysis.items():
            if 'error' in analysis:
                continue
            
            consensus = analysis['consensus']
            
            # Filter by confidence
            if consensus.get('confidence', 0) < min_confidence:
                continue
            
            # Generate signal
            signal_rec = {
                'symbol': symbol,
                'action': 'BUY' if consensus['bullish_score'] > 0 else 'SELL',
                'confidence': consensus['confidence'],
                'strength': consensus['bullish_score'],
                'consensus': consensus['consensus'],
                'recommendation': consensus['recommendation'],
                'factors': analysis['signals'],
                'features': analysis['features'],
                'timestamp': analysis['timestamp']
            }
            
            signals.append(signal_rec)
        
        # Sort by confidence (highest first)
        return sorted(signals, key=lambda x: x['confidence'], reverse=True)
    
    async def export_for_ml_training(
        self,
        portfolio_analysis: Dict[str, Dict[str, Any]],
        filename: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Export portfolio analysis features for ML training
        
        Args:
            portfolio_analysis: Output from analyze_portfolio
            filename: Optional CSV export filename
        
        Returns:
            DataFrame with all features
        """
        data_rows = []
        
        for symbol, analysis in portfolio_analysis.items():
            if 'error' in analysis:
                continue
            
            row = {'symbol': symbol}
            row.update(analysis['features'])
            row['consensus'] = analysis['consensus']['consensus']
            row['bullish_score'] = analysis['consensus']['bullish_score']
            row['timestamp'] = analysis['timestamp']
            data_rows.append(row)
        
        df = pd.DataFrame(data_rows)
        
        if filename:
            df.to_csv(filename, index=False)
            logger.info(f"Exported features to {filename}")
        
        return df


class DataProvider:
    """Abstract base class for data providers"""
    
    async def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500
    ) -> Optional[List[Dict[str, float]]]:
        """
        Fetch bars for a symbol/timeframe
        
        Returns list of: [{'t': timestamp, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume}, ...]
        """
        raise NotImplementedError


class AlpacaDataProvider(DataProvider):
    """Alpaca API data provider for SwiftBolt_ML"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = 'https://api.alpaca.markets'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
    
    async def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500
    ) -> Optional[List[Dict[str, float]]]:
        """
        Fetch historical bars from Alpaca
        
        Args:
            symbol: Stock symbol
            timeframe: '15m', '1h', '4h', '1d', etc.
            limit: Number of bars
        
        Returns:
            List of bar data
        """
        # This is a placeholder - implement with actual Alpaca SDK
        # Example:
        # from alpaca.data.historical import StockHistoricalDataClient
        #
        # client = StockHistoricalDataClient(self.api_key, self.api_secret)
        # bars = client.get_stock_bars(
        #     symbol=symbol,
        #     timeframe=TimeFrame.Minute15 if timeframe == '15m' else ...,
        #     limit=limit
        # )
        # return [{'t': b.timestamp, 'o': b.open, 'h': b.high, 'l': b.low, 'c': b.close, 'v': b.volume} ...]
        logger.warning("AlpacaDataProvider.fetch_bars not yet implemented")
        return None


if __name__ == "__main__":
    import os
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║  AdaptiveSuperTrend SwiftBolt_ML Integration Ready        ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  MultiTimeframeAnalyzer: Analyze 15m/1h/4h signals       ║
    ║  PortfolioAdapter: Portfolio-level analysis              ║
    ║  MLFeatureExtractor: Features for ML models              ║
    ║  DataProvider: Abstract data source interface            ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
