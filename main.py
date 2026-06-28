import bcrypt
import sqlite3
import jwt
import os
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from anthropic import Anthropic
from dotenv import load_dotenv
from database import get_connection


load_dotenv()

client = Anthropic()

MODEL = "claude-sonnet-4-6"
TOKEN_SECRET = os.getenv("JWT_SECRET")

app = FastAPI()
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


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


class Login(BaseModel):
    email: str
    password: str


def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, TOKEN_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


def get_optional_admin(credentials: HTTPAuthorizationCredentials = Depends(optional_security)):
    if credentials is None:
        return None
    try:
        payload = jwt.decode(credentials.credentials, TOKEN_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


def require_role(role: str):
    def checker(admin: dict = Depends(get_current_admin)):
        if admin["role"] != role:
            raise HTTPException(status_code=403, detail="Access denied")
        return admin

    return checker


tools = [{
    "name": "add_dj",
    "description": "Add a new DJ to the system.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the DJ"
            },
            "price": {
                "type": "integer",
            }
        },
        "required": ["name", "price"]
    }
}, {
    "name": "add_outlet",
    "description": "Add a new outlet to the system.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the outlet"
            },
            "location": {
                "type": "string",
                "description": "Location of the outlet"
            }
        },
        "required": ["name", "location"]
    }
}, {
    "name": "update_dj",
    "description": "Update the price of a DJ.",
    "input_schema": {
        "type": "object",
        "properties": {
            "dj_id": {
                "type": "integer",
                "description": "ID of the DJ"
            },
            "price": {
                "type": "integer",
            }
        },
        "required": ["dj_id", "price"]
    }
}, {
    "name": "update_outlet",
    "description": "Update the name of an outlet.",
    "input_schema": {
        "type": "object",
        "properties": {
            "outlet_id": {
                "type": "integer",
                "description": "ID of the outlet"
            },
            "name": {
                "type": "string",
                "description": "New name of the outlet"
            }
        },
        "required": ["outlet_id", "name"]
    }
}, {
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
    "name": "cancel_booking",
    "description": "Cancel a booking.",
    "input_schema": {
        "type": "object",
        "properties": {
            "booking_id": {
                "type": "integer",
                "description": "ID of the booking"
            },
            "cancel_reason": {
                "type": "string",
                "description": "Reason for cancellation"
            }
        },
        "required": ["booking_id", "cancel_reason"]
    }
}, {
    "name": "delete_dj",
    "description": "Delete a DJ by ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "dj_id": {
                "type": "integer",
                "description": "ID of the DJ"
            }
        },
        "required": ["dj_id"]
    }
}, {
    "name": "delete_outlet",
    "description": "Delete an outlet by ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "outlet_id": {
                "type": "integer",
                "description": "ID of the outlet"
            }
        },
        "required": ["outlet_id"]
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
}, {
    "name": "get_bookings",
    "description": "Get a list of all bookings.",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
}]


def tools_for_role(role):
    if role == "admin_dj":
        allowed = ["get_djs", "get_outlets", "get_bookings", "cancel_booking", "delete_dj", "book_dj", "update_dj",
                   "add_dj"]
    elif role == "admin_outlet":
        allowed = ["get_djs", "get_outlets", "get_bookings", "delete_outlet", "update_outlet", "add_outlet"]
    else:
        allowed = ["get_djs", "get_outlets", "get_bookings"]
    return [tool for tool in tools if tool["name"] in allowed]


def run_tool(tool_name, input_data):
    if tool_name == "get_djs":
        return get_djs()
    elif tool_name == "get_outlets":
        return get_outlets()
    elif tool_name == "get_bookings":
        return get_bookings()
    elif tool_name == "add_dj":
        return add_dj(DJCreate(**input_data))
    elif tool_name == "add_outlet":
        return add_outlet(OutletCreate(**input_data))
    elif tool_name == "update_dj":
        return update_dj(input_data["dj_id"], DJUpdate(price=input_data["price"]))
    elif tool_name == "update_outlet":
        return update_outlet(input_data["outlet_id"], OutletUpdate(name=input_data["name"]))
    elif tool_name == "delete_dj":
        return delete_dj(input_data["dj_id"])
    elif tool_name == "delete_outlet":
        return delete_outlet(input_data["outlet_id"])
    elif tool_name == "book_dj":
        return book_dj(BookingCreate(**input_data))
    elif tool_name == "cancel_booking":
        return cancel_booking(input_data["booking_id"], CancelBooking(cancel_reason=input_data["cancel_reason"]))
    else:
        return {"error": "Tool not found"}


def run_agent(message, role):
    loop_count = 0
    messages = [{"role": "user", "content": message}]
    agent_tools = tools_for_role(role)
    system_prompt = f"""You are the assistant for the Holywings DJ booking system.
    
Rules:
- Only use the tools that are available to you. Never claim or pretend you can perform an action if no tool exists for it.
- If you can't do something, say so honestly, and tell the user what you CAN do instead.

The current user's role is {role}.
"""
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            tools=agent_tools,
            system=system_prompt,
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/login")
def login(req: Login):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ADMIN WHERE email = ?", (req.email,))
    admin = cursor.fetchone()
    conn.close()
    if admin and bcrypt.checkpw(req.password.encode(), admin["password"].encode()):
        payload = {"id": admin["id"], "role": admin["role"], "exp": datetime.now(timezone.utc) + timedelta(minutes=30),}
        token = jwt.encode(payload, TOKEN_SECRET, algorithm="HS256")
        return {"token": token}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/chat")
def chat(req: ChatMessage, admin: dict | None = Depends(get_optional_admin)):
    if admin:
        role = admin["role"]
    else:
        role = None
    return {"reply": run_agent(req.message, role)}


@app.post("/djs", dependencies=[Depends(require_role("admin_dj"))])
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


@app.put("/djs/{dj_id}", dependencies=[Depends(require_role("admin_dj"))])
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


@app.delete("/djs/{dj_id}", dependencies=[Depends(require_role("admin_dj"))])
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


@app.post("/outlets", dependencies=[Depends(require_role("admin_outlet"))])
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


@app.put("/outlets/{outlet_id}", dependencies=[Depends(require_role("admin_outlet"))])
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


@app.delete("/outlets/{outlet_id}", dependencies=[Depends(require_role("admin_outlet"))])
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


@app.post("/bookings", dependencies=[Depends(require_role("admin_dj"))])
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


@app.put("/bookings/{booking_id}", dependencies=[Depends(require_role("admin_dj"))])
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
