"""Unit tests for the SocialSentimentTool helper."""

import pytest

from stockagents.tools.social_sentiment import SocialSentimentTool


def test_social_sentiment_combines_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aggregated buzz and sentiment should reflect both Reddit and X data."""

    reddit_posts = [
        {"text": "AAPL is breaking out", "engagement": 12, "preview": "AAPL is breaking out"},
        {"text": "I'm buying more AAPL", "engagement": 5, "preview": "I'm buying more AAPL"},
    ]
    x_posts = [
        {"text": "$AAPL to the moon!", "engagement": 20, "preview": "$AAPL to the moon!"}
    ]

    monkeypatch.setattr(
        "stockagents.tools.social_sentiment._fetch_reddit_mentions",
        lambda symbol: (reddit_posts, None),
    )
    monkeypatch.setattr(
        "stockagents.tools.social_sentiment._fetch_x_mentions",
        lambda symbol: (x_posts, None),
    )

    result = SocialSentimentTool("AAPL")

    assert result["reddit"]["mention_count"] == 2
    assert result["x"]["mention_count"] == 1
    assert result["combined_buzz_score"] > 0
    assert result["strength"] > 0
    assert "Reddit mentions" in result["narrative"]


def test_social_sentiment_handles_missing_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing social data should return informative error fields."""

    monkeypatch.setattr(
        "stockagents.tools.social_sentiment._fetch_reddit_mentions",
        lambda symbol: ([], "rate limited"),
    )
    monkeypatch.setattr(
        "stockagents.tools.social_sentiment._fetch_x_mentions",
        lambda symbol: ([], "no credentials"),
    )

    result = SocialSentimentTool("TSLA")

    assert result["reddit"]["mention_count"] == 0
    assert result["reddit"]["error"] == "rate limited"
    assert result["x"]["error"] == "no credentials"
    assert result["narrative"] == "Insufficient social data."


def test_social_sentiment_empty_symbol() -> None:
    """Blank ticker symbols should result in the default response."""

    result = SocialSentimentTool("   ")
    assert result["narrative"] == "Insufficient social data."
    assert result["strength"] == 0.0
