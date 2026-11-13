"""Test fixtures.

Every test runs against a freshly-seeded, deterministic workspace in a
throwaway SQLite file, so the suite never touches the demo database and
never depends on the order tests happen to run in.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

# Default to a throwaway SQLite file so the suite never touches the demo
# database. Set RUNWAY_TEST_DATABASE_URL to run the identical suite against
# PostgreSQL — that is how the portability claim is actually checked rather
# than asserted:
#
#   createdb runway_test
#   RUNWAY_TEST_DATABASE_URL="postgresql+psycopg:///runway_test?host=/run/postgresql" \
#       backend/.venv/bin/python -m pytest tests/ -q
_TMP = Path(tempfile.mkdtemp(prefix="runway-test-"))
os.environ["RUNWAY_DATABASE_URL"] = os.environ.get(
    "RUNWAY_TEST_DATABASE_URL", f"sqlite:///{_TMP / 'test.db'}")
os.environ["RUNWAY_MONTE_CARLO_PATHS"] = "800"
os.environ["RUNWAY_ENV"] = "test"
# Tests never call a paid or rate-limited model, even when backend/.env holds
# a real key: environment variables override the .env file in pydantic.
os.environ["RUNWAY_XKIRO_API_KEY"] = ""
os.environ["RUNWAY_ANTHROPIC_API_KEY"] = ""

import pytest  # noqa: E402

TODAY = date(2026, 11, 7)


@pytest.fixture(scope="session")
def seeded():
    from app.seed.seed import seed
    return seed("B", reset=True, today=TODAY, with_second=True, verbose=False)


@pytest.fixture(scope="session")
def business_id(seeded):
    return seeded["businesses"][0]["id"]


@pytest.fixture(scope="session")
def second_business_id(seeded):
    return seeded["businesses"][1]["id"]


@pytest.fixture()
def db(seeded):
    from app.core.db import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="session")
def client(seeded):
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def owner_auth(client, business_id):
    r = client.post("/api/auth/login",
                    json={"email": "owner@runway.demo", "password": "demo1234"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    return {"Authorization": f"Bearer {tok}", "X-Business-Id": business_id}


@pytest.fixture(scope="session")
def ca_auth(client):
    r = client.post("/api/auth/login",
                    json={"email": "ca@runway.demo", "password": "demo1234"})
    assert r.status_code == 200
    return r.json()


AS_OF = f"?as_of={TODAY.isoformat()}"
