from fastapi import Depends
from app.config import Settings, get_settings
from app.services.pipeline import NewsPipelineService

def get_pipeline_service(
    settings: Settings = Depends(get_settings),
) -> NewsPipelineService:
    return NewsPipelineService(settings=settings)
