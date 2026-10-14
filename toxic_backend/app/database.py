import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, "toxic_backend", "local.db")


def _resolve_database_url():
    raw_database_url = os.getenv("DATABASE_URL", "").strip()

    if not raw_database_url or "*" in raw_database_url:
        return f"sqlite:///{DEFAULT_SQLITE_PATH}"

    return raw_database_url


DATABASE_URL = _resolve_database_url()
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 5,
    "max_overflow": 10,
}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}


engine = create_engine(
    DATABASE_URL,
    **engine_kwargs
)


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
