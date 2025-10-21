import html
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import streamlit as st

from stockagents import parse_symbols, run_stock_analysis


def _format_score(score: object) -> tuple[str, float | None]:
    if isinstance(score, (int, float)):
        rounded = round(float(score), 1)
        return (str(rounded).rstrip("0").rstrip(".") if "." in str(rounded) else str(int(rounded)), float(score))
    return ("—", None)


def _score_color(score: float | None) -> str:
    if score is None:
        return "#6b7280"
    if score >= 7.5:
        return "#16a34a"
    if score >= 5:
        return "#facc15"
    return "#ef4444"


def _extract_forecast(text: str) -> str:
    lines: Iterable[str] = (line.strip() for line in text.splitlines())
    for line in lines:
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("forecast") or lowered.startswith("תחזית") or "**תחזית:**" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip().strip("*").strip()
            return line
    # If no explicit forecast line found, return first non-empty meaningful line
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and len(line) > 10:
            return line
    return "לא נמצאה תחזית מפורשת."


def _market_session_status() -> tuple[str, str]:
    """Determines the current US market session (Eastern Time)."""
    try:
        eastern_now = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return "סטטוס שוק: לא זמין", "#6b7280"

    weekday = eastern_now.weekday()
    current_time = eastern_now.time()

    pre_market_start = time(4, 0)
    market_open = time(9, 30)
    market_close = time(16, 0)
    after_hours_end = time(20, 0)

    if weekday >= 5:
        return "סטטוס שוק: סגור (סוף שבוע)", "#6b7280"
    if pre_market_start <= current_time < market_open:
        return "סטטוס שוק: פרה-מרקט פתוח", "#fbbf24"
    if market_open <= current_time < market_close:
        return "סטטוס שוק: מסחר פעיל", "#22c55e"
    if market_close <= current_time < after_hours_end:
        return "סטטוס שוק: אפטר-מרקט פתוח", "#60a5fa"
    return "סטטוס שוק: סגור", "#6b7280"


def _render_points(title: str, icon: str, points: list[str]) -> str:
    if not points:
        return ""
    items = "".join(
        "<li class='info-section__item'>{}</li>".format(
            point if point.startswith("<a ") else html.escape(point)
        )
        for point in points
    )
    return (
        "<div class='info-section'>"
        f"<div class='info-section__title'>{icon} {html.escape(title)}</div>"
        f"<ul class='info-section__list'>{items}</ul>"
        "</div>"
    )


def _forecast_tone(text: str) -> dict:
    normalized = (text or "").replace("**", "").lower()
    positive_keywords = [
        "עלייה",
        "עליה",
        "חיוב",
        "תנועה חיובית",
        "bullish",
        "upside",
        "התאוששות",
        "צמיחה",
        "עליות",
        "מגמה עולה",
        "support",
    ]
    negative_keywords = [
        "ירידה",
        "ירידות",
        "שלילי",
        "לחץ",
        "bearish",
        "downside",
        "תנועה שלילית",
        "sell-off",
        "מימוש",
        "מגמה יורדת",
        "decline",
    ]

    tone = "neutral"
    for keyword in negative_keywords:
        if keyword in normalized:
            tone = "negative"
            break
    else:
        for keyword in positive_keywords:
            if keyword in normalized:
                tone = "positive"
                break

    tone_styles = {
        "positive": {
            "label": "מגמה חיובית",
            "icon": "▲",
            "text_color": "#16a34a",
            "badge_bg": "rgba(22, 163, 74, 0.18)",
            "badge_border": "#16a34a",
        },
        "negative": {
            "label": "מגמה שלילית",
            "icon": "▼",
            "text_color": "#ef4444",
            "badge_bg": "rgba(239, 68, 68, 0.18)",
            "badge_border": "#ef4444",
        },
        "neutral": {
            "label": "מגמה ניטרלית",
            "icon": "➜",
            "text_color": "#fbbf24",
            "badge_bg": "rgba(251, 191, 36, 0.18)",
            "badge_border": "#fbbf24",
        },
    }
    return tone_styles[tone]


