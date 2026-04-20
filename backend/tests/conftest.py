"""
tests/conftest.py  –  Shared fixtures for pytest.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure security-critical env vars exist before importing app/auth modules.
os.environ.setdefault("SECRET_KEY", "unit-local-secret-very-strong-123456789")

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import Base
from main import app, get_db
import auth
from rate_limiter import limiter
from models import User
from security_utils import reset_security_state

# Use SQLite for tests (fast, no external dependency)
SQLALCHEMY_TEST_URL = "sqlite:///./test.db"
test_engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
    limiter.reset()
    auth.reset_auth_security_state()
    reset_security_state()
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()
    try:
        admin = User(
            username="admin",
            password_hash=auth.hash_password("admin123"),
            role="ADMIN",
        )
        session.add(admin)
        session.commit()
    finally:
        session.close()
    yield
    limiter.reset()
    auth.reset_auth_security_state()
    reset_security_state()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """FastAPI TestClient wired to the test DB."""
    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[auth._get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
