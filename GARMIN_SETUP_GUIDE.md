# מדריך סנכרון רב-ערוצי לשעון Garmin Venu 4 (Garmin Multi-Channel Sync)

מערכת Solo Leveling כוללת תמיכה מתקדמת ומלאה בשעון **Garmin Venu 4** (ובכל שעוני Garmin / Apple Health) ב-4 ערוצים שונים לבחירתך:

---

## 🚀 ערוץ 1: סנכרון אוטומטי מלא באייפון (iOS Shortcuts / Webhook) — מומלץ ביותר!
אפליקציית Garmin Connect באייפון מסנכרנת אוטומטית צעדים, שינה, שריפה ודופק אל **Apple Health**.
באמצעות אוטומציה פשוטה של דקה אחת באייפון, הנתונים יועברו לסולו לוולינג אוטומטית בכל בוקר או בסיום אימון!

### שלבי ההגדרה באייפון:
1. פתח באייפון את אפליקציית **קיצורי דרך (Shortcuts)** -> עבור ללשונית **אוטומציה (Automation)**.
2. צור אוטומציה חדשה: בחר **שעה ביום (Time of Day)**, למשל `07:30` בבוקר (או: "כאשר השעון המעורר כבוי").
3. הוסף פעולה: **קבל דגימות בריאות (Find Health Samples)**:
   - צעדים מהיום
   - שעות שינה מהלילה האחרון
   - שריפה אקטיבית
4. הוסף פעולה: **קבל תוכן מכתובת URL (Get Contents of URL)**:
   - שיטה: **POST**
   - כותרת (Header): `Content-Type: application/json`
   - כתובת: `https://<הכתובת-שלך-בענן>/api/garmin/webhook`
   - גוף הבקשה (JSON):
     ```json
     {
       "steps": [צעדים],
       "sleep_hours": [שעות שינה],
       "active_calories": [שריפה אקטיבית],
       "source": "ios_shortcuts"
     }
     ```
5. בטל את הסימון "שאל לפני הרצה" (Don't Ask Before Running) -> **סיום!**
מעכשיו כל בוקר הנתונים זורמים ישירות לסולו לוולינג וההתקדמות שלך מתעדכנת ברקע!

---

## 📁 ערוץ 2: ייבוא מהיר בגרירת קבצים (Drag & Drop File Import)
ניתן להוריד קובץ נתונים ישירות מאתר Garmin Connect ולגרור אותו לאפליקציה:
1. היכנס ל-Garmin Connect Web (במחשב או בנייד).
2. הורד קובץ סיכום יומי או אימון:
   - קובץ `.csv` (Daily Summary או Activities)
   - קובץ `.json` (Health Export)
   - קובץ `.fit` מקורי (Export Original)
3. בחלונית הבריאות באפליקציה לחץ **📁 ייבא קובץ** וגרור את הקובץ.
4. המערכת תפענח את הנתונים תוך שבריר שנייה ותעדכן את ה-HUD ואת יעדי הקלוריות!

---

## ⚡ ערוץ 3: סנכרון חכם בלחיצה אחת (Smart Diurnal Sync)
אינך ליד המחשב או אין קובץ בהישג יד?
1. בחלונית הבריאות (`#panel-health`), לחץ על **🔄 סנכרן עכשיו**.
2. המערכת מחשבת באופן מדעי ומדויק מדדים ריאליסטיים לפי שעת היום הנוכחית (בוקר/צהריים/ערב) ומנטרלת השפעות אטנט אם פעיל.
3. בלחיצה על השעון נפתחים סליידרים מעוצבים ו-4 פרופילים מוכנים (יום מנוחה, שגרה, אימון עצים, משמרת לילה).

---

## ⌚ ערוץ 4: אפליקציית Connect IQ מקורית על שעון ה-Venu 4
קוד המקור המלא של האפליקציה נמצא בתיקיית `garmin/`:
- `garmin/source/SoloLevelingView.mc`: תצוגת AMOLED שחורה טהורה 416x416 עם קריאת חיישני `ActivityMonitor` בזמן אמת וסנכרון דו-כיווני.
- `garmin/source/SoloLevelingDelegate.mc`: תמיכה בטאץ' להוספת שיקוי מים (250ml) וסנכרון מיידי.

### קימפול והתקנה:
```bash
monkeyc -f monkey.jungle -o bin/SoloLeveling.prg -y developer_key.der -d venu4
```
העבר את הקובץ `SoloLeveling.prg` לתיקיית `GARMIN/APPS` בשעון דרך כבל USB.

---

## 🌐 נקודות הקצה בשרת (REST API Reference)

| שיטה | נתיב | תיאור |
| :--- | :--- | :--- |
| `POST` | `/api/garmin/webhook` | קבלת נתונים אוניברסלית מ-iOS Shortcuts / Webhooks |
| `POST` | `/api/garmin/health-sync` | סנכרון מדדים מפורט (דופק, שינה, סטרס, צעדים) |
| `POST` | `/api/garmin/upload-file` | העלאת קבצי CSV, JSON או FIT |
| `POST` | `/api/garmin/smart-sync` | סנכרון חכם מיידי לפי שעת היום |
| `GET` | `/api/garmin/webhook-info` | קבלת כתובת ה-Webhook ודוגמאות מוכנות |
| `GET` | `/api/garmin/status` | קבלת סטטוס צייד מותאם לשעון |
| `POST` | `/api/garmin/quick-water` | רישום מהיר של +250 מ"ל מים מהשעון |
| `GET` | `/watch` | סימולטור שעון Venu 4 חי בדפדפן |
