from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# SQLite allows one writer at a time. Building a twin bundle writes state rows
# and can take several seconds on a cold start, so the driver's default 5 s
# lock wait made concurrent first-load requests fail with "database is
# locked". Wait up to 30 s instead (see also the per-business build lock in
# digital_twin_service, which stops parallel builds in the first place).
SQLITE_BUSY_TIMEOUT_S = 30
connect_args = ({"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_S}
                if settings.is_sqlite else {})
engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if settings.is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _rec):  # pragma: no cover - driver glue
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_S * 1000}")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def as_utc(dt):
    """Coerce a stored datetime to UTC-aware.

    SQLite has no timezone type, so values round-trip as naive even though
    they were written aware. Comparing one of those against ``now(UTC)``
    raises, which is a silent trap on expiry checks. Postgres returns aware
    values and is unaffected, so this must work for both.
    """
    from datetime import timezone as _tz
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=_tz.utc)


def create_all() -> None:
    """Create the schema if it is absent, then stamp it at the Alembic head.

    The zero-setup path (SQLite, `./run.sh setup`) needs a schema without
    anyone running a migration first. But a database created this way would
    be invisible to Alembic, and the first real migration would then try to
    create tables that already exist.

    Stamping after creation resolves that: a freshly-created database is
    recorded as already being at head, so subsequent migrations apply
    cleanly. A database that already has an `alembic_version` row is left
    alone entirely — migrations own it from then on.
    """
    from app import models  # noqa: F401  (registers mappers)
    from sqlalchemy import inspect as _inspect

    existing = set(_inspect(engine).get_table_names())
    if "alembic_version" in existing:
        return                      # under migration control; do not touch it

    Base.metadata.create_all(bind=engine)
    _stamp_alembic_head()


def _stamp_alembic_head() -> None:
    """Record a freshly-created schema as being at the migration head."""
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        return                      # alembic is optional for a bare demo run
    ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    if not ini.exists():
        return
    try:
        cfg = Config(str(ini))
        cfg.set_main_option("script_location", str(ini.parent / "migrations"))
        command.stamp(cfg, "head")
    except Exception:
        # Stamping is a convenience. A failure here must never stop the
        # application starting.
        pass
