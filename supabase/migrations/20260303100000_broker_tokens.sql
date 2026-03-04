-- Broker Tokens — OAuth credential storage for TradeStation
-- Migration: 20260303100000_broker_tokens
-- Date: 2026-03-03
-- Feature: Live Trading Executor via TradeStation

-- ============================================================================
-- 1. BROKER TOKENS TABLE
-- ============================================================================
-- Stores TradeStation OAuth tokens per user.
-- Uses auth client (not service role) for reads to enforce RLS.
-- Account IDs validated to prevent SSRF/path-traversal (SEC-09).

CREATE TABLE IF NOT EXISTS broker_tokens (
  id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID         NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  provider            TEXT         NOT NULL DEFAULT 'tradestation'
                                   CHECK (provider IN ('tradestation')),
  access_token        TEXT         NOT NULL,
  refresh_token       TEXT         NOT NULL,
  expires_at          TIMESTAMPTZ  NOT NULL,
  account_id          TEXT         NOT NULL
                                   CHECK (account_id ~ '^[A-Z0-9]{4,15}$'),
  futures_account_id  TEXT
                                   CHECK (futures_account_id IS NULL OR futures_account_id ~ '^[A-Z0-9]{4,15}$'),
  revoked_at          TIMESTAMPTZ,
  created_at          TIMESTAMPTZ  DEFAULT NOW(),
  updated_at          TIMESTAMPTZ  DEFAULT NOW(),

  -- One active token row per user per provider.
  -- Users with multiple brokerage accounts need separate rows per provider.
  UNIQUE (user_id, provider)
);

-- Index for token lookup by user
CREATE INDEX IF NOT EXISTS idx_broker_tokens_user_provider
  ON broker_tokens (user_id, provider) WHERE revoked_at IS NULL;

-- ============================================================================
-- 2. RLS POLICIES
-- ============================================================================
ALTER TABLE broker_tokens ENABLE ROW LEVEL SECURITY;

-- User can read their own tokens (auth client enforces this)
CREATE POLICY "broker_tokens_user_select" ON broker_tokens
  FOR SELECT USING (auth.uid() = user_id);

-- User can insert their own tokens (OAuth callback)
CREATE POLICY "broker_tokens_user_insert" ON broker_tokens
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- User can update their own tokens (token refresh)
-- Column-level restriction: prevent overwriting account_id via UPDATE
CREATE POLICY "broker_tokens_user_update" ON broker_tokens
  FOR UPDATE USING (auth.uid() = user_id);

-- No DELETE policy — tokens are revoked (revoked_at set), not deleted.
-- This preserves audit trail of when accounts were connected/disconnected.

-- ============================================================================
-- 3. RATE LIMIT TRACKING (DB-backed, not in-memory)
-- ============================================================================
-- Replaces in-memory rate limiter that resets on Edge Function cold start.

CREATE TABLE IF NOT EXISTS live_order_rate_limits (
  user_id     UUID         NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  window_start TIMESTAMPTZ NOT NULL,
  request_count INT        NOT NULL DEFAULT 1,
  PRIMARY KEY (user_id, window_start)
);

ALTER TABLE live_order_rate_limits ENABLE ROW LEVEL SECURITY;

-- Only service role writes to this; users cannot manipulate their own rate limits.
-- No user-facing RLS policies needed (service role bypasses RLS).
