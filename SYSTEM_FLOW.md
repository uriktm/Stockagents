# 🔍 זרימת המערכת: ממקלדת למסך

## סקירה כללית
מסמך זה מתאר את המסע המלא של ניתוח מניה במערכת Stockagents - מהרגע שהמשתמש מזין טיקר ועד לתחזית המוצגת בממשק.

---

## 🚀 זרימה מלאה בקצרה

```
משתמש → Streamlit/Desktop/CLI
    ↓
parse_symbols("AAPL, TSLA") → ['AAPL', 'TSLA']
    ↓
run_stock_analysis(['AAPL', 'TSLA'])
    ↓
create_assistant() → AlphaSynthesizerAgent (GPT-4o-mini)
    ↓
לכל מניה:
  Thread + Message: "Please analyze AAPL"
    ↓
  Assistant מפעיל כלים:
    • NewsAndBuzzTool → חדשות + סנטימנט
    • VolumeAndTechnicalsTool → RSI, MACD, Volume
    • CorporateEventsTool → תאריכי רווחים
    • AnalystRatingsTool → המלצות + מחירי יעד
    ↓
  Assistant מסנתז:
    • בודק עקביות אינדיקטורים
    • מחשב ציון ביטחון (1-10)
    • מחזיר תחזית + הסבר סיבתי
    ↓
חילוץ: confidence_score + forecast
    ↓
שמירת לוג: run_history.log + detailed_analysis.log
    ↓
מיון לפי ציון ביטחון
    ↓
הצגה בממשק: כרטיס עם תחזית + נתונים מפורטים
```

---

## 📂 מבנה קבצים מרכזי

### קבצי ליבה
- **`stockagents/core/analysis.py`** – תזמור ראשי, הפעלת Assistant
- **`stockagents/assistant/setup.py`** – יצירת Assistant + System Prompt

### כלי איסוף נתונים (4 כלים)
- **`stockagents/tools/news_and_buzz.py`** – חדשות מ-NewsAPI + סנטימנט GPT
- **`stockagents/tools/volume_and_technicals.py`** – RSI, MACD, Volume מ-yfinance
- **`stockagents/tools/corporate_events.py`** – תאריכי דוחות רווחים
- **`stockagents/tools/analyst_ratings.py`** – המלצות אנליסטים + מחירי יעד

### ממשקים
- **`streamlit_app.py`** – Streamlit Web App
- **`desktop_app.py`** – Qt Desktop App
- **`main.py` + `stockagents/cli/main.py`** – CLI

---

## 🛠️ הכלים בפירוט

### 🔹 NewsAndBuzzTool
**מקור:** NewsAPI.org (Bloomberg, Reuters, CNBC, WSJ, MarketWatch, Fool, SeekingAlpha, Benzinga, Yahoo)

**תהליך:**
1. מושך שם חברה מ-yfinance
2. בונה שאילתת חיפוש (טיקר + שם מלא + שם מקוצר)
3. מושך עד 15 כתבות מהמקורות
4. מסנן רלוונטיות
5. שולח כותרות ל-GPT-4o-mini לניתוח סנטימנט
6. מחזיר: `sentiment_score` (-1 ל-1), `narrative`, `buzz_factor`, `strength` (0-1)

**פלט לדוגמה:**
```python
{
  "sentiment_score": 0.65,
  "narrative": "Positive outlook driven by strong earnings...",
  "buzz_factor": 3.75,
  "strength": 0.82,
  "top_headlines": [...],
  "article_links": [...]
}
```

---

### 🔹 VolumeAndTechnicalsTool
**מקור:** yfinance (3 חודשי נתונים היסטוריים)

**תהליך:**
1. מחשב **RSI (14 תקופות)**: עוקב רווחים/הפסדים יומיים, מנרמל ל-0-100
2. מחשב **MACD**: MACD Line (EMA 12-26), Signal Line (EMA 9)
3. מזהה **Crossover**: האם MACD חצה Signal בין אתמול להיום
4. מחשב **Volume Spike**: נפח אחרון / ממוצע 20 ימים
5. **זיהוי אוטומטי יום לא מלא**: אם נפח < 10% ממוצע, לוקח יום קודם
6. מחזיר: `rsi`, `macd_signal_status`, `volume_spike_ratio`, `technical_signal`, `strength`

