import html
from datetime import datetime, time
from typing import Iterable
from zoneinfo import ZoneInfo

import streamlit as st

from main import _parse_symbols, run_stock_analysis


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
        f"<li style='margin-bottom:4px; direction:rtl; text-align:right;'>{point if point.startswith('<a ') else html.escape(point)}</li>"
        for point in points
    )
    return (
        f"<div style='margin-top:18px; direction:rtl; text-align:right;'>"
        f"<div style='font-weight:600; font-size:16px; margin-bottom:6px;'>{icon} {html.escape(title)}</div>"
        f"<ul style='padding-right:20px; padding-left:0; margin:0; color:#e5e7eb; list-style-position:inside;'>{items}</ul>"
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
        "<div style='display:inline-flex; align-items:center; gap:10px; flex-wrap:wrap;'>"
        f"<span style='display:inline-flex; align-items:center; gap:6px; padding:6px 14px; border-radius:999px; border:1px solid {tone['badge_border']}; background:{tone['badge_bg']}; color:{tone['badge_border']}; font-weight:700;'>"
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

    return (
        "<div style='background:linear-gradient(135deg,#111827,#0b1120); border:1px solid #1f2937; "
        "border-radius:18px; padding:24px; margin-bottom:24px; direction:rtl; text-align:right;'>"
        "<div style='display:flex; justify-content:space-between; align-items:center; gap:16px; direction:rtl;'>"
        f"<div style='color:#f9fafb; display:flex; flex-direction:column; gap:10px;'>"
        f"<div style='font-size:26px; font-weight:700; letter-spacing:0.4px;'>{html.escape(symbol)}</div>"
        f"<div style='margin-top:10px;'>{badge_html}</div>"
        f"<div style='font-size:18px; margin-top:8px;'>תחזית: <span style='color:{tone['text_color']}; font-weight:600;'>{forecast_safe}</span></div>"
        "</div>"
        "<div style='display:flex; flex-direction:column; align-items:center; gap:8px;'>"
        "<div style='font-size:14px; color:#bfdbfe;'>רמת ביטחון של המודל (1-10)</div>"
        f"<div style='width:130px; height:130px; border-radius:50%; background:{color}; display:flex; flex-direction:column; "
        "justify-content:center; align-items:center; flex-shrink:0;'>"
        f"<div style='font-size:48px; line-height:1; font-weight:900; color:#1a1a1a; margin-bottom:4px;'>{score_display}</div>"
        "<div style='font-size:18px; font-weight:700; color:#1a1a1a; margin-bottom:6px;'>/10</div>"
        "<div style='font-size:13px; font-weight:600; color:#2a2a2a;'>ציון ביטחון</div>"
        "</div>"
        "</div>"
        f"{sections if sections else ''}"
        "<details style='margin-top:20px; color:#f3f4f6; direction:rtl; text-align:right;'>"
        "<summary style='cursor:pointer; font-weight:600;'>הצג את הניתוח המלא</summary>"
        f"<pre style='white-space:pre-wrap; font-family:inherit; background:#0f172a; border-radius:12px; padding:16px; margin-top:12px; direction:rtl; text-align:right;'>{details}</pre>"
        "</details>"
        "</div>"
    )


st.set_page_config(page_title="Stockagents Dashboard", layout="wide")

# Hebrew RTL styling
st.markdown("""
<style>
    /* Hebrew font */
    * {
        font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    }
    
    /* Main container RTL */
    .main .block-container {
        direction: rtl;
        text-align: right;
    }
    
    /* Input fields RTL */
    .stTextInput > div > div > input {
        direction: rtl;
        text-align: right;
    }
    
    .stTextInput label {
        direction: rtl;
        text-align: right;
    }
    
    /* Buttons RTL */
    .stButton > button {
        direction: rtl;
    }
    
    /* All text elements RTL */
    p, h1, h2, h3, h4, h5, h6, label, div {
        direction: rtl;
        text-align: right;
    }
    
    /* Info/Error messages RTL */
    .stAlert {
        direction: rtl;
        text-align: right;
    }
    
    .stAlert > div {
        direction: rtl;
        text-align: right;
    }
    
    /* Spinner text RTL */
    .stSpinner > div {
        direction: rtl;
        text-align: right;
    }
    
    /* Markdown RTL */
    .stMarkdown {
        direction: rtl;
        text-align: right;
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
if "show_legend" not in st.session_state:
    st.session_state["show_legend"] = False

st.title("ממשק ניתוח מניות - Stockagents")

status_text, status_color = _market_session_status()
st.markdown(
    f"<div style='margin-bottom:16px; display:inline-block; padding:6px 14px; border-radius:999px; background:{status_color}; color:#0b1120; font-weight:700;'>"
    f"{html.escape(status_text)}"  # noqa: E231
    "</div>",
    unsafe_allow_html=True,
)

if st.button("📖 מדריך למדדים ומונחים", key="legend_button", help="לחצו להצגת מדריך המדדים"):
    st.session_state["show_legend"] = True

if st.session_state.get("show_legend"):
    st.markdown(
        """
        <style>
        .legend-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(15, 23, 42, 0.82);
            z-index: 9998;
        }
        .legend-modal {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: min(680px, 92%);
            max-height: 80vh;
            overflow-y: auto;
            background: #0b1120;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 28px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
            direction: rtl;
            text-align: right;
            color: #e5e7eb;
            z-index: 9999;
        }
        .legend-close-wrapper {
            position: absolute;
            top: 12px;
            left: 12px;
        }
        .legend-close-wrapper button {
            background: transparent;
            border: none;
            cursor: pointer;
            font-size: 20px;
            color: #fca5a5;
            padding: 0;
        }
        .legend-close-wrapper button:hover {
            color: #f87171;
        }
        </style>
        <div class='legend-overlay'></div>
        <div class='legend-modal'>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='legend-close-wrapper'>", unsafe_allow_html=True)
    close_clicked = st.button("✕", key="legend_close_button")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
            <h3 style='margin-top:0;'>מדריך למדדים ומונחים</h3>
            <h4 style='color:#d1d5db;'>מדדי חדשות וסנטימנט</h4>
            <ul style='padding-right:18px; line-height:1.7; color:#cbd5f5;'>
                <li><strong>ציון סנטימנט</strong>: ציון בין -1 ל-1 המבטא את הטון הכללי של החדשות.<br><small>-1 עד -0.3 שלילי מאוד · -0.3 עד 0 שלילי קל · 0 עד 0.3 חיובי קל · 0.3 עד 1 חיובי מאוד</small></li>
                <li><strong>Buzz Factor (חשיפה תקשורתית)</strong>: מספר הכתבות ביחס לממוצע.<br><small>< 1.0 חשיפה נמוכה · 1.0–2.0 נורמלי · > 2.0 חשיפה גבוהה</small></li>
            </ul>
            <h4 style='color:#d1d5db;'>מדדים טכניים</h4>
            <ul style='padding-right:18px; line-height:1.7; color:#cbd5f5;'>
                <li><strong>RSI (Relative Strength Index)</strong>: מדד כוח יחסי (0-100).<br><small>< 30 מכירה יתר — פוטנציאל לעלייה · 30–70 טווח נורמלי · > 70 קנייה יתר — פוטנציאל לירידה</small></li>
                <li><strong>MACD Crossover</strong>: אות מומנטום (Bullish / Bearish / No Crossover).</li>
                <li><strong>נפח מסחר</strong>: יחס הנפח היומי לממוצע.<br><small>< 1.0 נמוך · 1.0–1.5 נורמלי · > 2.0 גבוה מאוד — עניין מוגבר</small></li>
            </ul>
            <h4 style='color:#d1d5db;'>ציון ביטחון</h4>
            <ul style='padding-right:18px; line-height:1.7; color:#cbd5f5;'>
                <li>1–3 ביטחון נמוך מאוד</li>
                <li>4–6 ביטחון בינוני</li>
                <li>7–8 ביטחון גבוה</li>
                <li>9–10 ביטחון גבוה מאוד</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if close_clicked:
        st.session_state["show_legend"] = False
        st.experimental_rerun()

input_description = "הזן רשימת מניות מופרדות בפסיק"
symbols_input = st.text_input(input_description, placeholder="AAPL,MSFT,NVDA")
trigger = st.button("נתח")
status_placeholder = st.empty()
results_container = st.container()

if trigger:
    st.session_state["analysis_results"] = None
    st.session_state["analysis_error"] = None
    st.session_state["status_message"] = ""
    st.session_state["status_level"] = "info"
    symbols = _parse_symbols(symbols_input)
    if not symbols:
        st.session_state["analysis_error"] = "נא להזין לפחות סמל בורסאי אחד תקף."
    else:
        status_placeholder.info("מנתח מניות... זה עשוי לקחת מספר דקות...")
        with st.spinner("מנתח מניות... זה עשוי לקחת מספר דקות..."):
            results = run_stock_analysis(symbols)
        st.session_state["status_message"] = "הניתוח הושלם."
        st.session_state["status_level"] = "success"
        if not results:
            st.session_state["analysis_error"] = "לא התקבלו תוצאות ניתוח."
        else:
            st.session_state["analysis_results"] = results

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
