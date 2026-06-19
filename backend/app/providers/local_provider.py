import time
from base64 import b64encode

import httpx

from app.core.settings import Settings
from app.models.uploads import ValidatedUpload
from app.providers.base import ProviderError, ProviderResult
from app.providers.chat_completion_parser import parse_chat_completion_response
from app.services.verification_prompt_service import VerificationPromptService


class LocalModelVerificationProvider:
    def __init__(
        self,
        settings: Settings,
        prompt_service: VerificationPromptService | None = None,
    ):
        self._settings = settings
        self._prompt_service = prompt_service or VerificationPromptService()
        self._provider_name = "local"
        self._provider_url = settings.local_model_base_url
        self._model = settings.local_model_name

    async def verify(self, upload: ValidatedUpload, item_id: str) -> ProviderResult:
        started = time.perf_counter()
        payload = self._build_payload(upload=upload)
        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self._settings.provider_timeout_seconds) as client:
                response = await client.post(self._provider_url, headers=headers, json=payload)
                response.raise_for_status()
                return parse_chat_completion_response(
                    response=response,
                    model=self._model,
                    provider_name=self._provider_name,
                    provider_mode=self._settings.provider_mode,
                    started=started,
                    attempted_models=[self._model],
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

    def _build_payload(self, upload: ValidatedUpload) -> dict:
        prompt = self._prompt_service.build_prompt()
        return {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": prompt.system_instruction,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt.user_instruction},
                        self._build_image_part(upload),
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 1800,
            "stream": False,
        }

    def _build_image_part(self, upload: ValidatedUpload) -> dict:
        if upload.extension not in {".png", ".jpg", ".jpeg"}:
            raise ProviderError("Local mode only supports PNG and JPG uploads.", retryable=False)

        encoded = b64encode(upload.content).decode("ascii")
        mime_type = "image/png" if upload.extension == ".png" else "image/jpeg"
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{encoded}",
            },
        }
