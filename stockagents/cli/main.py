"""Command-line interface for running Stockagents analyses."""

from __future__ import annotations

import argparse
import logging
from typing import List

from stockagents.core import parse_symbols, run_stock_analysis


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Run the Stockagents assistant for one or more stocks.",
    )
    parser.add_argument(
        "--stocks",
        required=True,
        help="Comma-separated list of stock symbols to analyze (e.g., 'AAPL,MSFT,TSLA').",
    )
    return parser


def display_results(results: List[dict]) -> int:
    """Render assistant responses to stdout and return an exit code."""
    if not results:
        print("No analysis results were generated.")
        return 1

    exit_code = 0
    print("\n=== Stock Analysis Results (sorted by confidence) ===")
    for result in results:
        symbol = result.get("symbol", "?")
        error_message = result.get("error")
        if error_message:
            print(f"\n--- {symbol} ---")
            print(f"Analysis failed: {error_message}")
            exit_code = 1
            continue

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


def main() -> int:
    """Entry point invoked by ``python -m stockagents.cli`` or ``python main.py``."""
    logging.basicConfig(level=logging.INFO)
    parser = build_parser()
    args = parser.parse_args()
    symbols = parse_symbols(args.stocks)
    if not symbols:
        print("No valid stock symbols were provided. Please pass a comma-separated list via --stocks.")
        return 1

    results = run_stock_analysis(symbols)
    return display_results(results)


__all__ = ["main", "build_parser", "display_results"]
