from fastapi import APIRouter

from app.router.track1.events import router as events_router
from app.router.track1.search import router as search_router
from app.router.track1.investigate import router as investigate_router
from app.router.track1.impact import router as impact_router
from app.router.track1.connect import router as connect_router
from app.router.track1.evidence import router as evidence_router

router = APIRouter(prefix="/track1", tags=["track1"])

router.include_router(events_router)
router.include_router(search_router)
router.include_router(investigate_router)
router.include_router(impact_router)
router.include_router(connect_router)
router.include_router(evidence_router)

__all__ = ["router"]
