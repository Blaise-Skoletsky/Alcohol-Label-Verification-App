from functools import lru_cache

from app.core.settings import Settings, get_settings
from app.providers.factory import build_provider
from app.services.batch_service import BatchService
from app.services.sheet_service import SheetService
from app.services.upload_service import UploadService
from app.services.verification_prompt_service import VerificationPromptService
from app.services.verification_service import VerificationService


@lru_cache
def get_upload_service() -> UploadService:
    return UploadService()


@lru_cache
def get_sheet_service() -> SheetService:
    return SheetService()


@lru_cache
def get_verification_prompt_service() -> VerificationPromptService:
    return VerificationPromptService()


@lru_cache
def get_verification_service() -> VerificationService:
    settings = get_settings()
    provider = build_provider(
        settings,
        prompt_service=get_verification_prompt_service(),
    )
    return VerificationService(provider=provider)


@lru_cache
def get_batch_service() -> BatchService:
    settings = get_settings()
    return BatchService(
        settings=settings,
        verification_service=get_verification_service(),
    )


__all__ = [
    "BatchService",
    "Settings",
    "SheetService",
    "UploadService",
    "VerificationPromptService",
    "VerificationService",
    "get_batch_service",
    "get_settings",
    "get_sheet_service",
    "get_upload_service",
    "get_verification_prompt_service",
    "get_verification_service",
]