**פלט לדוגמה:**
```python
{
  "volume_spike_ratio": 2.3,
  "rsi": 58.42,
  "macd_signal_status": "Crossover",
  "technical_signal": "Bullish Momentum (MACD Crossover)",
  "strength": 0.76
}
```

---

### 🔹 CorporateEventsTool
**מקור:** yfinance

**תהליך:**
1. מושך תאריכי דוחות רווחים
2. מסנן תאריכים עתידיים
3. מחזיר התאריך הקרוב ביותר

**פלט לדוגמה:**
```python
{
  "upcoming_earnings_date": "2025-11-05",
  "has_upcoming_event": True
}
```

---

### 🔹 AnalystRatingsTool
**מקור:** yfinance

**תהליך:**
1. מושך המלצות אנליסטים (Strong Buy, Buy, Hold, Sell, Strong Sell)
2. מושך מחירי יעד (mean, median, high, low)
3. מושך 5 פעולות אחרונות (upgrades/downgrades)
4. מושך מחיר נוכחי
5. מחשב שינוי צפוי באחוזים
6. מחשב ציון קונצנזוס משוקלל (1-5)

**פלט לדוגמה:**
```python
{
  "consensus_rating": "Buy",
  "consensus_score": 3.94,
  "rating_distribution": {"strong_buy": 5, "buy": 7, "hold": 4, "sell": 1, "strong_sell": 0},
  "mean_target_price": 125.0,
  "latest_price": 110.0,
  "target_price_change": 15.0,
  "target_price_change_pct": 13.64,
  "recent_actions": [...]
}
```

---

## 🧠 סינתזה – איך Assistant מחליט?

### עקרונות הניתוח (מתוך System Prompt)
1. **ניתוח אובייקטיבי** – לא שמרני או אופטימי מדי
2. **בסיס על נתונים בלבד** – לא על הנחות
3. **שקיפות בנתונים מעורבים** – אם יש גורמים חיוביים ושליליים, לציין זאת

### הצלבות ובדיקות
#### ✅ ביטחון גבוה (8-10):
- sentiment חיובי (>0.5) **+** MACD Crossover חיובי **+** RSI בטווח בריא (30-70)
- לפחות **שני אינדיקטורים חזקים** (`strength >= 0.7`) באותו כיוון
- נפח מסחר גבוה (>2x) + סנטימנט עקבי

#### ⚠️ ביטחון בינוני (5-7):
- sentiment חיובי **אך** RSI > 75 (סיכון לתיקון)
- MACD חיובי **אך** נפח נמוך (0.7x)
- אינדיקטורים מנוגדים חלקית

#### ❌ ביטחון נמוך (1-4):
- נתונים סותרים בחוזקה
- חסר מידע חדשותי
- כל האינדיקטורים מנוגדים

### שדה `strength` (0-1)
כל כלי מחזיר `strength` שמציין עוצמת האות:
- **`strength >= 0.7`** → אות חזק
- **`strength <= 0.3`** → אות חלש
- **Assistant משתמש ב-strength** לקביעת עקביות

### כללי RSI מיוחדים
- **RSI > 75**: סיכון גבוה לתיקון – זהירות עם תחזיות חיוביות
- **RSI < 25**: סיכון להמשך ירידה
- **30 < RSI < 70**: טווח בריא למגמות

---

## 📊 חילוץ ועיבוד תוצאות

### פונקציות חילוץ (`stockagents/core/analysis.py`)
1. **`_render_assistant_response(messages)`** – חולץ הודעת Assistant מ-Thread
2. **`_extract_confidence_score(response)`** – מחפש תבניות:
   - `"confidence score: 8/10"`
   - `"ציון ביטחון: 9/10"`
   - `"8/10"`
3. **`_extract_forecast(response)`** – מחפש:
   - `"תחזית:"` / `"Forecast:"`
   - מילות מפתח: "צפוי", "עלייה", "ירידה", "bullish", "bearish"
