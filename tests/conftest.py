import pytest
import asyncio
from app.db.base import engine, Base


async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True, scope="function")
def prepare_db():
    asyncio.run(_reset_db())
    yield
