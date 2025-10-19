"""Tool that analyzes trading volume and technical indicators for a ticker."""

from __future__ import annotations

import logging
from typing import Dict

import yfinance as yf

LOGGER = logging.getLogger(__name__)


def VolumeAndTechnicalsTool(stock_symbol: str) -> Dict[str, object]:
    """Analyze volume, RSI, and MACD crossover information for ``stock_symbol``."""
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
        LOGGER.warning("Failed to fetch technicals for %s: %s", stock_symbol, exc)

    return result


__all__ = ["VolumeAndTechnicalsTool"]
