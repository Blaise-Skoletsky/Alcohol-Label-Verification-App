from typing import Literal

from pydantic import BaseModel


class ConfigResponse(BaseModel):
    provider_mode: Literal["openrouter", "local"]
    max_upload_mb: float
    max_batch_labels: int
    batch_concurrency: int
    allowed_file_types: list[str]
