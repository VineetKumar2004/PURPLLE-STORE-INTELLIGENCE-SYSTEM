"""Shared test fixtures."""
import os
import pytest
from app.db import init_db, get_connection


@pytest.fixture
def db_path(tmp_path):
    """Create a fresh test database."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def db_conn(db_path):
    """Return a connection to the test database."""
    conn = get_connection(db_path)
    yield conn
    conn.close()
