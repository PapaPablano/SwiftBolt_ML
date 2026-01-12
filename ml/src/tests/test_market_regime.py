import pandas as pd

from src.features.market_regime import add_market_regime_features


def test_market_regime_graceful_with_constant_prices():
    data = {
        "close": [100.0] * 60,
    }
    df = pd.DataFrame(data)

    result = add_market_regime_features(df)

    assert len(result) == len(df)
    assert "hmm_regime" in result.columns
    prob_cols = [c for c in result.columns if c.startswith("hmm_regime_prob_")]
    # Defaults to 3 states
    assert len(prob_cols) == 3
