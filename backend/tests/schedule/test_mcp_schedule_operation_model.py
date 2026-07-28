import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.mcp_schedule import (
    MCP_SCHEDULE_OPERATION_STATUSES,
    IdempotencyConflictError,
    McpScheduleOperation,
    claim_or_replay_operation,
    find_replay_operation,
)


def _operation(**overrides):
    values = {
        "user_id": 1,
        "category": "company",
        "action": "CREATE",
        "idempotency_key": "create-20260727-001",
        "correlation_id": "corr-20260727-001",
        "request_hash": "a" * 64,
        "status": "IN_PROGRESS",
    }
    values.update(overrides)
    return McpScheduleOperation(**values)


def test_operation_requires_identity_request_and_status_fields(db_session):
    operation = _operation()
    db_session.add(operation)
    db_session.commit()

    assert operation.id is not None
    assert operation.created_at is not None
    assert operation.updated_at is not None
    assert operation.__table__.c.created_at.server_default is not None
    assert operation.__table__.c.updated_at.server_default is not None
    assert operation.__table__.c.updated_at.onupdate is not None
    assert set(MCP_SCHEDULE_OPERATION_STATUSES) == {
        "IN_PROGRESS",
        "SUCCEEDED",
        "FAILED",
        "RECONCILIATION_REQUIRED",
        "MANUAL_REVIEW",
    }
    required_columns = {
        column.name
        for column in McpScheduleOperation.__table__.columns
        if not column.nullable and not column.primary_key
    }
    assert {
        "user_id",
        "category",
        "action",
        "idempotency_key",
        "correlation_id",
        "request_hash",
        "status",
        "created_at",
        "updated_at",
    } <= required_columns

    db_session.add(_operation(correlation_id="corr-required", status="NOT_A_STATE"))
    with pytest.raises(ValueError, match="invalid MCP schedule operation status"):
        db_session.commit()
    db_session.rollback()


