# הגדרת Postgres לייצור (תיקון C1)

## למה?
האפליקציה שמרה את כל הנתונים בקובץ SQLite מקומי. ב־Render החינמי מערכת
הקבצים זמנית — **כל redeploy מוחק את מסד הנתונים** ומחזיר עותק ישן מהגיט.
הפתרון: מסד Postgres חיצוני (חינמי), והקוד כבר תומך בו.

## איך זה עובד?
- אם מוגדר משתנה הסביבה `DATABASE_URL` — האפליקציה מתחברת ל־Postgres.
- אם לא מוגדר — היא ממשיכה עם SQLite מקומי (לפיתוח).
- אין צורך לשנות קוד — השכבה ב־`server.py` מתרגמת אוטומטית.

## אופציה 1: Supabase (מומלץ, חינמי)
1. הירשם ב־[supabase.com](https://supabase.com) → New Project.
2. בחר סיסמה למסד, המתן ~2 דקות.
3. Project Settings ← Database ← Connection string ← URI. העתק אותו.
   (הוא נראה כך: `postgresql://postgres:XXXX@db.xxxxx.supabase.co:5432/postgres`)
4. ב־Render: השירות שלך ← Environment ← Add Environment Variable:
   - Key: `DATABASE_URL`
   - Value: המחרוזת שהעתקת (החלף את `XXXX` בסיסמה שבחרת)
5. שמור — Render עושה redeploy אוטומטי.

## אופציה 2: Neon (חינמי)
1. הירשם ב־[neon.tech](https://neon.tech) → Create Project.
2. בלוח הבקרה: Connection Details ← העתק את ה־Connection String.
3. ב־Render: Environment ← הוסף `DATABASE_URL` עם המחרוזת. שמור.

## אופציה 3: Render Postgres (חינמי ל־90 יום, אחר כך בתשלום)
1. בדשבורד של Render: New ← PostgreSQL.
2. אחרי היצירה: לשונית Info ← Internal Database URL ← העתק.
3. בשירות האפליקציה: Environment ← הוסף `DATABASE_URL`. שמור.

## בדיקה שהכל עובד
אחרי ה־redeploy, פתח: `https://<your-app>.onrender.com/api/ping`
ואז רשום ארוחה/מנה באפליקציה, עשה redeploy ידני (Manual Deploy ← Deploy latest commit)
ובדוק שהנתונים **נשארו**. אם כן — התיקון עובד ✅

## הערות
- בטבלאות נוצרות אוטומטית בהפעלה הראשונה (`init_db`) — אין צורך לייבא סכמה.
- אם היו לך נתונים חשובים ב־SQLite הישן — ייצא אותם דרך `/api/backup` **לפני**
  המעבר, כי המעבר מתחיל ממסד ריק.
- אל תדביק את `DATABASE_URL` בקוד או בצ׳אט — רק ב־Environment של Render.