def _build_card(result: dict) -> str:
    symbol = result.get("symbol", "")
    score_display, numeric_score = _format_score(result.get("confidence_score"))
    forecast = _extract_forecast(result.get("response_text", "") or "") or "לא נמצאה תחזית מפורשת."
    forecast_safe = html.escape(forecast)
    color = _score_color(numeric_score)
    insights = result.get("tool_insights") or {}
    news = insights.get("news") or {}
    technicals = insights.get("technicals") or {}
    events = insights.get("events") or {}

    tone = _forecast_tone(forecast)
    badge_html = (
        "<div class='tone-badge-wrapper'>"
        f"<span class='tone-badge' style='border-color:{tone['badge_border']}; background:{tone['badge_bg']}; color:{tone['badge_border']}'>"
        f"{tone['icon']} {tone['label']}"
        "</span>"
        "</div>"
    )

    news_points: list[str] = []
    narrative = news.get("narrative")
    if isinstance(narrative, str) and narrative and narrative.lower() != "insufficient data":
        news_points.append(f"נרטיב: {narrative}")

    source_breakdown = news.get("source_breakdown") or []
    source_count = news.get("source_count")
    if source_breakdown:
        breakdown_text = ", ".join(
            f"{html.escape(str(item.get('source', '')))} ({int(item.get('count', 0))})"
            for item in source_breakdown
            if item
        )
        if isinstance(source_count, int) and source_count > 0:
            news_points.append(
                f"מספר מקורות עצמאיים: {source_count} ({breakdown_text})"
            )
        else:
            news_points.append(f"מקורות חדשות: {breakdown_text}")

    sentiment_score = news.get("sentiment_score")
    if isinstance(sentiment_score, (int, float)):
        sentiment_text = ""
        if sentiment_score >= 0.3:
            sentiment_text = "(חיובי מאוד)"
        elif sentiment_score >= 0:
            sentiment_text = "(חיובי קל)"
        elif sentiment_score >= -0.3:
            sentiment_text = "(שלילי קל)"
        else:
            sentiment_text = "(שלילי מאוד)"
        news_points.append(f"ציון סנטימנט: {round(float(sentiment_score), 2)} {sentiment_text}")
    
    buzz = news.get("buzz_factor")
    if isinstance(buzz, (int, float)) and buzz > 0:
        buzz_val = round(float(buzz), 2)
        buzz_text = ""
        if buzz_val > 2.0:
            buzz_text = "(חשיפה גבוהה)"
        elif buzz_val >= 1.0:
            buzz_text = "(נורמלי)"
        else:
            buzz_text = "(חשיפה נמוכה)"
        news_points.append(f"חשיפה תקשורתית: x{buzz_val} {buzz_text}")
    
    article_links = news.get("article_links", [])
    if article_links and isinstance(article_links, list):
        for link_info in article_links[:3]:
            if isinstance(link_info, dict):
                title = link_info.get("title", "")
                url = link_info.get("url", "")
                source_label = link_info.get("source")
                if title and url:
                    truncated_title = title if len(title) <= 60 else f"{title[:60]}..."
                    prefix = f"[{source_label}] " if source_label else ""
                    display_text = html.escape(f"{prefix}{truncated_title}")
                    news_points.append(
                        f'<a href="{html.escape(url)}" target="_blank" style="color:#60a5fa;">{display_text}</a>'
                    )

    technical_points: list[str] = []
    signal = technicals.get("technical_signal")
    if isinstance(signal, str) and signal:
        technical_points.append(f"איתות מרכזי: {signal}")
    
    rsi = technicals.get("rsi")
    if isinstance(rsi, (int, float)):
        rsi_val = round(float(rsi), 2)
        rsi_text = ""
        if rsi_val < 30:
            rsi_text = "(מכירה יתר - פוטנציאל לעלייה)"
        elif rsi_val > 70:
            rsi_text = "(קנייה יתר - פוטנציאל לירידה)"
        else:
            rsi_text = "(טווח נורמלי)"
        technical_points.append(f"RSI: {rsi_val} {rsi_text}")
    
    volume_ratio = technicals.get("volume_spike_ratio")
    if isinstance(volume_ratio, (int, float)) and volume_ratio > 0:
        vol_val = round(float(volume_ratio), 2)
        vol_text = ""
        if vol_val > 2.0:
            vol_text = "(נפח גבוה מאוד - עניין מוגבר)"
        elif vol_val >= 1.0:
            vol_text = "(נורמלי)"
        else:
            vol_text = "(נפח נמוך)"
        technical_points.append(f"נפח מסחר: x{vol_val} {vol_text}")

    event_points: list[str] = []
    earnings_date = events.get("upcoming_earnings_date")
    if isinstance(earnings_date, str) and earnings_date:
        event_points.append(f"דוח רבעוני צפוי ב-{earnings_date}")
    elif events.get("has_upcoming_event"):
        event_points.append("קיים אירוע תאגידי קרוב")

    sections = "".join(
        part
        for part in (
            _render_points("חדשות וסנטימנט", "📰", news_points),
            _render_points("ניתוח טכני", "📈", technical_points),
            _render_points("אירועים קרובים", "🗓️", event_points),
        )
        if part
    )

    response_text = result.get("response_text") or "(אין ניתוח מפורט מהסוכן.)"
    details = html.escape(response_text)

    sections_html = f"<div class='analysis-card__sections'>{sections}</div>" if sections else ""

    return (
        "<div class='analysis-card'>"
        "<div class='analysis-card__header'>"
        "<div class='analysis-card__summary'>"
        f"<div class='analysis-card__symbol'>{html.escape(symbol)}</div>"
        f"{badge_html}"
        f"<div class='analysis-card__forecast'>תחזית: <span style='color:{tone['text_color']};'>{forecast_safe}</span></div>"
        "</div>"
        "<div class='analysis-card__score'>"
        "<div class='score-chip__label'>רמת ביטחון של המודל</div>"
        f"<div class='score-chip' style='background:{color};'>"
        f"<div class='score-chip__value'>{score_display}</div>"
        "<div class='score-chip__suffix'>/10</div>"
        "</div>"
        "</div>"
        "</div>"
        f"{sections_html}"
        "<details class='analysis-card__details'>"
        "<summary>הצג את הניתוח המלא</summary>"
        f"<pre>{details}</pre>"
        "</details>"
        "</div>"
    )


