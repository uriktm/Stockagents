"""Tool that aggregates community sentiment from Reddit and X (Twitter)."""

from __future__ import annotations

import datetime as _dt
import logging
import os
import statistics
from typing import Dict, List, Optional, Tuple

import requests

from stockagents.tools.environment import load_local_env

LOGGER = logging.getLogger(__name__)

# Ensure environment variables from the local .env are available when the module loads.
load_local_env()

try:  # pragma: no cover - import guard
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except ModuleNotFoundError:  # pragma: no cover - handled gracefully in runtime logic
    SentimentIntensityAnalyzer = None  # type: ignore[assignment]

_ANALYZER: Optional[SentimentIntensityAnalyzer]
if SentimentIntensityAnalyzer is None:  # pragma: no cover - executed only when dependency missing
    _ANALYZER = None
else:
    _ANALYZER = SentimentIntensityAnalyzer()


def _analyze_sentiment(text: str) -> Optional[float]:
    """Return the VADER compound sentiment score for ``text``."""
    if not text or _ANALYZER is None:
        return None
    return float(_ANALYZER.polarity_scores(text).get("compound", 0.0))


def _isoformat_timestamp(timestamp: Optional[float]) -> Optional[str]:
    """Convert a Unix timestamp (seconds) to ISO8601 with ``Z`` suffix."""
    if not timestamp:
        return None
    try:
        return _dt.datetime.utcfromtimestamp(float(timestamp)).replace(microsecond=0).isoformat() + "Z"
    except (ValueError, OSError):  # pragma: no cover - defensive programming
        return None


