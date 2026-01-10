"""Database access layer for SwiftBolt ML pipeline."""

import logging
from contextlib import contextmanager
from typing import Any, Generator

import pandas as pd
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from config.settings import settings

logger = logging.getLogger(__name__)


class Database:
    """Database connection pool manager."""

    def __init__(self) -> None:
        """Initialize database connection pool."""
        self.pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.database_url,
        )
        logger.info("Database connection pool initialized")

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Get a database connection from the pool."""
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

    def fetch_ohlc_bars(
        self,
        symbol: str,
        timeframe: str = "d1",
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLC bars for a symbol from the database.

        Args:
            symbol: Stock ticker symbol
            timeframe: Timeframe (d1, h1, etc.)
            limit: Maximum number of bars to fetch (most recent)

        Returns:
            DataFrame with columns: ts, open, high, low, close, volume
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get symbol_id
                cur.execute(
                    "SELECT id FROM symbols WHERE ticker = %s",
                    (symbol.upper(),),
                )
                result = cur.fetchone()
                if not result:
                    raise ValueError(f"Symbol {symbol} not found in database")

                symbol_id = result["id"]

                # Fetch OHLC bars from v2 table (real Alpaca data only)
                query = """
                    SELECT ts, open, high, low, close, volume
                    FROM ohlc_bars_v2
                    WHERE symbol_id = %s 
                      AND timeframe = %s
                      AND provider = 'alpaca'
                      AND is_forecast = false
                    ORDER BY ts DESC
                """
                params = [symbol_id, timeframe]

                if limit:
                    query += " LIMIT %s"
                    params.append(limit)

                cur.execute(query, params)
                rows = cur.fetchall()

                if not rows:
                    logger.warning(f"No OHLC data found for {symbol} ({timeframe})")
                    return pd.DataFrame(
                        columns=["ts", "open", "high", "low", "close", "volume"]
                    )

                # Convert to DataFrame
                df = pd.DataFrame(rows)
                df["ts"] = pd.to_datetime(df["ts"])
                df = df.sort_values("ts")  # Sort ascending for time series
                df = df.reset_index(drop=True)

                logger.info(f"Fetched {len(df)} bars for {symbol} ({timeframe})")
                return df

    def get_symbol_id(self, symbol: str) -> str:
        """Get the UUID symbol_id for a ticker symbol."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id FROM symbols WHERE ticker = %s",
                    (symbol.upper(),),
                )
                result = cur.fetchone()
                if not result:
                    raise ValueError(f"Symbol {symbol} not found")
                return result["id"]

    def upsert_forecast(
        self,
        symbol_id: str,
        horizon: str,
        overall_label: str,
        confidence: float,
        points: list[dict[str, Any]],
    ) -> None:
        """
        Insert or update an ML forecast in the database.

        Args:
            symbol_id: UUID of the symbol
            horizon: Forecast horizon (e.g., "1D", "1W")
            overall_label: Bullish/Neutral/Bearish
            confidence: Confidence score (0-1)
            points: List of forecast points with ts, value, lower, upper
        """
        import json

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Upsert forecast
                cur.execute(
                    """
                    INSERT INTO ml_forecasts (
                        symbol_id, horizon, overall_label, confidence, points, run_at
                    )
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (symbol_id, horizon)
                    DO UPDATE SET
                        overall_label = EXCLUDED.overall_label,
                        confidence = EXCLUDED.confidence,
                        points = EXCLUDED.points,
                        run_at = EXCLUDED.run_at
                    """,
                    (symbol_id, horizon, overall_label, confidence, json.dumps(points)),
                )
                conn.commit()
                logger.info(
                    f"Upserted forecast for symbol_id={symbol_id}, "
                    f"horizon={horizon}, label={overall_label}"
                )

    def close(self) -> None:
        """Close all database connections."""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed")


# Singleton database instance
db = Database()