ROOT_DIR = Path(__file__).resolve().parent

_TEST_SUITES = [
    {
        "key": "all",
        "label": "כל הבדיקות (pytest)",
        "description": "מריץ את כל הבדיקות האוטומטיות בספריית tests לקבלת תמונת מצב מלאה.",
        "command": [sys.executable, "-m", "pytest"],
    },
    {
        "key": "tools",
        "label": "בדיקות כלי האיסוף המשולבים",
        "description": "בודק את שכבת התזמור של הכלים דרך tests/test_tools.py.",
        "command": [sys.executable, "-m", "pytest", "tests/test_tools.py"],
    },
    {
        "key": "analyst",
        "label": "בדיקות AnalystRatingsTool",
        "description": "ווידוא חישובי קונצנזוס ומחירי יעד (tests/test_analyst_ratings_tool.py).",
        "command": [sys.executable, "-m", "pytest", "tests/test_analyst_ratings_tool.py"],
    },
    {
        "key": "history",
        "label": "בדיקות היסטוריית הריצות",
        "description": "בדיקות שמאמתות את ניהול הלוגים והיסטוריית הריצות (tests/test_history.py).",
        "command": [sys.executable, "-m", "pytest", "tests/test_history.py"],
    },
    {
        "key": "social_unit",
        "label": "בדיקות SocialSentimentTool",
        "description": "בודק את שכבת הסנטימנט החברתי ברמת היחידה (tests/test_social_sentiment_tool.py).",
        "command": [sys.executable, "-m", "pytest", "tests/test_social_sentiment_tool.py"],
    },
    {
        "key": "social_integration",
        "label": "בדיקות אינטגרציית סנטימנט חברתי",
        "description": "הרצה מלאה מול ה-API (מדלג אוטומטית אם חסרים Credentials) דרך tests/test_social_sentiment_integration.py.",
        "command": [sys.executable, "-m", "pytest", "tests/test_social_sentiment_integration.py"],
    },
    {
        "key": "quick_script",
        "label": "Quick Test Analysis Script",
        "description": "סקריפט עומק שמפעיל run_stock_analysis עם לוגים מפורטים (quick_test_analysis.py).",
        "command": [sys.executable, "quick_test_analysis.py"],
    },
    {
        "key": "simple_script",
        "label": "Simple Smoke Test",
        "description": "בדיקת עשן בסיסית שמוודאת שהניתוח הבסיסי פועל (test_simple.py).",
        "command": [sys.executable, "test_simple.py"],
    },
]


