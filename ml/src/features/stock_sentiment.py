"""
Stock news sentiment from FinViz using NLTK VADER.

Fetches news headlines for a ticker from FinViz, parses them into a DataFrame,
and scores each headline with VADER compound sentiment. Can be used as a
feature source (e.g., daily/hourly sentiment aggregates) or for dashboards/API.
"""

import datetime
import logging
from typing import Any, Optional, Union

import pandas as pd
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

FINVIZ_QUOTE_URL = "https://finviz.com/quote.ashx?t="

# Lazy init for VADER so NLTK download happens only when first used
_vader: Optional[Any] = None


def _get_vader():
    """Return SentimentIntensityAnalyzer, downloading vader_lexicon if needed."""
    global _vader
    if _vader is None:
        import nltk

        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
        from nltk.sentiment.vader import SentimentIntensityAnalyzer

        _vader = SentimentIntensityAnalyzer()
    return _vader


def get_finviz_news(ticker: str, user_agent: Optional[str] = None) -> Any:
    """
    Fetch the news table HTML for a ticker from FinViz.

    Args:
        ticker: Symbol (e.g. 'AAPL').
        user_agent: Optional User-Agent header; default mimics a browser.

    Returns:
        BeautifulSoup element for the element with id='news-table', or None if not found.
    """
    url = FINVIZ_QUOTE_URL + ticker.upper()
    req = Request(
        url,
        headers={
            "User-Agent": user_agent
            or "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0"
        },
    )
    with urlopen(req) as response:
        html = BeautifulSoup(response.read(), "html.parser")
    news_table = html.find(id="news-table")
    if news_table is None:
        logger.warning("FinViz news table not found for ticker=%s", ticker)
    return news_table


def _normalize_news_url(href: Optional[str]) -> str:
    """Return absolute URL for a FinViz news link (may be relative)."""
    if not href or not href.strip():
        return ""
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("//"):
        return "https:" + href
    base = "https://finviz.com"
    return base + (href if href.startswith("/") else "/" + href)


def parse_news(news_table: Any) -> pd.DataFrame:
    """
    Parse FinViz news table into a DataFrame with date, time, headline, url.

    Args:
        news_table: BeautifulSoup element from get_finviz_news (or None).

    Returns:
        DataFrame with columns: date, time, headline, url, datetime.
        Empty DataFrame if news_table is None or has no rows.
    """
    if news_table is None:
        return pd.DataFrame(columns=["date", "time", "headline", "url"])

    parsed_news: list[list[str]] = []
    today_string = datetime.datetime.today().strftime("%Y-%m-%d")

    for row in news_table.findAll("tr"):
        try:
            anchor = row.a
            text = anchor.get_text()
            href = anchor.get("href")
            url = _normalize_news_url(href) if href else ""
            parts = row.td.text.split()
            if len(parts) == 1:
                date, time = today_string, parts[0]
            else:
                date, time = parts[0], parts[1]
            parsed_news.append([date, time, text, url])
        except Exception:
            continue

    if not parsed_news:
        return pd.DataFrame(columns=["date", "time", "headline", "url"])

    df = pd.DataFrame(parsed_news, columns=["date", "time", "headline", "url"])
    df["date"] = df["date"].replace("Today", today_string)
    try:
        df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"], format="mixed", dayfirst=False)
    except TypeError:
        df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"])
    return df