def _truncate(text: str, limit: int = 200) -> str:
    """Return a truncated preview of ``text`` for display in tool results."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _fetch_reddit_mentions(stock_symbol: str) -> Tuple[List[Dict[str, object]], Optional[str]]:
    """Retrieve Reddit submissions discussing ``stock_symbol`` using the PullPush API."""
    posts: List[Dict[str, object]] = []
    error: Optional[str] = None

    params = {
        "q": stock_symbol,
        "subreddit": "wallstreetbets,stocks,investing,StockMarket",
        "size": 40,
        "sort": "desc",
        "sort_type": "created_utc",
        "language": "en",
    }

    try:
        response = requests.get(
            "https://api.pullpush.io/reddit/search/submission/",
            params=params,
            headers={"User-Agent": "StockAgents/1.0 (+https://github.com/)"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            body = (item.get("selftext") or "").strip()
            if not title and not body:
                continue
            full_text = title if not body else f"{title}. {body}" if title else body
            post = {
                "title": title or _truncate(body, 80),
                "text": full_text,
                "preview": _truncate(full_text, 180),
                "subreddit": item.get("subreddit"),
                "url": item.get("full_link") or item.get("url"),
                "created_at": _isoformat_timestamp(item.get("created_utc")),
                "engagement": int(item.get("score") or 0) + int(item.get("num_comments") or 0),
            }
            posts.append(post)
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("Failed to fetch Reddit data for %s: %s", stock_symbol, exc)
        error = str(exc)

    return posts, error


def _fetch_x_mentions(stock_symbol: str) -> Tuple[List[Dict[str, object]], Optional[str]]:
    """Retrieve recent mentions from X (Twitter) using available credentials."""
    posts: List[Dict[str, object]] = []
    error: Optional[str] = None

    bearer_token = (os.getenv("TWITTER_BEARER_TOKEN") or os.getenv("X_BEARER_TOKEN"))
    if bearer_token:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        params = {
            "query": f"(\"{stock_symbol}\" OR ${stock_symbol}) lang:en -is:retweet",
            "max_results": 50,
            "tweet.fields": "created_at,lang,public_metrics",
        }
        try:
            response = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params=params,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("data", []):
                if not isinstance(item, dict):
                    continue
                text = (item.get("text") or "").strip()
                if not text:
                    continue
                metrics = item.get("public_metrics") or {}
                engagement = int(metrics.get("retweet_count", 0))
                engagement += int(metrics.get("reply_count", 0))
                engagement += int(metrics.get("like_count", 0))
                posts.append(
                    {
                        "text": text,
                        "preview": _truncate(text, 180),
                        "url": f"https://twitter.com/i/web/status/{item.get('id')}",
                        "created_at": item.get("created_at"),
                        "engagement": engagement,
                        "author_id": item.get("author_id"),
                    }
                )
        except (requests.RequestException, ValueError) as exc:
            LOGGER.warning("Failed to fetch Twitter data for %s: %s", stock_symbol, exc)
            error = str(exc)

        return posts, error

    serpapi_key = os.getenv("SERPAPI_API_KEY")
    if not serpapi_key:
        return posts, "Missing TWITTER_BEARER_TOKEN/X_BEARER_TOKEN or SERPAPI_API_KEY"

    params = {
        "engine": "twitter",
        "q": stock_symbol,
        "api_key": serpapi_key,
        "tweet_type": "top",
        "num": 20,
    }
    try:
        response = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("tweets", []):
            if not isinstance(item, dict):
                continue
            text = (item.get("snippet") or "").strip()
            if not text:
                continue
            engagement = 0
            metrics = item.get("engagement") or {}
            for key in ("retweet_count", "reply_count", "like_count", "favorite_count"):
                engagement += int(metrics.get(key, 0)) if isinstance(metrics, dict) else 0
            posts.append(
                {
                    "text": text,
                    "preview": _truncate(text, 180),
                    "url": item.get("link"),
                    "created_at": item.get("published_at"),
                    "engagement": engagement,
                    "author": item.get("user", {}).get("name") if isinstance(item.get("user"), dict) else None,
                }
            )
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("Failed to fetch SerpAPI Twitter data for %s: %s", stock_symbol, exc)
        error = str(exc)

    return posts, error


def _score_posts(posts: List[Dict[str, object]]) -> Dict[str, object]:
    """Compute aggregated statistics for a collection of social posts."""
    mention_count = len(posts)
    sentiments: List[float] = []
    for post in posts:
        sentiment = _analyze_sentiment(post.get("text", ""))
        if sentiment is not None:
            post["sentiment"] = round(sentiment, 3)
            sentiments.append(sentiment)
        else:
            post["sentiment"] = None
    average_sentiment = round(statistics.mean(sentiments), 3) if sentiments else None
    buzz_score = round(min(mention_count / 30.0, 1.0), 2) if mention_count else 0.0

    # Sort by engagement descending and return a trimmed copy for presentation
    sorted_posts = sorted(posts, key=lambda item: item.get("engagement", 0), reverse=True)
    top_posts = [
        {key: value for key, value in post.items() if key != "text"}
        for post in sorted_posts[:5]
    ]

    return {
        "mention_count": mention_count,
        "average_sentiment": average_sentiment,
        "buzz_score": buzz_score,
        "top_posts": top_posts,
    }


def SocialSentimentTool(stock_symbol: str) -> Dict[str, object]:
    """Gather Reddit and X sentiment data for ``stock_symbol``."""
    result: Dict[str, object] = {
        "reddit": {
            "mention_count": 0,
            "average_sentiment": None,
            "buzz_score": 0.0,
            "top_posts": [],
            "error": None,
        },
        "x": {
            "mention_count": 0,
            "average_sentiment": None,
            "buzz_score": 0.0,
            "top_posts": [],
            "error": None,
        },
        "combined_buzz_score": 0.0,
        "combined_sentiment": None,
        "narrative": "Insufficient social data.",
        "strength": 0.0,
    }

    if not stock_symbol or not stock_symbol.strip():
        LOGGER.warning("SocialSentimentTool received an empty stock symbol.")
        return result

    load_local_env()  # refresh for every invocation
    stock_symbol = stock_symbol.strip().upper()

    reddit_posts, reddit_error = _fetch_reddit_mentions(stock_symbol)
    reddit_metrics = _score_posts(reddit_posts) if reddit_posts else {
        "mention_count": 0,
        "average_sentiment": None,
        "buzz_score": 0.0,
        "top_posts": [],
    }
    result["reddit"].update(reddit_metrics)
    result["reddit"]["error"] = reddit_error

    x_posts, x_error = _fetch_x_mentions(stock_symbol)
    x_metrics = _score_posts(x_posts) if x_posts else {
        "mention_count": 0,
        "average_sentiment": None,
        "buzz_score": 0.0,
        "top_posts": [],
    }
    result["x"].update(x_metrics)
    result["x"]["error"] = x_error

    sentiments = [
        metric
        for metric in (result["reddit"].get("average_sentiment"), result["x"].get("average_sentiment"))
        if metric is not None
    ]
    if sentiments:
        result["combined_sentiment"] = round(statistics.mean(sentiments), 3)

    combined_buzz = result["reddit"].get("buzz_score", 0.0) + result["x"].get("buzz_score", 0.0)
    result["combined_buzz_score"] = round(min(combined_buzz, 1.5), 2)
    if result["combined_buzz_score"] > 0:
        result["strength"] = round(min(result["combined_buzz_score"] / 1.5, 1.0), 2)

    narrative_bits: List[str] = []
    if result["reddit"]["mention_count"]:
        reddit_sentiment = result["reddit"].get("average_sentiment")
        reddit_descriptor = "neutral"
        if reddit_sentiment is not None:
            if reddit_sentiment >= 0.1:
                reddit_descriptor = "bullish"
            elif reddit_sentiment <= -0.1:
                reddit_descriptor = "bearish"
            else:
                reddit_descriptor = "mixed"
        narrative_bits.append(
            f"Reddit mentions: {result['reddit']['mention_count']} ({reddit_descriptor})."
        )
    if result["x"]["mention_count"]:
        x_sentiment = result["x"].get("average_sentiment")
        x_descriptor = "neutral"
        if x_sentiment is not None:
            if x_sentiment >= 0.1:
                x_descriptor = "bullish"
            elif x_sentiment <= -0.1:
                x_descriptor = "bearish"
            else:
                x_descriptor = "mixed"
        narrative_bits.append(
            f"X mentions: {result['x']['mention_count']} ({x_descriptor})."
        )
    if result["combined_sentiment"] is not None:
        narrative_bits.append(f"Overall sentiment score: {result['combined_sentiment']:+.2f}.")

    if narrative_bits:
        result["narrative"] = " ".join(narrative_bits)

    return result


__all__ = ["SocialSentimentTool"]
