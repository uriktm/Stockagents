from __future__ import annotations

import os

import pytest

from stockagents.tools.environment import load_local_env
from stockagents.tools.social_sentiment import SocialSentimentTool


def test_social_sentiment_integration_runs_when_credentials_present() -> None:
    load_local_env()
    bearer = os.getenv("X_BEARER_TOKEN")
    serpapi = os.getenv("SERPAPI_API_KEY")

    if not bearer and not serpapi:
        pytest.skip("No social credentials configured; skipping integration test.")

    result = SocialSentimentTool("AAPL")

    assert isinstance(result, dict)
    assert "reddit" in result and isinstance(result["reddit"], dict)
    assert "x" in result and isinstance(result["x"], dict)

    assert isinstance(result.get("combined_buzz_score", 0.0), float)
    assert 0.0 <= result.get("combined_buzz_score", 0.0) <= 1.5

    strength = result.get("strength", 0.0)
    assert isinstance(strength, float)
    assert 0.0 <= strength <= 1.0

    narrative = result.get("narrative", "")
    assert isinstance(narrative, str)

    x_section = result["x"]
    assert "mention_count" in x_section
    assert isinstance(x_section.get("mention_count", 0), int)

    reddit_section = result["reddit"]
    assert "mention_count" in reddit_section
    assert isinstance(reddit_section.get("mention_count", 0), int)
