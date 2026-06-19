import json
import time
from base64 import b64encode

import httpx

from app.core.settings import Settings
from app.models.uploads import ValidatedUpload
from app.models.verification import (
    ModelMetadata,
    VerificationEvidence,
    VerificationFieldResult,
    VerificationFields,
    VerificationStatus,
)
from app.providers.base import ProviderError, ProviderResult
from app.services.verification_prompt_service import VerificationPromptService


VERIFICATION_FIELD_NAMES = (
    "artifact_legibility",
    "brand_name",
    "class_type_designation",
    "alcohol_content",
    "net_contents",
    "name_address",
    "country_of_origin",
    "government_warning",
)


class OpenRouterVerificationProvider:
    def __init__(
        self,
        settings: Settings,
        prompt_service: VerificationPromptService | None = None,
    ):
        self._settings = settings
        self._prompt_service = prompt_service or VerificationPromptService()
        self._provider_name = "openrouter"
        self._provider_url = settings.openrouter_base_url
        self._models = settings.openrouter_models
        self._api_key = settings.openrouter_api_key

    async def verify(self, upload: ValidatedUpload, item_id: str) -> ProviderResult:
        if not self._api_key:
            raise ProviderError(
                "Verification is not configured yet. Please add the OpenRouter API key on the backend.",
                retryable=False,
            )

        started = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        attempted_models: list[str] = []
        last_error: ProviderError | None = None
        async with httpx.AsyncClient(timeout=self._settings.provider_timeout_seconds) as client:
            for model in self._models:
                attempted_models.append(model)
                payload = self._build_payload(model=model, upload=upload)
                try:
                    response = await client.post(
                        self._provider_url,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    return self._parse_response(
                        response=response,
                        model=model,
                        started=started,
                        attempted_models=attempted_models,
                    )
                except httpx.TimeoutException as exc:
                    last_error = ProviderError(
                        "Verification took too long. Please try again in a moment."
                    )
                    if not self._has_next_model(model):
                        raise last_error from exc
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    last_error = ProviderError(
                        "The verification service could not process this file right now. Please try again later.",
                        retryable=status_code == 429 or status_code >= 500,
                    )
                    if not last_error.retryable or not self._has_next_model(model):
                        raise last_error from exc
                except httpx.HTTPError as exc:
                    last_error = ProviderError(
                        "We could not reach the verification service. Please try again later."
                    )
                    if not self._has_next_model(model):
                        raise last_error from exc
                except ProviderError as exc:
                    last_error = exc
                    if not exc.retryable or not self._has_next_model(model):
                        raise

        raise last_error or ProviderError("Verification could not be completed. Please try again.")

    def _has_next_model(self, current_model: str) -> bool:
        models = self._models
        return models.index(current_model) < len(models) - 1

    def _build_payload(self, model: str, upload: ValidatedUpload) -> dict:
        prompt = self._prompt_service.build_prompt()
        content = [{"type": "text", "text": prompt.user_instruction}]
        content.append(self._build_artifact_part(upload))
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": prompt.system_instruction,
                },
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 1800,
            "stream": False,
        }
        if upload.extension == ".pdf":
            payload["plugins"] = [{"id": "file-parser", "pdf": {"engine": "mistral-ocr"}}]
        return payload

    def _build_artifact_part(self, upload: ValidatedUpload) -> dict:
        encoded = b64encode(upload.content).decode("ascii")
        if upload.extension == ".pdf":
            return {
                "type": "file",
                "file": {
                    "filename": upload.filename,
                    "file_data": f"data:application/pdf;base64,{encoded}",
                },
            }

        mime_type = "image/png" if upload.extension == ".png" else "image/jpeg"
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{encoded}",
            },
        }

    def _parse_response(
        self,
        response: httpx.Response,
        model: str,
        started: float,
        attempted_models: list[str],
    ) -> ProviderResult:
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content) if isinstance(content, str) else content
            fields = self._parse_fields(parsed["fields"])
            duration_ms = int((time.perf_counter() - started) * 1000)
            return ProviderResult(
                status=VerificationStatus(parsed["status"]),
                summary=parsed["summary"],
                fields=fields,
                model=ModelMetadata(
                    provider=self._provider_name,
                    model=model,
                    provider_mode=self._settings.provider_mode,
                    duration_ms=duration_ms,
                    fallback_attempts=max(0, len(attempted_models) - 1),
                    attempted_models=attempted_models,
                ),
            )
        except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderError(
                "The verification service returned an unreadable response. Please try again."
            ) from exc

    def _parse_fields(self, raw_fields: dict) -> VerificationFields:
        def build_field(field_name: str) -> VerificationFieldResult:
            field = raw_fields[field_name]
            evidence = [self._parse_evidence_item(item) for item in field.get("evidence", [])]
            return VerificationFieldResult(
                status=field["status"],
                application_value=field.get("application_value"),
                label_value=field.get("label_value") or field.get("extracted_value"),
                confidence=field.get("confidence"),
                reason=field.get("reason") or field.get("explanation", ""),
                evidence=evidence,
            )

        return VerificationFields(
            **{field_name: build_field(field_name) for field_name in VERIFICATION_FIELD_NAMES}
        )

    def _parse_evidence_item(self, item: object) -> VerificationEvidence:
        if isinstance(item, str):
            return VerificationEvidence(summary=item)
        if isinstance(item, dict):
            return VerificationEvidence(
                summary=str(item.get("summary") or item.get("text") or item.get("message") or ""),
                source_excerpt=item.get("source_excerpt") or item.get("excerpt"),
            )
        return VerificationEvidence(summary=str(item))
