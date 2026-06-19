import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.dependencies import get_batch_service, get_upload_service
from app.core.settings import Settings, get_settings
from app.models.batch import BatchCreateResponse, BatchState
from app.services.batch_service import BatchService
from app.services.upload_service import UploadService, UploadValidationError

logger = logging.getLogger("alv.api")
router = APIRouter()


@router.post("/api/batches", response_model=BatchCreateResponse)
async def api_create_batch(
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
    upload_service: UploadService = Depends(get_upload_service),
    batch_service: BatchService = Depends(get_batch_service),
) -> BatchCreateResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one file.")
    if len(files) > settings.max_batch_count:
        raise HTTPException(
            status_code=400,
            detail=f"You can upload up to {settings.max_batch_count} files at a time.",
        )

    uploads = []
    for file in files:
        try:
            uploads.append(await upload_service.validate_upload(file, settings.max_upload_size_bytes))
        except UploadValidationError as exc:
            logger.info("Batch upload rejected before review: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await batch_service.submit(uploads)


@router.get("/api/batches/{batch_id}", response_model=BatchState)
async def api_get_batch(
    batch_id: str,
    batch_service: BatchService = Depends(get_batch_service),
) -> BatchState:
    batch = await batch_service.get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return batch
