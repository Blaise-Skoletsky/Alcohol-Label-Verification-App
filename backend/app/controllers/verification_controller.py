import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.dependencies import get_upload_service, get_verification_service
from app.core.settings import Settings, get_settings
from app.models.application import ApplicationValues, BeverageClass
from app.models.verification import VerificationResult, VerificationStatus
from app.services.upload_service import UploadService, UploadValidationError
from app.services.verification_service import VerificationService

logger = logging.getLogger("alv.api")
router = APIRouter()


def _normalize_beverage_class(value: str | None) -> BeverageClass | None:
    normalized = (value or "").strip().lower()
    if normalized in {"spirits", "wine", "malt"}:
        return normalized  # type: ignore[return-value]
    return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return None


@router.post("/api/verify", response_model=VerificationResult)
async def api_verify(
    file: UploadFile = File(...),
    brand_name: str | None = Form(None),
    beverage_class: str | None = Form(None),
    class_type_designation: str | None = Form(None),
    alcohol_content: str | None = Form(None),
    net_contents: str | None = Form(None),
    name_address: str | None = Form(None),
    country_of_origin: str | None = Form(None),
    malt_added_nonbeverage_alcohol: str | None = Form(None),
    malt_color_additive_applicable: str | None = Form(None),
    settings: Settings = Depends(get_settings),
    upload_service: UploadService = Depends(get_upload_service),
    verification_service: VerificationService = Depends(get_verification_service),
) -> VerificationResult:
    try:
        upload = await upload_service.validate_upload(file, settings.max_upload_size_bytes)
    except UploadValidationError as exc:
        logger.info("Upload rejected before review: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    application_values = ApplicationValues(
        brand_name=_clean(brand_name),
        beverage_class=_normalize_beverage_class(beverage_class),
        class_type_designation=_clean(class_type_designation),
        alcohol_content=_clean(alcohol_content),
        net_contents=_clean(net_contents),
        name_address=_clean(name_address),
        country_of_origin=_clean(country_of_origin),
        malt_added_nonbeverage_alcohol=_parse_bool(malt_added_nonbeverage_alcohol),
        malt_color_additive_applicable=_parse_bool(malt_color_additive_applicable),
    )

    result = await verification_service.verify(
        upload, item_id="single", application_values=application_values
    )
    if result.status == VerificationStatus.processing_error:
        detail = result.errors[0].message if result.errors else result.summary
        raise HTTPException(status_code=502, detail=detail)
    return result
