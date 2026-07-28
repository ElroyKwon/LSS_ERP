from pathlib import Path
import os
import shutil
import sys
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_MISSING_ENV = object()
_TEST_ENV_KEYS = ("ENVIRONMENT", "DATABASE_URL", "SECRET_KEY")
_ORIGINAL_ENV = {
    key: os.environ.get(key, _MISSING_ENV)
    for key in _TEST_ENV_KEYS
}
_BOOTSTRAP_DIR = Path(tempfile.mkdtemp(prefix="lss-erp-schedule-bootstrap-"))
_BOOTSTRAP_DB = _BOOTSTRAP_DIR / "schedule-test-bootstrap.sqlite3"

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_BOOTSTRAP_DB.as_posix()}"
os.environ["SECRET_KEY"] = "schedule-characterization-test-key"

from app import models  # noqa: E402,F401
from app.database import Base  # noqa: E402
from app.database import engine as application_engine  # noqa: E402
from app.database import get_db  # noqa: E402
from app.models.common import User  # noqa: E402
from app.models.master import Employee  # noqa: E402
from app.routers import schedule  # noqa: E402


def pytest_unconfigure(config):
    try:
        application_engine.dispose()
        shutil.rmtree(_BOOTSTRAP_DIR)
    finally:
        for key, original_value in _ORIGINAL_ENV.items():
            if original_value is _MISSING_ENV:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


@pytest.fixture()
def db_session(tmp_path):
    database_path = (tmp_path / "schedule-characterization.sqlite3").as_posix()
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    testing_session = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    Base.metadata.create_all(bind=engine)

    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def ordinary_user(db_session):
    employee = Employee(
        emp_code="E001",
        name="Alice",
        department_name="Engineering",
    )
    user = User(
        username="alice",
        employee_code="E001",
        password_hash="not-used-by-characterization-tests",
        name="Alice",
        labor_type="원가",
    )
    db_session.add_all([employee, user])
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def schedule_client(db_session):
    app = FastAPI()
    app.include_router(schedule.router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def mcp_schedule_writes_enabled(monkeypatch):
    """Opt in only tests that intentionally exercise backend schedule writes."""
    monkeypatch.setenv("MCP_SCHEDULE_WRITE_ENABLED", "true")
