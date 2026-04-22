from __future__ import annotations

import os

# Force DEMO_MODE + an in-memory-friendly SQLite URL before any app import
# picks up the real .env.
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./_revival_test.db")
