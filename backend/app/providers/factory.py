from app.core.settings import Settings
from app.providers.base import VerificationProvider
from app.providers.local_provider import LocalModelVerificationProvider
from app.providers.openrouter_provider import OpenRouterVerificationProvider
from app.services.verification_prompt_service import VerificationPromptService


def build_provider(
    settings: Settings,
    prompt_service: VerificationPromptService | None = None,
) -> VerificationProvider:
    if settings.provider_mode == "openrouter":
        return OpenRouterVerificationProvider(settings, prompt_service=prompt_service)
    return LocalModelVerificationProvider(settings, prompt_service=prompt_service)
