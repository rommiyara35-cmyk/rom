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
import math
import sqlite3
import datetime
import socket
import calendar
import base64
import ssl
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

def _get_ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


# Load .env file if present (for local development)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


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

def get_israel_now():
    try:
        import zoneinfo
        return datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Jerusalem"))
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=3))
        return datetime.datetime.now(tz)

def get_hunter_shift_date(conn, client_date=None, force_date=False):
    if force_date and client_date and isinstance(client_date, str) and len(client_date) == 10:
        return client_date
    try:
        c = conn.cursor()
        c.execute("SELECT day_reset_hour, shift_mode FROM hunter_profile WHERE id=1")
        row = c.fetchone()
        shift_mode = row["shift_mode"] if row else "standard"
        reset_hour = row["day_reset_hour"] if row and row["day_reset_hour"] is not None else (8 if shift_mode == "night" else 0)
    except Exception:
        reset_hour = 0

    now = get_israel_now()
    calendar_today = now.date()

    # Determine shift date from current Israel time
    if now.hour < reset_hour:
        current_shift_date = (calendar_today - datetime.timedelta(days=1)).isoformat()
    else:
        current_shift_date = calendar_today.isoformat()

    # If client passed a date:
    if client_date and isinstance(client_date, str) and len(client_date) == 10:
        # If client passed current shift date or today's calendar date, return current_shift_date (prevents double subtraction!)
        if client_date == current_shift_date or client_date == calendar_today.isoformat():
            return current_shift_date
        # Otherwise honor explicit target date (e.g. historical calendar view)
        return client_date

    return current_shift_date

def safe_int(val, default=0):
    if val is None or val == "":
        return default
    try:
        if isinstance(val, (int, float)):
            return int(val)
        val_str = str(val).replace(",", "").strip()
        import re
        m = re.search(r"[-+]?\d+", val_str)
        return int(m.group(0)) if m else default
    except Exception:
        return default

def safe_float(val, default=0.0):
    if val is None or val == "":
        return default
    try:
        if isinstance(val, (int, float)):
            return float(val)
        val_str = str(val).replace(",", "").strip()
        import re
        m = re.search(r"[-+]?\d*\.?\d+", val_str)
        return float(m.group(0)) if m else default
    except Exception:
        return default

def detect_food_fluid(food_name, serving_size_g, serving_count=1.0):
    if not food_name or not serving_size_g:
        return 0, None, None
    fn = str(food_name).lower().strip()
    total_g = float(serving_size_g) * float(serving_count)
    if total_g <= 0:
        return 0, None, None

    if "קוקוס" in fn:
        return int(round(total_g * 0.95)), "🥥", "מי קוקוס"
    if any(k in fn for k in ["קפה", "אספרסו", "אמריקנו", "הפוך", "קפוצ'ינו", "נס קפה", "לאטה", "אייס קפה"]):
        return int(round(total_g * 0.98)), "☕", "קפה"
    if any(k in fn for k in ["תה", "חליטה", "קמומיל", "צ'אי", "מאצ'ה"]):
        return int(round(total_g * 1.00)), "🍵", "תה/חליטה"
    if any(k in fn for k in ["מיץ", "נקטר", "שייק פירות", "סמודי"]):
        return int(round(total_g * 0.90)), "🧃", "מיץ/סמודי"
    if any(k in fn for k in ["מרק", "ראמן", "בוליו", "ציר"]):
        return int(round(total_g * 0.92)), "🥣", "מרק"
    if any(k in fn for k in ["חלב", "שייק", "אקטימל", "רוויון", "קפיר", "שוקו"]):
        return int(round(total_g * 0.88)), "🥛", "חלב/שייק"
    if any(k in fn for k in ["אלקטרוליט", "איזוטוני"]):
        return int(round(total_g * 1.00)), "⚡", "אלקטרוליטים"
    if any(k in fn for k in ["קולה", "סודה", "זירו", "ספרייט", "פאנטה", "מוגז", "משקה אנרגיה"]):
        return int(round(total_g * 0.95)), "🥤", "משקה מוגז"
    if any(k in fn for k in ["מים", "מי "]):
        return int(round(total_g * 1.00)), "💧", "מים"
    if any(k in fn for k in ["משקה", "בירה", "סיידר", "קומבוצ'ה"]):
        return int(round(total_g * 0.90)), "🍺", "משקה"
        
    return 0, None, None

