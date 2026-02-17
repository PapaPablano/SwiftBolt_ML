"""
Backend API for Strategy Management
This serves as a simple API layer for managing trading strategies without full ML integration
"""

from flask import Flask, jsonify, request
import json
import os
from datetime import datetime
from typing import Dict, List, Any
import uuid

app = Flask(__name__)

# In-memory storage for strategies (in production, this would be a database)
strategies = {}
next_strategy_id = 1

# Load existing strategies if they exist
def load_strategies():
    global strategies, next_strategy_id
    try:
        if os.path.exists('strategies.json'):
            with open('strategies.json', 'r') as f:
                data = json.load(f)
                strategies = data.get('strategies', {})
                next_strategy_id = data.get('next_strategy_id', 1)
    except Exception as e:
        print(f"Error loading strategies: {e}")

# Save strategies to file
def save_strategies():
    try:
        data = {
            'strategies': strategies,
            'next_strategy_id': next_strategy_id
        }
        with open('strategies.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving strategies: {e}")

# Load strategies on startup
load_strategies()

@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    """Get all strategies"""
    return jsonify({
        'strategies': list(strategies.values()),
        'count': len(strategies)
    })

@app.route('/api/strategies/<strategy_id>', methods=['GET'])
def get_strategy(strategy_id):
    """Get a specific strategy"""
    strategy = strategies.get(strategy_id)
    if not strategy:
        return jsonify({'error': 'Strategy not found'}), 404
    return jsonify(strategy)

@app.route('/api/strategies', methods=['POST'])
def create_strategy():
    """Create a new strategy"""
    global next_strategy_id
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'description', 'parameters', 'indicators']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Create strategy object
    strategy = {
        'id': str(next_strategy_id),
        'name': data['name'],
        'description': data['description'],
        'parameters': data['parameters'],
        'indicators': data['indicators'],
        'signal_filter': data.get('signal_filter', 'both'),
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
        'is_active': data.get('is_active', True)
    }
    
    strategies[strategy['id']] = strategy
    next_strategy_id += 1
    
    save_strategies()
    
    return jsonify(strategy), 201

@app.route('/api/strategies/<strategy_id>', methods=['PUT'])
def update_strategy(strategy_id):
    """Update an existing strategy"""
    strategy = strategies.get(strategy_id)
    if not strategy:
        return jsonify({'error': 'Strategy not found'}), 404
    
    data = request.get_json()
    
    # Update fields
    for key, value in data.items():
        if key != 'id':  # Don't allow updating ID
            strategy[key] = value
    
    strategy['updated_at'] = datetime.utcnow().isoformat()
    
    save_strategies()
    
    return jsonify(strategy)

@app.route('/api/strategies/<strategy_id>', methods=['DELETE'])
def delete_strategy(strategy_id):
    """Delete a strategy"""
    if strategy_id in strategies:
        del strategies[strategy_id]
        save_strategies()
        return jsonify({'message': 'Strategy deleted'})
    return jsonify({'error': 'Strategy not found'}), 404

@app.route('/api/strategies/<strategy_id>/backtest', methods=['POST'])
def backtest_strategy(strategy_id):
    """Run a backtest for a specific strategy"""
    strategy = strategies.get(strategy_id)
    if not strategy:
        return jsonify({'error': 'Strategy not found'}), 404
    
    # Load the backtester
    import importlib.util
    spec = importlib.util.spec_from_file_location("strategy_backtester", "/Users/ericpeterson/SwiftBolt_ML/strategy_backtester.py")
    strategy_backtester = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(strategy_backtester)
    
    # Generate mock data (in production this would use real data)
    from datetime import datetime, timedelta
    import pandas as pd
    
    # Simulate backtest with sample data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    # Create mock data
    mock_data = strategy_backtester.MockDataGenerator.generate_mock_data(
        "TEST", start_date, end_date, volatility=0.015, trend=0.0005
    )
    
    backtester = strategy_backtester.StrategyBacktester(mock_data)
    
    # Simple example - using first indicator to generate signal
    def simple_signal_function(df):
        if len(df['close']) < 10:
            return False
        
        # Sample signal based on first indicator
        if strategy['indicators']:
            indicator = strategy['indicators'][0]
            if indicator == 'sma_cross':
                sma_5 = df['close'].tail(5).mean()
                sma_20 = df['close'].tail(20).mean()
                return sma_5 > sma_20
        
        return False
    
    try:
        # Run the backtest with a basic buy signal
        result = backtester.run_simple_strategy(
            buy_signal_func=simple_signal_function,
            sell_signal_func=lambda df: False,  # Simplified
            initial_capital=10000.0,
            position_size=100
        )
        
        return jsonify({
            'strategy_id': strategy_id,
            'strategy_name': strategy['name'],
            'backtest_result': {
                'total_trades': result.total_trades,
                'winning_trades': result.winning_trades,
                'losing_trades': result.losing_trades,
                'total_profit': result.total_profit,
                'total_return': result.total_return,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'performance_metrics': result.performance_metrics
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'strategy-api'
    })

@app.route('/api/strategies/test', methods=['POST'])
def test_strategy():
    """Test a strategy with sample parameters"""
    data = request.get_json()
    
    # Validate test data
    if not data or 'strategy_config' not in data:
        return jsonify({'error': 'Missing strategy configuration'}), 400
    
    config = data['strategy_config']
    
    # Return the configuration as-is for now
    return jsonify({
        'status': 'success',
        'configuration': config,
        'message': 'Strategy configuration validated'
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)