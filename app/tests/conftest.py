import os
import uuid
import subprocess

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.db.public import get_db
from app.deps.auth import get_rls_session, get_principal
from app.schemas.auth import TokenClaims


# ---------- helpers ----------

def must_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def replace_dbname(url: str, new_db: str) -> str:
    base = url.rsplit("/", 1)[0]
    return f"{base}/{new_db}"


def assert_safe_test_db(db_name: str) -> None:
    if not db_name.startswith("app_test_"):
        raise RuntimeError(f"Refusing unsafe test db name: {db_name}")


def superuser_engine(admin_url: str):
    """Connect directly to the postgres maintenance DB using the superuser URL."""
    return create_engine(admin_url, poolclass=NullPool)


def create_test_db(admin_url: str, db_name: str) -> None:
    assert_safe_test_db(db_name)
    eng = superuser_engine(admin_url)
    with eng.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        # OWNER app_owner so alembic (which runs as app_owner) can create tables
        conn.execute(text(f'CREATE DATABASE "{db_name}" OWNER app_owner'))
    eng.dispose()


def drop_test_db(admin_url: str, db_name: str) -> None:
    assert_safe_test_db(db_name)
    eng = superuser_engine(admin_url)
    with eng.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(
            text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :db AND pid <> pg_backend_pid()
            """),
            {"db": db_name},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
    eng.dispose()


def run_alembic_upgrade(db_url: str) -> None:
    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = db_url
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=env)


# ---------- session-scoped DB fixtures ----------

@pytest.fixture(scope="session")
def test_db_url():
    # TEST_ADMIN_DATABASE_URL must point to postgres maintenance DB as a superuser
    # (or any role with CREATEDB). Used only for CREATE / DROP DATABASE.
    # Falls back to ALEMBIC_DATABASE_URL for containers where app_owner has CREATEDB.
    admin_url = os.getenv("TEST_ADMIN_DATABASE_URL") or must_env("ALEMBIC_DATABASE_URL")
    alembic_url = must_env("ALEMBIC_DATABASE_URL")

    test_db_name = f"app_test_{uuid.uuid4().hex[:10]}"
    assert_safe_test_db(test_db_name)
    test_url = replace_dbname(alembic_url, test_db_name)

    create_test_db(admin_url, test_db_name)
    try:
        run_alembic_upgrade(test_url)
        yield test_url
    finally:
        drop_test_db(admin_url, test_db_name)


@pytest.fixture(scope="session")
def db_engine(test_db_url):
    engine = create_engine(test_db_url, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def TestSessionLocal(test_db_url):
    # Use app_user (DATABASE_URL) against the test DB — mirrors production so
    # RLS grants and FORCE ROW LEVEL SECURITY behave identically to production.
    app_user_base = must_env("DATABASE_URL").rsplit("/", 1)[0]
    test_db_name = test_db_url.rsplit("/", 1)[-1]
    runtime_url = f"{app_user_base}/{test_db_name}"
    engine = create_engine(runtime_url, poolclass=NullPool)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield Session
    engine.dispose()


# ---------- per-test dependency overrides ----------

@pytest.fixture(autouse=True)
def override_get_db(TestSessionLocal):
    """Override get_db (public endpoints) to use the test DB."""
    def _get_db_override():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def override_get_rls_session(TestSessionLocal):
    """Override get_rls_session (RLS-protected endpoints) to use the test DB.

    JWT decoding and PG config variables are still exercised per-request so that
    tenant-isolation behaviour is preserved in integration tests.
    """
    def _rls_session_override(principal: TokenClaims = Depends(get_principal)):
        db = TestSessionLocal()
        try:
            db.execute(
                text("SELECT set_config('app.tenant_id', :tid, false)"),
                {"tid": str(principal.tenant_id)},
            )
            db.execute(
                text("SELECT set_config('app.user_id', :uid, false)"),
                {"uid": str(principal.user_id)},
            )
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_rls_session] = _rls_session_override
    yield
    app.dependency_overrides.pop(get_rls_session, None)


# ---------- HTTP client ----------

@pytest.fixture()
def client():
    return TestClient(app)