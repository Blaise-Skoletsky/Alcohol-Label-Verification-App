import json
import logging
import time
from base64 import b64encode
from collections.abc import Callable

import httpx

from app.core.settings import Settings
from app.models.application import ApplicationValues
from app.models.uploads import ValidatedUpload
from app.providers.base import ProviderError, ProviderPromptResult, ProviderResult
from app.providers.chat_completion_parser import (
    parse_chat_completion_prompt_response,
    parse_chat_completion_response,
)
from app.services.verification_prompt_service import (
    SpecialistVerificationPrompt,
    VerificationPrompt,
    VerificationPromptService,
)


logger = logging.getLogger("alv.local_provider")

LOCAL_SCHEMA_RETRY_COUNT = 1
LOCAL_MODEL_DIAGNOSTIC_PREVIEW_CHARS = 1200


class LocalModelVerificationProvider:
    def __init__(
        self,
        settings: Settings,
        prompt_service: VerificationPromptService | None = None,
    ):
        self._settings = settings
        self._prompt_service = prompt_service or VerificationPromptService()
        self._provider_name = "local"
        self._provider_url = self._normalize_ollama_chat_url(settings.local_model_base_url)
        self._model = settings.local_model_name

    async def verify(
        self,
        upload: ValidatedUpload,
        item_id: str,
        application_values: ApplicationValues | None = None,
    ) -> ProviderResult:
        started = time.perf_counter()
        prompt = self._build_prompt(application_values)
        payload = self._build_payload(upload=upload, prompt=prompt)
        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self._settings.provider_timeout_seconds) as client:
                return await self._post_with_schema_retry(
                    client=client,
                    payload=payload,
                    headers=headers,
                    started=started,
                    prompt_name="verification",
                    requested_fields=prompt.requested_fields,
                    parser=lambda response: parse_chat_completion_response(
                        response=response,
                        model=self._model,
                        provider_name=self._provider_name,
                        provider_mode=self._settings.provider_mode,
                        started=started,
                        attempted_models=[self._model],
                        deterministic_fields=prompt.deterministic_fields,
                    ),
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "The local model took too long to answer. Please make sure it is running and try again."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                "The local model could not review this file. Please check that the local model server supports image inputs."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "We could not reach the local model. Please start the local model server and try again."
            ) from exc

    async def run_prompt(
        self,
        *,
        upload: ValidatedUpload,
        prompt: VerificationPrompt | SpecialistVerificationPrompt,
        prompt_name: str,
    ) -> ProviderPromptResult:
        started = time.perf_counter()
        payload = self._build_payload(upload=upload, prompt=prompt)
        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self._settings.provider_timeout_seconds) as client:
                return await self._post_with_schema_retry(
                    client=client,
                    payload=payload,
                    headers=headers,
                    started=started,
                    prompt_name=prompt_name,
                    requested_fields=prompt.requested_fields,
                    parser=lambda response: parse_chat_completion_prompt_response(
                        response=response,
                        model=self._model,
                        provider_name=self._provider_name,
                        provider_mode=self._settings.provider_mode,
                        started=started,
                        attempted_models=[self._model],
                        requested_fields=prompt.requested_fields,
                    ),
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"The local model took too long to answer the {prompt_name} check."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                "The local model could not review this file. Please check that the local model server supports image inputs."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "We could not reach the local model. Please start the local model server and try again."
            ) from exc

    def _build_payload(
        self,
        upload: ValidatedUpload,
        application_values: ApplicationValues | None = None,
        prompt: VerificationPrompt | SpecialistVerificationPrompt | None = None,
    ) -> dict:
        prompt = prompt or self._build_prompt(application_values)
        encoded_image = self._encode_image(upload)
        return {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": prompt.system_instruction,
                },
                {
                    "role": "user",
                    "content": prompt.user_instruction,
                    "images": [encoded_image],
                },
            ],
            "format": self._build_response_schema(prompt.requested_fields),
            "options": {"temperature": 0, "num_predict": 1800},
            "stream": False,
        }

    def _build_prompt(self, application_values: ApplicationValues | None) -> VerificationPrompt:
        return self._prompt_service.build_prompt(
            application_values.to_prompt_mapping() if application_values else None
        )

    async def _post_with_schema_retry(
        self,
        *,
        client: httpx.AsyncClient,
        payload: dict,
        headers: dict[str, str],
        started: float,
        prompt_name: str,
        requested_fields: tuple[str, ...],
        parser: Callable[[httpx.Response], ProviderResult | ProviderPromptResult],
    ) -> ProviderResult | ProviderPromptResult:
        attempts = 1 + self._schema_retry_count()
        last_error: ProviderError | None = None
        for attempt in range(attempts):
            response = await client.post(self._provider_url, headers=headers, json=payload)
            response.raise_for_status()
            try:
                return parser(response)
            except ProviderError as exc:
                last_error = exc
                self._log_malformed_response(
                    response=response,
                    prompt_name=prompt_name,
                    requested_fields=requested_fields,
                    started=started,
                    error=exc,
                )
                if attempt < attempts - 1:
                    continue
                raise
        raise last_error or ProviderError(
            "The verification service returned an unreadable response. Please try again."
        )

    def _schema_retry_count(self) -> int:
        return min(1, max(0, LOCAL_SCHEMA_RETRY_COUNT))

    def _encode_image(self, upload: ValidatedUpload) -> str:
        if upload.extension not in {".png", ".jpg", ".jpeg"}:
            raise ProviderError("Local mode only supports PNG and JPG uploads.", retryable=False)

        return b64encode(upload.content).decode("ascii")

    def _build_response_schema(self, requested_fields: tuple[str, ...]) -> dict:
        field_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "application_value", "label_value", "reason", "evidence"],
            "properties": {
                "status": {"type": "string", "enum": ["pass", "fail"]},
                "application_value": {"type": "string"},
                "label_value": {"type": "string"},
                "reason": {"type": "string"},
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["summary"],
                        "properties": {
                            "summary": {"type": "string"},
                            "source_excerpt": {"type": "string"},
                        },
                    },
                },
            },
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "summary", "fields"],
            "properties": {
                "status": {"type": "string", "enum": ["pass", "fail"]},
                "summary": {"type": "string"},
                "fields": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(requested_fields),
                    "properties": {
                        field_name: field_schema for field_name in requested_fields
                    },
                },
            },
        }

    def _log_malformed_response(
        self,
        *,
        response: httpx.Response,
        prompt_name: str,
        requested_fields: tuple[str, ...],
        started: float,
        error: ProviderError,
    ) -> None:
        logger.warning(
            "Malformed local model response: specialist=%s requested_fields=%s "
            "model=%s duration_ms=%s response_shape=%s parse_error=%s response_preview=%s",
            prompt_name,
            list(requested_fields),
            self._model,
            int((time.perf_counter() - started) * 1000),
            self._response_shape(response),
            repr(error.__cause__ or error),
            self._response_preview(response),
        )

    def _response_preview(self, response: httpx.Response) -> str:
        limit = max(0, LOCAL_MODEL_DIAGNOSTIC_PREVIEW_CHARS)
        try:
            body = response.json()
            if isinstance(body, dict):
                content = self._response_content(body)
                if content is not None:
                    preview = content if isinstance(content, str) else json.dumps(content)
                else:
                    preview = json.dumps(body)
            else:
                preview = json.dumps(body)
        except (TypeError, ValueError, json.JSONDecodeError):
            preview = response.text
        return preview[:limit]

    def _response_shape(self, response: httpx.Response) -> dict:
        try:
            body = response.json()
        except (TypeError, ValueError, json.JSONDecodeError):
            return {"body_type": "non_json", "text_length": len(response.text)}
        if not isinstance(body, dict):
            return {"body_type": type(body).__name__}

        shape: dict[str, object] = {"body_keys": sorted(body.keys())}
        if isinstance(body.get("message"), dict):
            message = body["message"]
            content = message.get("content")
            shape["message_keys"] = sorted(message.keys())
            shape["message_content_type"] = type(content).__name__
            shape["message_content_length"] = len(content) if isinstance(content, str) else None
        if isinstance(body.get("choices"), list) and body["choices"]:
            first_choice = body["choices"][0]
            if isinstance(first_choice, dict) and isinstance(first_choice.get("message"), dict):
                message = first_choice["message"]
                content = message.get("content")
                shape["choice_message_keys"] = sorted(message.keys())
                shape["choice_message_content_type"] = type(content).__name__
                shape["choice_message_content_length"] = (
                    len(content) if isinstance(content, str) else None
                )
        return shape

    def _response_content(self, body: dict) -> object | None:
        if isinstance(body.get("message"), dict):
            return body["message"].get("content")
        if isinstance(body.get("choices"), list) and body["choices"]:
            first_choice = body["choices"][0]
            if isinstance(first_choice, dict) and isinstance(first_choice.get("message"), dict):
                return first_choice["message"].get("content")
        return None

    def _normalize_ollama_chat_url(self, url: str) -> str:
        suffix = "/v1/chat/completions"
        if url.rstrip("/").endswith(suffix):
            return url.rstrip("/")[: -len(suffix)] + "/api/chat"
        return url
