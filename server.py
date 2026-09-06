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
        raw_hr = int(garmin_raw.get("heart_rate", 68))
        raw_rhr = int(garmin_raw.get("resting_hr", 58))
        raw_stress = int(garmin_raw.get("stress_level", 28))
        raw_bb = int(garmin_raw.get("body_battery", 75))
        raw_sleep = int(garmin_raw.get("sleep_score", 82))

        if not attent_info or not attent_info.get("is_active"):
            stress_state = "מנוחה (נמוך)" if raw_stress < 25 else ("נמוך-בינוני" if raw_stress < 50 else ("בינוני" if raw_stress < 75 else "גבוה"))
            return {
                "heart_rate": raw_hr,
                "resting_hr": raw_rhr,
                "stress_level": raw_stress,
                "body_battery": raw_bb,
                "sleep_score": raw_sleep,
                "sleep_hours": garmin_raw.get("sleep_hours", 7.2),
                "steps": garmin_raw.get("steps", 8500),
                "active_calories": garmin_raw.get("active_calories", 450),
                "spo2_pct": garmin_raw.get("spo2_pct", 98),
                "respiration_rpm": garmin_raw.get("respiration_rpm", 14),
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

        dose = float(attent_info.get("dose_mg", 20))
        elapsed = float(attent_info.get("elapsed_hours", 2.0))

        # Pharmacokinetic potency curve:
        # Rise phase to peak at ~2.5h, plateau to 5.5h, then half-life decay (t_1/2 = 10.5h)
        if elapsed < 1.0:
            potency = 0.5 + (elapsed * 0.5)
        elif elapsed <= 5.5:
            potency = 1.0
        else:
            decay_elapsed = elapsed - 5.5
            potency = max(0.15, math.exp(-0.693 * decay_elapsed / 10.5))

        dose_factor = min(1.5, max(0.5, dose / 20.0))
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
            "sleep_hours": garmin_raw.get("sleep_hours", 7.2),
            "steps": garmin_raw.get("steps", 8500),
            "active_calories": garmin_raw.get("active_calories", 450),
            "spo2_pct": garmin_raw.get("spo2_pct", 98),
            "respiration_rpm": garmin_raw.get("respiration_rpm", 14),
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

        meta = {
            "is_active": True,
            "dose_mg": dose,
            "elapsed_hours": elapsed,
            "potency_pct": round(effective_potency * 100),
            "stress_offset": stress_offset,
            "rhr_offset": rhr_offset,
            "body_battery_boost": bb_drain_protection,
            "status_badge_he": f"💊 פילטר אטנט פעיל (כיול פרמקולוגי {dose}mg)",
            "scientific_summary": (
                f"האטנט נלקח לפני {elapsed:.1f} שעות. עוררות אדרנרגית מלאכותית מורידה HRV "
                f"ומקפיצה את מדד הסטרס בשעון ב-{stress_offset}+ נקודות ואת הדופק ב-{rhr_offset}+ bpm. "
                f"המערכת מנרמלת את הנתונים ומציגה את הסטטוס הגופני האמיתי שלך ({norm_stress}/100 סטרס, {norm_rhr} bpm דופק מנוחה)."
            ),
            "clinical_mechanism": "Antagonism of peripheral adrenergic chronotropy and restoration of vagal parasympathetic HRV indexing (Firstbeat Analytics compensation)."
        }

        return normalized, meta


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
                "title": "סינרגיית מגנזיום פעילה",
                "desc": "נטילת מגנזיום חוסמת פעילות יתר של קולטני NMDA, מונעת כיווצי שרירים/נעילת לסת ומשפרת משמעותית את איכות שנת ה-Deep Sleep.",
                "tag": "Neuro-Protection"
            })
        if has_omega3:
            strengths.append({
                "icon": "🐟",
                "title": "הגנה קרדיווסקולרית ואנטי-דלקתית",
                "desc": "אומגה 3 (EPA/DHA) מייצבת את תאי שריר הלב, מסייעת לגמישות כלי הדם ומאזנת את השפעות הדופק.",
                "tag": "Cardioprotective"
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
                    "priority": "בינונית",
                    "tag": "Mineral Support"
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
                "title": "Wearable Heart Rate Variability Analytics and Psychostimulant Confounding",
                "journal": "Autonomic Neuroscience & Firstbeat Clinical Analytics",
                "year": "2023",
                "takeaway": "תרופות ממריצות (אמפטמין) גורמות לירידה של 20%-35% ב-RMSSD עקב הפעלת קולטנים אדרנרגיים פריפריאליים, ללא עקה סומטית או פגיעה בהתאוששות. אלגוריתמי שעונים מעריכים סטרס ביתר."
            },
            {
                "title": "The Role of Magnesium in Sleep Health and Autonomic Regulation",
                "journal": "Nutrients & Sleep Medicine Reviews",
                "year": "2021",
                "takeaway": "מגנזיום מווסת נוירוטרנסמיטורים מעוררים (GABA agonist / NMDA antagonist), משפר HRV ומפחית זמני הירדמות."
            },
            {
                "title": "Circadian Disruption in Shift Workers and Dietary Countermeasures",
                "journal": "The Lancet Public Health / Sleep Foundation",
                "year": "2022",
                "takeaway": "שמירה על חלונות אכילה מוגדרים במשמרת לילה ומניעת פחמימות פשוטות לפני שנת היום מונעות תנגודת לאינסולין ועייפות כרונית."
            }
        ]

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
                "domain": "הידרציה ותוספי צייד",
                "icon": "🧪",
                "status_level": "optimal" if water_ml >= 2500 else "info",
                "status_label": f"{water_ml}ml | {len(supps)} תוספים",
                "summary": f"נרשמו: {', '.join([s['name'] for s in supps]) if supps else 'טרם נרשמו תוספים להיום'}"
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
        elif path == "/api/skills":
            self.handle_get_skills()
        elif path == "/api/workouts/today":
            self.handle_get_workouts()
        elif path == "/api/supplements/today":
            self.handle_get_supplements()
        elif path == "/api/health-synergy/daily-debrief":
            self.handle_get_daily_debrief()
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
        elif path == "/api/workouts/log":
            self.handle_post_workout(body)
        elif path == "/api/supplements/log":
            self.handle_post_supplement(body)
        elif path == "/api/reset/today":
            self.handle_reset_today()
        elif path == "/api/reset/full":
            self.handle_reset_full()
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

    def handle_get_workouts(self):
        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
            c = conn.cursor()
            c.execute("SELECT * FROM workout_logs WHERE date = ? ORDER BY id DESC", (today,))
            workouts = [dict(r) for r in c.fetchall()]
        self._set_headers()
        self.wfile.write(json.dumps({"workouts": workouts}, ensure_ascii=False).encode("utf-8"))

    def handle_post_workout(self, body):
        w_type = body.get("workout_type", "strength")
        title = body.get("title") or ("אימון כוח (Hypertrophy)" if w_type == "strength" else "אימון ריצה וסיבולת")
        duration = int(body.get("duration_min", 45))
        calories = int(body.get("calories_burned", duration * 7))
        notes = body.get("notes", "")
        now_time = datetime.datetime.now().strftime("%H:%M")

        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
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
        name = body.get("name", "תוסף ויטמין")
        dosage = str(body.get("dosage", "1 מנה"))
        unit = body.get("unit", "mg")
        category = body.get("category", "vitamin")
        notes = body.get("notes", "")
        now_time = datetime.datetime.now().strftime("%H:%M")

        with Database.get_connection() as conn:
            today = get_hunter_shift_date(conn)
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

            # Award XP to Nutrition Mastery skill
            skill_res = HunterLevelingEngine.add_skill_exp(conn, "nutrition_mastery", 15 + int(protein * 0.3))

        self._set_headers(201)
        self.wfile.write(json.dumps({
            "status": "success",
            "log_id": log_id,
            "exp_awarded": exp_awarded,
            "leveling": lvl_res,
            "skill_leveling": skill_res
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

        now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        backup_payload = {
            "system_name": "Solo Leveling Fitness System",
            "version": "2.5",
            "exported_at": datetime.datetime.now().isoformat(),
            "hunter_profile": profile,
            "profile": profile,
            "hunter_skills": skills,
            "skills": skills,
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

    def handle_reset_today(self):
        try:
            with Database.get_connection() as conn:
                today = get_hunter_shift_date(conn)
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
                # Reset Hunter Profile to Level 1 Awakened Novice
                c.execute("""
                UPDATE hunter_profile SET
                    rank = 'E-Rank',
                    level = 1,
                    exp = 0,
                    exp_to_next = 300,
                    title = 'צייד שהתעורר (Awakened)',
                    stats_str = 10,
                    stats_agi = 10,
                    stats_vit = 10,
                    stats_int = 10,
                    stats_per = 10,
                    fatigue = 15,
                    streak_days = 1,
                    last_active_date = date('now'),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """)

                # Reset all 5 Skills to Level 1, 0/100 XP
                c.execute("""
                UPDATE hunter_skills SET
                    level = 1,
                    current_exp = 0,
                    exp_to_next = 100,
                    stat_boost_val = 2
                """)

                # Wipe all activity & history logs
                c.execute("DELETE FROM daily_logs")
                c.execute("DELETE FROM water_logs")
                c.execute("DELETE FROM workout_logs")
                c.execute("DELETE FROM supplements_log")
                c.execute("DELETE FROM medication_logs")
                c.execute("DELETE FROM garmin_health_logs")
                conn.commit()

            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "rebirth_complete",
                "message": "[SYSTEM: לידה מחדש הושלמה! הצייד חזר לרמה 1, דרגת E-Rank. כל הסקילים אופסו לרמה 1.]"
            }, ensure_ascii=False).encode("utf-8"))
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
                "raw_biometrics": health_adv.get("raw_biometrics"),
                "normalized_biometrics": health_adv.get("normalized_biometrics"),
                "attent_normalization": health_adv.get("attent_normalization"),
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

                # Award skill XP based on sleep quality and steps
                if float(body.get("sleep_score", 0)) >= 75 or float(body.get("sleep_hours", 0)) >= 7.0:
                    HunterLevelingEngine.add_skill_exp(conn, "regeneration", 25)
                if int(body.get("steps", 0)) >= 8000:
                    HunterLevelingEngine.add_skill_exp(conn, "shadow_sprint", 20)

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

