import pytest

from app.core.database import Base, SessionLocal, engine
from app.modules.organization import models  # noqa: F401  (registers tables on Base.metadata)


@pytest.fixture(scope="session", autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine, checkfirst=True)
    yield


@pytest.fixture()
def db_session():
    """A session bound to a transaction that's always rolled back — service
    functions only flush(), never commit(), so nothing here is ever
    persisted past the test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
