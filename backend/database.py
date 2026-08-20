"""Подключение к БД. Один и тот же код работает и на SQLite, и на PostgreSQL."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import DATA_DIR, get_settings

settings = get_settings()
url = settings.database_url

connect_args = {}
if url.startswith("sqlite"):
    # У SQLite соединение привязано к потоку, а FastAPI ходит из пула
    connect_args["check_same_thread"] = False
    DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)

if url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _record):
        # В SQLite внешние ключи по умолчанию выключены, каскады без них не работают
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
