# למה השרת "נרדם" ואיך מעירים אותו

## הבעיה
השרת רץ על Render במסלול חינמי. כשאין תנועה ~15 דקות, Render **מרדים** אותו.
התעוררות (cold start) לוקחת ~38 שניות — וה־Shortcut באייפון מתיישן הרבה
לפני זה, אז הנתונים מהשעון/Shortcut פשוט נופלים בדרך.

## הפתרון: פינג כל כמה דקות
השרת חושף נקודת `/api/ping` קלה (בלי גישה ל־DB, תשובה מיידית).
פינג קבוע אליה משאיר את השרת ער 24/7.

### אופציה 1: UptimeRobot (מומלץ, חינמי)
1. הירשם ב־https://uptimerobot.com (חינם).
2. Add New Monitor:
   - Monitor Type: **HTTP(s)**
   - Friendly Name: `solo-leveling-keepalive`
   - URL: `https://rom-z019.onrender.com/api/ping`
   - Monitoring Interval: **5 minutes** (המינימום בחינם)
3. שמור. זהו — השרת יישאר ער.

### אופציה 2: cron-job.org (חינמי, בלי הרשמה מסורבלת)
1. הירשם ב־https://cron-job.org.
2. צור Cronjob חדש:
   - Title: `solo-leveling keepalive`
   - URL: `https://rom-z019.onrender.com/api/ping`
   - Schedule: כל **10 דקות**
3. שמור והפעל.

## בדיקה
פתח בדפדפן: `https://rom-z019.onrender.com/api/ping`
אמור להחזיר מיידית: `{"ok": true, "service": "solo-leveling", ...}`

## הערה
אחרי שהשעון דוחף נתונים ישירות (אפליקציית Connect IQ, כל 15 דקות),
ה־keep-alive עדיין חשוב — גם הדחיפות מהשעון ייכשלו אם השרת ישן.
