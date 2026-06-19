import json
import time

import httpx
from fastapi.testclient import TestClient

from app.core.dependencies import get_batch_service, get_verification_service
from app.core.settings import Settings
from app.main import app
from app.models.uploads import ValidatedUpload
from app.models.verification import (
    ModelMetadata,
    VerificationEvidence,
    VerificationFieldResult,
    VerificationFields,
    VerificationResult,
    VerificationStatus,
)
from app.providers.openrouter_provider import OpenRouterVerificationProvider
from app.providers.local_provider import LocalModelVerificationProvider
from app.providers.base import ProviderResult
from app.services.batch_service import BatchService
from app.services.result_guard_service import ResultGuardService
from app.services.verification_prompt_service import VerificationPromptService


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-png"


def make_field(
    *,
    status: str = "pass",
    application_value: str = "Application value",
    label_value: str = "Label value",
    reason: str = "Test field passed.",
    evidence: list[VerificationEvidence] | None = None,
) -> VerificationFieldResult:
    return VerificationFieldResult(
        status=status,
        application_value=application_value,
        label_value=label_value,
        reason=reason,
        evidence=evidence or [],
    )


def make_fields(
    *,
    alcohol_content: VerificationFieldResult | None = None,
    field_updates: dict[str, VerificationFieldResult] | None = None,
) -> VerificationFields:
    fields = {
        "artifact_legibility": make_field(
            application_value="Application section readable",
            label_value="Label artwork readable",
            reason="Both regions are readable.",
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
        "government_warning": make_field(
            application_value="Required government warning statement",
            label_value="GOVERNMENT WARNING: present",
            reason="Government warning present.",
        ),
    }
    if field_updates:
        fields.update(field_updates)
    return VerificationFields(**fields)


class TestVerificationService:
    async def verify(self, upload: ValidatedUpload, item_id: str) -> VerificationResult:
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
                    "government_warning": make_field(
                        application_value="Required warning statement",
                        label_value="GOVERNMENT WARNING: present",
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
    async def verify(self, upload: ValidatedUpload, item_id: str) -> VerificationResult:
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


def test_config_endpoint_exposes_safe_limits() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.json()
    assert body["provider_mode"] == "local"
    assert body["max_batch_labels"] == 400
    assert ".png" in body["allowed_file_types"]
    assert ".pdf" not in body["allowed_file_types"]
    assert "openrouter_api_key" not in body


def test_settings_accept_comma_separated_cors_origins() -> None:
    settings = Settings(cors_origins="http://localhost:7001,http://127.0.0.1:7001")

    assert settings.cors_origin_list == [
        "http://localhost:7001",
        "http://127.0.0.1:7001",
    ]


def test_verify_rejects_invalid_upload() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={"file": ("not-supported.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PNG, JPG, or JPEG files can be uploaded."


def test_verify_uses_verification_service() -> None:
    client = make_test_client()

    response = client.post(
        "/api/verify",
        files={"file": ("sample.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pass"
    assert body["model"]["provider"] == "test"
    assert body["model"]["model"] == "test-double"
    assert body["fields"]["brand_name"]["status"] == "pass"
    assert body["fields"]["brand_name"]["application_value"] == "Example Brand"
    assert body["fields"]["brand_name"]["label_value"] == "Example Brand"


def test_single_verify_returns_http_error_when_processing_fails() -> None:
    app.dependency_overrides.clear()
    error_service = ErrorVerificationService()

    def override_verification_service() -> ErrorVerificationService:
        return error_service

    app.dependency_overrides[get_verification_service] = override_verification_service
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={"file": ("sample.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "The model returned an unreadable response."


def test_batch_submission_and_progress_shape() -> None:
    client = make_test_client()

    response = client.post(
        "/api/batches",
        files=[
            ("files", ("sample-one.png", PNG_BYTES, "image/png")),
            ("files", ("sample-two-review.png", PNG_BYTES, "image/png")),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert len(body["items"]) == 2

    batch_id = body["batch_id"]
    last_body = None
    for _ in range(20):
        poll = client.get(f"/api/batches/{batch_id}")
        assert poll.status_code == 200
        last_body = poll.json()
        if last_body["status"] == "completed":
            break
        time.sleep(0.05)

    assert last_body is not None
    assert last_body["status"] == "completed"
    assert last_body["total_items"] == 2
    assert set(last_body["counts"]).issuperset(
        {"queued", "processing", "pass", "fail", "needs_review", "processing_error"}
    )
    assert all("status" in item for item in last_body["items"])


def test_openrouter_payload_sends_real_image_content() -> None:
    provider = OpenRouterVerificationProvider(Settings(openrouter_api_key="test-key"))
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    payload = provider._build_payload(model="google/gemini-3.5-flash", upload=upload)

    content = payload["messages"][1]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_local_provider_payload_sends_image_without_openrouter_plugins() -> None:
    provider = LocalModelVerificationProvider(Settings(provider_mode="local"))
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    payload = provider._build_payload(upload=upload)

    content = payload["messages"][1]["content"]
    assert payload["model"] == "qwen2.5-vl-7b-instruct"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "plugins" not in payload


def test_openrouter_payload_uses_shared_verification_prompt() -> None:
    provider = OpenRouterVerificationProvider(
        Settings(openrouter_api_key="test-key"),
        prompt_service=VerificationPromptService(),
    )
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    payload = provider._build_payload(model="google/gemini-3.5-flash", upload=upload)

    assert "alcohol label verification assistant" in payload["messages"][0]["content"]
    prompt_text = payload["messages"][1]["content"][0]["text"]
    assert "artifact_legibility" in prompt_text
    assert "brand_name" in prompt_text
    assert "class_type_designation" in prompt_text
    assert "alcohol_content" in prompt_text
    assert "net_contents" in prompt_text
    assert "name_address" in prompt_text
    assert "country_of_origin" in prompt_text
    assert "government_warning" in prompt_text
    assert "Never return needs_review for government_warning" in prompt_text
    assert '"government_warning":        {"status":"pass|fail",' in prompt_text


def test_openrouter_parser_accepts_string_evidence_items() -> None:
    provider = OpenRouterVerificationProvider(Settings(openrouter_api_key="test-key"))
    response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "status": "pass",
                                "summary": "All fields passed.",
                                "fields": {
                                    "artifact_legibility": {
                                        "status": "pass",
                                        "application_value": "Application readable",
                                        "label_value": "Label readable",
                                        "confidence": 1.0,
                                        "reason": "Both regions readable.",
                                        "evidence": [],
                                    },
                                    "brand_name": {
                                        "status": "pass",
                                        "application_value": "Example",
                                        "label_value": "Example",
                                        "confidence": 1.0,
                                        "reason": "Matched.",
                                        "evidence": ["Brand appears on label."],
                                    },
                                    "class_type_designation": {
                                        "status": "pass",
                                        "application_value": "Red Wine",
                                        "label_value": "Dry Red Table Wine",
                                        "confidence": 1.0,
                                        "reason": "Equivalent type.",
                                        "evidence": [],
                                    },
                                    "alcohol_content": {
                                        "status": "pass",
                                        "application_value": "13%",
                                        "label_value": "13% Alc./Vol.",
                                        "confidence": 1.0,
                                        "reason": "Matched.",
                                        "evidence": [],
                                    },
                                    "net_contents": {
                                        "status": "pass",
                                        "application_value": "750 mL",
                                        "label_value": "750 mL",
                                        "confidence": 1.0,
                                        "reason": "Matched.",
                                        "evidence": [],
                                    },
                                    "name_address": {
                                        "status": "pass",
                                        "application_value": "Example Producer, CA",
                                        "label_value": "BOTTLED BY Example Producer, CA",
                                        "confidence": 1.0,
                                        "reason": "Present.",
                                        "evidence": [],
                                    },
                                    "country_of_origin": {
                                        "status": "pass",
                                        "application_value": "Domestic",
                                        "label_value": "No import origin required",
                                        "confidence": 1.0,
                                        "reason": "Domestic product.",
                                        "evidence": [],
                                    },
                                    "government_warning": {
                                        "status": "pass",
                                        "application_value": "GOVERNMENT WARNING:",
                                        "label_value": "GOVERNMENT WARNING:",
                                        "confidence": 1.0,
                                        "reason": "Present.",
                                        "evidence": [],
                                    },
                                },
                            }
                        )
                    }
                }
            ]
        },
    )

    result = provider._parse_response(
        response=response,
        model="google/gemini-3.1-flash-lite-preview",
        started=time.perf_counter(),
        attempted_models=["google/gemini-3.1-flash-lite-preview"],
    )

    assert result.fields.brand_name.evidence[0].summary == "Brand appears on label."


def test_result_guard_does_not_allow_non_abv_text_to_pass_alcohol_content() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                alcohol_content=make_field(
                    application_value="13",
                    label_value="DRY RED TABLE WINE",
                    reason="Model incorrectly accepted class text.",
                )
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.needs_review
    assert result.fields.alcohol_content.status == "needs_review"
    assert "alcohol-content" in result.fields.alcohol_content.reason
