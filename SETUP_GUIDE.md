# מדריך הפעלה - Stockagents Desktop

## דרישות מקדימות

### 1. API Keys נדרשים

האפליקציה דורשת מפתחות API מהשירותים הבאים:

#### **OpenAI API Key (חובה)** ⭐
- היכן להשיג: https://platform.openai.com/api-keys
- לחץ "Create new secret key"
- העתק את המפתח (מתחיל ב-`sk-`)

#### **News API Key (מומלץ)** 📰
- היכן להשיג: https://newsapi.org/register
- תוכנית חינם: עד 100 בקשות ליום
- העתק את ה-API key

#### **Financial Modeling Prep API Key (אופציונלי)** 📊
- היכן להשיג: https://financialmodelingprep.com/developer/docs/
- תוכנית חינם זמינה
- העתק את ה-API key

### 2. יצירת קובץ .env

צור קובץ בשם `.env` בתיקיית הפרויקט עם התוכן הבא:

```env
# OpenAI API Key (חובה)
OPENAI_API_KEY=sk-your-key-here

# News API Key (מומלץ לתוצאות טובות יותר)
NEWSAPI_API_KEY=your-newsapi-key-here

# Financial Modeling Prep API Key (אופציונלי)
FMP_API_KEY=your-fmp-key-here
```

**החלף** את `your-key-here` במפתחות האמיתיים שלך!

## הפעלה

### שלב 1: התקנת תלויות
```bash
py -m pip install -r requirements.txt
```

### שלב 2: הפעלת האפליקציה
```bash
py desktop_app.py
```

## פתרון בעיות נפוצות

### החלון נסגר מיד
✅ **פתרון:** וודא שיש לך קובץ `.env` עם `OPENAI_API_KEY` תקין

### שגיאת "QThread: Destroyed while thread is still running"
✅ **פתרון:** עודכן - השגיאה תיקנתי בקוד

### "Authentication error" או "Invalid API key"
✅ **פתרון:** בדוק שהמפתח שלך מתחיל ב-`sk-` ושהוא עדיין פעיל

### לא מקבל חדשות או נתונים
✅ **פתרון:** הוסף את `NEWSAPI_API_KEY` ו-`FMP_API_KEY` לקובץ `.env`

## שימוש

1. הזן סימבולי מניות מופרדים בפסיקים (למשל: `NVDA, AAPL, TSLA`)
2. לחץ על כפתור "נתח"
3. המתן לתוצאות (יכול לקחת 30-60 שניות)
4. צפה בניתוח המפורט עם ציון ביטחון

## עלויות

- **OpenAI API:** מחיר משתנה לפי שימוש (בדרך כלל $0.01-$0.05 לניתוח)
- **News API:** חינם עד 100 בקשות ליום
- **FMP:** רוב המידע חינם בתוכנית הבסיסית

---
📧 לשאלות ובעיות: פתח issue ב-GitHub
