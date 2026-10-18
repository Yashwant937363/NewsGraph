from fastapi import APIRouter
from app.api.routes.pipeline import router as pipeline_router
from app.api.routes.articles import router as articles_router
from app.api.routes.phase1 import router as phase1_router
from app.api.routes.phase3 import router as phase3_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(pipeline_router)
api_router.include_router(articles_router)
api_router.include_router(phase1_router)
api_router.include_router(phase3_router)

