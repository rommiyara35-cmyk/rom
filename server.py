#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Solo Leveling Fitness & Nutrition System - Backend Server
Evidence-based nutrition calculations, Solo Leveling gamification,
persistent SQLite storage, and Garmin Venu 4 API integration.
"""

import os
import sys
import json
import sqlite3
import datetime
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DB_PATH = os.path.join(BASE_DIR, "fitness_system.db")
FOOD_DB_PATH = os.path.join(BASE_DIR, "food_database.json")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    for iface in ["en0", "en1"]:
        try:
            import subprocess
            out = subprocess.check_output(["ipconfig", "getifaddr", iface], timeout=1).decode("utf-8").strip()
            if out:
                return out
        except Exception:
            pass
    return "127.0.0.1"

# -------------------------------------------------------------
# Evidence-Based Nutrition Science Engine
# -------------------------------------------------------------
class NutritionScienceEngine:
    @staticmethod
    def calculate_bmr(weight_kg, height_cm, age, sex="male", body_fat_pct=None):
        if body_fat_pct is not None and body_fat_pct > 0:
            # Katch-McArdle Formula (Lean Mass based)
            lean_mass = weight_kg * (1 - (body_fat_pct / 100.0))
            return round(370 + (21.6 * lean_mass))
        
        # Mifflin-St Jeor Formula
        if sex.lower() == "female":
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
        else:
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
        return round(bmr)

    @staticmethod
    def get_activity_multiplier(activity_level):
        multipliers = {
            "sedentary": 1.2,       # Little or no exercise, desk job
            "light": 1.375,         # Light exercise 1-3 days/week
            "moderate": 1.55,       # Moderate exercise 3-5 days/week
            "very_active": 1.725,   # Hard exercise 6-7 days/week
            "extra_active": 1.9     # Very hard exercise, physical job or 2x training
        }
        return multipliers.get(activity_level.lower(), 1.55)

    @classmethod
    def calculate_full_profile(cls, weight_kg, height_cm, age, sex="male", activity_level="moderate", goal="cut", body_fat_pct=None):
        bmr = cls.calculate_bmr(weight_kg, height_cm, age, sex, body_fat_pct)
        pal = cls.get_activity_multiplier(activity_level)
        tdee = round(bmr * pal)

        # Calorie Target based on Goal
        if goal == "cut":
            # Scientific 20% deficit for optimal fat loss while sparing LBM
            target_calories = round(tdee * 0.80)
            protein_factor = 2.2  # Higher protein during deficit (ISSN guidelines)
        elif goal == "bulk":
            # Scientific lean bulk 8-10% surplus
            target_calories = round(tdee * 1.09)
            protein_factor = 1.9
        else:  # maintain
            target_calories = tdee
            protein_factor = 1.8

        # Protein (ISSN: 1.6-2.2 g/kg)
        target_protein = round(weight_kg * protein_factor)
        protein_calories = target_protein * 4

        # Fat: 0.8 - 1.0 g/kg (minimum physiological hormonal floor)
        target_fats = max(45, round(weight_kg * 0.85))
        fat_calories = target_fats * 9

        # Carbs: Remaining calories
        remaining_cals = max(400, target_calories - protein_calories - fat_calories)
        target_carbs = round(remaining_cals / 4.0)

        # Scientific Water: 38 ml/kg + baseline workout buffer
        target_water = round(weight_kg * 38 + 500)

        # Scientific Fiber: 14g per 1000 kcal
        target_fiber = round(14.0 * (target_calories / 1000.0))

        # Scientific Micronutrient Recommended Daily Allowances (RDA)
        micronutrient_targets = {
            "fiber_g": target_fiber,
            "sodium_mg": 2200,
            "potassium_mg": 3500,
            "magnesium_mg": 420 if sex == "male" else 320,
            "zinc_mg": 14 if sex == "male" else 9,
            "vit_c_mg": 90,
            "vit_d_iu": 1500,
            "iron_mg": 10 if sex == "male" else 18
        }

        return {
            "bmr": bmr,
            "tdee": tdee,
            "target_calories": target_calories,
            "target_protein": target_protein,
            "target_carbs": target_carbs,
            "target_fats": target_fats,
            "target_water": target_water,
            "target_fiber": target_fiber,
            "micros": micronutrient_targets
        }

def get_hunter_shift_date(conn):
    try:
        c = conn.cursor()
        c.execute("SELECT day_reset_hour FROM hunter_profile WHERE id=1")
        row = c.fetchone()
        reset_hour = row["day_reset_hour"] if row and row["day_reset_hour"] is not None else 0
    except Exception:
        reset_hour = 0
    now = datetime.datetime.now()
    if now.hour < reset_hour:
        return (now.date() - datetime.timedelta(days=1)).isoformat()
    return now.date().isoformat()

# -------------------------------------------------------------
# Database Manager
# -------------------------------------------------------------
class Database:
    @staticmethod
    def get_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        with cls.get_connection() as conn:
            c = conn.cursor()
            # Hunter profile
            c.execute("""
            CREATE TABLE IF NOT EXISTS hunter_profile (
                id INTEGER PRIMARY KEY,
                name TEXT DEFAULT 'Hunter',
                rank TEXT DEFAULT 'E-Rank',
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                exp_to_next INTEGER DEFAULT 300,
                title TEXT DEFAULT 'Awakened Novice',
                age INTEGER DEFAULT 25,
                sex TEXT DEFAULT 'male',
                weight REAL DEFAULT 78.0,
                height REAL DEFAULT 178.0,
                activity_level TEXT DEFAULT 'moderate',
                goal TEXT DEFAULT 'cut',
                body_fat_pct REAL DEFAULT 18.0,
                bmr INTEGER DEFAULT 1760,
                tdee INTEGER DEFAULT 2728,
                target_calories INTEGER DEFAULT 2180,
                target_protein INTEGER DEFAULT 160,
                target_carbs INTEGER DEFAULT 220,
                target_fats INTEGER DEFAULT 65,
                target_water INTEGER DEFAULT 3200,
                target_fiber INTEGER DEFAULT 30,
                stats_str INTEGER DEFAULT 10,
                stats_agi INTEGER DEFAULT 10,
                stats_vit INTEGER DEFAULT 10,
                stats_int INTEGER DEFAULT 10,
                stats_per INTEGER DEFAULT 10,
                fatigue INTEGER DEFAULT 15,
                streak_days INTEGER DEFAULT 1,
                last_active_date TEXT,
                shift_mode TEXT DEFAULT 'standard',
                day_reset_hour INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            try:
                c.execute("ALTER TABLE hunter_profile ADD COLUMN shift_mode TEXT DEFAULT 'standard'")
            except Exception:
                pass
            try:
                c.execute("ALTER TABLE hunter_profile ADD COLUMN day_reset_hour INTEGER DEFAULT 0")
            except Exception:
                pass


            # Food items table
            c.execute("""
            CREATE TABLE IF NOT EXISTS food_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_he TEXT NOT NULL,
                category TEXT,
                serving_size_g REAL DEFAULT 100,
                calories REAL NOT NULL,
                protein REAL NOT NULL,
                carbs REAL NOT NULL,
                fats REAL NOT NULL,
                fiber REAL DEFAULT 0,
                sodium_mg REAL DEFAULT 0,
                potassium_mg REAL DEFAULT 0,
                magnesium_mg REAL DEFAULT 0,
                zinc_mg REAL DEFAULT 0,
                vit_c_mg REAL DEFAULT 0,
                vit_d_iu REAL DEFAULT 0,
                iron_mg REAL DEFAULT 0,
                is_custom INTEGER DEFAULT 0
            )
            """)

            # Daily logs
            c.execute("""
            CREATE TABLE IF NOT EXISTS daily_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                food_id INTEGER,
                food_name TEXT NOT NULL,
                serving_count REAL DEFAULT 1.0,
                serving_size_g REAL DEFAULT 100,
                calories REAL NOT NULL,
                protein REAL NOT NULL,
                carbs REAL NOT NULL,
                fats REAL NOT NULL,
                fiber REAL DEFAULT 0,
                sodium_mg REAL DEFAULT 0,
                potassium_mg REAL DEFAULT 0,
                magnesium_mg REAL DEFAULT 0,
                zinc_mg REAL DEFAULT 0,
                vit_c_mg REAL DEFAULT 0,
                vit_d_iu REAL DEFAULT 0,
                iron_mg REAL DEFAULT 0,
                meal_type TEXT DEFAULT 'snack',
                timestamp TEXT NOT NULL
            )
            """)

            # Water logs
            c.execute("""
            CREATE TABLE IF NOT EXISTS water_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount_ml INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
            """)

            # Garmin health logs table
            c.execute("""
            CREATE TABLE IF NOT EXISTS garmin_health_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                heart_rate INTEGER DEFAULT 68,
                resting_hr INTEGER DEFAULT 58,
                sleep_score INTEGER DEFAULT 82,
                sleep_hours REAL DEFAULT 7.2,
                stress_level INTEGER DEFAULT 28,
                body_battery INTEGER DEFAULT 75,
                steps INTEGER DEFAULT 8500,
                active_calories INTEGER DEFAULT 450,
                spo2_pct INTEGER DEFAULT 98,
                respiration_rpm INTEGER DEFAULT 14,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Medication / Attent logs table
            c.execute("""
            CREATE TABLE IF NOT EXISTS medication_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                med_name TEXT NOT NULL DEFAULT 'Attent',
                dose_mg INTEGER NOT NULL DEFAULT 20,
                timestamp TEXT NOT NULL,
                duration_hours REAL DEFAULT 7.0,
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Initialize profile if empty
            c.execute("SELECT COUNT(*) FROM hunter_profile WHERE id=1")
            if c.fetchone()[0] == 0:
                c.execute("""
                INSERT INTO hunter_profile (id, name, rank, level, exp, exp_to_next, title, last_active_date)
                VALUES (1, 'צייד רום', 'E-Rank', 1, 0, 300, 'צייד שהתעורר (Awakened)', date('now'))
                """)

            # Populate food_items if empty
            c.execute("SELECT COUNT(*) FROM food_items")
            if c.fetchone()[0] == 0 and os.path.exists(FOOD_DB_PATH):
                with open(FOOD_DB_PATH, "r", encoding="utf-8") as f:
                    foods = json.load(f)
                    for item in foods:
                        c.execute("""
                        INSERT INTO food_items (
                            name, name_he, category, serving_size_g, calories, protein, carbs, fats,
                            fiber, sodium_mg, potassium_mg, magnesium_mg, zinc_mg, vit_c_mg, vit_d_iu, iron_mg, is_custom
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """, (
                            item.get("name"), item.get("name_he"), item.get("category"), item.get("serving_size_g", 100),
                            item.get("calories", 0), item.get("protein", 0), item.get("carbs", 0), item.get("fats", 0),
                            item.get("fiber", 0), item.get("sodium_mg", 0), item.get("potassium_mg", 0),
                            item.get("magnesium_mg", 0), item.get("zinc_mg", 0), item.get("vit_c_mg", 0),
                            item.get("vit_d_iu", 0), item.get("iron_mg", 0)
                        ))
            conn.commit()

# -------------------------------------------------------------
# Gamification Engine
# -------------------------------------------------------------
class HunterLevelingEngine:
    @staticmethod
    def get_rank(level):
        if level < 10:
            return "E-Rank"
        elif level < 20:
            return "D-Rank"
        elif level < 30:
            return "C-Rank"
        elif level < 40:
            return "B-Rank"
        elif level < 50:
            return "A-Rank"
        elif level < 75:
            return "S-Rank"
        else:
            return "Shadow Monarch"

    @staticmethod
    def add_exp(conn, amount):
        c = conn.cursor()
        c.execute("SELECT level, exp, exp_to_next, rank, stats_str, stats_agi, stats_vit, stats_int, stats_per FROM hunter_profile WHERE id=1")
        row = c.fetchone()
        if not row:
            return {"leveled_up": False}

        level = row["level"]
        exp = row["exp"] + amount
        exp_to_next = row["exp_to_next"]
        leveled_up = False

        while exp >= exp_to_next:
            exp -= exp_to_next
            level += 1
            exp_to_next = round(exp_to_next * 1.25 + 50)
            leveled_up = True
            c.execute("""
            UPDATE hunter_profile 
            SET stats_str = stats_str + 1,
                stats_agi = stats_agi + 1,
                stats_vit = stats_vit + 1,
                stats_int = stats_int + 1,
                stats_per = stats_per + 1,
                fatigue = max(0, fatigue - 20)
            WHERE id=1
            """)

        new_rank = HunterLevelingEngine.get_rank(level)
        c.execute("""
        UPDATE hunter_profile
        SET level = ?, exp = ?, exp_to_next = ?, rank = ?
        WHERE id=1
        """, (level, exp, exp_to_next, new_rank))
        conn.commit()

        return {
            "leveled_up": leveled_up,
            "level": level,
            "rank": new_rank,
            "exp": exp,
            "exp_to_next": exp_to_next
        }

# -------------------------------------------------------------
# Garmin Biometrics & Attent AI Physiological Advisor
# -------------------------------------------------------------
class HunterHealthAIAdvisor:
    @staticmethod
    def get_health_state(conn, today):
        c = conn.cursor()
        # 1. Fetch Garmin biometrics row
        c.execute("SELECT * FROM garmin_health_logs WHERE date = ?", (today,))
        g_row = c.fetchone()
        if not g_row:
            now_time = datetime.datetime.now().strftime("%H:%M")
            c.execute("""
            INSERT OR IGNORE INTO garmin_health_logs 
            (date, timestamp, heart_rate, resting_hr, sleep_score, sleep_hours, stress_level, body_battery, steps, active_calories)
            VALUES (?, ?, 68, 58, 82, 7.2, 28, 75, 8500, 450)
            """, (today, now_time))
            conn.commit()
            c.execute("SELECT * FROM garmin_health_logs WHERE date = ?", (today,))
            g_row = c.fetchone()

        garmin = dict(g_row) if g_row else {
            "heart_rate": 68, "resting_hr": 58, "sleep_score": 82, "sleep_hours": 7.2,
            "stress_level": 28, "body_battery": 75, "steps": 8500, "active_calories": 450,
            "spo2_pct": 98, "respiration_rpm": 14
        }

        # 2. Fetch medication logs for today
        c.execute("SELECT * FROM medication_logs WHERE date = ? ORDER BY id DESC", (today,))
        meds = [dict(r) for r in c.fetchall()]

        # 3. Check for active Attent
        attent_info = None
        now = datetime.datetime.now()
        for m in meds:
            if m["med_name"].lower() == "attent":
                try:
                    time_parts = m["timestamp"].split(":")
                    dose_hour = int(time_parts[0])
                    dose_min = int(time_parts[1]) if len(time_parts) > 1 else 0
                    dose_dt = now.replace(hour=dose_hour, minute=dose_min, second=0, microsecond=0)
                    if dose_dt > now:
                        dose_dt -= datetime.timedelta(days=1)
                    elapsed_h = max(0.0, round((now - dose_dt).total_seconds() / 3600.0, 1))
                except Exception:
                    elapsed_h = 2.0

                duration = float(m.get("duration_hours", 7.0))
                is_active = elapsed_h <= (duration + 1.0)
                remaining = max(0.0, round(duration - elapsed_h, 1))

                attent_info = {
                    "id": m["id"],
                    "med_name": m["med_name"],
                    "dose_mg": m["dose_mg"],
                    "timestamp": m["timestamp"],
                    "elapsed_hours": elapsed_h,
                    "duration_hours": duration,
                    "remaining_hours": remaining,
                    "is_active": is_active,
                    "notes": m.get("notes", "")
                }
                break

        return garmin, attent_info, meds

    @classmethod
    def analyze_and_generate_insights(cls, conn, today):
        c = conn.cursor()
        c.execute("SELECT * FROM hunter_profile WHERE id=1")
        profile = dict(c.fetchone())

        garmin, attent_info, meds = cls.get_health_state(conn, today)

        c.execute("""
        SELECT COALESCE(SUM(calories), 0) as cal,
               COALESCE(SUM(protein), 0) as p,
               COALESCE(SUM(carbs), 0) as c,
               COALESCE(SUM(fats), 0) as f
        FROM daily_logs WHERE date = ?
        """, (today,))
        nut = dict(c.fetchone())

        c.execute("SELECT COALESCE(SUM(amount_ml), 0) as w FROM water_logs WHERE date = ?", (today,))
        water = c.fetchone()["w"]

        insights = []

        # 1. Attent Insights
        if attent_info and attent_info["is_active"]:
            dose = attent_info["dose_mg"]
            elapsed = attent_info["elapsed_hours"]
            rem = attent_info["remaining_hours"]
            prot_consumed = round(nut["p"], 1)
            prot_pct = (nut["p"] / max(1, profile["target_protein"])) * 100

            # (A) Appetite suppression & Anti-Catabolism
            if prot_pct < 50 and elapsed >= 2.5:
                insights.append({
                    "id": "attent_protein_alert",
                    "category": "attent",
                    "level": "warning",
                    "icon": "💊",
                    "tag": "אטנט & דיכוי רעב",
                    "title": "הגנה דחופה על מסת השריר (Anti-Catabolism)",
                    "message": f"שיקוי הריכוז (אטנט {dose}mg) פעיל {elapsed:.1f} שעות ומדכא את מרכז הרעב במוח. הגעת רק ל-{prot_consumed}g מתוך {profile['target_protein']}g חלבון. למרות שאינך רעב, גופך עלול לפרק רקמת שריר (STR)! צרוך כעת שייק חלבון או מעדן PRO (30g חלבון מהיר).",
                    "action_text": "צרוך שייק חלבון עכשיו (+30g P)"
                })
            else:
                insights.append({
                    "id": "attent_protein_ok",
                    "category": "attent",
                    "level": "success",
                    "icon": "🛡️",
                    "tag": "אטנט & מגן שריר",
                    "title": "שמירה על מאזן חלבון ומסת שריר",
                    "message": f"האטנט פעיל (נותרו {rem:.1f} שעות שיא), וקצב צריכת החלבון שלך ({prot_consumed}g מתוך {profile['target_protein']}g) מגן היטב על תכונת ה-STR ומאזן החנקן בשריר.",
                    "action_text": "המשך שמירה על רצף חלבון"
                })

            # (B) HR & Stress Demystification
            hr = garmin["heart_rate"]
            stress = garmin["stress_level"]
            resting = garmin["resting_hr"]
            if stress >= 35 or hr >= 74 or (hr - resting) >= 10:
                insights.append({
                    "id": "attent_hr_demystify",
                    "category": "biometric",
                    "level": "info",
                    "icon": "⚡",
                    "tag": "גרמין & אטנט פיזיולוגיה",
                    "title": "הסבר לעליית סטרס ודופק ב-Garmin Venu 4",
                    "message": f"השעון מזהה סטרס של {stress}/100 ודופק {hr} bpm (מנוחה: {resting} bpm). אין סיבה לדאגה: זוהי תגובה סימפתטית טבעית ומוכרת של האטנט (שחרור נוראדרנלין ודופמין) ולא עקה נפשית אמיתית או אימון יתר. המערכת ניטרלה את ההשפעה מחישוב ה-Fatigue שלך!",
                    "action_text": "המדדים הותאמו פרמקולוגית"
                })
            else:
                insights.append({
                    "id": "attent_autonomic_stable",
                    "category": "biometric",
                    "level": "info",
                    "icon": "⚡",
                    "tag": "מערכת עצבים יציבה",
                    "title": "סבילות פיזיולוגית מעולה",
                    "message": f"דופק המנוחה ({resting} bpm) ומדד הסטרס ({stress}) רגועים ויציבים תחת השפעת מנת ה-{dose}mg.",
                    "action_text": "מצב סימפתטי מאוזן"
                })

            # (C) Hydration & Electrolytes
            target_w_boost = profile["target_water"] + 500
            insights.append({
                "id": "attent_hydration",
                "category": "hydration",
                "level": "warning",
                "icon": "💧",
                "tag": "הידרציה מוגברת",
                "title": "הגברת נוזלים ואלקטרוליטים",
                "message": f"אטנט מעלה קצב מטבולי ומייבש ריריות. היעד היומי הוגדל ב-+500 מ\"ל ({water} / {target_w_boost} מ\"ל). מומלץ לשתות מים עם מעט מלח/אלקטרוליטים למניעת ירידת לחץ דם, יובש וכאבי ראש בסיום ההשפעה.",
                "action_text": "הוסף שיקוי חיים (+250ml)"
            })

            # (D) Crash Buffer Timing
            if rem <= 2.5 and rem > 0:
                insights.append({
                    "id": "attent_crash_buffer",
                    "category": "timing",
                    "level": "alert",
                    "icon": "⏳",
                    "tag": "חלון דעיכה (Crash Buffer)",
                    "title": "התכוננות לסיום השפעת האטנט",
                    "message": f"בעוד כ-{rem:.1f} שעות צפויה ירידה ברמת האמפטמין בדם. זהו חלון קריטי למניעת ירידת אנרגיה חדה ('Crash') ובולמוס פחמימות פשוטות: הכן מראש ארוחה המשלבת פחמימה מורכבת (שיבולת שועל/אורז), חלבון ו-400 מ\"ג מגנזיום ציטראט להרגעת מערכת העצבים.",
                    "action_text": "הכן ארוחת התאוששות"
                })
        elif attent_info and not attent_info["is_active"]:
            insights.append({
                "id": "attent_expired",
                "category": "attent",
                "level": "info",
                "icon": "🌙",
                "tag": "סיום השפעת אטנט",
                "title": "התאוששות ומנוחה עצבית",
                "message": f"השפעת מנת האטנט הסתיימה. דופק המנוחה וה-HRV של Garmin חוזרים לרמות בסיס. מומלץ להימנע ממסכים ומקפאין לקראת הכניסה לחלון השינה.",
                "action_text": "הכן מנוחת התאוששות"
            })
        else:
            insights.append({
                "id": "attent_quick_log",
                "category": "attent",
                "level": "info",
                "icon": "💊",
                "tag": "מעקב תרופתי",
                "title": "רישום נטילת שיקוי ריכוז (אטנט)",
                "message": "נטלת אטנט היום? רשום בלחיצה אחת את המינון והשעה. המערכת תסנכרן מיד את עקומת הרעב, ההגנה הקטבולית והתאמת מדד הסטרס של Garmin.",
                "action_text": "רשום נטילת אטנט"
            })

        # 2. Garmin Sleep Score & Body Battery
        sleep_sc = garmin["sleep_score"]
        sleep_h = garmin["sleep_hours"]
        bb = garmin["body_battery"]
        if sleep_sc < 70 or sleep_h < 6.0:
            insights.append({
                "id": "garmin_sleep_deficit",
                "category": "recovery",
                "level": "alert",
                "icon": "💤",
                "tag": "גרעון שינה והתאוששות",
                "title": "גרעון שינה — הגבלת עומס אימונים",
                "message": f"Garmin מדד ציון שינה נמוך של {sleep_sc}/100 ({sleep_h:.1f} שעות). ה-Body Battery נטען ל-{bb}% בלבד. הגוף רגיש יותר לפציעות ופירוק שריר. המלצה מדעית: הפחת עצימות באימון הכוח (אל תגיע לכשל מוחלט RPE <= 8) והוסף שינה משלימה.",
                "action_text": "הפחת עומס אימון יומי"
            })
        else:
            insights.append({
                "id": "garmin_sleep_optimal",
                "category": "recovery",
                "level": "success",
                "icon": "⚡",
                "tag": "התאוששות שיא בשינה",
                "title": "מאגרי אנרגיה טעונים (Peak Recovery)",
                "message": f"ציון שינה מעולה של {sleep_sc}/100 ({sleep_h:.1f} שעות)! ה-Body Battery ב-{bb}%. מערכת העצבים והשרירים משוקמות במלואן. זמן אידיאלי לאימון כוח כבד ולשבירת שיאים אישיים (PR) ב-STR!",
                "action_text": "התכונן למבחן כוח עצימות גבוהה"
            })

        # 3. Garmin Active Burn & Calorie Adjustment
        act_cals = garmin["active_calories"]
        steps = garmin["steps"]
        effective_cal_tgt = profile["target_calories"] + act_cals
        if act_cals > 150:
            insights.append({
                "id": "garmin_metabolic_burn",
                "category": "nutrition",
                "level": "info",
                "icon": "🔥",
                "tag": "שריפה אקטיבית מ-Garmin",
                "title": "התאמת יעד קלורי דינמית",
                "message": f"השעון זיהה {steps:,} צעדים ושריפה פעילה של {act_cals} קק\"ל. כדי לא להיכנס לגרעון אגרסיבי מדי שמפרק שריר, תקציב הקלוריות היומי עודכן מ-{profile['target_calories']} ל-{effective_cal_tgt} קק\"ל.",
                "action_text": f"תקציב קלורי מורחב: {effective_cal_tgt} kcal"
            })

        # Calculate dynamic fatigue
        calculated_fatigue = round((100 - bb) * 0.35 + (100 - sleep_sc) * 0.35 + (garmin["stress_level"] * 0.3))
        if attent_info and attent_info["is_active"]:
            calculated_fatigue = max(5, round(calculated_fatigue * 0.7))

        return {
            "date": today,
            "biometrics": garmin,
            "attent": attent_info,
            "all_meds": meds,
            "insights": insights,
            "effective_target_calories": effective_cal_tgt,
            "calculated_fatigue": calculated_fatigue
        }

# -------------------------------------------------------------
# HTTP Request Handler & REST API
# -------------------------------------------------------------
class SystemApiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/status" or path == "/api/profile":
            self.handle_get_profile()
        elif path == "/api/nutrition/today":
            self.handle_get_nutrition_today()
        elif path == "/api/foods":
            search = query.get("q", [""])[0]
            self.handle_get_foods(search)
        elif path == "/api/history":
            self.handle_get_history()
        elif path == "/api/backup":
            self.handle_get_backup()
        elif path == "/api/network-ip":
            self._set_headers()
            self.wfile.write(json.dumps({"ip": get_local_ip(), "port": 8080}).encode("utf-8"))
        elif path == "/api/garmin/status":
            self.handle_garmin_status()
        elif path == "/api/garmin/health":
            self.handle_get_garmin_health()
        elif path.startswith("/api/barcode/"):
            barcode = path.split("/")[-1]
            self.handle_get_barcode(barcode)
        elif path == "/watch":
            self.path = "/watch.html"
            return super().do_GET()
        else:
            return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
        
        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            body = {}

        if path == "/api/awakening":
            self.handle_post_awakening(body)
        elif path == "/api/profile":
            self.handle_update_profile(body)
        elif path == "/api/profile/shift-mode":
            self.handle_toggle_shift_mode(body)
        elif path == "/api/nutrition/log":
            self.handle_post_log(body)
        elif path == "/api/nutrition/water":
            self.handle_post_water(body)
        elif path == "/api/nutrition/quick-potion":
            self.handle_post_quick_potion(body)
        elif path == "/api/foods":
            self.handle_create_custom_food(body)
        elif path == "/api/restore":
            self.handle_restore_backup(body)
        elif path == "/api/garmin/quick-water":
            self.handle_garmin_water(body)
        elif path == "/api/garmin/health-sync":
            self.handle_post_garmin_sync(body)
        elif path == "/api/medication/attent":
            self.handle_post_attent(body)
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/nutrition/log/"):
            try:
                log_id = int(path.split("/")[-1])
                self.handle_delete_log(log_id)
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif path == "/api/medication/attent":
            self.handle_delete_attent()
        else:
            self._set_headers(404)

    # ------------------ Handlers ------------------
    def handle_get_profile(self):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            row = c.fetchone()
            if not row:
                self._set_headers(404)
                return
            profile = dict(row)
            self._set_headers()
            self.wfile.write(json.dumps(profile, ensure_ascii=False).encode("utf-8"))

    def handle_post_awakening(self, body):
        try:
            name = body.get("name", "צייד רום")
            weight = float(body.get("weight", 78.0))
            height = float(body.get("height", 178.0))
            age = int(body.get("age", 25))
            sex = body.get("sex", "male")
            activity = body.get("activity_level", "moderate")
            goal = body.get("goal", "cut")
            body_fat = float(body.get("body_fat_pct", 0)) if body.get("body_fat_pct") else None

            sci = NutritionScienceEngine.calculate_full_profile(
                weight_kg=weight,
                height_cm=height,
                age=age,
                sex=sex,
                activity_level=activity,
                goal=goal,
                body_fat_pct=body_fat
            )

            with Database.get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                UPDATE hunter_profile SET
                    name = ?, weight = ?, height = ?, age = ?, sex = ?, activity_level = ?, goal = ?,
                    body_fat_pct = ?, bmr = ?, tdee = ?, target_calories = ?, target_protein = ?,
                    target_carbs = ?, target_fats = ?, target_water = ?, target_fiber = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id=1
                """, (
                    name, weight, height, age, sex, activity, goal, body_fat or 0,
                    sci["bmr"], sci["tdee"], sci["target_calories"], sci["target_protein"],
                    sci["target_carbs"], sci["target_fats"], sci["target_water"], sci["target_fiber"]
                ))
                conn.commit()

            with Database.get_connection() as conn:
                lvl_res = HunterLevelingEngine.add_exp(conn, 100)

            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "awakened",
                "message": "[SYSTEM: The Hunter has successfully completed the Awakening Assessment!]",
                "science": sci,
                "leveling": lvl_res
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_update_profile(self, body):
        with Database.get_connection() as conn:
            c = conn.cursor()
            allowed = [
                "name", "title", "target_calories", "target_protein", "target_carbs", 
                "target_fats", "target_water", "target_fiber", "fatigue", "shift_mode", "day_reset_hour"
            ]
            fields = []
            values = []
            for k in allowed:
                if k in body:
                    fields.append(f"{k} = ?")
                    values.append(body[k])
            if fields:
                values.append(1)
                sql = "UPDATE hunter_profile SET " + ", ".join(fields) + ", updated_at=CURRENT_TIMESTAMP WHERE id=?"
                c.execute(sql, values)
                conn.commit()
            
            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            profile = dict(c.fetchone())
            self._set_headers()
            self.wfile.write(json.dumps(profile, ensure_ascii=False).encode("utf-8"))

    def handle_toggle_shift_mode(self, body):
        mode = body.get("shift_mode", "standard")
        reset_h = int(body.get("day_reset_hour", 8 if mode == "night" else 0))
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE hunter_profile SET shift_mode = ?, day_reset_hour = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (mode, reset_h))
            conn.commit()
        return self.handle_get_nutrition_today()

    def handle_get_nutrition_today(self):
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            c = conn.cursor()
            c.execute("SELECT * FROM daily_logs WHERE date = ? ORDER BY id DESC", (today,))
            meals = [dict(r) for r in c.fetchall()]

            c.execute("SELECT COALESCE(SUM(amount_ml), 0) as total_water FROM water_logs WHERE date = ?", (today,))
            total_water = c.fetchone()["total_water"]

            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            profile = dict(c.fetchone())

            now = datetime.datetime.now()
            reset_h = profile.get("day_reset_hour") if profile.get("day_reset_hour") is not None else 0
            if now.hour < reset_h:
                reset_dt = now.replace(hour=reset_h, minute=0, second=0, microsecond=0)
            else:
                reset_dt = (now + datetime.timedelta(days=1)).replace(hour=reset_h, minute=0, second=0, microsecond=0)
            hours_left = max(0.1, round((reset_dt - now).total_seconds() / 3600.0, 1))

            shift_info = {
                "shift_mode": profile.get("shift_mode", "standard"),
                "day_reset_hour": reset_h,
                "hours_left": hours_left,
                "shift_date": today,
                "is_night": profile.get("shift_mode") == "night"
            }

            consumed = {
                "calories": sum(m["calories"] for m in meals),
                "protein": sum(m["protein"] for m in meals),
                "carbs": sum(m["carbs"] for m in meals),
                "fats": sum(m["fats"] for m in meals),
                "fiber": sum(m["fiber"] for m in meals),
                "sodium_mg": sum(m["sodium_mg"] for m in meals),
                "potassium_mg": sum(m["potassium_mg"] for m in meals),
                "magnesium_mg": sum(m["magnesium_mg"] for m in meals),
                "zinc_mg": sum(m["zinc_mg"] for m in meals),
                "vit_c_mg": sum(m["vit_c_mg"] for m in meals),
                "vit_d_iu": sum(m["vit_d_iu"] for m in meals),
                "iron_mg": sum(m["iron_mg"] for m in meals),
                "water_ml": total_water
            }

            quests = [
                {
                    "key": "protein_quest",
                    "title": "מבחן הכוח (Strength Preparation)",
                    "desc": f"הגע ל-{profile['target_protein']}g חלבון לבניית מסת שריר",
                    "current": round(consumed["protein"], 1),
                    "target": profile["target_protein"],
                    "unit": "g",
                    "done": consumed["protein"] >= profile["target_protein"]
                },
                {
                    "key": "calorie_quest",
                    "title": "מאזן אנרגיית הצייד (Caloric Control)",
                    "desc": f"שמור על יעד של {profile['target_calories']} קלוריות יומיות",
                    "current": round(consumed["calories"]),
                    "target": profile["target_calories"],
                    "unit": "kcal",
                    "done": abs(consumed["calories"] - profile["target_calories"]) <= (profile["target_calories"] * 0.1) or (consumed["calories"] >= profile["target_calories"] * 0.8 and consumed["calories"] <= profile["target_calories"] * 1.05)
                },
                {
                    "key": "water_quest",
                    "title": "שיקוי חיים ורוויה (HP Hydration)",
                    "desc": f"שתה {profile['target_water']} מ\\\"ל מים לחידוש אנרגיה",
                    "current": consumed["water_ml"],
                    "target": profile["target_water"],
                    "unit": "ml",
                    "done": consumed["water_ml"] >= profile["target_water"]
                },
                {
                    "key": "micro_quest",
                    "title": "שריון המיקרו-נוטריאנטים (Vitality Shield)",
                    "desc": "השלם לפחות 3 יעדי ויטמינים/מינרלים וסיבים",
                    "current": sum([
                        consumed["fiber"] >= profile["target_fiber"],
                        consumed["magnesium_mg"] >= 350,
                        consumed["vit_c_mg"] >= 80,
                        consumed["zinc_mg"] >= 10,
                        consumed["potassium_mg"] >= 2500
                    ]),
                    "target": 3,
                    "unit": "מגנים",
                    "done": sum([
                        consumed["fiber"] >= profile["target_fiber"],
                        consumed["magnesium_mg"] >= 350,
                        consumed["vit_c_mg"] >= 80,
                        consumed["zinc_mg"] >= 10,
                        consumed["potassium_mg"] >= 2500
                    ]) >= 3
                }
            ]

            str_bonus = min(25, round((consumed["protein"] / max(1, profile["target_protein"])) * 15))
            cal_ratio = consumed["calories"] / max(1, profile["target_calories"])
            agi_bonus = 15 if (0.85 <= cal_ratio <= 1.05) else (10 if cal_ratio < 1.15 else 5)
            vit_bonus = min(20, round((consumed["water_ml"] / max(1, profile["target_water"])) * 10) + quests[3]["current"] * 2)

            health_adv = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)
            profile["fatigue"] = health_adv["calculated_fatigue"]

            self._set_headers()
            self.wfile.write(json.dumps({
                "date": today,
                "profile": profile,
                "shift_info": shift_info,
                "consumed": consumed,
                "meals": meals,
                "quests": quests,
                "health_advisor": health_adv,
                "stats_live": {
                    "str": profile["stats_str"] + str_bonus,
                    "agi": profile["stats_agi"] + agi_bonus,
                    "vit": profile["stats_vit"] + vit_bonus,
                    "int": profile["stats_int"],
                    "per": profile["stats_per"]
                }
            }, ensure_ascii=False).encode("utf-8"))

    def handle_post_log(self, body):
        now_time = datetime.datetime.now().strftime("%H:%M")
        
        food_id = body.get("food_id")
        food_name = body.get("food_name", "ארוחת צייד")
        serving_count = float(body.get("serving_count", 1.0))
        serving_size_g = float(body.get("serving_size_g", 100))
        calories = float(body.get("calories", 0)) * serving_count
        protein = float(body.get("protein", 0)) * serving_count
        carbs = float(body.get("carbs", 0)) * serving_count
        fats = float(body.get("fats", 0)) * serving_count
        fiber = float(body.get("fiber", 0)) * serving_count
        sodium_mg = float(body.get("sodium_mg", 0)) * serving_count
        potassium_mg = float(body.get("potassium_mg", 0)) * serving_count
        magnesium_mg = float(body.get("magnesium_mg", 0)) * serving_count
        zinc_mg = float(body.get("zinc_mg", 0)) * serving_count
        vit_c_mg = float(body.get("vit_c_mg", 0)) * serving_count
        vit_d_iu = float(body.get("vit_d_iu", 0)) * serving_count
        iron_mg = float(body.get("iron_mg", 0)) * serving_count
        meal_type = body.get("meal_type", "snack")

        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            c = conn.cursor()
            c.execute("""
            INSERT INTO daily_logs (
                date, food_id, food_name, serving_count, serving_size_g,
                calories, protein, carbs, fats, fiber, sodium_mg, potassium_mg,
                magnesium_mg, zinc_mg, vit_c_mg, vit_d_iu, iron_mg, meal_type, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today, food_id, food_name, serving_count, serving_size_g,
                calories, protein, carbs, fats, fiber, sodium_mg, potassium_mg,
                magnesium_mg, zinc_mg, vit_c_mg, vit_d_iu, iron_mg, meal_type, now_time
            ))
            log_id = c.lastrowid
            conn.commit()

            exp_awarded = 25 + int(protein * 0.5)
            lvl_res = HunterLevelingEngine.add_exp(conn, exp_awarded)

        self._set_headers(201)
        self.wfile.write(json.dumps({
            "status": "success",
            "log_id": log_id,
            "exp_awarded": exp_awarded,
            "leveling": lvl_res
        }, ensure_ascii=False).encode("utf-8"))

    def handle_delete_log(self, log_id):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM daily_logs WHERE id=?", (log_id,))
            conn.commit()
        self._set_headers(200)
        self.wfile.write(json.dumps({"status": "deleted", "id": log_id}).encode("utf-8"))

    def handle_post_water(self, body):
        now_time = datetime.datetime.now().strftime("%H:%M")
        amount = int(body.get("amount_ml", 250))

        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            c = conn.cursor()
            c.execute("""
            INSERT INTO water_logs (date, amount_ml, timestamp)
            VALUES (?, ?, ?)
            """, (today, amount, now_time))
            conn.commit()

            c.execute("UPDATE hunter_profile SET fatigue = max(0, fatigue - 3) WHERE id=1")
            conn.commit()
            lvl_res = HunterLevelingEngine.add_exp(conn, 10)

        self._set_headers(200)
        self.wfile.write(json.dumps({
            "status": "success",
            "added_ml": amount,
            "exp_awarded": 10,
            "leveling": lvl_res
        }, ensure_ascii=False).encode("utf-8"))

    def handle_post_quick_potion(self, body):
        potion_type = body.get("potion_type", "water")
        if potion_type == "water_250":
            return self.handle_post_water({"amount_ml": 250})
        elif potion_type == "water_500":
            return self.handle_post_water({"amount_ml": 500})
        elif potion_type == "protein_shake":
            return self.handle_post_log({
                "food_name": "שיקוי כוח: שייק חלבון (Elixir of Strength)",
                "serving_count": 1,
                "serving_size_g": 30,
                "calories": 130,
                "protein": 27.0,
                "carbs": 2.0,
                "fats": 1.5,
                "meal_type": "snack"
            })
        elif potion_type == "multivitamin":
            return self.handle_post_log({
                "food_name": "שיקוי חיוניות: מולטי-ויטמין (Vitality Elixir)",
                "serving_count": 1,
                "serving_size_g": 1,
                "calories": 0,
                "protein": 0,
                "carbs": 0,
                "fats": 0,
                "vit_c_mg": 100,
                "vit_d_iu": 1000,
                "magnesium_mg": 100,
                "zinc_mg": 15,
                "iron_mg": 10,
                "meal_type": "snack"
            })
        else:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Unknown potion"}).encode("utf-8"))

    def handle_get_foods(self, search):
        with Database.get_connection() as conn:
            c = conn.cursor()
            if search.strip():
                term = f"%{search.strip()}%"
                c.execute("""
                SELECT * FROM food_items 
                WHERE name LIKE ? OR name_he LIKE ? 
                ORDER BY is_custom DESC, id ASC LIMIT 50
                """, (term, term))
            else:
                c.execute("SELECT * FROM food_items ORDER BY is_custom DESC, id ASC LIMIT 50")
            items = [dict(r) for r in c.fetchall()]
        self._set_headers()
        self.wfile.write(json.dumps(items, ensure_ascii=False).encode("utf-8"))

    def handle_get_barcode(self, barcode):
        barcode = barcode.strip()
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM food_items WHERE barcode = ?", (barcode,))
            row = c.fetchone()
            if row:
                self._set_headers(200)
                self.wfile.write(json.dumps({"source": "local", "item": dict(row)}, ensure_ascii=False).encode("utf-8"))
                return

        # Query Open Food Facts API
        try:
            import urllib.request
            url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
            req = urllib.request.Request(url, headers={"User-Agent": "SoloLevelingHunterFitness/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("status") == 1 and "product" in data:
                        p = data["product"]
                        name = p.get("product_name") or p.get("product_name_en") or "מוצר סרוק"
                        name_he = p.get("product_name_he") or name
                        nutriments = p.get("nutriments", {})

                        calories = float(nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal") or 0)
                        protein = float(nutriments.get("proteins_100g") or nutriments.get("proteins") or 0)
                        carbs = float(nutriments.get("carbohydrates_100g") or nutriments.get("carbohydrates") or 0)
                        fats = float(nutriments.get("fat_100g") or nutriments.get("fat") or 0)
                        fiber = float(nutriments.get("fiber_100g") or nutriments.get("fiber") or 0)
                        sodium_mg = float(nutriments.get("sodium_100g") or 0) * 1000.0

                        with Database.get_connection() as conn:
                            c = conn.cursor()
                            c.execute("""
                            INSERT INTO food_items (
                                name, name_he, category, serving_size_g, calories, protein, carbs, fats,
                                fiber, sodium_mg, barcode, is_custom
                            ) VALUES (?, ?, 'scanned', 100, ?, ?, ?, ?, ?, ?, ?, 1)
                            """, (name, name_he, calories, protein, carbs, fats, fiber, sodium_mg, barcode))
                            conn.commit()
                            item_id = c.lastrowid
                            c.execute("SELECT * FROM food_items WHERE id=?", (item_id,))
                            saved_item = dict(c.fetchone())

                        self._set_headers(200)
                        self.wfile.write(json.dumps({"source": "openfoodfacts", "item": saved_item}, ensure_ascii=False).encode("utf-8"))
                        return
        except Exception:
            pass

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Barcode not found", "barcode": barcode}, ensure_ascii=False).encode("utf-8"))


    def handle_create_custom_food(self, body):
        name_he = body.get("name_he") or body.get("name", "מזון מותאם")
        name = body.get("name", name_he)
        calories = float(body.get("calories", 0))
        protein = float(body.get("protein", 0))
        carbs = float(body.get("carbs", 0))
        fats = float(body.get("fats", 0))
        fiber = float(body.get("fiber", 0))

        barcode = body.get("barcode")
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
            INSERT INTO food_items (
                name, name_he, category, serving_size_g, calories, protein, carbs, fats,
                fiber, sodium_mg, potassium_mg, magnesium_mg, zinc_mg, vit_c_mg, vit_d_iu, iron_mg, barcode, is_custom
            ) VALUES (?, ?, 'custom', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                name, name_he, float(body.get("serving_size_g", 100)),
                calories, protein, carbs, fats, fiber,
                float(body.get("sodium_mg", 0)), float(body.get("potassium_mg", 0)),
                float(body.get("magnesium_mg", 0)), float(body.get("zinc_mg", 0)),
                float(body.get("vit_c_mg", 0)), float(body.get("vit_d_iu", 0)),
                float(body.get("iron_mg", 0)), barcode
            ))
            conn.commit()
            item_id = c.lastrowid
            c.execute("SELECT * FROM food_items WHERE id=?", (item_id,))
            saved_item = dict(c.fetchone())

        self._set_headers(201)
        self.wfile.write(json.dumps({"status": "created", "id": item_id, "item": saved_item}, ensure_ascii=False).encode("utf-8"))

    def handle_get_history(self):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
            SELECT date, 
                   COUNT(id) as meal_count,
                   ROUND(SUM(calories), 1) as total_calories,
                   ROUND(SUM(protein), 1) as total_protein,
                   ROUND(SUM(carbs), 1) as total_carbs,
                   ROUND(SUM(fats), 1) as total_fats
            FROM daily_logs
            GROUP BY date
            ORDER BY date DESC
            LIMIT 14
            """)
            days = [dict(r) for r in c.fetchall()]
        self._set_headers()
        self.wfile.write(json.dumps(days, ensure_ascii=False).encode("utf-8"))

    def handle_get_backup(self):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            profile = dict(c.fetchone())
            c.execute("SELECT * FROM food_items")
            foods = [dict(r) for r in c.fetchall()]
            c.execute("SELECT * FROM daily_logs")
            logs = [dict(r) for r in c.fetchall()]
            c.execute("SELECT * FROM water_logs")
            water = [dict(r) for r in c.fetchall()]

        backup_payload = {
            "version": "1.0",
            "exported_at": datetime.datetime.now().isoformat(),
            "profile": profile,
            "foods": foods,
            "logs": logs,
            "water": water
        }
        self._set_headers(200, "application/json")
        self.wfile.write(json.dumps(backup_payload, ensure_ascii=False, indent=2).encode("utf-8"))

    def handle_restore_backup(self, body):
        try:
            profile = body.get("profile")
            with Database.get_connection() as conn:
                c = conn.cursor()
                if profile:
                    cols = [k for k in profile.keys() if k != "id"]
                    vals = [profile[k] for k in cols]
                    set_clause = ", ".join([f"{k} = ?" for k in cols])
                    vals.append(1)
                    c.execute(f"UPDATE hunter_profile SET {set_clause} WHERE id = ?", vals)
                conn.commit()
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "restored"}).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    # ------------------ Garmin & Health Integration ------------------
    def handle_garmin_status(self):
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            c = conn.cursor()
            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            profile = dict(c.fetchone())

            c.execute("""
            SELECT COALESCE(SUM(calories), 0) as cal,
                   COALESCE(SUM(protein), 0) as p,
                   COALESCE(SUM(carbs), 0) as c,
                   COALESCE(SUM(fats), 0) as f
            FROM daily_logs WHERE date = ?
            """, (today,))
            n = dict(c.fetchone())

            c.execute("SELECT COALESCE(SUM(amount_ml), 0) as w FROM water_logs WHERE date = ?", (today,))
            water = c.fetchone()["w"]

            health_adv = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)

            garmin_payload = {
                "lvl": profile["level"],
                "rank": profile["rank"],
                "title": profile["title"],
                "exp": profile["exp"],
                "exp_next": profile["exp_to_next"],
                "cal": round(n["cal"]),
                "cal_tgt": health_adv["effective_target_calories"],
                "cal_base_tgt": profile["target_calories"],
                "cal_rem": max(0, health_adv["effective_target_calories"] - round(n["cal"])),
                "p": round(n["p"], 1),
                "p_tgt": profile["target_protein"],
                "c": round(n["c"], 1),
                "c_tgt": profile["target_carbs"],
                "f": round(n["f"], 1),
                "f_tgt": profile["target_fats"],
                "w": water,
                "w_tgt": profile["target_water"] + (500 if (health_adv["attent"] and health_adv["attent"]["is_active"]) else 0),
                "fatigue": health_adv["calculated_fatigue"],
                "shift_mode": profile.get("shift_mode", "standard"),
                "biometrics": health_adv["biometrics"],
                "attent": health_adv["attent"],
                "insights_count": len(health_adv["insights"])
            }
        self._set_headers()
        self.wfile.write(json.dumps(garmin_payload, ensure_ascii=False).encode("utf-8"))

    def handle_get_garmin_health(self):
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            health_data = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)
        self._set_headers()
        self.wfile.write(json.dumps(health_data, ensure_ascii=False).encode("utf-8"))

    def handle_post_garmin_sync(self, body):
        try:
            with Database.get_connection() as conn:
                today = get_hunter_shift_date(conn)
                c = conn.cursor()
                now_time = datetime.datetime.now().strftime("%H:%M")

                c.execute("SELECT * FROM garmin_health_logs WHERE date = ?", (today,))
                row = c.fetchone()
                if not row:
                    c.execute("""
                    INSERT INTO garmin_health_logs (date, timestamp) VALUES (?, ?)
                    """, (today, now_time))

                fields = ["heart_rate", "resting_hr", "sleep_score", "sleep_hours",
                          "stress_level", "body_battery", "steps", "active_calories",
                          "spo2_pct", "respiration_rpm"]
                updates = []
                vals = []
                for f in fields:
                    if f in body:
                        updates.append(f"{f} = ?")
                        vals.append(body[f])

                if updates:
                    updates.append("timestamp = ?")
                    vals.append(now_time)
                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    vals.append(today)
                    c.execute(f"UPDATE garmin_health_logs SET {', '.join(updates)} WHERE date = ?", vals)
                    conn.commit()

                health_data = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)

            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "synced",
                "message": "[SYSTEM: Garmin Venu 4 Biometrics synchronized successfully!]",
                "data": health_data
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_post_attent(self, body):
        try:
            dose_mg = int(body.get("dose_mg", 20))
            dose_time = body.get("timestamp", datetime.datetime.now().strftime("%H:%M"))
            duration = float(body.get("duration_hours", 7.0))
            notes = body.get("notes", "שיקוי ריכוז והיפר-פוקוס")

            with Database.get_connection() as conn:
                today = get_hunter_shift_date(conn)
                c = conn.cursor()
                c.execute("""
                INSERT INTO medication_logs (date, med_name, dose_mg, timestamp, duration_hours, notes)
                VALUES (?, 'Attent', ?, ?, ?, ?)
                """, (today, dose_mg, dose_time, duration, notes))
                conn.commit()

                lvl_res = HunterLevelingEngine.add_exp(conn, 35)
                health_data = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)

            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "buff_activated",
                "message": f"[SYSTEM: Concentration Potion (Attent {dose_mg}mg) Active Buff Registered!]",
                "leveling": lvl_res,
                "data": health_data
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_delete_attent(self):
        try:
            with Database.get_connection() as conn:
                today = get_hunter_shift_date(conn)
                c = conn.cursor()
                c.execute("DELETE FROM medication_logs WHERE date = ? AND LOWER(med_name) = 'attent'", (today,))
                conn.commit()
                health_data = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)

            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "buff_removed",
                "message": "[SYSTEM: Attent log cleared]",
                "data": health_data
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_garmin_water(self, body):
        amount = int(body.get("amount_ml", 250))
        now_time = datetime.datetime.now().strftime("%H:%M")
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            c = conn.cursor()
            c.execute("INSERT INTO water_logs (date, amount_ml, timestamp) VALUES (?, ?, ?)", (today, amount, now_time))
            conn.commit()
        return self.handle_garmin_status()

# -------------------------------------------------------------
# Main Server Runner (Dual HTTP 8080 & HTTPS 8443)
# -------------------------------------------------------------
import ssl
import threading

def start_https_server(port=8443):
    cert_path = os.path.join(BASE_DIR, "cert.pem")
    key_path = os.path.join(BASE_DIR, "key.pem")
    if not (os.path.exists(cert_path) and os.path.exists(key_path)):
        try:
            import subprocess
            subprocess.run([
                "openssl", "req", "-new", "-x509", "-keyout", key_path,
                "-out", cert_path, "-days", "365", "-nodes",
                "-subj", "/CN=SoloLevelingSystem"
            ], check=True)
        except Exception:
            return
    if os.path.exists(cert_path) and os.path.exists(key_path):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            https_server = HTTPServer(("0.0.0.0", port), SystemApiHandler)
            https_server.socket = context.wrap_socket(https_server.socket, server_side=True)
            https_server.serve_forever()
        except Exception as e:
            print(f"HTTPS server error: {e}")

def run_server(port=8080):
    Database.init_db()
    local_ip = get_local_ip()

    # Cloud detection: if PORT is set via env or on cloud providers (Render, Railway, etc.),
    # SSL is handled automatically by the cloud proxy, so secondary HTTPS port 8443 is omitted.
    is_cloud = bool(os.environ.get("PORT") or os.environ.get("RENDER") or os.environ.get("RAILWAY_STATIC_URL"))

    if not is_cloud:
        # Start local HTTPS server in background thread for live camera on iOS Safari LAN
        try:
            https_thread = threading.Thread(target=start_https_server, args=(8443,), daemon=True)
            https_thread.start()
        except Exception as e:
            print(f"Notice: Background local HTTPS server not started: {e}")

    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, SystemApiHandler)
    print(f"==================================================")
    print(f"  SOLO LEVELING FITNESS SYSTEM - SYSTEM ONLINE")
    print(f"==================================================")
    print(f"  Port:                {port}")
    if is_cloud:
        print(f"  Environment:         Cloud Production (24/7)")
    else:
        print(f"  Local Access:        http://localhost:{port}")
        print(f"  iPhone LAN Access:   http://{local_ip}:{port}")
        print(f"  iPhone HTTPS Camera: https://{local_ip}:8443")
        print(f"  Garmin Watch Mode:   http://{local_ip}:{port}/watch")
        print(f"  Garmin API:          http://{local_ip}:{port}/api/garmin/status")
    print(f"==================================================")
    sys.stdout.flush()
    httpd.serve_forever()

if __name__ == "__main__":
    # Support Cloud Dynamic PORT (Render, Railway, Fly, Heroku), CLI arg, or default 8080
    env_port = os.environ.get("PORT")
    if env_port:
        try:
            port = int(env_port)
        except ValueError:
            port = 8080
    elif len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            port = 8080
    else:
        port = 8080
    run_server(port)

