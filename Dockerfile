FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    SQLITE_DB_PATH=/app/data/hotel_email_triage.sqlite3

WORKDIR /app

COPY requirements-server.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-server.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "outlook_dashboard.main:app", "--host", "0.0.0.0", "--port", "8000"]
