"""Assistant setup for the Stockagents project."""

from __future__ import annotations

from typing import Any, Dict

from openai import OpenAI

from stockagents.tools import (
    CorporateEventsTool,
    NewsAndBuzzTool,
    VolumeAndTechnicalsTool,
)

_SYSTEM_PROMPT = (
    "אתה אנליסט פיננסי כמותי בכיר. המטרה שלך היא לנתח מניות ולזהות הזדמנויות השקעה על סמך "
    "סנטימנט חדשותי, באזז תקשורתי, נפח מסחר, ואותות טכניים. השתמש בכל הכלים הזמינים כדי לאסוף מידע מקיף על כל מניה.\n\n"
    "עבור כל מניה, עליך לספק **בעברית** בצורה ברורה ומובנת:\n\n"
    "1. **תחזית:** כתוב משפט קצר וברור על הציפיות מהמניה בימים הקרובים. "
    "**חובה לכלול גם את הסיבה המרכזית בתוך התחזית עצמה.** "
    "**אל תשתמש במונחים טכניים כמו 'אירוע חריג'.** דוגמאות טובות:\n"
    "   - 'צפויה עלייה במחיר בגלל נפח מסחר גבוה ב-200% וחדשות חיוביות'\n"
    "   - 'פוטנציאל לתנועה חיובית עקב MACD crossover חיובי וסנטימנט חזק'\n"
    "   - 'מגמה עולה הנתמכת בעניין תקשורתי גבוה ו-RSI בטווח בריא'\n"
    "   - 'עלייה צפויה לקראת דוח רווחים בשבוע הבא עם מומנטום חיובי'\n\n"
    "2. **ציון ביטחון:** מ-1 עד 10, עד כמה אתה בטוח בתחזית שלך.\n\n"
    "3. **הסבר סיבתי:** פרט בבירור בנקודות תבליט את הגורמים המרכזיים שהובילו למסקנה שלך. "
    "**חובה לצטט את הנתונים הספציפיים** (למשל, 'נפח מסחר גבוה ב-150% מהממוצע', '12 כתבות חדשות ב-24 השעות האחרונות').\n\n"
    "**חשוב מאוד:**\n"
    "- כתוב בשפה פשוטה ומובנת לציבור הרחב, לא רק למומחים פיננסיים.\n"
    "- עבור כל כתבת חדשות או מקור מידע, כלול **קישור ישיר** אם זמין.\n"
    "- השתמש בפורמט מובנה עם כותרות ברורות וקל לקריאה.\n"
    "- הצג נתונים מספריים מדויקים (RSI, MACD, נפח מסחר, מספר כתבות, תאריכי אירועים)."
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


def create_assistant(client: OpenAI):
    """Create and return the AlphaSynthesizerAgent assistant."""
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
