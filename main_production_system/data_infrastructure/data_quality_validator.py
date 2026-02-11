"""
Data Quality Validator & Backfill Engine (CORRECTED)
Ensures unified minimum dataset requirement (792 filtered rows) across timeframes.
Works backward from requirement to calculate required time spans.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from zoneinfo import ZoneInfo

import pandas as pd


logger = logging.getLogger(__name__)


class DataQualityValidator:
    """
    Validates data quality with UNIFIED minimum: 792 filtered market-hours rows.
    """

    # UNIFIED MINIMUM REQUIREMENT
    # 6.5 hours/day × 5 days/week × 4 weeks/month × 6 months = 792 rows at 1h timeframe
    MINIMUM_ROWS_REQUIRED: int = 792

    # Rows per trading day by timeframe (FILTERED - market hours only)
    ROWS_PER_DAY: Dict[str, float] = {
        "1min": 390.0,
        "5min": 78.0,
        "15min": 26.0,
        "30min": 13.0,
        "1h": 6.5,  # anchor
        "4h": 1.625,
        "1d": 1.0,
        "1wk": 0.2,
        "1mo": 0.044,
    }

    # Session multipliers (extended = more hours available)
    SESSION_MULTIPLIERS: Dict[str, float] = {
        "regular": 1.0,
        "extended": 2.46,
        "full": 2.46,
    }

    def __init__(self, market_calendar):
        self.calendar = market_calendar

    def calculate_required_trading_days(
        self,
        timeframe: str,
        session_type: str = "regular",
        minimum_rows: int = MINIMUM_ROWS_REQUIRED,
    ) -> int:
        rows_per_day = float(self.ROWS_PER_DAY.get(timeframe, 1.0))
        multiplier = float(self.SESSION_MULTIPLIERS.get(session_type, 1.0))
        effective_rows_per_day = max(rows_per_day * multiplier, 0.0001)
        trading_days_needed = int(-(-minimum_rows // int(effective_rows_per_day))) if effective_rows_per_day >= 1 else minimum_rows
        return max(trading_days_needed, 10)

    def validate_dataset(
        self,
        df: pd.DataFrame,
        timeframe: str,
        session_type: str,
        minimum_rows: int = MINIMUM_ROWS_REQUIRED,
        raise_error: bool = False,
    ) -> Dict:
        issues = []

        if df is None or len(df) == 0:
            issues.append("Dataset is empty")
            if raise_error:
                raise ValueError("Empty dataset")
            return {
                "is_valid": False,
                "rows_filtered": 0,
                "minimum_required": minimum_rows,
                "rows_needed": minimum_rows,
                "trading_days_current": 0,
                "trading_days_needed": self.calculate_required_trading_days(
                    timeframe, session_type, minimum_rows
                ),
                "data_range": "N/A",
                "issues": issues,
            }

        required_cols = ["time", "open", "high", "low", "close", "volume"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            issues.append(f"Missing columns: {missing_cols}")

        try:
            nan_count = int(df.isnull().sum().sum())
            if nan_count > 0:
                issues.append(f"Found {nan_count} NaN values")
        except Exception:
            pass

        current_rows = int(len(df))
        rows_per_day = float(self.ROWS_PER_DAY.get(timeframe, 1.0))
        multiplier = float(self.SESSION_MULTIPLIERS.get(session_type, 1.0))
        effective_rows_per_day = max(rows_per_day * multiplier, 0.0001)
        trading_days_current = current_rows / effective_rows_per_day
        trading_days_needed = self.calculate_required_trading_days(
            timeframe, session_type, minimum_rows
        )

        rows_needed = max(0, minimum_rows - current_rows)
        is_valid = current_rows >= minimum_rows and len(issues) == 0

        if not is_valid:
            logger.warning(
                f"[DATA_QA] Quality check failed: {timeframe}/{session_type} - {current_rows} rows (need {minimum_rows})"
            )

        if "time" in df.columns and len(df) > 0:
            start = df.iloc[0]["time"]
            end = df.iloc[-1]["time"]
            data_range = f"{start} to {end}"
        else:
            data_range = "Unknown"

        return {
            "is_valid": is_valid,
            "rows_filtered": current_rows,
            "minimum_required": minimum_rows,
            "rows_needed": rows_needed,
            "trading_days_current": int(trading_days_current),
            "trading_days_needed": trading_days_needed,
            "data_range": data_range,
            "issues": issues,
        }

    def calculate_backfill_start_date(
        self,
        timeframe: str,
        session_type: str = "regular",
        end_date: Optional[datetime] = None,
        minimum_rows: int = MINIMUM_ROWS_REQUIRED,
    ) -> datetime:
        if end_date is None:
            end_date = datetime.now(ZoneInfo("America/New_York"))

        trading_days_needed = self.calculate_required_trading_days(
            timeframe, session_type, minimum_rows
        )

        current = end_date.date()
        found = 0
        while found < trading_days_needed:
            if self.calendar.is_trading_day(current):
                found += 1
            current -= timedelta(days=1)

        start_date = datetime.combine(current, datetime.min.time()).replace(
            tzinfo=ZoneInfo("America/New_York")
        )

        logger.info(
            f"[DATA_QA] Calculated backfill: {timeframe}/{session_type} needs {trading_days_needed} trading days ({(end_date.date() - current).days} calendar days)"
        )

        return start_date

    def estimate_data_fetch_params(
        self,
        timeframe: str,
        session_type: str = "regular",
        minimum_rows: int = MINIMUM_ROWS_REQUIRED,
    ) -> Dict:
        trading_days = self.calculate_required_trading_days(
            timeframe, session_type, minimum_rows
        )
        start_date = self.calculate_backfill_start_date(
            timeframe, session_type, minimum_rows=minimum_rows
        )
        end_date = datetime.now(ZoneInfo("America/New_York"))
        rows_per_day = self.ROWS_PER_DAY.get(timeframe, 1.0)

        return {
            "timeframe": timeframe,
            "session_type": session_type,
            "minimum_rows_required": minimum_rows,
            "minimum_trading_days": trading_days,
            "rows_per_day": rows_per_day,
            "session_multiplier": self.SESSION_MULTIPLIERS.get(session_type, 1.0),
            "recommended_start_date": start_date.strftime("%Y-%m-%d"),
            "recommended_end_date": end_date.strftime("%Y-%m-%d"),
            "calendar_days_needed": (end_date.date() - start_date.date()).days,
            "months_approx": round((end_date.date() - start_date.date()).days / 30, 1),
        }


_validator_instance: Optional[DataQualityValidator] = None  # type: ignore[name-defined]


def get_data_quality_validator(market_calendar) -> DataQualityValidator:
    """Get or create global validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = DataQualityValidator(market_calendar)
    return _validator_instance


