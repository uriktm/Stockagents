# 🖥️ איך ליצור קיצור דרך על שולחן העבודה

## שיטה 1: אוטומטית (מומלץ) ⚡

### הרץ את הפקודה הבאה ב-PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File "d:\projects\Stockagents\create_desktop_shortcut.ps1"
```

זהו! קיצור הדרך נוצר אוטומטית על שולחן העבודה 🎉

---

## שיטה 2: ידנית 🖱️

### שלב 1: צור קיצור דרך
1. לחץ לחיצה ימנית על שולחן העבודה
2. בחר **New → Shortcut**

### שלב 2: הגדר את היעד
הדבק את השורה הבאה בשדה "Type the location of the item":

```
wscript.exe "d:\projects\Stockagents\run_stockagents.vbs"
```

### שלב 3: תן שם
כתוב: **Stockagents**

### שלב 4: (אופציונלי) שנה אייקון
1. לחץ לחיצה ימנית על קיצור הדרך → **Properties**
2. לחץ על **Change Icon**
3. בחר אייקון שאתה אוהב (מומלץ: גרף או מניות)

---

## שיטה 3: קיצור דרך פשוט עם Terminal 🖥️

אם אתה מעדיף לראות את הלוגים:

### צור קובץ BAT:
צור קובץ בשם `Stockagents.bat` עם התוכן:

```batch
@echo off
cd /d "d:\projects\Stockagents"
py desktop_app.py
pause
```

אחר כך צור קיצור דרך לקובץ הזה.

---

## 🎯 מה עשינו?

הקובץ `run_stockagents.vbs` מפעיל את האפליקציה **בלי להראות חלון של Terminal**.

זה נותן חוויה נקייה יותר - האפליקציה פשוט נפתחת!

---

## 🔧 פתרון בעיות

### "אין הרשאה להריץ סקריפטים"
הרץ את זה ב-PowerShell (כמנהל):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### האפליקציה לא נפתחת
1. וודא ש-Python מותקן ו-`py` זמין
2. וודא שכל התלויות מותקנות (`py -m pip install -r requirements.txt`)
3. בדוק שיש קובץ `.env` עם מפתחות API

---

## 📝 הערות

- הקיצור דרך יפעיל את האפליקציה **בלי חלון Terminal שחור**
- הלוגים עדיין נשמרים ב-`run_history.log`
- אם יש שגיאה, האפליקציה פשוט לא תיפתח - בדוק את הלוג

---

נהנה מ-Stockagents? ⭐ תן כוכב ב-GitHub!
