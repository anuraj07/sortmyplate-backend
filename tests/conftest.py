import pytest
import asyncio
from app.db.seed import init_db_and_seed

@pytest.fixture(autouse=True, scope="function")
def prepare_db():
    asyncio.run(init_db_and_seed())
    yield