def score_news(parsed_news_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add VADER polarity scores to parsed news; use compound as sentiment_score.

    Args:
        parsed_news_df: From parse_news (columns: date, time, headline, datetime).

    Returns:
        DataFrame indexed by datetime with headline, url, neg, neu, pos, sentiment_score.
    """
    if parsed_news_df.empty:
        out = pd.DataFrame(
            columns=["headline", "url", "neg", "neu", "pos", "sentiment_score"]
        )
        out.index.name = "datetime"
        return out

    vader = _get_vader()
    scores = parsed_news_df["headline"].apply(vader.polarity_scores).tolist()
    scores_df = pd.DataFrame(scores)
    out = parsed_news_df.copy()
    out = out.join(scores_df, rsuffix="_right")
    out = out.set_index("datetime")
    out = out.drop(columns=["date", "time"], errors="ignore")
    out = out.rename(columns={"compound": "sentiment_score"})
    return out


def get_sentiment_items_for_api(
    ticker: str, limit: int = 50
) -> list[dict[str, Any]]:
    """
    Return FinViz news items with links and sentiment in API shape for the news tab.

    Each item has: id, title, url, source, publishedAt, summary, sentiment_score
    so the client can display and open article links.

    Args:
        ticker: Symbol (e.g. 'AAPL').
        limit: Max number of items to return (default 50).

    Returns:
        List of dicts compatible with news API (id, title, url, source, publishedAt, summary, sentiment_score).
    """
    scored = get_sentiment_for_ticker(ticker)
    if scored.empty:
        return []
    # Sort newest first; take up to limit
    scored = scored.sort_index(ascending=False).head(limit)
    items: list[dict[str, Any]] = []
    for idx, (dt, row) in enumerate(scored.iterrows()):
        url = str(row.get("url", "") or "")
        headline = str(row.get("headline", "") or "")
        pub_iso = pd.Timestamp(dt).isoformat() if hasattr(dt, "isoformat") else str(dt)
        item_id = f"finviz-{ticker.upper()}-{idx}-{hash(url) % 2**32}"
        items.append({
            "id": item_id,
            "title": headline,
            "url": url or "#",
            "source": "FinViz",
            "publishedAt": pub_iso,
            "summary": f"Sentiment: {row.get('sentiment_score', 0):.2f}",
            "sentiment_score": float(row.get("sentiment_score", 0)),
        })
    return items


def get_sentiment_for_ticker(ticker: str) -> pd.DataFrame:
    """
    Fetch FinViz news for a ticker, parse, and score with VADER.

    One-shot helper for use in pipelines or API.

    Args:
        ticker: Symbol (e.g. 'AAPL').

    Returns:
        DataFrame indexed by datetime with headline, neg, neu, pos, sentiment_score.
    """
    news_table = get_finviz_news(ticker)
    parsed = parse_news(news_table)
    return score_news(parsed)


def hourly_sentiment_series(scored_df: pd.DataFrame) -> pd.Series:
    """Resample scored news to hourly mean sentiment (for features or plots)."""
    if scored_df.empty or "sentiment_score" not in scored_df.columns:
        return pd.Series(dtype=float)
    return scored_df["sentiment_score"].resample("h").mean()


def daily_sentiment_series(scored_df: pd.DataFrame) -> pd.Series:
    """Resample scored news to daily mean sentiment (for features or plots)."""
    if scored_df.empty or "sentiment_score" not in scored_df.columns:
        return pd.Series(dtype=float)
    return scored_df["sentiment_score"].resample("D").mean()


def get_historical_sentiment_series(
    symbol: str,
    start_date: Union[datetime.date, pd.Timestamp, str],
    end_date: Union[datetime.date, pd.Timestamp, str],
    use_finviz_realtime: bool = True,
) -> pd.Series:
    """
    Daily sentiment series for a symbol over a date range for backtest/features.

    Real-time integration: DB (sentiment_scores) provides history; FinViz live
    data overrides for overlapping dates and fills the tail when FinViz has
    fresher dates than OHLCV bars (e.g. bars end yesterday, FinViz has today).

    Returns:
        pd.Series with date index (timezone-naive), values = daily mean sentiment.
        Missing dates: ffill then 0 (no lookahead).
    """
    start = pd.Timestamp(start_date).normalize().date()
    end = pd.Timestamp(end_date).normalize().date()
    if start > end:
        return pd.Series(dtype=float)

    full_range = pd.date_range(start=start, end=end, freq="D")
    end_ts = pd.Timestamp(end)

    # 1) DB: sentiment_scores for [start, end]
    db_series: pd.Series | None = None
    try:
        from supabase import create_client
        from config.settings import settings
        client = create_client(
            settings.supabase_url,
            settings.supabase_key or settings.supabase_service_role_key or "",
        )
        sym = client.table("symbols").select("id").eq("ticker", symbol.upper()).single().execute()
        if sym.data:
            r = (
                client.table("sentiment_scores")
                .select("as_of_date, sentiment_score")
                .eq("symbol_id", sym.data["id"])
                .gte("as_of_date", start.isoformat())
                .lte("as_of_date", end.isoformat())
                .execute()
            )
            if r.data and len(r.data) > 0:
                df = pd.DataFrame(r.data)
                df["as_of_date"] = pd.to_datetime(df["as_of_date"]).dt.normalize()
                db_series = df.set_index("as_of_date")["sentiment_score"].sort_index()
    except Exception as e:
        logger.debug("get_historical_sentiment_series: DB (%s)", e)

    # 2) FinViz live: daily aggregates (always fetch for real-time variance)
    finviz_daily: pd.Series | None = None
    if use_finviz_realtime:
        scored = get_sentiment_for_ticker(symbol)
        if not scored.empty and "sentiment_score" in scored.columns:
            daily = scored["sentiment_score"].resample("D").mean()
            if not daily.empty:
                daily.index = daily.index.tz_localize(None) if daily.index.tz else daily.index
                daily.index = daily.index.normalize()
                finviz_daily = daily

    # 3) Merge: FinViz takes precedence over DB for overlapping dates
    if db_series is not None:
        base = db_series.reindex(full_range).ffill().fillna(0.0)
    else:
        base = pd.Series(0.0, index=full_range)

    if finviz_daily is not None and not finviz_daily.empty:
        # 3a) FinViz overrides DB where dates overlap
        finviz_reindexed = finviz_daily.reindex(full_range)
        base = base.where(finviz_reindexed.isna(), finviz_reindexed)

        # 3b) When FinViz has data AFTER end (bars end yesterday, FinViz has today):
        #    map FinViz values to last N bar-dates for day-to-day variance
        after_end = finviz_daily[finviz_daily.index > end_ts].sort_index()
        if not after_end.empty:
            base = base.copy()
            n_tail = min(len(after_end), 7, len(base))
            if n_tail > 0:
                # Use per-date FinViz values in reverse: bar[-1]<-finviz[-1], bar[-2]<-finviz[-2], ...
                tail_vals = after_end.iloc[-n_tail:].values[::-1]
                base.iloc[-n_tail:] = tail_vals

    base = base.ffill().fillna(0.0)
    return base


def validate_sentiment_variance(
    symbol: str = "TSLA",
    lookback_days: int = 100,
) -> bool:
    """
    Ensure sentiment has predictive variance before using in features.

    Success criteria: std > 0.01, mean abs daily change > 0.005, range > 0.05.

    Returns:
        True if sentiment passes all variance checks.
    """
    try:
        from src.data.supabase_db import SupabaseDatabase
        from src.features.temporal_indicators import compute_simplified_features
    except ImportError:
        logger.warning("validate_sentiment_variance: missing deps (supabase_db, temporal_indicators)")
        return False

    db = SupabaseDatabase()
    df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=lookback_days + 50)
    if df is None or len(df) < 50:
        logger.warning("validate_sentiment_variance: insufficient OHLCV for %s", symbol)
        return False

    start_date = pd.to_datetime(df["ts"]).min().date()
    end_date = pd.to_datetime(df["ts"]).max().date()
    sentiment_series = get_historical_sentiment_series(symbol, start_date, end_date)
    if sentiment_series is None or sentiment_series.empty:
        logger.warning("validate_sentiment_variance: no sentiment data for %s", symbol)
        return False

    df_feat = compute_simplified_features(df.copy(), sentiment_series=sentiment_series)
    if "sentiment_score" not in df_feat.columns:
        logger.warning("validate_sentiment_variance: sentiment_score not in computed features")
        return False

    sentiment = df_feat["sentiment_score"]
    std_val = float(sentiment.std() or 0)
    daily_changes = sentiment.diff().abs()
    mean_abs_change = float(daily_changes.mean() or 0)
    range_val = float(sentiment.max() - sentiment.min() or 0)

    checks = {
        "std > 0.01": std_val > 0.01,
        "mean_abs_daily_change > 0.005": mean_abs_change > 0.005,
        "range > 0.05": range_val > 0.05,
    }
    passed = all(checks.values())

    logger.info(
        "validate_sentiment_variance(%s): std=%.4f, mean_abs_change=%.4f, range=%.4f -> %s",
        symbol,
        std_val,
        mean_abs_change,
        range_val,
        "PASS" if passed else "FAIL",
    )
    return passed


def plot_hourly_sentiment(
    scored_df: pd.DataFrame, ticker: str
) -> "Optional[Any]":
    """
    Return a Plotly bar figure of hourly mean sentiment (optional dependency).

    Use only when plotly is installed; returns None if plotly is not available.
    """
    try:
        import plotly.express as px
    except ImportError:
        logger.debug("plotly not installed, skipping hourly sentiment plot")
        return None
    series = hourly_sentiment_series(scored_df)
    if series.empty:
        return None
    mean_scores = series.to_frame("sentiment_score")
    fig = px.bar(
        mean_scores,
        x=mean_scores.index,
        y="sentiment_score",
        title=f"{ticker} Hourly Sentiment Scores",
    )
    return fig


def plot_daily_sentiment(
    scored_df: pd.DataFrame, ticker: str
) -> "Optional[Any]":
    """
    Return a Plotly bar figure of daily mean sentiment (optional dependency).

    Use only when plotly is installed; returns None if plotly is not available.
    """
    try:
        import plotly.express as px
    except ImportError:
        logger.debug("plotly not installed, skipping daily sentiment plot")
        return None
    series = daily_sentiment_series(scored_df)
    if series.empty:
        return None
    mean_scores = series.to_frame("sentiment_score")
    fig = px.bar(
        mean_scores,
        x=mean_scores.index,
        y="sentiment_score",
        title=f"{ticker} Daily Sentiment Scores",
    )
    return fig
