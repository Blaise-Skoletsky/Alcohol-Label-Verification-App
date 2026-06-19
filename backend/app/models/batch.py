from enum import Enum

from pydantic import BaseModel, Field

from app.models.verification import VerificationResult, VerificationStatus


class BatchLifecycleStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"


class BatchCounts(BaseModel):
    queued: int = 0
    processing: int = 0
    pass_count: int = Field(default=0, serialization_alias="pass")
    fail: int = 0
    needs_review: int = 0
    processing_error: int = 0


class BatchItemState(BaseModel):
    item_id: str
    filename: str
    status: VerificationStatus
    result: VerificationResult | None = None


class BatchState(BaseModel):
    batch_id: str
    status: BatchLifecycleStatus
    total_items: int
    counts: BatchCounts
    items: list[BatchItemState]


class BatchCreateResponse(BaseModel):
    batch_id: str
    status: BatchLifecycleStatus
    total_items: int
    items: list[BatchItemState]