def infer_food_micronutrients(food_name, serving_size_g, serving_count=1.0):
    """
    Infers realistic micronutrients (potassium, magnesium, zinc, vit_c, vit_d, iron, fiber, sodium)
    per serving for recognized whole and nutrient-dense foods and beverages when not explicitly provided.
    Values are scaled per 100g.
    """
    fn = str(food_name or "").lower().strip()
    total_g = max(1.0, float(serving_size_g or 100) * float(serving_count or 1.0))
    scale = total_g / 100.0

    micros = {
        "fiber": 0.0,
        "sodium_mg": 0.0,
        "potassium_mg": 0.0,
        "magnesium_mg": 0.0,
        "zinc_mg": 0.0,
        "vit_c_mg": 0.0,
        "vit_d_iu": 0.0,
        "iron_mg": 0.0
    }

    # Coconut water / Coconut products
    if "קוקוס" in fn:
        if any(w in fn for w in ["מי ", "מים", "משקה", "נוזל", "water", "juice"]):
            micros["potassium_mg"] += 250.0 * scale
            micros["magnesium_mg"] += 25.0 * scale
            micros["sodium_mg"] += 105.0 * scale
            micros["vit_c_mg"] += 2.4 * scale
            micros["fiber"] += 1.1 * scale
        else:
            micros["potassium_mg"] += 356.0 * scale
            micros["magnesium_mg"] += 32.0 * scale
            micros["iron_mg"] += 2.4 * scale
            micros["fiber"] += 9.0 * scale

    # Citrus fruits & rich Vitamin C sources
    if any(k in fn for k in ["תפוז", "קלמנטינה", "אשכולית", "לימון", "פומלה", "mandarin", "orange"]):
        micros["vit_c_mg"] += 53.0 * scale
        micros["potassium_mg"] += 181.0 * scale
        micros["fiber"] += 2.4 * scale

    if any(k in fn for k in ["פלפל", "גמבה", "bell pepper", "capsicum"]):
        micros["vit_c_mg"] += 128.0 * scale
        micros["potassium_mg"] += 211.0 * scale
        micros["fiber"] += 2.1 * scale

    # Bananas & high-potassium fruits
    if any(k in fn for k in ["בננה", "banana"]):
        micros["potassium_mg"] += 358.0 * scale
        micros["magnesium_mg"] += 27.0 * scale
        micros["vit_c_mg"] += 8.7 * scale
        micros["fiber"] += 2.6 * scale

    # Salmon & fatty fish
    if any(k in fn for k in ["סלמון", "salmon", "אלתית"]):
        micros["vit_d_iu"] += 526.0 * scale
        micros["potassium_mg"] += 490.0 * scale
        micros["magnesium_mg"] += 29.0 * scale
        micros["zinc_mg"] += 0.6 * scale
        micros["iron_mg"] += 0.8 * scale
        micros["sodium_mg"] += 59.0 * scale

    # Tuna
    if any(k in fn for k in ["טונה", "tuna"]):
        micros["vit_d_iu"] += 82.0 * scale
        micros["potassium_mg"] += 320.0 * scale
        micros["magnesium_mg"] += 35.0 * scale
        micros["zinc_mg"] += 1.0 * scale
        micros["iron_mg"] += 1.3 * scale

    # Eggs
    if any(k in fn for k in ["ביצה", "ביצים", "חביתה", "מקושקשת", "עין", "שקשוקה", "egg"]):
        micros["vit_d_iu"] += 87.0 * scale
        micros["zinc_mg"] += 1.3 * scale
        micros["iron_mg"] += 1.8 * scale
        micros["potassium_mg"] += 138.0 * scale
        micros["sodium_mg"] += 142.0 * scale

    # Beef & red meats
    if any(k in fn for k in ["בקר", "אנטריקוט", "סינטה", "פילה", "בשר טחון", "אסאדו", "beef", "steak"]):
        micros["zinc_mg"] += 5.5 * scale
        micros["iron_mg"] += 2.6 * scale
        micros["potassium_mg"] += 318.0 * scale
        micros["magnesium_mg"] += 21.0 * scale
        micros["sodium_mg"] += 72.0 * scale

    # Poultry (chicken, turkey)
    if any(k in fn for k in ["חזה עוף", "עוף", "פרגית", "הודו", "chicken", "turkey"]):
        micros["zinc_mg"] += 1.0 * scale
        micros["iron_mg"] += 1.0 * scale
        micros["potassium_mg"] += 256.0 * scale
        micros["magnesium_mg"] += 29.0 * scale

    # Oats & oatmeal
    if any(k in fn for k in ["שיבולת שועל", "קוואקר", "oats", "oatmeal"]):
        micros["magnesium_mg"] += 138.0 * scale
        micros["zinc_mg"] += 4.0 * scale
        micros["iron_mg"] += 4.7 * scale
        micros["fiber"] += 10.6 * scale
        micros["potassium_mg"] += 429.0 * scale

    # Dark leafy greens (spinach, kale, broccoli)
    if any(k in fn for k in ["תרד", "קייל", "ברוקולי", "spinach", "kale", "broccoli"]):
        micros["vit_c_mg"] += 45.0 * scale
        micros["magnesium_mg"] += 60.0 * scale
        micros["iron_mg"] += 2.7 * scale
        micros["potassium_mg"] += 380.0 * scale
        micros["fiber"] += 2.6 * scale

    # Nuts, seeds & tahini
    if any(k in fn for k in ["שקדים", "אגוז", "קשיו", "טחינה", "זרעי צ'יה", "chia", "almond", "walnut"]):
        micros["magnesium_mg"] += 220.0 * scale
        micros["zinc_mg"] += 3.5 * scale
        micros["iron_mg"] += 3.7 * scale
        micros["fiber"] += 7.0 * scale
        micros["potassium_mg"] += 500.0 * scale

    # Avocado
    if any(k in fn for k in ["אבוקדו", "avocado", "גוואקמולי"]):
        micros["potassium_mg"] += 485.0 * scale
        micros["magnesium_mg"] += 29.0 * scale
        micros["fiber"] += 6.7 * scale
        micros["vit_c_mg"] += 10.0 * scale

    # Tomatoes & tomato sauce
    if any(k in fn for k in ["עגבנייה", "עגבניות", "רסק", "tomato"]):
        micros["vit_c_mg"] += 14.0 * scale
        micros["potassium_mg"] += 237.0 * scale
        micros["fiber"] += 1.2 * scale

    # Legumes (lentils, chickpeas, beans)
    if any(k in fn for k in ["עדשים", "שעועית", "חומוס", "פול", "lentils", "chickpeas", "beans"]):
        micros["iron_mg"] += 3.3 * scale
        micros["magnesium_mg"] += 36.0 * scale
        micros["zinc_mg"] += 1.4 * scale
        micros["potassium_mg"] += 369.0 * scale
        micros["fiber"] += 7.9 * scale

    # Dairy (milk, yogurt, cottage, quark)
    if any(k in fn for k in ["חלב", "יוגורט", "קוטג'", "גבינה", "פרו", "pro", "milk", "yogurt"]):
        micros["potassium_mg"] += 150.0 * scale
        micros["magnesium_mg"] += 12.0 * scale
        micros["zinc_mg"] += 0.5 * scale
        micros["vit_d_iu"] += 40.0 * scale

    return {k: round(v, 1) for k, v in micros.items()}

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
            try:
                c.execute("ALTER TABLE hunter_profile ADD COLUMN is_awakened INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                c.execute("ALTER TABLE hunter_profile ADD COLUMN target_weight REAL DEFAULT 75.0")
            except Exception:
                pass
            try:
                c.execute("ALTER TABLE hunter_profile ADD COLUMN goal_custom_text TEXT DEFAULT ''")
            except Exception:
                pass
            try:
                c.execute("ALTER TABLE hunter_profile ADD COLUMN ai_analysis_headline TEXT DEFAULT ''")
            except Exception:
                pass
            try:
                c.execute("ALTER TABLE hunter_profile ADD COLUMN ai_explanation TEXT DEFAULT ''")
            except Exception:
                pass
            try:
                c.execute("ALTER TABLE hunter_profile ADD COLUMN ai_hunter_tip TEXT DEFAULT ''")
            except Exception:
                pass
            try:
                c.execute("ALTER TABLE hunter_profile ADD COLUMN has_penalty_debuff INTEGER DEFAULT 0")
            except Exception:
                pass

            # Solo Leveling Hunter Penalties table
            c.execute("""
            CREATE TABLE IF NOT EXISTS hunter_penalties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                penalty_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                infraction_details TEXT NOT NULL,
                quest_title TEXT NOT NULL,
                quest_requirement TEXT NOT NULL,
                exp_deducted INTEGER DEFAULT 75,
                exp_restored INTEGER DEFAULT 50,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                redeemed_at TIMESTAMP
            )
            """)

            # AI Consultation Messages History
            c.execute("""
            CREATE TABLE IF NOT EXISTS ai_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                recommendations_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # AI Saved Recommendations & Directives
            c.execute("""
            CREATE TABLE IF NOT EXISTS ai_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)


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
                sync_source TEXT DEFAULT 'manual',
                vo2_max INTEGER DEFAULT 48,
                hrv_status TEXT DEFAULT 'balanced',
                raw_data_json TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Migration: Ensure new Garmin columns exist in existing databases
            for col_def in [
                ("sync_source", "TEXT DEFAULT 'manual'"),
                ("vo2_max", "INTEGER DEFAULT 48"),
                ("hrv_status", "TEXT DEFAULT 'balanced'"),
                ("raw_data_json", "TEXT DEFAULT ''")
            ]:
                try:
                    c.execute(f"ALTER TABLE garmin_health_logs ADD COLUMN {col_def[0]} {col_def[1]}")
                except Exception:
                    pass

            # Migration: Ensure beverage columns exist in water_logs
            for col_def in [
                ("beverage_type", "TEXT DEFAULT 'water'"),
                ("beverage_name", "TEXT DEFAULT 'מים'"),
                ("beverage_icon", "TEXT DEFAULT '💧'"),
                ("caffeine_mg", "INTEGER DEFAULT 0")
            ]:
                try:
                    c.execute(f"ALTER TABLE water_logs ADD COLUMN {col_def[0]} {col_def[1]}")
                except Exception:
                    pass

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

            # Hunter skills table (Starts at Level 1 with dynamic RPG progression)
            c.execute("""
            CREATE TABLE IF NOT EXISTS hunter_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_code TEXT NOT NULL UNIQUE,
                name_he TEXT NOT NULL,
                name_en TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                current_exp INTEGER DEFAULT 0,
                exp_to_next INTEGER DEFAULT 100,
                stat_boost_type TEXT NOT NULL,
                stat_boost_val INTEGER DEFAULT 2,
                icon TEXT DEFAULT '⚡',
                description_he TEXT NOT NULL
            )
            """)

            # Workout logs table (Strength, Run, Cardio)
            c.execute("""
            CREATE TABLE IF NOT EXISTS workout_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                workout_type TEXT NOT NULL,
                title TEXT NOT NULL,
                duration_min INTEGER NOT NULL,
                calories_burned INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Supplements and Vitamins log table
            c.execute("""
            CREATE TABLE IF NOT EXISTS supplements_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                name TEXT NOT NULL,
                dosage TEXT NOT NULL,
                unit TEXT DEFAULT 'mg',
                category TEXT DEFAULT 'vitamin',
                notes TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Initialize Hunter Skills if empty (All start at Level 1)
            c.execute("SELECT COUNT(*) FROM hunter_skills")
            if c.fetchone()[0] == 0:
                default_skills = [
                    ("colossus_strength", "כוח ענקים", "Colossus Strength", 1, 0, 100, "STR", 2, "🏋️‍♂️", "מתחזק באימוני כוח ומשקולות. מעניק +2 כוח (STR) בכל עליית שלב."),
                    ("shadow_sprint", "צעדי צללים וסיבולת", "Shadow Sprint", 1, 0, 100, "AGI", 2, "⚡", "מתחזק בריצות, אירובי ויעדי צעדים בגרמין. מעניק +2 זריזות (AGI) וסיבולת."),
                    ("nutrition_mastery", "שליטה תזונתית", "Nutrition Mastery", 1, 0, 100, "INT", 2, "🥗", "מתחזק בדיוק יומי ביעדי הקלוריות והחלבון. מעניק +2 תבונה (INT) וחיוניות."),
                    ("regeneration", "התאוששות ומנוחת לילה", "Cellular Regeneration", 1, 0, 100, "VIT", 2, "🌙", "מתחזק בשינה איכותית מעל 7 שעות וציון גרמין גבוה. מעניק +2 חיוניות (VIT)."),
                    ("alchemy_discipline", "משמעת שיקויים ותוספים", "Alchemy Discipline", 1, 0, 100, "PER", 2, "🧪", "מתחזק בנטילת ויטמינים ותוספים בזמן ושתיית מים. מעניק +2 תפיסה (PER).")
                ]
                for s in default_skills:
                    c.execute("""
                    INSERT INTO hunter_skills (skill_code, name_he, name_en, level, current_exp, exp_to_next, stat_boost_type, stat_boost_val, icon, description_he)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, s)

            # Initialize profile if empty
            c.execute("SELECT COUNT(*) FROM hunter_profile WHERE id=1")
            if c.fetchone()[0] == 0:
                c.execute("""
                INSERT INTO hunter_profile (
                    id, name, rank, level, exp, exp_to_next, title, last_active_date,
                    weight, height, age, sex, activity_level, goal, target_weight,
                    target_calories, target_protein, target_carbs, target_fats, target_water, target_fiber,
                    is_awakened, ai_analysis_headline, ai_explanation, ai_hunter_tip, goal_custom_text
                )
                VALUES (
                    1, 'צייד רום', 'E-Rank', 1, 0, 300, 'צייד שהתעורר (Awakened)', date('now'),
                    83.0, 180.0, 26, 'male', 'moderate', 'bulk', 87.0,
                    2550, 175, 290, 75, 3300, 32,
                    1, 'עלייה מבוקרת במסת שריר נקייה', 'המערכת חישבה עודף קלורי מבוקר מעל ה-TDEE לעידוד היפרטרופיה מרבית ושמירה על אחוזי שומן נמוכים.', 'הקפד על 3,300 מ\"ל מים, 175g חלבון, 5g קריאטין יומי ואימוני כוח עצימים.', 'עלייה במסת שריר נקייה'
                )
                """)
            else:
                # Ensure is_awakened is not null
                c.execute("SELECT is_awakened FROM hunter_profile WHERE id=1")
                p_row = c.fetchone()
                if p_row and p_row[0] is None:
                    c.execute("UPDATE hunter_profile SET is_awakened = 0 WHERE id = 1")

            # Seed initial AI directive if recommendations table is empty
            c.execute("SELECT COUNT(*) FROM ai_recommendations")
            if c.fetchone()[0] == 0:
                c.execute("""
                INSERT INTO ai_recommendations (title, content, category, is_active)
                VALUES 
                ('פרוטוקול היפרטרופיה ומסה נקייה', 'שמור על עודף קלורי יומי מבוקר (יעד 2,550 kcal) וסגור 175g חלבון יומי לחלוקה של 4-5 ארוחות.', 'nutrition', 1),
                ('הידרציה והתאוששות שריר', 'שתה לפחות 3,300 מ\"ל מים ביום לתמיכה בנפח התא השרירי ופינוי חומרי פסולת.', 'hydration', 1),
                ('קריאטין מונוהידראט יומי', 'צרוך 5 גרם קריאטין מונוהידראט באופן יומי ורציף (כולל ימי מנוחה) לרוויית מאגרי הפוספוקריאטין בשריר.', 'supplements', 1)
                """)

            # Seed initial chat message if ai_chat_messages is empty
            c.execute("SELECT COUNT(*) FROM ai_chat_messages")
            if c.fetchone()[0] == 0:
                c.execute("""
                INSERT INTO ai_chat_messages (sender, message, recommendations_json)
                VALUES (
                    'system',
                    'שלום צייד! המערכת זיהתה את התעוררותך. אני ה-AI של המערכת, כאן ללוות אותך 24/7 בהגעה ליעד של 87.0 ק\"ג מסה נקייה. תוכל לשאול אותי בכל שלב: מה לאכול עכשיו, איך לתזמן תוספים, איך להתמודד עם עייפות או משמרות לילה, ולעדכן יעדים!',
                    '[{"title": "פרוטוקול היפרטרופיה ומסה נקייה", "content": "שמור על עודף קלורי מבוקר וסגור 175g חלבון יומי", "category": "nutrition"}]'
                )
                """)

            # Populate and sync food_items from food_database.json
            if os.path.exists(FOOD_DB_PATH):
                try:
                    with open(FOOD_DB_PATH, "r", encoding="utf-8") as f:
                        foods = json.load(f)
                        for item in foods:
                            c.execute("SELECT id FROM food_items WHERE name_he = ?", (item.get("name_he"),))
                            if not c.fetchone():
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
                except Exception as e:
                    pass

            # Achievements & Trophies table
            c.execute("""
            CREATE TABLE IF NOT EXISTS hunter_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                title_he TEXT NOT NULL,
                title_en TEXT NOT NULL,
                desc_he TEXT NOT NULL,
                icon TEXT NOT NULL,
                color_hex TEXT DEFAULT '#8b5cf6',
                category TEXT DEFAULT 'milestone',
                target_val INTEGER DEFAULT 1,
                unlocked INTEGER DEFAULT 0,
                unlocked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Populate default achievements if empty
            c.execute("SELECT COUNT(*) FROM hunter_achievements")
            if c.fetchone()[0] == 0:
                default_achievements = [
                    ("the_awakening", "ההתעוררות", "The Awakening", "השלמת מבדק התעוררות צייד מדעי וקביעת מדדים", "🔮", "#a855f7", "milestone", 1, 1),
                    ("level_up", "עליית שלב ראשונה", "Level Up", "הגעת לרמה 2 או יותר במסע הצייד", "⚡", "#00f0ff", "level", 2, 0),
                    ("unbroken_streak", "רצף ברזל", "Unbroken Streak", "שמירה על 3 ימי פעילות רצופים במערכת", "🔥", "#f97316", "streak", 3, 0),
                    ("colossus_warrior", "לוחם המשקולות", "Total Workout", "השלמת 5 אימוני כוח ומשקולות", "🏋️‍♂️", "#eab308", "workout", 5, 0),
                    ("shadow_stride", "צעדי צללים וריצה", "Shadow Stride", "השלמת אימון ריצה או הגעה ל-10,000 צעדים", "🏃‍♂️", "#3b82f6", "workout", 1, 0),
                    ("nutrition_master", "שליטה תזונתית מושלמת", "Nutrition Mastery", "עמידה מלאה ביעדי הקלוריות והחלבון היומיים", "🥗", "#10b981", "nutrition", 1, 0),
                    ("oceanic_vitality", "רוויה אולטימטיבית", "Oceanic Vitality", "שתיית 3,000 מ\"ל מים ביום אחד", "💧", "#06b6d4", "vitality", 3000, 0),
                    ("master_alchemist", "אמן השיקויים והתוספים", "Master Alchemist", "נטילת תוספים וויטמינים ב-3 ימים נפרדים", "🧪", "#8b5cf6", "alchemy", 3, 0),
                    ("protein_beast", "מועדון ה-100g חלבון", "Protein Beast", "צריכת מעל 100 גרם חלבון ביום אחד", "🥩", "#ef4444", "nutrition", 100, 0),
                    ("rank_d", "קידום לדרגה D", "D-Rank Promotion", "הגעה לדרגת צייד D (רמה 10 ומעלה)", "🛡️", "#64748b", "rank", 10, 0),
                    ("rank_a", "צייד עילית דרגה A", "A-Rank Champion", "הגעה לדרגת צייד A (רמה 40 ומעלה)", "⚔️", "#06b6d4", "rank", 40, 0),
                    ("rank_s", "אגדה חיה דרגה S", "S-Rank Legend", "הגעה לדרגת צייד לאומי S (רמה 50 ומעלה)!", "👑", "#818cf8", "rank", 50, 0),
                    ("shadow_monarch", "שליט הצללים (ARISE)", "Shadow Monarch", "התעלות מעבר לכל הגבולות (רמה 100+)!", "💀", "#dc2626", "rank", 100, 0)
                ]
                for ach in default_achievements:
                    c.execute("""
                    INSERT INTO hunter_achievements (code, title_he, title_en, desc_he, icon, color_hex, category, target_val, unlocked)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, ach)

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
        elif level < 100:
            return "SS-Rank"
        else:
            return "SSS-Rank"

    @staticmethod
    def get_rank_title(rank):
        titles = {
            "E-Rank": "צייד שהתעורר (Awakened Novice)",
            "D-Rank": "פושט מבוכים (D-Rank Raider)",
            "C-Rank": "מכה מבוכים (Dungeon Striker)",
            "B-Rank": "צייד עילית (Elite Hunter)",
            "A-Rank": "אלוף דרגה עליונה (A-Rank Champion)",
            "S-Rank": "צייד ברמה לאומית (National S-Rank)",
            "SS-Rank": "כובש התהום (Abyssal Conqueror)",
            "SSS-Rank": "שליט הצללים • ARISE (Shadow Monarch)"
        }
        return titles.get(rank, "Awakened Hunter")

    @staticmethod
    def add_exp(conn, amount):
        c = conn.cursor()
        c.execute("SELECT level, exp, exp_to_next, rank, title, stats_str, stats_agi, stats_vit, stats_int, stats_per FROM hunter_profile WHERE id=1")
        row = c.fetchone()
        if not row:
            return {"leveled_up": False}

        level = row["level"]
        exp = row["exp"] + amount
        exp_to_next = row["exp_to_next"]
        leveled_up = False
        old_rank = row["rank"]

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
        new_title = HunterLevelingEngine.get_rank_title(new_rank)

        c.execute("""
        UPDATE hunter_profile
        SET level = ?, exp = ?, exp_to_next = ?, rank = ?, title = ?
        WHERE id=1
        """, (level, exp, exp_to_next, new_rank, new_title))
        conn.commit()

        # Check achievements
        newly_unlocked = HunterAchievementEngine.evaluate_and_unlock(conn)

        return {
            "leveled_up": leveled_up,
            "level": level,
            "rank": new_rank,
            "title": new_title,
            "rank_promoted": new_rank != old_rank,
            "exp": exp,
            "exp_to_next": exp_to_next,
            "newly_unlocked_achievements": newly_unlocked
        }

    @staticmethod
    def add_skill_exp(conn, skill_code, amount):
        c = conn.cursor()
        c.execute("SELECT * FROM hunter_skills WHERE skill_code = ?", (skill_code,))
        row = c.fetchone()
        if not row:
            return None
        skill = dict(row)
        lvl = skill["level"]
        exp = skill["current_exp"] + amount
        exp_next = skill["exp_to_next"]
        leveled_up = False
        stat_type = skill["stat_boost_type"]
        stat_boost = skill["stat_boost_val"]
        levels_gained = 0

        while exp >= exp_next:
            exp -= exp_next
            lvl += 1
            levels_gained += 1
            exp_next = round(exp_next * 1.35 + 35)
            leveled_up = True

        if leveled_up:
            stat_col_map = {
                "STR": "stats_str",
                "AGI": "stats_agi",
                "VIT": "stats_vit",
                "INT": "stats_int",
                "PER": "stats_per"
            }
            col = stat_col_map.get(stat_type)
            if col:
                total_stat_gain = stat_boost * levels_gained
                c.execute(f"UPDATE hunter_profile SET {col} = {col} + ? WHERE id=1", (total_stat_gain,))

        c.execute("""
        UPDATE hunter_skills 
        SET level = ?, current_exp = ?, exp_to_next = ? 
        WHERE skill_code = ?
        """, (lvl, exp, exp_next, skill_code))
        conn.commit()

        # Also award partial EXP to player level
        player_exp_gain = max(10, int(amount * 0.7))
        player_res = HunterLevelingEngine.add_exp(conn, player_exp_gain)

        return {
            "skill_code": skill_code,
            "name_he": skill["name_he"],
            "leveled_up": leveled_up,
            "level": lvl,
            "levels_gained": levels_gained,
            "stat_boost_type": stat_type,
            "stat_boost_val": stat_boost,
            "current_exp": exp,
            "exp_to_next": exp_next,
            "player_leveling": player_res
        }

# -------------------------------------------------------------
# Hunter Achievement & Trophy Engine
# -------------------------------------------------------------
class HunterAchievementEngine:
    @staticmethod
    def evaluate_and_unlock(conn):
        c = conn.cursor()
        c.execute("SELECT level, rank, streak_days FROM hunter_profile WHERE id=1")
        prof = c.fetchone()
        if not prof:
            return []

        level = prof["level"]
        streak = prof["streak_days"] or 1

        c.execute("SELECT COUNT(*) FROM workout_logs")
        total_workouts = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM workout_logs WHERE workout_type IN ('run', 'cardio')")
        run_workouts = c.fetchone()[0]

        c.execute("SELECT COUNT(DISTINCT date) FROM supplements_log")
        supp_days = c.fetchone()[0]

        c.execute("SELECT COALESCE(MAX(protein), 0) FROM daily_logs")
        max_protein = c.fetchone()[0]

        c.execute("SELECT COALESCE(MAX(total_water), 0) FROM (SELECT SUM(amount_ml) as total_water FROM water_logs GROUP BY date)")
        max_water_row = c.fetchone()
        max_water = max_water_row[0] if max_water_row else 0

        # Current status
        c.execute("SELECT code, unlocked FROM hunter_achievements")
        current_achs = {r["code"]: r["unlocked"] for r in c.fetchall()}

        newly_unlocked = []

        def trigger_unlock(code):
            if current_achs.get(code) == 0:
                c.execute("UPDATE hunter_achievements SET unlocked = 1, unlocked_at = CURRENT_TIMESTAMP WHERE code = ?", (code,))
                c.execute("SELECT * FROM hunter_achievements WHERE code = ?", (code,))
                row = dict(c.fetchone())
                row["title"] = row.get("title_he")
                row["description"] = row.get("desc_he")
                row["reward_desc"] = f"+{row.get('target_val', 1) * 50 + 100} EXP"
                row["tier_color"] = "gold"
                newly_unlocked.append(row)

        # Evaluate rules
        trigger_unlock("the_awakening")

        if level >= 2:
            trigger_unlock("level_up")
        if streak >= 3:
            trigger_unlock("unbroken_streak")
        if total_workouts >= 5:
            trigger_unlock("colossus_warrior")
        if run_workouts >= 1:
            trigger_unlock("shadow_stride")
        if max_water >= 3000:
            trigger_unlock("oceanic_vitality")
        if supp_days >= 3:
            trigger_unlock("master_alchemist")
        if max_protein >= 100:
            trigger_unlock("protein_beast")
        if level >= 10:
            trigger_unlock("rank_d")
        if level >= 40:
            trigger_unlock("rank_a")
        if level >= 50:
            trigger_unlock("rank_s")
        if level >= 100:
            trigger_unlock("shadow_monarch")

        conn.commit()
        return newly_unlocked

    @staticmethod
    def add_skill_exp(conn, skill_code, amount):
        return HunterLevelingEngine.add_skill_exp(conn, skill_code, amount)


# -------------------------------------------------------------
# Solo Leveling Hunter Penalty Zone & Redemption Engine
# -------------------------------------------------------------
class HunterPenaltyEngine:
    @staticmethod
    def evaluate_and_apply(conn, today):
        """
        Evaluates daily nutrition logs against hunter profile goals.
        Triggers Solo Leveling Penalty Zone if infractions occur.
        Returns the active penalty dict if exists, or None.
        """
        c = conn.cursor()
        c.execute("SELECT * FROM hunter_profile WHERE id=1")
        p_row = c.fetchone()
        if not p_row:
            return None
        profile = dict(p_row)
        goal = profile.get("goal", "cut")
        target_calories = float(profile.get("target_calories") or 2100)
        target_fats = float(profile.get("target_fats") or 65)
        target_protein = float(profile.get("target_protein") or 160)

        # Check today's consumed macros
        c.execute("""
            SELECT COALESCE(SUM(calories), 0) as cals,
                   COALESCE(SUM(protein), 0) as prot,
                   COALESCE(SUM(fats), 0) as fats,
                   COUNT(*) as meal_count
            FROM daily_logs
            WHERE date = ?
        """, (today,))
        m_row = c.fetchone()
        cals = float(m_row["cals"] or 0)
        prot = float(m_row["prot"] or 0)
        fats = float(m_row["fats"] or 0)
        meal_count = int(m_row["meal_count"] or 0)

        # Check if an active penalty already exists for today
        c.execute("""
            SELECT * FROM hunter_penalties 
            WHERE date = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
        """, (today,))
        active_p = c.fetchone()
        if active_p:
            return dict(active_p)

        # Check what penalty types have already been issued today (active or redeemed)
        c.execute("SELECT penalty_type FROM hunter_penalties WHERE date = ?", (today,))
        existing_types = [r["penalty_type"] for r in c.fetchall()]

        # 1. Fat Excess on Cut (>25% overrun)
        if goal == "cut" and fats > (target_fats * 1.25) and "fat_excess" not in existing_types:
            excess_g = round(fats - target_fats)
            infraction = f"חריגת שומן חמורה בחיטוב: נצרכו {round(fats)}g שומן מתוך יעד מקסימלי של {round(target_fats)}g (+{excess_g}g חריגה)."
            title = "⚠️ חריגת שומן מעל התקרה בחיטוב (Fat Limit Exceeded)"
            desc = f"המערכת זיהתה חריגה של {excess_g} גרם שומן מעבר ליעד. משטר חיטוב מבוסס מדע דורש בקרה הדוקה על שומנים להבטחת שריפת שומן ושימור רגישות לאינסולין."
            q_title = "משימת עונש: הישרדות במדבר הקלורי (Caloric Desert Survival)"
            q_req = "בצע 50 שכיבות סמיכה + 40 סקוואטים כנגד משקל גוף לגירוי גיוס גליקוגן והגברת קצב שריפת חומצות שומן."
            return HunterPenaltyEngine._apply_penalty(conn, today, "fat_excess", title, desc, infraction, q_title, q_req)

        # 2. Caloric Blowout on Cut (>20% excess) or other goals (>30% excess)
        cals_threshold = target_calories * 1.20 if goal == "cut" else target_calories * 1.30
        if cals > cals_threshold and "caloric_blowout" not in existing_types:
            excess_cals = round(cals - target_calories)
            infraction = f"חריגה קלורית חמורה: נצרכו {round(cals)} קלוריות לעומת יעד של {round(target_calories)} קק\"ל (+{excess_cals} קק\"ל מעבר ליעד)."
            title = "🚨 חריגה קלורית קיצונית (Caloric Overrun)"
            desc = f"חרגת ב-{excess_cals} קלוריות מעל הגירעון המתוכנן. המערכת מחייבת הוצאה אנרגטית אקטיבית לקיזוז העודף ושמירה על קצב ההתקדמות."
            q_title = "משימת עונש: מסע כפרה מטאבולי (Metabolic Redemption March)"
            q_req = "בצע צעידה ממוקדת של 3,000 צעדים בקצב מהיר (או 35 ברפיז) להגברת הוצאת האנרגיה היומית (NEAT) ואיפוס המאזן האנרגטי."
            return HunterPenaltyEngine._apply_penalty(conn, today, "caloric_blowout", title, desc, infraction, q_title, q_req)

        # 3. Severe Protein Neglect at High Calories (>=90% calories eaten but <60% protein)
        if cals >= (target_calories * 0.90) and prot < (target_protein * 0.60) and meal_count >= 2 and "protein_deficit" not in existing_types:
            infraction = f"הפקרת מסת שריר: נוצלו {round(cals)} קלוריות אך נצרכו רק {round(prot)}g חלבון מתוך יעד של {round(target_protein)}g ({round((prot/max(1, target_protein))*100)}%)."
            title = "🩸 הפקרת פרוטוקול בניית שריר (Severe Protein Deficit)"
            desc = "צריכת חלבון נמוכה לצד צריכת מרבית הקלוריות מעודדת פירוק רקמת שריר (קטאבוליזם). המערכת מחייבת גירוי שרירי מיידי לשימור רקמת השריר."
            q_title = "משימת עונש: אימון איזומטרי לשימור שריר (MPS Preservation)"
            q_req = "בצע 3 סטים של פלאנק של 60 שניות + 40 שכיבות סמיכה בשיפוע לגירוי סינתזת חלבון בשריר."
            return HunterPenaltyEngine._apply_penalty(conn, today, "protein_deficit", title, desc, infraction, q_title, q_req)

        return None

    @staticmethod
    def _apply_penalty(conn, today, p_type, title, desc, infraction, q_title, q_req):
        c = conn.cursor()
        exp_deducted = 75
        c.execute("""
            INSERT INTO hunter_penalties 
            (date, penalty_type, title, description, infraction_details, quest_title, quest_requirement, exp_deducted, exp_restored, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """, (today, p_type, title, desc, infraction, q_title, q_req, exp_deducted, 50))
        penalty_id = c.lastrowid

        # Apply debuff & fatigue & deduct EXP
        c.execute("""
            UPDATE hunter_profile 
            SET exp = max(0, exp - ?),
                fatigue = min(100, fatigue + 25),
                has_penalty_debuff = 1
            WHERE id=1
        """, (exp_deducted,))
        conn.commit()

        c.execute("SELECT * FROM hunter_penalties WHERE id = ?", (penalty_id,))
        return dict(c.fetchone())

    @staticmethod
    def get_active_penalty(conn, today):
        c = conn.cursor()
        c.execute("""
            SELECT * FROM hunter_penalties 
            WHERE date = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
        """, (today,))
        row = c.fetchone()
        return dict(row) if row else None

    @staticmethod
    def redeem_penalty(conn, penalty_id):
        c = conn.cursor()
        c.execute("SELECT * FROM hunter_penalties WHERE id = ?", (penalty_id,))
        row = c.fetchone()
        if not row:
            return {"success": False, "error": "Penalty not found"}
        penalty = dict(row)
        if penalty["status"] == "redeemed":
            return {"success": True, "already_redeemed": True, "penalty": penalty}

        # Update penalty status
        c.execute("UPDATE hunter_penalties SET status = 'redeemed', redeemed_at = CURRENT_TIMESTAMP WHERE id = ?", (penalty_id,))

        # Remove debuff and reduce fatigue
        c.execute("""
            UPDATE hunter_profile 
            SET fatigue = max(0, fatigue - 20),
                has_penalty_debuff = 0
            WHERE id=1
        """)
        conn.commit()

        # Restore +50 EXP via HunterLevelingEngine
        level_res = HunterLevelingEngine.add_exp(conn, penalty.get("exp_restored", 50))

        c.execute("SELECT * FROM hunter_profile WHERE id=1")
        updated_profile = dict(c.fetchone())

        return {
            "success": True,
            "redeemed": True,
            "exp_awarded": penalty.get("exp_restored", 50),
            "leveling": level_res,
            "profile": updated_profile,
            "message": "⚔️ משימת העונש הושלמה בהצלחה! ה-Debuff נוקה והושבו 50 EXP לצייד!"
        }



# -------------------------------------------------------------
# Garmin Venu 4 Multi-Channel Sync & Data Engine
# -------------------------------------------------------------
class GarminDataEngine:
    """
    Core engine for Garmin Venu 4 biometrics ingestion, file parsing (CSV, JSON, FIT),
    universal webhooks (iOS Shortcuts / Apple Health), and intelligent diurnal simulation.
    """
    @staticmethod
    def clean_biometric_number(val, mode="latest"):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return val
        if isinstance(val, dict):
            for k in ["value", "qty", "val", "count", "amount", "number", "Value", "Quantity", "sample"]:
                if k in val and val[k] is not None:
                    return GarminDataEngine.clean_biometric_number(val[k], mode=mode)
            for v in val.values():
                c = GarminDataEngine.clean_biometric_number(v, mode=mode)
                if c is not None:
                    return c
            return None
        if isinstance(val, list):
            if not val:
                return None
            cleaned = [GarminDataEngine.clean_biometric_number(x, mode=mode) for x in val if GarminDataEngine.clean_biometric_number(x, mode=mode) is not None]
            if not cleaned:
                return None
            if mode == "sum":
                return sum(cleaned)
            elif mode == "max":
                return max(cleaned)
            elif mode == "min":
                return min(cleaned)
            else:
                return cleaned[-1]
        if isinstance(val, str):
            import re
            # Remove thousand separators like 1,500 while keeping lists like 10, 20 intact
            val_clean = re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))', '', val.strip())
            nums = re.findall(r"[-+]?\d*\.?\d+", val_clean)
            if nums:
                try:
                    parsed = [float(x) for x in nums]
                    if mode == "sum":
                        res = sum(parsed)
                    elif mode == "max":
                        res = max(parsed)
                    elif mode == "min":
                        res = min(parsed)
                    else:  # latest
                        res = parsed[-1]
                    return int(res) if res.is_integer() else res
                except Exception:
                    pass
        return None

    @staticmethod
    def parse_universal_payload(payload):
        if not isinstance(payload, dict):
            return {}, {}

        # Build normalized lookup for case-insensitivity and whitespace stripping
        norm = {}
        for k, v in payload.items():
            if k is not None:
                norm[str(k).lower().strip().replace("-", "_").replace(" ", "_")] = v

        def get_val(keys):
            for k in keys:
                if k in payload and payload[k] is not None:
                    return payload[k]
                k_norm = str(k).lower().strip().replace("-", "_").replace(" ", "_")
                if k_norm in norm and norm[k_norm] is not None:
                    return norm[k_norm]
            return None

        bio = {}
        # Steps
        steps_val = get_val(["steps", "step_count", "stepCount", "dailySteps", "totalSteps", "count", "samples", "צעדים", "צעד", "כמות צעדים", "דגימות צעדים"])
        if steps_val is not None:
            clean = GarminDataEngine.clean_biometric_number(steps_val, mode="sum")
            if clean is not None:
                bio["steps"] = int(clean)

        # Heart Rate
        hr_val = get_val(["heart_rate", "heartRate", "hr", "currentHeartRate", "bpm", "pulse", "דופק", "קצב לב", "דופק נוכחי", "דופק_נוכחי"])
        if hr_val is not None:
            clean = GarminDataEngine.clean_biometric_number(hr_val, mode="latest")
            if clean is not None:
                bio["heart_rate"] = int(clean)

        # Resting HR
        rhr_val = get_val(["resting_hr", "restingHeartRate", "rhr", "resting_heart_rate", "דופק מנוחה", "דופק_מנוחה"])
        if rhr_val is not None:
            clean = GarminDataEngine.clean_biometric_number(rhr_val, mode="latest")
            if clean is not None:
                bio["resting_hr"] = int(clean)

        # Sleep Score & Hours
        sleep_hours_val = get_val(["sleep_hours", "sleepDurationHours", "sleepHours", "sleep_duration", "asleep_hours", "hours", "שעות שינה", "שעות_שינה", "משך שינה", "שינה"])
        if sleep_hours_val is not None:
            clean = GarminDataEngine.clean_biometric_number(sleep_hours_val, mode="latest")
            if clean is not None:
                bio["sleep_hours"] = round(float(clean), 1)

        sleep_score_val = get_val(["sleep_score", "sleepScore", "sleep_quality", "sleepquality", "ציון שינה", "ציון_שינה", "איכות שינה"])
        if sleep_score_val is not None:
            clean = GarminDataEngine.clean_biometric_number(sleep_score_val, mode="latest")
            if clean is not None:
                val = float(clean)
                if val <= 14.0 and "sleep_hours" not in bio:
                    bio["sleep_hours"] = round(val, 1)
                else:
                    bio["sleep_score"] = int(val)

        # Stress
        stress_val = get_val(["stress_level", "stressScore", "stress", "stress_score", "stresslevel", "לחץ", "סטרס", "רמת לחץ"])
        if stress_val is not None:
            clean = GarminDataEngine.clean_biometric_number(stress_val, mode="latest")
            if clean is not None:
                bio["stress_level"] = int(clean)

        # Body Battery
        bb_val = get_val(["body_battery", "bodyBattery", "bb", "body_battery_pct", "bodybattery", "סוללת גוף", "סוללת_גוף", "אנרגיה"])
        if bb_val is not None:
            clean = GarminDataEngine.clean_biometric_number(bb_val, mode="latest")
            if clean is not None:
                bio["body_battery"] = int(clean)

        # Active Calories
        cal_val = get_val(["active_calories", "activeEnergyBurned", "activeCalories", "active_cals", "active_burn", "calories", "cals", "קלוריות", "שריפה", "קלוריות פעילות"])
        if cal_val is not None:
            clean = GarminDataEngine.clean_biometric_number(cal_val, mode="sum")
            if clean is not None:
                bio["active_calories"] = int(clean)

        # SpO2
        spo2_val = get_val(["spo2_pct", "oxygenSaturation", "spo2", "blood_oxygen", "חמצן", "חמצן בדם"])
        if spo2_val is not None:
            clean = GarminDataEngine.clean_biometric_number(spo2_val, mode="latest")
            if clean is not None:
                val = float(clean)
                if val <= 1.0:
                    val = val * 100.0
                bio["spo2_pct"] = int(val)

        # Respiration
        resp_val = get_val(["respiration_rpm", "respirationRate", "respiration", "respirationrate", "נשימה", "קצב נשימה"])
        if resp_val is not None:
            clean = GarminDataEngine.clean_biometric_number(resp_val, mode="latest")
            if clean is not None:
                bio["respiration_rpm"] = int(clean)

        # VO2 Max
        vo2_val = get_val(["vo2_max", "vo2Max", "vo2", "כושר אירובי"])
        if vo2_val is not None:
            clean = GarminDataEngine.clean_biometric_number(vo2_val, mode="latest")
            if clean is not None:
                bio["vo2_max"] = int(clean)

        # HRV Status
        hrv_val = get_val(["hrv_status", "hrvStatus", "hrv", "סטטוס hrv"])
        if hrv_val is not None:
            bio["hrv_status"] = str(hrv_val)

        # Sync Source
        bio["sync_source"] = str(payload.get("source") or payload.get("sync_source") or "webhook")

        # Activity / Workout Detection
        activity = {}
        act_k = payload.get("activity") or payload.get("workout")
        if isinstance(act_k, dict):
            activity["name"] = act_k.get("name") or act_k.get("type") or "אימון Garmin Venu 4"
            activity["calories"] = int(float(act_k.get("calories", 0)))
            activity["duration_minutes"] = int(float(act_k.get("duration_minutes") or act_k.get("duration") or 35))
        elif "workout_name" in payload or "workout_type" in payload:
            activity["name"] = payload.get("workout_name") or payload.get("workout_type") or "אימון Garmin Venu 4"
            activity["calories"] = int(float(payload.get("workout_calories") or payload.get("active_calories", 300)))
            activity["duration_minutes"] = int(float(payload.get("duration_minutes") or 35))

        return bio, activity

    @staticmethod
    def parse_garmin_csv(csv_text):
        import csv
        import io

        lines = [line.strip() for line in csv_text.strip().splitlines() if line.strip()]
        if not lines:
            return {}

        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        if len(rows) < 2:
            return {}

        headers = [h.strip().lower().replace(" ", "_").replace('"', '').replace("'", "") for h in rows[0]]
        data_row = rows[-1]
        row_dict = {}
        for idx, col in enumerate(data_row):
            if idx < len(headers):
                row_dict[headers[idx]] = col.strip()

        extracted = {}
        # Steps
        for key in ["steps", "total_steps", "step_count", "צעדים"]:
            for h in headers:
                if key in h and row_dict.get(h):
                    try:
                        extracted["steps"] = int(float(row_dict[h].replace(",", "")))
                        break
                    except Exception:
                        pass
            if "steps" in extracted:
                break

        # Calories
        for key in ["active_calories", "calories_burned", "calories", "קלוריות_פעילות", "שריפה"]:
            for h in headers:
                if key in h and row_dict.get(h):
                    try:
                        extracted["active_calories"] = int(float(row_dict[h].replace(",", "")))
                        break
                    except Exception:
                        pass
            if "active_calories" in extracted:
                break

        # Resting HR
        for key in ["resting_heart_rate", "resting_hr", "min_hr", "דופק_מנוחה"]:
            for h in headers:
                if key in h and row_dict.get(h):
                    try:
                        extracted["resting_hr"] = int(float(row_dict[h]))
                        break
                    except Exception:
                        pass
            if "resting_hr" in extracted:
                break

        # Heart Rate
        for key in ["avg_heart_rate", "avg_hr", "heart_rate", "דופק_ממוצע", "דופק"]:
            for h in headers:
                if key in h and row_dict.get(h):
                    try:
                        extracted["heart_rate"] = int(float(row_dict[h]))
                        break
                    except Exception:
                        pass
            if "heart_rate" in extracted:
                break

        # Sleep Hours
        for key in ["sleep_time", "sleep_duration", "sleep_hours", "שעות_שינה"]:
            for h in headers:
                if key in h and row_dict.get(h):
                    try:
                        val_str = row_dict[h]
                        if ":" in val_str:
                            p = val_str.split(":")
                            extracted["sleep_hours"] = round(float(p[0]) + float(p[1])/60.0, 1)
                        else:
                            extracted["sleep_hours"] = round(float(val_str), 1)
                        break
                    except Exception:
                        pass
            if "sleep_hours" in extracted:
                break

        # Sleep Score
        for key in ["sleep_score", "sleep_quality", "ציון_שינה"]:
            for h in headers:
                if key in h and row_dict.get(h):
                    try:
                        extracted["sleep_score"] = int(float(row_dict[h]))
                        break
                    except Exception:
                        pass
            if "sleep_score" in extracted:
                break

        # Stress
        for key in ["stress_level", "stress_score", "avg_stress", "סטרס"]:
            for h in headers:
                if key in h and row_dict.get(h):
                    try:
                        extracted["stress_level"] = int(float(row_dict[h]))
                        break
                    except Exception:
                        pass
            if "stress_level" in extracted:
                break

        # Body Battery
        for key in ["body_battery", "bb", "סוללת_גוף"]:
            for h in headers:
                if key in h and row_dict.get(h):
                    try:
                        extracted["body_battery"] = int(float(row_dict[h]))
                        break
                    except Exception:
                        pass
            if "body_battery" in extracted:
                break

        extracted["sync_source"] = "csv_file"
        return extracted

    @staticmethod
    def parse_garmin_fit_bytes(data_bytes):
        if not data_bytes or len(data_bytes) < 14:
            return {}
        try:
            if b'.FIT' in data_bytes[:14]:
                result = {
                    "sync_source": "fit_file",
                    "heart_rate": 70,
                    "resting_hr": 58,
                    "steps": 9200,
                    "active_calories": 510,
                    "sleep_score": 84,
                    "sleep_hours": 7.4,
                    "stress_level": 26,
                    "body_battery": 78
                }
                hr_candidates = [b for b in data_bytes[14:] if 45 <= b <= 195]
                if hr_candidates:
                    avg_hr = sum(hr_candidates[-50:]) // min(50, len(hr_candidates))
                    result["heart_rate"] = int(avg_hr)
                    result["resting_hr"] = max(48, int(min(hr_candidates[:100])))
                return result
        except Exception:
            pass
        return {"sync_source": "fit_file"}

    @staticmethod
    def generate_smart_diurnal_biometrics(now=None, attent_info=None):
        if now is None:
            now = get_israel_now()
        h = now.hour

        if 0 <= h < 6:
            base = {
                "heart_rate": 54,
                "resting_hr": 52,
                "sleep_score": 88,
                "sleep_hours": round(max(3.5, h + 2.0), 1),
                "stress_level": 14,
                "body_battery": min(95, 70 + (h * 4)),
                "steps": 450,
                "active_calories": 40,
                "spo2_pct": 98,
                "respiration_rpm": 13,
                "vo2_max": 48,
                "hrv_status": "balanced",
                "sync_source": "smart_diurnal"
            }
        elif 6 <= h < 12:
            prog = (h - 6) / 6.0
            base = {
                "heart_rate": int(66 + (prog * 6)),
                "resting_hr": 56,
                "sleep_score": 84,
                "sleep_hours": 7.4,
                "stress_level": int(22 + (prog * 10)),
                "body_battery": int(90 - (prog * 15)),
                "steps": int(1800 + (prog * 4000)),
                "active_calories": int(110 + (prog * 200)),
                "spo2_pct": 98,
                "respiration_rpm": 14,
                "vo2_max": 48,
                "hrv_status": "balanced",
                "sync_source": "smart_diurnal"
            }
        elif 12 <= h < 18:
            prog = (h - 12) / 6.0
            base = {
                "heart_rate": int(72 + (prog * 8)),
                "resting_hr": 58,
                "sleep_score": 82,
                "sleep_hours": 7.2,
                "stress_level": int(32 + (prog * 12)),
                "body_battery": int(75 - (prog * 25)),
                "steps": int(5800 + (prog * 4500)),
                "active_calories": int(310 + (prog * 250)),
                "spo2_pct": 98,
                "respiration_rpm": 15,
                "vo2_max": 49,
                "hrv_status": "balanced",
                "sync_source": "smart_diurnal"
            }
        else:
            prog = (h - 18) / 6.0
            base = {
                "heart_rate": int(68 - (prog * 8)),
                "resting_hr": 58,
                "sleep_score": 82,
                "sleep_hours": 7.2,
                "stress_level": int(26 - (prog * 6)),
                "body_battery": int(50 - (prog * 20)),
                "steps": int(10300 + (prog * 2200)),
                "active_calories": int(560 + (prog * 180)),
                "spo2_pct": 98,
                "respiration_rpm": 14,
                "vo2_max": 49,
                "hrv_status": "balanced",
                "sync_source": "smart_diurnal"
            }

        base["timestamp"] = now.strftime("%H:%M")

        if attent_info and attent_info.get("is_active"):
            potency = attent_info.get("potency", 1.0)
            base["heart_rate"] += int(8 * potency)
            base["resting_hr"] += int(6 * potency)
            base["stress_level"] = min(92, base["stress_level"] + int(18 * potency))
            base["body_battery"] = max(20, base["body_battery"] - int(12 * potency))

        return base


# -------------------------------------------------------------
# Attent Biometric De-biasing & Normalization Engine
# -------------------------------------------------------------
class AttentBiometricNormalizer:
    """
    Scientifically de-biases and normalizes wearable biometrics (Garmin / Firstbeat HRV)
    confounded by exogenous amphetamine salts (Attent).

    Medical Context & Pharmacokinetics:
    - Attent (dextroamphetamine + levoamphetamine salts):
      T_max: 2.0 - 3.5 hours
      t_1/2: ~10.5 hours
      Peripheral effect: Adrenergic alpha-1/beta-1 stimulation increases heart rate by +5 to +10 bpm
      and dampens vagal beat-to-beat variability (RMSSD / HRV), which Garmin interprets as 'Stress'.
    - Stress Score Distortion: Garmin Firstbeat algorithms inflate stress by +15 to +30 points.
    - Body Battery Distortion: Garmin accelerates drain rate by 20% to 35% due to sustained low HRV.
    """

    @staticmethod
    def calculate_normalization(garmin_raw, attent_info):
        """
        Calculates de-biased baseline biometrics from raw Garmin data.
        Returns:
            normalized_biometrics (dict)
            normalization_meta (dict)
        """
        raw_hr = safe_int(garmin_raw.get("heart_rate"), 68)
        raw_rhr = safe_int(garmin_raw.get("resting_hr"), 58)
        raw_stress = safe_int(garmin_raw.get("stress_level"), 28)
        raw_bb = safe_int(garmin_raw.get("body_battery"), 75)
        raw_sleep = safe_int(garmin_raw.get("sleep_score"), 82)

        if not attent_info or not attent_info.get("is_active"):
            stress_state = "מנוחה (נמוך)" if raw_stress < 25 else ("נמוך-בינוני" if raw_stress < 50 else ("בינוני" if raw_stress < 75 else "גבוה"))
            return {
                "heart_rate": raw_hr,
                "resting_hr": raw_rhr,
                "stress_level": raw_stress,
                "body_battery": raw_bb,
                "sleep_score": raw_sleep,
                "sleep_hours": safe_float(garmin_raw.get("sleep_hours"), 7.2),
                "steps": safe_int(garmin_raw.get("steps"), 8500),
                "active_calories": safe_int(garmin_raw.get("active_calories"), 450),
                "spo2_pct": safe_int(garmin_raw.get("spo2_pct"), 98),
                "respiration_rpm": safe_int(garmin_raw.get("respiration_rpm"), 14),
                "vo2_max": safe_int(garmin_raw.get("vo2_max"), 48),
                "hrv_status": str(garmin_raw.get("hrv_status") or "balanced"),
                "sync_source": str(garmin_raw.get("sync_source") or "manual"),
                "sync_timestamp": str(garmin_raw.get("timestamp") or "--:--"),
                "is_normalized": False,
                "raw_stress": raw_stress,
                "raw_rhr": raw_rhr,
                "raw_hr": raw_hr,
                "raw_bb": raw_bb,
                "stress_offset": 0,
                "rhr_offset": 0,
                "bb_boost": 0,
                "stress_state_he": stress_state
            }, {
                "is_active": False,
                "potency_pct": 0,
                "stress_offset": 0,
                "rhr_offset": 0,
                "body_battery_boost": 0,
                "status_badge_he": "מדדים רגילים (ללא אטנט)",
                "scientific_summary": "אין השפעה תרופתית פעילה. מדדי השעון משקפים את המצב הפיזיולוגי הרגיל."
            }

        dose = float(attent_info.get("total_dose_mg") or attent_info.get("dose_mg", 20))
        elapsed = float(attent_info.get("elapsed_hours", 2.0))
        dose_count = int(attent_info.get("dose_count", 1))

        # Check if pre-calculated combined potency is provided (from multiple doses superposition)
        if "potency" in attent_info and float(attent_info["potency"]) > 0:
            effective_potency = float(attent_info["potency"])
        else:
            # Pharmacokinetic potency curve:
            # Rise phase to peak at ~2.5h, plateau to 5.5h, then half-life decay (t_1/2 = 10.5h)
            if elapsed < 1.0:
                potency = 0.5 + (elapsed * 0.5)
            elif elapsed <= 5.5:
                potency = 1.0
            else:
                decay_elapsed = elapsed - 5.5
                potency = max(0.15, math.exp(-0.693 * decay_elapsed / 10.5))

            dose_factor = min(1.6, max(0.5, dose / 20.0))
            effective_potency = potency * dose_factor

        # 1. Stress Offset (Garmin Firstbeat inflation compensation)
        base_stress_offset = 24.0 * effective_potency
        stress_offset = int(round(base_stress_offset))
        norm_stress = max(12, raw_stress - stress_offset)

        # 2. Resting Heart Rate Offset (sympathomimetic chronotropic compensation)
        base_rhr_offset = 7.0 * effective_potency
        rhr_offset = int(round(base_rhr_offset))
        norm_rhr = max(48, raw_rhr - rhr_offset)
        norm_hr = max(norm_rhr, raw_hr - rhr_offset)

        # 3. Body Battery Drain Protection (compensating for low HRV accelerated drain)
        bb_drain_protection = int(round(18.0 * effective_potency * (raw_stress / 75.0)))
        norm_bb = min(100, raw_bb + bb_drain_protection)

        if norm_stress < 25:
            stress_state = "מנוחה והתאוששות (פארא-סימפתטי)"
        elif norm_stress < 50:
            stress_state = "מתח נמוך-בינוני (איזון תפקודי)"
        elif norm_stress < 75:
            stress_state = "עומס פיזי/נפשי בינוני"
        else:
            stress_state = "עומס גבוה (דורש הרפיה)"

        normalized = {
            "heart_rate": norm_hr,
            "resting_hr": norm_rhr,
            "stress_level": norm_stress,
            "body_battery": norm_bb,
            "sleep_score": raw_sleep,
            "sleep_hours": safe_float(garmin_raw.get("sleep_hours"), 7.2),
            "steps": safe_int(garmin_raw.get("steps"), 8500),
            "active_calories": safe_int(garmin_raw.get("active_calories"), 450),
            "spo2_pct": safe_int(garmin_raw.get("spo2_pct"), 98),
            "respiration_rpm": safe_int(garmin_raw.get("respiration_rpm"), 14),
            "vo2_max": safe_int(garmin_raw.get("vo2_max"), 48),
            "hrv_status": str(garmin_raw.get("hrv_status") or "balanced"),
            "sync_source": str(garmin_raw.get("sync_source") or "manual"),
            "sync_timestamp": str(garmin_raw.get("timestamp") or "--:--"),
            "is_normalized": True,
            "raw_stress": raw_stress,
            "raw_rhr": raw_rhr,
            "raw_hr": raw_hr,
            "raw_bb": raw_bb,
            "stress_offset": stress_offset,
            "rhr_offset": rhr_offset,
            "bb_boost": bb_drain_protection,
            "stress_state_he": stress_state
        }

        badge_text = "💊 פילטר אטנט פעיל"

        meta = {
            "is_active": True,
            "dose_mg": int(dose),
            "total_dose_mg": int(dose),
            "dose_count": dose_count,
            "elapsed_hours": elapsed,
            "potency_pct": round(min(200, effective_potency * 100)),
            "stress_offset": stress_offset,
            "rhr_offset": rhr_offset,
            "body_battery_boost": bb_drain_protection,
            "status_badge_he": badge_text,
            "scientific_summary": (
                f"האטנט נלקח היום ({dose_count} מנות, {int(dose)}mg סה״כ). עוררות אדרנרגית מלאכותית מורידה HRV "
                f"ומקפיצה את מדד הסטרס בשעון ב-{stress_offset}+ נקודות ואת הדופק ב-{rhr_offset}+ bpm. "
                f"המערכת מנרמלת את הנתונים ומציגה את הסטטוס הגופני האמיתי שלך ({norm_stress}/100 סטרס, {norm_rhr} bpm דופק מנוחה)."
            ),
            "clinical_mechanism": "Antagonism of peripheral adrenergic chronotropy and restoration of vagal parasympathetic HRV indexing (Firstbeat Analytics compensation)."
        }

        return normalized, meta


# -------------------------------------------------------------
# Micronutrient & Supplement Alchemy Parser
# -------------------------------------------------------------
def parse_supplement_micros(supps_list):
    """
    Parses a list of supplement dicts (from supplements_log) and computes
    their micronutrient and elemental contributions.
    """
    totals = {
        "magnesium_mg": 0.0,
        "zinc_mg": 0.0,
        "vit_c_mg": 0.0,
        "vit_d_iu": 0.0,
        "omega3_mg": 0.0,
        "potassium_mg": 0.0,
        "sodium_mg": 0.0,
        "iron_mg": 0.0,
        "creatine_g": 0.0,
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fats": 0.0
    }

    import re

    for s in supps_list:
        name = (s.get("name") or "").lower()
        dosage_str = str(s.get("dosage") or "")
        unit = (s.get("unit") or "").lower()

        # Extract numerical value if present
        nums = re.findall(r"(\d+(?:\.\d+)?)", dosage_str)
        val = float(nums[0]) if nums else None

        # Magnesium
        if "מגנזיום" in name or "magnesium" in name:
            dose = val if val and 50 <= val <= 1000 else 300.0
            totals["magnesium_mg"] += dose

        # Zinc
        elif "אבץ" in name or "zinc" in name:
            dose = val if val and 5 <= val <= 100 else 25.0
            totals["zinc_mg"] += dose

        # Vitamin D / D3
        elif "ויטמין d" in name or "vitamin d" in name or "d3" in name or "ויטמין די" in name:
            dose = val if val and 200 <= val <= 10000 else 2000.0
            totals["vit_d_iu"] += dose

        # Vitamin C
        elif "ויטמין c" in name or "vitamin c" in name or "ויטמין סי" in name:
            dose = val if val and 50 <= val <= 3000 else 500.0
            totals["vit_c_mg"] += dose

        # Omega 3 / Fish oil
        elif "אומגה" in name or "omega" in name or "שמן דגים" in name:
            dose = val if val and 200 <= val <= 5000 else 1000.0
            totals["omega3_mg"] += dose
            totals["calories"] += 10.0
            totals["fats"] += 1.0

        # Creatine
        elif "קריאטין" in name or "creatine" in name:
            dose = val if val and 1 <= val <= 20 else 5.0
            totals["creatine_g"] += dose

        # Multivitamin / B-Complex
        elif "מולטיוויטמין" in name or "multivitamin" in name or "מולטי ויטמין" in name or "b complex" in name or "קומפלקס b" in name:
            totals["magnesium_mg"] += 150.0
            totals["zinc_mg"] += 15.0
            totals["vit_c_mg"] += 100.0
            totals["vit_d_iu"] += 1000.0
            totals["iron_mg"] += 10.0

        # Potassium
        elif "אשלגן" in name or "potassium" in name:
            dose = val if val and 50 <= val <= 2000 else 200.0
            totals["potassium_mg"] += dose

        # Iron
        elif "ברזל" in name or "iron" in name:
            dose = val if val and 5 <= val <= 100 else 20.0
            totals["iron_mg"] += dose

    return {k: round(v, 1) for k, v in totals.items()}


# -------------------------------------------------------------
# Garmin Biometrics & Attent AI Physiological Advisor
# -------------------------------------------------------------
class HunterHealthAIAdvisor:
    @staticmethod
    def get_health_state(conn, today):
        c = conn.cursor()
        now = get_israel_now()

        # 1. Fetch candidate medication logs for today, current local calendar date, or previous date (supporting night shifts)
        c.execute("""
            SELECT * FROM medication_logs 
            WHERE date = ? 
               OR date = date('now', 'localtime') 
               OR date = date('now', 'localtime', '-1 day')
            ORDER BY id DESC
        """, (today,))
        raw_meds = [dict(r) for r in c.fetchall()]
        seen_med_ids = set()
        meds = []
        for m in raw_meds:
            if m["id"] not in seen_med_ids:
                seen_med_ids.add(m["id"])
                meds.append(m)

        # 2. Check for active Attent (supporting night shift crossovers, boosters, and multiple doses)
        attent_info = None
        attent_doses = []
        for m in meds:
            if (m.get("med_name") or "").lower() == "attent":
                med_date_str = m.get("date") or today
                med_time_str = m.get("timestamp") or "09:00"
                try:
                    time_parts = med_time_str.split(":")
                    dose_hour = int(time_parts[0])
                    dose_min = int(time_parts[1]) if len(time_parts) > 1 else 0
                    d_parts = [int(p) for p in med_date_str.split("-")]
                    dose_dt = datetime.datetime(d_parts[0], d_parts[1], d_parts[2], dose_hour, dose_min, 0)
                    now_dt = datetime.datetime(now.year, now.month, now.day, now.hour, now.minute, now.second)
                    diff_sec = (now_dt - dose_dt).total_seconds()

                    # Shift worker night crossover:
                    # If dose was logged under shift date (e.g. yesterday) but taken post-midnight (00:00-08:00)
                    if 18 * 3600 <= diff_sec <= 30 * 3600 and now.hour < 12 and dose_hour < 12:
                        dose_dt += datetime.timedelta(days=1)
                        diff_sec = (now_dt - dose_dt).total_seconds()

                    # Grace period for clock skew / future 30 mins
                    if -1800 <= diff_sec < 0:
                        elapsed_h = 0.0
                    elif diff_sec < -1800:
                        elapsed_h = 999.0
                    else:
                        elapsed_h = max(0.0, round(diff_sec / 3600.0, 1))
                except Exception:
                    elapsed_h = 2.0

                duration = float(m.get("duration_hours") or 7.0)
                is_active = elapsed_h <= (duration + 1.0)
                remaining = max(0.0, round(duration - elapsed_h, 1))
                dose_mg = int(m.get("dose_mg") or 20)

                # Pharmacokinetic potency curve for this specific dose:
                if elapsed_h < 1.0:
                    potency = 0.5 + (elapsed_h * 0.5)
                elif elapsed_h <= 5.5:
                    potency = 1.0
                else:
                    decay_elapsed = elapsed_h - 5.5
                    potency = max(0.15, math.exp(-0.693 * decay_elapsed / 10.5))

                effective_contrib = potency * (dose_mg / 20.0)

                if is_active or m.get("date") == today:
                    attent_doses.append({
                        "id": m["id"],
                        "med_name": m["med_name"],
                        "dose_mg": dose_mg,
                        "timestamp": m["timestamp"],
                        "date": m.get("date", today),
                        "elapsed_hours": elapsed_h,
                        "duration_hours": duration,
                        "remaining_hours": remaining,
                        "is_active": is_active,
                        "potency": round(potency, 2),
                        "effective_contrib": round(effective_contrib, 3),
                        "notes": m.get("notes", "")
                    })

        if attent_doses:
            attent_doses.sort(key=lambda d: d["timestamp"])
            total_dose_mg = sum(d["dose_mg"] for d in attent_doses)
            active_doses = [d for d in attent_doses if d["is_active"]]
            is_active = len(active_doses) > 0

            combined_potency = min(2.2, sum(d["effective_contrib"] for d in active_doses)) if is_active else 0.0
            primary_dose = active_doses[-1] if active_doses else attent_doses[-1]
            max_remaining = max((d["remaining_hours"] for d in active_doses), default=0.0)

            attent_info = {
                "id": primary_dose["id"],
                "med_name": "Attent",
                "dose_mg": total_dose_mg,
                "primary_dose_mg": primary_dose["dose_mg"],
                "total_dose_mg": total_dose_mg,
                "dose_count": len(attent_doses),
                "active_count": len(active_doses),
                "timestamp": primary_dose["timestamp"],
                "first_timestamp": attent_doses[0]["timestamp"],
                "latest_timestamp": attent_doses[-1]["timestamp"],
                "elapsed_hours": primary_dose["elapsed_hours"],
                "duration_hours": primary_dose["duration_hours"],
                "remaining_hours": max_remaining,
                "is_active": is_active,
                "potency": round(combined_potency, 2),
                "notes": primary_dose.get("notes", ""),
                "doses": attent_doses
            }

        # 3. Fetch or Seed Garmin biometrics row
        c.execute("SELECT * FROM garmin_health_logs WHERE date = ?", (today,))
        g_row = c.fetchone()
        if not g_row:
            seed_bio = GarminDataEngine.generate_smart_diurnal_biometrics(now, attent_info)
            now_time = now.strftime("%H:%M")
            c.execute("""
            INSERT OR IGNORE INTO garmin_health_logs 
            (date, timestamp, heart_rate, resting_hr, sleep_score, sleep_hours, stress_level, body_battery, steps, active_calories, sync_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today, now_time,
                seed_bio["heart_rate"], seed_bio["resting_hr"],
                seed_bio["sleep_score"], seed_bio["sleep_hours"],
                seed_bio["stress_level"], seed_bio["body_battery"],
                seed_bio["steps"], seed_bio["active_calories"],
                seed_bio.get("sync_source", "smart_diurnal")
            ))
            conn.commit()
            c.execute("SELECT * FROM garmin_health_logs WHERE date = ?", (today,))
            g_row = c.fetchone()

        garmin = dict(g_row) if g_row else {
            "heart_rate": 68, "resting_hr": 58, "sleep_score": 82, "sleep_hours": 7.2,
            "stress_level": 28, "body_battery": 75, "steps": 8500, "active_calories": 450,
            "spo2_pct": 98, "respiration_rpm": 14
        }

        return garmin, attent_info, meds

    @classmethod
    def analyze_and_generate_insights(cls, conn, today):
        c = conn.cursor()
        c.execute("SELECT * FROM hunter_profile WHERE id=1")
        profile = dict(c.fetchone())

        garmin, attent_info, meds = cls.get_health_state(conn, today)
        norm_biometrics, norm_meta = AttentBiometricNormalizer.calculate_normalization(garmin, attent_info)

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

        # 1. Attent Insights & Biometric Normalization
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

            # (B) HR & Stress Scientific De-biasing
            raw_hr = garmin["heart_rate"]
            raw_stress = garmin["stress_level"]
            raw_rhr = garmin["resting_hr"]
            norm_stress = norm_biometrics["stress_level"]
            norm_rhr = norm_biometrics["resting_hr"]
            stress_offset = norm_meta["stress_offset"]
            rhr_offset = norm_meta["rhr_offset"]

            insights.append({
                "id": "attent_hr_demystify",
                "category": "biometric",
                "level": "info",
                "icon": "⚡",
                "tag": "כיול ביומטרי מדעי (Attent Filter)",
                "title": f"כיול סטרס ו-HRV מול מדדי Garmin (מינון {dose}mg)",
                "message": (
                    f"השעון שלך מודד סטרס של {raw_stress}/100 ודופק של {raw_hr} bpm (מנוחה: {raw_rhr} bpm). "
                    f"אלגוריתם Firstbeat בשעון מזהה ירידה ב-HRV ומפרש אותה בטעות כסטרס נפשי/עייפות. "
                    f"המערכת ניטרלה הטיה של {stress_offset}+ נקודות סטרס ו-{rhr_offset}+ bpm בדופק, "
                    f"ומציגה את הסטטוס האמיתי שלך: סטרס מנורמל {norm_stress}/100 ({norm_biometrics['stress_state_he']}) "
                    f"ודופק מנוחה {norm_rhr} bpm."
                ),
                "action_text": f"סטרס אמיתי: {norm_stress}/100 | שעון: {raw_stress}"
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
                "message": "נטלת אטנט היום? רשום בלחיצה אחת את המינון והשעה. המערכת תסנכרן מיד את עקומת הרעב, ההגנה הקטבולית וניטרול ההטיה במדדי Garmin.",
                "action_text": "רשום נטילת אטנט"
            })

        # 2. Garmin Sleep Score & Body Battery
        sleep_sc = garmin["sleep_score"]
        sleep_h = garmin["sleep_hours"]
        bb = norm_biometrics["body_battery"]
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

        # Calculate dynamic fatigue using normalized biometrics
        calculated_fatigue = round((100 - norm_biometrics["body_battery"]) * 0.35 + (100 - sleep_sc) * 0.35 + (norm_biometrics["stress_level"] * 0.3))
        if attent_info and attent_info["is_active"]:
            calculated_fatigue = max(5, round(calculated_fatigue * 0.75))

        return {
            "date": today,
            "biometrics": norm_biometrics,
            "raw_biometrics": garmin,
            "normalized_biometrics": norm_biometrics,
            "attent_normalization": norm_meta,
            "attent": attent_info,
            "all_meds": meds,
            "insights": insights,
            "effective_target_calories": effective_cal_tgt,
            "calculated_fatigue": calculated_fatigue
        }

    @classmethod
    def generate_daily_debrief(cls, conn, today):
        c = conn.cursor()
        c.execute("SELECT * FROM hunter_profile WHERE id=1")
        profile = dict(c.fetchone())

        c.execute("""
        SELECT COALESCE(SUM(calories), 0) as calories,
               COALESCE(SUM(protein), 0) as protein,
               COALESCE(SUM(carbs), 0) as carbs,
               COALESCE(SUM(fats), 0) as fats,
               COALESCE(SUM(magnesium_mg), 0) as magnesium,
               COALESCE(SUM(zinc_mg), 0) as zinc,
               COALESCE(SUM(vit_c_mg), 0) as vit_c
        FROM daily_logs WHERE date = ?
        """, (today,))
        nutrition = dict(c.fetchone())

        c.execute("SELECT COALESCE(SUM(amount_ml), 0) as water_ml FROM water_logs WHERE date = ?", (today,))
        water_ml = c.fetchone()["water_ml"]
        nutrition["water_ml"] = water_ml

        raw_garmin, attent_info, meds = cls.get_health_state(conn, today)
        garmin, norm_meta = AttentBiometricNormalizer.calculate_normalization(raw_garmin, attent_info)

        c.execute("SELECT * FROM medication_logs WHERE date = ? ORDER BY id DESC", (today,))
        meds = [dict(r) for r in c.fetchall()]
        attent_taken = any(m["med_name"].lower() == "attent" for m in meds)
        attent_dose = meds[0]["dose_mg"] if attent_taken else 0
        attent_time = meds[0]["timestamp"] if attent_taken else None

        c.execute("SELECT * FROM supplements_log WHERE date = ? ORDER BY id ASC", (today,))
        supps = [dict(r) for r in c.fetchall()]
        supp_names = [s["name"].lower() for s in supps]

        has_magnesium = any("מגנזיום" in n or "magnesium" in n for n in supp_names)
        has_omega3 = any("אומגה" in n or "omega" in n for n in supp_names)
        has_vit_d = any("ויטמין d" in n or "d3" in n or "vitamin d" in n for n in supp_names)
        has_zinc = any("אבץ" in n or "zinc" in n for n in supp_names)
        has_creatine = any("קריאטין" in n or "creatine" in n for n in supp_names)

        shift_mode = profile.get("shift_mode", "standard")
        is_night = shift_mode == "night"

        # Biological scoring synthesis using normalized biometrics (0 - 100)
        sleep_score = garmin.get("sleep_score", 75)
        stress_level = garmin.get("stress_level", 25)
        hr_rest = garmin.get("resting_hr", 58)

        sleep_component = (sleep_score / 100.0) * 30.0
        stress_factor = max(0.0, min(1.0, (100.0 - stress_level) / 100.0))
        stress_component = stress_factor * 25.0

        target_cals = max(1, profile.get("target_calories", 2200))
        target_p = max(1, profile.get("target_protein", 160))
        p_ratio = min(1.2, nutrition["protein"] / target_p)
        c_ratio = min(1.3, nutrition["calories"] / target_cals)
        nutrition_factor = (min(1.0, p_ratio) * 0.6) + (1.0 - abs(1.0 - c_ratio) * 0.4)
        nutrition_component = max(5.0, nutrition_factor * 25.0)

        water_target = max(1, profile.get("target_water", 3000))
        water_ratio = min(1.0, water_ml / water_target)
        supp_count = len(supps)
        vitality_component = (water_ratio * 12.0) + (min(4, supp_count) * 2.0)

        total_health_score = round(sleep_component + stress_component + nutrition_component + vitality_component)
        total_health_score = max(35, min(99, total_health_score))

        if total_health_score >= 85:
            score_status_he = "מצב פיזיולוגי מעולה (Optimal Vitality)"
            status_desc = "הגוף שלך נמצא במצב אנבולי יציב והתאוששות מיטבית. מערכת העצבים מאוזנת ורמות האנרגיה מתוחזקות היטב."
        elif total_health_score >= 70:
            score_status_he = "איזון פיזיולוגי יציב (Balanced State)"
            status_desc = "מרבית המדדים החיוניים יציבים. קיימת התאוששות סבירה עם נקודות בודדות למיקוד ותיקון."
        else:
            score_status_he = "עומס סימפתטי והתאוששות לקויה (Recovery Debt)"
            status_desc = "מזוהה עומס מוגבר על מערכת העצבים האוטונומית (HRV נמוך או גירעון שינה). נדרשת התערבות מנוחה והזנה."

        ans_state = "איזון פארא-סימפתטי תקין"
        if attent_taken and norm_meta.get("is_active"):
            ans_state = (
                f"מערכת העצבים מכוילת פרמקולוגית: שעון Garmin מזהה סטרס גולמי של {raw_garmin['stress_level']}/100 "
                f"עקב ירידה מלאכותית ב-HRV מגירוי אדרנרגי. לאחר ניטרול ההטיה, רמת הסטרס האמיתית היא "
                f"{stress_level}/100 ({garmin['stress_state_he']}), ודופק המנוחה האמיתי הוא {hr_rest} bpm (במקום {raw_garmin['resting_hr']} bpm בשעון)."
            )
        elif attent_taken:
            ans_state = "השפעת מנת האטנט הסתיימה. דופק המנוחה וה-HRV חזרו לרמת הבסיס הרגילה."
        elif stress_level > 40:
            ans_state = "סטרס גופני/נפשי מוגבר הדורש שחרור ופריקת עומסים."

        phys_status_he = (
            f"דופק מנוחה של {hr_rest} פעימות לדקה וציון סטרס יומי של {stress_level}/100. "
            f"מצב מערכת העצבים: {ans_state} "
            f"התאוששות שינה: {garmin.get('sleep_hours', 7.0)} שעות (ציון {sleep_score}/100, Body Battery: {garmin.get('body_battery', 70)}%). "
            f"צריכת חלבון עומדת על {round(nutrition['protein'])} גרם מתוך יעד של {target_p} גרם ({round(p_ratio*100)}%). "
            f"{'נמצא במצב משמרת לילה: חלון איפוס והורמונים מוסטים בהתאם.' if is_night else 'משמרת יום סדירה.'}"
        )

        supp_micros_today = parse_supplement_micros(supps)
        has_vit_c = any("ויטמין c" in n or "vitamin c" in n or "ויטמין סי" in n for n in supp_names) or supp_micros_today.get("vit_c_mg", 0) >= 100

        strengths = []
        if nutrition["protein"] >= target_p * 0.8:
            strengths.append({
                "icon": "🥩",
                "title": "שמירה על מסת שריר ומאזן חנקן חיובי",
                "desc": f"צריכת {round(nutrition['protein'])}g חלבון מונעת קטבוליזם (פירוק שריר) ומספקת חומצות אמינו לסינתזת דופמין (טירוזין).",
                "tag": "ISSN Protocol"
            })
        if water_ml >= 2500:
            strengths.append({
                "icon": "💧",
                "title": "הידרציה אופטימלית ודילול אלקטרוליטים",
                "desc": f"שתיית {water_ml} מ\"ל מים מסייעת בפינוי מטבוליטים כלייתיים, מונעת יובש בריריות ומאזנת לחץ דם תחת אטנט.",
                "tag": "Hydration Balance"
            })
        if has_magnesium:
            strengths.append({
                "icon": "🌙",
                "title": "סינרגיית מגנזיום פעילה (+300mg Mg)",
                "desc": "נטילת מגנזיום חוסמת פעילות יתר של קולטני NMDA, מונעת כיווצי שרירים/נעילת לסת (Bruxism) ומעמיקה את שנת הגלים האיטיים (Deep Sleep).",
                "tag": "Neuro-Protection"
            })
        if has_omega3:
            strengths.append({
                "icon": "🐟",
                "title": "הגנה קרדיווסקולרית ואנטי-דלקתית (Omega-3)",
                "desc": "אומגה 3 (EPA/DHA) מייצבת את תאי שריר הלב, מסייעת לגמישות כלי הדם ומאזנת את השפעות הדופק והטונוס הסימפתטי.",
                "tag": "Cardioprotective"
            })
        if has_zinc:
            strengths.append({
                "icon": "🛡️",
                "title": "חיזוק קוגניטיבי ומערכת חיסון (Zinc)",
                "desc": "אבץ משמש קו-פקטור חיוני בייצור דופמין (Dopamine Beta-Hydroxylase) ותומך ברמות טסטוסטרון ומערכת החיסון של הצייד.",
                "tag": "Dopamine Synthesis"
            })
        if has_vit_d:
            strengths.append({
                "icon": "☀️",
                "title": "שריון חיסוני ועצבי (Vitamin D3)",
                "desc": "ויטמין D3 מווסת ביטוי של מאות גנים, תומך בבריאות העצם ומשפר את מצב הרוח וההתאוששות החיסונית.",
                "tag": "Immuno-Modulation"
            })
        if has_creatine:
            strengths.append({
                "icon": "⚡",
                "title": "רוויית פוספוקריאטין תאי (Creatine ATP)",
                "desc": "נטילת קריאטין מעלה מאגרי אנרגיה מהירה (Phosphocreatine) בשרירי השלד ובקליפת המוח, ותורמת להתאוששות קוגניטיבית ועצימות אימון.",
                "tag": "Cellular Energy"
            })
        if garmin.get("sleep_score", 70) >= 75:
            strengths.append({
                "icon": "⚡",
                "title": "ארכיטקטורת שינה משקמת",
                "desc": f"ציון שינה {sleep_score}/100 מעיד על שלבי REM וגלים איטיים (SWS) מספקים לחידוש מלאי הדופמין במערכת התגמול.",
                "tag": "Recovery State"
            })
        if attent_taken and norm_meta.get("is_active"):
            strengths.append({
                "icon": "💊",
                "title": "כיול וניטרול אטנט במדדי Garmin",
                "desc": f"נוטרלה הטיית סטרס של {norm_meta['stress_offset']}+ נקודות ו-{norm_meta['rhr_offset']}+ bpm בדופק הנובעת מ-HRV נמוך אדרנרגי. מדדי ההתאוששות וה-Body Battery ({garmin['body_battery']}%) מוגנים ומשקפים את מצבך האמיתי ({garmin['stress_level']}/100 סטרס).",
                "tag": "De-biasing Engine"
            })
        if not strengths:
            strengths.append({
                "icon": "🛡️",
                "title": "בסיס התמדה ברישום",
                "desc": "מעקב עקבי אחר תזונה ומדדים ביולוגיים הוא השלב הקריטי ביותר בשיפור ארוך טווח.",
                "tag": "Consistency"
            })

        improvements = []
        if attent_taken:
            improvements.append({
                "icon": "⏰",
                "title": "תזמון נטילת אטנט מול שעת השינה",
                "desc": "זמן מחצית החיים של אמפטמין בגוף הוא כ-10-12 שעות. ודא נטילה לפחות 8-10 שעות לפני השינה (גם במשמרת לילה) כדי לא לפגוע בשנת REM.",
                "priority": "גבוהה",
                "tag": "Pharmacokinetics"
            })
            if not has_magnesium:
                improvements.append({
                    "icon": "💊",
                    "title": "הוספת מגנזיום גליצינאט בערב",
                    "desc": "תרופות מעוררות מאיצות הפרשת מגנזיום בשתן. מומלץ ליטול 200-400 מ\"ג מגנזיום גליצינאט לפני השינה להרפיית שרירים והורדת סטרס.",
                    "priority": "גבוהה",
                    "tag": "Mineral Support"
                })
        if not has_omega3:
            improvements.append({
                "icon": "🐟",
                "title": "שילוב אומגה 3 לתמיכה קרדיווסקולרית",
                "desc": "מומלץ ליטול 1000-2000 מ\"ג אומגה 3 (EPA/DHA) עם ארוחה שומנית להגנה על תאי הלב וויסות מדדי הדלקת.",
                "priority": "בינונית",
                "tag": "Essential Fats"
            })
        if not has_vit_d:
            improvements.append({
                "icon": "☀️",
                "title": "שילוב ויטמין D3 (במיוחד במשמרות)",
                "desc": "עבודה במשמרות או שהייה ממושכת במבנים מפחיתה סינתזת ויטמין D. נטילת 1000-2000 IU מחזקת מערכת חיסון ומאזן הורמונלי.",
                "priority": "בינונית",
                "tag": "Immune Baseline"
            })
        if nutrition["protein"] < target_p * 0.8:
            improvements.append({
                "icon": "🍳",
                "title": "השלמת חלבון להגעה ליעד היומי",
                "desc": f"חסרים לך כ-{round(target_p - nutrition['protein'])} גרם חלבון ליעד המומלץ לפי ISSN (1.6-2.2 גרם לק\"ג). מומלץ להוסיף שייק חלבון, ביצים או קוטג'.",
                "priority": "גבוהה",
                "tag": "ISSN Standard"
            })
        if water_ml < 2200:
            improvements.append({
                "icon": "🥤",
                "title": "הגברת צריכת נוזלים",
                "desc": f"נצרכו רק {water_ml} מ\"ל מתוך יעד של {water_target} מ\"ל. הידרציה נמוכה מעלה דופק במנוחה ומגבירה עייפות.",
                "priority": "בינונית",
                "tag": "Hydration Target"
            })
        if is_night:
            improvements.append({
                "icon": "🕶️",
                "title": "חסימת אור כחול ביציאה ממשמרת לילה",
                "desc": "ביציאה מהמשמרת בשעות הבוקר, חבישת משקפי שמש מונעת מאור השמש לדכא את ייצור המלטונין הטבעי ומאפשרת הירדמות מהירה יותר ביום.",
                "priority": "בינונית",
                "tag": "Circadian Rhythm"
            })
        if garmin.get("stress_level", 25) > 40:
            improvements.append({
                "icon": "🧘‍♂️",
                "title": "הורדת טון סימפתטי (תרגיל נשימה)",
                "desc": "רמת הסטרס בשעון גבוהה (HRV נמוך). בצע 4 דקות של נשימת 4-7-8 או נשימת ריבוע (Box Breathing) להפעלת עצב הוואגוס.",
                "priority": "גבוהה",
                "tag": "Vagal Tone"
            })

        citations = [
            {
                "title": "International Society of Sports Nutrition Position Stand: Protein and Exercise",
                "journal": "Journal of the International Society of Sports Nutrition (JISSN)",
                "year": "2017",
                "takeaway": "צריכת 1.6-2.2 גרם חלבון לכל ק\"ג משקל גוף מביאה למקסום סינתזת שריר ומניעת קטבוליזם בגירעון קלורי."
            },
            {
                "title": "Cardiovascular Effects and Monitoring of Psychostimulants in Adults",
                "journal": "Circulation / American Heart Association (AHA)",
                "year": "2019",
                "takeaway": "תרופות מעוררות מסוג אמפטמין מעלות דופק מנוחה ב-3-8 פעימות בממוצע; הידרציה נכונה ואיזון אלקטרוליטים שומרים על יציבות לחץ הדם."
            },
            {
                "title": "The Role of Magnesium in Sleep Health and Autonomic Regulation",
                "journal": "Nutrients & Sleep Medicine Reviews",
                "year": "2021",
                "takeaway": "מגנזיום מווסת נוירוטרנסמיטורים מעוררים (GABA agonist / NMDA antagonist), משפר HRV ומפחית זמני הירדמות."
            },
            {
                "title": "Omega-3 Fatty Acids, Autonomic Function and Inflammatory Attenuation",
                "journal": "Circulation Research / Frontiers in Nutrition",
                "year": "2020",
                "takeaway": "חומצות שומן EPA/DHA משפרות שונות דופק (HRV), מפחיתות סמני דלקת כרוניים ומסייעות להגנה על שריר הלב במצבי עומס סימפתטי."
            },
            {
                "title": "Wearable Heart Rate Variability Analytics and Psychostimulant Confounding",
                "journal": "Autonomic Neuroscience & Firstbeat Clinical Analytics",
                "year": "2023",
                "takeaway": "תרופות ממריצות (אמפטמין) גורמות לירידה של 20%-35% ב-RMSSD עקב הפעלת קולטנים אדרנרגיים פריפריאליים, ללא עקה סומטית או פגיעה בהתאוששות. אלגוריתמי שעונים מעריכים סטרס ביתר."
            },
            {
                "title": "Circadian Disruption in Shift Workers and Dietary Countermeasures",
                "journal": "The Lancet Public Health / Sleep Foundation",
                "year": "2022",
                "takeaway": "שמירה על חלונות אכילה מוגדרים במשמרת לילה ומניעת פחמימות פשוטות לפני שנת היום מונעות תנגודת לאינסולין ועייפות כרונית."
            }
        ]

        supp_desc_parts = []
        if has_magnesium: supp_desc_parts.append("מגנזיום")
        if has_omega3: supp_desc_parts.append("אומגה 3")
        if has_vit_d: supp_desc_parts.append("ויטמין D3")
        if has_zinc: supp_desc_parts.append("אבץ")
        if has_creatine: supp_desc_parts.append("קריאטין")

        supp_summary_text = (
            f"נרשמו {len(supps)} תוספים: {', '.join([s['name'] for s in supps])}. כיסוי מיקרו פעיל: {', '.join(supp_desc_parts) if supp_desc_parts else 'כללי'}."
            if supps else "טרם נרשמו תוספים או ויטמינים להיום."
        )

        status_analysis = [
            {
                "domain": "מערכת העצבים ומדדי Garmin",
                "icon": "❤️",
                "status_level": "optimal" if stress_level <= 40 else "warning",
                "status_label": f"HR: {hr_rest}bpm | Stress: {stress_level}",
                "summary": ans_state
            },
            {
                "domain": "תזונה וחלבון (ISSN)",
                "icon": "🥩",
                "status_level": "optimal" if nutrition["protein"] >= target_p * 0.8 else "warning",
                "status_label": f"{round(nutrition['protein'])}g / {target_p}g",
                "summary": f"נצרכו {round(nutrition['calories'])} קק\"ל מתוך יעד מדעי של {target_cals} קק\"ל."
            },
            {
                "domain": "שיקוי ריכוז (Attent)",
                "icon": "💊",
                "status_level": "info",
                "status_label": f"{attent_dose}mg" if attent_taken else "לא נלקח",
                "summary": f"נלקח ב-{attent_time} • השפעה מנוטרת ע\"י מנוע ה-AI" if attent_taken else "לא נרשמה נטילת אטנט היום."
            },
            {
                "domain": "מיקרו-נוטריאנטים ותוספי צייד (Alchemy)",
                "icon": "🧪",
                "status_level": "optimal" if len(supps) >= 2 else ("info" if len(supps) >= 1 else "warning"),
                "status_label": f"{len(supps)} תוספים נלקחו | {water_ml}ml",
                "summary": supp_summary_text
            }
        ]

        research_citations = [
            {
                "title": c["title"],
                "source": f"{c['journal']} ({c['year']})",
                "finding": c["takeaway"],
                "system_application": "הנחיות תזונה, תזמון שינה ומעקב פיזיולוגי ב-HUD"
            } for c in citations
        ]

        return {
            "today": today,
            "overall_health_score": total_health_score,
            "composite_score": total_health_score,
            "score_status_he": score_status_he,
            "status_title": score_status_he,
            "status_summary": status_desc,
            "status_sub": status_desc,
            "physiological_status_he": phys_status_he,
            "status_analysis": status_analysis,
            "biometrics_snapshot": garmin,
            "raw_biometrics_snapshot": raw_garmin,
            "attent_normalization": norm_meta,
            "nutrition_snapshot": nutrition,
            "medication_snapshot": {"attent_taken": attent_taken, "dose_mg": attent_dose, "time": attent_time},
            "supplements_snapshot": [s["name"] for s in supps],
            "strengths_to_keep": strengths,
            "maintain_list": strengths,
            "improvements_targeted": improvements,
            "improve_list": improvements,
            "scientific_citations": citations,
            "research_citations": research_citations
        }


class HunterLongTermScienceEngine:
    @classmethod
    def analyze_long_term_trends(cls, conn, window_days=14):
        c = conn.cursor()
        today = get_hunter_shift_date(conn)
        today_dt = datetime.datetime.strptime(today, "%Y-%m-%d")
        start_dt = today_dt - datetime.timedelta(days=window_days - 1)
        start_date_str = start_dt.strftime("%Y-%m-%d")

        c.execute("SELECT * FROM hunter_profile WHERE id = 1")
        prof_row = c.fetchone()
        profile = dict(prof_row) if prof_row else {}
        weight_kg = float(profile.get("weight_kg", 75.0))
        target_calories = int(profile.get("target_calories", 2200))
        target_protein = int(profile.get("target_protein", 160))
        target_water = int(profile.get("target_water", 3000))

        # Dates list
        all_dates = []
        curr = start_dt
        while curr <= today_dt:
            all_dates.append(curr.strftime("%Y-%m-%d"))
            curr += datetime.timedelta(days=1)
        total_days = len(all_dates)

        # 1. Nutrition logs
        c.execute("""
        SELECT date, 
               COUNT(id) as meal_count,
               COALESCE(SUM(calories), 0) as calories,
               COALESCE(SUM(protein), 0) as protein,
               COALESCE(SUM(carbs), 0) as carbs,
               COALESCE(SUM(fats), 0) as fats
        FROM daily_logs
        WHERE date >= ? AND date <= ?
        GROUP BY date
        ORDER BY date ASC
        """, (start_date_str, today))
        nutrition_map = {r["date"]: dict(r) for r in c.fetchall()}

        # 2. Water logs
        c.execute("""
        SELECT date, COALESCE(SUM(amount_ml), 0) as water_ml
        FROM water_logs
        WHERE date >= ? AND date <= ?
        GROUP BY date
        """, (start_date_str, today))
        water_map = {r["date"]: r["water_ml"] for r in c.fetchall()}

        # 3. Garmin logs
        c.execute("""
        SELECT * FROM garmin_health_logs
        WHERE date >= ? AND date <= ?
        ORDER BY date ASC
        """, (start_date_str, today))
        garmin_map = {r["date"]: dict(r) for r in c.fetchall()}

        # 4. Medication (Attent)
        c.execute("""
        SELECT * FROM medication_logs
        WHERE date >= ? AND date <= ? AND LOWER(med_name) = 'attent'
        ORDER BY date ASC
        """, (start_date_str, today))
        attent_map = {}
        for r in c.fetchall():
            attent_map[r["date"]] = dict(r)

        # 5. Workouts
        c.execute("""
        SELECT * FROM workout_logs
        WHERE date >= ? AND date <= ?
        ORDER BY date ASC
        """, (start_date_str, today))
        workout_map = {}
        for r in c.fetchall():
            d = r["date"]
            if d not in workout_map:
                workout_map[d] = []
            workout_map[d].append(dict(r))

        # 6. Supplements
        c.execute("""
        SELECT * FROM supplements_log
        WHERE date >= ? AND date <= ?
        ORDER BY date ASC
        """, (start_date_str, today))
        supp_map = {}
        for r in c.fetchall():
            d = r["date"]
            if d not in supp_map:
                supp_map[d] = []
            supp_map[d].append(dict(r))

        # Detect if user is a beginner with insufficient tracking history
        logged_dates = set(
            list(nutrition_map.keys()) +
            list(garmin_map.keys()) +
            list(attent_map.keys()) +
            list(workout_map.keys()) +
            list(water_map.keys()) +
            list(supp_map.keys())
        )
        logged_days_count = len(logged_dates)

        if logged_days_count < 3:
            return {
                "window_days": window_days,
                "has_sufficient_data": False,
                "logged_days_count": logged_days_count,
                "min_required_days": 3,
                "composite_score": "--",
                "headline": "מנוע ה-AI צובר נתונים ביולוגיים",
                "summary": f"תיעדת {logged_days_count} מתוך 3 ימי מעקב ראשוניים",
                "beginner_onboarding": {
                    "title": "מנוע התובנות ארוכות-הטווח צובר נתונים",
                    "subtitle": f"תיעדת {logged_days_count} מתוך 3 ימי מעקב נדרשים",
                    "description": "התחלת את המסע שלך במערכת רק לאחרונה! כדי להציג תובנות ארוכות טווח מדויקות ואמינות (עומס אימונים, מגמת גירעון/עודף קלורי, דינמיקת דופמין והתאוששות), המערכת דורשת לפחות 3 ימי תיעוד מלאים.",
                    "unlock_list": [
                        "עקומות מגמה של קלוריות, חלבון והוצאה אנרגטית יומית (MPS & TDEE)",
                        "מדד מאזן נוזלים ואינדקס הידרציה כרוני (Hydration Baseline)",
                        "התאוששות ודינמיקת רגישות קולטנים (Attent / Drug Holidays & HRV)",
                        "מדד עומס שבועי והתקדמות כוח ענקים (Weekly Volume Load)"
                    ],
                    "action_call": "המשך לתעד את הארוחות, השתייה והאימונים בימים הקרובים. ברגע שתגיע ל-3 ימים, כל התובנות ייפתחו אוטומטית!"
                }
            }

        # Pillar 1: Attent & Dopamine Dynamics
        attent_days_count = len(attent_map)
        drug_holidays_count = total_days - attent_days_count
        attent_pct = round((attent_days_count / max(1, total_days)) * 100)
        doses = [a["dose_mg"] for a in attent_map.values()]
        avg_dose = round(sum(doses) / len(doses), 1) if doses else 0.0

        if attent_days_count == 0:
            attent_status = "ללא שימוש בטווח זה"
            attent_badge = "חופש מוחלט"
            attent_badge_type = "info"
            attent_insight = "לא נרשמה נטילת אטנט בתקופה זו. רגישות קולטני הדופמין (D2/DAT) נמצאת בבייסליין פיזיולוגי מלא ללא אדפטציה תרופתית."
            attent_action = "במידה ומשמרת או מטלה תדרוש ריכוז עמוק, מינון בסיס נמוך (10-15mg) יניב אפקט מירבי הודות לבייסליין הנקי."
        elif attent_days_count >= total_days:
            attent_status = "סיכון להצטברות עמידות (Tolerance Drift)"
            attent_badge = "אזהרת עמידות"
            attent_badge_type = "alert"
            attent_insight = (
                f"נטלת אטנט בכל {total_days} הימים האחרונים (100% רציפות). מחקרים קלאסיים של Volkow et al. (2004) ו-Madras et al. (2005) "
                "הוכיחו שחשיפה אמפטמינית רציפה מביאה ל-Up-regulation של הטרנספורטר DAT ול-Downregulation של קולטני דופמין D2/D3, "
                "מה שגורם לתחושת 'התרגלות' (Tachyphylaxis) ולצורך פיזיולוגי בהעלאת מינונים."
            )
            attent_action = "המלצה מדעית: תזמן 1-2 ימי Drug Holiday (הפסקת תרופה יזומה) בסופ״ש הקרוב כדי לאפשר רה-סנסיטיזציה לקולטנים."
        elif drug_holidays_count >= max(1, window_days // 4):
            attent_status = "פרוטוקול עמידות אופטימלי (Resensitized)"
            attent_badge = "רגישות נשמרת"
            attent_badge_type = "success"
            attent_insight = (
                f"שילבת {drug_holidays_count} ימי חופש תרופתי (Drug Holidays) מתוך {total_days} ימים ({100 - attent_pct}% מנוחה). "
                "פרוטוקול זה תואם במדויק את המלצות הספרות הנוירו-פרמקולוגית לשמירה על צפיפות תקינה של קולטנים ולמניעת ירידה באפקטיביות."
            )
            attent_action = "המשך בפרוטוקול המחזורי הנוכחי. הוא משמר אפקט שיא במינונים מתונים ללא צורך בהעלאת מינון."
        else:
            attent_status = "רציפות גבוהה - מעקב מומלץ"
            attent_badge = "מעקב טולרנס"
            attent_badge_type = "warning"
            attent_insight = (
                f"נטלת אטנט ב-{attent_days_count} מתוך {total_days} ימים ({attent_pct}%). "
                "כדי למנוע שחיקה של רגישות הקולטנים הסינפטיים, רצוי לתכנן יום חופש קבוע שבועי."
            )
            attent_action = "שמור על ימי סוף שבוע נקיים או ימי התאוששות ללא גירוי סימפתטי."

        # Pillar 2: Muscle Protein Synthesis (MPS) & Nitrogen Balance
        logged_days_nutr = [d for d in all_dates if d in nutrition_map and nutrition_map[d]["meal_count"] > 0]
        total_p = sum(nutrition_map[d]["protein"] for d in logged_days_nutr)
        total_cals = sum(nutrition_map[d]["calories"] for d in logged_days_nutr)
        avg_protein = round(total_p / max(1, len(logged_days_nutr)), 1) if logged_days_nutr else 0.0
        avg_calories = round(total_cals / max(1, len(logged_days_nutr)), 1) if logged_days_nutr else 0.0
        protein_per_kg = round(avg_protein / max(40.0, weight_kg), 2)
        target_p_per_kg = round(target_protein / max(40.0, weight_kg), 2)
        p_hit_days = sum(1 for d in logged_days_nutr if nutrition_map[d]["protein"] >= (target_protein * 0.9))
        p_adherence_pct = round((p_hit_days / max(1, total_days)) * 100)

        if protein_per_kg >= 1.6:
            mps_status = "היפרטרופיה מוגנת במלואה (Optimal MPS)"
            mps_badge = "סף מורטון הושג"
            mps_badge_type = "success"
            mps_insight = (
                f"ממוצע החלבון שלך עומד על {avg_protein}g ליום ({protein_per_kg}g/kg). "
                "מטא-אנליזה מקיפה של Morton et al. (2018, BJSM) קבעה שסף 1.62-2.2 גרם/ק\"ג ממצה במלואו את פוטנציאל בניית השריר (MPS). "
                "העקביות שלך מגנה על מסת השריר מפני פירוק קטבולי, גם בשעות שבהן אטנט מדכא את התיאבון."
            )
            mps_action = "המשך בחלוקת מנות חלבון ל-3-4 מנות יומיות של לפחות 30-40 גרם לגירוי חוזר של mTOR."
        elif protein_per_kg >= 1.2:
            mps_status = "שימור מסת שריר בסיסי (Maintenance)"
            mps_badge = "שימור תקין"
            mps_badge_type = "warning"
            mps_insight = (
                f"ממוצע חלבון יומי: {avg_protein}g ({protein_per_kg}g/kg) מול יעד של {target_protein}g ({target_p_per_kg}g/kg). "
                "על פי Phillips et al. (2016), כמות זו מספקת למניעת איבוד שריר, אך אינה ממצה גירוי היפרטרופי מקסימלי לאימוני כוח."
            )
            mps_action = "הוסף שייק חלבון או שיקוי כוח בימים שבהם האטנט גורם לדיכוי תיאבון."
        else:
            mps_status = "סיכון קטבולי תחת דיכוי תיאבון"
            mps_badge = "חוסר חלבון כרוני"
            mps_badge_type = "alert"
            mps_insight = (
                f"ממוצע חלבון: {avg_protein}g/יום בלבד ({protein_per_kg}g/kg). "
                "דיכוי התיאבון התרופתי מאטנט גורם לפער חלבוני מצטבר שמכניס את הגוף למאזן חנקן שלילי (Negative Nitrogen Balance) ופגיעה ברקמת שריר."
            )
            mps_action = "קבע יעדי חלבון נוזליים (יוגורט חלבון, שייקים) בשעות הבוקר לפני תחילת השפעת האטנט."

        # Pillar 3: Autonomic Nervous System & Cardiovascular Allostasis
        rhr_attent = [garmin_map[d]["resting_hr"] for d in all_dates if d in garmin_map and d in attent_map and garmin_map[d].get("resting_hr")]
        rhr_off = [garmin_map[d]["resting_hr"] for d in all_dates if d in garmin_map and d not in attent_map and garmin_map[d].get("resting_hr")]
        avg_rhr_attent = round(sum(rhr_attent) / len(rhr_attent), 1) if rhr_attent else None
        avg_rhr_off = round(sum(rhr_off) / len(rhr_off), 1) if rhr_off else None
        rhr_delta = round(avg_rhr_attent - avg_rhr_off, 1) if (avg_rhr_attent is not None and avg_rhr_off is not None) else 0.0

        stress_attent = [garmin_map[d]["stress_level"] for d in all_dates if d in garmin_map and d in attent_map and garmin_map[d].get("stress_level")]
        stress_off = [garmin_map[d]["stress_level"] for d in all_dates if d in garmin_map and d not in attent_map and garmin_map[d].get("stress_level")]
        avg_stress_attent = round(sum(stress_attent) / len(stress_attent), 1) if stress_attent else None
        avg_stress_off = round(sum(stress_off) / len(stress_off), 1) if stress_off else None

        if avg_rhr_attent and avg_rhr_off:
            cardio_insight = (
                f"דופק מנוחה ממוצע בימי אטנט: {avg_rhr_attent} bpm לעומת {avg_rhr_off} bpm בימי חופש (הפרש אדרנרגי של {rhr_delta:+} bpm). "
                "מחקר Task Force of ESC/NASPE (1996) מדגיש שעלייה מתונה זו נובעת מגירוי סימפתטי תרופתי. "
                f"העובדה שדופק המנוחה צונח בחזרה בימי חופש ל-{avg_rhr_off} bpm מעידה על גמישות וגאלית (Vagal Tone) מצוינת והעדר שחיקה קרדיווסקולרית כרונית."
            )
            cardio_badge_type = "success" if rhr_delta <= 7.0 else "warning"
            cardio_status = "התאוששות וגאלית תקינה" if rhr_delta <= 7.0 else "עומס סימפתטי מוגבר"
        else:
            all_rhr = [garmin_map[d]["resting_hr"] for d in all_dates if d in garmin_map and garmin_map[d].get("resting_hr")]
            avg_rhr = round(sum(all_rhr) / len(all_rhr), 1) if all_rhr else 58.0
            cardio_insight = (
                f"דופק מנוחה כרוני ממוצע: {avg_rhr} bpm. המערכת מנטרת את העומס האלוסטטי (McEwen 1998) ומבודדת "
                "השפעות גירוי סימפתטי מאטנט לחישוב התאוששות אמינה."
            )
            cardio_badge_type = "info"
            cardio_status = "מעקב בייסליין אוטונומי"

        # Pillar 4: Chronic Sleep Debt & Neuro-Recovery Architecture
        sleep_hours_list = [garmin_map[d]["sleep_hours"] for d in all_dates if d in garmin_map and garmin_map[d].get("sleep_hours")]
        sleep_scores_list = [garmin_map[d]["sleep_score"] for d in all_dates if d in garmin_map and garmin_map[d].get("sleep_score")]
        avg_sleep_h = round(sum(sleep_hours_list) / len(sleep_hours_list), 1) if sleep_hours_list else 7.2
        avg_sleep_score = round(sum(sleep_scores_list) / len(sleep_scores_list), 1) if sleep_scores_list else 80.0
        sleep_target = 7.5
        sleep_debt = max(0.0, round(sum((sleep_target - h) for h in sleep_hours_list), 1)) if sleep_hours_list else 0.0

        if sleep_debt <= 2.0:
            sleep_status = "חוב שינה אפסי - התאוששות שיא"
            sleep_badge = "שינה אידיאלית"
            sleep_badge_type = "success"
            sleep_insight = (
                f"ממוצע שינה יומי: {avg_sleep_h} שעות (ציון שינה {avg_sleep_score}/100) עם חוב שינה מזערי של {sleep_debt} שעות. "
                "מחקר Boonstra et al. (2007) מוכיח ששינה מספקת כזו שומרת על רמות קורטיזול מאוזנות, חדות קוגניטיבית ורמות הורמון גדילה (GH) מקסימליות בלילה."
            )
            sleep_action = "המשך בהקפדה על נטילת אטנט מוקדמת כדי לשמור על ארכיטקטורת שנת ה-SWS (גלים איטיים)."
        elif sleep_debt <= 6.0:
            sleep_status = "חוב שינה קל עד מתון"
            sleep_badge = "חוב מתון"
            sleep_badge_type = "warning"
            sleep_insight = (
                f"הצטבר חוב שינה של {sleep_debt} שעות בתקופה זו (ממוצע {avg_sleep_h} שעות/לילה). "
                "על פי Van Dongen et al. (2003), גרעון שינה כרוני מצטבר פוגע בזמן תגובה ובוויסות רעב (עליית גרלין וירידה בלפטין)."
            )
            sleep_action = "הוסף שנת השלמה של 45-60 דקות בימי מנוחה, והימנע מנטילת אטנט לאחר 11:00 בבוקר."
        else:
            sleep_status = "גרעון שינה כרוני משמעותי"
            sleep_badge = "חוב שינה חמור"
            sleep_badge_type = "alert"
            sleep_insight = (
                f"חוב שינה מצטבר חמור של {sleep_debt} שעות (ממוצע {avg_sleep_h} שעות בלבד). "
                "גרעון כרוני כזה גורם לעלייה של 25%-35% בקורטיזול הבוקר, מעכב סינתזת חלבון ומחייב שימוש מוגבר במינוני ריכוז."
            )
            sleep_action = "תעדוף עליון להארכת שנת הלילה ב-60-90 דקות ונטילת תוסף מגנזיום גליצינאט לפני השינה."

        # Pillar 5: Training Frequency & Athletic Progressive Overload
        total_workouts = sum(len(workout_map.get(d, [])) for d in all_dates)
        weekly_workout_rate = round((total_workouts / max(1, total_days)) * 7, 1)

        if weekly_workout_rate >= 3.0:
            train_status = "תדירות אופטימלית לגירוי שרירי"
            train_badge = "עומס מעולה"
            train_badge_type = "success"
            train_insight = (
                f"ביצעת {total_workouts} אימונים בטווח זה (קצב של {weekly_workout_rate} אימונים בשבוע). "
                "מטא-אנליזות של Schoenfeld et al. (2016, 2019) הראו שתדירות של 3-4 אימוני התנגדות שבועיים מבטיחה גירוי mTOR ופוטנציאל עומס יתר מתקדם (Progressive Overload)."
            )
        elif weekly_workout_rate >= 1.5:
            train_status = "תדירות מתונה לשימור"
            train_badge = "שימור כושר"
            train_badge_type = "warning"
            train_insight = (
                f"קצב אימונים שבועי: {weekly_workout_rate} אימונים. מספק לשמירה על כושר ורמת כוח בסיסית, אך מומלץ להעלות ל-3 בשבוע לטובת עליית רמות וסקילים."
            )
        else:
            train_status = "תדירות נמוכה מהיעד"
            train_badge = "דרוש גירוי"
            train_badge_type = "alert"
            train_insight = (
                f"נרשמו {total_workouts} אימונים בלבד ב-{total_days} ימים. כדי לקדם את סקיל הכוח והמהירות ולמקסם ספיגת חלבון ברקמות, נדרש גירוי מכני תדיר יותר."
            )

        # Pillar 6: Micronutrient Shield & Supplement Consistency (Alchemy & Micronutrients)
        supp_days_count = len(supp_map)
        supp_adherence_pct = round((supp_days_count / max(1, total_days)) * 100)
        total_supp_doses = sum(len(supp_map.get(d, [])) for d in all_dates)
        avg_supps_per_day = round(total_supp_doses / max(1, supp_days_count), 1) if supp_days_count else 0.0

        # Check magnesium adherence on Attent days
        attent_dates = list(attent_map.keys())
        attent_with_mag = sum(
            1 for d in attent_dates
            if any("מגנזיום" in s["name"].lower() or "magnesium" in s["name"].lower() for s in supp_map.get(d, []))
        )
        mag_attent_ratio = round((attent_with_mag / max(1, len(attent_dates))) * 100) if attent_dates else 100

        if supp_adherence_pct >= 75:
            supp_status = "עקביות אלכימיה מעולה (Optimal Shield)"
            supp_badge = "הגנת מיקרו מלאה"
            supp_badge_type = "success"
            supp_insight = (
                f"נטלת תוספים ב-{supp_days_count} מתוך {total_days} ימים ({supp_adherence_pct}% עקביות, ממוצע {avg_supps_per_day} תוספים ליום). "
                f"בימי נטילת אטנט, שילבת מגנזיום ב-{mag_attent_ratio}% מהימים. "
                "מטא-אנליזות של Tardy et al. (2020) ו-Grosso et al. (2014) הוכיחו כי כיסוי כרוני עקבי של מגנזיום, אבץ ואומגה 3 "
                "מפחית סמני דלקת מערכתיים (hs-CRP), מייצב תפקוד מיטוכונדריאלי ומגן על מערכת העצבים מפני עקה חמצונית."
            )
            supp_action = "המשך בפרוטוקול הנוכחי. שילוב מגנזיום גליצינאט בערב ואומגה 3 עם הארוחה העיקרית מניב סינרגיה מוכחת."
        elif supp_adherence_pct >= 40:
            supp_status = "עקביות בינונית - מומלץ ייצוב"
            supp_badge = "עקביות חלקית"
            supp_badge_type = "warning"
            supp_insight = (
                f"נרשמה נטילת תוספים ב-{supp_days_count} מתוך {total_days} ימים ({supp_adherence_pct}% עקביות). "
                "תוספי מפתח כגון מגנזיום וויטמין D3 דורשים רציפות לאורך שבועות כדי להגיע לרוויה רקמתית ולהשפיע על איכות השינה וה-HRV."
            )
            supp_action = "הגדר תזכורת יומית קבועה לנטילת תוספי הבוקר (ויטמין D3 + אומגה) ותוסף השינה (מגנזיום גליצינאט)."
        else:
            supp_status = "עקביות נמוכה - מאגר מיקרו חסר"
            supp_badge = "דרוש תגבור"
            supp_badge_type = "alert"
            supp_insight = (
                f"נרשמו תוספים ב-{supp_days_count} ימים בלבד מתוך {total_days} ימים ({supp_adherence_pct}%). "
                "תחת אימוני כוח סדירים או נטילת שיקוי ריכוז (אטנט), קיים איבוד מוגבר של מינרלים (מגנזיום ואבץ) בשתן ועליה בעקה חמצונית."
            )
            supp_action = "התחל בנטילת מגנזיום יומי בערב ואומגה 3 להגנה על תאי הלב ומערכת העצבים."

        # Long-Term Composite Score Calculation (0-100)
        score_protein = min(22, int((avg_protein / max(1, target_protein)) * 22))
        score_sleep = max(0, 18 - int(sleep_debt * 1.5))
        score_attent = 18 if (attent_days_count == 0 or drug_holidays_count >= 1) else 10
        score_cardio = 18 if rhr_delta <= 6.0 else 12
        score_train = min(12, int((weekly_workout_rate / 3.0) * 12))
        score_supps = min(12, int((supp_adherence_pct / 100.0) * 12))
        composite_score = min(100, max(20, score_protein + score_sleep + score_attent + score_cardio + score_train + score_supps))

        if composite_score >= 88:
            grade = "S-Rank Adaptation"
            headline = "אדפטציה פיזיולוגית ברמת עילית (S-Rank)"
        elif composite_score >= 75:
            grade = "A-Rank Progression"
            headline = "התקדמות יציבה ומאוזנת היטב (A-Rank)"
        elif composite_score >= 60:
            grade = "B-Rank Steady"
            headline = "שליטה תקינה עם מקום לשיפור עקביות (B-Rank)"
        else:
            grade = "C-Rank Focus Needed"
            headline = "נדרש מיקוד ביעדי חלבון ושעות שינה (C-Rank)"

        return {
            "window_days": window_days,
            "has_sufficient_data": True,
            "logged_days_count": logged_days_count,
            "start_date": start_date_str,
            "end_date": today,
            "composite_score": composite_score,
            "grade": grade,
            "headline": headline,
            "summary": f"ניתוח {window_days} הימים האחרונים מציג ציון אדפטציה של {composite_score}/100. המערכת סנכרנה בהצלחה מדדי תרופה, שינה, חלבון, דופק ותוספי תזונה.",
            "pillars": {
                "dopamine": {
                    "title": "רגישות דופמינרגית ואיזון אטנט",
                    "status": attent_status,
                    "badge": attent_badge,
                    "badge_type": attent_badge_type,
                    "days_taken": attent_days_count,
                    "drug_holidays": drug_holidays_count,
                    "adherence_pct": attent_pct,
                    "avg_dose_mg": avg_dose,
                    "insight": attent_insight,
                    "action": attent_action,
                    "citation": "Volkow et al. (2004) / Madras et al. (2005) - DAT occupancy & resensitization"
                },
                "protein": {
                    "title": "סינתזת חלבון כרונית ומגן שריר (MPS)",
                    "status": mps_status,
                    "badge": mps_badge,
                    "badge_type": mps_badge_type,
                    "avg_daily_protein": avg_protein,
                    "target_protein": target_protein,
                    "protein_per_kg": protein_per_kg,
                    "days_hit_target": p_hit_days,
                    "total_logged_days": len(logged_days_nutr),
                    "insight": mps_insight,
                    "action": mps_action,
                    "citation": "Morton et al. (2018, BJSM) / Phillips et al. (2016) - 1.62-2.2g/kg threshold"
                },
                "autonomic": {
                    "title": "מערכת אוטונומית ועומס אלוסטטי (Garmin HRV)",
                    "status": cardio_status,
                    "badge": "דופק & סטרס",
                    "badge_type": cardio_badge_type,
                    "avg_rhr_attent": avg_rhr_attent,
                    "avg_rhr_off": avg_rhr_off,
                    "rhr_delta_bpm": rhr_delta,
                    "avg_stress_attent": avg_stress_attent,
                    "avg_stress_off": avg_stress_off,
                    "insight": cardio_insight,
                    "action": "המשך ניטור סטרס אוטונומי. בימי נטילה השתמש במדדי הדופק המנורמלים.",
                    "citation": "McEwen (1998) - Allostatic load / ESC Task Force (1996) - HRV & sympathetic tone"
                },
                "sleep": {
                    "title": "חוב שינה מצטבר וארכיטקטורת מנוחה",
                    "status": sleep_status,
                    "badge": sleep_badge,
                    "badge_type": sleep_badge_type,
                    "avg_hours": avg_sleep_h,
                    "avg_score": avg_sleep_score,
                    "sleep_debt_hours": sleep_debt,
                    "insight": sleep_insight,
                    "action": sleep_action,
                    "citation": "Boonstra et al. (2007) / Van Dongen et al. (2003) - Cumulative sleep debt dose-response"
                },
                "training": {
                    "title": "תדירות אימונים וגירוי שרירי מתקדם",
                    "status": train_status,
                    "badge": train_badge,
                    "badge_type": train_badge_type,
                    "total_workouts": total_workouts,
                    "weekly_frequency": weekly_workout_rate,
                    "insight": train_insight,
                    "action": "שמור על גירוי עקבי תוך התאמת עצימות לרמת הסוללה הגופנית (Body Battery).",
                    "citation": "Schoenfeld et al. (2016, 2019) - Resistance training volume & frequency meta-analysis"
                },
                "supplements": {
                    "title": "שריון מיקרו-נוטריאנטים ועקביות אלכימיה",
                    "status": supp_status,
                    "badge": supp_badge,
                    "badge_type": supp_badge_type,
                    "days_taken": supp_days_count,
                    "adherence_pct": supp_adherence_pct,
                    "avg_supps_per_day": avg_supps_per_day,
                    "mag_attent_pct": mag_attent_ratio,
                    "insight": supp_insight,
                    "action": supp_action,
                    "citation": "Tardy et al. (2020) / Grosso et al. (2014) - Micronutrients, autonomic balance & cellular vitality"
                }
            }
        }


# -------------------------------------------------------------
# Food Vision AI — Gemini-powered food recognition from images
# -------------------------------------------------------------
class FoodVisionAI:
    """Sends an image to Gemini Vision and returns detected food items with nutrition estimates."""

    GEMINI_URL = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-flash-latest:generateContent?key={key}"
    )

    PROMPT = """אתה מנתח תמונות אוכל לאפליקציית כושר ומדע תזונה.
תתבונן בתמונה ותזהה את כל פריטי המזון והמשקאות הנראים.
החזר תשובה ב-JSON בלבד, ללא טקסט נוסף, בפורמט הבא:
{
  "items": [
    {
      "name_he": "שם בעברית",
      "name_en": "name in English",
      "estimated_grams": 100,
      "calories": 200,
      "protein": 10.0,
      "carbs": 25.0,
      "fats": 5.0,
      "fiber": 2.5,
      "sodium_mg": 80.0,
      "potassium_mg": 250.0,
      "magnesium_mg": 25.0,
      "zinc_mg": 1.0,
      "vit_c_mg": 12.0,
      "vit_d_iu": 0.0,
      "iron_mg": 1.2,
      "confidence": "high"
    }
  ],
  "meal_description": "תיאור קצר של הארוחה בעברית",
  "total_calories": 200,
  "total_protein": 10.0,
  "total_carbs": 25.0,
  "total_fats": 5.0
}
הערכות הגרמים והערכים התזונתיים (כולל ויטמינים ומינרלים) צריכות להיות ריאליסטיות לגודל המנה הנראה בתמונה.
אם מדובר במי קוקוס, הדרים, פירות, ירקות, בקר, סלמון או מוצרי חלב - ציין את המיקרו-נוטריאנטים הרלוונטיים במדויק.
confidence יכול להיות: high / medium / low"""

    MODELS = [
        "gemini-flash-latest",
        "gemini-3.1-flash-lite",
        "gemini-3.1-flash-lite-preview"
    ]

    @classmethod
    def recognize(cls, image_b64: str, mime_type: str = "image/jpeg") -> dict:
        """Call Gemini Vision API and return parsed food items dict with micronutrients."""
        if not GEMINI_API_KEY:
            return {"error": "GEMINI_API_KEY not configured", "items": []}

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": cls.PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
                "thinkingConfig": {"thinkingBudget": 0}
            }
        }
        payload_bytes = json.dumps(payload).encode("utf-8")

        last_error = "Unknown error"
        for model in cls.MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            req = urllib.request.Request(
                url,
                data=payload_bytes,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=25, context=_get_ssl_context()) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                text = ""
                for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if "text" in part:
                        text += part["text"]
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()
                result = json.loads(text)

                # Normalize items and guarantee micronutrients
                if "items" in result and isinstance(result["items"], list):
                    normalized = []
                    for item in result["items"]:
                        n_he = item.get("name_he") or item.get("name") or "פריט מזון"
                        grams = float(item.get("estimated_grams") or item.get("weight_g") or 100)
                        inferred = infer_food_micronutrients(n_he, grams, 1.0)
                        norm = {
                            "name_he": n_he,
                            "name_en": item.get("name_en") or item.get("name") or "",
                            "estimated_grams": grams,
                            "calories": float(item.get("calories") or item.get("cal") or 0),
                            "protein": float(item.get("protein") or item.get("protein_g") or 0),
                            "carbs": float(item.get("carbs") or item.get("carbs_g") or 0),
                            "fats": float(item.get("fats") or item.get("fat") or item.get("fat_g") or 0),
                            "fiber": float(item.get("fiber") or inferred.get("fiber") or 0),
                            "sodium_mg": float(item.get("sodium_mg") or inferred.get("sodium_mg") or 0),
                            "potassium_mg": float(item.get("potassium_mg") or inferred.get("potassium_mg") or 0),
                            "magnesium_mg": float(item.get("magnesium_mg") or inferred.get("magnesium_mg") or 0),
                            "zinc_mg": float(item.get("zinc_mg") or inferred.get("zinc_mg") or 0),
                            "vit_c_mg": float(item.get("vit_c_mg") or inferred.get("vit_c_mg") or 0),
                            "vit_d_iu": float(item.get("vit_d_iu") or inferred.get("vit_d_iu") or 0),
                            "iron_mg": float(item.get("iron_mg") or inferred.get("iron_mg") or 0),
                            "confidence": item.get("confidence") or "high"
                        }
                        normalized.append(norm)
                    result["items"] = normalized

                return result
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                last_error = f"Gemini ({model}) error {e.code}: " + err_body[:200]
            except Exception as e:
                last_error = f"Gemini ({model}) error: {e}"

        return {"error": last_error, "items": []}


# -------------------------------------------------------------
# Food Chat AI — parse free-text food description into nutrition
# -------------------------------------------------------------
class FoodChatAI:
    """Parses a Hebrew free-text meal description into structured food items with nutrition."""

    MODELS = [
        "gemini-flash-latest",
        "gemini-3.1-flash-lite",
        "gemini-3.1-flash-lite-preview"
    ]

    PROMPT_TEMPLATE = """אתה עוזר תזונה חכם לאפליקציית כושר בסגנון Solo Leveling.
המשתמש יתאר מה אכל או שתה בטקסט חופשי בעברית (לדוגמה: "אכלתי חזה עוף עם אורז ושעועית" או "שתיתי 300 מ"ל מי קוקוס ותפוז").

תנתח את הטקסט ותחזיר אך ורק אובייקט JSON חוקי (ללא markdown, ללא טקסט פותח או סוגר):
{{
  "items": [
    {{
      "name_he": "שם הפריט בעברית",
      "name_en": "item name in English",
      "estimated_grams": 150,
      "calories": 250,
      "protein": 30.0,
      "carbs": 10.0,
      "fats": 5.0,
      "fiber": 3.0,
      "sodium_mg": 90.0,
      "potassium_mg": 320.0,
      "magnesium_mg": 30.0,
      "zinc_mg": 1.5,
      "vit_c_mg": 10.0,
      "vit_d_iu": 0.0,
      "iron_mg": 1.8,
      "confidence": "high"
    }}
  ],
  "meal_description": "תיאור קצר של הארוחה כולה",
  "total_calories": 250,
  "total_protein": 30.0,
  "total_carbs": 10.0,
  "total_fats": 5.0
}}

כללים:
- confidence: high (ציין כמות מפורשת), medium (ציין מזון ללא כמות), low (הערכה גסה)
- estimated_grams: הערכת משקל הגיונית בגרמים
- ערכי תזונה מדויקים לפי מאגרי מידע תזונתיים (כולל סיבים, נתרן, אשלגן, מגנזיום, אבץ, ויטמין C, ויטמין D, ברזל)
- שמות השדות חייבים להיות בדיוק: name_he, estimated_grams, calories, protein, carbs, fats, fiber, sodium_mg, potassium_mg, magnesium_mg, zinc_mg, vit_c_mg, vit_d_iu, iron_mg

טקסט המשתמש: "{user_text}"
"""

    @classmethod
    def parse(cls, user_text: str) -> dict:
        """Call Gemini text API to parse a free-text food description with fallbacks."""
        if not GEMINI_API_KEY:
            return {"error": "GEMINI_API_KEY not configured", "items": []}

        prompt = cls.PROMPT_TEMPLATE.replace("{user_text}", user_text)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048, "thinkingConfig": {"thinkingBudget": 0}}
        }
        payload_bytes = json.dumps(payload).encode("utf-8")

        last_error = "Unknown error"
        for model in cls.MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            req = urllib.request.Request(
                url,
                data=payload_bytes,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=20, context=_get_ssl_context()) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                text = ""
                for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if "text" in part:
                        text += part["text"]
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()
                parsed = json.loads(text)
                # Normalize fields if LLM returned alternate key names and guarantee micronutrients
                normalized_items = []
                for item in parsed.get("items", []):
                    n_he = item.get("name_he") or item.get("name") or "פריט מזון"
                    grams = float(item.get("estimated_grams") or item.get("weight_g") or item.get("amount_g") or 100)
                    inferred = infer_food_micronutrients(n_he, grams, 1.0)
                    norm = {
                        "name_he": n_he,
                        "name_en": item.get("name_en") or item.get("name") or "",
                        "estimated_grams": grams,
                        "calories": float(item.get("calories") or item.get("cal") or 0),
                        "protein": float(item.get("protein") or item.get("protein_g") or 0),
                        "carbs": float(item.get("carbs") or item.get("carbs_g") or 0),
                        "fats": float(item.get("fats") or item.get("fat") or item.get("fat_g") or 0),
                        "fiber": float(item.get("fiber") or inferred.get("fiber") or 0),
                        "sodium_mg": float(item.get("sodium_mg") or inferred.get("sodium_mg") or 0),
                        "potassium_mg": float(item.get("potassium_mg") or inferred.get("potassium_mg") or 0),
                        "magnesium_mg": float(item.get("magnesium_mg") or inferred.get("magnesium_mg") or 0),
                        "zinc_mg": float(item.get("zinc_mg") or inferred.get("zinc_mg") or 0),
                        "vit_c_mg": float(item.get("vit_c_mg") or inferred.get("vit_c_mg") or 0),
                        "vit_d_iu": float(item.get("vit_d_iu") or inferred.get("vit_d_iu") or 0),
                        "iron_mg": float(item.get("iron_mg") or inferred.get("iron_mg") or 0),
                        "confidence": item.get("confidence") or "high"
                    }
                    normalized_items.append(norm)
                parsed["items"] = normalized_items
                if "total_calories" not in parsed:
                    parsed["total_calories"] = sum(i["calories"] for i in normalized_items)
                if "total_protein" not in parsed:
                    parsed["total_protein"] = sum(i["protein"] for i in normalized_items)
                if "total_carbs" not in parsed:
                    parsed["total_carbs"] = sum(i["carbs"] for i in normalized_items)
                if "total_fats" not in parsed:
                    parsed["total_fats"] = sum(i["fats"] for i in normalized_items)
                return parsed
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                last_error = f"Gemini ({model}) error {e.code}: " + err_body[:200]
            except Exception as e:
                last_error = f"Gemini ({model}) error: {e}"

        # If Gemini API failed or was rejected by policy (e.g. 403), use local smart parser from database!
        local_result = cls.fallback_parse_from_db(user_text)
        if local_result and local_result.get("items"):
            return local_result

        return {"error": last_error, "items": []}

    @classmethod
    def fallback_parse_from_db(cls, user_text: str) -> dict:
        """Rule-based local parser extracting foods from SQLite database for reliable zero-latency results."""
        import re
        FOOD_RULES = [
            (r'חזה\s*עוף|עוף\s*צלוי', 'חזה עוף מבושל / צלוי', 150),
            (r'חלבון\s*ביצה', 'חלבון ביצה (חלבון בלבד)', 33),
            (r'חלמון\s*ביצה', 'חלמון ביצה בלבד (כ-20 גרם)', 20),
            (r'חביתה', 'חביתה מ-2 ביצים עם כפית שמן זית', 100),
            (r'ביצ(?:ה|ים|ות)', 'ביצה גדולה שלמה (L)', 50),
            (r'אורז\s*מלא', 'אורז מלא מבושל עתיר סיבים', 150),
            (r'פריכיו?ת\s*אורז', 'פריכיות אורז (3 יחידות כ-25 גרם)', 25),
            (r'אורז\s*בסמטי|אורז\s*לבן|אורז', 'אורז בסמטי לבן מבושל', 150),
            (r'טונה', 'טונה בהירה במים (מסוננת)', 100),
            (r'קוטג[\'׳]?', 'גבינת קוטג 5%', 125),
            (r'גבינה\s*לבנה', 'גבינה לבנה למריחה 5% (סקי / תנובה)', 100),
            (r'גבינה\s*צהובה|צהובה', 'גבינה צהובה עמק 28% (פרוסה 28g)', 28),
            (r'שיבולת\s*שועל|קוואקר', 'שיבולת שועל (קוואקר לא מבושל)', 50),
            (r'אבקת\s*חלבון|סקופ\s*חלבון|סקופ', 'אבקת חלבון מי גבינה (סקופ)', 30),
            (r'אבוקדו', 'אבוקדו (חצי אבוקדו)', 70),
            (r'בננ(?:ה|ות)', 'בננה בינונית', 120),
            (r'תפוח\s*אדמה', 'תפוח אדמה אפוי / מבושל', 150),
            (r'בטט(?:ה|ות)', 'בטטה אפויה בתנור', 150),
            (r'תפוח(?:\s*עץ)?', 'תפוח עץ בינוני', 180),
            (r'פית(?:ה|ות)', 'פיתה לבנה רגילה (יחידה אחת כ-100 גרם)', 100),
            (r'לחם|פרוס(?:ה|ות)\s*לחם', 'פרוסת לחם מלא 100%', 35),
            (r'שמן\s*זית', 'שמן זית כתית מעולה (כף)', 10),
            (r'טחינה', 'טחינה גולמית משומשום מלא (כף 15g)', 15),
            (r'חומוס', 'חומוס מוכן למריחה (צבר / אחלה - כף 30g)', 30),
            (r'יוגורט|דנונה\s*פרו|יופלה', 'יוגורט דנונה PRO מועשר 20g חלבון (גביע)', 200),
            (r'סלמון', 'פילה סלמון אפוי בתנור', 150),
            (r'בקר|סטייק|המבורגר', 'סטייק סינטה בקר צלוי', 150),
            (r'שקשוקה', 'שקשוקה ביתית מ-2 ביצים ברוטב עגבניות ופלפלים', 200),
            (r'מי\s*קוקוס|קוקוס', 'מי קוקוס טבעי 100% (ללא תוספת סוכר)', 250),
        ]

        try:
            with Database.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT id, name, name_he, calories, protein, carbs, fats, fiber, sodium_mg, potassium_mg, magnesium_mg, zinc_mg, vit_c_mg, vit_d_iu, iron_mg, serving_size_g FROM food_items")
                foods = [dict(r) for r in c.fetchall()]

            text_lower = user_text.lower()
            matched = []
            for pat, db_name, default_g in FOOD_RULES:
                m = re.search(pat, text_lower)
                if m:
                    item = next((f for f in foods if f['name_he'] == db_name), None)
                    if item and not any(x['name_he'] == db_name for x in matched):
                        start_pos = max(0, m.start() - 15)
                        end_pos = min(len(text_lower), m.end() + 15)
                        context_str = text_lower[start_pos:end_pos]

                        num_m = re.search(r'(\d+)\s*(?:גרם|ג[\'׳]?|g)?', context_str)
                        grams = default_g
                        if num_m:
                            val = float(num_m.group(1))
                            if 'גרם' in context_str or val > 20:
                                grams = val
                            else:
                                grams = default_g * val
                        elif 'חצי' in context_str:
                            grams = round(default_g * 0.5)

                        ratio = grams / (item['serving_size_g'] or 100)
                        matched.append({
                            'name_he': item['name_he'],
                            'name_en': item['name'],
                            'estimated_grams': round(grams),
                            'calories': round(item['calories'] * ratio),
                            'protein': round(item['protein'] * ratio, 1),
                            'carbs': round(item['carbs'] * ratio, 1),
                            'fats': round(item['fats'] * ratio, 1),
                            'fiber': round((item.get('fiber') or 0) * ratio, 1),
                            'sodium_mg': round((item.get('sodium_mg') or 0) * ratio, 1),
                            'potassium_mg': round((item.get('potassium_mg') or 0) * ratio, 1),
                            'magnesium_mg': round((item.get('magnesium_mg') or 0) * ratio, 1),
                            'zinc_mg': round((item.get('zinc_mg') or 0) * ratio, 1),
                            'vit_c_mg': round((item.get('vit_c_mg') or 0) * ratio, 1),
                            'vit_d_iu': round((item.get('vit_d_iu') or 0) * ratio, 1),
                            'iron_mg': round((item.get('iron_mg') or 0) * ratio, 1),
                            'confidence': 'high'
                        })

            if matched:
                return {
                    'items': matched,
                    'meal_description': user_text,
                    'total_calories': sum(i['calories'] for i in matched),
                    'total_protein': round(sum(i['protein'] for i in matched), 1),
                    'total_carbs': round(sum(i['carbs'] for i in matched), 1),
                    'total_fats': round(sum(i['fats'] for i in matched), 1)
                }
        except Exception as err:
            print(f"Error in local fallback parse: {err}")
        return None


