"""Tool that analyzes trading volume and technical indicators for a ticker."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional

import yfinance as yf

LOGGER = logging.getLogger(__name__)


def _compute_rsi(close_series, period: int = 14) -> Optional[float]:
    if close_series is None or close_series.empty or close_series.shape[0] <= period:
        return None

    delta = close_series.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)

    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    if avg_gain.empty or avg_loss.empty:
        return None

    last_avg_gain = avg_gain.iloc[-1]
    last_avg_loss = avg_loss.iloc[-1]
    if last_avg_loss == 0:
        return 100.0
    if last_avg_gain == 0:
        return 0.0

    rs = last_avg_gain / last_avg_loss
    return float(round(100 - (100 / (1 + rs)), 2))


def VolumeAndTechnicalsTool(stock_symbol: str) -> Dict[str, object]:
    """Analyze volume, RSI, MACD crossover, and intraday momentum for ``stock_symbol``."""
    result: Dict[str, object] = {
        "volume_spike_ratio": None,
        "technical_signal": "Insufficient Data",
        "rsi": None,
        "macd_signal_status": "Unavailable",
        "strength": 0.0,
        "intraday": {
            "last_price": None,
            "change_percent": None,
            "short_term_rsi": None,
            "volume_ratio": None,
            "last_update": None,
        },
    }

    if not stock_symbol or not stock_symbol.strip():
        LOGGER.warning("VolumeAndTechnicalsTool received an empty stock symbol.")
        return result

    try:
        ticker = yf.Ticker(stock_symbol.strip())
        history = ticker.history(period="3mo", interval="1d")
        if history is None or history.empty:
            LOGGER.warning("No historical data for %s", stock_symbol)
            return result

        volume = history.get("Volume")
        close = history.get("Close")
        if volume is None or close is None or volume.empty or close.empty:
            return result

        volume = volume.dropna()
        if volume.shape[0] >= 2:
            # Use the most recent COMPLETED trading day's volume
            # If current day is incomplete (intraday/after-hours), use previous day
            recent_volume = volume.iloc[-1]
            
            # Check if volume seems abnormally low (might be incomplete day)
            lookback_volume = volume.iloc[:-1].tail(20)
            average_volume = lookback_volume.mean()
            
            # If recent volume is suspiciously low (< 10% of average), use previous day
            if average_volume > 0 and recent_volume < (average_volume * 0.1):
                LOGGER.info(
                    "Recent volume for %s seems incomplete (%d vs avg %d), using previous day",
                    stock_symbol, recent_volume, int(average_volume)
                )
                LOGGER.debug(
                    "Recent volume for %s seems incomplete, details: recent_volume=%d, average_volume=%d, ratio=%.2f",
                    stock_symbol, recent_volume, int(average_volume), recent_volume / average_volume
                )
                if volume.shape[0] >= 3:
                    recent_volume = volume.iloc[-2]
                    lookback_volume = volume.iloc[:-2].tail(20)
                    average_volume = lookback_volume.mean()
            
            if average_volume and average_volume > 0:
                result["volume_spike_ratio"] = float(recent_volume / average_volume)

        close = close.dropna()
        if close.shape[0] < 15:
            return result

        daily_rsi = _compute_rsi(close)
        if daily_rsi is not None:
            result["rsi"] = daily_rsi

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

        # Compute a simple strength metric (0-1) combining RSI distance from mid, volume spike, and MACD alignment
        strength_components = []
        if result["rsi"] is not None:
            rsi = result["rsi"]
            strength_components.append(min(abs(rsi - 50) / 40, 1.0))
        if result["volume_spike_ratio"]:
            strength_components.append(min(result["volume_spike_ratio"] / 3.0, 1.0))
        if result["technical_signal"].startswith("Bullish"):
            strength_components.append(min(max(macd_diff, 0) * 5, 1.0))
        elif result["technical_signal"].startswith("Bearish"):
            strength_components.append(min(max(-macd_diff, 0) * 5, 1.0))

        if strength_components:
            result["strength"] = round(sum(strength_components) / len(strength_components), 2)

        intraday_result = result["intraday"]
        try:
            intraday_history = ticker.history(period="7d", interval="30m")
        except Exception as exc:
            LOGGER.debug("Intraday fetch failed for %s: %s", stock_symbol, exc)
            intraday_history = None

        if intraday_history is not None and not intraday_history.empty:
            intraday_history = intraday_history.dropna()
            if not intraday_history.empty:
                intraday_point = intraday_history.iloc[-1]
                last_price = intraday_point.get("Close")
                if last_price is not None:
                    intraday_result["last_price"] = float(last_price)

                timestamp = intraday_point.name
                if isinstance(timestamp, datetime):
                    intraday_result["last_update"] = timestamp.isoformat()
                elif hasattr(timestamp, "to_pydatetime"):
                    intraday_result["last_update"] = timestamp.to_pydatetime().isoformat()
                else:
                    intraday_result["last_update"] = str(timestamp)

                daily_close = close
                previous_close = None
                if daily_close is not None and not daily_close.empty:
                    if daily_close.shape[0] >= 2:
                        previous_close = float(daily_close.iloc[-2])
                    else:
                        previous_close = float(daily_close.iloc[-1])

                if previous_close and previous_close > 0 and last_price is not None:
                    change_percent = ((float(last_price) - previous_close) / previous_close) * 100
                    intraday_result["change_percent"] = float(round(change_percent, 2))

                intraday_close = intraday_history.get("Close")
                short_rsi = _compute_rsi(intraday_close, period=14)
                if short_rsi is not None:
                    intraday_result["short_term_rsi"] = short_rsi

                intraday_volume = intraday_history.get("Volume")
                if intraday_volume is not None and not intraday_volume.empty:
                    recent_volume = intraday_volume.iloc[-1]
                    lookback_intraday = intraday_volume.iloc[:-1].tail(20)
                    average_intraday = lookback_intraday.mean()
                    if average_intraday and average_intraday > 0:
                        intraday_result["volume_ratio"] = float(round(recent_volume / average_intraday, 2))

        # Log the complete results for debugging
        LOGGER.info(
            "Technical analysis for %s: RSI=%.2f, Volume Ratio=%.2f, Signal=%s, MACD Status=%s, Strength=%.2f",
            stock_symbol,
            result.get("rsi") or 0,
            result.get("volume_spike_ratio") or 0,
            result.get("technical_signal"),
            result.get("macd_signal_status"),
            result.get("strength", 0.0)
        )

    except Exception as exc:  # pragma: no cover - best-effort logging
        LOGGER.warning("Failed to fetch technicals for %s: %s", stock_symbol, exc)

    return result


__all__ = ["VolumeAndTechnicalsTool"]