def _run_test_suite(command: list[str]) -> tuple[int, str]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(ROOT_DIR),
    )
    output, _ = process.communicate()
    return process.returncode, output


def _format_command(command: list[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in command)


st.set_page_config(page_title="Stockagents Dashboard", layout="wide")

# Hebrew RTL styling
st.markdown("""
<style>
    :root {
        color-scheme: dark;
    }

    * {
        font-family: 'Rubik', 'Assistant', 'Segoe UI', Tahoma, Arial, sans-serif;
    }

    .stApp {
        background: radial-gradient(120% 120% at 78% 0%, rgba(30, 64, 175, 0.55) 0%, #020617 60%, #000000 100%);
        color: #f8fafc;
    }

    .main .block-container {
        direction: rtl;
        text-align: right;
        max-width: 1150px;
        padding-top: 2.6rem;
        padding-bottom: 4rem;
    }

    .stTextInput > div > div > input {
        direction: rtl;
        text-align: right;
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.32);
        border-radius: 14px;
        padding: 0.75rem 1rem;
        color: #f8fafc;
    }

    .stTextInput > div > div > input:focus {
        border-color: #38bdf8;
        box-shadow: 0 0 0 1px #38bdf8;
    }

    .stTextInput label {
        direction: rtl;
        text-align: right;
        color: #cbd5f5;
        font-weight: 600;
    }

    .stButton > button {
        direction: rtl;
        border-radius: 12px;
        border: none;
        padding: 0.65rem 1.9rem;
        font-weight: 700;
        background: linear-gradient(135deg, #38bdf8, #34d399);
        color: #041424;
        box-shadow: 0 16px 32px rgba(56, 189, 248, 0.25);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 20px 36px rgba(52, 211, 153, 0.28);
    }

    .stButton > button:focus {
        border: none;
        outline: none;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.45);
    }

    p, h1, h2, h3, h4, h5, h6, label, div {
        direction: rtl;
        text-align: right;
    }

    .stAlert, .stAlert > div, .stSpinner > div, .stMarkdown {
        direction: rtl;
        text-align: right;
    }

    .hero-card {
        background: linear-gradient(135deg, rgba(30, 64, 175, 0.48), rgba(56, 189, 248, 0.35), rgba(34, 197, 94, 0.3));
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 28px;
        padding: 34px 36px;
        color: #f8fafc;
        display: flex;
        flex-wrap: wrap;
        gap: 28px;
        justify-content: space-between;
        box-shadow: 0 25px 60px rgba(15, 23, 42, 0.55);
    }

    .hero-card__text {
        max-width: 620px;
        display: flex;
        flex-direction: column;
        gap: 18px;
    }

    .hero-card__text h1 {
        font-size: 2.35rem;
        margin: 0;
        letter-spacing: 0.02em;
    }

    .hero-card__text p {
        margin: 0;
        color: #e2e8f0;
        line-height: 1.6;
        font-size: 1.05rem;
    }

    .hero-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 6px;
    }

    .hero-chip {
        background: rgba(15, 23, 42, 0.45);
        border: 1px solid rgba(148, 163, 184, 0.35);
        color: #f8fafc;
        padding: 0.45rem 0.9rem;
        border-radius: 999px;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .hero-card__status {
        display: flex;
        flex-direction: column;
        gap: 18px;
        align-items: flex-start;
        justify-content: center;
        min-width: 220px;
    }

    .hero-card__status-label {
        font-size: 0.85rem;
        letter-spacing: 0.05em;
        color: #cbd5f5;
    }

    .hero-card__status-chip {
        padding: 0.6rem 1.2rem;
        border-radius: 999px;
        font-weight: 800;
        font-size: 1.05rem;
        color: #020617;
        box-shadow: 0 18px 42px rgba(14, 165, 233, 0.35);
    }

    .hero-card__status-note {
        color: #e0f2fe;
        font-size: 0.9rem;
        line-height: 1.5;
    }

    .input-hint {
        margin: 28px 0 10px;
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 18px;
        padding: 16px 20px;
        color: #e2e8f0;
        font-size: 0.95rem;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .input-hint strong {
        color: #f8fafc;
        font-size: 1.05rem;
    }

    .input-hint span {
        color: #cbd5f5;
        font-size: 0.88rem;
    }

    .tone-badge-wrapper {
        display: inline-flex;
        align-items: center;
    }

    .tone-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 0.45rem 1.1rem;
        border-radius: 999px;
        border: 1px solid;
        font-weight: 700;
        font-size: 0.95rem;
        background: rgba(15, 23, 42, 0.6);
    }

    .analysis-card {
        background: linear-gradient(165deg, rgba(15, 23, 42, 0.92), rgba(2, 6, 23, 0.92));
        border: 1px solid rgba(30, 64, 175, 0.28);
        border-radius: 24px;
        padding: 28px;
        margin-bottom: 26px;
        color: #f8fafc;
        box-shadow: 0 22px 50px rgba(2, 6, 23, 0.65);
    }

    .analysis-card__header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 24px;
        flex-wrap: wrap;
    }

    .analysis-card__summary {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .analysis-card__symbol {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .analysis-card__forecast {
        font-size: 1.05rem;
        color: #e2e8f0;
        font-weight: 600;
    }

    .analysis-card__score {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }

    .score-chip__label {
        font-size: 0.85rem;
        color: #cbd5f5;
        letter-spacing: 0.03em;
    }

    .score-chip {
        width: 132px;
        height: 132px;
        border-radius: 26px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        color: #041424;
        font-weight: 800;
        box-shadow: 0 18px 40px rgba(59, 130, 246, 0.35);
    }

    .score-chip__value {
        font-size: 3.3rem;
        line-height: 1;
    }

    .score-chip__suffix {
        font-size: 1rem;
        font-weight: 700;
        margin-top: 2px;
    }

    .analysis-card__sections {
        margin-top: 24px;
        display: grid;
        gap: 18px;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    }

    .info-section {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 18px;
        padding: 18px 20px;
        min-height: 160px;
    }

    .info-section__title {
        font-weight: 700;
        font-size: 1.05rem;
        margin-bottom: 10px;
        color: #c4d4ff;
    }

    .info-section__list {
        margin: 0;
        padding-right: 1.1rem;
        list-style-position: inside;
        display: flex;
        flex-direction: column;
        gap: 8px;
        color: #e5e7eb;
    }

    .info-section__item {
        font-size: 0.95rem;
        line-height: 1.6;
    }

    .info-section__item a {
        color: #38bdf8;
        text-decoration: none;
    }

    .info-section__item a:hover {
        text-decoration: underline;
    }

    .analysis-card__details {
        margin-top: 26px;
        color: #f3f4f6;
    }

    .analysis-card__details summary {
        cursor: pointer;
        font-weight: 700;
        color: #93c5fd;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    .analysis-card__details summary::-webkit-details-marker {
        display: none;
    }

    .analysis-card__details summary::after {
        content: '▼';
        font-size: 0.75rem;
        color: #38bdf8;
        transition: transform 0.2s ease;
    }

    .analysis-card__details[open] summary::after {
        transform: rotate(180deg);
    }

    .analysis-card__details pre {
        white-space: pre-wrap;
        font-family: 'Rubik', 'Assistant', 'Segoe UI', sans-serif;
        background: rgba(8, 25, 48, 0.85);
        border-radius: 16px;
        padding: 18px;
        margin-top: 14px;
        color: #f1f5f9;
        border: 1px solid rgba(59, 130, 246, 0.35);
    }

    @media (max-width: 768px) {
        .hero-card {
            padding: 26px;
        }

        .hero-card__text h1 {
            font-size: 1.8rem;
        }

        .analysis-card {
            padding: 22px;
        }

        .score-chip {
            width: 120px;
            height: 120px;
        }
    }
</style>
""", unsafe_allow_html=True)

if "analysis_results" not in st.session_state:
    st.session_state["analysis_results"] = None
if "analysis_error" not in st.session_state:
    st.session_state["analysis_error"] = None
if "status_message" not in st.session_state:
    st.session_state["status_message"] = ""
if "status_level" not in st.session_state:
    st.session_state["status_level"] = "info"
if "analysis_in_progress" not in st.session_state:
    st.session_state["analysis_in_progress"] = False
if "analysis_pending_symbols" not in st.session_state:
    st.session_state["analysis_pending_symbols"] = None
if "test_results" not in st.session_state:
    st.session_state["test_results"] = {}
if "test_summary" not in st.session_state:
    st.session_state["test_summary"] = None

analysis_tab, health_tab = st.tabs(["ניתוח מניות", "בריאות המערכת ובדיקות"])

with analysis_tab:
    status_text, status_color = _market_session_status()
    hero_html = f"""
    <div class='hero-card'>
        <div class='hero-card__text'>
            <h1>ממשק ניתוח מניות - Stockagents</h1>
            <p>
                לוח הבקרה החכם שמרכז עבורך תחזיות, חדשות, ניתוחים טכניים ואירועים תאגידיים - הכל בעברית,
                עם דגש על הדברים שבאמת חשוב לדעת לפני קבלת החלטה.
            </p>
            <div class='hero-chips'>
                <span class='hero-chip'>מעקב חדשות בזמן אמת</span>
                <span class='hero-chip'>איתותים טכניים</span>
                <span class='hero-chip'>אירועים תאגידיים קרובים</span>
            </div>
        </div>
        <div class='hero-card__status'>
            <div class='hero-card__status-label'>סטטוס שוק</div>
            <div class='hero-card__status-chip' style='background:{status_color};'>
                {html.escape(status_text)}
            </div>
            <div class='hero-card__status-note'>
                בדוק את מצב השוק לפני ניתוח - חלק מהאיתותים עובדים טוב יותר בזמני מסחר פעילים.
            </div>
        </div>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

    st.markdown(
        """
        <div class='input-hint'>
            <strong>איך להתחיל?</strong>
            <span>הקלד סימולי מניות באנגלית, מופרדים בפסיק, לדוגמה: <code>AAPL, MSFT, NVDA</code>.</span>
            <span>לחיצה על "נתח" תפעיל את הסוכן ותציג כרטיס תמציתי עם הסבר, מדדי סנטימנט וטכני וקישורים בולטים.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    input_description = "הזן רשימת מניות מופרדות בפסיק"
    symbols_input = st.text_input(input_description, placeholder="AAPL,MSFT,NVDA")
    trigger = st.button("נתח", disabled=st.session_state["analysis_in_progress"])
    status_placeholder = st.empty()
    results_container = st.container()

    if trigger and not st.session_state["analysis_in_progress"]:
        st.session_state["analysis_results"] = None
        st.session_state["analysis_error"] = None
        st.session_state["status_message"] = ""
        st.session_state["status_level"] = "info"
        symbols = parse_symbols(symbols_input)
        if not symbols:
            st.session_state["analysis_error"] = "נא להזין לפחות סמל בורסאי אחד תקף."
            st.session_state["analysis_in_progress"] = False
            st.session_state["analysis_pending_symbols"] = None
        else:
            st.session_state["analysis_in_progress"] = True
            st.session_state["analysis_pending_symbols"] = symbols
            st.session_state["status_message"] = "מנתח מניות... זה עשוי לקחת מספר דקות..."
            st.session_state["status_level"] = "info"
            st.rerun()

    pending_symbols = st.session_state.get("analysis_pending_symbols")
    if st.session_state["analysis_in_progress"] and pending_symbols:
        status_placeholder.info("מנתח מניות... זה עשוי לקחת מספר דקות...")
        results = None
        try:
            with st.spinner("מנתח מניות... זה עשוי לקחת מספר דקות..."):
                results = run_stock_analysis(pending_symbols)
        except Exception as exc:  # pragma: no cover - best-effort UI feedback
            st.session_state["analysis_error"] = str(exc)
            st.session_state["status_message"] = "הניתוח נכשל."
            st.session_state["status_level"] = "error"
        else:
            st.session_state["status_message"] = "הניתוח הושלם."
            st.session_state["status_level"] = "success"
            if not results:
                st.session_state["analysis_error"] = "לא התקבלו תוצאות ניתוח."
                st.session_state["analysis_results"] = None
            else:
                st.session_state["analysis_error"] = None
                st.session_state["analysis_results"] = results
        finally:
            st.session_state["analysis_in_progress"] = False
            st.session_state["analysis_pending_symbols"] = None

    message = st.session_state.get("status_message")
    level = st.session_state.get("status_level", "info")
    if message:
        getattr(status_placeholder, level)(message)

    error_message = st.session_state.get("analysis_error")
    results = st.session_state.get("analysis_results")

    if error_message:
        results_container.error(error_message)
    elif results:
        for result in results:
            if result.get("error"):
                results_container.error(f"{result.get('symbol', '')}: {result['error']}")
                continue
            card_html = _build_card(result)
        results_container.markdown(card_html, unsafe_allow_html=True)
    else:
        results_container.info("הזן מניות ולחץ \"נתח\" כדי להתחיל.")


with health_tab:
    st.header("מרכז בריאות המערכת והבדיקות")
    st.markdown(
        """
        מרכז זה מאפשר הפעלה ידנית של כלל הבדיקות על רכיבי Stockagents – בדיוק כפי שמתואר במסמך
        <code>SYSTEM_FLOW</code>. ניתן להריץ כל חבילה בנפרד כדי לבודד תקלות, או להפעיל את כולן יחד לקבלת תמונת מצב מלאה.
        """,
        unsafe_allow_html=True,
    )
    st.caption("כל בדיקה רצה בסביבת העבודה הנוכחית ומדפיסה את פלט הקונסולה המלא שלה להלן.")

    if st.button("הרץ את כל הבדיקות", key="run_all_tests"):
        total = len(_TEST_SUITES)
        passed = 0
        results_state = dict(st.session_state["test_results"])
        for suite in _TEST_SUITES:
            with st.spinner(f"מפעיל {suite['label']}..."):
                returncode, output = _run_test_suite(suite["command"])
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            results_state[suite["key"]] = {
                "returncode": returncode,
                "output": output,
                "timestamp": timestamp,
                "command": _format_command(suite["command"]),
            }
            if returncode == 0:
                passed += 1
        st.session_state["test_results"] = results_state
        st.session_state["test_summary"] = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "passed": passed,
        }

    summary = st.session_state.get("test_summary")
    if summary:
        summary_message = (
            f"עודכן לאחרונה ב-{summary['timestamp']} · {summary['passed']} מתוך {summary['total']} חבילות עברו בהצלחה"
        )
        if summary["passed"] == summary["total"]:
            st.success(summary_message)
        elif summary["passed"] == 0:
            st.error(summary_message)
        else:
            st.warning(summary_message)

    for suite in _TEST_SUITES:
        suite_container = st.container()
        with suite_container:
            st.subheader(suite["label"])
            st.markdown(suite["description"])
            cols = st.columns([1, 4])
            run_key = f"run_suite_{suite['key']}"
            run_clicked = cols[0].button("הרץ", key=run_key)
            cols[1].code(_format_command(suite["command"]), language="bash")

            if run_clicked:
                with st.spinner(f"מריץ {suite['label']}..."):
                    returncode, output = _run_test_suite(suite["command"])
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                results_state = dict(st.session_state["test_results"])
                results_state[suite["key"]] = {
                    "returncode": returncode,
                    "output": output,
                    "timestamp": timestamp,
                    "command": _format_command(suite["command"]),
                }
                st.session_state["test_results"] = results_state
                st.session_state["test_summary"] = {
                    "timestamp": timestamp,
                    "total": len(_TEST_SUITES),
                    "passed": sum(
                        1
                        for value in st.session_state["test_results"].values()
                        if value.get("returncode") == 0
                    ),
                }

            result = st.session_state["test_results"].get(suite["key"])
            if result:
                status_message = (
                    f"✅ הבדיקה עברה ({result['timestamp']})"
                    if result["returncode"] == 0
                    else f"❌ הבדיקה נכשלה ({result['timestamp']})"
                )
                status_func = st.success if result["returncode"] == 0 else st.error
                status_func(status_message)
                st.code(result["output"] or "(ללא פלט)", language="bash")
