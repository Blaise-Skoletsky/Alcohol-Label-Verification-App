import time

import httpx

from app.core.settings import Settings
from app.models.uploads import ValidatedUpload
from app.providers.base import ProviderError, ProviderResult
from app.providers.openrouter_provider import OpenRouterVerificationProvider
from app.services.verification_prompt_service import VerificationPromptService


class LocalModelVerificationProvider(OpenRouterVerificationProvider):
    def __init__(
        self,
        settings: Settings,
        prompt_service: VerificationPromptService | None = None,
    ):
        super().__init__(settings, prompt_service=prompt_service)
        self._provider_name = "local"
        self._provider_url = settings.local_model_base_url
        self._models = [settings.local_model_name]
        self._api_key = None

    async def verify(self, upload: ValidatedUpload, item_id: str) -> ProviderResult:
        started = time.perf_counter()
        model = self._models[0]
        payload = self._build_payload(model=model, upload=upload)
        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self._settings.provider_timeout_seconds) as client:
                response = await client.post(self._provider_url, headers=headers, json=payload)
                response.raise_for_status()
                result = self._parse_response(
                    response=response,
                    model=model,
                    started=started,
                    attempted_models=[model],
                )
                result.model.provider = "local"
                return result
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
