"""Database initialization helpers."""

from sqlalchemy.engine import Engine

import app.models  # noqa: F401  # Register ORM mappings before creating metadata.
from app.db.base import Base
from app.db.session import engine as default_engine


def init_db(engine: Engine = default_engine) -> None:
    """Create database tables from ORM metadata.

    This is intentionally migration-ready: future phases can replace direct metadata
    creation with Alembic migrations without changing model definitions.
    """
    Base.metadata.create_all(bind=engine)
