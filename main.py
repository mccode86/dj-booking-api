from fastapi import FastAPI
import sqlite3
from database import DB_PATH
from pydantic import BaseModel

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


class DJCreate(BaseModel):
    name: str
    price: int


@app.post("/djs")
def add_dj(dj: DJCreate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO DJ (name, price) VALUES (?, ?)", (dj.name, dj.price))
    conn.commit()
    conn.close()
    return {"message": "DJ added successfully"}
