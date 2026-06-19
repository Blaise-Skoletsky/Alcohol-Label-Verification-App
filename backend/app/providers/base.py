from dataclasses import dataclass
from typing import Protocol

from app.models.uploads import ValidatedUpload
from app.models.verification import ModelMetadata, VerificationFields, VerificationStatus


class ProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


@dataclass(slots=True)
class ProviderResult:
    status: VerificationStatus
    summary: str
    fields: VerificationFields
    model: ModelMetadata


class VerificationProvider(Protocol):
    async def verify(self, upload: ValidatedUpload, item_id: str) -> ProviderResult:
        ...
