-- ============================================================================
-- MARKET CALENDAR TABLE (for fast DB-level filtering)
-- ============================================================================

CREATE TABLE IF NOT EXISTS market_calendar (
    date DATE PRIMARY KEY,
    is_trading_day BOOLEAN NOT NULL,
    market_open TIME NOT NULL,      -- 09:30 ET
    market_close TIME NOT NULL,     -- 16:00 ET
    is_early_close BOOLEAN DEFAULT FALSE,
    early_close_time TIME,
    holiday_name TEXT,
    notes TEXT
);

-- Populate market calendar for 2024-2030
INSERT INTO market_calendar (date, is_trading_day, market_open, market_close, holiday_name)
SELECT
    d,
    EXTRACT(DOW FROM d) NOT IN (0, 6) AND
    NOT d IN (
        '2024-01-01'::date,  -- New Year
        '2024-01-15'::date,  -- MLK Day
        '2024-02-19'::date,  -- Presidents Day
        '2024-03-29'::date,  -- Good Friday
        '2024-05-27'::date,  -- Memorial Day
        '2024-06-19'::date,  -- Juneteenth
        '2024-07-04'::date,  -- Independence Day
        '2024-09-02'::date,  -- Labor Day
        '2024-11-28'::date,  -- Thanksgiving
        '2024-12-25'::date,  -- Christmas
        -- 2025 holidays
        '2025-01-01'::date,
        '2025-01-20'::date,
        '2025-02-17'::date,
        '2025-04-18'::date,
        '2025-05-26'::date,
        '2025-06-19'::date,
        '2025-07-04'::date,
        '2025-09-01'::date,
        '2025-11-27'::date,
        '2025-12-25'::date,
        -- 2026 holidays
        '2026-01-01'::date,
        '2026-01-19'::date,
        '2026-02-16'::date,
        '2026-04-03'::date,
        '2026-05-25'::date,
        '2026-06-19'::date,
        '2026-07-03'::date,
        '2026-09-07'::date,
        '2026-11-26'::date,
        '2026-12-25'::date,
        -- 2027 holidays
        '2027-01-01'::date,
        '2027-01-18'::date,
        '2027-02-15'::date,
        '2027-03-26'::date,
        '2027-05-31'::date,
        '2027-06-18'::date,
        '2027-07-05'::date,
        '2027-09-06'::date,
        '2027-11-25'::date,
        '2027-12-24'::date,
        -- 2028 holidays
        '2028-01-17'::date,
        '2028-02-21'::date,
        '2028-04-14'::date,
        '2028-05-29'::date,
        '2028-06-19'::date,
        '2028-07-04'::date,
        '2028-09-04'::date,
        '2028-11-23'::date,
        '2028-12-25'::date,
        -- 2029 holidays
        '2029-01-01'::date,
        '2029-01-15'::date,
        '2029-02-19'::date,
        '2029-03-30'::date,
        '2029-05-28'::date,
        '2029-06-19'::date,
        '2029-07-04'::date,
        '2029-09-03'::date,
        '2029-11-22'::date,
        '2029-12-25'::date,
        -- 2030 holidays
        '2030-01-01'::date,
        '2030-01-21'::date,
        '2030-02-18'::date,
        '2030-04-19'::date,
        '2030-05-27'::date,
        '2030-06-19'::date,
        '2030-07-04'::date,
        '2030-09-02'::date,
        '2030-11-28'::date,
        '2030-12-25'::date
    ) as is_trading_day,
    '09:30'::time,
    '16:00'::time,
    NULL
FROM generate_series('2024-01-01'::date, '2030-12-31'::date, INTERVAL '1 day') d
ON CONFLICT (date) DO NOTHING;

-- Mark early closes
UPDATE market_calendar SET
    is_early_close = TRUE,
    early_close_time = '13:00'::time
WHERE
    -- Day after Thanksgiving
    (EXTRACT(MONTH FROM date) = 11 AND EXTRACT(DOW FROM date) = 5 
     AND EXTRACT(DAY FROM date) BETWEEN 23 AND 29) OR
    -- Christmas Eve
    (EXTRACT(MONTH FROM date) = 12 AND EXTRACT(DAY FROM date) = 24) OR
    -- July 3 (if July 4 is weekday)
    (EXTRACT(MONTH FROM date) = 7 AND EXTRACT(DAY FROM date) = 3 
     AND EXTRACT(DOW FROM '2024-07-04'::date) != 6);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_market_calendar_date_trading ON market_calendar (date, is_trading_day);
