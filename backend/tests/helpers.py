import json
import time

import httpx
from fastapi.testclient import TestClient

from app.core.dependencies import get_batch_service, get_verification_service
from app.core.settings import Settings
from app.main import app
from app.models.application import ApplicationValues
from app.models.uploads import ValidatedUpload
from app.models.verification import (
    GovernmentWarningExtraction,
    ModelMetadata,
    VerificationEvidence,
    VerificationFieldResult,
    VerificationFields,
    VerificationResult,
    VerificationStatus,
)
from app.providers.base import ProviderPromptResult, ProviderResult
from app.providers.chat_completion_parser import (
    parse_chat_completion_response,
)
from app.services.batch_service import BatchService
from app.services.result_guard_service import (
    GOVERNMENT_WARNING_BODY,
    GOVERNMENT_WARNING_FULL_TEXT,
    GOVERNMENT_WARNING_HEADING,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-png"


def make_field(
    *,
    status: str = "pass",
    application_value: str = "Application value",
    label_value: str = "Label value",
    reason: str = "Test field passed.",
    evidence: list[VerificationEvidence] | None = None,
    **extra: object,
) -> VerificationFieldResult:
    return VerificationFieldResult(
        status=status,
        application_value=application_value,
        label_value=label_value,
        reason=reason,
        evidence=evidence or [],
        **extra,
    )


def make_warning_field(
    *,
    status: str = "pass",
    application_value: str = "Required federal government warning",
    label_value: str = GOVERNMENT_WARNING_FULL_TEXT,
    reason: str = "Government warning present.",
    evidence: list[VerificationEvidence] | None = None,
    warning_block_visible: bool | None = True,
    warning_heading_text: str | None = f"{GOVERNMENT_WARNING_HEADING}:",
    warning_body_text: str | None = GOVERNMENT_WARNING_BODY,
    warning_full_text: str | None = GOVERNMENT_WARNING_FULL_TEXT,
    warning_unreadable_or_obscured: bool | None = False,
) -> VerificationFieldResult:
    return make_field(
        status=status,
        application_value=application_value,
        label_value=label_value,
        reason=reason,
        evidence=evidence,
        warning_extraction=GovernmentWarningExtraction(
            block_visible=warning_block_visible,
            heading_text=warning_heading_text,
            body_text=warning_body_text,
            full_text=warning_full_text,
            unreadable_or_obscured=warning_unreadable_or_obscured,
        ),
    )


def make_fields(
    *,
    alcohol_content: VerificationFieldResult | None = None,
    field_updates: dict[str, VerificationFieldResult] | None = None,
) -> VerificationFields:
    fields = {
        "artifact_legibility": make_field(
            application_value="N/A - text entry form",
            label_value="Label artwork readable",
            reason="Label artwork is readable.",
        ),
        "brand_name": make_field(
            application_value="Example Brand",
            label_value="Example Brand",
            reason="Brand name matched.",
        ),
        "class_type_designation": make_field(
            application_value="Red Wine",
            label_value="Dry Red Table Wine",
            reason="Class/type meaning matched.",
        ),
        "alcohol_content": alcohol_content
        or make_field(
            application_value="5.0% ABV",
            label_value="5.0% ABV",
            reason="Alcohol content matched.",
        ),
        "net_contents": make_field(
            application_value="750 mL",
            label_value="750 mL",
            reason="Net contents matched.",
        ),
        "name_address": make_field(
            application_value="Example Producer, Napa, CA",
            label_value="BOTTLED BY Example Producer, Napa, CA",
            reason="Name and address appeared on label.",
        ),
        "country_of_origin": make_field(
            application_value="Domestic product",
            label_value="No import country statement required",
            reason="Product is clearly domestic.",
        ),
        "color_additive_disclosure": make_field(
            application_value="Not Required",
            label_value="Not Required",
            reason="Backend applicability: Malt color additive disclosure is not required for this row.",
        ),
        "government_warning": make_warning_field(
            application_value="Required government warning statement",
            label_value=GOVERNMENT_WARNING_FULL_TEXT,
            reason="Government warning present.",
        ),
    }
    if field_updates:
        fields.update(field_updates)
    return VerificationFields(**fields)


class TestVerificationService:
    async def verify(
        self,
        upload: ValidatedUpload,
        item_id: str,
        application_values: "ApplicationValues | None" = None,
    ) -> VerificationResult:
        self.last_application_values = application_values
        evidence = [VerificationEvidence(summary="Test verification service used.")]
        return VerificationResult(
            item_id=item_id,
            filename=upload.filename,
            status=VerificationStatus.pass_status,
            summary="The test verification service returned a pass result.",
            fields=make_fields(
                field_updates={
                    "brand_name": make_field(
                        application_value="Example Brand",
                        label_value="Example Brand",
                        reason="Test brand name passed.",
                        evidence=evidence,
                    ),
                    "alcohol_content": make_field(
                        application_value="5.0% ABV",
                        label_value="5.0% ABV",
                        reason="Test alcohol content passed.",
                        evidence=evidence,
                    ),
                    "government_warning": make_warning_field(
                        application_value="Required warning statement",
                        label_value=GOVERNMENT_WARNING_FULL_TEXT,
                        reason="Test government warning passed.",
                        evidence=evidence,
                    ),
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
                attempted_models=["test-double"],
            ),
        )


class ErrorVerificationService:
    async def verify(
        self,
        upload: ValidatedUpload,
        item_id: str,
        application_values: "ApplicationValues | None" = None,
    ) -> VerificationResult:
        return VerificationResult(
            item_id=item_id,
            filename=upload.filename,
            status=VerificationStatus.processing_error,
            summary="The model returned an unreadable response.",
            errors=[
                {
                    "code": "processing_error",
                    "message": "The model returned an unreadable response.",
                }
            ],
        )


class SpecialistRunner:
    def __init__(self, omit_fields: set[str] | None = None):
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.omit_fields = omit_fields or set()

    async def run_prompt(self, *, upload, prompt, prompt_name: str) -> ProviderPromptResult:
        self.calls.append((prompt_name, prompt.requested_fields))
        source_fields = make_fields()
        fields = {
            field_name: getattr(source_fields, field_name)
            for field_name in prompt.requested_fields
            if field_name not in self.omit_fields
        }
        return ProviderPromptResult(
            status=VerificationStatus.pass_status,
            summary=f"{prompt_name} passed.",
            fields=fields,
            model=ModelMetadata(
                provider="test",
                model=f"test-{prompt_name}",
                provider_mode="local",
                duration_ms=10,
                attempted_models=[f"test-{prompt_name}"],
            ),
        )


def make_prompt_response_content(requested_fields: tuple[str, ...]) -> dict:
    fields = make_fields().model_dump()
    if "government_warning" in requested_fields:
        fields["government_warning"] = make_raw_warning_field()
    return {
        "status": "pass",
        "summary": "Requested fields passed.",
        "fields": {
            field_name: fields[field_name]
            for field_name in requested_fields
        },
    }


def make_provider_response(*, json_body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=200,
        json=json_body,
        request=httpx.Request("POST", "http://provider.test/chat"),
    )


def make_raw_warning_field(
    *,
    status: str = "pass",
    label_value: str = GOVERNMENT_WARNING_FULL_TEXT,
    reason: str = "Present.",
    warning_block_visible: object = True,
    warning_heading_text: object = f"{GOVERNMENT_WARNING_HEADING}:",
    warning_body_text: object = GOVERNMENT_WARNING_BODY,
    warning_full_text: object = GOVERNMENT_WARNING_FULL_TEXT,
    warning_unreadable_or_obscured: object = False,
) -> dict:
    return {
        "status": status,
        "application_value": "Required federal government warning",
        "label_value": label_value,
        "reason": reason,
        "evidence": [],
        "warning_block_visible": warning_block_visible,
        "warning_heading_text": warning_heading_text,
        "warning_body_text": warning_body_text,
        "warning_full_text": warning_full_text,
        "warning_unreadable_or_obscured": warning_unreadable_or_obscured,
    }


def make_chat_completion_result_content(
    *,
    government_warning: dict | None = None,
    status: str = "pass",
) -> dict:
    fields = make_fields().model_dump()
    fields["government_warning"] = government_warning or make_raw_warning_field()
    return {
        "status": status,
        "summary": "Model claimed all checks passed.",
        "fields": fields,
    }


class WireFakeProvider:
    def __init__(self, content: dict):
        self._content = content

    async def verify(
        self,
        upload: ValidatedUpload,
        item_id: str,
        application_values: ApplicationValues | None = None,
    ) -> ProviderResult:
        return parse_chat_completion_response(
            response=make_provider_response(
                json_body={
                    "choices": [
                        {"message": {"content": json.dumps(self._content)}}
                    ]
                }
            ),
            model="test-wire-model",
            provider_name="test-wire",
            provider_mode="local",
            started=time.perf_counter(),
            attempted_models=["test-wire-model"],
        )


def make_test_client() -> TestClient:
    app.dependency_overrides.clear()
    test_verification_service = TestVerificationService()
    test_batch_service = BatchService(
        settings=Settings(provider_mode="local"),
        verification_service=test_verification_service,
    )

    def override_verification_service() -> TestVerificationService:
        return test_verification_service

    def override_batch_service() -> BatchService:
        return test_batch_service

    app.dependency_overrides[get_verification_service] = override_verification_service
    app.dependency_overrides[get_batch_service] = override_batch_service
    return TestClient(app)


def wait_for_batch(client: TestClient, batch_id: str, *, attempts: int = 20) -> dict:
    for _ in range(attempts):
        response = client.get(f"/api/batches/{batch_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"completed", "failed"}:
            return body
        time.sleep(0.05)
    raise AssertionError("Batch did not complete in time.")
