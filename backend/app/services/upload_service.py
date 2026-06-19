from pathlib import Path

from fastapi import UploadFile

from app.models.uploads import ValidatedUpload


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}
ALLOWED_FILE_TYPES = [".png", ".jpg", ".jpeg", ".pdf"]


class UploadValidationError(ValueError):
    pass


def _sniff_extension(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"%PDF"):
        return ".pdf"
    return None


class UploadService:
    async def validate_upload(
        self,
        file: UploadFile,
        max_upload_size_bytes: int,
    ) -> ValidatedUpload:
        filename = (file.filename or "").strip()
        if not filename:
            raise UploadValidationError("Please choose a file before submitting.")

        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise UploadValidationError("Only PNG, JPG, JPEG, or PDF files can be uploaded.")

        content = await file.read()
        if not content:
            raise UploadValidationError("The uploaded file is empty. Please choose a valid file.")

        if len(content) > max_upload_size_bytes:
            max_megabytes = round(max_upload_size_bytes / (1024 * 1024), 1)
            raise UploadValidationError(
                f"This file is too large. Please upload a file smaller than {max_megabytes} MB."
            )

        sniffed_extension = _sniff_extension(content)
        if sniffed_extension is None:
            raise UploadValidationError(
                "We could not recognize this file. Please upload a PNG, JPG, JPEG, or PDF file."
            )

        if extension == ".jpeg":
            extension = ".jpg"

        if extension != sniffed_extension:
            raise UploadValidationError(
                "The file extension does not match the file contents. Please re-export the file and try again."
            )

        return ValidatedUpload(
            filename=filename,
            content_type=file.content_type,
            extension=extension,
            content=content,
        )
