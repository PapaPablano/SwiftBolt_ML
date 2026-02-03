#!/usr/bin/env python3
"""
Load the Hugging Face stock-trading RL agent (Adilbai/stock-trading-rl-agent),
run it on TSLA data, and compare performance to our walk-forward XGBoost/ARIMA.

Requires: pip install -r requirements_rl_compare.txt
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ID = "Adilbai/stock-trading-rl-agent"
MODEL_FILENAME = "final_model.zip"
SCALER_FILENAME = "scaler.pkl"
LOOKBACK = 60
SYMBOL = "TSLA"
PERIOD = "5y"


def _build_state_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build state features to match Adilbai/dataprocessor (technical indicators + lags)."""
    df = df.copy()
    df = df.sort_values("Date")
    # Technical indicators (match dataprocessor.py)
    df["SMA_5"] = df["Close"].rolling(window=5).mean()
    df["SMA_10"] = df["Close"].rolling(window=10).mean()
    df["SMA_20"] = df["Close"].rolling(window=20).mean()
    df["SMA_50"] = df["Close"].rolling(window=50).mean()
    df["EMA_12"] = df["Close"].ewm(span=12).mean()
    df["EMA_26"] = df["Close"].ewm(span=26).mean()
    df["MACD"] = df["EMA_12"] - df["EMA_26"]
    df["MACD_Signal"] = df["MACD"].ewm(span=9).mean()
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    df["BB_Middle"] = df["Close"].rolling(window=20).mean()
    bb_std = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["BB_Middle"] + (bb_std * 2)
    df["BB_Lower"] = df["BB_Middle"] - (bb_std * 2)
    df["BB_Width"] = df["BB_Upper"] - df["BB_Lower"]
    df["BB_Position"] = (df["Close"] - df["BB_Lower"]) / df["BB_Width"].replace(0, np.nan)
    df["Volatility"] = df["Close"].rolling(window=20).std()
    df["Price_Change"] = df["Close"].pct_change()
    df["High_Low_Ratio"] = df["High"] / df["Low"].replace(0, np.nan)
    df["Open_Close_Ratio"] = df["Open"] / df["Close"].replace(0, np.nan)
    df["Volume_SMA"] = df["Volume"].rolling(window=20).mean()
    df["Volume_Ratio"] = df["Volume"] / df["Volume_SMA"].replace(0, np.nan)
    for col in ["Close", "Volume", "Price_Change", "RSI", "MACD", "Volatility"]:
        for lag in [1, 2, 3, 5, 10]:
            if col in df.columns:
                df[f"{col}_lag_{lag}"] = df[col].shift(lag)
    return df


def _state_features_list() -> list:
    """Order of state features expected by the model (match dataprocessor create_rl_states_actions)."""
    base = [
        "Open", "High", "Low", "Close", "Volume",
        "SMA_5", "SMA_10", "SMA_20", "SMA_50",
        "EMA_12", "EMA_26", "MACD", "MACD_Signal", "RSI",
        "BB_Position", "BB_Width", "Volatility",
        "Price_Change", "High_Low_Ratio", "Volume_Ratio",
    ]
    lags = []
    for col in ["Close", "Volume", "Price_Change", "RSI", "MACD", "Volatility"]:
        for lag in [1, 2, 3, 5, 10]:
            lags.append(f"{col}_lag_{lag}")
    return base + lags


class MinimalStockEnv:
    """Minimal env matching Adilbai observation/action space for evaluation."""

    def __init__(self, states: np.ndarray, prices: np.ndarray, initial_balance: float = 10000, transaction_cost: float = 0.001):
        self.states = states  # (n_steps, lookback, n_features)
        self.prices = prices
        self.initial_balance = initial_balance
        self.transaction_cost = transaction_cost
        self.max_steps = len(states) - 1
        self.current_step = 0
        self.balance = initial_balance
        self.shares_held = 0
        self.net_worth = initial_balance
        self.peak_net_worth = initial_balance
        self.daily_returns = []
        self.trade_history = []

    def reset(self, seed=None):
        self.current_step = 0
        self.balance = self.initial_balance
        self.shares_held = 0
        self.net_worth = self.initial_balance
        self.peak_net_worth = self.initial_balance
        self.daily_returns = []
        self.trade_history = []
        return self._get_obs()

    def _get_obs(self):
        market = self.states[min(self.current_step, len(self.states) - 1)].flatten().astype(np.float32)
        price = self.prices[min(self.current_step, len(self.prices) - 1)]
        portfolio = np.array([
            self.balance / self.initial_balance,
            self.shares_held * price / self.initial_balance,
            self.net_worth / self.initial_balance,
            (self.net_worth - self.initial_balance) / self.initial_balance,
            len(self.trade_history) / 100.0,
            0.0, 0.0, 0.0,
        ], dtype=np.float32)
        return np.concatenate([market, portfolio])

    def step(self, action):
        action_type = int(np.clip(action[0], 0, 2))
        position_size = float(np.clip(action[1], 0, 1))
        price = self.prices[self.current_step]
        prev_net = self.net_worth

        if action_type == 1:  # Buy
            max_affordable = self.balance / price
            shares = int(max_affordable * position_size)
            if shares > 0:
                cost = shares * price
                tc = cost * self.transaction_cost
                if self.balance >= cost + tc:
                    self.shares_held += shares
                    self.balance -= (cost + tc)
                    self.trade_history.append({"action": "BUY", "shares": shares, "price": price})
        elif action_type == 2:  # Sell
            shares = int(self.shares_held * position_size)
            if shares > 0:
                revenue = shares * price
                tc = revenue * self.transaction_cost
                self.shares_held -= shares
                self.balance += (revenue - tc)
                self.trade_history.append({"action": "SELL", "shares": shares, "price": price})

        self.net_worth = self.balance + self.shares_held * price
        if self.net_worth > self.peak_net_worth:
            self.peak_net_worth = self.net_worth
        if prev_net > 0:
            self.daily_returns.append((self.net_worth - prev_net) / prev_net)
        reward = (self.net_worth - prev_net) / prev_net if prev_net > 0 else 0.0
        self.current_step += 1
        done = self.current_step >= self.max_steps
        info = {}
        if done:
            total_return = (self.net_worth - self.initial_balance) / self.initial_balance
            returns = np.array(self.daily_returns) if self.daily_returns else np.array([0.0])
            sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0.0
            info = {"total_return": total_return, "sharpe_ratio": sharpe, "total_trades": len(self.trade_history)}
        return self._get_obs(), reward, done, False, info


