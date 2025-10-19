"""Tool that aggregates recent news and sentiment for a ticker."""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List

import requests
import yfinance as yf
from openai import OpenAI

from stockagents.tools.environment import load_local_env

LOGGER = logging.getLogger(__name__)

# Ensure environment variables from the local .env are available when the module loads.
load_local_env()


def NewsAndBuzzTool(stock_symbol: str) -> Dict[str, object]:
    """Gather news, sentiment, and media buzz metrics for ``stock_symbol``."""
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

    # Always reload to bypass stale environment cache
    load_local_env()

    news_api_key = os.getenv("NEWSAPI_API_KEY") or os.getenv("NEWS_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not news_api_key:
        LOGGER.warning("NewsAndBuzzTool requires NEWSAPI_API_KEY (or NEWS_API_KEY).")
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

    for article in combined_articles:
        article.pop("_dedupe_key", None)

    return result


__all__ = ["NewsAndBuzzTool"]
