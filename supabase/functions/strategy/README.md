# Strategy Management Function

This Supabase function provides a REST API for managing trading strategies in the SwiftBolt_ML project.

## Endpoints

### GET /strategy
Fetch all strategies

### POST /strategy
Create a new strategy

### PUT /strategy
Update an existing strategy

### DELETE /strategy
Delete a strategy

## Data Model

### Strategy Fields
- `id`: Unique identifier
- `name`: Strategy name
- `description`: Description of the strategy
- `parameters`: JSON object containing strategy parameters
- `type`: Type of strategy (e.g., "backtest", "live")
- `created_at`: Timestamp when created
- `updated_at`: Timestamp when updated

## Usage Examples

### Create Strategy
```bash
curl -X POST https://your-supabase-url.supabase.co/functions/v1/strategy \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mean Reversion",
    "description": "Mean reversion strategy for stock pairs",
    "parameters": {
      "lookback_period": 20,
      "z_score_threshold": 2.0
    },
    "type": "backtest"
  }'
```

### Get Strategies
```bash
curl https://your-supabase-url.supabase.co/functions/v1/strategy
```