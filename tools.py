"""Utility tools for the Stockagents project."""

from __future__ import annotations

import logging
from typing import Dict

import yfinance as yf


LOGGER = logging.getLogger(__name__)


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
