"""Tool that retrieves analyst ratings and price target data for a ticker."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import yfinance as yf

LOGGER = logging.getLogger(__name__)


def _safe_last_price(ticker: yf.Ticker) -> Optional[float]:
    """Best-effort extraction of the latest trading price for ``ticker``."""

    price: Optional[float] = None

    try:
        fast_info = getattr(ticker, "fast_info", None)
        if isinstance(fast_info, dict):
            price = fast_info.get("lastPrice") or fast_info.get("last_price")
        else:
            price = getattr(fast_info, "last_price", None) or getattr(
                fast_info, "lastPrice", None
            )
    except Exception:  # pragma: no cover - defensive guard
        price = None

    if price is None:
        try:
            info = getattr(ticker, "info", {})
            if isinstance(info, dict):
                price = info.get("regularMarketPrice") or info.get("previousClose")
        except Exception:  # pragma: no cover - defensive guard
            price = None

    return float(price) if price is not None else None


def AnalystRatingsTool(stock_symbol: str) -> Dict[str, object]:
    """Fetch analyst ratings, target prices, and recommendation distribution."""

    default_distribution: Dict[str, int] = {
        "strong_buy": 0,
        "buy": 0,
        "hold": 0,
        "sell": 0,
        "strong_sell": 0,
    }

    result: Dict[str, object] = {
        "consensus_rating": None,
        "consensus_score": None,
        "rating_distribution": default_distribution.copy(),
        "mean_target_price": None,
        "median_target_price": None,
        "target_price_low": None,
        "target_price_high": None,
        "latest_price": None,
        "target_price_change": None,
        "target_price_change_pct": None,
        "recent_actions": [],
    }

    if not stock_symbol or not stock_symbol.strip():
        LOGGER.warning("AnalystRatingsTool received an empty stock symbol.")
        return result

    stock_symbol = stock_symbol.strip().upper()

    try:
        ticker = yf.Ticker(stock_symbol)
    except Exception as exc:  # pragma: no cover - object creation should not fail
        LOGGER.warning("Failed to initialise yfinance.Ticker for %s: %s", stock_symbol, exc)
        return result

    price_targets: Dict[str, Optional[float]] = {}
    try:
        data = ticker.get_analyst_price_targets()
        if isinstance(data, dict):
            price_targets = data
    except Exception as exc:
        LOGGER.warning("Failed to fetch analyst price targets for %s: %s", stock_symbol, exc)

    latest_price = _safe_last_price(ticker)
    if latest_price is None:
        price_target_current = price_targets.get("current") if price_targets else None
        if price_target_current is not None:
            try:
                latest_price = float(price_target_current)
            except (TypeError, ValueError):
                latest_price = None

    if price_targets:
        def _get_numeric(key: str) -> Optional[float]:
            value = price_targets.get(key)
            try:
                return float(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        result["mean_target_price"] = _get_numeric("mean")
        result["median_target_price"] = _get_numeric("median")
        result["target_price_low"] = _get_numeric("low")
        result["target_price_high"] = _get_numeric("high")

    result["latest_price"] = latest_price

    mean_target = result["mean_target_price"]
    if mean_target is not None and latest_price is not None:
        delta = mean_target - latest_price
        result["target_price_change"] = round(delta, 2)
        if latest_price:
            result["target_price_change_pct"] = round(delta / latest_price * 100, 2)

    recommendations_df = None
    try:
        recommendations_df = ticker.get_recommendations_summary()
    except Exception as exc:
        LOGGER.warning(
            "Failed to fetch analyst recommendations summary for %s: %s",
            stock_symbol,
            exc,
        )

    if recommendations_df is not None:
        try:
            latest_row = recommendations_df.iloc[-1]
            mapping = {
                "strongBuy": "strong_buy",
                "buy": "buy",
                "hold": "hold",
                "sell": "sell",
                "strongSell": "strong_sell",
            }
            distribution = {}
            for column, target_key in mapping.items():
                count = latest_row.get(column, 0)
                try:
                    distribution[target_key] = int(count) if count == count else 0
                except (TypeError, ValueError):
                    distribution[target_key] = 0

            result["rating_distribution"] = {**default_distribution, **distribution}

            total = sum(result["rating_distribution"].values())
            if total > 0:
                weights = {
                    "strong_buy": 5,
                    "buy": 4,
                    "hold": 3,
                    "sell": 2,
                    "strong_sell": 1,
                }
                score = sum(
                    result["rating_distribution"][key] * weight
                    for key, weight in weights.items()
                ) / total
                result["consensus_score"] = round(score, 2)
                if score >= 4.5:
                    result["consensus_rating"] = "Strong Buy"
                elif score >= 3.5:
                    result["consensus_rating"] = "Buy"
                elif score >= 2.5:
                    result["consensus_rating"] = "Hold"
                elif score >= 1.5:
                    result["consensus_rating"] = "Sell"
                else:
                    result["consensus_rating"] = "Strong Sell"
        except Exception as exc:  # pragma: no cover - defensive guard
            LOGGER.warning(
                "Failed to process recommendations summary for %s: %s",
                stock_symbol,
                exc,
            )

    recent_actions: List[Dict[str, Optional[str]]] = []
    try:
        actions_df = ticker.get_upgrades_downgrades()
        if actions_df is not None and not actions_df.empty:
            trimmed = actions_df.tail(5)
            for idx, row in trimmed.iloc[::-1].iterrows():
                date_str: Optional[str] = None
                if hasattr(idx, "isoformat"):
                    try:
                        date_str = idx.isoformat()
                    except Exception:  # pragma: no cover - defensive guard
                        date_str = None
                elif isinstance(idx, str):
                    date_str = idx

                recent_actions.append(
                    {
                        "date": date_str,
                        "firm": row.get("firm"),
                        "from_grade": row.get("fromGrade"),
                        "to_grade": row.get("toGrade"),
                        "action": row.get("action"),
                    }
                )
    except Exception as exc:
        LOGGER.warning("Failed to fetch upgrades/downgrades for %s: %s", stock_symbol, exc)

    result["recent_actions"] = recent_actions

    return result


__all__ = ["AnalystRatingsTool"]
