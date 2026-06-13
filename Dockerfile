# ---- API Mockmaster production image ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# SQLite default lives here; mount a volume at /app/data to persist it,
# or set DATABASE_URL to a managed Postgres for real production.
ENV DATABASE_URL="sqlite:////app/data/mockmaster.db"
RUN mkdir -p /app/data

EXPOSE 8000

# Honour the platform's $PORT (Render/Railway/Fly set it) and default to 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
