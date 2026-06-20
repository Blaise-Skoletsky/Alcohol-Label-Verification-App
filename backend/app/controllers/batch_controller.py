import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.dependencies import get_batch_service, get_upload_service
from app.core.settings import Settings, get_settings
from app.models.application import ApplicationValues
from app.models.batch import BatchCreateResponse, BatchState
from app.services.batch_service import BatchService
from app.services.upload_service import UploadService, UploadValidationError

logger = logging.getLogger("alv.api")
router = APIRouter()

_BEVERAGE_CLASSES = {"spirits", "wine", "malt"}


def _row_to_application_values(row: object) -> ApplicationValues:
    if not isinstance(row, dict):
        return ApplicationValues()

    def field(name: str) -> str | None:
        value = row.get(name)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    beverage_class = (field("beverage_class") or "").lower()
    return ApplicationValues(
        brand_name=field("brand_name"),
        beverage_class=beverage_class if beverage_class in _BEVERAGE_CLASSES else None,  # type: ignore[arg-type]
        class_type_designation=field("class_type_designation"),
        alcohol_content=field("alcohol_content"),
        net_contents=field("net_contents"),
        name_address=field("name_address"),
        country_of_origin=field("country_of_origin"),
    )


@router.post("/api/batches", response_model=BatchCreateResponse)
async def api_create_batch(
    files: list[UploadFile] = File(...),
    rows: str | None = Form(None),
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

    application_values: list[ApplicationValues] = [ApplicationValues() for _ in files]
    if rows is not None:
        try:
            parsed_rows = json.loads(rows)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="The batch rows are not valid JSON.") from exc
        if not isinstance(parsed_rows, list) or len(parsed_rows) != len(files):
            raise HTTPException(
                status_code=400,
                detail="The batch rows must align one-to-one with the uploaded files.",
            )
        application_values = [_row_to_application_values(row) for row in parsed_rows]

    uploads = []
    for file in files:
        try:
            uploads.append(await upload_service.validate_upload(file, settings.max_upload_size_bytes))
        except UploadValidationError as exc:
            logger.info("Batch upload rejected before review: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await batch_service.submit(uploads, application_values)


@router.get("/api/batches/{batch_id}", response_model=BatchState)
async def api_get_batch(
    batch_id: str,
    batch_service: BatchService = Depends(get_batch_service),
) -> BatchState:
    batch = await batch_service.get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return batch
