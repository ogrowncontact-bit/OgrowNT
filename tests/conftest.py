import os

# Must be set before any packages.shared.* module is imported, since
# packages/shared/db.py builds the SQLAlchemy engine at import time.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://ogrownt:ogrownt@localhost:5432/ogrownt_test"
)
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("MARKET_DATA_PROVIDER", "mock")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from apps.api.deps import get_session  # noqa: E402
from apps.api.main import app  # noqa: E402
from packages.shared.db import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
