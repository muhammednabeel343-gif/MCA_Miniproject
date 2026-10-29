import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

logger = logging.getLogger("database")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, "toxic_backend", "local.db")


def _resolve_database_url():
    raw_database_url = os.getenv("DATABASE_URL", "").strip()

    if not raw_database_url or "*" in raw_database_url:
        return f"sqlite:///{DEFAULT_SQLITE_PATH}"

    return raw_database_url


def _create_engine(database_url):
    engine_kwargs = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
    }

    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(database_url, **engine_kwargs)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        fallback_url = f"sqlite:///{DEFAULT_SQLITE_PATH}"
        fallback_kwargs = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 5,
            "max_overflow": 10,
            "connect_args": {"check_same_thread": False},
        }
        logger.warning(
            "Database connection failed for %s; falling back to SQLite at %s: %s",
            database_url,
            fallback_url,
            exc,
        )
        engine = create_engine(fallback_url, **fallback_kwargs)

    return engine


DATABASE_URL = _resolve_database_url()
engine = _create_engine(DATABASE_URL)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