def test_operation_enforces_per_user_idempotency_key_uniqueness(db_session):
    db_session.add(_operation())
    db_session.commit()

    db_session.add(_operation(correlation_id="corr-20260727-002"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(_operation(user_id=2, correlation_id="corr-20260727-003"))
    db_session.commit()


def test_operation_enforces_unique_correlation_id(db_session):
    db_session.add(_operation())
    db_session.commit()

    db_session.add(
        _operation(
            user_id=2,
            idempotency_key="create-20260727-002",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_key_and_same_request_finds_replay(db_session):
    operation = _operation()
    db_session.add(operation)
    db_session.commit()

    replay = find_replay_operation(
        db_session,
        user_id=operation.user_id,
        idempotency_key=operation.idempotency_key,
        request_hash=operation.request_hash,
    )

    assert replay.id == operation.id


def test_same_key_and_different_request_raises_idempotency_conflict(db_session):
    operation = _operation()
    db_session.add(operation)
    db_session.commit()

    with pytest.raises(IdempotencyConflictError):
        find_replay_operation(
            db_session,
            user_id=operation.user_id,
            idempotency_key=operation.idempotency_key,
            request_hash="b" * 64,
        )


def test_claim_or_replay_recovers_from_a_unique_collision_in_another_session(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'operation-race.sqlite3').as_posix()}")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    from app.database import Base
    from app.models.common import User

    Base.metadata.create_all(bind=engine)
    first_session = Session()
    second_session = Session()
    try:
        first_session.add(
            User(
                username="operation-race",
                password_hash="not-used",
                name="Operation Race",
            )
        )
        first_session.commit()
        user_id = first_session.query(User.id).filter_by(username="operation-race").scalar()

        first, first_claimed = claim_or_replay_operation(
            first_session,
            operation=_operation(user_id=user_id),
        )
        first_session.commit()

        replay, second_claimed = claim_or_replay_operation(
            second_session,
            operation=_operation(user_id=user_id),
        )

        assert first_claimed is True
        assert second_claimed is False
        assert replay.id == first.id
        second_session.commit()
    finally:
        first_session.close()
        second_session.close()
        engine.dispose()


def test_claim_or_replay_rejects_a_different_request_after_unique_collision(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'operation-conflict.sqlite3').as_posix()}")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    from app.database import Base
    from app.models.common import User

    Base.metadata.create_all(bind=engine)
    first_session = Session()
    second_session = Session()
    try:
        first_session.add(
            User(
                username="operation-conflict",
                password_hash="not-used",
                name="Operation Conflict",
            )
        )
        first_session.commit()
        user_id = first_session.query(User.id).filter_by(username="operation-conflict").scalar()
        claim_or_replay_operation(first_session, operation=_operation(user_id=user_id))
        first_session.commit()

        with pytest.raises(IdempotencyConflictError):
            claim_or_replay_operation(
                second_session,
                operation=_operation(user_id=user_id, request_hash="b" * 64),
            )
    finally:
        first_session.close()
        second_session.close()
        engine.dispose()


def test_operation_json_keeps_only_bounded_safe_result_and_error_fields(db_session):
    operation = _operation(
        result_json={
            "status": "SUCCEEDED",
            "event_id": "event_20260727_001",
            "etag": '"etag-001"',
            "replayed": False,
            "description": "unbounded event description must never be retained",
            "Authorization": "Bearer secret-token",
            "credential_path": r"C:\\Users\\alice\\.config\\gcloud\\credentials.json",
            "vault_path": r"G:\\내 드라이브\\_Obsidian\\personal.md",
            "nested": {"secret": "do not retain"},
        },
        error_json={
            "code": "reconciliation_required",
            "status": "RECONCILIATION_REQUIRED",
            "retryable": False,
            "http_status": 502,
            "message": "free-text diagnostic must never be retained",
            "authorization": "Bearer another-secret",
            "credentials": {"client_secret": "do not retain"},
        },
    )
    db_session.add(operation)
    db_session.commit()
    db_session.refresh(operation)

    assert operation.result_json == {
        "status": "SUCCEEDED",
        "event_id": "event_20260727_001",
        "etag": '"etag-001"',
        "replayed": False,
    }
    assert operation.error_json == {
        "code": "reconciliation_required",
        "status": "RECONCILIATION_REQUIRED",
        "retryable": False,
        "http_status": 502,
    }

    operation.result_json = {"etag": r"C:\\private\\credentials.json"}
    operation.error_json = {"code": "failed", "message": "Bearer secret-token"}
    db_session.commit()
    db_session.refresh(operation)

    assert operation.result_json == {}
    assert operation.error_json == {"code": "failed"}


def test_calendar_ensure_does_not_create_operation_journal(monkeypatch, tmp_path):
    from app.utils import schema

    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'calendar-only.sqlite3').as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE timesheet_entries (id INTEGER PRIMARY KEY)"))
        monkeypatch.setattr(
            schema,
            "ensure_mcp_schedule_operation_tables",
            lambda _engine: pytest.fail("calendar schema must not create the operation journal"),
        )

        schema.ensure_calendar_schedule_tables(engine)
    finally:
        engine.dispose()


def test_fresh_sqlite_development_schema_matches_model_and_enforces_foreign_key(tmp_path):
    from app.utils.schema import ensure_mcp_schedule_operation_tables

    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'operation-schema.sqlite3').as_posix()}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        ensure_mcp_schedule_operation_tables(engine)
        inspector = inspect(engine)
        columns = {column["name"]: column for column in inspector.get_columns("mcp_schedule_operations")}
        column_names = set(columns)
        assert column_names == {
            "id",
            "user_id",
            "category",
            "action",
            "event_id",
            "idempotency_key",
            "correlation_id",
            "request_hash",
            "expected_etag",
            "desired_state_hash",
            "status",
            "result_json",
            "error_json",
            "created_at",
            "updated_at",
        }
        assert {name for name, column in columns.items() if not column["nullable"]} == {
            "user_id", "category", "action", "idempotency_key", "correlation_id",
            "request_hash", "status", "created_at", "updated_at",
        }
        assert inspector.get_pk_constraint("mcp_schedule_operations")["constrained_columns"] == ["id"]
        assert "CURRENT_TIMESTAMP" in str(columns["created_at"]["default"]).upper()
        assert "CURRENT_TIMESTAMP" in str(columns["updated_at"]["default"]).upper()
        foreign_keys = inspector.get_foreign_keys("mcp_schedule_operations")
        assert [(foreign_key["constrained_columns"], foreign_key["referred_table"]) for foreign_key in foreign_keys] == [
            (["user_id"], "users"),
        ]
        unique_columns = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("mcp_schedule_operations")
        }
        index_names = {
            index["name"]
            for index in inspector.get_indexes("mcp_schedule_operations")
        }
        assert unique_columns == {
            ("user_id", "idempotency_key"),
            ("correlation_id",),
        }
        assert index_names == {
            "idx_mcp_schedule_operations_user_id",
            "idx_mcp_schedule_operations_event_id",
        }
        with engine.connect() as connection:
            table_sql = connection.execute(text("""
                SELECT sql FROM sqlite_master
                WHERE type = 'table' AND name = 'mcp_schedule_operations'
            """)).scalar_one()
        assert "ck_mcp_schedule_operations_status" in table_sql
        assert "RECONCILIATION_REQUIRED" in table_sql
        with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(text("""
                    INSERT INTO mcp_schedule_operations (
                        user_id, category, action, idempotency_key, correlation_id,
                        request_hash, status
                    ) VALUES (999, 'company', 'CREATE', 'orphan-key', 'orphan-correlation',
                        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'IN_PROGRESS')
                """))
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id) VALUES (1)"))
            with pytest.raises(IntegrityError):
                connection.execute(text("""
                    INSERT INTO mcp_schedule_operations (
                        user_id, category, action, idempotency_key, correlation_id,
                        request_hash, status
                    ) VALUES (1, 'company', 'CREATE', 'invalid-status-key', 'invalid-status-correlation',
                        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'INVALID')
                """))
    finally:
        engine.dispose()


