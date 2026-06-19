import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.dependencies import get_upload_service, get_verification_service
from app.core.settings import Settings, get_settings
from app.models.verification import VerificationResult, VerificationStatus
from app.services.upload_service import UploadService, UploadValidationError
from app.services.verification_service import VerificationService

logger = logging.getLogger("alv.api")
router = APIRouter()


@router.post("/api/verify", response_model=VerificationResult)
async def api_verify(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    upload_service: UploadService = Depends(get_upload_service),
    verification_service: VerificationService = Depends(get_verification_service),
) -> VerificationResult:
    try:
        upload = await upload_service.validate_upload(file, settings.max_upload_size_bytes)
    except UploadValidationError as exc:
        logger.info("Upload rejected before review: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await verification_service.verify(upload, item_id="single")
    if result.status == VerificationStatus.processing_error:
        detail = result.errors[0].message if result.errors else result.summary
        raise HTTPException(status_code=502, detail=detail)
    return result
