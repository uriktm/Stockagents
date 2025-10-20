"""Tests for scoring stored forecast runs against realised price data."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from stockagents.core.history import (
    EvaluationSummary,
    classify_forecast_direction,
    classify_percent_change,
    evaluate_run_history,
    parse_run_history,
)


def test_classify_forecast_direction_variants() -> None:
    """Ensure heuristic keyword detection works for mixed/positive/negative cases."""

    assert classify_forecast_direction("צפויה עלייה חדה במחיר") == "up"
    assert classify_forecast_direction("מניית XYZ בירידה חדה".lower()) == "down"
    assert classify_forecast_direction("מגמה מעורבת צפויה".lower()) == "mixed"
    assert classify_forecast_direction("No directional hints here") == "unknown"


def test_classify_percent_change_thresholds() -> None:
    """Percent classification should respect the configured thresholds."""

    assert classify_percent_change(1.2, 0.5) == "up"
    assert classify_percent_change(-0.8, 0.5) == "down"
    assert classify_percent_change(0.1, 0.5) == "flat"
    assert classify_percent_change(None, 0.5) == "unknown"


def test_evaluate_run_history_updates_log(tmp_path: Path) -> None:
    """Historical evaluation should append outcome lines and report updates."""

    log_path = tmp_path / "run_history.log"
    log_path.write_text(
        "\n".join(
            [
                "=== Stock Analysis Run ===",
                "Run Date: 2025-10-20T12:00:00+03:00",
                "- Stock: TEST",
                "- Forecast: צפויה עלייה במחיר המניה בשל ביקוש גבוה",
                "- Confidence: 7.00",
                "",
            ]
        ),
        encoding="utf-8",
    )

    def stub_fetcher(symbol: str, start: date, end: date):
        assert symbol == "TEST"
        assert start <= date(2025, 10, 20) <= end
        return [
            (date(2025, 10, 17), 100.0),
            (date(2025, 10, 20), 103.0),
        ]

    summary = evaluate_run_history(
        log_path=log_path,
        price_fetcher=stub_fetcher,
        threshold=0.5,
        update_file=True,
    )

    assert isinstance(summary, EvaluationSummary)
    assert summary.updated_entries == 1
    assert summary.results[0].status == "match"
    assert "Actual Movement" in log_path.read_text(encoding="utf-8")


def test_parse_run_history_handles_empty(tmp_path: Path) -> None:
    """Parsing a missing history file should return an empty list without errors."""

    log_path = tmp_path / "run_history.log"
    entries = parse_run_history(log_path)
    assert entries == []

