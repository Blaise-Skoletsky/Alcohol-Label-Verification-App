from dataclasses import dataclass


@dataclass(slots=True)
class ValidatedUpload:
    filename: str
    content_type: str | None
    extension: str
    content: bytes
