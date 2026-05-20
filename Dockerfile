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

RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=4)"

CMD ["python", "-m", "uvicorn", "outlook_dashboard.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--log-level", "warning", "--no-access-log"]
