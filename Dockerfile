FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first so this layer is cached across code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app (dj_booking.db comes along so the demo has seeded data)
COPY . .

# Cloud Run injects $PORT; shell form lets it expand at runtime
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
