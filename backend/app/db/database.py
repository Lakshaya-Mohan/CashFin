import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DEFAULT_DB_URL = "postgresql+psycopg2://cashfin_user:cashfin_password@localhost:5432/cashfin"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

try:
    engine = create_engine(DATABASE_URL)
except Exception:
    # Fallback to SQLite in-memory if DB connection/driver setup fails at module load
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


def get_db():
    """FastAPI dependency for obtaining a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()