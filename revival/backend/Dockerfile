FROM python:3.12-slim

WORKDIR /app

# System deps — only what pydantic/sqlalchemy/anthropic actually need.
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY fixtures ./fixtures
COPY pytest.ini .
COPY alembic.ini .
COPY migrations ./migrations

ENV PYTHONUNBUFFERED=1 \
    DEMO_MODE=true \
    DATABASE_URL=sqlite:///./revival.db \
    CORS_ORIGINS=http://localhost:5174

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8001/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
