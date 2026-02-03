# Comparison Models

This doc describes external models used for comparison with our walk-forward XGBoost/ARIMA pipeline.

## 1. Hugging Face RL Agent (Adilbai/stock-trading-rl-agent)

- **What:** PPO stock-trading agent (Hold/Buy/Sell + position size).
- **Run:** `python compare_rl_agent.py` (from `ml/`).
- **Deps:** `pip install -r requirements_rl_compare.txt` (stable-baselines3, huggingface-sb3, gymnasium).
- **Output:** Total return, Sharpe, trades vs our directional accuracy.

## 2. Google Research TimesFM (time series foundation model)

- **What:** Pretrained decoder-only time-series forecasting model (TimesFM 2.5 200M).
- **Repo:** Clone into project root for comparison:

  ```bash
  cd /path/to/SwiftBolt_ML
  gh repo clone google-research/timesfm
  # or: git clone https://github.com/google-research/timesfm.git
  ```

- **Install:** (use quotes so zsh doesn't glob `.[torch]`)

  ```bash
  cd timesfm
  pip install -e ".[torch]"
  cd ..
  ```

- **Run comparison:**

  ```bash
  cd ml
  python compare_timesfm.py
  ```

- **Output:** TimesFM directional accuracy (from point forecast) vs our XGBoost/ARIMA walk-forward accuracy.
