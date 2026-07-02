"""Database session engine.

Minimal SQLAlchemy wiring so the app and Alembic have a single source of
truth for the engine/session. No models or business logic live here —
those will be added per-module in app/modules/<module>/models.py.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
