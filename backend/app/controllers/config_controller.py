from fastapi import APIRouter, Depends

from app.core.settings import Settings, get_settings
from app.models.config import ConfigResponse
from app.services.upload_service import ALLOWED_FILE_TYPES

router = APIRouter()


@router.get("/api/config", response_model=ConfigResponse)
def api_config(settings: Settings = Depends(get_settings)) -> ConfigResponse:
    return ConfigResponse(
        provider_mode=settings.provider_mode,
        environment=settings.environment,
        demo_batch_manifest_url=settings.demo_batch_manifest_url
        if settings.environment.lower() == "production"
        else None,
        max_upload_mb=round(settings.max_upload_size_bytes / (1024 * 1024), 1),
        max_batch_labels=settings.max_batch_count,
        batch_concurrency=settings.batch_concurrency,
        allowed_file_types=ALLOWED_FILE_TYPES,
    )
