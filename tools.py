"""Utility tools for the Stockagents project."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List

from openai import OpenAI
import requests
import yfinance as yf


LOGGER = logging.getLogger(__name__)


def _load_local_env() -> None:
    """Load environment variables from .env file, overriding existing values to bypass stale system cache."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                # Force override to bypass Windows environment cache
                os.environ[key.strip()] = value.strip()
    except OSError:
        LOGGER.warning("Failed to read local .env file.")


_load_local_env()


def CorporateEventsTool(stock_symbol: str) -> Dict[str, object]:
    """Checks for upcoming corporate events for a given stock symbol, such as earnings report dates. Returns the date of the next earnings report if available."""
    result: Dict[str, object] = {
        "upcoming_earnings_date": None,
        "has_upcoming_event": False,
    }

    if not stock_symbol or not stock_symbol.strip():
        LOGGER.warning("CorporateEventsTool received an empty stock symbol.")
        return result

    try:
        # Pull the issuer's event calendar so investors know if catalysts like earnings are approaching.
        ticker = yf.Ticker(stock_symbol.strip())
        # Get more dates and filter for future ones
        earnings_dates = ticker.get_earnings_dates(limit=10)
        if earnings_dates is not None and not earnings_dates.empty:
            # Get current date for comparison
            today = datetime.now(timezone.utc).date()
            
            # Filter for future dates only
            future_dates = []
            for timestamp in earnings_dates.index:
                event_date = timestamp.to_pydatetime().date()
                if event_date >= today:
                    future_dates.append(timestamp)
            
            # Get the nearest future date
            if future_dates:
                next_event_timestamp = min(future_dates)
                upcoming_date = next_event_timestamp.to_pydatetime().date().isoformat()
                result["upcoming_earnings_date"] = upcoming_date
                result["has_upcoming_event"] = True
    except Exception as exc:  # pragma: no cover - best-effort logging
        LOGGER.warning(
            "Failed to fetch corporate events for %s: %s", stock_symbol, exc
        )

    return result


def VolumeAndTechnicalsTool(stock_symbol: str) -> Dict[str, object]:
    """Analyzes the trading volume and key technical indicators (RSI, MACD) for a given stock symbol. Returns the volume spike ratio and technical signals."""
    result: Dict[str, object] = {
        "volume_spike_ratio": None,
        "technical_signal": "Insufficient Data",
        "rsi": None,
        "macd_signal_status": "Unavailable",
    }

    if not stock_symbol or not stock_symbol.strip():
        LOGGER.warning("VolumeAndTechnicalsTool received an empty stock symbol.")
        return result

    try:
        # Gather recent price and volume history to gauge whether the ticker is drawing unusual trading interest.
        ticker = yf.Ticker(stock_symbol.strip())
        history = ticker.history(period="3mo", interval="1d")
        if history is None or history.empty:
            return result

        volume = history.get("Volume")
        close = history.get("Close")
        if volume is None or close is None or volume.empty or close.empty:
            return result

        volume = volume.dropna()
        if volume.shape[0] >= 2:
            recent_volume = volume.iloc[-1]
            lookback_volume = volume.iloc[:-1].tail(20)
            average_volume = lookback_volume.mean()
            if average_volume and average_volume > 0:
                # Compare today's turnover vs. the recent baseline to flag potential accumulation or distribution.
                result["volume_spike_ratio"] = float(recent_volume / average_volume)

        close = close.dropna()
        if close.shape[0] < 15:
            return result

        delta = close.diff()
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)

        avg_gain = gains.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        avg_loss = losses.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        if not avg_gain.empty and not avg_loss.empty:
            last_avg_gain = avg_gain.iloc[-1]
            last_avg_loss = avg_loss.iloc[-1]
            if last_avg_loss == 0:
                rsi_value = 100.0
            elif last_avg_gain == 0:
                rsi_value = 0.0
            else:
                rs = last_avg_gain / last_avg_loss
                rsi_value = 100 - (100 / (1 + rs))
            result["rsi"] = float(round(rsi_value, 2))

        macd_fast = close.ewm(span=12, adjust=False).mean()
        macd_slow = close.ewm(span=26, adjust=False).mean()
        macd_line = macd_fast - macd_slow
        signal_line = macd_line.ewm(span=9, adjust=False).mean()

        if macd_line.empty or signal_line.empty:
            return result

        macd_current = macd_line.iloc[-1]
        signal_current = signal_line.iloc[-1]
        macd_prev = None
        signal_prev = None
        if macd_line.shape[0] >= 2 and signal_line.shape[0] >= 2:
            macd_prev = macd_line.iloc[-2]
            signal_prev = signal_line.iloc[-2]

        macd_diff = macd_current - signal_current
        if macd_prev is not None and signal_prev is not None:
            prev_diff = macd_prev - signal_prev
            if prev_diff <= 0 < macd_diff or prev_diff >= 0 > macd_diff:
                # Flag crossover events which traders read as major momentum shifts.
                result["macd_signal_status"] = "Crossover"
            else:
                result["macd_signal_status"] = "No Crossover"
        else:
            result["macd_signal_status"] = "No Crossover"

        if result["macd_signal_status"] == "Crossover":
            if macd_diff > 0:
                result["technical_signal"] = "Bullish Momentum (MACD Crossover)"
            elif macd_diff < 0:
                result["technical_signal"] = "Bearish Momentum (MACD Crossover)"
            else:
                result["technical_signal"] = "Neutral Momentum (MACD Crossover)"
        else:
            if macd_diff > 0:
                result["technical_signal"] = "Bullish Momentum"
            elif macd_diff < 0:
                result["technical_signal"] = "Bearish Momentum"
            else:
                result["technical_signal"] = "Neutral Momentum"

    except Exception as exc:  # pragma: no cover - best-effort logging
        LOGGER.warning(
            "Failed to fetch technicals for %s: %s", stock_symbol, exc
        )

    return result


