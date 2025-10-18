"""Assistant setup for the Stockagents project."""

from __future__ import annotations

from typing import Any, Dict

from openai import OpenAI

from tools import CorporateEventsTool, NewsAndBuzzTool, VolumeAndTechnicalsTool

_SYSTEM_PROMPT = (
    "You are a senior quantitative financial analyst. Your goal is to identify stocks "
    "with the potential for a positive abnormal event today. An 'abnormal event' can be "
    "strong news sentiment, unusual media buzz, higher-than-average trading volume, or a "
    "clear technical signal. Use all available tools to gather comprehensive information "
    "for each stock. For each stock, you must provide:\n"
    "1.  **Forecast:** What is the expected abnormal event (e.g., 'Positive price movement', "
    "'High media attention').\n"
    "2.  **Confidence Score:** From 1 to 10, how confident are you in your forecast.\n"
    "3.  **Causal Explanation (XAI):** Clearly detail in bullet points the key factors that "
    "led to your conclusion. You must cite the specific data (e.g., 'Trading volume is 150% "
    "above average', '12 news articles in the last 24 hours')."
)


def _build_function_tool_schema(func) -> Dict[str, Any]:
    """Helper to build the function tool schema for the Assistants API."""
    description = func.__doc__.strip() if func.__doc__ else ""
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_symbol": {
                        "type": "string",
                        "description": "A valid stock ticker symbol (e.g., 'AAPL').",
                    }
                },
                "required": ["stock_symbol"],
            },
        },
    }


def create_assistant():
    """Create and return the AlphaSynthesizerAgent assistant."""
    client = OpenAI()
    assistant = client.beta.assistants.create(
        name="AlphaSynthesizerAgent",
        instructions=_SYSTEM_PROMPT,
        model="gpt-4o-mini",
        tools=[
            _build_function_tool_schema(NewsAndBuzzTool),
            _build_function_tool_schema(VolumeAndTechnicalsTool),
            _build_function_tool_schema(CorporateEventsTool),
        ],
    )
    return assistant
