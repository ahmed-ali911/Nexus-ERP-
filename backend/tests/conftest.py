import pytest

from app.core.database import Base, SessionLocal, engine
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.master_data import models as master_data_models  # noqa: F401
from app.modules.organization import models as org_models  # noqa: F401

# All three imports above register their tables on Base.metadata for create_all().


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
