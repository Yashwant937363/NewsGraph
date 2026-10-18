from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.router import api_router
from app.api.routes.articles import ui_router
from app.api.routes.phase1 import phase1_ui_router
from app.config import get_settings
from app.core.db import close_db, init_db
from app.core.logging import setup_logging

settings = get_settings()
logger = setup_logging(level=settings.log_level)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting News Event Clustering Pipeline Service...")
    try:
        await init_db()
        logger.info("Connected to MongoDB & Beanie initialized.")
    except Exception as e:
        logger.warning(f"MongoDB connection skipped or failed on startup: {e}")
    yield
    try:
        await close_db()
    except Exception:
        pass
    logger.info("Shutting down News Event Clustering Pipeline Service...")

app = FastAPI(
    title="News Event Clustering Pipeline",
    version="1.0.0",
    description="Pipeline fetching articles from NewsAPI, deduplicating them, generating embeddings, and clustering them into events.",
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(ui_router)
app.include_router(phase1_ui_router)

@app.get("/")
async def root():
    return {
        "message": "News Event Clustering Pipeline API is running",
        "docs_url": "/docs",
        "api_v1": "/api/v1",
        "articles_ui": "/articles",
        "phase1_ui": "/phase1",
    }

