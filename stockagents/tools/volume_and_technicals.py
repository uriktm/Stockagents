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
        "strength": 0.0,
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
