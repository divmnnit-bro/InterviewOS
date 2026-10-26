from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Deterministic constraint names keep Alembic migrations stable and diff-able.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def normalize_database_url(database_url: str) -> URL:
    """Select the installed psycopg v3 driver for standard Postgres URLs.

    Managed database providers commonly expose ``postgres://`` or
    ``postgresql://`` URLs. SQLAlchemy otherwise defaults those to psycopg2,
    which this project does not install.
    """
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url


engine = create_engine(
    normalize_database_url(settings.DATABASE_URL),
    pool_pre_ping=True,  # drop dead connections instead of failing a request
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DB_ECHO,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed afterwards.

    Services decide when to commit; on an unhandled error we roll back so a
    half-finished booking is never persisted.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
