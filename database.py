import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dj_booking.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS DJ (
    id INTEGER PRIMARY KEY,
    name TEXT,
    price INTEGER,
    active INTEGER DEFAULT 1)
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS OUTLET (
    id INTEGER PRIMARY KEY,
    name TEXT,
    location TEXT,
    active INTEGER DEFAULT 1)
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS BOOKING (
    id INTEGER PRIMARY KEY,
    dj_id INTEGER,
    outlet_id INTEGER,
    date TEXT,
    status TEXT DEFAULT 'Booked',
    cancel_reason TEXT,
    FOREIGN KEY (dj_id) REFERENCES DJ(id),
    FOREIGN KEY (outlet_id) REFERENCES OUTLET(id))
    """)

    conn.commit()
    conn.close()


init_db()


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
