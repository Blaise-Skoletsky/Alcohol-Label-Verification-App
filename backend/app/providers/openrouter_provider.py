import time
from base64 import b64encode

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

    async def verify(
        self,
        upload: ValidatedUpload,
        item_id: str,
        application_values: ApplicationValues | None = None,
    ) -> ProviderResult:
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
        prompt = self._build_prompt(application_values)
        async with httpx.AsyncClient(timeout=self._settings.provider_timeout_seconds) as client:
            for model in self._models:
                attempted_models.append(model)
                payload = self._build_payload(model=model, upload=upload, prompt=prompt)
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
                        deterministic_fields=prompt.deterministic_fields,
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

    async def run_prompt(
        self,
        *,
        upload: ValidatedUpload,
        prompt: VerificationPrompt | SpecialistVerificationPrompt,
        prompt_name: str,
    ) -> ProviderPromptResult:
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
                payload = self._build_payload(model=model, upload=upload, prompt=prompt)
                try:
                    response = await client.post(
                        self._provider_url,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    return self._parse_prompt_response(
                        response=response,
                        model=model,
                        started=started,
                        attempted_models=attempted_models,
                        requested_fields=prompt.requested_fields,
                    )
                except httpx.TimeoutException as exc:
                    last_error = ProviderError(
                        f"The {prompt_name} check took too long. Please try again in a moment."
                    )
                    if not self._has_next_model(model):
                        raise last_error from exc
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    last_error = ProviderError(
                        f"The {prompt_name} check could not process this file right now. Please try again later.",
                        retryable=status_code == 429 or status_code >= 500,
                    )
                    if not last_error.retryable or not self._has_next_model(model):
                        raise last_error from exc
                except httpx.HTTPError as exc:
                    last_error = ProviderError(
                        f"We could not reach the verification service for the {prompt_name} check. Please try again later."
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

    def _build_payload(
        self,
        model: str,
        upload: ValidatedUpload,
        application_values: ApplicationValues | None = None,
        prompt: VerificationPrompt | SpecialistVerificationPrompt | None = None,
    ) -> dict:
        prompt = prompt or self._build_prompt(application_values)
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
        return payload

    def _build_prompt(self, application_values: ApplicationValues | None) -> VerificationPrompt:
        return self._prompt_service.build_prompt(
            application_values.to_prompt_mapping() if application_values else None
        )

    def _build_artifact_part(self, upload: ValidatedUpload) -> dict:
        encoded = b64encode(upload.content).decode("ascii")
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
        deterministic_fields: dict | None = None,
    ) -> ProviderResult:
        return parse_chat_completion_response(
            response=response,
            model=model,
            provider_name=self._provider_name,
            provider_mode=self._settings.provider_mode,
            started=started,
            attempted_models=attempted_models,
            deterministic_fields=deterministic_fields,
        )

    def _parse_prompt_response(
        self,
        response: httpx.Response,
        model: str,
        started: float,
        attempted_models: list[str],
        requested_fields: tuple[str, ...],
    ) -> ProviderPromptResult:
        return parse_chat_completion_prompt_response(
            response=response,
            model=model,
            provider_name=self._provider_name,
            provider_mode=self._settings.provider_mode,
            started=started,
            attempted_models=attempted_models,
            requested_fields=requested_fields,
        )
