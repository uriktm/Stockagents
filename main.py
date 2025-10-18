"""Command-line entry point for running stock analyses with the Stockagents assistant."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from typing import Dict, Iterable, List, Optional

from openai import OpenAI

from agent_setup import create_assistant
from tools import CorporateEventsTool, NewsAndBuzzTool, VolumeAndTechnicalsTool


LOGGER = logging.getLogger(__name__)


def _parse_symbols(raw: str) -> List[str]:
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
    tool_dispatch: Dict[str, callable],
    poll_interval: float = 1.0,
) -> str:
    """Polls the Assistants API until the run reaches a terminal state."""
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
                        outputs.append({"tool_call_id": getattr(call, "id", ""), "output": json.dumps({"error": "Unknown tool"})})
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
                    outputs.append({
                        "tool_call_id": getattr(call, "id", ""),
                        "output": json.dumps(tool_output if tool_output is not None else {}),
                    })
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
    """Extracts the latest assistant message from the thread messages."""
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
    """Extracts the numeric confidence score from the assistant's response."""
    if not raw_response:
        return None

    match = re.search(r"confidence\s*score[^0-9]*([0-9]+(?:\.[0-9]+)?)", raw_response, re.IGNORECASE)
    if not match:
        return None

    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def _confidence_sort_key(result: Dict[str, object]) -> tuple[bool, float]:
    """Produces a sorting key that ranks higher confidence scores first."""
    score = result.get("confidence_score")
    if isinstance(score, (int, float)):
        return True, float(score)
    return False, float("-inf")


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Run the Stockagents assistant for one or more stocks.")
    parser.add_argument(
        "--stocks",
        required=True,
        help="Comma-separated list of stock symbols to analyze (e.g., 'AAPL,MSFT,TSLA').",
    )

    args = parser.parse_args()
    symbols = _parse_symbols(args.stocks)
    if not symbols:
        print("No valid stock symbols were provided. Please pass a comma-separated list via --stocks.")
        return 1

    client = OpenAI()
    assistant = create_assistant(client)
    tool_dispatch = {
        "NewsAndBuzzTool": NewsAndBuzzTool,
        "VolumeAndTechnicalsTool": VolumeAndTechnicalsTool,
        "CorporateEventsTool": CorporateEventsTool,
    }

    exit_code = 0
    results: List[Dict[str, object]] = []
    for symbol in symbols:
        print(f"\n=== Analyzing {symbol} ===")
        try:
            thread = client.beta.threads.create()

            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Please analyze the stock: {symbol}",
            )

            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id,
            )

            status = _wait_for_run_completion(client, thread.id, run.id, tool_dispatch)
            if status != "completed":
                print(f"Assistant run for {symbol} ended with status: {status}")
                exit_code = 1
                continue

            messages = client.beta.threads.messages.list(thread_id=thread.id)
            response_text = _render_assistant_response(messages.data)
            results.append({"symbol": symbol, "response_text": response_text})
        except Exception as exc:  # pragma: no cover - best-effort logging
            print(f"An error occurred while processing {symbol}: {exc}")
            exit_code = 1

    if results:
        for result in results:
            result["confidence_score"] = _extract_confidence_score(result.get("response_text") or "")

        results.sort(key=_confidence_sort_key, reverse=True)

        print("\n=== Stock Analysis Results (sorted by confidence) ===")
        for result in results:
            symbol = result["symbol"]
            response_text = (result.get("response_text") or "").strip() or "(No assistant response was generated.)"
            confidence_score = result.get("confidence_score")

            print(f"\n--- {symbol} ---")
            if confidence_score is not None:
                numeric_score = float(confidence_score)
                if numeric_score.is_integer():
                    score_display = int(numeric_score)
                else:
                    score_display = round(numeric_score, 2)
                print(f"Confidence Score: {score_display}")
            else:
                print("Confidence Score: Not found")
            print(response_text)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
