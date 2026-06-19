import logging

from app.models.errors import VerificationError
from app.models.uploads import ValidatedUpload
from app.models.verification import VerificationResult, VerificationStatus
from app.providers.base import ProviderError, VerificationProvider
from app.services.result_guard_service import ResultGuardService

logger = logging.getLogger("alv.verification")


class VerificationService:
    def __init__(
        self,
        provider: VerificationProvider,
        result_guard: ResultGuardService | None = None,
    ):
        self._provider = provider
        self._result_guard = result_guard or ResultGuardService()

    async def verify(self, upload: ValidatedUpload, item_id: str) -> VerificationResult:
        try:
            provider_result = self._result_guard.enforce(
                await self._provider.verify(upload=upload, item_id=item_id)
            )
        except ProviderError as exc:
            logger.warning(
                "Review could not finish for '%s' (%s): %s",
                upload.filename,
                item_id,
                exc.message,
            )
            return self._build_error_result(
                item_id=item_id,
                filename=upload.filename,
                message=exc.message,
            )
        except Exception:
            logger.exception(
                "Unexpected review problem for '%s' (%s). File contents were not logged.",
                upload.filename,
                item_id,
            )
            return self._build_error_result(
                item_id=item_id,
                filename=upload.filename,
                message="We could not finish processing this file. Please try again.",
            )

        logger.info(
            "Review completed for '%s' (%s): status=%s provider=%s model=%s duration_ms=%s",
            upload.filename,
            item_id,
            provider_result.status,
            provider_result.model.provider,
            provider_result.model.model,
            provider_result.model.duration_ms,
        )
        return VerificationResult(
            item_id=item_id,
            filename=upload.filename,
            status=provider_result.status,
            summary=provider_result.summary,
            fields=provider_result.fields,
            model=provider_result.model,
        )

    def _build_error_result(
        self,
        item_id: str,
        filename: str,
        message: str,
    ) -> VerificationResult:
        return VerificationResult(
            item_id=item_id,
            filename=filename,
            status=VerificationStatus.processing_error,
            summary=message,
            errors=[VerificationError(code="processing_error", message=message)],
        )
