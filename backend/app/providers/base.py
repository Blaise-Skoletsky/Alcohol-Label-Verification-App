from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.models.application import ApplicationValues
from app.models.uploads import ValidatedUpload
from app.models.verification import ModelMetadata, VerificationFields, VerificationStatus
from app.models.verification import VerificationFieldResult

if TYPE_CHECKING:
    from app.services.verification_prompt_service import (
        SpecialistVerificationPrompt,
        VerificationPrompt,
    )


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


@dataclass(slots=True)
class ProviderPromptResult:
    status: VerificationStatus
    summary: str
    fields: dict[str, VerificationFieldResult]
    model: ModelMetadata


class VerificationProvider(Protocol):
    async def verify(
        self,
        upload: ValidatedUpload,
        item_id: str,
        application_values: ApplicationValues | None = None,
    ) -> ProviderResult:
        ...


class VerificationPromptRunner(Protocol):
    async def run_prompt(
        self,
        *,
        upload: ValidatedUpload,
        prompt: "VerificationPrompt | SpecialistVerificationPrompt",
        prompt_name: str,
    ) -> ProviderPromptResult:
        ...
