"""
Thin Streamlit UI for stock news sentiment using ml.src.features.stock_sentiment.

Run from repo root: streamlit run ml/src/scripts/run_stock_sentiment_app.py

Requires: streamlit (e.g. pip install streamlit)
"""

import sys
from pathlib import Path

# Allow importing from ml.src when run as script (from repo root or ml/)
_script_dir = Path(__file__).resolve().parent
_ml_root = _script_dir.parents[1]  # ml/
_repo_root = _script_dir.parents[2]  # SwiftBolt_ML/
for _p in (_ml_root, _repo_root):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import streamlit as st

from src.features.stock_sentiment import (
    get_finviz_news,
    get_sentiment_for_ticker,
    parse_news,
    plot_daily_sentiment,
    plot_hourly_sentiment,
    score_news,
)

st.set_page_config(
    page_title="Stock News Sentiment (SwiftBolt)",
    layout="wide",
)
st.header("Stock News Sentiment")
ticker = st.text_input("Enter Stock Ticker", "").strip().upper() or None

if ticker:
    try:
        st.subheader(f"Hourly and Daily Sentiment for {ticker}")
        news_table = get_finviz_news(ticker)
        parsed = parse_news(news_table)
        if parsed.empty:
            st.warning(f"No news table or rows found for {ticker}.")
        else:
            scored = score_news(parsed)
            fig_h = plot_hourly_sentiment(scored, ticker)
            fig_d = plot_daily_sentiment(scored, ticker)
            if fig_h:
                st.plotly_chart(fig_h)
            if fig_d:
                st.plotly_chart(fig_d)
            st.caption(
                f"Charts show average sentiment (VADER compound) for {ticker} "
                "from FinViz headlines. Table below: per-headline neg/neu/pos and compound."
            )
            st.dataframe(scored)
    except Exception as e:
        st.error(str(e))
else:
    st.info("Enter a ticker (e.g. AAPL) and run to see sentiment.")

st.markdown(
    """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True,
)