def test_actual_application_sqlite_engine_enforces_operation_foreign_keys():
    from app.database import Base, engine as application_engine
    from app.models.common import User

    if application_engine.dialect.name != "sqlite":
        pytest.skip("application database is not SQLite")

    application_engine.dispose()
    inspector = inspect(application_engine)
    created_users = not inspector.has_table("users")
    created_operations = not inspector.has_table("mcp_schedule_operations")
    try:
        User.__table__.create(bind=application_engine, checkfirst=True)
        McpScheduleOperation.__table__.create(bind=application_engine, checkfirst=True)

        with application_engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

        with application_engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(text("""
                    INSERT INTO mcp_schedule_operations (
                        user_id, category, action, idempotency_key, correlation_id,
                        request_hash, status
                    ) VALUES (999, 'company', 'CREATE', 'app-engine-orphan-key',
                        'app-engine-orphan-correlation',
                        'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
                        'IN_PROGRESS')
                """))
    finally:
        if created_operations:
            McpScheduleOperation.__table__.drop(bind=application_engine, checkfirst=True)
        if created_users:
            User.__table__.drop(bind=application_engine, checkfirst=True)
        application_engine.dispose()


def test_postgresql_migration_structure_matches_operation_journal(monkeypatch):
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260727_0015_mcp_schedule_operations.py"
    spec = importlib.util.spec_from_file_location("mcp_schedule_operation_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    captured = {"indexes": []}

    def capture_table(name, *elements, **kwargs):
        captured["name"] = name
        captured["elements"] = elements
        captured["kwargs"] = kwargs

    def capture_index(name, table_name, columns, **kwargs):
        captured["indexes"].append((name, table_name, tuple(columns), kwargs))

    monkeypatch.setattr(
        migration,
        "op",
        SimpleNamespace(create_table=capture_table, create_index=capture_index),
    )
    migration.upgrade()

    columns = {element.name: element for element in captured["elements"] if hasattr(element, "nullable")}
    constraints = {element.name: element for element in captured["elements"] if getattr(element, "name", None)}
    assert captured["name"] == "mcp_schedule_operations"
    assert set(columns) == set(McpScheduleOperation.__table__.columns.keys())
    assert columns["user_id"].nullable is False
    assert columns["created_at"].server_default is not None
    assert columns["updated_at"].server_default is not None
    assert next(iter(columns["user_id"].foreign_keys)).target_fullname == "users.id"
    assert set(constraints) >= {
        "uq_mcp_schedule_operations_user_idempotency_key",
        "uq_mcp_schedule_operations_correlation_id",
        "ck_mcp_schedule_operations_status",
    }
    assert captured["indexes"] == [
        ("idx_mcp_schedule_operations_user_id", "mcp_schedule_operations", ("user_id",), {}),
        ("idx_mcp_schedule_operations_event_id", "mcp_schedule_operations", ("event_id",), {}),
    ]
