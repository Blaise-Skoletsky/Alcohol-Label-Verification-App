import asyncio
from uuid import uuid4

from app.core.settings import Settings
from app.models.application import ApplicationValues
from app.models.batch import (
    BatchCounts,
    BatchCreateResponse,
    BatchItemState,
    BatchLifecycleStatus,
    BatchState,
)
from app.models.uploads import ValidatedUpload
from app.models.verification import VerificationResult, VerificationStatus
from app.services.verification_service import VerificationService


class BatchService:
    def __init__(self, settings: Settings, verification_service: VerificationService):
        self._settings = settings
        self._verification_service = verification_service
        self._batches: dict[str, BatchState] = {}
        self._lock = asyncio.Lock()

    async def submit(
        self,
        uploads: list[ValidatedUpload],
        application_values: list[ApplicationValues] | None = None,
    ) -> BatchCreateResponse:
        if application_values is None:
            application_values = [ApplicationValues() for _ in uploads]
        batch_id = str(uuid4())
        items = [
            BatchItemState(
                item_id=f"{batch_id}:{index + 1}",
                filename=upload.filename,
                status=VerificationStatus.queued,
            )
            for index, upload in enumerate(uploads)
        ]
        batch = BatchState(
            batch_id=batch_id,
            status=BatchLifecycleStatus.queued,
            total_items=len(items),
            counts=BatchCounts(queued=len(items)),
            items=items,
        )
        async with self._lock:
            self._batches[batch_id] = batch

        asyncio.create_task(
            self._process_batch(
                batch_id=batch_id,
                uploads=uploads,
                application_values=application_values,
            )
        )
        return BatchCreateResponse(
            batch_id=batch.batch_id,
            status=batch.status,
            total_items=batch.total_items,
            items=batch.items,
        )

    async def get(self, batch_id: str) -> BatchState | None:
        async with self._lock:
            batch = self._batches.get(batch_id)
            return batch.model_copy(deep=True) if batch else None

    async def _process_batch(
        self,
        batch_id: str,
        uploads: list[ValidatedUpload],
        application_values: list[ApplicationValues],
    ) -> None:
        semaphore = asyncio.Semaphore(self._settings.batch_concurrency)
        await self._set_batch_status(batch_id, BatchLifecycleStatus.processing)

        async def worker(index: int, upload: ValidatedUpload) -> None:
            item_id = f"{batch_id}:{index + 1}"
            values = application_values[index] if index < len(application_values) else None
            async with semaphore:
                await self._set_item_status(batch_id, item_id, VerificationStatus.processing)
                result = await self._verification_service.verify(
                    upload, item_id, application_values=values
                )
            await self._set_item_result(batch_id, item_id, result)

        await asyncio.gather(*(worker(index, upload) for index, upload in enumerate(uploads)))
        await self._set_batch_status(batch_id, BatchLifecycleStatus.completed)

    async def _set_batch_status(self, batch_id: str, status: BatchLifecycleStatus) -> None:
        async with self._lock:
            batch = self._batches[batch_id]
            batch.status = status

    async def _set_item_status(
        self,
        batch_id: str,
        item_id: str,
        status: VerificationStatus,
    ) -> None:
        async with self._lock:
            batch = self._batches[batch_id]
            item = next(entry for entry in batch.items if entry.item_id == item_id)
            item.status = status
            batch.counts = self._calculate_counts(batch.items)

    async def _set_item_result(
        self,
        batch_id: str,
        item_id: str,
        result: VerificationResult,
    ) -> None:
        async with self._lock:
            batch = self._batches[batch_id]
            item = next(entry for entry in batch.items if entry.item_id == item_id)
            item.status = result.status
            item.result = result
            batch.counts = self._calculate_counts(batch.items)

    def _calculate_counts(self, items: list[BatchItemState]) -> BatchCounts:
        counts = BatchCounts()
        for item in items:
            if item.status == VerificationStatus.queued:
                counts.queued += 1
            elif item.status == VerificationStatus.processing:
                counts.processing += 1
            elif item.status == VerificationStatus.pass_status:
                counts.pass_count += 1
            elif item.status == VerificationStatus.fail:
                counts.fail += 1
            elif item.status == VerificationStatus.processing_error:
                counts.processing_error += 1
        return counts
