"""Unit tests for the AnalystRatingsTool."""

from __future__ import annotations

import pandas as pd

from stockagents.tools import analyst_ratings


def test_analyst_ratings_tool_handles_empty_symbol() -> None:
    """Verify the tool returns safe defaults for an empty stock symbol."""

    result = analyst_ratings.AnalystRatingsTool("")

    assert result["consensus_rating"] is None
    assert result["consensus_score"] is None
    assert all(value == 0 for value in result["rating_distribution"].values())
    assert result["recent_actions"] == []


def test_analyst_ratings_tool_aggregates_data(monkeypatch) -> None:
    """The tool should combine price targets, ratings, and actions when available."""

    class DummyTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def get_analyst_price_targets(self) -> dict:
            return {
                "current": 110.0,
                "mean": 125.0,
                "median": 123.0,
                "high": 150.0,
                "low": 95.0,
            }

        def get_recommendations_summary(self):
            return pd.DataFrame(
                [
                    {"strongBuy": 4, "buy": 8, "hold": 3, "sell": 1, "strongSell": 0},
                    {"strongBuy": 5, "buy": 7, "hold": 4, "sell": 1, "strongSell": 0},
                ]
            )

        def get_upgrades_downgrades(self):
            df = pd.DataFrame(
                [
                    {"firm": "Firm A", "toGrade": "Buy", "fromGrade": "Hold", "action": "up"},
                    {"firm": "Firm B", "toGrade": "Hold", "fromGrade": "Buy", "action": "down"},
                ]
            )
            df.index = pd.to_datetime(["2024-01-01", "2024-01-05"])
            return df

        @property
        def fast_info(self):
            return {"lastPrice": 110.0}

    monkeypatch.setattr(analyst_ratings.yf, "Ticker", lambda symbol: DummyTicker(symbol))

    result = analyst_ratings.AnalystRatingsTool("AAPL")

    assert result["latest_price"] == 110.0
    assert result["mean_target_price"] == 125.0
    assert result["target_price_change"] == 15.0
    assert result["target_price_change_pct"] == 13.64
    assert result["rating_distribution"] == {
        "strong_buy": 5,
        "buy": 7,
        "hold": 4,
        "sell": 1,
        "strong_sell": 0,
    }
    assert result["consensus_rating"] == "Buy"
    assert result["consensus_score"] == 3.94

    assert len(result["recent_actions"]) == 2
    assert result["recent_actions"][0]["firm"] == "Firm B"
    assert result["recent_actions"][1]["firm"] == "Firm A"
