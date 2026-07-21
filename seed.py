import json
from pathlib import Path
import sqlite3
from database import DB_PATH
import bcrypt
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
SEED_PATH = BASE_DIR / "data/seed-data.json"

secret_dj = os.getenv("ADMIN_DJ_PASSWORD")
secret_outlet = os.getenv("ADMIN_OUTLET_PASSWORD")
hashed_dj = bcrypt.hashpw(secret_dj.encode(), bcrypt.gensalt())
hashed_outlet = bcrypt.hashpw(secret_outlet.encode(), bcrypt.gensalt())

with open(SEED_PATH, "r") as f:
    data = json.load(f)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("DELETE FROM DJ")
cursor.execute("DELETE FROM OUTLET")
cursor.execute("DELETE FROM ADMIN")
cursor.execute("INSERT INTO ADMIN (role, email, password) VALUES (?, ?, ?)", ("admin_dj", "admin.dj@gmail.com", hashed_dj.decode()))
cursor.execute("INSERT INTO ADMIN (role, email, password) VALUES (?, ?, ?)", ("admin_outlet", "admin.outlet@gmail.com", hashed_outlet.decode()))
for dj in data["djs"]:
    cursor.execute("INSERT INTO DJ (name, price) VALUES (?, ?)", (dj["name"], dj["price"]))
for outlet in data["outlets"]:
    cursor.execute("INSERT INTO OUTLET (name, location) VALUES (?, ?)", (outlet["name"], outlet["location"]))
conn.commit()
conn.close()
