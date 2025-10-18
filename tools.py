"""Utility tools for the Stockagents project."""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List

from openai import OpenAI
import requests
import yfinance as yf


LOGGER = logging.getLogger(__name__)


def _load_local_env() -> None:
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
                os.environ.setdefault(key.strip(), value.strip())
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
        ticker = yf.Ticker(stock_symbol.strip())
        earnings_dates = ticker.get_earnings_dates(limit=1)
        if earnings_dates is not None and not earnings_dates.empty:
            next_event_timestamp = earnings_dates.index[0]
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
    """Fetches recent news articles for a given stock symbol, analyzes their sentiment, and calculates the media buzz factor."""

    result: Dict[str, object] = {
        "sentiment_score": None,
        "narrative": "Insufficient data",
        "buzz_factor": 0.0,
        "top_headlines": [],
    }

    if not stock_symbol or not stock_symbol.strip():
        LOGGER.warning("NewsAndBuzzTool received an empty stock symbol.")
        return result

    news_api_key = os.getenv("NEWSAPI_API_KEY") or os.getenv("NEWS_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not news_api_key:
        LOGGER.warning("NewsAndBuzzTool cannot run without NEWSAPI_API_KEY.")
        return result

    if not openai_api_key:
        LOGGER.warning("NewsAndBuzzTool cannot run without OPENAI_API_KEY.")
        return result

    stock_symbol = stock_symbol.strip()

    try:
        response = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": stock_symbol,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 10,
            },
            headers={"Authorization": news_api_key},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        articles: List[Dict[str, object]] = payload.get("articles", []) if isinstance(payload, dict) else []
    except (requests.RequestException, json.JSONDecodeError) as exc:
        LOGGER.warning("Failed to fetch news for %s: %s", stock_symbol, exc)
        return result

    headlines = [
        article.get("title")
        for article in articles
        if isinstance(article, dict) and article.get("title")
    ][:5]

    if not headlines:
        return result

    result["top_headlines"] = headlines
    buzz_factor = round(len(articles) / 4.0, 2)
    result["buzz_factor"] = buzz_factor

    try:
        client = OpenAI(api_key=openai_api_key)
        sentiment_prompt = (
            "You are a financial news analyst. Analyze the sentiment of the following news "
            f"headlines about {stock_symbol}. Provide a JSON object with keys 'sentiment_score' (a number between -1 and 1) "
            "and 'narrative' (a short sentence summarizing the sentiment). Headlines: "
            + json.dumps(headlines)
        )
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You analyze financial news sentiment."},
                {"role": "user", "content": sentiment_prompt},
            ],
            temperature=0.2,
            max_tokens=250,
        )
        message = completion.choices[0].message
        content = message.content if message else "{}"
        sentiment_data = json.loads(content)
        sentiment_score = float(sentiment_data.get("sentiment_score", 0))
        narrative = str(sentiment_data.get("narrative", "No summary provided."))
        result["sentiment_score"] = sentiment_score
        result["narrative"] = narrative
    except (KeyError, ValueError, json.JSONDecodeError, TypeError) as exc:
        LOGGER.warning("Failed to parse sentiment response for %s: %s", stock_symbol, exc)
    except Exception as exc:  # pragma: no cover - best-effort logging
        LOGGER.warning("OpenAI sentiment analysis failed for %s: %s", stock_symbol, exc)

    return result

