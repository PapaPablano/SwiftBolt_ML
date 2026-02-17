-- TradeStation Strategy System Database Schema
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Strategies table
CREATE TABLE IF NOT EXISTS ts_strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Indicators table (predefined technical indicators)
CREATE TABLE IF NOT EXISTS ts_indicators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    parameters JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Strategy Conditions (rules that trigger actions)
CREATE TABLE IF NOT EXISTS ts_strategy_conditions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID REFERENCES ts_strategies(id) ON DELETE CASCADE,
    indicator_id UUID REFERENCES ts_indicators(id),
    threshold DOUBLE PRECISION NOT NULL,
    operator TEXT CHECK (operator IN ('>', '<', '>=', '<=', '=', 'CROSS_ABOVE', 'CROSS_BELOW')),
    logical_operator TEXT CHECK (logical_operator IN ('AND', 'OR')) DEFAULT 'AND',
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Trading Actions (what to do when conditions are met)
CREATE TABLE IF NOT EXISTS ts_trading_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID REFERENCES ts_strategies(id) ON DELETE CASCADE,
    action_type TEXT CHECK (action_type IN ('BUY', 'SELL', 'STOP_LOSS', 'TAKE_PROFIT', 'CLOSE_POSITION')),
    parameters JSONB DEFAULT '{}'::jsonb,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. TradeStation Credentials (encrypted storage)
CREATE TABLE IF NOT EXISTS ts_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Execution Log (track trades)
CREATE TABLE IF NOT EXISTS ts_execution_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID REFERENCES ts_strategies(id),
    action_id UUID REFERENCES ts_trading_actions(id),
    symbol TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT CHECK (status IN ('PENDING', 'FILLED', 'REJECTED', 'CANCELLED')),
    quantity INTEGER,
    price DOUBLE PRECISION,
    filled_at TIMESTAMP WITH TIME ZONE,
    raw_response JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ts_strategies_user ON ts_strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_ts_conditions_strategy ON ts_strategy_conditions(strategy_id);
CREATE INDEX IF NOT EXISTS idx_ts_actions_strategy ON ts_trading_actions(strategy_id);
CREATE INDEX IF NOT EXISTS idx_ts_credentials_user ON ts_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_ts_execution_log_strategy ON ts_execution_log(strategy_id);

-- Insert default indicators
INSERT INTO ts_indicators (name, description, parameters) VALUES
    ('RSI', 'Relative Strength Index', '{"period": 14, "overbought": 70, "oversold": 30}'),
    ('MACD', 'Moving Average Convergence Divergence', '{"fast_period": 12, "slow_period": 26, "signal_period": 9}'),
    ('SMA', 'Simple Moving Average', '{"period": 20}'),
    ('EMA', 'Exponential Moving Average', '{"period": 20}'),
    ('BB', 'Bollinger Bands', '{"period": 20, "std_dev": 2}'),
    ('ATR', 'Average True Range', '{"period": 14}'),
    ('STOCH', 'Stochastic Oscillator', '{"k_period": 14, "d_period": 3}'),
    ('VWAP', 'Volume Weighted Average Price', '{}')
ON CONFLICT (name) DO NOTHING;

-- Enable RLS
ALTER TABLE ts_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE ts_indicators ENABLE ROW LEVEL SECURITY;
ALTER TABLE ts_strategy_conditions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ts_trading_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ts_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE ts_execution_log ENABLE ROW LEVEL SECURITY;

-- RLS Policies for strategies (users can only see their own)
CREATE POLICY "Users can manage own strategies" ON ts_strategies
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own conditions" ON ts_strategy_conditions
    FOR ALL USING (
        EXISTS (SELECT 1 FROM ts_strategies WHERE id = strategy_id AND user_id = auth.uid())
    );

CREATE POLICY "Users can manage own actions" ON ts_trading_actions
    FOR ALL USING (
        EXISTS (SELECT 1 FROM ts_strategies WHERE id = strategy_id AND user_id = auth.uid())
    );

CREATE POLICY "Users can manage own credentials" ON ts_credentials
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own execution logs" ON ts_execution_log
    FOR ALL USING (
        EXISTS (SELECT 1 FROM ts_strategies WHERE id = strategy_id AND user_id = auth.uid())
    );

-- Indicators are read-only for all authenticated users
CREATE POLICY "Anyone can read indicators" ON ts_indicators
    FOR SELECT USING (true);