def NewsAndBuzzTool(stock_symbol: str) -> Dict[str, object]:
    """Aggregates recent news for a stock symbol from multiple financial feeds, analyzes sentiment, and measures media buzz.

    Returns a dictionary containing:
    - sentiment_score (float between -1 and 1)
    - narrative (short sentiment summary)
    - buzz_factor (media attention multiplier)
    - top_headlines (list of titles)
    - article_links (list of dicts with 'title', 'url', and 'source')
    - source_count (int) and sources_used (list of source labels)
    - source_breakdown (list of dicts describing article counts per source)
    """

    result: Dict[str, object] = {
        "sentiment_score": None,
        "narrative": "Insufficient data",
        "buzz_factor": 0.0,
        "top_headlines": [],
        "article_links": [],
        "source_count": 0,
        "sources_used": [],
        "source_breakdown": [],
    }

    if not stock_symbol or not stock_symbol.strip():
        LOGGER.warning("NewsAndBuzzTool received an empty stock symbol.")
        return result

    # Always reload from .env to bypass stale environment cache
    _load_local_env()

    news_api_key = os.getenv("NEWSAPI_API_KEY") or os.getenv("NEWS_API_KEY")
    fmp_api_key = os.getenv("FMP_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not news_api_key and not fmp_api_key:
        LOGGER.warning("NewsAndBuzzTool requires at least one news API key (NewsAPI or FMP_API_KEY).")
        return result

    if not openai_api_key:
        LOGGER.warning("NewsAndBuzzTool cannot run without OPENAI_API_KEY.")
        return result

    stock_symbol = stock_symbol.strip().upper()

    company_name = None
    try:
        ticker = yf.Ticker(stock_symbol)
        info = ticker.info
        if info:
            raw_name = info.get("longName") or info.get("shortName")
            if raw_name:
                company_name = raw_name.replace('"', "").strip()
    except Exception:
        pass

    suffixes = (
        " inc.",
        " inc",
        " corporation",
        " corp.",
        " corp",
        " company",
        " co.",
        " co",
        " ltd.",
        " ltd",
    )

    primary_company_name = company_name
    short_company_name = None
    if company_name:
        candidate = company_name
        lower_candidate = candidate.lower()
        for suffix in suffixes:
            if lower_candidate.endswith(suffix):
                candidate = candidate[: -len(suffix)].strip()
                lower_candidate = candidate.lower()
        if candidate and candidate.lower() != company_name.lower():
            short_company_name = candidate

    search_terms = [stock_symbol, f'"{stock_symbol}"']
    if company_name:
        search_terms.append(f'"{company_name}"')
    if short_company_name:
        search_terms.append(f'"{short_company_name}"')

    seen_terms = set()
    unique_terms = []
    for term in search_terms:
        if term and term not in seen_terms:
            unique_terms.append(term)
            seen_terms.add(term)
    search_query = f"({' OR '.join(unique_terms)})"

    combined_articles: List[Dict[str, object]] = []
    sources_used: Dict[str, int] = {}

    def add_article(raw_article: Dict[str, object], source_label: str) -> None:
        if not isinstance(raw_article, dict):
            return
        title = (raw_article.get("title") or "").strip()
        url = (raw_article.get("url") or "").strip()
        if not title:
            return
        description = raw_article.get("description") or raw_article.get("text") or ""
        content = raw_article.get("content") or raw_article.get("text") or ""
        published_at = raw_article.get("publishedAt") or raw_article.get("publishedDate")
        dedupe_key = url.lower() if url else title.lower()
        if any(article.get("_dedupe_key") == dedupe_key for article in combined_articles):
            return
        combined_articles.append(
            {
                "title": title,
                "url": url,
                "description": description,
                "content": content,
                "source": source_label,
                "publishedAt": published_at,
                "_dedupe_key": dedupe_key,
            }
        )
        sources_used[source_label] = sources_used.get(source_label, 0) + 1

    if news_api_key:
        try:
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": search_query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 15,
                    "domains": "bloomberg.com,reuters.com,cnbc.com,marketwatch.com,wsj.com,fool.com,seekingalpha.com,benzinga.com,yahoo.com,finance.yahoo.com",
                    "searchIn": "title,description",
                },
                headers={"Authorization": news_api_key},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            articles = payload.get("articles", []) if isinstance(payload, dict) else []
            for article in articles:
                add_article(article, "NewsAPI")
        except (requests.RequestException, json.JSONDecodeError) as exc:
            LOGGER.warning("Failed to fetch NewsAPI articles for %s: %s", stock_symbol, exc)

    if fmp_api_key:
        fmp_endpoints = (
            "https://financialmodelingprep.com/api/v4/stock_news",
            "https://financialmodelingprep.com/api/v3/stock_news",
        )
        for endpoint in fmp_endpoints:
            try:
                response = requests.get(
                    endpoint,
                    params={"tickers": stock_symbol, "limit": 25, "apikey": fmp_api_key},
                    timeout=10,
                )
                if response.status_code == 403:
                    text = response.text.lower()
                    if "legacy endpoint" in text or "invalid api key" in text:
                        LOGGER.info(
                            "FMP endpoint %s not available for the current plan; skipping.",
                            endpoint,
                        )
                        continue
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict):
                    articles = payload.get("data") or payload.get("news") or []
                else:
                    articles = payload
                if not isinstance(articles, list):
                    articles = []
                for article in articles:
                    add_article(article, "FMP")
            except (requests.RequestException, json.JSONDecodeError) as exc:
                LOGGER.warning("Failed to fetch FMP articles for %s from %s: %s", stock_symbol, endpoint, exc)

    if not combined_articles:
        return result

    company_aliases = {stock_symbol.lower()}
    if primary_company_name:
        company_aliases.add(primary_company_name.lower())
    if short_company_name:
        company_aliases.add(short_company_name.lower())

    def is_relevant(article: Dict[str, object]) -> bool:
        title = (article.get("title") or "").lower()
        description = (article.get("description") or "").lower()
        content = (article.get("content") or "").lower()
        combined = f"{title} {description} {content}"
        return any(alias in combined for alias in company_aliases if alias)

    filtered_articles = [article for article in combined_articles if is_relevant(article)]

    if not filtered_articles:
        return result

    # Sort by publish date (newest first) when available
    filtered_articles.sort(
        key=lambda a: a.get("publishedAt") or "",
        reverse=True,
    )

    headlines = [article["title"] for article in filtered_articles[:5]]
    article_links = [
        {"title": article["title"], "url": article["url"], "source": article["source"]}
        for article in filtered_articles[:5]
        if article.get("url")
    ]

    result["top_headlines"] = headlines
    result["article_links"] = article_links

    buzz_factor = round(len(filtered_articles) / 4.0, 2)
    result["buzz_factor"] = buzz_factor

    source_breakdown = [
        {"source": source, "count": count}
        for source, count in sources_used.items()
        if count > 0
    ]
    source_breakdown.sort(key=lambda item: (-item["count"], item["source"]))
    result["source_breakdown"] = source_breakdown
    result["sources_used"] = [item["source"] for item in source_breakdown]
    result["source_count"] = len(result["sources_used"])

    try:
        client = OpenAI(api_key=openai_api_key)
        sentiment_prompt = (
            "You are a financial news analyst. Analyze the sentiment of the following news "
            f"headlines about {stock_symbol}. Provide a JSON object with keys 'sentiment_score' (a number between -1 and 1) "
            "and 'narrative' (a short sentence summarizing the sentiment). Headlines: "
            + json.dumps(headlines)
        )
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You analyze financial news sentiment."},
                {"role": "user", "content": sentiment_prompt},
            ],
            temperature=0.2,
            max_tokens=250,
        )
        message = completion.choices[0].message
        content = (message.content or "{}") if message else "{}"
        sentiment_data = json.loads(content)
        sentiment_score = float(sentiment_data.get("sentiment_score", 0))
        narrative = str(sentiment_data.get("narrative", "No summary provided."))
        result["sentiment_score"] = sentiment_score
        result["narrative"] = narrative
    except (KeyError, ValueError, json.JSONDecodeError, TypeError) as exc:
        LOGGER.warning("Failed to parse sentiment response for %s: %s", stock_symbol, exc)
    except Exception as exc:  # pragma: no cover - best-effort logging
        LOGGER.warning("OpenAI sentiment analysis failed for %s: %s", stock_symbol, exc)

    # Remove helper key before returning
    for article in combined_articles:
        article.pop("_dedupe_key", None)

    return result

