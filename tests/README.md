# בדיקות Stockagents

## סקירה
תיקיה זו מכילה את כל הבדיקות עבור הפרויקט Stockagents.

## מבנה
```
tests/
├── test_analyst_ratings_tool.py          # בדיקות יחידה ל-AnalystRatingsTool
├── test_social_sentiment_tool.py         # בדיקות יחידה ל-SocialSentimentTool
├── test_social_sentiment_integration.py  # בדיקות אינטגרציה (דורשות API keys)
├── test_history.py                       # בדיקות ניהול היסטוריה
└── README.md                              # קובץ זה
```

## הרצת בדיקות

### דרך מהירה (סקריפט אוטומטי)
```powershell
.\scripts\run_tests.ps1
```
הסקריפט יבצע:
- יצירת/עדכון venv
- התקנת תלויות
- הרצת כל הבדיקות
- יצירת דוחות

### דרך ידנית
```powershell
# התקנה חד-פעמית
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install -r requirements-dev.txt

# הרצת בדיקות עם דוחות
.\.venv\Scripts\python -m pytest --html=reports/test-report.html --self-contained-html --junitxml=reports/junit.xml --cov=stockagents --cov-report=term-missing:skip-covered --cov-report=xml:reports/coverage.xml
```

### הרצה מהירה ללא דוחות
```powershell
.\.venv\Scripts\python -m pytest
```

## דוחות
לאחר ההרצה, הדוחות נמצאים ב:
- **HTML**: `reports/test-report.html` (פתח בדפדפן)
- **JUnit XML**: `reports/junit.xml` (לשילוב CI)
- **כיסוי קוד**: `reports/coverage.xml` + תקציר בטרמינל

## סוגי בדיקות

### בדיקות יחידה (Unit Tests)
משתמשות ב-`monkeypatch` כדי לדמות API calls ולא דורשות credentials אמיתיים.

### בדיקות אינטגרציה (Integration Tests)
- רצות רק אם יש API keys בסביבה
- מדלגות אוטומטית (`pytest.skip`) אם אין credentials
- לדוגמה: `test_social_sentiment_integration.py`

## סטטוס בדיקות נוכחי
```
10 בדיקות עברו בהצלחה ✓
כיסוי קוד: 42%
```

## הוספת בדיקות חדשות
1. צור קובץ `test_*.py` בתיקיה זו
2. כתוב פונקציות שמתחילות ב-`test_`
3. הרץ `pytest` לוודא שהן עוברות
4. עדכן README זה במידת הצורך
