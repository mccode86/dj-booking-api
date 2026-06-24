from fastapi import FastAPI
import sqlite3

from oauthlib.openid import connect

from database import DB_PATH
from pydantic import BaseModel

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


class DJCreate(BaseModel):
    name: str
    price: int


class DJUpdate(BaseModel):
    price: int


class OutletCreate(BaseModel):
    name: str
    location: str


class OutletUpdate(BaseModel):
    name: str


class BookingCreate(BaseModel):
    dj_id: int
    outlet_id: int
    date: str


class CancelBooking(BaseModel):
    cancel_reason: str


@app.post("/djs")
def add_dj(dj: DJCreate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO DJ (name, price) VALUES (?, ?)", (dj.name, dj.price))
    conn.commit()
    conn.close()
    return {"message": "DJ added successfully"}


@app.get("/djs")
def get_djs():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DJ WHERE active = 1")
    djs = cursor.fetchall()
    conn.close()
    djs = [dict(dj) for dj in djs]
    return {"djs": djs}


@app.put("/djs/{dj_id}")
def update_dj(dj_id: int, dj: DJUpdate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE DJ SET price = ? WHERE id = ?", (dj.price, dj_id))
    conn.commit()
    conn.close()
    return {"message": "DJ's price updated successfully"}




@app.delete("/djs/{dj_id}")
def delete_dj(dj_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE DJ SET active = 0 WHERE id = ?", (dj_id,))
    conn.commit()
    conn.close()
    return {"message": "DJ deleted successfully"}


@app.post("/outlets")
def add_outlet(outlet: OutletCreate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO OUTLET (name, location) VALUES (?, ?)", (outlet.name, outlet.location))
    conn.commit()
    conn.close()
    return {"message": "Outlet added successfully"}


@app.get("/outlets")
def get_outlets():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM OUTLET WHERE active = 1")
    outlets = cursor.fetchall()
    conn.close()
    outlets = [dict(outlet) for outlet in outlets]
    return {"outlets": outlets}


@app.put("/outlets/{outlet_id}")
def update_outlet(outlet_id: int, outlet: OutletUpdate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE OUTLET SET name = ? WHERE id = ?", (outlet.name, outlet_id))
    conn.commit()
    conn.close()
    return {"message": "Outlet's name updated successfully"}


@app.delete("/outlets/{outlet_id}")
def delete_outlet(outlet_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE OUTLET SET active = 0 WHERE id = ?", (outlet_id,))
    conn.commit()
    conn.close()
    return {"message": "Outlet deleted successfully"}


@app.post("/bookings")
def book_dj(booking: BookingCreate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM BOOKING WHERE dj_id = ? AND date = ?", (booking.dj_id, booking.date))
    book = cursor.fetchall()
    if book:
        conn.close()
        return {"message": "DJ is already booked on this date"}
    cursor.execute("INSERT INTO BOOKING (dj_id, outlet_id, date) VALUES (?, ?, ?)", (booking.dj_id, booking.outlet_id, booking.date))
    conn.commit()
    conn.close()
    return {"message": "DJ booked successfully"}


@app.get("/bookings")
def get_bookings():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM BOOKING")
    bookings = cursor.fetchall()
    conn.close()
    bookings = [dict(booking) for booking in bookings]
    return {"bookings": bookings}


@app.put("/bookings/{booking_id}")
def cancel_booking(booking_id: int, booking: CancelBooking):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE BOOKING SET status = 'Cancelled', cancel_reason = ? WHERE id = ?", (booking.cancel_reason, booking_id))
    conn.commit()
    conn.close()
    return {"message": "DJ's booking cancelled successfully"}
