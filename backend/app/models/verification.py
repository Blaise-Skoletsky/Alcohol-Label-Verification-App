from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.models.errors import VerificationError


class VerificationStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    pass_status = "pass"
    fail = "fail"
    processing_error = "processing_error"


class VerificationEvidence(BaseModel):
    summary: str
    source_excerpt: str | None = None


class VerificationFieldResult(BaseModel):
    status: Literal["pass", "fail"]
    application_value: str | None = None
    label_value: str | None = None
    reason: str
    evidence: list[VerificationEvidence] = Field(default_factory=list)


class VerificationFields(BaseModel):
    artifact_legibility: VerificationFieldResult
    brand_name: VerificationFieldResult
    class_type_designation: VerificationFieldResult
    alcohol_content: VerificationFieldResult
    net_contents: VerificationFieldResult
    name_address: VerificationFieldResult
    country_of_origin: VerificationFieldResult
    government_warning: VerificationFieldResult


class ModelMetadata(BaseModel):
    provider: str
    model: str
    provider_mode: Literal["openrouter", "local"]
    duration_ms: int | None = None
    fallback_attempts: int = 0
    attempted_models: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    item_id: str
    filename: str
    status: VerificationStatus
    summary: str
    fields: VerificationFields | None = None
    model: ModelMetadata | None = None
    errors: list[VerificationError] = Field(default_factory=list)
