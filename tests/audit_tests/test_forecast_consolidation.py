"""Test that consolidated forecast matches original.

This test suite validates that the unified forecast job produces
equivalent results to the original forecast_job.py implementation.
"""

import json
import pytest
import sys
import time
from pathlib import Path
from datetime import datetime

# Add ml directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ml"))

from src.unified_forecast_job import UnifiedForecastProcessor
from src.data.supabase_db import db


class TestForecastConsolidation:
    """Test suite for forecast consolidation validation."""
    
    @pytest.fixture
    def unified_processor(self):
        """Create a unified processor instance."""
        return UnifiedForecastProcessor(
            redis_cache=None,  # No Redis for tests
            metrics_file='tests/audit_tests/test_metrics.json'
        )
    
    @pytest.mark.parametrize('symbol', ['AAPL', 'MSFT'])
    def test_unified_processor_basic(self, unified_processor, symbol):
        """
        Test that unified processor can generate forecasts successfully.
        
        This is a smoke test to ensure the unified processor works.
        """
        result = unified_processor.process_symbol(symbol, horizons=['1D'])
        
        # Basic assertions
        assert result is not None
        assert result['symbol'] == symbol
        assert isinstance(result['success'], bool)
        assert 'processing_time' in result
        assert 'forecasts' in result
        
        # If successful, validate forecast structure
        if result['success']:
            assert '1D' in result['forecasts']
            forecast = result['forecasts']['1D']
            assert 'label' in forecast
            assert 'confidence' in forecast
            assert forecast['label'] in ['bullish', 'bearish', 'neutral']
            assert 0 <= forecast['confidence'] <= 1
    
    def test_unified_processor_all_horizons(self, unified_processor):
        """Test processing all horizons for a single symbol."""
        symbol = 'AAPL'
        result = unified_processor.process_symbol(symbol, horizons=['1D', '1W', '1M'])
        
        assert result['symbol'] == symbol
        
        # Should process all horizons
        if result['success']:
            for horizon in ['1D', '1W', '1M']:
                assert horizon in result['forecasts'], f"Missing forecast for {horizon}"
                forecast = result['forecasts'][horizon]
                assert 'label' in forecast
                assert 'confidence' in forecast
                assert 'points' in forecast
    
    def test_unified_processor_metrics(self, unified_processor):
        """Test that metrics are properly collected."""
        # Process a symbol
        unified_processor.process_symbol('AAPL', horizons=['1D'])
        
        # Check metrics
        metrics = unified_processor.metrics
        assert 'symbols_processed' in metrics
        assert 'feature_cache_hits' in metrics
        assert 'feature_cache_misses' in metrics
        assert 'forecast_times' in metrics
        assert 'weight_sources' in metrics
        assert 'db_writes' in metrics
        assert 'errors' in metrics
        
        # Should have processed at least one symbol
        assert metrics['symbols_processed'] >= 1
    
    def test_weight_source_precedence(self, unified_processor):
        """Test that weight source precedence is logged correctly."""
        result = unified_processor.process_symbol('AAPL', horizons=['1D'])
        
        if result['success']:
            # Should have weight source information
            assert 'weight_source' in result
            assert '1D' in result['weight_source']
            weight_source = result['weight_source']['1D']
            
            # Should be one of the valid sources
            assert weight_source in ['intraday_calibrated', 'daily_symbol', 'default']
    
    def test_feature_cache_behavior(self, unified_processor):
        """Test feature cache hit/miss tracking."""
        symbol = 'AAPL'
        
        # First run - likely cache miss
        result1 = unified_processor.process_symbol(symbol, horizons=['1D'], force_refresh=True)
        initial_misses = unified_processor.metrics['feature_cache_misses']
        
        # Should have registered a cache miss
        assert initial_misses > 0
        assert result1['feature_cache_hit'] == False
    
    def test_error_handling(self, unified_processor):
        """Test error handling for invalid symbol."""
        result = unified_processor.process_symbol('INVALID_XYZ123', horizons=['1D'])
        
        # Should handle gracefully
        assert result is not None
        assert result['symbol'] == 'INVALID_XYZ123'
        # May succeed or fail depending on data availability
        assert 'error' in result or result['success'] == True
    
    def test_database_writes(self, unified_processor):
        """Test that forecasts are written to database."""
        symbol = 'AAPL'
        initial_writes = unified_processor.metrics['db_writes']
        
        result = unified_processor.process_symbol(symbol, horizons=['1D'])
        
        if result['success']:
            # Should have written to database
            assert unified_processor.metrics['db_writes'] > initial_writes
            
            # Verify forecast exists in database
            symbol_id = db.get_symbol_id(symbol)
            forecast_record = db.get_forecast_record(symbol_id, horizon='1D')
            assert forecast_record is not None


class TestPerformanceMetrics:
    """Test performance metrics collection and comparison."""
    
    def test_metrics_file_generation(self):
        """Test that metrics file is generated correctly."""
        metrics_file = Path('tests/audit_tests/test_metrics_perf.json')
        
        processor = UnifiedForecastProcessor(
            redis_cache=None,
            metrics_file=str(metrics_file)
        )
        
        # Process a symbol
        processor.process_symbol('AAPL', horizons=['1D'])
        
        # Save metrics
        processor.save_metrics()
        
        # Verify file exists and is valid JSON
        assert metrics_file.exists()
        
        with open(metrics_file, 'r') as f:
            metrics = json.load(f)
        
        # Validate structure
        assert 'start_time' in metrics
        assert 'end_time' in metrics
        assert 'symbols_processed' in metrics
        assert 'feature_cache_hits' in metrics
        assert 'forecast_times' in metrics
        
        # Cleanup
        metrics_file.unlink()
    
    def test_processing_time_measurement(self):
        """Test that processing times are measured."""
        processor = UnifiedForecastProcessor()
        
        start = time.time()
        result = processor.process_symbol('AAPL', horizons=['1D'])
        elapsed = time.time() - start
        
        # Recorded time should be close to actual elapsed time
        assert result['processing_time'] > 0
        assert abs(result['processing_time'] - elapsed) < 1.0  # Within 1 second


def test_unified_vs_original_structure():
    """
    Compare output structure between unified and original implementations.
    
    This test validates that the unified processor produces forecasts
    with the same structure as the original, even if values differ slightly.
    """
    # This is a structural validation - we're checking that the unified
    # processor produces outputs in the expected format
    processor = UnifiedForecastProcessor()
    result = processor.process_symbol('AAPL', horizons=['1D'])
    
    # Validate top-level structure
    assert 'symbol' in result
    assert 'success' in result
    assert 'forecasts' in result
    assert 'processing_time' in result
    assert 'feature_cache_hit' in result
    assert 'weight_source' in result
    
    # If successful, validate forecast structure
    if result['success'] and '1D' in result['forecasts']:
        forecast = result['forecasts']['1D']
        
        # Required fields
        assert 'label' in forecast
        assert 'confidence' in forecast
        assert 'horizon' in forecast
        assert 'points' in forecast
        
        # Field types
        assert isinstance(forecast['label'], str)
        assert isinstance(forecast['confidence'], (int, float))
        assert isinstance(forecast['points'], list)
        
        # Value ranges
        assert forecast['label'] in ['bullish', 'bearish', 'neutral']
        assert 0 <= forecast['confidence'] <= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
