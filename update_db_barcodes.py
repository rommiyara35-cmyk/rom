import sqlite3
import json

DB_PATH = "/Users/rommiyara/.gemini/antigravity/scratch/solo-leveling-fitness/fitness_system.db"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Ensure barcode column exists
try:
    c.execute("ALTER TABLE food_items ADD COLUMN barcode TEXT")
except Exception:
    pass

# Assign barcodes to existing items
c.execute("UPDATE food_items SET barcode = '7290000045579' WHERE name_he LIKE '%קוטג%'")
c.execute("UPDATE food_items SET barcode = '7290000078027' WHERE name_he LIKE '%טונה%'")
c.execute("UPDATE food_items SET barcode = '7290000067649' WHERE name_he LIKE '%יוגורט פרו%'")

# Insert additional popular Israeli scanned items
items = [
    ("Tnuva GO PRO Protein Drink (Vanilla 27g)", "משקה חלב תנובה GO פרו וניל (27g חלבון)", "dairy", 250, 165, 27.0, 8.5, 2.5, 0.0, 110, 320, 25, 1.2, 0, 15, 0.2, "7290000067656"),
    ("Osem Bamba (80g)", "במבה אסם קלאסית (80 גרם)", "snacks", 80, 432, 14.0, 42.0, 24.0, 4.0, 340, 420, 70, 2.5, 0, 0, 2.0, "7290000066062"),
    ("Allin Protein Bar (60g)", "חטיף חלבון אולאין Allin (שוקולד 20g חלבון)", "snacks", 60, 218, 20.2, 19.5, 6.8, 4.5, 120, 140, 30, 1.5, 0, 0, 1.8, "7290000088996")
]

for it in items:
    c.execute("SELECT id FROM food_items WHERE barcode = ?", (it[16],))
    if not c.fetchone():
        c.execute("""
        INSERT INTO food_items (
            name, name_he, category, serving_size_g, calories, protein, carbs, fats,
            fiber, sodium_mg, potassium_mg, magnesium_mg, zinc_mg, vit_c_mg, vit_d_iu, iron_mg, barcode, is_custom
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, it)

conn.commit()
print("Barcodes seeded in database!")
