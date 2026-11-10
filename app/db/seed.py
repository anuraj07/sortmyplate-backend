import logging
from app.db.base import engine, Base

logger = logging.getLogger(__name__)

async def init_db():
    """
    Initializes database tables on startup.
    No demo/dummy users are seeded.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema verified and initialized.")
