"""Utilities for evaluating historical Stockagents forecasts against market data."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from .analysis import LOG_FILE_PATH

# Type alias for price history fetchers. Each tuple represents (trading_date, close_price).
PriceHistory = Sequence[Tuple[date, float]]


@dataclasses.dataclass
class RunHistoryEntry:
    """Structured representation of a single run entry from ``run_history.log``."""

    run_date_text: Optional[str]
    stock: Optional[str]
    forecast: Optional[str]
    confidence_text: Optional[str]
    extra_lines: List[str]
    run_date: Optional[datetime]


@dataclasses.dataclass
class EvaluationResult:
    """Summary of how a historical forecast compared to actual price action."""

    symbol: str
    run_date: Optional[datetime]
    forecast: Optional[str]
    predicted_direction: str
    actual_direction: str
    percent_change: Optional[float]
    baseline_date: Optional[date]
    baseline_close: Optional[float]
    target_date: Optional[date]
    target_close: Optional[float]
    status: str
    reason: Optional[str] = None

    def movement_line(self) -> str:
        """Return a human-readable summary of the observed market move."""

        if self.percent_change is None or self.baseline_close is None or self.target_close is None:
            reason = self.reason or "Insufficient market data"
            return f"- Actual Movement: Unavailable ({reason})"

        direction_titles = {
            "up": "Up",
            "down": "Down",
            "flat": "Flat",
            "unknown": "Unknown",
        }
        direction = direction_titles.get(self.actual_direction, "Unknown")
        pct_display = f"{self.percent_change:+.2f}%"
        baseline_label = self.baseline_date.isoformat() if self.baseline_date else "?"
        target_label = self.target_date.isoformat() if self.target_date else "?"
        return (
            f"- Actual Movement: {direction} {pct_display} "
            f"({baseline_label}: {self.baseline_close:.2f} → {target_label}: {self.target_close:.2f})"
        )

    def outcome_line(self) -> str:
        """Return a formatted string describing the accuracy outcome."""

        status_title = {
            "match": "Match",
            "mismatch": "Mismatch",
            "inconclusive": "Inconclusive",
            "insufficient-data": "Inconclusive",
            "error": "Error",
        }.get(self.status, self.status.title())

        base = f"- Prediction Outcome: {status_title}"
        if self.reason:
            return f"{base} ({self.reason})"
        if self.predicted_direction and self.actual_direction and self.percent_change is not None:
            return (
                f"{base} (predicted {self.predicted_direction}, "
                f"actual {self.actual_direction} {self.percent_change:+.2f}%)"
            )
        return base


@dataclasses.dataclass
class EvaluationSummary:
    """Container for ``evaluate_run_history`` outputs."""

    results: List[EvaluationResult]
    updated_entries: int
    log_path: Path


def parse_run_history(log_path: Path = LOG_FILE_PATH) -> List[RunHistoryEntry]:
    """Parse ``run_history.log`` into structured entries."""

    if not log_path.exists():
        return []

    content = log_path.read_text(encoding="utf-8")
    blocks = content.split("=== Stock Analysis Run ===")
    entries: List[RunHistoryEntry] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        run_date_text = _extract_prefixed_value(lines, "Run Date:")
        stock = _extract_prefixed_value(lines, "- Stock:")
        forecast = _extract_prefixed_value(lines, "- Forecast:")
        confidence_text = _extract_prefixed_value(lines, "- Confidence:")
        extra_lines = [
            line
            for line in lines
            if line.startswith("- ")
            and not line.startswith("- Stock:")
            and not line.startswith("- Forecast:")
            and not line.startswith("- Confidence:")
        ]
        run_date = None
        if run_date_text:
            try:
                run_date = datetime.fromisoformat(run_date_text)
            except ValueError:
                run_date = None

        entries.append(
            RunHistoryEntry(
                run_date_text=run_date_text,
                stock=stock,
                forecast=forecast,
                confidence_text=confidence_text,
                extra_lines=extra_lines,
                run_date=run_date,
            )
        )

    return entries


def _extract_prefixed_value(lines: Iterable[str], prefix: str) -> Optional[str]:
    """Extract the value after ``prefix`` from the first matching line."""

    for line in lines:
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def classify_forecast_direction(forecast: Optional[str]) -> str:
    """Infer the expected price direction from a free-form forecast string."""

    if not forecast:
        return "unknown"

    text = forecast.lower()

    positive_keywords = [
        "עלייה",
        "יעלה",
        "עליות",
        "חיובי",
        "אופטימי",
        "bullish",
        "positive",
        "up",
        "higher",
        "increase",
        "צמיחה",
        "חיזוק",
        "קנייה",
    ]
    negative_keywords = [
        "ירידה",
        "ירידות",
        "שלילי",
        "לחץ",
        "bearish",
        "down",
        "נפילה",
        "תיקון",
        "sell",
        "חולשה",
    ]
    mixed_keywords = [
        "מעורבת",
        "מעורב",
        "mixed",
        "neutral",
        "דשדוש",
        "תנודת",
    ]

    has_positive = any(keyword in text for keyword in positive_keywords)
    has_negative = any(keyword in text for keyword in negative_keywords)
    has_mixed = any(keyword in text for keyword in mixed_keywords)

    if (has_positive and has_negative) or has_mixed:
        return "mixed"
    if has_positive:
        return "up"
    if has_negative:
        return "down"
    return "unknown"


def classify_percent_change(percent: Optional[float], threshold: float) -> str:
    """Categorize a percent change into up/down/flat buckets."""

    if percent is None:
        return "unknown"
    if percent >= threshold:
        return "up"
    if percent <= -threshold:
        return "down"
    return "flat"


def determine_outcome(predicted: str, actual: str, percent_change: Optional[float]) -> Tuple[str, Optional[str]]:
    """Compare predicted and actual directions and derive an accuracy label."""

    if predicted == "unknown" or actual == "unknown":
        return "inconclusive", "Forecast or market direction unavailable"

    if predicted == "mixed":
        if actual == "flat":
            return "match", "Mixed outlook aligned with flat movement"
        return "inconclusive", "Mixed outlook cannot be scored against directional move"

    if predicted == "flat":
        if actual == "flat":
            return "match", None
        return "mismatch", "Forecast expected flat movement"

    if predicted == actual:
        return "match", None

    if percent_change is None:
        return "inconclusive", "Percent change unavailable"

    return "mismatch", f"Predicted {predicted}, actual {actual} ({percent_change:+.2f}%)"


def default_price_fetcher(symbol: str, start: date, end: date) -> PriceHistory:
    """Retrieve historical prices using ``yfinance`` as the data source."""

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("yfinance is required for price fetching") from exc

    # yfinance expects an exclusive end date; include one buffer day.
    end_plus_one = end + timedelta(days=1)
    data = yf.download(
        symbol,
        start=start.isoformat(),
        end=end_plus_one.isoformat(),
        interval="1d",
        progress=False,
    )

    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("pandas is required for price parsing") from exc

    if isinstance(data, pd.DataFrame):
        rows = data.reset_index()
        history: List[Tuple[date, float]] = []
        for _, row in rows.iterrows():
            idx = row.get("Date")
            close_value = row.get("Close")
            if pd.isna(close_value):
                continue
            trading_date = idx.date() if hasattr(idx, "date") else idx
            history.append((trading_date, float(close_value)))
        return history

    return []


def evaluate_entry(
    entry: RunHistoryEntry,
    *,
    price_fetcher: Callable[[str, date, date], PriceHistory],
    threshold: float,
) -> EvaluationResult:
    """Evaluate a single history entry."""

    symbol = entry.stock or "Unknown"
    predicted_direction = classify_forecast_direction(entry.forecast)

    if entry.run_date is None or entry.stock is None:
        return EvaluationResult(
            symbol=symbol,
            run_date=entry.run_date,
            forecast=entry.forecast,
            predicted_direction=predicted_direction,
            actual_direction="unknown",
            percent_change=None,
            baseline_date=None,
            baseline_close=None,
            target_date=None,
            target_close=None,
            status="error",
            reason="Missing run date or stock symbol",
        )

    run_day = entry.run_date.date()
    start = run_day - timedelta(days=7)
    end = run_day + timedelta(days=7)

    try:
        history = list(price_fetcher(entry.stock, start, end))
    except Exception as exc:  # pragma: no cover - network/IO errors
        return EvaluationResult(
            symbol=symbol,
            run_date=entry.run_date,
            forecast=entry.forecast,
            predicted_direction=predicted_direction,
            actual_direction="unknown",
            percent_change=None,
            baseline_date=None,
            baseline_close=None,
            target_date=None,
            target_close=None,
            status="error",
            reason=f"Price fetch failed: {exc}",
        )

    if len(history) < 2:
        return EvaluationResult(
            symbol=symbol,
            run_date=entry.run_date,
            forecast=entry.forecast,
            predicted_direction=predicted_direction,
            actual_direction="unknown",
            percent_change=None,
            baseline_date=None,
            baseline_close=None,
            target_date=None,
            target_close=None,
            status="insufficient-data",
            reason="Not enough trading sessions in selected window",
        )

    sorted_history = sorted(history, key=lambda item: item[0])
    target_index = None
    for idx, (session_date, _) in enumerate(sorted_history):
        if session_date >= run_day:
            target_index = idx
            break

    if target_index is None:
        return EvaluationResult(
            symbol=symbol,
            run_date=entry.run_date,
            forecast=entry.forecast,
            predicted_direction=predicted_direction,
            actual_direction="unknown",
            percent_change=None,
            baseline_date=None,
            baseline_close=None,
            target_date=None,
            target_close=None,
            status="insufficient-data",
            reason="No trading day on or after run date",
        )

    if target_index == 0:
        return EvaluationResult(
            symbol=symbol,
            run_date=entry.run_date,
            forecast=entry.forecast,
            predicted_direction=predicted_direction,
            actual_direction="unknown",
            percent_change=None,
            baseline_date=None,
            baseline_close=None,
            target_date=None,
            target_close=None,
            status="insufficient-data",
            reason="No earlier trading day to compare against",
        )

    baseline_date, baseline_close = sorted_history[target_index - 1]
    target_date, target_close = sorted_history[target_index]

    if baseline_close == 0:
        percent_change = None
    else:
        percent_change = ((target_close - baseline_close) / baseline_close) * 100

    actual_direction = classify_percent_change(percent_change, threshold)
    status, reason = determine_outcome(predicted_direction, actual_direction, percent_change)

    return EvaluationResult(
        symbol=symbol,
        run_date=entry.run_date,
        forecast=entry.forecast,
        predicted_direction=predicted_direction,
        actual_direction=actual_direction,
        percent_change=percent_change,
        baseline_date=baseline_date,
        baseline_close=baseline_close,
        target_date=target_date,
        target_close=target_close,
        status=status,
        reason=reason,
    )


def evaluate_run_history(
    *,
    log_path: Path = LOG_FILE_PATH,
    price_fetcher: Callable[[str, date, date], PriceHistory] = default_price_fetcher,
    threshold: float = 0.5,
    update_file: bool = True,
) -> EvaluationSummary:
    """Compare forecast history against realised price action and optionally update the log."""

    entries = parse_run_history(log_path)
    results: List[EvaluationResult] = []
    updated_entries = 0

    if not entries:
        return EvaluationSummary(results=[], updated_entries=0, log_path=log_path)

    for entry in entries:
        previous_eval_lines = [
            line
            for line in entry.extra_lines
            if line.startswith("- Actual Movement:")
            or line.startswith("- Prediction Outcome:")
        ]
        entry.extra_lines = [
            line
            for line in entry.extra_lines
            if not line.startswith("- Actual Movement:")
            and not line.startswith("- Prediction Outcome:")
        ]

        evaluation = evaluate_entry(entry, price_fetcher=price_fetcher, threshold=threshold)
        results.append(evaluation)

        if update_file:
            new_lines = [evaluation.movement_line(), evaluation.outcome_line()]
            if previous_eval_lines != new_lines:
                entry.extra_lines.extend(new_lines)
                updated_entries += 1
            else:
                entry.extra_lines.extend(previous_eval_lines)

    if update_file:
        _write_entries(log_path, entries)

    return EvaluationSummary(results=results, updated_entries=updated_entries, log_path=log_path)


def _write_entries(log_path: Path, entries: List[RunHistoryEntry]) -> None:
    """Persist the run history entries back to disk."""

    output_blocks: List[str] = []

    for entry in entries:
        lines: List[str] = ["=== Stock Analysis Run ==="]
        if entry.run_date_text:
            lines.append(f"Run Date: {entry.run_date_text}")
        if entry.stock:
            lines.append(f"- Stock: {entry.stock}")
        if entry.forecast:
            lines.append(f"- Forecast: {entry.forecast}")
        if entry.confidence_text:
            lines.append(f"- Confidence: {entry.confidence_text}")
        lines.extend(entry.extra_lines)
        output_blocks.append("\n".join(lines))

    text = "\n\n".join(output_blocks) + "\n"
    log_path.write_text(text, encoding="utf-8")


__all__ = [
    "EvaluationResult",
    "EvaluationSummary",
    "RunHistoryEntry",
    "classify_forecast_direction",
    "classify_percent_change",
    "determine_outcome",
    "evaluate_run_history",
    "parse_run_history",
]

