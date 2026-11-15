"""Shared fixtures.

The API tests need a PostgreSQL database they are allowed to wipe. Point
TEST_DATABASE_URL at one, e.g.

    docker run -d --rm --network host -e POSTGRES_PASSWORD=test -e POSTGRES_DB=ataraxia_test \
        postgres:15-alpine -c port=55432 -c listen_addresses=127.0.0.1
    TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55432/ataraxia_test \
        .venv/bin/python -m pytest tests

Without it those tests are skipped. They refuse to run against anything but
localhost so the production database can never be touched by accident.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bot"))


@pytest.fixture(scope="session")
def test_database_url():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    if urlparse(url).hostname not in ("127.0.0.1", "localhost", "::1"):
        pytest.fail("TEST_DATABASE_URL must point to localhost")
    return url
