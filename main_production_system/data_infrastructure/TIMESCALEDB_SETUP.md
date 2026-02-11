# TimescaleDB Setup Guide

This guide explains how to set up TimescaleDB for the market calendar and trading hours filtering system.

## Prerequisites

1. **TimescaleDB installed** - See [TimescaleDB Installation Guide](https://docs.timescale.com/getting-started/latest/)
2. **Python packages installed**:
   ```bash
   pip install psycopg2-binary pandas_market_calendars holidays
   ```

## Step 1: Configure Database Connection

Set the following environment variables:

### Option A: Environment Variables (Recommended for Production)

```bash
export TIMESCALEDB_HOST=localhost
export TIMESCALEDB_PORT=5432
export TIMESCALEDB_DATABASE=timescale
export TIMESCALEDB_USER=postgres
export TIMESCALEDB_PASSWORD=your_password_here
```

### Option B: .env File (Development)

1. Copy `.env.example` to `.env`:
   ```bash
   cp main_production_system/data_infrastructure/.env.example main_production_system/data_infrastructure/.env
   ```

2. Edit `.env` with your database credentials

3. Load in Python:
   ```python
   from dotenv import load_dotenv
   load_dotenv('main_production_system/data_infrastructure/.env')
   ```

### Option C: Streamlit Secrets (For Dashboard)

Add to `.streamlit/secrets.toml`:

```toml
[TIMESCALEDB]
HOST = "localhost"
PORT = 5432
DATABASE = "timescale"
USER = "postgres"
PASSWORD = "your_password_here"
```

## Step 2: Create Database (if needed)

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database
CREATE DATABASE timescale;

-- Connect to new database
\c timescale

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

## Step 3: Run Schema Setup

### Automatic (Recommended)

```bash
python3 scripts/setup_timescaledb_schema.py
```

### Manual

1. Connect to your TimescaleDB instance:
   ```bash
   psql -U postgres -d timescale
   ```

2. Execute the schema file:
   ```sql
   \i main_production_system/data_infrastructure/timescale_schema.sql
   ```

   Or copy-paste the contents of `timescale_schema.sql` into psql.

## Step 4: Verify Setup

Check that the market_calendar table was created:

```sql
SELECT COUNT(*) FROM market_calendar WHERE is_trading_day = TRUE;
-- Should return ~1500+ trading days (2024-2030)
```

## Step 5: Test Connection

Run the market hours test (doesn't require TimescaleDB):

```bash
python3 scripts/test_market_hours.py
```

## Troubleshooting

### Connection Errors

- **"Connection refused"**: Check if PostgreSQL/TimescaleDB is running
  ```bash
  # macOS
  brew services list | grep postgresql
  
  # Linux
  sudo systemctl status postgresql
  ```

- **"Authentication failed"**: Verify username and password
- **"Database does not exist"**: Create the database first (Step 2)

### Schema Errors

- **"relation already exists"**: Table already created (safe to ignore)
- **"permission denied"**: Ensure user has CREATE TABLE privileges

### Python Import Errors

- **"No module named 'psycopg2'"**: Install with `pip install psycopg2-binary`
- **"No module named 'pandas_market_calendars'"**: Install with `pip install pandas_market_calendars`

## Next Steps

After setup is complete:

1. The market calendar will automatically filter trading hours data
2. The trading page will display market status
3. All data fetches will exclude weekends/holidays by default

## Notes

- The market_calendar table is updated annually (currently covers 2024-2030)
- Database connection is cached for performance
- Market hours filtering happens at the Python level (fast, <10ms overhead)
- Future optimization: Move filtering to database level using market_calendar table
