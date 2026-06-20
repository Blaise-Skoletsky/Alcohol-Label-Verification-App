from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    provider_mode: Literal["openrouter", "local"] = Field(
        default="local",
        validation_alias=AliasChoices("ALV_PROVIDER_MODE", "PROVIDER_MODE", "MODEL_PROVIDER"),
    )
    local_model_base_url: str = Field(
        default="http://localhost:1234/v1/chat/completions",
        validation_alias=AliasChoices("ALV_LOCAL_MODEL_BASE_URL", "LOCAL_MODEL_BASE_URL"),
    )
    local_model_name: str = Field(
        default="qwen2.5-vl-7b-instruct",
        validation_alias=AliasChoices("ALV_LOCAL_MODEL_NAME", "LOCAL_MODEL_NAME"),
    )
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY"),
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1/chat/completions",
        validation_alias=AliasChoices("ALV_OPENROUTER_BASE_URL", "OPENROUTER_BASE_URL"),
    )
    openrouter_model_primary: str = Field(
        default="google/gemini-3.1-flash-lite-preview",
        validation_alias=AliasChoices(
            "ALV_OPENROUTER_MODEL_PRIMARY",
            "OPENROUTER_MODEL_PRIMARY",
        ),
    )
    openrouter_model_fallbacks: str = Field(
        default="google/gemini-2.5-flash-lite,google/gemini-2.5-flash",
        validation_alias=AliasChoices(
            "ALV_OPENROUTER_MODEL_FALLBACKS",
            "OPENROUTER_MODEL_FALLBACKS",
        ),
    )
    provider_timeout_seconds: float = Field(
        default=45.0,
        validation_alias=AliasChoices(
            "ALV_PROVIDER_TIMEOUT_SECONDS",
            "PROVIDER_TIMEOUT_SECONDS",
            "OPENROUTER_TIMEOUT_SECONDS",
        ),
    )
    max_upload_size_bytes: int = Field(
        default=15 * 1024 * 1024,
        validation_alias=AliasChoices("ALV_MAX_UPLOAD_SIZE_BYTES", "MAX_UPLOAD_SIZE_BYTES"),
    )
    max_upload_mb: float | None = Field(
        default=None,
        validation_alias=AliasChoices("ALV_MAX_UPLOAD_MB", "MAX_UPLOAD_MB"),
    )
    max_batch_count: int = Field(
        default=350,
        validation_alias=AliasChoices("ALV_MAX_BATCH_COUNT", "MAX_BATCH_COUNT", "MAX_BATCH_LABELS"),
    )
    batch_concurrency: int = Field(
        default=5,
        validation_alias=AliasChoices("ALV_BATCH_CONCURRENCY", "BATCH_CONCURRENCY"),
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias=AliasChoices("ALV_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    @property
    def openrouter_models(self) -> list[str]:
        models = [self.openrouter_model_primary.strip()]
        models.extend(
            model.strip()
            for model in self.openrouter_model_fallbacks.split(",")
            if model.strip()
        )
        return list(dict.fromkeys(model for model in models if model))

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def model_post_init(self, __context: object) -> None:
        if self.max_upload_mb is not None:
            self.max_upload_size_bytes = int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()