4. **`_collect_tool_insights(symbol)`** – מריץ שוב את הכלים לצורך הצגה בממשק

### דוגמת פלט Assistant
```
תחזית: צפויה עלייה במחיר בגלל נפח מסחר גבוה ב-200% וחדשות חיוביות

ציון ביטחון: 9/10 - כל האינדיקטורים חיוביים ועקביים

הסבר סיבתי:
• נפח מסחר גבוה ב-200% מהממוצע
• MACD Crossover חיובי
• RSI בטווח בריא (58)
• סנטימנט חדשותי חיובי מאוד (0.65) עם 15 כתבות ב-24 שעות
• המלצות אנליסטים: Buy (ציון 3.94/5)
• מחיר יעד ממוצע 13.6% מעל המחיר הנוכחי
```

---

## 💾 לוגים

### `logs/run_history.log`
סיכום כל ריצה:
```
=== Stock Analysis Run ===
Run Date: 2025-10-20T19:45:23+03:00
- Stock: AAPL
- Forecast: צפויה עלייה במחיר בגלל נפח מסחר גבוה ב-200% וחדשות חיוביות
- Confidence: 9.00
```

### `logs/detailed_analysis.log`
לוגים מפורטים (DEBUG level) מכל כלי:
```
2025-10-20 19:45:10 - stockagents.tools.volume_and_technicals - INFO - 
Technical analysis for AAPL: RSI=58.42, Volume Ratio=2.30, 
Signal=Bullish Momentum (MACD Crossover), MACD Status=Crossover, Strength=0.76
```

---

## 🖥️ הצגה בממשק

### מבנה תוצאה
```python
{
  "symbol": "AAPL",
  "forecast": "צפויה עלייה...",
  "confidence_score": 9.0,
  "response_text": "...",
  "tool_insights": {
    "news": {...},
    "technicals": {...},
    "events": {...}
  }
}
```

### רכיבי הצגה (Streamlit)
- **תחזית** (מודגשת)
- **ציון ביטחון** (ירוק 8+, צהוב 5-7, אדום <5)
- **פירוט סיבתי** (נקודות תבליט)
- **קישורים לכתבות** (clickable)
- **נתונים טכניים** (RSI, MACD, Volume)
- **תאריך דוח רווחים**
- **המלצות אנליסטים**

---

## 🔬 בדיקות

### בדיקות יחידה
- `tests/test_analyst_ratings_tool.py`
- `tests/test_social_sentiment_tool.py`
- `tests/test_history.py`
- משתמשות ב-**monkeypatch** לדמות API calls

### בדיקות אינטגרציה
- `tests/test_social_sentiment_integration.py`
- רצות רק עם credentials אמיתיים
- מדלגות אוטומטית (`pytest.skip`) אם אין API keys

### הרצה
```bash
# אוטומטי עם דוחות
.\scripts\run_tests.ps1

# ידני
.\.venv\Scripts\python -m pytest
```

---

## 📝 נקודות מפתח

### API Keys נדרשים (`.env`)
- `OPENAI_API_KEY` – GPT-4o-mini לסנטימנט ול-Assistant
- `NEWSAPI_API_KEY` – NewsAPI.org
- `X_BEARER_TOKEN` (אופציונלי) – Twitter/X sentiment
- `SERPAPI_API_KEY` (אופציונלי) – גיבוי ל-Twitter

### מקורות נתונים
- **NewsAPI.org** – חדשות פיננסיות
- **yfinance** – נתונים טכניים, רווחים, אנליסטים
- **OpenAI GPT-4o-mini** – ניתוח סנטימנט, סינתזה

### תפקיד ה-Assistant
**AlphaSynthesizerAgent** הוא אנליסט בכיר שמחליט:
- אילו כלים להפעיל
- איך לשקלל נתונים
- מה רמת הביטחון
- מה התחזית הסופית

---

## 📖 מסמכים נוספים
- `AGENTS.md` – מפרט Agent
- `PROJECT_PLAN.md` – תוכנית פרויקט
- `tests/README.md` – מדריך בדיקות
- `SETUP_GUIDE.md` – הוראות התקנה
