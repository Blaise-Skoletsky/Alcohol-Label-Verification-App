import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from app.core.dependencies import get_sheet_service
from app.core.settings import Settings, get_settings
from app.services.sheet_service import SheetParseError, SheetService

logger = logging.getLogger("alv.api")
router = APIRouter()


@router.post("/api/sheets/parse")
async def api_parse_sheet(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    sheet_service: SheetService = Depends(get_sheet_service),
) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The spreadsheet is empty.")
    if len(content) > settings.max_upload_size_bytes:
        max_megabytes = round(settings.max_upload_size_bytes / (1024 * 1024), 1)
        raise HTTPException(
            status_code=400,
            detail=f"This spreadsheet is too large. Please keep it under {max_megabytes} MB.",
        )

    try:
        return sheet_service.parse(file.filename or "", content)
    except SheetParseError as exc:
        logger.info("Sheet rejected before import: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/sheets/template.csv")
def api_sheet_template(
    sheet_service: SheetService = Depends(get_sheet_service),
) -> PlainTextResponse:
    return PlainTextResponse(
        sheet_service.template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="label_batch_template.csv"'},
    )
