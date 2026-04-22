from __future__ import annotations

import os

import pytest

# Force DEMO_MODE + an in-memory-friendly SQLite URL before any app import
# picks up the real .env.
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./_revival_test.db")
# Allow webhook signature bypass for the automated test suite.
os.environ.setdefault("REVIVAL_TEST_BYPASS", "1")


