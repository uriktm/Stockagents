"""Command-line interface for running Stockagents analyses."""

from __future__ import annotations

import argparse
import logging
from typing import List

from stockagents.core import evaluate_run_history, parse_symbols, run_stock_analysis


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Run the Stockagents assistant for one or more stocks.",
    )
    parser.add_argument(
        "--stocks",
        help="Comma-separated list of stock symbols to analyze (e.g., 'AAPL,MSFT,TSLA').",
    )
    parser.add_argument(
        "--evaluate-history",
        action="store_true",
        help="Review run_history.log against realised market data and update the log with results.",
    )
    parser.add_argument(
        "--movement-threshold",
        type=float,
        default=0.5,
        help="Minimum daily percent change to consider a move as up or down when scoring history (default: 0.5).",
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
    if args.evaluate_history:
        summary = evaluate_run_history(
            threshold=max(args.movement_threshold, 0.0),
            update_file=True,
        )
        if not summary.results:
            print("run_history.log is empty – nothing to evaluate.")
            return 0

        print("\n=== Run History Evaluation ===")
        for result in summary.results:
            symbol_display = result.symbol or "?"
            run_date_display = result.run_date.isoformat() if result.run_date else "Unknown date"
            print(f"\n--- {symbol_display} ({run_date_display}) ---")
            if result.forecast:
                print(f"Forecast: {result.forecast}")
            print(result.movement_line())
            print(result.outcome_line())

        print(
            f"\nUpdated {summary.updated_entries} entr"
            f"{'ies' if summary.updated_entries != 1 else 'y'} in {summary.log_path.name}."
        )
        return 0

    symbols = parse_symbols(args.stocks or "")
    if not symbols:
        print(
            "No valid stock symbols were provided. Pass a comma-separated list via --stocks, "
            "or use --evaluate-history to score past runs."
        )
        return 1

    results = run_stock_analysis(symbols)
    return display_results(results)


__all__ = ["main", "build_parser", "display_results"]
