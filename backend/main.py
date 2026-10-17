from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).parent / "app" / "static"

from app.config.falkordb_client import close_falkordb, init_falkordb
from app.router.track1 import router as track1_router
from app.router.track1.evidence import router as evidence_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing newsgraph...")

    try:
        if not init_falkordb():
            raise RuntimeError(
                "FalkorDB is unavailable. Application startup aborted."
            )
        yield
    finally:
        close_falkordb()
    print("Shutting down newsgraph...")


app = FastAPI(lifespan=lifespan)

app.include_router(
    router=track1_router,
)
app.include_router(
    router=evidence_router,
    prefix="/api/v1",
)

@app.get("/")
async def root():
    """Serve the FalkorDB canvas visualization webpage."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint to verify FalkorDB connectivity."""
    from app.config.falkordb_client import is_falkordb_healthy

    if is_falkordb_healthy():
        return {"status": "healthy"}
    else:
        return {"status": "unhealthy"}