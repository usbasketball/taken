from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


def _build_url(url: str) -> str:
    # Neon / Heroku use postgres:// but SQLAlchemy requires postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _make_engine():
    url = _build_url(settings.database_url)
    if url.startswith("sqlite"):
        # SQLite (used in tests) — no connection pool config
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(
        url,
        pool_pre_ping=True,  # verify connection health before use (important for serverless)
        pool_size=5,
        max_overflow=10,
        connect_args={"sslmode": "require"} if "neon.tech" in url else {},
    )


engine = _make_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass
