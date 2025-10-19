"""PySide6 desktop interface for the Stockagents analysis workflow."""

from __future__ import annotations

import sys
from datetime import datetime, time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)
from zoneinfo import ZoneInfo

from stockagents import parse_symbols, run_stock_analysis


def _format_score(score: object) -> tuple[str, Optional[float]]:
    if isinstance(score, (int, float)):
        rounded = round(float(score), 1)
        display = str(rounded)
        if display.endswith(".0"):
            display = display[:-2]
        return display, float(score)
    return "—", None


def _score_color(score: Optional[float]) -> str:
    if score is None:
        return "#6b7280"
    if score >= 7.5:
        return "#16a34a"
    if score >= 5:
        return "#facc15"
    return "#ef4444"


def _forecast_tone(text: str) -> dict[str, str]:
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


class AnalysisWorker(QObject):
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, symbols: List[str]):
        super().__init__()
        self._symbols = symbols

    @Slot()
    def run(self) -> None:
        try:
            results = run_stock_analysis(self._symbols)
        except Exception as exc:  # pragma: no cover - GUI best effort
            self.failed.emit(str(exc))
        else:
            self.finished.emit(results)


class ResultCard(QFrame):
    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("resultCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            QFrame#resultCard {
                background-color: rgba(15, 23, 42, 0.85);
                border: 1px solid rgba(148, 163, 184, 0.3);
                border-radius: 14px;
                color: #e2e8f0;
            }
            QFrame#resultCard QLabel {
                font-size: 14px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = self._build_header(result)
        layout.addLayout(header)

        sections = self._build_sections(result.get("tool_insights") or {})
        if sections:
            layout.addWidget(sections)

        details = self._build_details(result.get("response_text"))
        layout.addWidget(details)

    def _build_header(self, result: Dict[str, Any]) -> QHBoxLayout:
        symbol = str(result.get("symbol", ""))
        score_display, numeric_score = _format_score(result.get("confidence_score"))
        forecast = result.get("forecast") or "לא נמצאה תחזית מפורשת."
        tone = _forecast_tone(forecast)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        summary_layout = QVBoxLayout()
        summary_layout.setSpacing(6)

        symbol_label = QLabel(symbol)
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        symbol_label.setFont(font)
        summary_layout.addWidget(symbol_label)

        badge_label = QLabel(f"{tone['icon']} {tone['label']}")
        badge_label.setAlignment(Qt.AlignRight)
        badge_label.setStyleSheet(
            f"background-color: {tone['badge_bg']};"
            f"border: 1px solid {tone['badge_border']};"
            "border-radius: 999px;"
            "padding: 4px 12px;"
            "font-weight: 600;"
        )
        summary_layout.addWidget(badge_label)

        forecast_label = QLabel(f"תחזית: <span style='color:{tone['text_color']};'>{forecast}</span>")
        forecast_label.setTextFormat(Qt.RichText)
        forecast_label.setWordWrap(True)
        summary_layout.addWidget(forecast_label)

        summary_layout.addStretch(1)
        header_layout.addLayout(summary_layout, 1)

        score_layout = QVBoxLayout()
        score_layout.setSpacing(6)
        score_label = QLabel("רמת ביטחון של המודל")
        score_label.setAlignment(Qt.AlignCenter)
        score_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        score_layout.addWidget(score_label)

        chip = QLabel(f"<b>{score_display}</b><span style='font-size:12px;'> /10</span>")
        chip.setAlignment(Qt.AlignCenter)
        chip.setTextFormat(Qt.RichText)
        chip.setStyleSheet(
            f"background-color: {_score_color(numeric_score)};"
            "color: #0f172a;"
            "padding: 10px 18px;"
            "border-radius: 999px;"
            "font-size: 16px;"
        )
        score_layout.addWidget(chip)
        score_layout.addStretch(1)
        header_layout.addLayout(score_layout)

        return header_layout

    def _build_sections(self, insights: Dict[str, Dict[str, Any]]) -> Optional[QWidget]:
        sections: List[QWidget] = []

        news_widget = self._build_section(
            "📰 חדשות וסנטימנט",
            self._news_points(insights.get("news") or {}),
        )
        if news_widget:
            sections.append(news_widget)

        technical_widget = self._build_section(
            "📈 ניתוח טכני",
            self._technical_points(insights.get("technicals") or {}),
        )
        if technical_widget:
            sections.append(technical_widget)

        events_widget = self._build_section(
            "🗓️ אירועים קרובים",
            self._event_points(insights.get("events") or {}),
        )
        if events_widget:
            sections.append(events_widget)

        if not sections:
            return None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        for section in sections:
            layout.addWidget(section)
        return container

    def _build_section(self, title: str, points: List[Dict[str, object]]) -> Optional[QWidget]:
        if not points:
            return None
        group = QGroupBox(title)
        group.setStyleSheet(
            "QGroupBox { font-weight: 600; border: 1px solid rgba(148, 163, 184, 0.2); "
            "border-radius: 10px; margin-top: 12px; padding: 10px 12px 12px 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top right; padding: 0 4px; }"
        )
        layout = QVBoxLayout()
        layout.setSpacing(6)
        for point in points:
            label = QLabel(point["text"])
            label.setWordWrap(True)
            if point.get("is_link"):
                label.setTextFormat(Qt.RichText)
                label.setOpenExternalLinks(True)
                label.setStyleSheet("color: #38bdf8;")
            else:
                label.setTextFormat(Qt.PlainText)
                label.setStyleSheet("color: #cbd5f5;")
            layout.addWidget(label)
        group.setLayout(layout)
        return group

    def _news_points(self, data: Dict[str, Any]) -> List[Dict[str, object]]:
        points: List[Dict[str, object]] = []
        narrative = data.get("narrative")
        if isinstance(narrative, str) and narrative and narrative.lower() != "insufficient data":
            points.append({"text": f"נרטיב: {narrative}"})

        source_breakdown = data.get("source_breakdown") or []
        source_count = data.get("source_count")
        if source_breakdown:
            breakdown_parts = []
            for item in source_breakdown:
                if isinstance(item, dict):
                    source = str(item.get("source", ""))
                    count = item.get("count", 0)
                    breakdown_parts.append(f"{source} ({int(count)})")
            if breakdown_parts:
                breakdown_text = ", ".join(breakdown_parts)
                if isinstance(source_count, int) and source_count > 0:
                    points.append({
                        "text": f"מספר מקורות עצמאיים: {source_count} ({breakdown_text})",
                    })
                else:
                    points.append({"text": f"מקורות חדשות: {breakdown_text}"})

        sentiment_score = data.get("sentiment_score")
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
            points.append({"text": f"ציון סנטימנט: {round(float(sentiment_score), 2)} {sentiment_text}"})

        buzz = data.get("buzz_factor")
        if isinstance(buzz, (int, float)) and buzz > 0:
            buzz_val = round(float(buzz), 2)
            if buzz_val > 2.0:
                buzz_text = "(חשיפה גבוהה)"
            elif buzz_val >= 1.0:
                buzz_text = "(נורמלי)"
            else:
                buzz_text = "(חשיפה נמוכה)"
            points.append({"text": f"חשיפה תקשורתית: x{buzz_val} {buzz_text}"})

        article_links = data.get("article_links", [])
        if article_links and isinstance(article_links, list):
            for link_info in article_links[:3]:
                if isinstance(link_info, dict):
                    title = str(link_info.get("title", ""))
                    url = str(link_info.get("url", ""))
                    source_label = link_info.get("source")
                    if title and url:
                        truncated = title if len(title) <= 60 else f"{title[:60]}..."
                        prefix = f"[{source_label}] " if source_label else ""
                        display = f"{prefix}{truncated}"
                        points.append({
                            "text": f"<a href='{url}'>{display}</a>",
                            "is_link": True,
                        })
        return points

    def _technical_points(self, data: Dict[str, Any]) -> List[Dict[str, object]]:
        points: List[Dict[str, object]] = []
        signal = data.get("technical_signal")
        if isinstance(signal, str) and signal:
            points.append({"text": f"איתות מרכזי: {signal}"})

        rsi = data.get("rsi")
        if isinstance(rsi, (int, float)):
            rsi_val = round(float(rsi), 2)
            if rsi_val < 30:
                rsi_text = "(מכירה יתר - פוטנציאל לעלייה)"
            elif rsi_val > 70:
                rsi_text = "(קנייה יתר - פוטנציאל לירידה)"
            else:
                rsi_text = "(טווח נורמלי)"
            points.append({"text": f"RSI: {rsi_val} {rsi_text}"})

        volume_ratio = data.get("volume_spike_ratio")
        if isinstance(volume_ratio, (int, float)) and volume_ratio > 0:
            vol_val = round(float(volume_ratio), 2)
            if vol_val > 2.0:
                vol_text = "(נפח גבוה מאוד - עניין מוגבר)"
            elif vol_val >= 1.0:
                vol_text = "(נורמלי)"
            else:
                vol_text = "(נפח נמוך)"
            points.append({"text": f"נפח מסחר: x{vol_val} {vol_text}"})

        return points

    def _event_points(self, data: Dict[str, Any]) -> List[Dict[str, object]]:
        points: List[Dict[str, object]] = []
        earnings_date = data.get("upcoming_earnings_date")
        if isinstance(earnings_date, str) and earnings_date:
            points.append({"text": f"דוח רבעוני צפוי ב-{earnings_date}"})
        elif data.get("has_upcoming_event"):
            points.append({"text": "קיים אירוע תאגידי קרוב"})
        return points

    def _build_details(self, response_text: Optional[str]) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        toggle = QToolButton()
        toggle.setText("הצג את הניתוח המלא")
        toggle.setCheckable(True)
        toggle.setArrowType(Qt.RightArrow)
        layout.addWidget(toggle)

        details = QTextEdit()
        details.setReadOnly(True)
        details.setVisible(False)
        details.setStyleSheet(
            "background-color: rgba(15, 23, 42, 0.6); border: 1px solid rgba(148, 163, 184, 0.25);"
            "border-radius: 10px; color: #e2e8f0;"
        )
        details.setPlainText(response_text or "(אין ניתוח מפורט מהסוכן.)")
        layout.addWidget(details)

        def on_toggled(checked: bool) -> None:
            details.setVisible(checked)
            toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
            toggle.setText("הסתר את הניתוח המלא" if checked else "הצג את הניתוח המלא")

        toggle.toggled.connect(on_toggled)
        return container


class AnalysisWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Stockagents Desktop")
        self.resize(1100, 780)
        self.setLayoutDirection(Qt.RightToLeft)

        central = QWidget()
        self.setCentralWidget(central)

        self._thread: Optional[QThread] = None
        self._worker: Optional[AnalysisWorker] = None

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        self.hero = self._build_hero()
        main_layout.addWidget(self.hero)

        controls = self._build_controls()
        main_layout.addLayout(controls)

        self.status_label = QLabel("הזן סימבולים מופרדים בפסיקים ולחץ נתח")
        self.status_label.setStyleSheet("color: #cbd5f5; font-weight: 500;")
        main_layout.addWidget(self.status_label)

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(14)
        self.results_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.results_container)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        main_layout.addWidget(scroll, 1)

        self._session_timer = QTimer(self)
        self._session_timer.timeout.connect(self._refresh_session_status)
        self._session_timer.start(60000)
        self._refresh_session_status()

    def _build_hero(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("hero")
        frame.setStyleSheet(
            """
            QFrame#hero {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(37, 99, 235, 0.85),
                    stop:1 rgba(2, 6, 23, 0.92));
                border-radius: 20px;
                color: #f8fafc;
                padding: 24px;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)

        title = QLabel("Stockagents - לוח מחוונים חכם")
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        subtitle = QLabel("נתח במהירות מניות חמות עם שילוב נתונים חדשותיים, טכניים ואירועים")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #cbd5f5; font-size: 15px;")
        layout.addWidget(subtitle)

        self.session_badge = QLabel()
        self.session_badge.setAlignment(Qt.AlignRight)
        self.session_badge.setStyleSheet(
            "border-radius: 999px; padding: 6px 14px; font-weight: 600;"
        )
        layout.addWidget(self.session_badge, alignment=Qt.AlignRight)

        return frame

    def _build_controls(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("לדוגמה: NVDA, MSFT, TSLA")
        self.symbol_input.setStyleSheet(
            "background-color: rgba(15, 23, 42, 0.85);"
            "border: 1px solid rgba(148, 163, 184, 0.4);"
            "border-radius: 12px;"
            "padding: 12px;"
            "color: #f8fafc;"
        )
        self.symbol_input.returnPressed.connect(self._trigger_analysis)
        layout.addWidget(self.symbol_input, 1)

        self.analyze_button = QPushButton("נתח")
        self.analyze_button.setStyleSheet(
            "background-color: #38bdf8; color: #0f172a;"
            "font-weight: 700; font-size: 16px;"
            "padding: 12px 24px; border-radius: 12px;"
        )
        self.analyze_button.clicked.connect(self._trigger_analysis)
        layout.addWidget(self.analyze_button)

        return layout

    def _refresh_session_status(self) -> None:
        text, color = _market_session_status()
        self.session_badge.setText(text)
        self.session_badge.setStyleSheet(
            f"background-color: {color}; color: #0f172a; border-radius: 999px; padding: 6px 14px;"
        )

    def _trigger_analysis(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        raw_text = self.symbol_input.text()
        symbols = parse_symbols(raw_text)
        if not symbols:
            self.status_label.setText("אנא הזן לפחות סימבול אחד חוקי.")
            self.status_label.setStyleSheet("color: #f87171; font-weight: 600;")
            return

        self.status_label.setText("מריץ ניתוח...")
        self.status_label.setStyleSheet("color: #38bdf8; font-weight: 600;")
        self.analyze_button.setEnabled(False)
        self.symbol_input.setEnabled(False)

        self._thread = QThread()
        self._worker = AnalysisWorker(symbols)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_results)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._handle_error)
        self._worker.failed.connect(self._thread.quit)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    @Slot(list)
    def _handle_results(self, results: List[Dict[str, Any]]) -> None:
        self._reset_controls()
        if not results:
            self.status_label.setText("לא התקבלו תוצאות. ודא שהסימבולים נכונים ושוב נסה.")
            self.status_label.setStyleSheet("color: #fbbf24; font-weight: 600;")
            self._clear_results()
            return

        self.status_label.setText("הניתוח הושלם בהצלחה.")
        self.status_label.setStyleSheet("color: #4ade80; font-weight: 600;")
        self._populate_results(results)

    @Slot(str)
    def _handle_error(self, message: str) -> None:
        self._reset_controls()
        self.status_label.setText(f"אירעה שגיאה במהלך הניתוח: {message}")
        self.status_label.setStyleSheet("color: #f87171; font-weight: 600;")
        self._clear_results()

    def _reset_controls(self) -> None:
        self.analyze_button.setEnabled(True)
        self.symbol_input.setEnabled(True)
        self._thread = None
        self._worker = None

    def _clear_results(self) -> None:
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_results(self, results: List[Dict[str, Any]]) -> None:
        self._clear_results()
        for result in results:
            card = ResultCard(result)
            self.results_layout.insertWidget(self.results_layout.count() - 1, card)

    def closeEvent(self, event) -> None:  # pragma: no cover - GUI cleanup
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        super().closeEvent(event)


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    window = AnalysisWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
