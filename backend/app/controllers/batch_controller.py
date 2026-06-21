import json
import logging
import time

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


def _duration_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _log_batch_validation_rejected(
    *,
    file_count: int,
    rows_present: bool,
    started: float,
    reason: str,
) -> None:
    logger.info(
        "Batch upload validation rejected: file_count=%s rows_present=%s duration_ms=%s reason=%s",
        file_count,
        rows_present,
        _duration_ms(started),
        reason,
    )


def _row_to_application_values(row: object) -> ApplicationValues:
    if not isinstance(row, dict):
        return ApplicationValues()

    def field(name: str) -> str | None:
        value = row.get(name)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def bool_field(name: str) -> bool | None:
        value = row.get(name)
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
        return None

    beverage_class = (field("beverage_class") or "").lower()
    return ApplicationValues(
        brand_name=field("brand_name"),
        beverage_class=beverage_class if beverage_class in _BEVERAGE_CLASSES else None,  # type: ignore[arg-type]
        class_type_designation=field("class_type_designation"),
        alcohol_content=field("alcohol_content"),
        net_contents=field("net_contents"),
        name_address=field("name_address"),
        country_of_origin=field("country_of_origin"),
        malt_added_nonbeverage_alcohol=bool_field("malt_added_nonbeverage_alcohol"),
        malt_color_additive_applicable=bool_field("malt_color_additive_applicable"),
    )


@router.post("/api/batches", response_model=BatchCreateResponse)
async def api_create_batch(
    files: list[UploadFile] = File(...),
    rows: str | None = Form(None),
    settings: Settings = Depends(get_settings),
    upload_service: UploadService = Depends(get_upload_service),
    batch_service: BatchService = Depends(get_batch_service),
) -> BatchCreateResponse:
    validation_started = time.perf_counter()
    rows_present = rows is not None
    file_count = len(files)
    logger.info(
        "Batch upload validation started: file_count=%s rows_present=%s",
        file_count,
        rows_present,
    )

    if not files:
        reason = "Please upload at least one file."
        _log_batch_validation_rejected(
            file_count=file_count,
            rows_present=rows_present,
            started=validation_started,
            reason=reason,
        )
        raise HTTPException(status_code=400, detail=reason)
    if len(files) > settings.max_batch_count:
        reason = f"You can upload up to {settings.max_batch_count} files at a time."
        _log_batch_validation_rejected(
            file_count=file_count,
            rows_present=rows_present,
            started=validation_started,
            reason=reason,
        )
        raise HTTPException(
            status_code=400,
            detail=reason,
        )

    application_values: list[ApplicationValues] = [ApplicationValues() for _ in files]
    if rows is not None:
        try:
            parsed_rows = json.loads(rows)
        except json.JSONDecodeError as exc:
            reason = "The batch rows are not valid JSON."
            _log_batch_validation_rejected(
                file_count=file_count,
                rows_present=rows_present,
                started=validation_started,
                reason=reason,
            )
            raise HTTPException(status_code=400, detail=reason) from exc
        if not isinstance(parsed_rows, list) or len(parsed_rows) != len(files):
            reason = "The batch rows must align one-to-one with the uploaded files."
            _log_batch_validation_rejected(
                file_count=file_count,
                rows_present=rows_present,
                started=validation_started,
                reason=reason,
            )
            raise HTTPException(
                status_code=400,
                detail=reason,
            )
        application_values = [_row_to_application_values(row) for row in parsed_rows]

    uploads = []
    for file in files:
        try:
            uploads.append(await upload_service.validate_upload(file, settings.max_upload_size_bytes))
        except UploadValidationError as exc:
            _log_batch_validation_rejected(
                file_count=file_count,
                rows_present=rows_present,
                started=validation_started,
                reason=str(exc),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    validation_duration_ms = _duration_ms(validation_started)
    response = await batch_service.submit(uploads, application_values)
    logger.info(
        "Batch upload validation accepted: batch_id=%s file_count=%s rows_present=%s duration_ms=%s",
        response.batch_id,
        file_count,
        rows_present,
        validation_duration_ms,
    )
    return response


@router.get("/api/batches/{batch_id}", response_model=BatchState)
async def api_get_batch(
    batch_id: str,
    batch_service: BatchService = Depends(get_batch_service),
) -> BatchState:
    batch = await batch_service.get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return batch
