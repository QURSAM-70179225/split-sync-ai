"""SQLAlchemy engine, session factory, lightweight migrations and FastAPI dependency."""
from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings

settings = get_settings()
IS_SQLITE = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    if IS_SQLITE:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Columns added after v1. create_all() never alters existing tables, so older
# splitsync.db files get these via ALTER TABLE on startup.
_ADDED_COLUMNS = {
    "expenses": {
        "category": "VARCHAR(30) NOT NULL DEFAULT 'other'",
        "source": "VARCHAR(10) NOT NULL DEFAULT 'chat'",
        "items_json": "TEXT",
    },
}


def _migrate() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)
    _migrate()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
