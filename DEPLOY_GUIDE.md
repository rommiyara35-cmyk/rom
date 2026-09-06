# ⚡ מדריך העלאה לענן (24/7 ללא תלות במחשב)

מערכת ה-Solo Leveling Fitness שלך מוכנה כעת לעלייה לענן חינמי (**Render**).  
לאחר סיום התהליך (לוקח פחות מ-2 דקות), תקבל כתובת אינטרנט מאובטחת כגון:  
`https://solo-leveling-fitness.onrender.com`  
היא תעבוד תמיד, מכל מקום (במשמרות, בסלולר, באימון), ועם תמיכה מלאה במצלמה באייפון.

---

## 🛠 שלב 1: העלאת הפרויקט לחשבון ה-GitHub שלך

אם עדיין אין לך מאגר ב-GitHub:
1. היכנס ל-[github.com/new](https://github.com/new) וצור מאגר חדש (למשל בשם `solo-fitness-system`).
2. בטרמינל במחשב הרץ את הפקודות הבאות:
```bash
cd /Users/rommiyara/.gemini/antigravity/scratch/solo-leveling-fitness
git remote add origin https://github.com/<השם-משתמש-שלך>/solo-fitness-system.git
git push -u origin main
```

---

## 🚀 שלב 2: חיבור חינמי ל-Render (קליק אחד)

1. היכנס ל-[render.com](https://render.com) והתחבר (בחינם עם חשבון ה-GitHub שלך).
2. לחץ על **New +** ובחר **Web Service**.
3. בחר את המאגר שיצרת (`solo-fitness-system`).
4. שדות ההגדרה יתמלאו אוטומטית הודות לקובץ `render.yaml` שהכנו עבורך:
   - **Name**: `solo-leveling-fitness` (או כל שם שתרצה)
   - **Runtime**: `Python 3`
   - **Start Command**: `python3 server.py`
   - **Plan Type**: `Free`
5. לחץ **Create Web Service**.

---

## 🎉 זהו!
תוך כדקה המערכת באוויר!  
רנדר תציג לך קישור ירוק: `https://<השם-שבחרת>.onrender.com`.
פתח את הקישור הזה באייפון שלך:
1. לחץ על כפתור השיתוף ב-Safari.
2. בחר **"הוסף למסך הבית" (Add to Home Screen)**.
3. כעת יש לך אפליקציית Solo Leveling אמיתית באייפון שפועלת 24/7 ללא צורך במחשב פועל וללא Wi-Fi!
