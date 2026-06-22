import json
from pathlib import Path
import sqlite3
from database import DB_PATH

BASE_DIR = Path(__file__).resolve().parent
SEED_PATH = BASE_DIR / "data/seed-data.json"

with open(SEED_PATH, "r") as f:
    data = json.load(f)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("DELETE FROM DJ")
cursor.execute("DELETE FROM OUTLET")
for dj in data["djs"]:
    cursor.execute("INSERT INTO DJ (name, price) VALUES (?, ?)", (dj["name"], dj["price"]))
for outlet in data["outlets"]:
    cursor.execute("INSERT INTO OUTLET (name, location) VALUES (?, ?)", (outlet["name"], outlet["location"]))
conn.commit()
conn.close()
