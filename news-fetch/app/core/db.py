import asyncio
import logging
from typing import Optional
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import Settings, get_settings
from app.models.documents.article import ArticleDocument
from app.models.documents.fetch_state import FetchStateDocument
from app.models.documents.phase1_ledger import Phase1LedgerDocument
from app.models.documents.phase2_ledger import Phase2LedgerDocument
from app.models.documents.phase3_ledger import Phase3LedgerDocument
from app.models.documents.alias_cache import EntityAliasDocument

logger = logging.getLogger("news_pipeline.db")

_mongo_client: Optional[AsyncIOMotorClient] = None


async def init_db(settings: Optional[Settings] = None) -> AsyncIOMotorClient:
    global _mongo_client
    if settings is None:
        settings = get_settings()

    try:
        current_loop = asyncio.get_running_loop()
        if _mongo_client is not None:
            if _mongo_client.get_io_loop() != current_loop or current_loop.is_closed():
                _mongo_client.close()
                _mongo_client = None
    except Exception:
        _mongo_client = None

    if _mongo_client is None:
        logger.info(f"Connecting to MongoDB at {settings.mongodb_url} (db={settings.mongodb_db_name})...")
        _mongo_client = AsyncIOMotorClient(settings.mongodb_url)


    db = _mongo_client[settings.mongodb_db_name]
    await init_beanie(
        database=db,
        document_models=[
            ArticleDocument,
            FetchStateDocument,
            Phase1LedgerDocument,
            Phase2LedgerDocument,
            Phase3LedgerDocument,
            EntityAliasDocument,
        ],
    )
    logger.info("MongoDB and Beanie initialized successfully.")
    return _mongo_client



async def close_db() -> None:
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        logger.info("MongoDB connection closed.")
