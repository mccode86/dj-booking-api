from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from anthropic import Anthropic
from dotenv import load_dotenv
from database import get_connection
import sqlite3


load_dotenv()

client = Anthropic()

MODEL = "claude-sonnet-4-6"

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


class ChatMessage(BaseModel):
    message: str


tools = [{
    "name": "book_dj",
    "description": "Book a DJ for a specific date.",
    "input_schema": {
        "type": "object",
        "properties": {
            "dj_id": {
                "type": "integer",
                "description": "ID of the DJ"
            },
            "outlet_id": {
                "type": "integer",
                "description": "ID of the outlet"
            },
            "date": {
                "type": "string",
                "description": "Date of the booking"
            }
        },
        "required": ["dj_id", "outlet_id", "date"]
    }
}, {
    "name": "get_djs",
    "description": "Get a list of all DJs.",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
}, {
    "name": "get_outlets",
    "description": "Get a list of all outlets.",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
}]


def run_agent(message):
    loop_count = 0
    messages = [{"role": "user", "content": message}]
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            tools=tools,
            messages=messages
        )

        if response.stop_reason != "tool_use":
            return response.content[0].text

        messages.append({"role": "assistant", "content": response.content})
        for block in response.content:
            if block.type == "tool_use":
                result = run_tool(block.name, block.input)
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    }]
                })
        loop_count += 1
        if loop_count >= 10:
            return "Sorry, too many loops. Please try again later."


def run_tool(tool_name, input_data):
    if tool_name == "get_djs":
        return get_djs()
    elif tool_name == "get_outlets":
        return get_outlets()
    elif tool_name == "book_dj":
        return book_dj(BookingCreate(**input_data))
    else:
        return {"error": "Tool not found"}


@app.post("/chat")
def chat(req: ChatMessage):
    return {"reply": run_agent(req.message)}


@app.post("/djs")
def add_dj(dj: DJCreate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO DJ (name, price) VALUES (?, ?)", (dj.name, dj.price))
    conn.commit()
    conn.close()
    return {"message": "DJ added successfully"}


@app.get("/djs")
def get_djs():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DJ WHERE active = 1")
    djs = cursor.fetchall()
    conn.close()
    djs = [dict(dj) for dj in djs]
    return {"djs": djs}


@app.put("/djs/{dj_id}")
def update_dj(dj_id: int, dj: DJUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE DJ SET price = ? WHERE id = ?", (dj.price, dj_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="DJ not found")
    conn.commit()
    conn.close()
    return {"message": "DJ's price updated successfully"}


@app.delete("/djs/{dj_id}")
def delete_dj(dj_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE DJ SET active = 0 WHERE id = ?", (dj_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="DJ not found")
    conn.commit()
    conn.close()
    return {"message": "DJ deleted successfully"}


@app.post("/outlets")
def add_outlet(outlet: OutletCreate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO OUTLET (name, location) VALUES (?, ?)", (outlet.name, outlet.location))
    conn.commit()
    conn.close()
    return {"message": "Outlet added successfully"}


@app.get("/outlets")
def get_outlets():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM OUTLET WHERE active = 1")
    outlets = cursor.fetchall()
    conn.close()
    outlets = [dict(outlet) for outlet in outlets]
    return {"outlets": outlets}


@app.put("/outlets/{outlet_id}")
def update_outlet(outlet_id: int, outlet: OutletUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE OUTLET SET name = ? WHERE id = ?", (outlet.name, outlet_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Outlet not found")
    conn.commit()
    conn.close()
    return {"message": "Outlet's name updated successfully"}


@app.delete("/outlets/{outlet_id}")
def delete_outlet(outlet_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE OUTLET SET active = 0 WHERE id = ?", (outlet_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Outlet not found")
    conn.commit()
    conn.close()
    return {"message": "Outlet deleted successfully"}


@app.post("/bookings")
def book_dj(booking: BookingCreate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM BOOKING WHERE dj_id = ? AND date = ?", (booking.dj_id, booking.date))
    book = cursor.fetchall()
    if book:
        conn.close()
        return {"message": "DJ is already booked on this date"}
    try:
        cursor.execute("INSERT INTO BOOKING (dj_id, outlet_id, date) VALUES (?, ?, ?)",
                       (booking.dj_id, booking.outlet_id, booking.date))
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=404, detail="DJ or outlet not found")
    conn.commit()
    conn.close()
    return {"message": "DJ booked successfully"}


@app.get("/bookings")
def get_bookings():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM BOOKING")
    bookings = cursor.fetchall()
    conn.close()
    bookings = [dict(booking) for booking in bookings]
    return {"bookings": bookings}


@app.put("/bookings/{booking_id}")
def cancel_booking(booking_id: int, booking: CancelBooking):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE BOOKING SET status = 'Cancelled', cancel_reason = ? WHERE id = ?",
                   (booking.cancel_reason, booking_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Booking not found")
    conn.commit()
    conn.close()
    return {"message": "DJ's booking cancelled successfully"}
