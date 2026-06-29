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
