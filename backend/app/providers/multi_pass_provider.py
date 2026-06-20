import asyncio
import time

from app.models.application import ApplicationValues
from app.models.uploads import ValidatedUpload
from app.models.verification import (
    ModelMetadata,
    VerificationFieldResult,
    VerificationFields,
    VerificationStatus,
)
from app.providers.base import ProviderError, ProviderPromptResult, ProviderResult
from app.providers.chat_completion_parser import VERIFICATION_FIELD_NAMES
from app.providers.base import VerificationPromptRunner
from app.services.verification_prompt_service import VerificationPromptService


class MultiPassVerificationProvider:
    def __init__(
        self,
        runner: VerificationPromptRunner,
        prompt_service: VerificationPromptService | None = None,
    ):
        self._runner = runner
        self._prompt_service = prompt_service or VerificationPromptService()

    async def verify(
        self,
        upload: ValidatedUpload,
        item_id: str,
        application_values: ApplicationValues | None = None,
    ) -> ProviderResult:
        started = time.perf_counter()
        prompts = self._prompt_service.build_specialist_prompts(
            application_values.to_prompt_mapping() if application_values else None
        )
        if not prompts:
            raise ProviderError("No verification checks were configured.", retryable=False)

        results = await asyncio.gather(
            *(
                self._runner.run_prompt(
                    upload=upload,
                    prompt=prompt,
                    prompt_name=prompt.name,
                )
                for prompt in prompts
            )
        )
        fields = self._merge_fields(prompts[0].deterministic_fields, results)
        return ProviderResult(
            status=self._overall_status(fields),
            summary=self._summary(fields),
            fields=fields,
            model=self._model_metadata(results, started),
        )

    def _merge_fields(
        self,
        deterministic_fields: dict,
        results: tuple[ProviderPromptResult, ...],
    ) -> VerificationFields:
        merged: dict[str, VerificationFieldResult] = {
            field_name: self._build_field(field)
            for field_name, field in deterministic_fields.items()
        }
        for result in results:
            for field_name, field in result.fields.items():
                if field_name in merged:
                    raise ProviderError(
                        f"Duplicate verification field returned: {field_name}",
                        retryable=False,
                    )
                merged[field_name] = field

        missing_fields = [
            field_name for field_name in VERIFICATION_FIELD_NAMES if field_name not in merged
        ]
        if missing_fields:
            raise ProviderError(
                f"Verification response omitted required fields: {', '.join(missing_fields)}",
                retryable=False,
            )
        return VerificationFields(
            **{field_name: merged[field_name] for field_name in VERIFICATION_FIELD_NAMES}
        )

    def _build_field(self, field: dict) -> VerificationFieldResult:
        return VerificationFieldResult(
            status=field["status"],
            application_value=field.get("application_value"),
            label_value=field.get("label_value") or field.get("extracted_value"),
            reason=field.get("reason") or field.get("explanation", ""),
            evidence=field.get("evidence", []),
        )

    def _overall_status(self, fields: VerificationFields) -> VerificationStatus:
        statuses = [
            value["status"]
            for value in fields.model_dump().values()
        ]
        if "fail" in statuses:
            return VerificationStatus.fail
        return VerificationStatus.pass_status

    def _summary(self, fields: VerificationFields) -> str:
        failed_fields = [
            field_name
            for field_name, value in fields.model_dump().items()
            if value["status"] == "fail"
        ]
        if failed_fields:
            return f"Required checks failed: {', '.join(failed_fields)}."
        return "All required checks passed."

    def _model_metadata(
        self,
        results: tuple[ProviderPromptResult, ...],
        started: float,
    ) -> ModelMetadata:
        first = results[0].model
        attempted_models = [
            f"{index + 1}:{model}"
            for index, result in enumerate(results)
            for model in result.model.attempted_models
        ]
        models = ", ".join(result.model.model for result in results)
        return ModelMetadata(
            provider=first.provider,
            model=f"multi-pass({models})",
            provider_mode=first.provider_mode,
            duration_ms=int((time.perf_counter() - started) * 1000),
            fallback_attempts=sum(result.model.fallback_attempts for result in results),
            attempted_models=attempted_models,
        )
