from fastapi.testclient import TestClient
from main import app
from database import get_connection
from dotenv import load_dotenv
import os

load_dotenv()

client = TestClient(app)

def test_booking():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM BOOKING WHERE date = '2024-05-01'")
    conn.commit()
    conn.close()
    response = client.post("/login", json={"email": "hwadmin.dj@gmail.com", "password": os.getenv("ADMIN_DJ_PASSWORD")})
    token = response.json()["token"]
    response = client.post("/bookings", json={"dj_id": 1, "outlet_id": 1,"date": "2024-05-01"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"message": "DJ booked successfully"}
    response_2 = client.post("/bookings", json={"dj_id": 1, "outlet_id": 1, "date": "2024-05-01"}, headers={"Authorization": f"Bearer {token}"})
    assert response_2.status_code == 200
    assert response_2.json() == {"message": "DJ is already booked on this date"}

def login():
    response = client.post("/login", json={"email": "hwadmin.dj@gmail.com", "password": os.getenv("ADMIN_DJ_PASSWORD")})
    return {"Authorization": f"Bearer {response.json()['token']}"}

def clear_date(date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM BOOKING WHERE date = ?", (date,))
    conn.commit()
    conn.close()

def latest_booking_id(dj_id, date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM BOOKING WHERE dj_id = ? AND date = ? ORDER BY id DESC", (dj_id, date))
    booking_id = cursor.fetchone()[0]
    conn.close()
    return booking_id

def test_booking_after_dj_cancels():
    clear_date("2024-05-02")
    headers = login()
    response = client.post("/bookings", json={"dj_id": 1, "outlet_id": 1, "date": "2024-05-02"}, headers=headers)
    assert response.json() == {"message": "DJ booked successfully"}

    booking_id = latest_booking_id(1, "2024-05-02")
    response = client.put(f"/bookings/{booking_id}", json={"cancel_reason": "DJ sakit", "cancelled_by": "dj"}, headers=headers)
    assert response.json() == {"message": "DJ's booking cancelled successfully"}

    response_2 = client.post("/bookings", json={"dj_id": 1, "outlet_id": 1, "date": "2024-05-02"}, headers=headers)
    assert response_2.status_code == 200
    assert response_2.json() == {"message": "DJ cancelled on this date. The date stays closed across all outlets."}

    response_3 = client.post("/bookings", json={"dj_id": 1, "outlet_id": 2, "date": "2024-05-02"}, headers=headers)
    assert response_3.json() == {"message": "DJ cancelled on this date. The date stays closed across all outlets."}

def test_booking_after_outlet_cancels():
    clear_date("2024-05-03")
    headers = login()
    response = client.post("/bookings", json={"dj_id": 1, "outlet_id": 1, "date": "2024-05-03"}, headers=headers)
    assert response.json() == {"message": "DJ booked successfully"}

    booking_id = latest_booking_id(1, "2024-05-03")
    response = client.put(f"/bookings/{booking_id}", json={"cancel_reason": "Event dibatalkan outlet", "cancelled_by": "outlet"}, headers=headers)
    assert response.json() == {"message": "DJ's booking cancelled successfully"}

    response_2 = client.post("/bookings", json={"dj_id": 1, "outlet_id": 2, "date": "2024-05-03"}, headers=headers)
    assert response_2.status_code == 200
    assert response_2.json() == {"message": "DJ booked successfully"}

    response_3 = client.post("/bookings", json={"dj_id": 1, "outlet_id": 3, "date": "2024-05-03"}, headers=headers)
    assert response_3.json() == {"message": "DJ is already booked on this date"}

def test_dj_cancel_after_outlet_cancel_closes_date():
    clear_date("2024-05-04")
    headers = login()
    client.post("/bookings", json={"dj_id": 1, "outlet_id": 1, "date": "2024-05-04"}, headers=headers)
    booking_id = latest_booking_id(1, "2024-05-04")
    client.put(f"/bookings/{booking_id}", json={"cancel_reason": "Event dibatalkan outlet", "cancelled_by": "outlet"}, headers=headers)

    client.post("/bookings", json={"dj_id": 1, "outlet_id": 2, "date": "2024-05-04"}, headers=headers)
    booking_id = latest_booking_id(1, "2024-05-04")
    client.put(f"/bookings/{booking_id}", json={"cancel_reason": "DJ sakit", "cancelled_by": "dj"}, headers=headers)

    response = client.post("/bookings", json={"dj_id": 1, "outlet_id": 3, "date": "2024-05-04"}, headers=headers)
    assert response.json() == {"message": "DJ cancelled on this date. The date stays closed across all outlets."}

def test_cancel_requires_cancelled_by():
    clear_date("2024-05-05")
    headers = login()
    client.post("/bookings", json={"dj_id": 1, "outlet_id": 1, "date": "2024-05-05"}, headers=headers)
    booking_id = latest_booking_id(1, "2024-05-05")
    response = client.put(f"/bookings/{booking_id}", json={"cancel_reason": "DJ sakit"}, headers=headers)
    assert response.status_code == 422
