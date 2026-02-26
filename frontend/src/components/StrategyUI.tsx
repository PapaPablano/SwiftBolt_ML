import React, { useState, useEffect } from 'react';
import { StrategyConditionBuilder, Condition } from './StrategyConditionBuilder';

// Type definitions for our strategy components
interface StrategyParameter {
  name: string;
  type: 'number' | 'string' | 'boolean';
  value: any;
  description: string;
}

interface StrategyIndicator {
  name: string;
  description: string;
  enabled: boolean;
}

interface StrategyConditions {
  entry: Condition[];
  exit: Condition[];
  stoploss?: Condition[];
  takeprofit?: Condition[];
}

interface Strategy {
  id: string;
  name: string;
  description: string;
  parameters: StrategyParameter[];
  indicators: StrategyIndicator[];
  conditions?: StrategyConditions;
  signalFilter: 'buy' | 'sell' | 'both';
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

// Available indicators for condition builder
const AVAILABLE_INDICATORS = [
  'RSI', 'MACD', 'Stochastic', 'Bollinger Bands', 'ATR',
  'ADX', 'SuperTrend', 'Volume', 'Close', 'Open', 'High', 'Low'
];

// Mock data for demonstration
const mockStrategies: Strategy[] = [
  {
    id: '1',
    name: 'SuperTrend Strategy',
    description: 'A trend-following strategy using SuperTrend indicator',
    parameters: [
      { name: 'length', type: 'number', value: 10, description: 'Indicator length' },
      { name: 'multiplier', type: 'number', value: 3.0, description: 'Multiplier for SuperTrend' }
    ],
    indicators: [
      { name: 'SuperTrend', description: 'SuperTrend indicator', enabled: true },
      { name: 'RSI', description: 'Relative Strength Index', enabled: true },
      { name: 'MACD', description: 'Moving Average Convergence Divergence', enabled: false }
    ],
    conditions: {
      entry: [],
      exit: []
    },
    signalFilter: 'both',
    isActive: true,
    createdAt: '2023-01-01T00:00:00Z',
    updatedAt: '2023-01-01T00:00:00Z'
  },
  {
    id: '2',
    name: 'RSI Oversold Strategy',
    description: 'A mean-reversion strategy using RSI below 30',
    parameters: [
      { name: 'rsiLength', type: 'number', value: 14, description: 'RSI calculation period' },
      { name: 'overboughtLevel', type: 'number', value: 70, description: 'RSI overbought level' },
      { name: 'oversoldLevel', type: 'number', value: 30, description: 'RSI oversold level' }
    ],
    indicators: [
      { name: 'RSI', description: 'Relative Strength Index', enabled: true },
      { name: 'BBands', description: 'Bollinger Bands', enabled: true }
    ],
    conditions: {
      entry: [],
      exit: []
    },
    signalFilter: 'buy',
    isActive: true,
    createdAt: '2023-01-01T00:00:00Z',
    updatedAt: '2023-01-01T00:00:00Z'
  }
];

const StrategyUI: React.FC = () => {
  const [strategies, setStrategies] = useState<Strategy[]>(mockStrategies);
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(mockStrategies[0]);
  const [isEditing, setIsEditing] = useState(false);
  const [newStrategy, setNewStrategy] = useState<Omit<Strategy, 'id' | 'createdAt' | 'updatedAt'>>({
    name: '',
    description: '',
    parameters: [],
    indicators: [],
    conditions: {
      entry: [],
      exit: []
    },
    signalFilter: 'both',
    isActive: true
  });
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [isTesting, setIsTesting] = useState(false);

  // Initialize from mock data
  useEffect(() => {
    setSelectedStrategy(strategies[0]);
  }, []);

  const handleCreateStrategy = () => {
    const strategy: Strategy = {
      ...newStrategy,
      id: `strategy-${Date.now()}`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    
    setStrategies([...strategies, strategy]);
    setNewStrategy({
      name: '',
      description: '',
      parameters: [],
      indicators: [],
      signalFilter: 'both',
      isActive: true
    });
  };

  const handleUpdateStrategy = () => {
    if (!selectedStrategy) return;
    
    const updatedStrategies = strategies.map(s => 
      s.id === selectedStrategy.id ? { ...selectedStrategy, updatedAt: new Date().toISOString() } : s
    );
    
    setStrategies(updatedStrategies);
    setIsEditing(false);
  };

  const handleBacktest = async () => {
    if (!selectedStrategy) return;
    
    setIsTesting(true);
    
    try {
      // Simulate API call to backtest endpoint
      // In real implementation, this would call the backend API
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Mock backtest results
      const results = {
        totalTrades: Math.floor(Math.random() * 50) + 10,
        winningTrades: Math.floor(Math.random() * 30) + 5,
        losingTrades: Math.floor(Math.random() * 20) + 2,
        totalProfit: (Math.random() * 10000 - 5000).toFixed(2),
        totalReturn: (Math.random() * 50 - 25).toFixed(2),
        maxDrawdown: (Math.random() * 15).toFixed(2),
        sharpeRatio: (Math.random() * 3 + 1).toFixed(2),
        performanceMetrics: {
          winRate: Math.random().toFixed(2),
          avgProfit: (Math.random() * 2000 - 1000).toFixed(2),
          avgWin: (Math.random() * 500).toFixed(2),
          avgLoss: (Math.random() * 300).toFixed(2)
        }
      };
      
      setBacktestResults(results);
    } catch (error) {
      console.error('Backtest failed:', error);
    } finally {
      setIsTesting(false);
    }
  };

  const renderParameterEditor = (param: StrategyParameter, index: number) => (
    <div key={index} className="mb-3">
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {param.name}
      </label>
      <input
        type={param.type === 'number' ? 'number' : param.type === 'boolean' ? 'checkbox' : 'text'}
        value={param.value.toString()}
        onChange={(e) => {
          if (selectedStrategy) {
            const updatedParams = [...selectedStrategy.parameters];
            updatedParams[index].value = param.type === 'number' ? parseFloat(e.target.value) : 
                                      param.type === 'boolean' ? e.target.checked : e.target.value;
            setSelectedStrategy({ ...selectedStrategy, parameters: updatedParams });
          }
        }}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <p className="text-xs text-gray-500 mt-1">{param.description}</p>
    </div>
  );

  const renderIndicatorSelector = (indicator: StrategyIndicator, index: number) => (
    <div key={index} className="flex items-center mb-2">
      <input
        type="checkbox"
        checked={indicator.enabled}
        onChange={(e) => {
          if (selectedStrategy) {
            const updatedIndicators = [...selectedStrategy.indicators];
            updatedIndicators[index].enabled = e.target.checked;
            setSelectedStrategy({ ...selectedStrategy, indicators: updatedIndicators });
          }
        }}
        className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
      />
      <span className="text-sm font-medium text-gray-700">{indicator.name}</span>
      <span className="ml-2 text-xs text-gray-500">{indicator.description}</span>
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Strategy Management</h1>
        <p className="text-gray-600">Create, manage, and backtest trading strategies</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Strategy List */}
        <div className="lg:col-span-1">
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="p-4 border-b border-gray-200">
              <div className="flex justify-between items-center">
                <h2 className="text-lg font-semibold text-gray-900">Strategies</h2>
                <button 
                  onClick={() => setIsEditing(true)}
                  className="ml-2 px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                >
                  New
                </button>
              </div>
            </div>
            <div className="divide-y divide-gray-200">
              {strategies.map((strategy) => (
                <div 
                  key={strategy.id}
                  className={`p-4 cursor-pointer hover:bg-gray-50 ${selectedStrategy?.id === strategy.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''}`}
                  onClick={() => {
                    setSelectedStrategy(strategy);
                    setBacktestResults(null);
                  }}
                >
                  <div className="flex justify-between items-start">
                    <h3 className="font-medium text-gray-900">{strategy.name}</h3>
                    <span className={`px-2 py-1 text-xs rounded-full ${strategy.isActive ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                      {strategy.isActive ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">{strategy.description}</p>
                  <div className="mt-2 flex space-x-2">
                    <span className="text-xs text-gray-400">{strategy.parameters.length} params</span>
                    <span className="text-xs text-gray-400">{strategy.indicators.filter(i => i.enabled).length} indicators</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Strategy Details */}
        <div className="lg:col-span-2">
          {selectedStrategy ? (
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="p-6">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">{selectedStrategy.name}</h2>
                    <p className="text-gray-600 mt-1">{selectedStrategy.description}</p>
                  </div>
                  <div className="flex space-x-2">
                    <button 
                      onClick={handleBacktest}
                      disabled={isTesting}
                      className={`px-4 py-2 rounded-md text-sm font-medium ${
                        isTesting 
                          ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                          : 'bg-green-600 text-white hover:bg-green-700'
                      }`}
                    >
                      {isTesting ? 'Testing...' : 'Backtest'}
                    </button>
                    <button 
                      onClick={() => setSelectedStrategy(null)}
                      className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-50"
                    >
                      Close
                    </button>
                  </div>
                </div>

                {backtestResults ? (
                  <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                    <h3 className="font-medium text-gray-900 mb-3">Backtest Results</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="bg-white p-3 rounded shadow">
                        <p className="text-sm text-gray-500">Total Trades</p>
                        <p className="text-lg font-semibold">{backtestResults.totalTrades}</p>
                      </div>
                      <div className="bg-white p-3 rounded shadow">
                        <p className="text-sm text-gray-500">Win Rate</p>
                        <p className="text-lg font-semibold">{backtestResults.performanceMetrics.winRate * 100}%</p>
                      </div>
                      <div className="bg-white p-3 rounded shadow">
                        <p className="text-sm text-gray-500">Profit/Loss</p>
                        <p className="text-lg font-semibold">${backtestResults.totalProfit}</p>
                      </div>
                      <div className="bg-white p-3 rounded shadow">
                        <p className="text-sm text-gray-500">Return</p>
                        <p className="text-lg font-semibold">{backtestResults.totalReturn}%</p>
                      </div>
                    </div>
                  </div>
                ) : null}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                  <div>
                    <h3 className="font-medium text-gray-900 mb-3">Parameters</h3>
                    {selectedStrategy.parameters.map((param, index) => (
                      renderParameterEditor(param, index)
                    ))}

                    <h3 className="font-medium text-gray-900 mt-6 mb-3">Indicators</h3>
                    {selectedStrategy.indicators.map((indicator, index) => (
                      renderIndicatorSelector(indicator, index)
                    ))}
                  </div>

                  <div>
                    <h3 className="font-medium text-gray-900 mb-3">Strategy Details</h3>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700">Signal Filter</label>
                        <select
                          value={selectedStrategy.signalFilter}
                          onChange={(e) => setSelectedStrategy({...selectedStrategy, signalFilter: e.target.value as any})}
                          className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
                        >
                          <option value="buy">Buy Only</option>
                          <option value="sell">Sell Only</option>
                          <option value="both">Both</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700">Status</label>
                        <div className="mt-1">
                          <button
                            type="button"
                            className={`inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white ${
                              selectedStrategy.isActive 
                                ? 'bg-green-600 hover:bg-green-700' 
                                : 'bg-red-600 hover:bg-red-700'
                            }`}
                            onClick={() => setSelectedStrategy({...selectedStrategy, isActive: !selectedStrategy.isActive})}
                          >
                            {selectedStrategy.isActive ? 'Active' : 'Inactive'}
                          </button>
                        </div>
                      </div>

                      <div className="pt-4 border-t border-gray-200">
                        <h4 className="font-medium text-gray-900 mb-2">Timeline</h4>
                        <div className="text-sm text-gray-500">
                          <p>Created: {new Date(selectedStrategy.createdAt).toLocaleDateString()}</p>
                          <p>Updated: {new Date(selectedStrategy.updatedAt).toLocaleDateString()}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Condition Builders */}
                {selectedStrategy.conditions && (
                  <div className="space-y-4 mb-6">
                    <div className="border-t border-gray-200 pt-6">
                      <h3 className="font-medium text-gray-900 mb-4">Strategy Conditions</h3>
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <StrategyConditionBuilder
                          signalType="entry"
                          initialConditions={selectedStrategy.conditions.entry}
                          onConditionsChange={(conditions) => {
                            setSelectedStrategy({
                              ...selectedStrategy,
                              conditions: {
                                ...selectedStrategy.conditions!,
                                entry: conditions
                              }
                            });
                          }}
                          availableIndicators={AVAILABLE_INDICATORS}
                        />
                        <StrategyConditionBuilder
                          signalType="exit"
                          initialConditions={selectedStrategy.conditions.exit}
                          onConditionsChange={(conditions) => {
                            setSelectedStrategy({
                              ...selectedStrategy,
                              conditions: {
                                ...selectedStrategy.conditions!,
                                exit: conditions
                              }
                            });
                          }}
                          availableIndicators={AVAILABLE_INDICATORS}
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div className="mt-6 flex justify-end space-x-3">
                  <button
                    onClick={() => {
                      setSelectedStrategy(null);
                      setBacktestResults(null);
                    }}
                    className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleUpdateStrategy}
                    className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
                  >
                    Save Changes
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="p-6 text-center">
                <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Strategy</h3>
                <p className="text-gray-500">Choose a strategy from the list to view and edit details</p>
              </div>
            </div>
          )}

          {/* New Strategy Form */}
          {isEditing && (
            <div className="mt-6 bg-white shadow rounded-lg overflow-hidden">
              <div className="p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Create New Strategy</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Strategy Name</label>
                    <input
                      type="text"
                      value={newStrategy.name}
                      onChange={(e) => setNewStrategy({...newStrategy, name: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="Enter strategy name"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Signal Filter</label>
                    <select
                      value={newStrategy.signalFilter}
                      onChange={(e) => setNewStrategy({...newStrategy, signalFilter: e.target.value as any})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="buy">Buy Only</option>
                      <option value="sell">Sell Only</option>
                      <option value="both">Both</option>
                    </select>
                  </div>
                </div>

                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                  <textarea
                    value={newStrategy.description}
                    onChange={(e) => setNewStrategy({...newStrategy, description: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={3}
                    placeholder="Describe your strategy"
                  />
                </div>

                <div className="mt-6 flex justify-end space-x-3">
                  <button
                    onClick={() => setIsEditing(false)}
                    className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateStrategy}
                    className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
                  >
                    Create Strategy
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StrategyUI;