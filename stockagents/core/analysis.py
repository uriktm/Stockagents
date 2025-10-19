"""Business logic for orchestrating Stockagents assistant runs."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from openai import OpenAI

from stockagents.assistant import create_assistant
from stockagents.tools import (
    CorporateEventsTool,
    NewsAndBuzzTool,
    VolumeAndTechnicalsTool,
)

LOGGER = logging.getLogger(__name__)
LOG_FILE_PATH = Path(__file__).resolve().parent.parent.parent / "run_history.log"
DETAILED_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "detailed_analysis.log"

# Configure detailed file logging
def _setup_detailed_logging():
    """Setup detailed logging to file with full debug information."""
    file_handler = logging.FileHandler(DETAILED_LOG_PATH, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
    )
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)
    LOGGER.setLevel(logging.DEBUG)

# Call setup on module load
_setup_detailed_logging()


def parse_symbols(raw: str) -> List[str]:
    """Parse a comma-separated string of tickers into a normalized list."""
    symbols: List[str] = []
    if not raw:
        return symbols

    for chunk in raw.split(","):
        symbol = chunk.strip().upper()
        if symbol:
            symbols.append(symbol)
    return symbols


def _wait_for_run_completion(
    client: OpenAI,
    thread_id: str,
    run_id: str,
    tool_dispatch: Dict[str, Callable[..., object]],
    poll_interval: float = 1.0,
) -> str:
    """Poll the Assistants API until the run reaches a terminal state."""
    terminal_states = {"completed", "failed", "cancelled", "expired"}

    while True:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        status = getattr(run, "status", None)
        if status == "requires_action":
            action = getattr(run, "required_action", None)
            submit = getattr(action, "submit_tool_outputs", None) if action else None
            tool_calls = getattr(submit, "tool_calls", None) if submit else None
            if tool_calls:
                outputs = []
                for call in tool_calls:
                    function_meta = getattr(call, "function", None)
                    name = getattr(function_meta, "name", "") if function_meta else ""
                    arguments = getattr(function_meta, "arguments", "") if function_meta else ""
                    LOGGER.info("Run %s requested tool %s", run_id, name)
                    handler = tool_dispatch.get(name)
                    if handler is None:
                        LOGGER.error("No handler registered for tool %s", name)
                        outputs.append(
                            {
                                "tool_call_id": getattr(call, "id", ""),
                                "output": json.dumps({"error": "Unknown tool"}),
                            }
                        )
                        continue
                    try:
                        parsed_args = json.loads(arguments) if arguments else {}
                    except json.JSONDecodeError:
                        LOGGER.error("Failed to decode arguments for tool %s", name)
                        parsed_args = {}
                    if not isinstance(parsed_args, dict):
                        LOGGER.error("Unexpected arguments type for tool %s", name)
                        parsed_args = {}
                    try:
                        tool_output = handler(**parsed_args)
                        LOGGER.info("Tool %s completed", name)
                    except Exception as exc:  # pragma: no cover - best-effort logging
                        LOGGER.exception("Tool %s execution failed", name)
                        tool_output = {"error": str(exc)}
                    outputs.append(
                        {
                            "tool_call_id": getattr(call, "id", ""),
                            "output": json.dumps(tool_output if tool_output is not None else {}),
                        }
                    )
                if outputs:
                    client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run_id,
                        tool_outputs=outputs,
                    )
                    continue
        if status in terminal_states:
            LOGGER.info("Run %s reached terminal status: %s", run_id, status)
            return status or "unknown"
        time.sleep(max(poll_interval, 0.1))


def _render_assistant_response(messages: Iterable) -> str:
    """Extract the latest assistant message from the thread messages."""
    sorted_messages = sorted(
        list(messages),
        key=lambda msg: getattr(msg, "created_at", 0),
        reverse=True,
    )
    for message in sorted_messages:
        if getattr(message, "role", "") != "assistant":
            continue
        parts: List[str] = []
        for block in getattr(message, "content", []):
            if getattr(block, "type", "") == "text":
                text = getattr(getattr(block, "text", None), "value", None)
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts)
    return "(No assistant response was generated.)"


def _extract_confidence_score(raw_response: str) -> Optional[float]:
    """Extract the numeric confidence score from the assistant's response."""
    if not raw_response:
        LOGGER.warning("Empty response for confidence extraction")
        return None

    patterns = [
        r"confidence\s*score[^0-9]*([0-9]+(?:\.[0-9]+)?)",
        r"ציון\s*ביטחון[^0-9]*([0-9]+(?:\.[0-9]+)?)",
        r"([0-9]+(?:\.[0-9]+)?)\s*/\s*10",
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, raw_response, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                LOGGER.info(
                    "Confidence score extracted: %.1f (using pattern #%d: '%s')",
                    score, i + 1, pattern[:50]
                )
                return score
            except (TypeError, ValueError) as e:
                LOGGER.warning("Failed to convert confidence score: %s", e)
                continue
    
    # If no pattern matched, log a sample of the response for debugging
    LOGGER.warning(
        "No confidence score found in response. Sample (first 300 chars): %s",
        raw_response[:300]
    )
    return None


def _extract_forecast(raw_response: str) -> Optional[str]:
    """Attempt to extract the forecast statement from the assistant's response."""
    if not raw_response:
        LOGGER.warning("Empty response received for forecast extraction")
        return None

    # Try multiple patterns to extract forecast
    patterns = [
        # Hebrew with colon
        r"^\s*-?\s*\*?\*?תחזית\*?\*?[^:]*:\s*(.+)$",
        # English with colon
        r"^\s*-?\s*\*?\*?forecast\*?\*?[^:]*:\s*(.+)$",
        # Hebrew with number prefix (1. תחזית:)
        r"^\s*\d+\.\s*\*?\*?תחזית\*?\*?[^:]*:\s*(.+)$",
        # English with number prefix
        r"^\s*\d+\.\s*\*?\*?forecast\*?\*?[^:]*:\s*(.+)$",
        # Look for common forecast indicators with more context
        r"(?:צפויה?|פוטנציאל ל|מגמת?)[^\n]{15,250}",
        r"(?:expected|potential for|trend of|bullish|bearish)[^\n]{15,250}",
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, raw_response, re.IGNORECASE | re.MULTILINE)
        if match:
            # Extract the matched text
            if match.lastindex:  # If there's a capturing group
                forecast = match.group(1).strip()
            else:
                forecast = match.group(0).strip()
            
            # Clean up the forecast
            forecast = forecast.strip('*').strip()
            
            # Skip if it's too short or looks like a header
            if len(forecast) > 10 and not forecast.endswith(':'):
                LOGGER.info("Forecast extracted using pattern #%d", i + 1)
                return forecast
    
    # Last resort: try to find the first substantial sentence
    lines = raw_response.split('\n')
    for line in lines:
        line = line.strip().strip('*').strip('-').strip()
        if len(line) > 20 and not line.endswith(':') and not line.startswith('#'):
            # Check if it contains forecast-like keywords
            forecast_keywords = ['צפוי', 'עלי', 'ירידה', 'מגמה', 'פוטנציאל', 'expected', 'trend', 'potential', 'bullish', 'bearish']
            if any(keyword in line.lower() for keyword in forecast_keywords):
                LOGGER.info("Forecast extracted using fallback method")
                return line
    
    # Ultimate fallback: return the first non-empty line if it's substantial
    for line in lines:
        line = line.strip().strip('*').strip('-').strip()
        if len(line) > 30:
            LOGGER.warning("Using first substantial line as forecast (no keywords matched)")
            return line
    
    LOGGER.error("Failed to extract forecast from response. First 200 chars: %s", raw_response[:200])
    return None


def _append_run_log(entry: Dict[str, object]) -> None:
    """Append the run details to the persistent log file."""
    timestamp = datetime.now(timezone.utc).astimezone().isoformat()
    symbol = entry.get("symbol", "Unknown")
    forecast = entry.get("forecast") or "Unavailable"
    confidence = entry.get("confidence_score")
    confidence_display = "Unavailable"
    if isinstance(confidence, (int, float)):
        confidence_display = f"{float(confidence):.2f}"
    elif isinstance(confidence, str) and confidence.strip():
        confidence_display = confidence.strip()

    log_lines = [
        "\n=== Stock Analysis Run ===",
        f"Run Date: {timestamp}",
        f"- Stock: {symbol}",
        f"- Forecast: {forecast}",
        f"- Confidence: {confidence_display}",
    ]

    try:
        with LOG_FILE_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write("\n".join(log_lines) + "\n")
    except OSError:
        LOGGER.exception("Failed to write run log entry for %s", symbol)


def _confidence_sort_key(result: Dict[str, object]) -> Tuple[bool, float]:
    """Produce a sorting key that ranks higher confidence scores first."""
    score = result.get("confidence_score")
    if isinstance(score, (int, float)):
        return True, float(score)
    return False, float("-inf")


def _collect_tool_insights(symbol: str) -> Dict[str, Dict[str, object]]:
    """Collect raw outputs from the registered tools so UIs can surface structured insights."""
    insights: Dict[str, Dict[str, object]] = {}
    for key, tool in (
        ("news", NewsAndBuzzTool),
        ("technicals", VolumeAndTechnicalsTool),
        ("events", CorporateEventsTool),
    ):
        try:
            insights[key] = tool(symbol)
        except Exception as exc:  # pragma: no cover - best-effort logging
            LOGGER.warning("Failed to gather %s insights for %s: %s", key, symbol, exc)
            insights[key] = {"error": str(exc)}
    return insights


def run_stock_analysis(
    symbols: List[str],
    client: Optional[OpenAI] = None,
) -> List[Dict[str, object]]:
    """Run the assistant workflow for the requested symbols and return sorted results."""
    if not symbols:
        return []

    if client is None:
        api_key = None
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.is_file():
            with env_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")
        local_client = OpenAI(api_key=api_key) if api_key else OpenAI()
    else:
        local_client = client
    assistant = create_assistant(local_client)
    tool_dispatch = {
        "NewsAndBuzzTool": NewsAndBuzzTool,
        "VolumeAndTechnicalsTool": VolumeAndTechnicalsTool,
        "CorporateEventsTool": CorporateEventsTool,
    }

    results: List[Dict[str, object]] = []
    for symbol in symbols:
        entry: Dict[str, object] = {"symbol": symbol}
        LOGGER.info("Analyzing %s", symbol)
        try:
            thread = local_client.beta.threads.create()

            local_client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Please analyze the stock: {symbol}",
            )

            run = local_client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id,
            )

            status = _wait_for_run_completion(local_client, thread.id, run.id, tool_dispatch)
            if status != "completed":
                entry["error"] = f"Assistant run ended with status: {status}"
            else:
                messages = local_client.beta.threads.messages.list(thread_id=thread.id)
                response_text = _render_assistant_response(messages.data)
                entry["response_text"] = response_text
                
                # Log the full response for debugging
                LOGGER.info("Full assistant response for %s:\n%s", symbol, response_text[:500])
                
                entry["confidence_score"] = _extract_confidence_score(response_text)
                entry["forecast"] = _extract_forecast(response_text)
                
                # Log what was extracted
                LOGGER.info("Extracted for %s - Confidence: %s, Forecast: %s", 
                           symbol, entry["confidence_score"], entry["forecast"])
        except Exception as exc:  # pragma: no cover - best-effort logging
            LOGGER.exception("An error occurred while processing %s", symbol)
            entry["error"] = str(exc)

        if "error" not in entry:
            entry["tool_insights"] = _collect_tool_insights(symbol)
        else:
            entry["tool_insights"] = {}

        _append_run_log(entry)
        results.append(entry)

    for result in results:
        if "confidence_score" not in result:
            response_text = result.get("response_text") or ""
            result["confidence_score"] = _extract_confidence_score(response_text)
        if "forecast" not in result:
            response_text = result.get("response_text") or ""
            result["forecast"] = _extract_forecast(response_text)

    results.sort(key=_confidence_sort_key, reverse=True)
    return results


__all__ = ["run_stock_analysis", "parse_symbols"]
