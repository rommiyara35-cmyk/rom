# מדריך חיבור וסנכרון לשעון Garmin Venu 4 (Garmin Connect IQ)

מערכת Solo Leveling כוללת תמיכה מלאה במסך ה-AMOLED העגול (416x416) של ה-Garmin Venu 4.

---

## אפשרות 1: שימוש בסימולטור השעון החי (ללא צורך בהתקנה)
המערכת כוללת תצוגת שעון אינטראקטיבית מדויקת לחלוטין:
1. פתח בדפדפן או באייפון את הכתובת:
   `http://<IP-שלך>:8080/watch`
2. תראה את שעון ה-Venu 4 בגודל ובצבעים האמיתיים.
3. הקשה על כפתור המים בשעון מעלה מיד 250 מ"ל מים ביומן ומסנכרנת את האפליקציה!

---

## אפשרות 2: התקנה על שעון ה-Garmin באמצעות Connect IQ SDK

### דרישות מוקדמות:
- **Garmin Connect IQ SDK** מותקן (דרך Garmin SDK Manager).
- שעון Garmin Venu 4 מחובר לרשת ה-WiFi הביתית שלך (אותה רשת בה רץ השרת על המחשב).

### שלבי הקימפול וההרצה:
1. פתח את תיקיית הפרויקט:
   `/Users/rommiyara/.gemini/antigravity/scratch/solo-leveling-fitness/garmin`
2. עדכן בקובץ `SoloLevelingView.mc` ו-`SoloLevelingDelegate.mc` את כתובת ה-IP של המחשב ברשת המקומית (מופיעה במסך ההגדרות באפליקציה, למשל `http://192.168.1.X:8080`).
3. קמפל את הפרויקט באמצעות פקודת Connect IQ:
   ```bash
   monkeyc -f monkey.jungle -o bin/SoloLeveling.prg -y developer_key.der -d venu4
   ```
4. העבר את הקובץ `SoloLeveling.prg` לתיקיית `GARMIN/APPS` בשעון דרך כבל ה-USB (או הרץ ישירות ב-Connect IQ Device Simulator).

---

## נקודות הקצה הייעודיות לשעון (Garmin Watch REST API)

- **קבלת סטטוס שעון מותאם זיכרון**:
  `GET /api/garmin/status`
  מחזיר JSON קל משקל:
  ```json
  {
    "lvl": 1,
    "rank": "E-Rank",
    "cal": 1450,
    "cal_tgt": 2180,
    "cal_rem": 730,
    "p": 120.0,
    "p_tgt": 160,
    "c": 165.0,
    "c_tgt": 220,
    "f": 45.0,
    "f_tgt": 65,
    "w": 2250,
    "w_tgt": 3000
  }
  ```

- **הוספת מים מהירה בלחיצה על השעון**:
  `POST /api/garmin/quick-water`
  Body: `{"amount_ml": 250}`