def main():
    print("=" * 60)
    print("RL AGENT vs WALK-FORWARD COMPARISON (TSLA)")
    print("=" * 60)

    # --- Load RL model and scaler from Hub ---
    print("\nLoading model and scaler from Hugging Face Hub...")
    try:
        from huggingface_sb3 import load_from_hub
        from stable_baselines3 import PPO
        from huggingface_hub import hf_hub_download
        import pickle
    except ImportError as e:
        print(f"Missing dependencies: {e}")
        print("Install with: pip install -r requirements_rl_compare.txt")
        sys.exit(1)

    try:
        checkpoint = load_from_hub(repo_id=REPO_ID, filename=MODEL_FILENAME)
        model = PPO.load(checkpoint)
        scaler_path = hf_hub_download(repo_id=REPO_ID, filename=SCALER_FILENAME)
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
        print(f"  Model: {REPO_ID}/{MODEL_FILENAME}")
        print(f"  Scaler: loaded")
    except Exception as e:
        print(f"Failed to load from Hub: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --- Get TSLA data (yfinance, 5y to match training) ---
    print(f"\nLoading {SYMBOL} data ({PERIOD})...")
    try:
        import yfinance as yf
        ticker = yf.Ticker(SYMBOL)
        hist = ticker.history(period=PERIOD, interval="1d")
        if hist.empty or len(hist) < LOOKBACK + 50:
            print("Insufficient yfinance data")
            sys.exit(1)
        hist = hist.reset_index()
        hist = hist.rename(columns={"Date": "Date", "Open": "Open", "High": "High", "Low": "Low", "Close": "Close", "Volume": "Volume"})
        df = hist[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
        df["Date"] = pd.to_datetime(df["Date"])
    except Exception as e:
        print(f"Data load failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --- Build states (match dataprocessor + scaler) ---
    print("Building state features and sequences...")
    df = _build_state_features(df)
    feats = _state_features_list()
    feats = [f for f in feats if f in df.columns]
    if hasattr(scaler, "feature_names_in_"):
        scaler_feats = list(scaler.feature_names_in_)
        feats = [f for f in scaler_feats if f in df.columns]
        if len(feats) < len(scaler_feats):
            print(f"  Warning: using {len(feats)} features (scaler expected {len(scaler_feats)})")
    if len(feats) < 20:
        print(f"Missing features; have {len(feats)} of expected ~50")
    df_clean = df.dropna()
    if len(df_clean) < LOOKBACK + 10:
        print("Too few rows after dropna")
        sys.exit(1)
    try:
        X = scaler.transform(df_clean[feats])
    except Exception as e:
        print(f"Scaler transform failed (feature mismatch?): {e}")
        sys.exit(1)
    states_list = []
    prices_list = []
    for i in range(LOOKBACK, len(df_clean)):
        states_list.append(X[i - LOOKBACK : i])
        prices_list.append(df_clean["Close"].iloc[i])  # current bar close for step
    states = np.array(states_list, dtype=np.float32)
    prices = np.array(prices_list, dtype=np.float32)
    print(f"  States shape: {states.shape}")

    # --- Run RL agent ---
    print("\nRunning RL agent evaluation...")
    env = MinimalStockEnv(states=states, prices=prices, initial_balance=10000, transaction_cost=0.001)
    obs = env.reset()
    total_reward = 0.0
    while True:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, truncated, info = env.step(action)
        total_reward += reward
        if done:
            break

    rl_return = info.get("total_return", (env.net_worth - env.initial_balance) / env.initial_balance)
    rl_sharpe = info.get("sharpe_ratio", 0.0)
    rl_trades = info.get("total_trades", len(env.trade_history))

    # --- Our walk-forward metrics (from last run) ---
    our_xgboost_acc = 0.515
    our_arima_acc = 0.472

    # --- Print comparison ---
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON")
    print("=" * 60)
    print("\n--- Hugging Face RL Agent (Adilbai/stock-trading-rl-agent) ---")
    print(f"  Total return:  {rl_return:.1%}")
    print(f"  Sharpe ratio:  {rl_sharpe:.2f}")
    print(f"  Total trades:  {rl_trades}")
    print(f"  Final net worth: ${env.net_worth:,.0f} (start $10,000)")
    print("\n--- Our walk-forward (Supabase TSLA 5d, same period style) ---")
    print(f"  XGBoost accuracy:  {our_xgboost_acc:.1%}")
    print(f"  ARIMA-GARCH accuracy: {our_arima_acc:.1%}")
    print("\n--- Note ---")
    print("  RL agent: trading strategy (return/Sharpe).")
    print("  Ours: directional accuracy (bullish/bearish). Different metrics.")
    print("  Run: python walk_forward_weekly.py TSLA --horizon 5 --threshold 0.02")
    print("  for latest walk-forward numbers.")
    print("=" * 60)


if __name__ == "__main__":
    main()