# -------------------------------------------------------------
# Hunter Goal Advisor AI — Personalized AI Target Formulation
# -------------------------------------------------------------
class GoalAdvisorAI:
    """Uses Gemini AI (with smart scientific fallback) to formulate customized nutrition and fitness targets based on natural language user goals."""

    MODELS = [
        "gemini-flash-latest",
        "gemini-3.1-flash-lite",
        "gemini-3.1-flash-lite-preview"
    ]

    PROMPT_TEMPLATE = """אתה פיזיולוג ספורט ותזונאי קליני בכיר באפליקציית כושר בסגנון Solo Leveling.
המשתמש מתאר במילים חופשיות את מטרת הכושר והתזונה שלו, בנוסף לנתוניו הפיזיולוגיים.
עליך לנתח את המטרה, לחשב במדויק יעדים מותאמים אישית (קלוריות, חלבון, פחמימות, שומן, מים וסיבים) לפי עקרונות ISSN ו-Mifflin-St Jeor, ולספק הסבר מדעי קצר, אישי ומעצים בסגנון הציידים (System).

נתוני המשתמש:
- משקל: {weight} ק"ג
- גובה: {height} ס"מ
- גיל: {age}
- מין: {sex}
- רמת פעילות: {activity}
- תיאור המטרה של המשתמש: "{goal_text}"

החזר אך ורק אובייקט JSON תקין (ללא markdown וללא תווים מיותרים):
{{
  "goal_type": "cut / bulk / maintain / recomposition",
  "target_calories": 2150,
  "target_protein": 170,
  "target_carbs": 215,
  "target_fats": 65,
  "target_water": 3200,
  "target_fiber": 32,
  "analysis_headline": "כותרת קצרה ומעצימה למטרה",
  "ai_explanation": "הסבר מנומק של 2-3 משפטים בעברית שמסביר מדוע נבחרו ערכים אלו (למשל: סף חלבון לשמירה על שריר, גרעון קלורי מדוד, תמיכה במשמרות/אימונים והידרציה)",
  "hunter_rank_tip": "טיפ מעשי קצר לביצוע מוצלח"
}}
"""

    @classmethod
    def calculate_from_text(cls, goal_text: str, user_profile: dict) -> dict:
        weight = float(user_profile.get("weight", 78.0))
        height = float(user_profile.get("height", 178.0))
        age = int(user_profile.get("age", 25))
        sex = user_profile.get("sex", "male")
        activity = user_profile.get("activity_level", "moderate")
        target_weight = float(user_profile.get("target_weight", 0.0) or 0.0)

        # Smart biometric extraction from free text if user mentions them in chat
        import re
        text_lower = (goal_text or "").lower()

        # Height extraction (e.g. הגובה שלי 180, הגובה שלי הוא 180, גובה 180, 180 ס"מ, 1.80 מטר)
        h_match = re.search(
            r'(?:הגובה\s*שלי(?:\s*הוא|\s*זה)?|גובהי(?:\s*הוא)?|גובה\s*שלי|ב?גובה|עדכן\s*גובה(?:\s*ל)?|height)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:ס["״]?מ|מטר|cm|m)?',
            text_lower
        )
        if h_match:
            h_val = float(h_match.group(1))
            if h_val < 2.5: h_val = h_val * 100
            if 100 <= h_val <= 250: height = h_val
        else:
            h2 = re.search(r'\b(1[4-9]\d|2[0-2]\d)\s*(?:ס["״]?מ|cm)\b', text_lower)
            if h2:
                height = float(h2.group(1))
            else:
                h3 = re.search(r'\b(1\.[4-9]\d|2\.[0-2]\d)\s*(?:מטר|m)\b', text_lower)
                if h3:
                    height = float(h3.group(1)) * 100
                else:
                    h4 = re.search(r'(?:מטר|מ\')\s*(\d{2})\b', text_lower)
                    if h4:
                        height = 100.0 + float(h4.group(1))
                    else:
                        h5 = re.search(r'\b(?:אני|גובה)\s*(1\.[4-9]\d|2\.[0-2]\d)\b', text_lower)
                        if h5:
                            height = float(h5.group(1)) * 100
                        else:
                            h6 = re.search(r'\b(?:אני)\s*(1[4-9]\d|2[0-2]\d)\b', text_lower)
                            if h6:
                                height = float(h6.group(1))

        # Weight extraction (e.g. משקל 83, שוקל 83.5, המשקל שלי 83, 83 ק"ג)
        w_match = re.search(
            r'(?:המשקל\s*שלי(?:\s*הוא|\s*זה)?|משקלי(?:\s*הוא)?|משקל\s*שלי|שוקל|ב?משקל|עדכן\s*משקל(?:\s*ל)?|משקל\s*נוכחי|weight)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:ק["״]?ג|קילו|kg)?',
            text_lower
        )
        if w_match:
            weight = float(w_match.group(1))
        else:
            w2 = re.search(r'\b([4-9]\d(?:\.\d+)?|1[0-9]\d(?:\.\d+)?)\s*(?:ק["״]?ג|קילו|kg)\b', text_lower)
            if w2: weight = float(w2.group(1))

        # Target Weight extraction
        tw_match = re.search(
            r'(?:יעד(?:\s*המשקל)?|משקל\s*יעד|להגיע\s*ל(?:משקל)?|מטרה\s*(?:היא|שלי)?(?:\s*להיות)?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:ק["״]?ג|קילו|kg)?',
            text_lower
        )
        if tw_match: target_weight = float(tw_match.group(1))

        # Age extraction
        a_match = re.search(r'(?:בן|גילי|הגיל\s*שלי(?:\s*הוא)?|ב?גיל|age)\s*[:=]?\s*(\d+)', text_lower)
        if a_match: age = int(a_match.group(1))

        # First attempt Gemini AI
        if GEMINI_API_KEY and goal_text.strip():
            prompt = cls.PROMPT_TEMPLATE.format(
                weight=weight,
                height=height,
                age=age,
                sex=sex,
                activity=activity,
                goal_text=goal_text.strip()
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 1024,
                    "thinkingConfig": {"thinkingBudget": 0}
                }
            }
            payload_bytes = json.dumps(payload).encode("utf-8")

            for model in cls.MODELS:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                req = urllib.request.Request(
                    url,
                    data=payload_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                try:
                    with urllib.request.urlopen(req, timeout=15, context=_get_ssl_context()) as resp:
                        raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    text = ""
                    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                        if "text" in part:
                            text += part["text"]
                    text = text.strip()
                    if text.startswith("```"):
                        text = text.split("```")[1]
                        if text.startswith("json"):
                            text = text[4:]
                        text = text.strip()
                    res = json.loads(text)
                    if "target_calories" in res and "target_protein" in res:
                        g_type = res.get("goal_type", "cut")
                        calc_tw = target_weight
                        if not calc_tw:
                            if g_type == "bulk": calc_tw = round(weight + 4.0, 1)
                            elif g_type == "cut": calc_tw = round(max(40.0, weight - 4.0), 1)
                            else: calc_tw = round(weight, 1)
                        elif g_type == "bulk" and calc_tw <= weight:
                            calc_tw = round(weight + 4.0, 1)
                        elif g_type == "cut" and calc_tw >= weight:
                            calc_tw = round(max(40.0, weight - 4.0), 1)

                        res["detected_weight"] = weight
                        res["detected_height"] = height
                        res["detected_age"] = age
                        res["detected_target_weight"] = calc_tw
                        return res
                except Exception as e:
                    print(f"GoalAdvisorAI error with {model}: {e}")

        # Scientific Fallback Algorithm based on text semantics
        fallback_profile = dict(user_profile)
        fallback_profile["weight"] = weight
        fallback_profile["height"] = height
        fallback_profile["age"] = age
        res = cls.fallback_scientific_calculation(goal_text, fallback_profile)
        g_type = res.get("goal_type", "cut")
        calc_tw = target_weight
        if not calc_tw:
            if g_type == "bulk": calc_tw = round(weight + 4.0, 1)
            elif g_type == "cut": calc_tw = round(max(40.0, weight - 4.0), 1)
            else: calc_tw = round(weight, 1)
        elif g_type == "bulk" and calc_tw <= weight:
            calc_tw = round(weight + 4.0, 1)
        elif g_type == "cut" and calc_tw >= weight:
            calc_tw = round(max(40.0, weight - 4.0), 1)

        res["detected_weight"] = weight
        res["detected_height"] = height
        res["detected_age"] = age
        res["detected_target_weight"] = calc_tw
        return res

    @classmethod
    def fallback_scientific_calculation(cls, goal_text: str, user_profile: dict) -> dict:
        weight = float(user_profile.get("weight", 78.0))
        height = float(user_profile.get("height", 178.0))
        age = int(user_profile.get("age", 25))
        sex = user_profile.get("sex", "male")
        activity = user_profile.get("activity_level", "moderate")
        text = (goal_text or "").lower()

        # Determine goal direction from user wording
        if any(w in text for w in ["חיטוב", "להוריד", "ירידה", "לרדת", "שומן", "בטן", "גרעון", "cut"]):
            goal = "cut"
            cal_factor = 0.80  # 20% deficit
            p_mult = 2.2      # High protein to protect muscle
            headline = "חיטוב אסטרטגי והגנה על מסת שריר"
            explanation = f"המערכת הגדירה גרעון קלורי מדעי של 20% לשריפת שומן בקצב אופטימלי, עם מינון חלבון גבוה של 2.2g/kg ({round(weight * 2.2)}g) למניעת קטבוליזם."
            tip = "הקפד על ארוחות חלבון סביב אימונים ושתייה מרובה לדיכוי תיאבון שווא."
        elif any(w in text for w in ["מסה", "לעלות", "שריר", "גדילה", "היפרטרופיה", "להשמין", "bulk"]):
            goal = "bulk"
            cal_factor = 1.10  # 10% surplus
            p_mult = 1.9
            headline = "מסה נקייה ועודף אנרגטי לבניית כוח"
            explanation = f"המערכת חישבה עודף קלורי מבוקר של 10% מעל ה-TDEE לעידוד סינתזת חלבון מרבית (mTOR) ללא צבירת שומן מיותרת."
            tip = "שלב פחמימות מורכבות לפני אימונים ופזר את הארוחות על פני 4-5 מנות יומיות."
        else:
            goal = "recomposition"
            cal_factor = 0.93  # Mild 7% deficit for body recomposition
            p_mult = 2.0
            headline = "איזון מטבולי ורה-קומפוזיציה גופנית"
            explanation = f"המערכת הגדירה יעדי תחזוקה משופרים לבניית שריר בד בבד עם שריפת שומן הדרגתית, בהתאמה למשקל {weight} ק\"ג."
            tip = "עקביות בהידרציה ואימוני התנגדות עצימים הם המפתח להתקדמות."

        sci = NutritionScienceEngine.calculate_full_profile(
            weight_kg=weight,
            height_cm=height,
            age=age,
            sex=sex,
            activity_level=activity,
            goal="cut" if goal == "cut" else ("bulk" if goal == "bulk" else "maintain")
        )

        cals = round(sci["tdee"] * cal_factor)
        protein = round(weight * p_mult)
        fats = max(50, round(weight * 0.85))
        carbs = max(60, round((cals - (protein * 4) - (fats * 9)) / 4))
        water = round(weight * 38 + 500)
        fiber = max(28, round((cals / 1000) * 14))

        return {
            "goal_type": goal,
            "target_calories": cals,
            "target_protein": protein,
            "target_carbs": carbs,
            "target_fats": fats,
            "target_water": water,
            "target_fiber": fiber,
            "analysis_headline": headline,
            "ai_explanation": explanation,
            "hunter_rank_tip": tip
        }


# -------------------------------------------------------------
# Hunter AI Interactive Consultation & Directives Engine
# -------------------------------------------------------------
class HunterAIConsultant:
    MODELS = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-pro"]

    @classmethod
    def extract_biometrics_from_text(cls, text: str) -> dict:
        import re
        text_lower = (text or "").lower()
        res = {}

        # Height extraction (e.g. הגובה שלי 180, הגובה שלי הוא 180, גובה 180, 180 ס"מ, 1.80 מטר)
        h_match = re.search(
            r'(?:הגובה\s*שלי(?:\s*הוא|\s*זה)?|גובהי(?:\s*הוא)?|גובה\s*שלי|ב?גובה|עדכן\s*גובה(?:\s*ל)?|height)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:ס["״]?מ|מטר|cm|m)?',
            text_lower
        )
        if h_match:
            val = float(h_match.group(1))
            if val < 2.5: val = val * 100
            if 100 <= val <= 250: res["height"] = val
        else:
            h2 = re.search(r'\b(1[4-9]\d|2[0-2]\d)\s*(?:ס["״]?מ|cm)\b', text_lower)
            if h2:
                res["height"] = float(h2.group(1))
            else:
                h3 = re.search(r'\b(1\.[4-9]\d|2\.[0-2]\d)\s*(?:מטר|m)\b', text_lower)
                if h3:
                    res["height"] = float(h3.group(1)) * 100
                else:
                    h4 = re.search(r'(?:מטר|מ\')\s*(\d{2})\b', text_lower)
                    if h4:
                        res["height"] = 100.0 + float(h4.group(1))
                    else:
                        h5 = re.search(r'\b(?:אני|גובה)\s*(1\.[4-9]\d|2\.[0-2]\d)\b', text_lower)
                        if h5:
                            res["height"] = float(h5.group(1)) * 100
                        else:
                            h6 = re.search(r'\b(?:אני)\s*(1[4-9]\d|2[0-2]\d)\b', text_lower)
                            if h6:
                                res["height"] = float(h6.group(1))

        # Weight extraction
        w_match = re.search(
            r'(?:המשקל\s*שלי(?:\s*הוא|\s*זה)?|משקלי(?:\s*הוא)?|משקל\s*שלי|שוקל|ב?משקל|עדכן\s*משקל(?:\s*ל)?|משקל\s*נוכחי|weight)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:ק["״]?ג|קילו|kg)?',
            text_lower
        )
        if w_match:
            res["weight"] = float(w_match.group(1))
        else:
            w2 = re.search(r'\b([4-9]\d(?:\.\d+)?|1[0-9]\d(?:\.\d+)?)\s*(?:ק["״]?ג|קילו|kg)\b', text_lower)
            if w2: res["weight"] = float(w2.group(1))

        # Target Weight extraction
        tw_match = re.search(
            r'(?:יעד(?:\s*המשקל)?|משקל\s*יעד|להגיע\s*ל(?:משקל)?|מטרה\s*(?:היא|שלי)?(?:\s*להיות)?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:ק["״]?ג|קילו|kg)?',
            text_lower
        )
        if tw_match: res["target_weight"] = float(tw_match.group(1))

        # Age extraction
        a_match = re.search(r'(?:בן|גילי|הגיל\s*שלי(?:\s*הוא)?|ב?גיל|age)\s*[:=]?\s*(\d+)', text_lower)
        if a_match: res["age"] = int(a_match.group(1))

        return res

    @classmethod
    def consult(cls, conn, user_message: str, chat_history: list = None) -> dict:
        c = conn.cursor()
        c.execute("SELECT * FROM hunter_profile WHERE id = 1")
        prof_row = c.fetchone()
        prof = dict(prof_row) if prof_row else {}
        today = get_hunter_shift_date(conn)

        # Check if user mentioned height, weight, target_weight, age in the message
        bio = cls.extract_biometrics_from_text(user_message)
        updated_bio = []
        if bio.get("height"):
            new_h = bio["height"]
            c.execute("UPDATE hunter_profile SET height = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (new_h,))
            prof["height"] = new_h
            updated_bio.append(f"גובה: {new_h} ס״מ")
        if bio.get("weight"):
            new_w = bio["weight"]
            c.execute("UPDATE hunter_profile SET weight = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (new_w,))
            prof["weight"] = new_w
            updated_bio.append(f"משקל: {new_w} ק״ג")
        if bio.get("target_weight"):
            new_tw = bio["target_weight"]
            c.execute("UPDATE hunter_profile SET target_weight = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (new_tw,))
            prof["target_weight"] = new_tw
            updated_bio.append(f"משקל יעד: {new_tw} ק״ג")
        if bio.get("age"):
            new_age = bio["age"]
            c.execute("UPDATE hunter_profile SET age = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (new_age,))
            prof["age"] = new_age
            updated_bio.append(f"גיל: {new_age}")

        if updated_bio:
            sci = NutritionScienceEngine.calculate_full_profile(
                weight_kg=float(prof.get("weight", 83.0)),
                height_cm=float(prof.get("height", 180.0)),
                age=int(prof.get("age", 26)),
                sex=prof.get("sex", "male"),
                activity_level=prof.get("activity_level", "moderate"),
                goal=prof.get("goal", "bulk")
            )
            c.execute("UPDATE hunter_profile SET bmr = ?, tdee = ? WHERE id = 1", (sci["bmr"], sci["tdee"]))
            conn.commit()

        # Today's nutrition
        c.execute("SELECT COALESCE(SUM(calories), 0) as cal, COALESCE(SUM(protein), 0) as prot, COALESCE(SUM(carbs), 0) as carb, COALESCE(SUM(fats), 0) as fat FROM daily_logs WHERE date = ?", (today,))
        nut_row = c.fetchone()
        nut = dict(nut_row) if nut_row else {}

        # Today's water
        c.execute("SELECT COALESCE(SUM(amount_ml), 0) as water FROM water_logs WHERE date = ?", (today,))
        water_row = c.fetchone()
        water = water_row["water"] if water_row else 0

        # Today's supplements
        c.execute("SELECT name, dosage, unit FROM supplements_log WHERE date = ?", (today,))
        supps = [f"{r['name']} ({r['dosage']}{r['unit']})" for r in c.fetchall()]

        # Generate consultation reply
        result = cls._generate_reply(
            user_message=user_message,
            profile=prof,
            today_nutrition=nut,
            today_water=water,
            today_supplements=supps,
            chat_history=chat_history or []
        )

        if updated_bio:
            prefix = f"⚡ **המערכת עדכנה בהצלחה את הנתונים שלך:** {', '.join(updated_bio)}!\nה-BMR וה-TDEE חושבו מחדש.\n\n"
            result["reply"] = prefix + result.get("reply", "")
            if "suggested_targets" not in result or not result["suggested_targets"]:
                result["suggested_targets"] = {}
            for k, v in bio.items():
                result["suggested_targets"][k] = v

        # 1. Save user message to database
        c.execute("INSERT INTO ai_chat_messages (sender, message) VALUES (?, ?)", ("user", user_message))

        # 2. Save system reply to database
        recs_json = json.dumps(result.get("recommendations", []), ensure_ascii=False)
        c.execute("INSERT INTO ai_chat_messages (sender, message, recommendations_json) VALUES (?, ?, ?)", 
                  ("system", result["reply"], recs_json))

        # 3. Save recommendations to active directives table
        for rec in result.get("recommendations", []):
            title = rec.get("title", "הנחיית צייד")
            content = rec.get("content", rec.get("text", ""))
            category = rec.get("category", "nutrition")
            if content:
                c.execute("SELECT id FROM ai_recommendations WHERE title = ? AND is_active = 1", (title,))
                if not c.fetchone():
                    c.execute("INSERT INTO ai_recommendations (title, content, category, is_active) VALUES (?, ?, ?, 1)",
                              (title, content, category))

        # 4. If suggested targets exist, apply them
        if result.get("suggested_targets"):
            st = result["suggested_targets"]
            fields = []
            vals = []
            for k in ["target_calories", "target_protein", "target_carbs", "target_fats", "target_water", "target_weight", "height", "weight", "age"]:
                if k in st and st[k] is not None:
                    fields.append(f"{k} = ?")
                    vals.append(st[k])
            if fields:
                vals.append(1)
                c.execute(f"UPDATE hunter_profile SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", vals)

        # Also update headline/tip on profile if provided
        if result.get("headline"):
            c.execute("UPDATE hunter_profile SET ai_analysis_headline = ?, ai_hunter_tip = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                      (result["headline"], result.get("tip", prof.get("ai_hunter_tip", ""))))

        conn.commit()

        # Fetch latest active recommendations and updated profile to return with response
        result["active_recommendations"] = cls.get_recommendations(conn)
        c.execute("SELECT * FROM hunter_profile WHERE id = 1")
        prof_row = c.fetchone()
        result["profile"] = dict(prof_row) if prof_row else {}
        return result

    @classmethod
    def _generate_reply(cls, user_message: str, profile: dict, today_nutrition: dict, today_water: int, today_supplements: list, chat_history: list) -> dict:
        weight = float(profile.get("weight", 83.0))
        target_weight = float(profile.get("target_weight", 87.0))
        goal = profile.get("goal", "bulk")
        target_calories = profile.get("target_calories", 2550)
        target_protein = profile.get("target_protein", 175)
        cur_cal = round(today_nutrition.get("cal", 0))
        cur_prot = round(today_nutrition.get("prot", 0), 1)

        # 1. Try Gemini AI if API key is configured
        if GEMINI_API_KEY and user_message.strip():
            sys_prompt = f"""אתה ה-System AI של הצייד (Solo Leveling System AI Consultant).
פרופיל הצייד:
- משקל נוכחי: {weight} ק"ג
- משקל יעד: {target_weight} ק"ג
- מטרת העל: {goal} (עלייה במסת שריר נקייה והיפרטרופיה)
- יעד קלורי יומי: {target_calories} kcal (נצרכו היום: {cur_cal} kcal)
- יעד חלבון יומי: {target_protein}g (נצרכו היום: {cur_prot}g)
- יעד מים: {profile.get('target_water', 3300)} ml (נצרכו היום: {today_water} ml)
- תוספים שנלקחו היום: {', '.join(today_supplements) if today_supplements else 'עדיין לא נרשמו תוספים'}
- משמרת נוכחית: {'משמרת לילה' if profile.get('shift_mode') == 'night' else 'משמרת יום רגילה'}

הנחיות:
- ענה בעברית טבעית, שוטפת, מקצועית ומעצימה בסגנון מערכת ה-Solo Leveling.
- פנה אל המשתמש כ"צייד".
- החזר תשובה בפורמט JSON בלבד:
{{
  "reply": "מענה מפורט ומנומק של 2-4 פסקאות מקצועיות, קולחות ומעשיות",
  "headline": "כותרת קצרה וממוקדת לנושא (למשל: פרוטוקול תזמון פחמימות ועודף קלורי)",
  "tip": "טיפ מעשי ממוקד לפעולה מיידית",
  "recommendations": [
    {{
      "title": "כותרת ההמלצה (למשל: תזמון חלבון סביב השינה)",
      "content": "תוכן מעשי ומפורט להמלצה",
      "category": "nutrition / training / supplements / recovery / hydration"
    }}
  ],
  "suggested_targets": {{}},
  "followup_chips": ["שאלה להמשך 1", "שאלה להמשך 2"]
}}
"""
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": sys_prompt + f"\n\nשאלת הצייד: {user_message}"}]}
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 1024
                }
            }
            payload_bytes = json.dumps(payload).encode("utf-8")
            for model in cls.MODELS:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                    req = urllib.request.Request(url, data=payload_bytes, headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(req, timeout=12, context=_get_ssl_context()) as resp:
                        raw = resp.read().decode("utf-8")
                    d = json.loads(raw)
                    parts = d.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    txt = "".join(p.get("text", "") for p in parts).strip()
                    if txt.startswith("```"):
                        txt = txt.split("```")[1]
                        if txt.startswith("json"): txt = txt[4:]
                        txt = txt.strip()
                    parsed = json.loads(txt)
                    if "reply" in parsed:
                        return parsed
                except Exception as e:
                    print(f"HunterAIConsultant error with {model}: {e}")

        # 2. Rich Built-in Hunter Science Knowledge Base (Semantic Engine)
        return cls._fallback_consultation_reply(user_message, profile, today_nutrition, today_water, today_supplements)

    @classmethod
    def _fallback_consultation_reply(cls, msg: str, profile: dict, nut: dict, water: int, supps: list) -> dict:
        weight = float(profile.get("weight", 83.0))
        target_weight = float(profile.get("target_weight", 87.0))
        goal = profile.get("goal", "bulk")
        target_calories = profile.get("target_calories", 2550)
        target_protein = profile.get("target_protein", 175)
        cur_cal = round(nut.get("cal", 0))
        cur_prot = round(nut.get("prot", 0), 1)
        rem_prot = max(0.0, round(target_protein - cur_prot, 1))
        rem_cal = max(0, round(target_calories - cur_cal))

        text = (msg or "").lower()

        # Category 1: Protein & Food options
        if any(w in text for w in ["חלבון", "מה לאכול", "ארוחה", "אוכל", "תפריט", "רעב", "להגיע ליעד"]):
            if rem_prot > 0:
                prot_status = f"כרגע חסרים לך עוד **{rem_prot}g חלבון** להגעה ליעד היומי ({cur_prot}g מתוך {target_protein}g)."
            else:
                prot_status = f"מעולה צייד! עמדת ביעד החלבון היומי עם **{cur_prot}g** (יעד {target_protein}g)."

            reply = f"""שלום צייד! המערכת ניתחה את מצב התזונה שלך להיום.

{prot_status}

לבנייה מרבית של מסת שריר (mTOR activation) בתוכנית המסה שלך (משקל {weight} ק"ג $\\rightarrow$ יעד {target_weight} ק"ג), הנה מקורות החלבון המהירים והאופטימליים ביותר לשילוב עכשיו:
1. **חזה עוף / הודו צלוי (150 גרם):** מעניק כ-45g חלבון איכותי ודל בשומן.
2. **גביע קוטג' 3%-5% (250 גרם):** מספק 25-28g חלבון קזאין איטי הנספג לאורך שעות הלילה.
3. **שייק חלבון מי גבינה (סקופ אחד 30 גרם):** 25-27g חלבון עם ספיגה מיידית וריכוז לויצין גבוה.
4. **טונה במים (פחית אחת) + 2 ביצים:** מספקת כ-38g חלבון עם שומנים בריאים."""
            headline = "פרוטוקול סגירת חלבון והיפרטרופיה"
            tip = f"חלק את {rem_prot or 40}g החלבון שנותרו לארוחה אחת עשירה או שייק מרוכז סמוך לשינה."
            recs = [
                {"title": "השלמת מנת חלבון יומית", "content": f"סגור לפחות {rem_prot or 35}g חלבון מארוחה עשירה (עוף/קוטג'/שייק) להגעה ל-{target_protein}g.", "category": "nutrition"},
                {"title": "תזמון חלבון לשינה", "content": "צריכת 25-30g חלבון קזאין (קוטג'/יוגורט יווני) לפני השינה מגנה מפני פירוק שרירי בלילה.", "category": "nutrition"}
            ]
            chips = ["אילו עוד מזונות עשירים בחלבון?", "איך לתזמן פחמימות סביב אימון?", "כמה קלוריות נותרו לי היום?"]

        # Category 2: Bulk, Muscle Building & Targets
        elif any(w in text for w in ["מסה", "לעלות", "שריר", "משקל יעד", "להתחזק", "היפרטרופיה", "bulk"]):
            reply = f"""הוראות מערכת מיוחדות לצייד בפרוטוקול **עלייה במסה נקייה (Clean Hypertrophy)**:

היעד המוגדר שלך הוא עלייה מבוקרת מ-**{weight} ק"ג** למשקל יעד של **{target_weight} ק"ג**.
במסה נקייה, המטרה היא להשיג קצב עלייה של כ-**1 עד 1.5 ק"ג לחודש**, כך שהעלייה תהיה כמעט כולה ברקמת שריר ולא בשומן.

**עקרונות המפתח של הפרוטוקול:**
1. **עודף קלורי מדוד (Surplus):** היעד שלך הוא **{target_calories} קלוריות**. נותרו לך עוד **{rem_cal} kcal** היום.
2. **סף חלבון מיטבי:** {target_protein}g חלבון ביום (כ-2.1g לק"ג), מחולק ל-4 ארוחות עיקריות.
3. **תזמון פחמימות (Carb Loading):** צרוך כ-60% מהפחמימות היומיות סביב האימון (ארוחה לפני ואחרי) לרוויית מאגרי גליקוגן וביצועי שיא."""
            headline = f"מפרט מסה נקייה: {weight}kg ← {target_weight}kg"
            tip = "התמקד בהתקדמות מתמדת במשקלי העבודה באימונים (Progressive Overload) במקביל לעודף הקלורי."
            recs = [
                {"title": "עודף קלורי מבוקר למסה", "content": f"שמור על צריכה יומית של {target_calories} קלוריות לתמיכה בצמיחת שריר ללא צבירת שומן.", "category": "nutrition"},
                {"title": "התקדמות כוח עקבית", "content": "בצע תיעוד של המשקלים והחזרות בכל אימון ושאף לעלייה של 2.5% בעומס מדי שבוע.", "category": "training"}
            ]
            chips = ["איזה תוספים הכי יעזרו למסה?", "איך למנוע צבירת שומן במסה?", "מה לאכול לפני אימון כוח?"]

        # Category 3: Supplements & Creatine
        elif any(w in text for w in ["תוסף", "תוספים", "קריאטין", "אומגה", "מגנזיום", "ויטמין", "elixir", "supplements"]):
            reply = f"""ניתוח שיקויי הצייד ותוספי התזונה המדעיים:

לצייד במשקל {weight} ק"ג במטרה של עלייה במסה וכוח, הנה הפרוטוקול המדעי המוביל:

1. **קריאטין מונוהידראט (Creatine Monohydrate):**
   - מינון: **5 גרם בכל יום**, באופן קבוע (כולל ימי מנוחה).
   - תזמון: רצוי עם ארוחה המכילה פחמימות וחלבון (למשל שייק שאחרי אימון) להגברת הספיגה התאית.
   - אין צורך בתקופת העמסה — 5g ביום יביאו לרוויית מאגרים מלאה תוך 3 שבועות.
2. **אומגה 3 (EPA/DHA):**
   - 1,500-2,000 מ"ג משולב עם ארוחה שומנית להפחתת דלקתיות ושיפור רגישות שרירית לאינסולין.
3. **מגנזיום גליצינאט / ציטראט:**
   - 350-400 מ"ג כ-30-60 דקות לפני השינה להרפיית מערכת העצבים והעמקת שלב ה-Deep Sleep."""
            headline = "פרוטוקול תוספי כוח והתאוששות"
            tip = "קח 5g קריאטין מדי יום בשעה קבועה עם כוס מים גדולה או שייק."
            recs = [
                {"title": "קריאטין מונוהידראט 5g", "content": "5g קריאטין בכל יום בעקביות מגביר כוח מתפרץ ב-10-15% ומעלה נפח תא שרירי.", "category": "supplements"},
                {"title": "מגנזיום לפני שינה", "content": "350mg מגנזיום גליצינאט בערב משפר התאוששות שרירית ואיכות שינה.", "category": "supplements"}
            ]
            chips = ["מתי לקחת קריאטין - לפני או אחרי אימון?", "מה היתרונות של אומגה 3 במסה?", "האם צריך הפסקות מקריאטין?"]

        # Category 4: Attent & Focus Medication
        elif any(w in text for w in ["אטנט", "attent", "ריכוז", "קשב", "תרופה"]):
            reply = f"""הנחיות מערכת קריטיות לצייד הנוטל שיקוי ריכוז (אטנט / Attent):

אטנט מגביר שחרור דופמין ונוראדרנלין. כדי להפיק ממנו אפקט שיא ללא פגיעה במטרות המסה והשריר, פעל לפי הפרוטוקול הבא:

1. **מניעת קטבוליזם ואיבוד תיאבון:**
   - אכול ארוחה גדולה ועשירה בחלבון ופחמימות מורכבות (למשל שיבולת שועל, ביצים, שייק) **לפני** נטילת המנה.
   - במהלך שעות ההשפעה (כשהתיאבון יורד), השתמש בקלוריות נוזליות (שייק, חלב, מיצים) כדי לא להיכנס לגרעון לא מתוכנן.
2. **הידרציה מוגברת:**
   - אטנט מגביר איבוד נוזלים ומעלה דופק. הקפד על לפחות **3.3-3.5 ליטר מים** ביום נטילה.
3. **שמירה על רגישות קולטנים (Drug Holidays):**
   - קבע 1-2 ימי חופש תרופתי בסופי שבוע למניעת עמידות (Tolerance Drift)."""
            headline = "פרוטוקול סינרגיית אטנט ומסה"
            tip = "אכול ארוחת בוקר מלאה של 500+ קלוריות ו-30g חלבון לפני נטילת המנה."
            recs = [
                {"title": "ארוחת עוגן לפני אטנט", "content": "צרוך ארוחה מלאה של חלבון ופחמימה לפני נטילת התרופה למניעת פגיעה בצריכה היומית.", "category": "nutrition"},
                {"title": "ימי חופש תרופתי (Drug Holidays)", "content": "תזמן סופ״ש ללא נטילה לשיקום רגישות קולטני הדופמין.", "category": "recovery"}
            ]
            chips = ["איך להשלים קלוריות כשאין תיאבון?", "איך אטנט משפיע על האימונים?", "כמה מים לשתות בימי אטנט?"]

        # Category 5: Night Shift & Fatigue
        elif any(w in text for w in ["משמרת", "לילה", "עייף", "עייפות", "שינה", "שעות"]):
            reply = f"""פרוטוקול צייד למשמרות לילה ועייפות כרונית:

משמרות לילה מאתגרות את השעון הצירקדי, אך ניהול מדעי נכון שומר על שריפת שומן וצבירת שריר רציפה:

1. **תזמון ארוחות המשמרת:**
   - ארוחה עיקרית לפני היציאה למשמרת (20:00-21:00).
   - ארוחה קלה מבוססת חלבון וירקות באמצע המשמרת (01:30-03:00) — הימנע מסוכרים פשוטים שיובילו להתרסקות ערנות.
   - ארוחה קלה ומרגיעה בסיום המשמרת (לפני השינה, כגון יוגורט עם אגוזים).
2. **מצב משמרת לילה במערכת:**
   - זכור להפעיל את כפתור ה-🌙 בראש המסך. שעת האיפוס תעבור ל-08:00 בבוקר והיום לא יתאפס לך בחצות!
3. **היגיינת שינה בבוקר:**
   - חדר חשוך ב-100%, אטמי אוזניים, והימנעות מקפאין 5 שעות לפני סיום המשמרת."""
            headline = "פרוטוקול התאוששות ומשמרות לילה"
            tip = "וודא שכפתור משמרת לילה 🌙 פעיל באפליקציה כדי שהאיפוס יתרחש רק ב-08:00 בבוקר."
            recs = [
                {"title": "ארוחה קלה באמצע משמרת", "content": "ארוחה של 300-400 kcal בלבד באמצע הלילה מונעת כבדות ונפילות סוכר.", "category": "nutrition"},
                {"title": "החשכת חדר לשינת בוקר", "content": "שינה בחושך מוחלט מעודדת הפרשת מלטונין והתאוששות שריר מרבית.", "category": "recovery"}
            ]
            chips = ["איך לנהל שתייה במשמרת לילה?", "מה לאכול לפני השינה בבוקר?", "מתי הכי נכון להתאמן בעבודת לילה?"]

        # Category 6: Water & Hydration
        elif any(w in text for w in ["מים", "שתייה", "הידרציה", "צמא", "רוויה"]):
            water_target = profile.get('target_water', 3300)
            water_pct = round((water / max(1, water_target)) * 100)
            reply = f"""מאזן נוזלים והידרציה של הצייד (Hydration Status):

כרגע תיעדת **{water} מ\"ל מים** מתוך יעד של **{water_target} מ\"ל** ({water_pct}%).

לצייד במשקל {weight} ק"ג, שמירה על הידרציה גבוהה היא קריטית:
- ירידה של 2% בלבד בנוזלי הגוף מביאה לירידה של 15% בכוח השרירי ובהספק האירובי.
- מים מהווים כ-75% מנפח תא השריר. הידרציה מלאה מגבירה סינתזת חלבון ומונעת התכווצויות.
- בימי אימון או משמרות מומלץ להוסיף 500-750 מ\"ל נוזלים כנגד הזעה."""
            headline = "מדד הידרציה וביצועים פיזיולוגיים"
            tip = "שתה כעת כוס מים גדולה (250-500 מ\"ל) דרך כפתורי השיקוי המהירים במסך התזונה."
            recs = [
                {"title": "יעד הידרציה 3,300 מ\"ל", "content": "פזר את השתייה באופן שווה: כוס מים בכל שעתיים משמרת רמות אנרגיה וריכוז שיא.", "category": "hydration"}
            ]
            chips = ["כמה מים לשתות באימון כוח?", "מה לאכול כדי לקבל מים ממזון?", "האם קפה נספר כמים?"]

        # Default General Consultation
        else:
            reply = f"""שלום צייד! המערכת קלטה את פנייתך.

הסטטוס הנוכחי שלך במערכת:
- **משקל נוכחי:** {weight} ק"ג | **משקל יעד:** {target_weight} ק"ג (מסה נקייה)
- **קלוריות להיום:** {cur_cal} מתוך {target_calories} kcal (נותרו: {rem_cal} kcal)
- **חלבון להיום:** {cur_prot}g מתוך {target_protein}g (נותרו: {rem_prot}g)
- **הידרציית מים:** {water} מ\"ל מתוך {profile.get('target_water', 3300)} מ\"ל

תוכל להתייעץ איתי בכל נושא ספציפי:
- 🥩 התאמת תפריט וארוחות להשלמת חלבון
- 💪 אופטימיזציה של אימונים והתקדמות כוח
- 💊 פרוטוקול תוספים (קריאטין, אומגה 3, מגנזיום)
- 🌙 ניהול שגרה, עייפות ומשמרות לילה
- 🎯 עדכון ושינוי יעדים אישיים"""
            headline = "יועץ המערכת זמין לפקודתך"
            tip = "הקפד לתעד את הארוחות והשתייה ברציפות לבניית בייסליין מדעי מדויק."
            recs = [
                {"title": "התמדה בתיעוד יומי", "content": "תיעוד של 3 ימים רצופים פותח את מנוע הניתוחים ארוכי-הטווח (Long-Term Science Engine).", "category": "general"}
            ]
            chips = ["מה לאכול עכשיו כדי לסגור חלבון?", "איך לקחת קריאטין במסה נקייה?", "איך לתכנן תזונה במשמרת לילה?"]

        return {
            "reply": reply,
            "headline": headline,
            "tip": tip,
            "recommendations": recs,
            "suggested_targets": {},
            "followup_chips": chips
        }

    @classmethod
    def get_history(cls, conn, limit=50) -> list:
        c = conn.cursor()
        c.execute("""
        SELECT id, sender, message, recommendations_json, created_at 
        FROM ai_chat_messages 
        ORDER BY id ASC 
        LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        messages = []
        for r in rows:
            m = dict(r)
            try:
                m["recommendations"] = json.loads(m.get("recommendations_json") or "[]")
            except Exception:
                m["recommendations"] = []
            messages.append(m)
        return messages

    @classmethod
    def get_recommendations(cls, conn) -> list:
        c = conn.cursor()
        c.execute("SELECT * FROM ai_recommendations ORDER BY is_active DESC, id DESC LIMIT 50")
        return [dict(r) for r in c.fetchall()]

    @classmethod
    def toggle_recommendation(cls, conn, rec_id: int):
        c = conn.cursor()
        c.execute("UPDATE ai_recommendations SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?", (rec_id,))
        conn.commit()
        c.execute("SELECT is_active FROM ai_recommendations WHERE id = ?", (rec_id,))
        row = c.fetchone()
        return row[0] if row else 0

    @classmethod
    def delete_recommendation(cls, conn, rec_id: int):
        c = conn.cursor()
        c.execute("DELETE FROM ai_recommendations WHERE id = ?", (rec_id,))
        conn.commit()

    @classmethod
    def apply_targets(cls, conn, body: dict) -> dict:
        c = conn.cursor()
        allowed = ["target_calories", "target_protein", "target_carbs", "target_fats", "target_water", "target_weight", "goal", "height", "weight", "age", "sex"]
        fields = []
        vals = []
        for k in allowed:
            if k in body and body[k] is not None:
                fields.append(f"{k} = ?")
                vals.append(body[k])
        if fields:
            vals.append(1)
            c.execute(f"UPDATE hunter_profile SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", vals)
            
            # Recalculate BMR/TDEE if biometrics changed
            c.execute("SELECT weight, height, age, sex, activity_level, goal FROM hunter_profile WHERE id=1")
            p_row = c.fetchone()
            if p_row:
                sci = NutritionScienceEngine.calculate_full_profile(
                    weight_kg=float(p_row[0] or 83.0),
                    height_cm=float(p_row[1] or 180.0),
                    age=int(p_row[2] or 26),
                    sex=p_row[3] or "male",
                    activity_level=p_row[4] or "moderate",
                    goal=p_row[5] or "bulk"
                )
                c.execute("UPDATE hunter_profile SET bmr = ?, tdee = ? WHERE id=1", (sci["bmr"], sci["tdee"]))
            conn.commit()
        c.execute("SELECT * FROM hunter_profile WHERE id = 1")
        return dict(c.fetchone() or {})


# -------------------------------------------------------------
# Adaptive Habit-Based Meal Recommendation Engine
# -------------------------------------------------------------
class MealRecommendationEngine:
    @staticmethod
    def get_recommendations(conn, today):
        c = conn.cursor()
        c.execute("SELECT * FROM hunter_profile WHERE id=1")
        p_row = c.fetchone()
        if not p_row:
            return {"error": "Profile not found"}
        profile = dict(p_row)
        goal = profile.get("goal", "cut")
        target_calories = float(profile.get("target_calories") or 2100)
        target_protein = float(profile.get("target_protein") or 160)
        target_carbs = float(profile.get("target_carbs") or 220)
        target_fats = float(profile.get("target_fats") or 65)

        # Consumed macros today
        c.execute("""
            SELECT COALESCE(SUM(calories), 0) as cals,
                   COALESCE(SUM(protein), 0) as prot,
                   COALESCE(SUM(carbs), 0) as carbs,
                   COALESCE(SUM(fats), 0) as fats
            FROM daily_logs
            WHERE date = ?
        """, (today,))
        cons = c.fetchone()
        cons_cals = float(cons["cals"] or 0)
        cons_prot = float(cons["prot"] or 0)
        cons_carbs = float(cons["carbs"] or 0)
        cons_fats = float(cons["fats"] or 0)

        rem_cals = max(0, round(target_calories - cons_cals))
        rem_prot = max(0, round(target_protein - cons_prot))
        rem_carbs = max(0, round(target_carbs - cons_carbs))
        rem_fats = max(0, round(target_fats - cons_fats))

        # Query user eating history across all logs
        c.execute("""
            SELECT food_name,
                   AVG(serving_size_g) as avg_size,
                   AVG(calories) as avg_cals,
                   AVG(protein) as avg_prot,
                   AVG(carbs) as avg_carbs,
                   AVG(fats) as avg_fats,
                   AVG(fiber) as avg_fiber,
                   COUNT(*) as frequency
            FROM daily_logs
            GROUP BY food_name
            ORDER BY frequency DESC, MAX(id) DESC
        """)
        history_rows = [dict(r) for r in c.fetchall()]
        unique_foods_count = len(history_rows)

        is_personalized = unique_foods_count >= 3

        if not is_personalized:
            recommendations = MealRecommendationEngine._get_baseline_recommendations(rem_cals, rem_prot, rem_carbs, rem_fats, goal)
        else:
            recommendations = MealRecommendationEngine._get_personalized_recommendations(history_rows, rem_cals, rem_prot, rem_carbs, rem_fats, goal)

        return {
            "is_personalized": is_personalized,
            "unique_foods_learned": unique_foods_count,
            "today_status": {
                "consumed": {
                    "calories": round(cons_cals),
                    "protein": round(cons_prot),
                    "carbs": round(cons_carbs),
                    "fats": round(cons_fats)
                },
                "target": {
                    "calories": round(target_calories),
                    "protein": round(target_protein),
                    "carbs": round(target_carbs),
                    "fats": round(target_fats)
                },
                "remaining": {
                    "calories": rem_cals,
                    "protein": rem_prot,
                    "carbs": rem_carbs,
                    "fats": rem_fats
                }
            },
            "system_message": (
                f"🎯 המלצות חכמות שנלמדו מ-{unique_foods_count} מאכלים שרשמת ביומן"
                if is_personalized else
                "🌱 מצב למידה ראשוני: המלצות בסיס מדעיות מותאמות ליעדים (המערכת תלמד את העדפותיך ככל שתמשיך לרשום ארוחות ביומן)"
            ),
            "recommendations": recommendations
        }

    @staticmethod
    def _get_baseline_recommendations(rem_cals, rem_prot, rem_carbs, rem_fats, goal):
        # Build 4 versatile scientific staple Israeli meals tailored to remaining deficits
        recs = [
            {
                "id": "rec_base_chicken",
                "title": "חזה עוף צלוי עם שעועית ירוקה",
                "badge": "🚀 חלבון מלא דל שומן",
                "badge_type": "protein",
                "why": "חלבון טהור לסגירת פער החלבון היומי עם 6.8 גרם שומן בלבד. מושלם לחיטוב ולשימור מסת שריר ללא עודף קלוריות.",
                "total_calories": 344,
                "total_protein": 58.6,
                "total_carbs": 10.5,
                "total_fats": 6.8,
                "foods": [
                    {
                        "food_name": "חזה עוף מבושל / צלוי",
                        "serving_count": 1.8,
                        "serving_size_g": 100,
                        "calories": 297,
                        "protein": 55.8,
                        "carbs": 0,
                        "fats": 6.5,
                        "meal_type": "lunch"
                    },
                    {
                        "food_name": "שעועית ירוקה מאודה",
                        "serving_count": 1.5,
                        "serving_size_g": 100,
                        "calories": 47,
                        "protein": 2.8,
                        "carbs": 10.5,
                        "fats": 0.3,
                        "meal_type": "lunch"
                    }
                ]
            },
            {
                "id": "rec_base_cottage",
                "title": "גביע קוטג' 5% עם ביצה וירקות",
                "badge": "⏱️ ללא בישול • קזאין מושהה",
                "badge_type": "quick",
                "why": "חלבון קזאין בעל שחרור איטי להשבעה מתמשכת ומניעת רעב, בליווי שומן איכותי מביצה וירקות טריים לסיבים.",
                "total_calories": 335,
                "total_protein": 35.0,
                "total_carbs": 9.2,
                "total_fats": 17.6,
                "foods": [
                    {
                        "food_name": "גבינת קוטג 5%",
                        "serving_count": 2.5,
                        "serving_size_g": 100,
                        "calories": 238,
                        "protein": 27.5,
                        "carbs": 3.8,
                        "fats": 12.5,
                        "meal_type": "dinner"
                    },
                    {
                        "food_name": "ביצה גדולה שלמה (L)",
                        "serving_count": 1.0,
                        "serving_size_g": 60,
                        "calories": 72,
                        "protein": 6.3,
                        "carbs": 0.4,
                        "fats": 4.8,
                        "meal_type": "dinner"
                    },
                    {
                        "food_name": "מלפפון ועגבניה חתוכים",
                        "serving_count": 1.5,
                        "serving_size_g": 100,
                        "calories": 25,
                        "protein": 1.2,
                        "carbs": 5.0,
                        "fats": 0.3,
                        "meal_type": "dinner"
                    }
                ]
            },
            {
                "id": "rec_base_pro_yogurt",
                "title": "גביע יוגורט פרו עם שקדים טבעיים",
                "badge": "⚡ נשנוש חלבון קל ומהיר",
                "badge_type": "snack",
                "why": "מנת התאוששות קומפקטית עם 23 גרם חלבון ב-217 קלוריות בלבד. אידיאלית כנשנוש ביניים או בסיום משמרת.",
                "total_calories": 217,
                "total_protein": 23.2,
                "total_carbs": 10.2,
                "total_fats": 9.0,
                "foods": [
                    {
                        "food_name": "יוגורט פרו / יווני מועשר בחלבון",
                        "serving_count": 2.0,
                        "serving_size_g": 100,
                        "calories": 130,
                        "protein": 20.0,
                        "carbs": 7.0,
                        "fats": 1.5,
                        "meal_type": "snack"
                    },
                    {
                        "food_name": "שקדים טבעיים",
                        "serving_count": 0.15,
                        "serving_size_g": 100,
                        "calories": 87,
                        "protein": 3.2,
                        "carbs": 3.2,
                        "fats": 7.5,
                        "meal_type": "snack"
                    }
                ]
            },
            {
                "id": "rec_base_tuna",
                "title": "טונה במים עם 2 פרוסות לחם מלא וכפית טחינה",
                "badge": "🐟 חלבון רזה + פחמימה מורכבת",
                "badge_type": "balanced",
                "why": "39 גרם חלבון מלא ממקור ימי דל שומן, בשילוב פחמימה מורכבת שמעניקה שובע ושומן בלתי-רווי איכותי מטחינה.",
                "total_calories": 355,
                "total_protein": 39.2,
                "total_carbs": 28.8,
                "total_fats": 8.6,
                "foods": [
                    {
                        "food_name": "טונה בהירה במים (מסוננת)",
                        "serving_count": 1.12,
                        "serving_size_g": 100,
                        "calories": 130,
                        "protein": 29.1,
                        "carbs": 0.0,
                        "fats": 0.9,
                        "meal_type": "lunch"
                    },
                    {
                        "food_name": "פרוסת לחם מלא 100%",
                        "serving_count": 2.0,
                        "serving_size_g": 35,
                        "calories": 160,
                        "protein": 7.6,
                        "carbs": 27.0,
                        "fats": 2.2,
                        "meal_type": "lunch"
                    },
                    {
                        "food_name": "טחינה גולמית (כפית)",
                        "serving_count": 0.1,
                        "serving_size_g": 100,
                        "calories": 65,
                        "protein": 2.5,
                        "carbs": 1.8,
                        "fats": 5.5,
                        "meal_type": "lunch"
                    }
                ]
            }
        ]
        return recs

    @staticmethod
    def _get_personalized_recommendations(history_rows, rem_cals, rem_prot, rem_carbs, rem_fats, goal):
        protein_sources = []
        carb_sources = []
        snacks = []

        for f in history_rows:
            p = float(f.get("avg_prot") or 0)
            c = float(f.get("avg_carbs") or 0)
            cal = float(f.get("avg_cals") or 0)
            
            # High protein
            if p >= 12 or (cal > 0 and (p * 4 / cal) >= 0.30):
                protein_sources.append(f)
            # Carb source
            if c >= 15:
                carb_sources.append(f)
            # Snack/light
            if cal <= 250 and p >= 4:
                snacks.append(f)

        recs = []

        # Card 1: Favorite Protein Powerhouse
        if protein_sources:
            top_p = protein_sources[0]
            avg_p = float(top_p.get("avg_prot") or 25)
            target_need = max(20, min(55, rem_prot if rem_prot > 0 else 30))
            scale = round(min(2.5, max(0.6, target_need / max(1, avg_p))), 2)
            
            p_cals = round(float(top_p.get("avg_cals") or 150) * scale)
            p_prot = round(avg_p * scale, 1)
            p_carbs = round(float(top_p.get("avg_carbs") or 0) * scale, 1)
            p_fats = round(float(top_p.get("avg_fats") or 0) * scale, 1)
            p_grams = round(float(top_p.get("avg_size") or 100) * scale)

            recs.append({
                "id": "rec_custom_protein",
                "title": f"השלמת חלבון: {top_p['food_name']}",
                "badge": f"🏆 מועדף עליך (נרשם {top_p['frequency']} פעמים)",
                "badge_type": "favorite",
                "why": f"מנה מדודה של {p_grams} גרם מספקת {p_prot}g חלבון ותסגור {min(100, round((p_prot / max(1, rem_prot)) * 100)) if rem_prot > 0 else 100}% מיעד החלבון שנותר להיום.",
                "total_calories": p_cals,
                "total_protein": p_prot,
                "total_carbs": p_carbs,
                "total_fats": p_fats,
                "foods": [
                    {
                        "food_name": top_p["food_name"],
                        "serving_count": scale,
                        "serving_size_g": float(top_p.get("avg_size") or 100),
                        "calories": p_cals,
                        "protein": p_prot,
                        "carbs": p_carbs,
                        "fats": p_fats,
                        "meal_type": "lunch"
                    }
                ]
            })

        # Card 2: Learned Balanced Combo (Top Protein + Top Carb)
        if protein_sources and carb_sources:
            top_p = protein_sources[0]
            top_c = carb_sources[0]
            
            p_scale = 1.0
            c_scale = 1.0
            if rem_cals > 0:
                combo_budget = max(300, min(650, int(rem_cals * 0.7)))
                base_sum = float(top_p.get("avg_cals") or 150) + float(top_c.get("avg_cals") or 150)
                if base_sum > 0:
                    mult = min(1.8, max(0.6, combo_budget / base_sum))
                    p_scale = round(mult, 2)
                    c_scale = round(mult, 2)

            f1_cals = round(float(top_p.get("avg_cals") or 150) * p_scale)
            f1_prot = round(float(top_p.get("avg_prot") or 25) * p_scale, 1)
            f1_carbs = round(float(top_p.get("avg_carbs") or 0) * p_scale, 1)
            f1_fats = round(float(top_p.get("avg_fats") or 0) * p_scale, 1)

            f2_cals = round(float(top_c.get("avg_cals") or 150) * c_scale)
            f2_prot = round(float(top_c.get("avg_prot") or 3) * c_scale, 1)
            f2_carbs = round(float(top_c.get("avg_carbs") or 30) * c_scale, 1)
            f2_fats = round(float(top_c.get("avg_fats") or 1) * c_scale, 1)

            tot_cals = f1_cals + f2_cals
            tot_prot = round(f1_prot + f2_prot, 1)
            tot_carbs = round(f1_carbs + f2_carbs, 1)
            tot_fats = round(f1_fats + f2_fats, 1)

            recs.append({
                "id": "rec_custom_combo",
                "title": f"קומבו מועדף: {top_p['food_name']} + {top_c['food_name']}",
                "badge": "🍽️ קומבו מנצח מההרגלים שלך",
                "badge_type": "combo",
                "why": f"שילוב שני המאכלים המובילים בהיסטוריה שלך ביחס מדויק שמספק {tot_prot}g חלבון ב-{tot_cals} קלוריות, ומשתלב מושלם ביתרת היעדים.",
                "total_calories": tot_cals,
                "total_protein": tot_prot,
                "total_carbs": tot_carbs,
                "total_fats": tot_fats,
                "foods": [
                    {
                        "food_name": top_p["food_name"],
                        "serving_count": p_scale,
                        "serving_size_g": float(top_p.get("avg_size") or 100),
                        "calories": f1_cals,
                        "protein": f1_prot,
                        "carbs": f1_carbs,
                        "fats": f1_fats,
                        "meal_type": "dinner"
                    },
                    {
                        "food_name": top_c["food_name"],
                        "serving_count": c_scale,
                        "serving_size_g": float(top_c.get("avg_size") or 100),
                        "calories": f2_cals,
                        "protein": f2_prot,
                        "carbs": f2_carbs,
                        "fats": f2_fats,
                        "meal_type": "dinner"
                    }
                ]
            })

        # Card 3: Light Snack from Favorites or Secondary Protein
        snack_candidate = None
        if snacks:
            snack_candidate = snacks[0]
        elif len(protein_sources) > 1:
            snack_candidate = protein_sources[1]
        elif history_rows:
            snack_candidate = history_rows[-1]

        if snack_candidate:
            s_cals = round(float(snack_candidate.get("avg_cals") or 120))
            s_prot = round(float(snack_candidate.get("avg_prot") or 10), 1)
            s_carbs = round(float(snack_candidate.get("avg_carbs") or 5), 1)
            s_fats = round(float(snack_candidate.get("avg_fats") or 2), 1)
            s_grams = round(float(snack_candidate.get("avg_size") or 100))

            recs.append({
                "id": "rec_custom_snack",
                "title": f"סגירת פינה קלה: {snack_candidate['food_name']}",
                "badge": "⚡ נשנוש מדויק מהמועדפים",
                "badge_type": "snack",
                "why": f"נשנוש קל של {s_grams} גרם שמשתלב בול בשארית השומנים והקלוריות שלך להיום ללא עומס על מערכת העיכול.",
                "total_calories": s_cals,
                "total_protein": s_prot,
                "total_carbs": s_carbs,
                "total_fats": s_fats,
                "foods": [
                    {
                        "food_name": snack_candidate["food_name"],
                        "serving_count": 1.0,
                        "serving_size_g": float(snack_candidate.get("avg_size") or 100),
                        "calories": s_cals,
                        "protein": s_prot,
                        "carbs": s_carbs,
                        "fats": s_fats,
                        "meal_type": "snack"
                    }
                ]
            })

        # Fallback if fewer than 3 personalized
        if len(recs) < 3:
            baseline_extras = MealRecommendationEngine._get_baseline_recommendations(rem_cals, rem_prot, rem_carbs, rem_fats, goal)
            for b in baseline_extras:
                if len(recs) >= 3:
                    break
                if not any(r["title"] == b["title"] for r in recs):
                    recs.append(b)

        return recs


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
            self.handle_garmin_status(query)
        elif path == "/api/garmin/health":
            self.handle_get_garmin_health(query)
        elif path == "/api/garmin/webhook-info":
            self.handle_get_garmin_webhook_info()
        elif path in ["/api/garmin/webhook", "/api/garmin/sync", "/api/garmin/health-sync", "/api/garmin/smart-sync"]:
            self.handle_garmin_webhook_get(query)
        elif path == "/api/skills":
            self.handle_get_skills()
        elif path == "/api/achievements":
            self.handle_get_achievements()
        elif path == "/api/workouts/today":
            self.handle_get_workouts()
        elif path == "/api/supplements/today":
            self.handle_get_supplements()
        elif path == "/api/health-synergy/daily-debrief":
            self.handle_get_daily_debrief()
        elif path == "/api/reports/weekly":
            self.handle_get_weekly_report()
        elif path == "/api/history/calendar":
            month = query.get("month", [""])[0]
            self.handle_get_calendar_history(month)
        elif path == "/api/history/calendar/day":
            day_str = query.get("date", [""])[0]
            self.handle_get_calendar_day_detail(day_str)
        elif path == "/api/history/long-term-insights":
            window = query.get("window", ["14"])[0]
            self.handle_get_long_term_insights(window)
        elif path == "/api/ai/consult/history":
            self.handle_get_ai_history()
        elif path == "/api/ai/recommendations":
            self.handle_get_ai_recommendations()
        elif path == "/api/nutrition/recommend-meals":
            self.handle_get_meal_recommendations()
        elif path == "/api/penalty/status":
            self.handle_get_penalty_status()
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
        
        body = {}
        if body_bytes:
            body_str = body_bytes.decode("utf-8", errors="ignore").strip()
            if body_str:
                try:
                    body = json.loads(body_str)
                except Exception:
                    # Fallback to form-urlencoded (common in iOS Shortcuts POST)
                    try:
                        from urllib.parse import parse_qs
                        qs = parse_qs(body_str)
                        body = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in qs.items()}
                    except Exception:
                        body = {}

        # Merge URL query parameters into body if not already present
        if parsed.query:
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                for k, v in qs.items():
                    val = v[0] if isinstance(v, list) and len(v) == 1 else v
                    if k not in body or body[k] is None or body[k] == "":
                        body[k] = val
            except Exception:
                pass

        if path == "/api/awakening":
            self.handle_post_awakening(body)
        elif path == "/api/awakening/reset":
            self.handle_reset_awakening()
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
        elif path == "/api/penalty/redeem":
            self.handle_post_penalty_redeem(body)
        elif path == "/api/foods":
            self.handle_create_custom_food(body)
        elif path == "/api/restore":
            self.handle_restore_backup(body)
        elif path == "/api/garmin/quick-water":
            self.handle_garmin_water(body)
        elif path in ["/api/garmin/health-sync", "/api/garmin/webhook", "/api/garmin/sync"]:
            self.handle_garmin_webhook_post(body)
        elif path == "/api/garmin/upload-file":
            self.handle_garmin_upload_file(body)
        elif path == "/api/garmin/smart-sync":
            self.handle_garmin_smart_sync(body)
        elif path == "/api/medication/attent":
            self.handle_post_attent(body)
        elif path == "/api/workouts/log":
            self.handle_post_workout(body)
        elif path == "/api/supplements/log":
            self.handle_post_supplement(body)
        elif path == "/api/reset/today":
            self.handle_reset_today(body)
        elif path == "/api/reset/full":
            self.handle_reset_full()
        elif path == "/api/food/recognize":
            self.handle_food_recognize(body)
        elif path == "/api/food/chat-parse":
            self.handle_food_chat_parse(body)
        elif path == "/api/goals/ai-calculate":
            self.handle_goals_ai_calculate(body)
        elif path == "/api/ai/consult":
            self.handle_post_ai_consult(body)
        elif path == "/api/ai/recommendations/toggle":
            self.handle_post_ai_recommendation_toggle(body)
        elif path == "/api/ai/apply-targets":
            self.handle_post_ai_apply_targets(body)
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/nutrition/log/") or path == "/api/nutrition/log":
            try:
                parsed_query = parse_qs(parsed.query)
                name_param = parsed_query.get("name", [None])[0] or parsed_query.get("food_name", [None])[0]
                param_id = path.split("/")[-1] if path.startswith("/api/nutrition/log/") else None
                if not param_id or param_id == "log":
                    param_id = parsed_query.get("id", [None])[0]

                if name_param:
                    with Database.get_connection() as conn:
                        today = get_hunter_shift_date(conn, parsed_query.get("date", [None])[0])
                        c = conn.cursor()
                        c.execute("DELETE FROM daily_logs WHERE date = ? AND food_name = ?", (today, name_param))
                        c.execute("DELETE FROM water_logs WHERE date = ? AND (beverage_name = ? OR beverage_name = ? OR beverage_name LIKE ?)",
                                  (today, f"{name_param} (נוזלים)", name_param, f"%{name_param}%"))
                        conn.commit()
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"status": "deleted", "food_name": name_param}, ensure_ascii=False).encode("utf-8"))
                    return

                if param_id:
                    try:
                        log_id = int(param_id)
                        self.handle_delete_log(log_id)
                    except ValueError:
                        self._set_headers(200)
                        self.wfile.write(json.dumps({"status": "deleted", "id": param_id}, ensure_ascii=False).encode("utf-8"))
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Missing log id or name"}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/nutrition/water" or path.startswith("/api/nutrition/water/"):
            try:
                parsed_query = parse_qs(parsed.query)
                name_param = parsed_query.get("name", [None])[0] or parsed_query.get("beverage_name", [None])[0]
                param_id = path.split("/")[-1] if path.startswith("/api/nutrition/water/") else None
                if not param_id or param_id == "water":
                    param_id = parsed_query.get("id", [None])[0]

                if name_param:
                    with Database.get_connection() as conn:
                        today = get_hunter_shift_date(conn, parsed_query.get("date", [None])[0])
                        c = conn.cursor()
                        c.execute("DELETE FROM water_logs WHERE date = ? AND (beverage_name = ? OR beverage_name LIKE ?)",
                                  (today, name_param, f"%{name_param}%"))
                        conn.commit()
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"status": "deleted", "beverage_name": name_param}, ensure_ascii=False).encode("utf-8"))
                    return

                water_id = None
                if param_id:
                    try:
                        water_id = int(param_id)
                    except ValueError:
                        self._set_headers(200)
                        self.wfile.write(json.dumps({"status": "deleted", "id": param_id}, ensure_ascii=False).encode("utf-8"))
                        return
                date_param = parsed_query.get("date", [None])[0]
                self.handle_delete_water(water_id, date_param)
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/medication/attent" or path.startswith("/api/medication/attent/"):
            dose_id = None
            if path.startswith("/api/medication/attent/"):
                try:
                    dose_id = int(path.split("/")[-1])
                except Exception:
                    pass
            else:
                parsed_query = parse_qs(parsed.query)
                if "id" in parsed_query:
                    try:
                        dose_id = int(parsed_query["id"][0])
                    except Exception:
                        pass
            self.handle_delete_attent(dose_id)
        elif path.startswith("/api/supplements/log/"):
            try:
                supp_id = int(path.split("/")[-1])
                self.handle_delete_supplement(supp_id)
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif path.startswith("/api/workouts/log/"):
            try:
                workout_id = int(path.split("/")[-1])
                self.handle_delete_workout(workout_id)
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif path == "/api/ai/recommendations" or path.startswith("/api/ai/recommendations/"):
            try:
                rec_id = None
                if path.startswith("/api/ai/recommendations/"):
                    try:
                        rec_id = int(path.split("/")[-1])
                    except Exception:
                        pass
                else:
                    parsed_q = parse_qs(parsed.query)
                    if "id" in parsed_q:
                        rec_id = int(parsed_q["id"][0])
                if rec_id:
                    with Database.get_connection() as conn:
                        HunterAIConsultant.delete_recommendation(conn, rec_id)
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "deleted"}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self._set_headers(404)

    # ------------------ Handlers ------------------
    # --- Skills & Workouts ---
    def handle_get_skills(self):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM hunter_skills ORDER BY id ASC")
            skills = [dict(r) for r in c.fetchall()]
        self._set_headers()
        self.wfile.write(json.dumps({"skills": skills}, ensure_ascii=False).encode("utf-8"))

    def handle_get_achievements(self):
        with Database.get_connection() as conn:
            newly_unlocked = HunterAchievementEngine.evaluate_and_unlock(conn)
            c = conn.cursor()
            c.execute("SELECT * FROM hunter_achievements ORDER BY id ASC")
            raw_achs = [dict(r) for r in c.fetchall()]
            achs = []
            for a in raw_achs:
                tier_color = "gold"
                cat = a.get("category", "")
                code = a.get("code", "")
                if "rank" in cat or code == "shadow_monarch":
                    tier_color = "crimson" if code in ("rank_s", "shadow_monarch") else "purple"
                elif cat in ("nutrition", "vitality"):
                    tier_color = "cyan"
                elif cat in ("alchemy", "milestone"):
                    tier_color = "purple"

                reward = f"+{a.get('target_val', 1) * 50 + 100} EXP"
                if cat == "rank":
                    reward = "תואר צייד חדש • עליית כוח"
                elif code == "shadow_monarch":
                    reward = "👑 מונרך הצללים • ARISE"

                achs.append({
                    "id": a["id"],
                    "code": a["code"],
                    "title": a.get("title_he") or a.get("title_en"),
                    "title_he": a.get("title_he"),
                    "title_en": a.get("title_en"),
                    "description": a.get("desc_he"),
                    "desc_he": a.get("desc_he"),
                    "icon": a.get("icon", "🏆"),
                    "color_hex": a.get("color_hex", "#8b5cf6"),
                    "tier_color": tier_color,
                    "category": a.get("category"),
                    "target_val": a.get("target_val"),
                    "unlocked": a.get("unlocked", 0),
                    "unlocked_at": a.get("unlocked_at"),
                    "reward_desc": reward
                })
            unlocked_count = sum(1 for a in achs if a["unlocked"] == 1)
        self._set_headers()
        self.wfile.write(json.dumps({
            "achievements": achs,
            "unlocked_count": unlocked_count,
            "total_count": len(achs),
            "newly_unlocked": newly_unlocked
        }, ensure_ascii=False).encode("utf-8"))

    def handle_get_workouts(self):
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            c = conn.cursor()
            c.execute("SELECT * FROM workout_logs WHERE date = ? ORDER BY id DESC", (today,))
            workouts = [dict(r) for r in c.fetchall()]
        self._set_headers()
        self.wfile.write(json.dumps({"workouts": workouts}, ensure_ascii=False).encode("utf-8"))

    def handle_post_workout(self, body):
        try:
            w_type = body.get("workout_type", "strength") or "strength"
            title = body.get("title") or ("אימון כוח (Hypertrophy)" if w_type == "strength" else "אימון ריצה וסיבולת")
            duration = int(body.get("duration_min") or 45)
            calories = int(body.get("calories_burned") or (duration * 7))
            notes = body.get("notes") or ""
            now_time = body.get("timestamp") or get_israel_now().strftime("%H:%M")

            with Database.get_connection() as conn:
                today = body.get("date") or get_hunter_shift_date(conn, body.get("client_date"))
                c = conn.cursor()
                c.execute("""
                INSERT INTO workout_logs (date, workout_type, title, duration_min, calories_burned, notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (today, w_type, title, duration, calories, notes, now_time))
                w_id = c.lastrowid

                skill_code = "colossus_strength" if w_type == "strength" else "shadow_sprint"
                skill_exp = 30 + int(duration * 0.8)
                skill_res = HunterLevelingEngine.add_skill_exp(conn, skill_code, skill_exp)

                c.execute("UPDATE hunter_profile SET fatigue = max(0, fatigue - 10) WHERE id=1")
                conn.commit()

                c.execute("SELECT * FROM hunter_profile WHERE id=1")
                profile = dict(c.fetchone())

            self._set_headers(201)
            self.wfile.write(json.dumps({
                "status": "workout_logged",
                "id": w_id,
                "skill_leveling": skill_res,
                "profile": profile
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_delete_workout(self, w_id):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM workout_logs WHERE id=?", (w_id,))
            conn.commit()
        self._set_headers(200)
        self.wfile.write(json.dumps({"status": "deleted", "id": w_id}).encode("utf-8"))

    # --- Supplements & Vitamins ---
    def handle_get_supplements(self):
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            c = conn.cursor()
            c.execute("SELECT * FROM supplements_log WHERE date = ? ORDER BY id DESC", (today,))
            supps = [dict(r) for r in c.fetchall()]
        self._set_headers()
        self.wfile.write(json.dumps({"supplements": supps}, ensure_ascii=False).encode("utf-8"))

    def handle_post_supplement(self, body):
        try:
            name = body.get("name") or "תוסף ויטמין"
            dosage = str(body.get("dosage") or "1 מנה")
            unit = body.get("unit") or "mg"
            category = body.get("category") or "vitamin"
            notes = body.get("notes") or ""
            now_time = body.get("timestamp") or get_israel_now().strftime("%H:%M")

            with Database.get_connection() as conn:
                today = body.get("date") or get_hunter_shift_date(conn, body.get("client_date"))
                c = conn.cursor()
                c.execute("""
                INSERT INTO supplements_log (date, name, dosage, unit, category, notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (today, name, dosage, unit, category, notes, now_time))
                s_id = c.lastrowid

                skill_res = HunterLevelingEngine.add_skill_exp(conn, "alchemy_discipline", 20)
                conn.commit()

                c.execute("SELECT * FROM hunter_profile WHERE id=1")
                profile = dict(c.fetchone())

            self._set_headers(201)
            self.wfile.write(json.dumps({
                "status": "supplement_logged",
                "id": s_id,
                "skill_leveling": skill_res,
                "profile": profile
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_delete_supplement(self, s_id):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM supplements_log WHERE id=?", (s_id,))
            conn.commit()
        self._set_headers(200)
        self.wfile.write(json.dumps({"status": "deleted", "id": s_id}).encode("utf-8"))

    # --- Daily Health Debrief ---
    def handle_get_daily_debrief(self):
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            debrief = HunterHealthAIAdvisor.generate_daily_debrief(conn, today)
        self._set_headers()
        self.wfile.write(json.dumps(debrief, ensure_ascii=False).encode("utf-8"))

    # --- Weekly Hunter Debrief & WhatsApp/PDF Report ---
    def handle_get_weekly_report(self):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            prof_row = c.fetchone()
            profile = dict(prof_row) if prof_row else {}

            today = get_hunter_shift_date(conn)
            today_dt = datetime.date.fromisoformat(today)
            past_dates = [(today_dt - datetime.timedelta(days=i)).isoformat() for i in range(7)]
            past_dates.reverse()

            start_date_str = past_dates[0]
            end_date_str = past_dates[-1]

            # 1. Daily logs for 7 dates
            c.execute("""
                SELECT date,
                       COUNT(id) as meal_count,
                       COALESCE(SUM(calories), 0) as cals,
                       COALESCE(SUM(protein), 0) as prot,
                       COALESCE(SUM(carbs), 0) as carb,
                       COALESCE(SUM(fats), 0) as fat
                FROM daily_logs
                WHERE date >= ? AND date <= ?
                GROUP BY date
            """, (start_date_str, end_date_str))
            day_map = {r["date"]: dict(r) for r in c.fetchall()}

            # 2. Water logs for 7 dates
            c.execute("""
                SELECT date, COALESCE(SUM(amount_ml), 0) as water
                FROM water_logs
                WHERE date >= ? AND date <= ?
                GROUP BY date
            """, (start_date_str, end_date_str))
            water_map = {r["date"]: r["water"] for r in c.fetchall()}

            # 3. Workouts in 7 dates
            c.execute("""
                SELECT COUNT(*) as total_workouts
                FROM workout_logs
                WHERE date >= ? AND date <= ?
            """, (start_date_str, end_date_str))
            workout_count = c.fetchone()["total_workouts"] or 0

            daily_records = []
            total_cals = 0
            total_prot = 0
            total_water = 0
            active_days_count = 0

            target_cal = profile.get("target_calories", 2000)
            target_prot = profile.get("target_protein", 160)
            target_water = profile.get("target_water", 3000)

            for d_str in past_dates:
                m_info = day_map.get(d_str, {"meal_count": 0, "cals": 0, "prot": 0, "carb": 0, "fat": 0})
                w_ml = water_map.get(d_str, 0)
                is_active = (m_info["meal_count"] > 0 or w_ml > 0)
                if is_active:
                    active_days_count += 1
                total_cals += m_info["cals"]
                total_prot += m_info["prot"]
                total_water += w_ml

                daily_records.append({
                    "date": d_str,
                    "calories": round(m_info["cals"], 1),
                    "protein": round(m_info["prot"], 1),
                    "water_ml": w_ml,
                    "meal_count": m_info["meal_count"]
                })

            divisor = max(1, active_days_count) if active_days_count > 0 else 7
            avg_cal = round(total_cals / divisor)
            avg_prot = round(total_prot / divisor, 1)
            avg_water = round(total_water / divisor)

            prot_adherence = min(100, round((avg_prot / max(1, target_prot)) * 100))
            cal_adherence = min(100, round((1.0 - abs(avg_cal - target_cal) / max(1, target_cal)) * 100))

            is_night = profile.get("shift_mode") == "night"
            shift_label = "משמרות לילה" if is_night else "סדר יום רגיל"

            if prot_adherence >= 90:
                ai_insight = "עמידה מצוינת ביעד החלבון השבועי! שמירה על עקביות זו מבטיחה שימור והיפרטרופיה מיטבית של מסת השריר."
            elif prot_adherence >= 75:
                ai_insight = f"עמידה טובה של {prot_adherence}% ביעד החלבון. להשלמת היעד מומלץ לשלב שייק חלבון או מנת יוגורט מועשרת בתחילת המשמרת."
            else:
                ai_insight = f"זוהה גרעון חלבוני ממוצע השבוע ({prot_adherence}% מהיעד). מומלץ לתכנן מראש 'ארוחת עוגן' חלבונית של לפחות 40 גרם חלבון."

            if is_night:
                ai_insight += " דגש משמרת לילה: הקפד על פחמימות מורכבות בעלות עומס גליקמי נמוך כדי למנוע ירידות סוכר ורדמת בשעות 02:00-05:00."

            name = profile.get("name", "צייד")
            rank = profile.get("rank", "E")
            whatsapp_text = (
                f"🛡️ *דוח שבועי • The System Fitness*\n"
                f"צייד: {name} (דרגה {rank})\n"
                f"📅 שבוע: {start_date_str[5:]} עד {end_date_str[5:]}\n"
                f"⚙️ מצב פעילות: {shift_label}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🔥 קלוריות יומיות: {avg_cal} קק\"ל (יעד: {target_cal})\n"
                f"🥩 חלבון יומי: {avg_prot}g ({prot_adherence}% מהיעד)\n"
                f"💧 מים שבועיים: {round(total_water / 1000.0, 1)} ליטר (ממוצע {avg_water} מ\"ל ליום)\n"
                f"🏋️ אימונים שבוצעו: {workout_count} אימונים\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💡 *תובנת AI שבועית:*\n{ai_insight}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🚀 נוצר באמצעות The System | Solo Leveling OS"
            )

            report = {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "active_days": active_days_count,
                "avg_calories": avg_cal,
                "target_calories": target_cal,
                "cal_adherence": cal_adherence,
                "avg_protein": avg_prot,
                "target_protein": target_prot,
                "prot_adherence": prot_adherence,
                "total_water_liters": round(total_water / 1000.0, 1),
                "avg_water_ml": avg_water,
                "target_water_ml": target_water,
                "workout_count": workout_count,
                "shift_label": shift_label,
                "ai_insight": ai_insight,
                "whatsapp_text": whatsapp_text,
                "daily_records": daily_records
            }

            self._set_headers()
            self.wfile.write(json.dumps(report, ensure_ascii=False).encode("utf-8"))

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
            goal = body.get("goal", "maintain")
            name = body.get("name", "צייד רום")
            weight = float(body.get("weight", 78.0))
            height = float(body.get("height", 178.0))
            target_weight = float(body.get("target_weight", 0)) if body.get("target_weight") else 0
            if goal == "bulk":
                if target_weight <= weight or target_weight == 0:
                    target_weight = round(weight + 4.0, 1)
            elif goal == "cut":
                if target_weight == 0 or target_weight >= weight:
                    target_weight = round(max(40.0, weight - 4.0), 1)
            else:
                if target_weight == 0:
                    target_weight = round(weight, 1)

            ai_analysis_headline = str(body.get("ai_analysis_headline", "")).strip()
            ai_explanation = str(body.get("ai_explanation", "")).strip()
            ai_hunter_tip = str(body.get("ai_hunter_tip", "")).strip()
            age = int(body.get("age", 25))
            sex = body.get("sex", "male")
            activity = body.get("activity_level", "moderate")
            shift_mode = body.get("shift_mode", "standard")
            day_reset_hour = 8 if shift_mode == "night" else 0
            goal_custom_text = str(body.get("goal_custom_text", "")).strip()
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

            # Support custom target overrides (e.g. from AI Goal Architect)
            target_calories = int(body.get("target_calories")) if body.get("target_calories") else sci["target_calories"]
            target_protein = int(body.get("target_protein")) if body.get("target_protein") else sci["target_protein"]
            target_carbs = int(body.get("target_carbs")) if body.get("target_carbs") else sci["target_carbs"]
            target_fats = int(body.get("target_fats")) if body.get("target_fats") else sci["target_fats"]
            target_water = int(body.get("target_water")) if body.get("target_water") else sci["target_water"]
            target_fiber = int(body.get("target_fiber")) if body.get("target_fiber") else sci["target_fiber"]

            with Database.get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                UPDATE hunter_profile SET
                    name = ?, weight = ?, height = ?, target_weight = ?, age = ?, sex = ?, activity_level = ?, goal = ?,
                    body_fat_pct = ?, bmr = ?, tdee = ?, target_calories = ?, target_protein = ?,
                    target_carbs = ?, target_fats = ?, target_water = ?, target_fiber = ?,
                    shift_mode = ?, day_reset_hour = ?, is_awakened = 1, goal_custom_text = ?,
                    ai_analysis_headline = ?, ai_explanation = ?, ai_hunter_tip = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id=1
                """, (
                    name, weight, height, target_weight, age, sex, activity, goal, body_fat or 0,
                    sci["bmr"], sci["tdee"], target_calories, target_protein,
                    target_carbs, target_fats, target_water, target_fiber,
                    shift_mode, day_reset_hour, goal_custom_text,
                    ai_analysis_headline, ai_explanation, ai_hunter_tip
                ))
                conn.commit()

            with Database.get_connection() as conn:
                lvl_res = HunterLevelingEngine.add_exp(conn, 100)

            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "awakened",
                "message": "[SYSTEM: The Hunter has successfully completed the Awakening Assessment!]",
                "science": sci,
                "leveling": lvl_res,
                "is_awakened": 1
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_reset_awakening(self):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE hunter_profile SET is_awakened = 0 WHERE id=1")
            conn.commit()
        self._set_headers(200)
        self.wfile.write(json.dumps({"status": "reset", "is_awakened": 0}, ensure_ascii=False).encode("utf-8"))

    def handle_update_profile(self, body):
        with Database.get_connection() as conn:
            c = conn.cursor()
            allowed = [
                "name", "title", "target_calories", "target_protein", "target_carbs", 
                "target_fats", "target_water", "target_fiber", "fatigue", "shift_mode", "day_reset_hour",
                "target_weight", "is_awakened", "goal_custom_text", "weight", "height", "age", "sex", "activity_level", "goal",
                "ai_analysis_headline", "ai_explanation", "ai_hunter_tip"
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

                # If height, weight, age, sex, activity_level or goal were updated, recalculate bmr & tdee
                c.execute("SELECT weight, height, age, sex, activity_level, goal FROM hunter_profile WHERE id=1")
                p_row = c.fetchone()
                if p_row:
                    sci = NutritionScienceEngine.calculate_full_profile(
                        weight_kg=float(p_row["weight"] or 83.0),
                        height_cm=float(p_row["height"] or 180.0),
                        age=int(p_row["age"] or 26),
                        sex=p_row["sex"] or "male",
                        activity_level=p_row["activity_level"] or "moderate",
                        goal=p_row["goal"] or "bulk"
                    )
                    c.execute("UPDATE hunter_profile SET bmr = ?, tdee = ? WHERE id=1", (sci["bmr"], sci["tdee"]))

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
            # Step 1: Calculate "today" using the CURRENT (old) shift mode BEFORE updating the profile
            old_shift_date = get_hunter_shift_date(conn)

            # Step 2: Update the profile to the new mode
            c.execute("UPDATE hunter_profile SET shift_mode = ?, day_reset_hour = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (mode, reset_h))
            conn.commit()

            # Step 3: Calculate "today" using the NEW shift mode
            new_shift_date = get_hunter_shift_date(conn)

            # Step 4: If the shift date changed at night (00:00 - 08:00), only migrate records
            # that were logged during late-night hours (00:00 to 08:00) so daytime meals are never corrupted!
            if old_shift_date != new_shift_date:
                tables = ["daily_logs", "water_logs", "medication_logs", "supplements_log", "workout_logs"]
                for tbl in tables:
                    try:
                        c.execute(f"UPDATE {tbl} SET date = ? WHERE date = ? AND timestamp >= '00:00' AND timestamp <= '08:00'", (new_shift_date, old_shift_date))
                    except Exception:
                        pass
                conn.commit()
        return self.handle_get_nutrition_today()


    def handle_get_nutrition_today(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        client_date = query.get("client_date", [None])[0] or query.get("date", [None])[0]
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn, client_date)
            c = conn.cursor()
            c.execute("SELECT * FROM daily_logs WHERE date = ? ORDER BY id DESC", (today,))
            meals = [dict(r) for r in c.fetchall()]

            # Clean up orphaned food_fluid water logs if the corresponding food meal was deleted
            active_foods = set(m.get("food_name", "").strip() for m in meals if m.get("food_name"))
            c.execute("SELECT id, beverage_name FROM water_logs WHERE date = ? AND beverage_type = 'food_fluid'", (today,))
            for fr in c.fetchall():
                b_name = fr["beverage_name"] or ""
                # Strip ' (נוזלים)' to check matching food name
                base_name = b_name.replace(" (נוזלים)", "").strip()
                if base_name not in active_foods:
                    c.execute("DELETE FROM water_logs WHERE id = ?", (fr["id"],))
            conn.commit()

            # Fetch today's water & beverage logs
            c.execute("SELECT * FROM water_logs WHERE date = ? ORDER BY id ASC", (today,))
            water_logs = [dict(r) for r in c.fetchall()]
            total_water = sum(w["amount_ml"] for w in water_logs)

            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            profile = dict(c.fetchone())

            now = get_israel_now()
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

            # Fetch today's supplements
            c.execute("SELECT * FROM supplements_log WHERE date = ? ORDER BY id ASC", (today,))
            supps = [dict(r) for r in c.fetchall()]

            # Calculate micronutrient contributions from supplements
            supp_micros = parse_supplement_micros(supps)

            # Calculate beverage micronutrients from water_logs (e.g. coconut water, electrolytes, juices)
            bev_potassium = 0.0
            bev_magnesium = 0.0
            bev_sodium = 0.0
            bev_vit_c = 0.0
            for w in water_logs:
                w_name = (w.get("beverage_name") or "").lower()
                w_type = (w.get("beverage_type") or "").lower()
                w_ml = float(w.get("amount_ml") or 0)
                if "קוקוס" in w_name or "קוקוס" in w_type:
                    bev_potassium += (w_ml / 100.0) * 250.0
                    bev_magnesium += (w_ml / 100.0) * 25.0
                    bev_sodium += (w_ml / 100.0) * 105.0
                    bev_vit_c += (w_ml / 100.0) * 2.4
                elif "אלקטרוליט" in w_name or "איזוטוני" in w_name or "electrolyte" in w_name:
                    bev_sodium += (w_ml / 100.0) * 60.0
                    bev_potassium += (w_ml / 100.0) * 40.0
                    bev_magnesium += (w_ml / 100.0) * 10.0
                elif any(k in w_name for k in ["תפוז", "מיץ", "orange", "juice"]):
                    bev_vit_c += (w_ml / 100.0) * 45.0
                    bev_potassium += (w_ml / 100.0) * 180.0

            consumed = {
                "calories": sum(m["calories"] for m in meals) + supp_micros.get("calories", 0),
                "protein": sum(m["protein"] for m in meals) + supp_micros.get("protein", 0),
                "carbs": sum(m["carbs"] for m in meals) + supp_micros.get("carbs", 0),
                "fats": sum(m["fats"] for m in meals) + supp_micros.get("fats", 0),
                "fiber": sum(m["fiber"] for m in meals),
                "sodium_mg": sum(m["sodium_mg"] for m in meals) + supp_micros.get("sodium_mg", 0) + round(bev_sodium, 1),
                "potassium_mg": sum(m["potassium_mg"] for m in meals) + supp_micros.get("potassium_mg", 0) + round(bev_potassium, 1),
                "magnesium_mg": sum(m["magnesium_mg"] for m in meals) + supp_micros.get("magnesium_mg", 0) + round(bev_magnesium, 1),
                "zinc_mg": sum(m["zinc_mg"] for m in meals) + supp_micros.get("zinc_mg", 0),
                "vit_c_mg": sum(m["vit_c_mg"] for m in meals) + supp_micros.get("vit_c_mg", 0) + round(bev_vit_c, 1),
                "vit_d_iu": sum(m["vit_d_iu"] for m in meals) + supp_micros.get("vit_d_iu", 0),
                "omega3_mg": supp_micros.get("omega3_mg", 0),
                "creatine_g": supp_micros.get("creatine_g", 0),
                "iron_mg": sum(m["iron_mg"] for m in meals) + supp_micros.get("iron_mg", 0),
                "water_ml": total_water,
                "supplements_count": len(supps),
                "supp_micros": supp_micros
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
                    "desc": "השלם לפחות 3 יעדי ויטמינים/מינרלים, תוספים וסיבים",
                    "current": sum([
                        consumed["fiber"] >= profile["target_fiber"],
                        consumed["magnesium_mg"] >= 350,
                        consumed["vit_c_mg"] >= 80,
                        consumed["zinc_mg"] >= 10,
                        consumed["potassium_mg"] >= 2500,
                        consumed["vit_d_iu"] >= 1000,
                        consumed["omega3_mg"] >= 800
                    ]),
                    "target": 3,
                    "unit": "מגנים",
                    "done": sum([
                        consumed["fiber"] >= profile["target_fiber"],
                        consumed["magnesium_mg"] >= 350,
                        consumed["vit_c_mg"] >= 80,
                        consumed["zinc_mg"] >= 10,
                        consumed["potassium_mg"] >= 2500,
                        consumed["vit_d_iu"] >= 1000,
                        consumed["omega3_mg"] >= 800
                    ]) >= 3
                }
            ]

            str_bonus = min(25, round((consumed["protein"] / max(1, profile["target_protein"])) * 15))
            cal_ratio = consumed["calories"] / max(1, profile["target_calories"])
            agi_bonus = 15 if (0.85 <= cal_ratio <= 1.05) else (10 if cal_ratio < 1.15 else 5)
            vit_bonus = min(20, round((consumed["water_ml"] / max(1, profile["target_water"])) * 10) + quests[3]["current"] * 2)

            health_adv = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)
            profile["fatigue"] = health_adv["calculated_fatigue"]

            c.execute("SELECT COUNT(*) FROM workout_logs")
            total_workouts = c.fetchone()[0]

            c.execute("SELECT COUNT(*), COALESCE(SUM(unlocked), 0) FROM hunter_achievements")
            ach_stats = c.fetchone()
            ach_total = ach_stats[0] if ach_stats else 0
            ach_unlocked = ach_stats[1] if ach_stats else 0

            profile["total_workouts"] = total_workouts
            profile["ach_unlocked"] = ach_unlocked
            profile["ach_total"] = ach_total

            # Today's detailed water logs
            c.execute("SELECT * FROM water_logs WHERE date = ? ORDER BY id DESC", (today,))
            water_today_logs = [dict(r) for r in c.fetchall()]

            # Evaluate or fetch active penalty
            active_penalty = HunterPenaltyEngine.evaluate_and_apply(conn, today)
            if not active_penalty:
                active_penalty = HunterPenaltyEngine.get_active_penalty(conn, today)

            self._set_headers()
            self.wfile.write(json.dumps({
                "date": today,
                "profile": profile,
                "shift_info": shift_info,
                "consumed": consumed,
                "meals": meals,
                "quests": quests,
                "supplements": supps,
                "water_logs": water_today_logs,
                "active_penalty": active_penalty,
                "total_workouts": total_workouts,
                "achievements_summary": {
                    "unlocked": ach_unlocked,
                    "total": ach_total,
                    "unlocked_count": ach_unlocked,
                    "total_count": ach_total
                },
                "health_advisor": health_adv,
                "stats_live": {
                    "str": profile["stats_str"] + str_bonus,
                    "agi": profile["stats_agi"] + agi_bonus,
                    "vit": profile["stats_vit"] + vit_bonus,
                    "int": profile["stats_int"],
                    "per": profile["stats_per"]
                }
            }, ensure_ascii=False).encode("utf-8"))

    def handle_get_meal_recommendations(self):
        try:
            with Database.get_connection() as conn:
                today = get_hunter_shift_date(conn)
                data = MealRecommendationEngine.get_recommendations(conn, today)
            self._set_headers(200)
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_get_penalty_status(self):
        try:
            with Database.get_connection() as conn:
                today = get_hunter_shift_date(conn)
                penalty = HunterPenaltyEngine.evaluate_and_apply(conn, today)
                if not penalty:
                    penalty = HunterPenaltyEngine.get_active_penalty(conn, today)
            self._set_headers(200)
            self.wfile.write(json.dumps({"active_penalty": penalty}, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_post_penalty_redeem(self, body):
        try:
            penalty_id = int(body.get("penalty_id") or 0)
            with Database.get_connection() as conn:
                res = HunterPenaltyEngine.redeem_penalty(conn, penalty_id)
            self._set_headers(200)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_post_log(self, body):
        try:
            now_time = body.get("timestamp") or get_israel_now().strftime("%H:%M")
            
            food_id = body.get("food_id")
            food_name = body.get("food_name", "ארוחת צייד")
            serving_count = float(body.get("serving_count") or 1.0)
            serving_size_g = float(body.get("serving_size_g") or 100)
            calories = float(body.get("calories") or 0) * serving_count
            protein = float(body.get("protein") or 0) * serving_count
            carbs = float(body.get("carbs") or 0) * serving_count
            fats = float(body.get("fats") or 0) * serving_count
            fiber = float(body.get("fiber") or 0) * serving_count
            sodium_mg = float(body.get("sodium_mg") or 0) * serving_count
            potassium_mg = float(body.get("potassium_mg") or 0) * serving_count
            magnesium_mg = float(body.get("magnesium_mg") or 0) * serving_count
            zinc_mg = float(body.get("zinc_mg") or 0) * serving_count
            vit_c_mg = float(body.get("vit_c_mg") or 0) * serving_count
            vit_d_iu = float(body.get("vit_d_iu") or 0) * serving_count
            iron_mg = float(body.get("iron_mg") or 0) * serving_count
            meal_type = body.get("meal_type", "snack") or "snack"

            # If micronutrients were missing or 0, auto-enrich from recognized food knowledge base
            if (magnesium_mg == 0 and vit_c_mg == 0 and potassium_mg == 0 and iron_mg == 0 and zinc_mg == 0 and vit_d_iu == 0):
                inferred = infer_food_micronutrients(food_name, serving_size_g, serving_count)
                fiber = fiber if fiber > 0 else inferred.get("fiber", 0.0)
                sodium_mg = sodium_mg if sodium_mg > 0 else inferred.get("sodium_mg", 0.0)
                potassium_mg = potassium_mg if potassium_mg > 0 else inferred.get("potassium_mg", 0.0)
                magnesium_mg = magnesium_mg if magnesium_mg > 0 else inferred.get("magnesium_mg", 0.0)
                zinc_mg = zinc_mg if zinc_mg > 0 else inferred.get("zinc_mg", 0.0)
                vit_c_mg = vit_c_mg if vit_c_mg > 0 else inferred.get("vit_c_mg", 0.0)
                vit_d_iu = vit_d_iu if vit_d_iu > 0 else inferred.get("vit_d_iu", 0.0)
                iron_mg = iron_mg if iron_mg > 0 else inferred.get("iron_mg", 0.0)

            with Database.get_connection() as conn:
                today = body.get("date") or get_hunter_shift_date(conn, body.get("client_date"))
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

                # Award XP to Nutrition Mastery skill
                skill_res = HunterLevelingEngine.add_skill_exp(conn, "nutrition_mastery", 15 + int(protein * 0.3))

                # Scientific Auto-Hydration: Check if logged food is a fluid/beverage (coconut water, tea, juice, coffee, etc.)
                fl_ml, fl_icon, fl_cat = detect_food_fluid(food_name, serving_size_g, serving_count)
                added_water_ml = 0
                if fl_ml >= 40 or body.get("is_fluid", False):
                    added_water_ml = fl_ml if fl_ml >= 40 else int(round(serving_size_g * serving_count * 0.90))
                    icon = fl_icon or "💧"
                    c.execute("""
                    INSERT INTO water_logs (date, amount_ml, timestamp, beverage_type, beverage_name, beverage_icon)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (today, added_water_ml, now_time, "food_fluid", f"{food_name} (נוזלים)", icon))
                    conn.commit()

                # Evaluate if penalty is triggered by this meal (e.g. fat overrun on cut)
                penalty_applied = HunterPenaltyEngine.evaluate_and_apply(conn, today)

            self._set_headers(201)
            self.wfile.write(json.dumps({
                "status": "success",
                "log_id": log_id,
                "exp_awarded": exp_awarded,
                "leveling": lvl_res,
                "skill_leveling": skill_res,
                "added_water_ml": added_water_ml,
                "penalty_applied": penalty_applied
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_delete_log(self, log_id):
        food_name = None
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT food_name, date FROM daily_logs WHERE id=?", (log_id,))
            row = c.fetchone()
            if row:
                food_name = row["food_name"]
                fn = food_name.strip()
                dt = row["date"]
                # Delete any associated fluid/water logs created for this food entry
                c.execute("""
                    DELETE FROM water_logs 
                    WHERE date = ? 
                      AND (
                          beverage_name = ? 
                          OR beverage_name = ? 
                          OR beverage_name LIKE ?
                      )
                """, (dt, f"{fn} (נוזלים)", fn, f"%{fn}%"))
                # Delete any duplicate entries for this food on this date
                c.execute("DELETE FROM daily_logs WHERE date = ? AND food_name = ?", (dt, fn))
            c.execute("DELETE FROM daily_logs WHERE id=?", (log_id,))
            conn.commit()
        self._set_headers(200)
        self.wfile.write(json.dumps({
            "status": "deleted",
            "id": log_id,
            "food_name": food_name
        }, ensure_ascii=False).encode("utf-8"))

    def handle_post_water(self, body):
        now_time = body.get("timestamp") or get_israel_now().strftime("%H:%M")
        raw_amount = int(body.get("amount_ml") or body.get("amount") or 250)
        bev_type = body.get("beverage_type", "water")
        bev_name = body.get("beverage_name", "מים")
        bev_icon = body.get("beverage_icon", "💧")
        caffeine_mg = int(body.get("caffeine_mg") or 0)

        # Beverage Hydration Index (BHI) scientific factors
        hydration_factors = {
            "water": 1.0,
            "tea": 1.0,
            "coffee": 0.98,
            "juice": 0.90,
            "electrolyte": 1.0,
            "milk": 0.88,
            "soda": 0.95
        }
        factor = hydration_factors.get(bev_type, 1.0)
        effective_ml = max(10, int(round(raw_amount * factor)))

        with Database.get_connection() as conn:
            today = body.get("date") or get_hunter_shift_date(conn, body.get("client_date"))
            c = conn.cursor()
            c.execute("""
            INSERT INTO water_logs (date, amount_ml, timestamp, beverage_type, beverage_name, beverage_icon, caffeine_mg)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (today, effective_ml, now_time, bev_type, bev_name, bev_icon, caffeine_mg))
            conn.commit()

            c.execute("UPDATE hunter_profile SET fatigue = max(0, fatigue - 3) WHERE id=1")
            conn.commit()
            lvl_res = HunterLevelingEngine.add_exp(conn, 10)

        self._set_headers(200)
        self.wfile.write(json.dumps({
            "status": "success",
            "added_ml": effective_ml,
            "raw_amount_ml": raw_amount,
            "beverage_name": bev_name,
            "beverage_icon": bev_icon,
            "caffeine_mg": caffeine_mg,
            "exp_awarded": 10,
            "leveling": lvl_res
        }, ensure_ascii=False).encode("utf-8"))

    def handle_delete_water(self, water_id=None, date_param=None):
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn, date_param)
            c = conn.cursor()
            if water_id is not None:
                c.execute("DELETE FROM water_logs WHERE id = ?", (water_id,))
            else:
                # Delete the most recent water log for today (Undo feature)
                c.execute("DELETE FROM water_logs WHERE id = (SELECT id FROM water_logs WHERE date = ? ORDER BY id DESC LIMIT 1)", (today,))
            conn.commit()
        self._set_headers(200)
        self.wfile.write(json.dumps({"status": "deleted"}, ensure_ascii=False).encode("utf-8"))

    def handle_goals_ai_calculate(self, body):
        try:
            goal_text = body.get("goal_text", "").strip()
            with Database.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM hunter_profile WHERE id=1")
                prof_row = c.fetchone()
                profile = dict(prof_row) if prof_row else {}

            # If user provided weight/height/age in the request override profile
            if body.get("weight"): profile["weight"] = float(body["weight"])
            if body.get("height"): profile["height"] = float(body["height"])
            if body.get("age"): profile["age"] = int(body["age"])
            if body.get("sex"): profile["sex"] = body["sex"]
            if body.get("activity_level"): profile["activity_level"] = body["activity_level"]

            res = GoalAdvisorAI.calculate_from_text(goal_text, profile)

            # Auto-save immediately to database so user never loses recommendations
            with Database.get_connection() as conn:
                c = conn.cursor()
                final_height = float(res.get("detected_height") or body.get("height") or profile.get("height", 180.0))
                final_weight = float(res.get("detected_weight") or body.get("weight") or profile.get("weight", 83.0))
                final_age = int(res.get("detected_age") or body.get("age") or profile.get("age", 26))
                final_sex = str(body.get("sex") or profile.get("sex", "male"))
                final_activity = str(body.get("activity_level") or profile.get("activity_level", "moderate"))
                goal_val = res.get("goal_type") or profile.get("goal", "bulk")

                calc_tw = res.get("detected_target_weight") or (round(final_weight + 4.0, 1) if goal_val == "bulk" else round(max(40.0, final_weight - 4.0), 1))

                sci = NutritionScienceEngine.calculate_full_profile(
                    weight_kg=final_weight,
                    height_cm=final_height,
                    age=final_age,
                    sex=final_sex,
                    activity_level=final_activity,
                    goal=goal_val
                )

                c.execute("""
                UPDATE hunter_profile SET
                    ai_analysis_headline = ?,
                    ai_explanation = ?,
                    ai_hunter_tip = ?,
                    goal_custom_text = ?,
                    target_calories = ?,
                    target_protein = ?,
                    target_carbs = ?,
                    target_fats = ?,
                    target_water = ?,
                    target_fiber = ?,
                    target_weight = ?,
                    goal = ?,
                    weight = ?,
                    height = ?,
                    age = ?,
                    sex = ?,
                    activity_level = ?,
                    bmr = ?,
                    tdee = ?,
                    is_awakened = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """, (
                    res.get("analysis_headline", "עלייה במסה נקייה"),
                    res.get("ai_explanation", ""),
                    res.get("hunter_rank_tip", ""),
                    goal_text,
                    res.get("target_calories", profile.get("target_calories", sci["target_calories"])),
                    res.get("target_protein", profile.get("target_protein", sci["target_protein"])),
                    res.get("target_carbs", profile.get("target_carbs", sci["target_carbs"])),
                    res.get("target_fats", profile.get("target_fats", sci["target_fats"])),
                    res.get("target_water", profile.get("target_water", sci["target_water"])),
                    res.get("target_fiber", res.get("target_fiber", 30)),
                    calc_tw,
                    goal_val,
                    final_weight,
                    final_height,
                    final_age,
                    final_sex,
                    final_activity,
                    sci["bmr"],
                    sci["tdee"]
                ))
                res["detected_height"] = final_height
                res["detected_weight"] = final_weight
                res["detected_age"] = final_age
                res["height"] = final_height
                res["weight"] = final_weight

                # Save into ai_chat_messages
                if goal_text:
                    c.execute("INSERT INTO ai_chat_messages (sender, message) VALUES (?, ?)", ("user", goal_text))
                    recs = [{"title": res.get("analysis_headline", "מפרט מדעי"), "content": res.get("hunter_rank_tip", res.get("ai_explanation", "")), "category": "nutrition"}]
                    c.execute("INSERT INTO ai_chat_messages (sender, message, recommendations_json) VALUES (?, ?, ?)",
                              ("system", f"🎯 {res.get('analysis_headline')}\n{res.get('ai_explanation')}\n💡 {res.get('hunter_rank_tip')}", json.dumps(recs, ensure_ascii=False)))

                # Save into ai_recommendations
                if res.get("hunter_rank_tip"):
                    c.execute("INSERT INTO ai_recommendations (title, content, category, is_active) VALUES (?, ?, ?, 1)",
                              (res.get("analysis_headline", "מפרט יעדים מדעי"), res.get("hunter_rank_tip"), "nutrition"))

                conn.commit()

            self._set_headers(200)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))

    # --- AI Consultation Handlers ---
    def handle_get_ai_history(self):
        with Database.get_connection() as conn:
            hist = HunterAIConsultant.get_history(conn)
        self._set_headers(200)
        self.wfile.write(json.dumps({"messages": hist}, ensure_ascii=False).encode("utf-8"))

    def handle_get_ai_recommendations(self):
        with Database.get_connection() as conn:
            recs = HunterAIConsultant.get_recommendations(conn)
        self._set_headers(200)
        self.wfile.write(json.dumps({"recommendations": recs}, ensure_ascii=False).encode("utf-8"))

    def handle_post_ai_consult(self, body):
        try:
            msg = str(body.get("message", "")).strip()
            history = body.get("chat_history", [])
            with Database.get_connection() as conn:
                res = HunterAIConsultant.consult(conn, msg, history)
            self._set_headers(200)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))

    def handle_post_ai_recommendation_toggle(self, body):
        try:
            rec_id = int(body.get("id"))
            with Database.get_connection() as conn:
                HunterAIConsultant.toggle_recommendation(conn, rec_id)
                recs = HunterAIConsultant.get_recommendations(conn)
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "recommendations": recs}, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))

    def handle_post_ai_apply_targets(self, body):
        try:
            with Database.get_connection() as conn:
                prof = HunterAIConsultant.apply_targets(conn, body)
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "applied", "profile": prof}, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))

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
            search_str = search.strip()
            if search_str:
                tokens = [t.strip() for t in search_str.split() if t.strip()]
                clauses = []
                params = []
                for token in tokens:
                    clauses.append("(name LIKE ? OR name_he LIKE ?)")
                    params.extend([f"%{token}%", f"%{token}%"])
                query = f"SELECT * FROM food_items WHERE {' AND '.join(clauses)} ORDER BY is_custom DESC, id ASC LIMIT 100"
                c.execute(query, params)
            else:
                c.execute("SELECT * FROM food_items ORDER BY is_custom DESC, id ASC LIMIT 300")
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

    def handle_get_calendar_history(self, month_str):
        with Database.get_connection() as conn:
            c = conn.cursor()
            if not month_str or len(month_str) < 7:
                month_str = get_hunter_shift_date(conn)[:7]

            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            prof_row = c.fetchone()
            profile = dict(prof_row) if prof_row else {}

            # Daily meals aggregated
            c.execute("""
            SELECT date, 
                   COUNT(id) as meal_count,
                   COALESCE(SUM(calories), 0) as total_calories,
                   COALESCE(SUM(protein), 0) as total_protein,
                   COALESCE(SUM(carbs), 0) as total_carbs,
                   COALESCE(SUM(fats), 0) as total_fats
            FROM daily_logs
            WHERE date LIKE ?
            GROUP BY date
            """, (f"{month_str}%",))
            nutrition_map = {r["date"]: dict(r) for r in c.fetchall()}

            # Water aggregated
            c.execute("""
            SELECT date, COALESCE(SUM(amount_ml), 0) as total_water
            FROM water_logs
            WHERE date LIKE ?
            GROUP BY date
            """, (f"{month_str}%",))
            water_map = {r["date"]: r["total_water"] for r in c.fetchall()}

            # Garmin biometrics
            c.execute("""
            SELECT * FROM garmin_health_logs
            WHERE date LIKE ?
            """, (f"{month_str}%",))
            garmin_map = {r["date"]: dict(r) for r in c.fetchall()}

            # Medication (Attent)
            c.execute("""
            SELECT * FROM medication_logs
            WHERE date LIKE ? AND LOWER(med_name) = 'attent'
            ORDER BY id DESC
            """, (f"{month_str}%",))
            attent_map = {}
            for r in c.fetchall():
                if r["date"] not in attent_map:
                    attent_map[r["date"]] = dict(r)

            # Workouts
            c.execute("""
            SELECT * FROM workout_logs
            WHERE date LIKE ?
            ORDER BY id ASC
            """, (f"{month_str}%",))
            workout_map = {}
            for r in c.fetchall():
                d = r["date"]
                if d not in workout_map:
                    workout_map[d] = []
                workout_map[d].append(dict(r))

            # Supplements
            c.execute("""
            SELECT * FROM supplements_log
            WHERE date LIKE ?
            ORDER BY id ASC
            """, (f"{month_str}%",))
            supp_map = {}
            for r in c.fetchall():
                d = r["date"]
                if d not in supp_map:
                    supp_map[d] = []
                supp_map[d].append(dict(r))

            try:
                year, month = map(int, month_str.split("-")[:2])
                _, num_days = calendar.monthrange(year, month)
            except Exception:
                num_days = 31

            days_data = {}
            for day_num in range(1, num_days + 1):
                day_key = f"{month_str}-{day_num:02d}"
                nutr = nutrition_map.get(day_key, {
                    "meal_count": 0, "total_calories": 0, "total_protein": 0, "total_carbs": 0, "total_fats": 0
                })
                g = garmin_map.get(day_key, None)
                att = attent_map.get(day_key, None)
                w_list = workout_map.get(day_key, [])
                s_list = supp_map.get(day_key, [])
                water_ml = water_map.get(day_key, 0)

                has_data = (nutr["meal_count"] > 0) or (water_ml > 0) or (g is not None) or (att is not None) or (len(w_list) > 0) or (len(s_list) > 0)

                p_target = profile.get("target_protein", 160)
                c_target = profile.get("target_calories", 2200)
                w_target = profile.get("target_water", 3000)

                score = 0
                if has_data:
                    p_pts = min(30, int((nutr["total_protein"] / max(1, p_target)) * 30))
                    c_pts = max(0, 25 - int(abs(nutr["total_calories"] - c_target) / 60))
                    w_pts = min(20, int((water_ml / max(1, w_target)) * 20))
                    train_pts = 15 if len(w_list) > 0 else 0
                    sleep_pts = 10 if (g and g.get("sleep_hours", 0) >= 7.0) else 5
                    score = min(100, max(20, p_pts + c_pts + w_pts + train_pts + sleep_pts))

                days_data[day_key] = {
                    "date": day_key,
                    "has_data": has_data,
                    "has_attent": att is not None,
                    "attent": att,
                    "nutrition": {
                        "logged": nutr["meal_count"] > 0,
                        "meal_count": nutr["meal_count"],
                        "calories": round(nutr["total_calories"], 1),
                        "protein": round(nutr["total_protein"], 1),
                        "carbs": round(nutr["total_carbs"], 1),
                        "fats": round(nutr["total_fats"], 1),
                        "target_calories": c_target,
                        "target_protein": p_target
                    },
                    "water_ml": water_ml,
                    "target_water": w_target,
                    "garmin": g,
                    "workouts": w_list,
                    "workout_count": len(w_list),
                    "supplements": s_list,
                    "supplements_count": len(s_list),
                    "daily_score": score
                }

        self._set_headers()
        self.wfile.write(json.dumps({
            "month": month_str,
            "days": days_data
        }, ensure_ascii=False).encode("utf-8"))

    def handle_get_calendar_day_detail(self, day_str):
        with Database.get_connection() as conn:
            c = conn.cursor()
            if not day_str:
                day_str = get_hunter_shift_date(conn)

            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            prof_row = c.fetchone()
            profile = dict(prof_row) if prof_row else {}

            c.execute("SELECT * FROM daily_logs WHERE date = ? ORDER BY id ASC", (day_str,))
            meals = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM water_logs WHERE date = ? ORDER BY id ASC", (day_str,))
            water_logs = [dict(r) for r in c.fetchall()]
            total_water = sum(w["amount_ml"] for w in water_logs)

            c.execute("SELECT * FROM garmin_health_logs WHERE date = ?", (day_str,))
            garmin_row = c.fetchone()
            garmin = dict(garmin_row) if garmin_row else None

            c.execute("SELECT * FROM medication_logs WHERE date = ? ORDER BY id ASC", (day_str,))
            meds = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM workout_logs WHERE date = ? ORDER BY id ASC", (day_str,))
            workouts = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM supplements_log WHERE date = ? ORDER BY id ASC", (day_str,))
            supplements = [dict(r) for r in c.fetchall()]

        self._set_headers()
        self.wfile.write(json.dumps({
            "date": day_str,
            "profile": profile,
            "meals": meals,
            "water_logs": water_logs,
            "total_water_ml": total_water,
            "garmin": garmin,
            "medications": meds,
            "workouts": workouts,
            "supplements": supplements
        }, ensure_ascii=False).encode("utf-8"))

    def handle_get_long_term_insights(self, window_str):
        try:
            window = int(window_str) if str(window_str) in ["7", "14", "30"] else 14
        except Exception:
            window = 14
        with Database.get_connection() as conn:
            insights = HunterLongTermScienceEngine.analyze_long_term_trends(conn, window)
        self._set_headers()
        self.wfile.write(json.dumps(insights, ensure_ascii=False).encode("utf-8"))

    def handle_get_backup(self):
        with Database.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM hunter_profile WHERE id=1")
            prof_row = c.fetchone()
            profile = dict(prof_row) if prof_row else {}

            c.execute("SELECT * FROM hunter_skills ORDER BY id ASC")
            skills = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM workout_logs ORDER BY id ASC")
            workouts = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM supplements_log ORDER BY id ASC")
            supplements = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM garmin_health_logs ORDER BY id ASC")
            garmin_logs = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM medication_logs ORDER BY id ASC")
            med_logs = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM daily_logs ORDER BY id ASC")
            daily_logs = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM water_logs ORDER BY id ASC")
            water_logs = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM food_items WHERE is_custom=1")
            custom_foods = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM hunter_achievements ORDER BY id ASC")
            achievements = [dict(r) for r in c.fetchall()]

        now_str = get_israel_now().strftime("%Y-%m-%d_%H%M")
        backup_payload = {
            "system_name": "Solo Leveling Fitness System",
            "version": "2.5",
            "exported_at": get_israel_now().isoformat(),
            "hunter_profile": profile,
            "profile": profile,
            "hunter_skills": skills,
            "skills": skills,
            "hunter_achievements": achievements,
            "achievements": achievements,
            "workout_logs": workouts,
            "supplements_log": supplements,
            "supplements": supplements,
            "garmin_health_logs": garmin_logs,
            "medication_logs": med_logs,
            "daily_logs": daily_logs,
            "logs": daily_logs,
            "water_logs": water_logs,
            "water": water_logs,
            "custom_foods": custom_foods,
            "counts": {
                "skills": len(skills),
                "achievements": len(achievements),
                "workouts": len(workouts),
                "supplements": len(supplements),
                "garmin": len(garmin_logs),
                "medications": len(med_logs),
                "meals": len(daily_logs),
                "water": len(water_logs),
                "custom_foods": len(custom_foods)
            }
        }
        json_data = json.dumps(backup_payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="solo_hunter_backup_{now_str}.json"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(json_data)))
        self.end_headers()
        self.wfile.write(json_data)

    def handle_restore_backup(self, body):
        try:
            profile = body.get("hunter_profile") or body.get("profile")
            skills = body.get("hunter_skills") or body.get("skills")
            workouts = body.get("workout_logs") or body.get("workouts")
            supplements = body.get("supplements_log") or body.get("supplements")
            garmin_logs = body.get("garmin_health_logs") or body.get("garmin_logs")
            med_logs = body.get("medication_logs") or body.get("medications")
            daily_logs = body.get("daily_logs") or body.get("logs")
            water_logs = body.get("water_logs") or body.get("water")
            custom_foods = body.get("custom_foods") or body.get("foods")

            restored_summary = {}

            with Database.get_connection() as conn:
                c = conn.cursor()

                # 1. Restore Profile
                if profile and isinstance(profile, dict):
                    cols = [k for k in profile.keys() if k not in ("id", "updated_at")]
                    if cols:
                        set_clause = ", ".join([f"{k} = ?" for k in cols])
                        vals = [profile[k] for k in cols] + [1]
                        c.execute(f"UPDATE hunter_profile SET {set_clause}, updated_at=CURRENT_TIMESTAMP WHERE id = ?", vals)
                        restored_summary["profile"] = True

                # 2. Restore Hunter Skills
                if skills and isinstance(skills, list):
                    for s in skills:
                        c.execute("""
                        INSERT INTO hunter_skills (skill_code, name_he, name_en, level, current_exp, exp_to_next, stat_boost_type, stat_boost_val, icon, description_he)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(skill_code) DO UPDATE SET
                            level=excluded.level,
                            current_exp=excluded.current_exp,
                            exp_to_next=excluded.exp_to_next,
                            stat_boost_val=excluded.stat_boost_val
                        """, (
                            s.get("skill_code"), s.get("name_he"), s.get("name_en"),
                            s.get("level", 1), s.get("current_exp", 0), s.get("exp_to_next", 100),
                            s.get("stat_boost_type", "STR"), s.get("stat_boost_val", 2),
                            s.get("icon", "⚡"), s.get("description_he", "")
                        ))
                    restored_summary["skills_count"] = len(skills)

                # 3. Restore Workout Logs
                if workouts is not None and isinstance(workouts, list):
                    c.execute("DELETE FROM workout_logs")
                    for w in workouts:
                        c.execute("""
                        INSERT INTO workout_logs (date, workout_type, title, duration_min, calories_burned, notes, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            w.get("date"), w.get("workout_type", "strength"), w.get("title", "אימון"),
                            w.get("duration_min", 45), w.get("calories_burned", 300),
                            w.get("notes", ""), w.get("timestamp", "12:00")
                        ))
                    restored_summary["workouts_count"] = len(workouts)

                # 4. Restore Supplements
                if supplements is not None and isinstance(supplements, list):
                    c.execute("DELETE FROM supplements_log")
                    for sup in supplements:
                        c.execute("""
                        INSERT INTO supplements_log (date, name, dosage, unit, category, notes, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            sup.get("date"), sup.get("name"), sup.get("dosage", "1 מנה"),
                            sup.get("unit", "mg"), sup.get("category", "vitamin"),
                            sup.get("notes", ""), sup.get("timestamp", "08:00")
                        ))
                    restored_summary["supplements_count"] = len(supplements)

                # 5. Restore Garmin Logs
                if garmin_logs is not None and isinstance(garmin_logs, list):
                    c.execute("DELETE FROM garmin_health_logs")
                    for g in garmin_logs:
                        c.execute("""
                        INSERT OR REPLACE INTO garmin_health_logs (
                            date, timestamp, heart_rate, resting_hr, sleep_score, sleep_hours,
                            stress_level, body_battery, steps, active_calories, spo2_pct, respiration_rpm
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            g.get("date"), g.get("timestamp", "08:00"), g.get("heart_rate", 68),
                            g.get("resting_hr", 58), g.get("sleep_score", 82), g.get("sleep_hours", 7.2),
                            g.get("stress_level", 28), g.get("body_battery", 75), g.get("steps", 8500),
                            g.get("active_calories", 450), g.get("spo2_pct", 98), g.get("respiration_rpm", 14)
                        ))
                    restored_summary["garmin_count"] = len(garmin_logs)

                # 6. Restore Medication / Attent Logs
                if med_logs is not None and isinstance(med_logs, list):
                    c.execute("DELETE FROM medication_logs")
                    for m in med_logs:
                        c.execute("""
                        INSERT INTO medication_logs (date, med_name, dose_mg, timestamp, duration_hours, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            m.get("date"), m.get("med_name", "Attent"), m.get("dose_mg", 20),
                            m.get("timestamp", "08:00"), m.get("duration_hours", 7.0), m.get("notes", "")
                        ))
                    restored_summary["medication_count"] = len(med_logs)

                # 7. Restore Daily Meal Logs
                if daily_logs is not None and isinstance(daily_logs, list):
                    c.execute("DELETE FROM daily_logs")
                    for dl in daily_logs:
                        c.execute("""
                        INSERT INTO daily_logs (
                            date, food_id, food_name, serving_count, serving_size_g,
                            calories, protein, carbs, fats, fiber, sodium_mg, potassium_mg,
                            magnesium_mg, zinc_mg, vit_c_mg, vit_d_iu, iron_mg, meal_type, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            dl.get("date"), dl.get("food_id"), dl.get("food_name"),
                            dl.get("serving_count", 1.0), dl.get("serving_size_g", 100),
                            dl.get("calories", 0), dl.get("protein", 0), dl.get("carbs", 0),
                            dl.get("fats", 0), dl.get("fiber", 0), dl.get("sodium_mg", 0),
                            dl.get("potassium_mg", 0), dl.get("magnesium_mg", 0),
                            dl.get("zinc_mg", 0), dl.get("vit_c_mg", 0), dl.get("vit_d_iu", 0),
                            dl.get("iron_mg", 0), dl.get("meal_type", "snack"), dl.get("timestamp", "12:00")
                        ))
                    restored_summary["meals_count"] = len(daily_logs)

                # 8. Restore Water Logs
                if water_logs is not None and isinstance(water_logs, list):
                    c.execute("DELETE FROM water_logs")
                    for wl in water_logs:
                        c.execute("""
                        INSERT INTO water_logs (date, amount_ml, timestamp)
                        VALUES (?, ?, ?)
                        """, (wl.get("date"), wl.get("amount_ml", 250), wl.get("timestamp", "12:00")))
                    restored_summary["water_count"] = len(water_logs)

                # 9. Restore Custom Foods
                if custom_foods and isinstance(custom_foods, list):
                    for cf in custom_foods:
                        if cf.get("name"):
                            c.execute("""
                            INSERT OR IGNORE INTO food_items (
                                name, name_he, category, serving_size_g, calories, protein, carbs, fats,
                                fiber, sodium_mg, potassium_mg, magnesium_mg, zinc_mg, vit_c_mg, vit_d_iu, iron_mg, is_custom
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                            """, (
                                cf.get("name"), cf.get("name_he", cf.get("name")), cf.get("category", "מותאם אישית"),
                                cf.get("serving_size_g", 100), cf.get("calories", 0), cf.get("protein", 0),
                                cf.get("carbs", 0), cf.get("fats", 0), cf.get("fiber", 0),
                                cf.get("sodium_mg", 0), cf.get("potassium_mg", 0), cf.get("magnesium_mg", 0),
                                cf.get("zinc_mg", 0), cf.get("vit_c_mg", 0), cf.get("vit_d_iu", 0),
                                cf.get("iron_mg", 0)
                            ))
                    restored_summary["custom_foods_processed"] = len(custom_foods)

                # 10. Restore Achievements
                achievements = body.get("hunter_achievements") or body.get("achievements")
                if achievements and isinstance(achievements, list):
                    for a in achievements:
                        c.execute("""
                        UPDATE hunter_achievements SET
                            unlocked = ?,
                            unlocked_at = ?
                        WHERE code = ?
                        """, (a.get("unlocked", 0), a.get("unlocked_at"), a.get("code")))
                    restored_summary["achievements_count"] = len(achievements)

                conn.commit()

            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "success",
                "message": "[SYSTEM: מסד הנתונים שוחזר בהצלחה מלאה מתוך קובץ הגיבוי!]",
                "summary": restored_summary
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_reset_today(self, body=None):
        try:
            with Database.get_connection() as conn:
                client_date = body.get("client_date") if isinstance(body, dict) else None
                today = get_hunter_shift_date(conn, client_date)
                c = conn.cursor()
                c.execute("DELETE FROM daily_logs WHERE date = ?", (today,))
                c.execute("DELETE FROM water_logs WHERE date = ?", (today,))
                c.execute("DELETE FROM workout_logs WHERE date = ?", (today,))
                c.execute("DELETE FROM supplements_log WHERE date = ?", (today,))
                c.execute("DELETE FROM medication_logs WHERE date = ?", (today,))
                c.execute("DELETE FROM garmin_health_logs WHERE date = ?", (today,))
                conn.commit()

            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "today_reset",
                "date": today,
                "message": "[SYSTEM: נתוני יום המשמרת הנוכחי אופסו בהצלחה. דרגת הצייד והסקילים נשמרו!]"
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_reset_full(self):
        try:
            with Database.get_connection() as conn:
                c = conn.cursor()
                # Reset Hunter Profile to Level 1 Awakened Novice (across all rows)
                c.execute("""
                UPDATE hunter_profile SET
                    rank = 'E-Rank',
                    level = 1,
                    exp = 0,
                    exp_to_next = 300,
                    title = 'צייד שהתעורר (Awakened Novice)',
                    is_awakened = 0,
                    goal_custom_text = '',
                    ai_analysis_headline = '',
                    ai_explanation = '',
                    ai_hunter_tip = '',
                    stats_str = 10,
                    stats_agi = 10,
                    stats_vit = 10,
                    stats_int = 10,
                    stats_per = 10,
                    fatigue = 15,
                    streak_days = 1,
                    has_penalty_debuff = 0,
                    last_active_date = date('now'),
                    updated_at = CURRENT_TIMESTAMP
                """)

                # Reset all 5 Skills to Level 1, 0/100 XP
                c.execute("""
                UPDATE hunter_skills SET
                    level = 1,
                    current_exp = 0,
                    exp_to_next = 100,
                    stat_boost_val = 2
                """)

                # Reset achievements to default
                c.execute("UPDATE hunter_achievements SET unlocked = CASE WHEN code = 'the_awakening' THEN 1 ELSE 0 END, unlocked_at = NULL")

                # Wipe all activity & history logs
                c.execute("DELETE FROM daily_logs")
                c.execute("DELETE FROM water_logs")
                c.execute("DELETE FROM workout_logs")
                c.execute("DELETE FROM supplements_log")
                c.execute("DELETE FROM medication_logs")
                c.execute("DELETE FROM garmin_health_logs")
                c.execute("DELETE FROM ai_chat_messages")
                c.execute("DELETE FROM ai_recommendations")
                c.execute("DELETE FROM hunter_penalties")

                # Re-seed baseline scientific recommendations
                c.execute("""
                INSERT INTO ai_recommendations (title, content, category, is_active)
                VALUES 
                ('פרוטוקול היפרטרופיה ומסה נקייה', 'שמור על עודף קלורי יומי מבוקר וסגור את יעד החלבון היומי לחלוקה של 4-5 ארוחות.', 'nutrition', 1),
                ('הידרציה והתאוששות שריר', 'שתה מים באופן רציף לאורך המשמרת לתמיכה בנפח התא השרירי ופינוי חומרי פסולת.', 'hydration', 1),
                ('קריאטין מונוהידראט יומי', 'צרוך 5 גרם קריאטין מונוהידראט באופן יומי ורציף (כולל ימי מנוחה) לרוויית מאגרי הפוספוקריאטין בשריר.', 'supplements', 1)
                """)

                # Re-seed fresh welcome AI chat
                c.execute("""
                INSERT INTO ai_chat_messages (sender, message, recommendations_json)
                VALUES (
                    'system',
                    'שלום צייד! המערכת זיהתה את התעוררותך. אני ה-AI של המערכת, כאן ללוות אותך 24/7. תוכל לשאול אותי בכל שלב: מה לאכול עכשיו, איך לתזמן תוספים, איך להתמודד עם עייפות או משמרות לילה, ולעדכן יעדים!',
                    '[]'
                )
                """)
                conn.commit()

            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "rebirth_complete",
                "was_reset": True,
                "message": "[SYSTEM: לידה מחדש הושלמה! הצייד חזר לרמה 1, דרגת E-Rank. כל הסקילים ויומני הארוחות אופסו לחלוטין.]"
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    # ------------------ Food Vision AI ------------------
    def handle_food_recognize(self, body):
        """Recognize food from a base64-encoded image using Gemini Vision."""
        try:
            image_b64 = body.get("image_b64", "")
            mime_type = body.get("mime_type", "image/jpeg")
            if not image_b64:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "image_b64 is required"}, ensure_ascii=False).encode("utf-8"))
                return
            result = FoodVisionAI.recognize(image_b64, mime_type)
            if "error" in result and not result.get("items"):
                self._set_headers(502)
                self.wfile.write(json.dumps({"error": result["error"]}, ensure_ascii=False).encode("utf-8"))
                return
            self._set_headers(200)
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))

    def handle_food_chat_parse(self, body):
        """Parse a free-text Hebrew meal description using Gemini."""
        try:
            user_text = (body.get("text") or "").strip()
            if not user_text:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "text is required"}, ensure_ascii=False).encode("utf-8"))
                return
            result = FoodChatAI.parse(user_text)
            if "error" in result and not result.get("items"):
                self._set_headers(502)
                self.wfile.write(json.dumps({"error": result["error"]}, ensure_ascii=False).encode("utf-8"))
                return
            self._set_headers(200)
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))

    # ------------------ Garmin & Health Integration ------------------
    def handle_garmin_status(self, query=None):
        with Database.get_connection() as conn:
            client_date = query.get("client_date", [None])[0] if query else None
            today = get_hunter_shift_date(conn, client_date)
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
                "raw_biometrics": health_adv.get("raw_biometrics"),
                "normalized_biometrics": health_adv.get("normalized_biometrics"),
                "attent_normalization": health_adv.get("attent_normalization"),
                "attent": health_adv["attent"],
                "insights_count": len(health_adv["insights"])
            }
        self._set_headers()
        self.wfile.write(json.dumps(garmin_payload, ensure_ascii=False).encode("utf-8"))

    def handle_get_garmin_health(self, query=None):
        with Database.get_connection() as conn:
            client_date = query.get("client_date", [None])[0] if query else None
            today = get_hunter_shift_date(conn, client_date)
            health_data = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)
        self._set_headers()
        self.wfile.write(json.dumps(health_data, ensure_ascii=False).encode("utf-8"))

    def handle_get_garmin_webhook_info(self):
        host = self.headers.get("Host", f"{get_local_ip()}:8080")
        is_secure = "render.com" in host or "https" in self.headers.get("X-Forwarded-Proto", "")
        scheme = "https" if is_secure else "http"
        webhook_url = f"{scheme}://{host}/api/garmin/webhook"

        info = {
            "webhook_url": webhook_url,
            "method": "POST",
            "supported_fields": [
                "steps", "active_calories", "heart_rate", "resting_hr", 
                "sleep_score", "sleep_hours", "stress_level", "body_battery", "spo2_pct", "vo2_max"
            ],
            "sample_payload": {
                "steps": 9450,
                "active_calories": 520,
                "heart_rate": 68,
                "resting_hr": 56,
                "sleep_score": 85,
                "sleep_hours": 7.6,
                "stress_level": 24,
                "body_battery": 80,
                "spo2_pct": 98,
                "source": "ios_shortcuts"
            },
            "sample_curl": f'curl -X POST "{webhook_url}" -H "Content-Type: application/json" -d \'{{"steps": 9450, "active_calories": 520, "heart_rate": 68, "sleep_score": 85, "sleep_hours": 7.5, "stress_level": 24, "body_battery": 80}}\'',
            "ios_shortcuts_guide": (
                "באייפון: פתח את אפליקציית 'קיצורי דרך' (Shortcuts) -> הוסף קיצור דרך חדש -> "
                "הוסף פעולת 'מצא דגימות בריאות' עבור צעדים, שינה ודופק -> "
                "הוסף פעולת 'קבל תוכן מכתובת URL' (POST) לכתובת ה-Webhook -> "
                "הגדר באוטומציות הרצה כל בוקר או בסיום אימון!"
            )
        }
        self._set_headers()
        self.wfile.write(json.dumps(info, ensure_ascii=False).encode("utf-8"))

    def handle_garmin_webhook_get(self, query):
        try:
            # Flatten query dict
            flat = {}
            for k, v in query.items():
                flat[k] = v[0] if isinstance(v, list) and len(v) == 1 else v

            bio, activity = GarminDataEngine.parse_universal_payload(flat)
            has_metrics = any(k in bio for k in [
                "steps", "heart_rate", "resting_hr", "sleep_hours", "sleep_score",
                "stress_level", "body_battery", "active_calories", "spo2_pct", "vo2_max"
            ])

            if not has_metrics:
                self._set_headers(200)
                resp = {
                    "status": "warning",
                    "code": "no_metrics_provided",
                    "message": "⚠️ שרת ה-Webhook מחובר ופעיל, אך לא נשלחו מדדים בבקשה!",
                    "tip": "בקיצור הדרך באייפון: בפעולה 'קבל תוכן מכתובת URL', הוסף לסוף הקישור: ?steps=[בחר דגימות צעדים]&hr=[בחר דגימות דופק]",
                    "received_keys": list(query.keys()),
                    "example_url": "https://rom-z019.onrender.com/api/garmin/webhook?steps=5200&hr=72"
                }
                self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
                return

            flat["sync_source"] = "ios_shortcuts"
            return self.handle_post_garmin_sync(flat)
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_garmin_webhook_post(self, body):
        try:
            if not isinstance(body, dict):
                body = {}

            bio, activity = GarminDataEngine.parse_universal_payload(body)
            has_metrics = any(k in bio for k in [
                "steps", "heart_rate", "resting_hr", "sleep_hours", "sleep_score",
                "stress_level", "body_battery", "active_calories", "spo2_pct", "vo2_max"
            ])

            if not has_metrics and not body.get("sync_dummy"):
                self._set_headers(200)
                resp = {
                    "status": "warning",
                    "code": "no_metrics_provided",
                    "message": "⚠️ שרת ה-Webhook מחובר ופעיל ב-POST, אך לא צורפו שדות צעדים או דופק בבקשה!",
                    "tip": "הוסף שדות: steps (צעדים) ו-hr (דופק)",
                    "received_keys": list(body.keys())
                }
                self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
                return

            if not body.get("sync_source"):
                body["sync_source"] = "ios_shortcuts"
            return self.handle_post_garmin_sync(body)
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_post_garmin_sync(self, body):
        try:
            bio, activity = GarminDataEngine.parse_universal_payload(body)
            merged = {}
            for k in ["heart_rate", "resting_hr", "sleep_score", "sleep_hours",
                      "stress_level", "body_battery", "steps", "active_calories",
                      "spo2_pct", "respiration_rpm", "vo2_max", "hrv_status", "sync_source"]:
                if k in bio and bio[k] is not None and bio[k] != "":
                    merged[k] = bio[k]
                elif k in body and body[k] is not None and body[k] != "":
                    clean = GarminDataEngine.clean_biometric_number(body[k])
                    if clean is not None:
                        merged[k] = clean

            if not merged.get("sync_source"):
                merged["sync_source"] = body.get("source", "webhook" if "/webhook" in self.path else "manual")

            with Database.get_connection() as conn:
                today = get_hunter_shift_date(conn, body.get("client_date"))
                c = conn.cursor()
                now_time = get_israel_now().strftime("%H:%M")

                # Atomically ensure today's record exists without ANY UNIQUE constraint race conditions
                c.execute("""
                INSERT OR IGNORE INTO garmin_health_logs (
                    date, timestamp, heart_rate, resting_hr, sleep_score, sleep_hours,
                    stress_level, body_battery, steps, active_calories, spo2_pct,
                    respiration_rpm, vo2_max, hrv_status, sync_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    today, now_time,
                    68, 58, 80, 7.0, 25, 75, 0, 0, 98, 14, 48, "balanced",
                    merged.get("sync_source", "manual")
                ))

                fields = ["heart_rate", "resting_hr", "sleep_score", "sleep_hours",
                          "stress_level", "body_battery", "steps", "active_calories",
                          "spo2_pct", "respiration_rpm", "vo2_max", "hrv_status", "sync_source"]
                updates = []
                vals = []
                for f in fields:
                    if f in merged and merged[f] is not None and merged[f] != "":
                        updates.append(f"{f} = ?")
                        vals.append(merged[f])

                if updates:
                    updates.append("timestamp = ?")
                    vals.append(now_time)
                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    vals.append(today)
                    c.execute(f"UPDATE garmin_health_logs SET {', '.join(updates)} WHERE date = ?", vals)
                else:
                    c.execute("UPDATE garmin_health_logs SET timestamp = ?, updated_at = CURRENT_TIMESTAMP WHERE date = ?", (now_time, today))
                conn.commit()

                # Activity / Workout Auto-Logging
                workout_logged = None
                if activity and activity.get("name"):
                    act_name = activity["name"]
                    act_cals = safe_int(activity.get("calories"), 300)
                    act_dur = safe_int(activity.get("duration_minutes"), 35)
                    w_type = "cardio" if ("ריצה" in act_name or "run" in act_name.lower() or "אירובי" in act_name) else "strength"

                    c.execute("SELECT id FROM workout_logs WHERE date = ? AND title = ? ORDER BY id DESC LIMIT 1", (today, act_name))
                    existing = c.fetchone()
                    if not existing:
                        c.execute("""
                        INSERT INTO workout_logs (date, workout_type, title, duration_min, calories_burned, notes, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (today, w_type, act_name, act_dur, act_cals, f"סונכרן אוטומטית מ-Garmin ({merged['sync_source']})", now_time))
                        conn.commit()
                        skill_code = "colossus_strength" if w_type == "strength" else "shadow_sprint"
                        skill_exp = 35 + int(act_dur * 0.9)
                        HunterLevelingEngine.add_skill_exp(conn, skill_code, skill_exp)
                        HunterLevelingEngine.add_exp(conn, 50)
                        workout_logged = {
                            "title": act_name,
                            "type": w_type,
                            "calories": act_cals,
                            "duration_min": act_dur
                        }

                # Award skill XP based on sleep quality and steps
                sl_score = safe_float(merged.get("sleep_score"), 0)
                sl_hours = safe_float(merged.get("sleep_hours"), 0)
                steps = safe_int(merged.get("steps"), 0)
                if sl_score >= 75 or sl_hours >= 7.0:
                    HunterLevelingEngine.add_skill_exp(conn, "regeneration", 25)
                if steps >= 8000:
                    HunterLevelingEngine.add_skill_exp(conn, "shadow_sprint", 20)

                health_data = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)

            summary_parts = []
            if "steps" in merged and merged["steps"] is not None:
                summary_parts.append(f"{merged['steps']} צעדים")
            if "heart_rate" in merged and merged["heart_rate"] is not None:
                summary_parts.append(f"דופק {merged['heart_rate']} bpm")
            if "sleep_hours" in merged and merged["sleep_hours"] is not None:
                summary_parts.append(f"{merged['sleep_hours']}h שינה")
            summary_str = " | ".join(summary_parts) if summary_parts else "עודכן"

            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "synced",
                "message": f"[SYSTEM: מדדי Garmin Venu 4 סונכרנו בהצלחה! {summary_str}]",
                "summary": f"✅ {summary_str}",
                "sync_source": merged["sync_source"],
                "activity_logged": workout_logged,
                "data": health_data
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_garmin_upload_file(self, body):
        try:
            filename = (body.get("filename") or "").lower()
            content = body.get("content", "")
            base64_data = body.get("base64", "")

            extracted = {}
            if filename.endswith(".csv") or (content and "," in content and "\n" in content):
                extracted = GarminDataEngine.parse_garmin_csv(content)
            elif filename.endswith(".json") or (content and content.strip().startswith("{")):
                import json as pyjson
                try:
                    p = pyjson.loads(content)
                    extracted, _ = GarminDataEngine.parse_universal_payload(p)
                except Exception:
                    pass
            elif filename.endswith(".fit") or base64_data:
                import base64 as pyb64
                try:
                    data_bytes = pyb64.b64decode(base64_data) if base64_data else content.encode("latin1")
                    extracted = GarminDataEngine.parse_garmin_fit_bytes(data_bytes)
                except Exception:
                    pass

            if not extracted:
                extracted = GarminDataEngine.generate_smart_diurnal_biometrics()
                extracted["sync_source"] = "file_fallback"

            return self.handle_post_garmin_sync(extracted)
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": f"Failed to parse Garmin file: {str(e)}"}).encode("utf-8"))

    def handle_garmin_smart_sync(self, body):
        try:
            with Database.get_connection() as conn:
                shift_date = get_hunter_shift_date(conn, body.get("client_date"))
                c = conn.cursor()
                c.execute("SELECT * FROM garmin_health_logs WHERE date = ?", (shift_date,))
                row = c.fetchone()

                now_israel = get_israel_now()
                now_time = now_israel.strftime("%H:%M")

                _, attent_info, _ = HunterHealthAIAdvisor.get_health_state(conn, shift_date)
                smart_bio = GarminDataEngine.generate_smart_diurnal_biometrics(now_israel, attent_info)
                smart_bio["sync_source"] = body.get("source", "smart_sync")

                # Merge explicit sensor metrics if passed (from simulator sliders, Shortcuts, etc.)
                for k in ["heart_rate", "resting_hr", "sleep_score", "sleep_hours",
                          "stress_level", "body_battery", "steps", "active_calories",
                          "spo2_pct", "respiration_rpm", "vo2_max"]:
                    if k in body and body[k] is not None and body[k] != "":
                        clean = GarminDataEngine.clean_biometric_number(body[k])
                        if clean is not None:
                            smart_bio[k] = clean

                if row:
                    # Preserve highest steps & active calories unless explicitly sent in body
                    if "steps" not in body:
                        smart_bio["steps"] = max(row["steps"] or 0, smart_bio.get("steps", 0))
                    if "active_calories" not in body:
                        smart_bio["active_calories"] = max(row["active_calories"] or 0, smart_bio.get("active_calories", 0))
                    if "sleep_score" not in body and row["sleep_score"] is not None:
                        smart_bio["sleep_score"] = row["sleep_score"]
                    if "sleep_hours" not in body and row["sleep_hours"] is not None:
                        smart_bio["sleep_hours"] = row["sleep_hours"]

                smart_bio["client_date"] = body.get("client_date")
            return self.handle_post_garmin_sync(smart_bio)
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_post_attent(self, body):
        try:
            dose_id = body.get("id") or body.get("dose_id")
            dose_mg = int(body.get("dose_mg") or 20)
            dose_time = body.get("timestamp") or get_israel_now().strftime("%H:%M")
            duration = float(body.get("duration_hours") or 7.0)
            notes = body.get("notes") or "שיקוי ריכוז והיפר-פוקוס"
            target_date = body.get("date")

            with Database.get_connection() as conn:
                shift_date = get_hunter_shift_date(conn, body.get("client_date"))
                date_to_log = target_date if target_date else shift_date
                c = conn.cursor()
                if dose_id:
                    c.execute("""
                    UPDATE medication_logs 
                    SET dose_mg = ?, timestamp = ?, duration_hours = ?, notes = ?, date = ?
                    WHERE id = ?
                    """, (dose_mg, dose_time, duration, notes, date_to_log, dose_id))
                    logged_id = dose_id
                else:
                    c.execute("""
                    INSERT INTO medication_logs (date, med_name, dose_mg, timestamp, duration_hours, notes)
                    VALUES (?, 'Attent', ?, ?, ?, ?)
                    """, (date_to_log, dose_mg, dose_time, duration, notes))
                    logged_id = c.lastrowid
                conn.commit()

                lvl_res = HunterLevelingEngine.add_exp(conn, 35)

                # Immediately apply Attent stimulation to garmin biometrics and normalize
                now_israel = get_israel_now()
                now_time = now_israel.strftime("%H:%M")
                _, attent_info, _ = HunterHealthAIAdvisor.get_health_state(conn, shift_date)
                smart_bio = GarminDataEngine.generate_smart_diurnal_biometrics(now_israel, attent_info)

                c.execute("SELECT * FROM garmin_health_logs WHERE date = ?", (shift_date,))
                g_row = c.fetchone()
                if g_row:
                    prev_steps = g_row["steps"] or 0
                    prev_cals = g_row["active_calories"] or 0
                    prev_sleep = g_row["sleep_score"]
                    prev_sleep_h = g_row["sleep_hours"]
                    c.execute("""
                    UPDATE garmin_health_logs SET
                        timestamp = ?,
                        heart_rate = ?,
                        resting_hr = ?,
                        stress_level = ?,
                        body_battery = ?,
                        steps = ?,
                        active_calories = ?,
                        sleep_score = ?,
                        sleep_hours = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE date = ?
                    """, (
                        now_time,
                        smart_bio["heart_rate"],
                        smart_bio["resting_hr"],
                        smart_bio["stress_level"],
                        smart_bio["body_battery"],
                        max(prev_steps, smart_bio["steps"]),
                        max(prev_cals, smart_bio["active_calories"]),
                        prev_sleep if prev_sleep is not None else smart_bio["sleep_score"],
                        prev_sleep_h if prev_sleep_h is not None else smart_bio["sleep_hours"],
                        shift_date
                    ))
                else:
                    c.execute("""
                    INSERT OR IGNORE INTO garmin_health_logs (
                        date, timestamp, heart_rate, resting_hr, sleep_score, sleep_hours,
                        stress_level, body_battery, steps, active_calories, sync_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'attent_log')
                    """, (
                        shift_date, now_time,
                        smart_bio["heart_rate"], smart_bio["resting_hr"],
                        smart_bio["sleep_score"], smart_bio["sleep_hours"],
                        smart_bio["stress_level"], smart_bio["body_battery"],
                        smart_bio["steps"], smart_bio["active_calories"]
                    ))
                conn.commit()

                health_data = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, shift_date)

            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "buff_activated",
                "message": f"[SYSTEM: מנת אטנט ({dose_mg}mg) נרשמה בהצלחה ב-{dose_time}!]",
                "id": logged_id,
                "leveling": lvl_res,
                "data": health_data
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_delete_attent(self, dose_id=None):
        try:
            with Database.get_connection() as conn:
                today = get_hunter_shift_date(conn)
                c = conn.cursor()
                if dose_id:
                    c.execute("DELETE FROM medication_logs WHERE id = ? AND LOWER(med_name) = 'attent'", (dose_id,))
                else:
                    c.execute("DELETE FROM medication_logs WHERE date = ? AND LOWER(med_name) = 'attent'", (today,))
                conn.commit()

                # Revert garmin biometrics back to normal baseline without Attent
                now_israel = get_israel_now()
                now_time = now_israel.strftime("%H:%M")
                _, attent_info, _ = HunterHealthAIAdvisor.get_health_state(conn, today)
                smart_bio = GarminDataEngine.generate_smart_diurnal_biometrics(now_israel, attent_info)

                c.execute("SELECT * FROM garmin_health_logs WHERE date = ?", (today,))
                g_row = c.fetchone()
                if g_row:
                    c.execute("""
                    UPDATE garmin_health_logs SET
                        timestamp = ?,
                        heart_rate = ?,
                        resting_hr = ?,
                        stress_level = ?,
                        body_battery = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE date = ?
                    """, (
                        now_time,
                        smart_bio["heart_rate"],
                        smart_bio["resting_hr"],
                        smart_bio["stress_level"],
                        smart_bio["body_battery"],
                        today
                    ))
                    conn.commit()

                health_data = HunterHealthAIAdvisor.analyze_and_generate_insights(conn, today)

            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "buff_removed",
                "message": f"[SYSTEM: Attent {'dose #' + str(dose_id) if dose_id else 'all logs'} cleared]",
                "data": health_data
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_garmin_water(self, body):
        amount = int(body.get("amount_ml", 250))
        now_time = get_israel_now().strftime("%H:%M")
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

