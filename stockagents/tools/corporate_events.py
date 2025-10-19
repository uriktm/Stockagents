"""Tool that surfaces upcoming corporate events for a ticker."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict

import yfinance as yf

LOGGER = logging.getLogger(__name__)


def CorporateEventsTool(stock_symbol: str) -> Dict[str, object]:
    """Return information about the next corporate earnings event for ``stock_symbol``."""
    result: Dict[str, object] = {
        "upcoming_earnings_date": None,
        "has_upcoming_event": False,
    }

    if not stock_symbol or not stock_symbol.strip():
        LOGGER.warning("CorporateEventsTool received an empty stock symbol.")
        return result

    try:
        ticker = yf.Ticker(stock_symbol.strip())
        earnings_dates = ticker.get_earnings_dates(limit=10)
        if earnings_dates is not None and not earnings_dates.empty:
            today = datetime.now(timezone.utc).date()

            future_dates = []
            for timestamp in earnings_dates.index:
                event_date = timestamp.to_pydatetime().date()
                if event_date >= today:
                    future_dates.append(timestamp)

            if future_dates:
                next_event_timestamp = min(future_dates)
                upcoming_date = next_event_timestamp.to_pydatetime().date().isoformat()
                result["upcoming_earnings_date"] = upcoming_date
                result["has_upcoming_event"] = True
    except Exception as exc:  # pragma: no cover - best-effort logging
        LOGGER.warning("Failed to fetch corporate events for %s: %s", stock_symbol, exc)

    return result


__all__ = ["CorporateEventsTool"]
