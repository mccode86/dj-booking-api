from fastapi.testclient import TestClient
from main import app
from database import get_connection

client = TestClient(app)

def test_booking():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM BOOKING WHERE date = '2024-05-01'")
    conn.commit()
    conn.close()
    response = client.post("/bookings", json={"dj_id": 1, "outlet_id": 1,"date": "2024-05-01"})
    assert response.status_code == 200
    assert response.json() == {"message": "DJ booked successfully"}
    response_2 = client.post("/bookings", json={"dj_id": 1, "outlet_id": 1, "date": "2024-05-01"})
    assert response_2.status_code == 200
    assert response_2.json() == {"message": "DJ is already booked on this date"}



