import io
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
        {"queued", "processing", "pass", "fail", "processing_error"}
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

    system_text = payload["messages"][0]["content"]
    user_text = payload["messages"][1]["content"][0]["text"]
    assert system_text.startswith("NON-NEGOTIABLE GOVERNMENT WARNING GATE")
    assert "alcohol label verification assistant" in system_text
    assert "artifact_legibility" in system_text
    assert "brand_name" in system_text
    assert "class_type_designation" in system_text
    assert "alcohol_content" in system_text
    assert "net_contents" in system_text
    assert "name_address" in system_text
    assert "country_of_origin" in system_text
    assert "government_warning" in system_text
    assert "Allowed statuses: pass or fail only" in system_text
    assert '"government_warning":        {"status":"pass|fail",' in system_text
    assert '"application_value":"Required federal government warning"' in system_text
    assert "APPLICATION_VALUES_JSON" in system_text
    assert "The uploaded image is label artwork only" in system_text
    assert "Do not extract application values from the image" in system_text
    assert "prefix 'GOVERNMENT WARNING:' is all caps and visibly bold" in system_text
    assert "Never invent or fill in government_warning.label_value from regulatory knowledge" in system_text
    assert "Review the attached label artwork image using the system rules." in user_text
    assert "APPLICATION_VALUES_JSON" in user_text
    assert '"brand_name": "{{brand_name}}"' in user_text
    assert "government_warning" not in user_text


def test_verification_prompt_accepts_application_values() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "Stone's Throw",
            "class_type_designation": "Wine",
            "alcohol_content": "13.5% ABV",
            "net_contents": "750 mL",
            "name_address": "Example Producer, Napa, CA",
            "country_of_origin": "Domestic product",
        }
    )

    assert "\"brand_name\": \"Stone's Throw\"" in prompt.user_instruction
    assert '"class_type_designation": "Wine"' in prompt.user_instruction
    assert '"alcohol_content": "13.5% ABV"' in prompt.user_instruction
    assert "The uploaded image is label artwork only" in prompt.system_instruction
    assert "Do not extract application values from the image" in prompt.system_instruction


def test_verify_forwards_application_values_to_service() -> None:
    app.dependency_overrides.clear()
    service = TestVerificationService()
    app.dependency_overrides[get_verification_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={"file": ("sample.png", PNG_BYTES, "image/png")},
        data={
            "brand_name": "Coyam",
            "beverage_class": "wine",
            "class_type_designation": "Red Wine",
            "alcohol_content": "14.5%",
            "net_contents": "750 mL",
            "name_address": "Banfi Products Corp",
            "country_of_origin": "Chile",
        },
    )

    assert response.status_code == 200
    values = service.last_application_values
    assert isinstance(values, ApplicationValues)
    assert values.brand_name == "Coyam"
    assert values.beverage_class == "wine"
    assert values.net_contents == "750 mL"
    assert values.country_of_origin == "Chile"
    app.dependency_overrides.clear()


def test_provider_payload_includes_application_values() -> None:
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

    payload = provider._build_payload(
        model="google/gemini-3.5-flash",
        upload=upload,
        application_values=ApplicationValues(brand_name="Coyam", net_contents="750 mL"),
    )

    user_text = payload["messages"][1]["content"][0]["text"]
    assert '"brand_name": "Coyam"' in user_text
    assert '"net_contents": "750 mL"' in user_text


def test_batch_accepts_aligned_rows() -> None:
    client = make_test_client()

    response = client.post(
        "/api/batches",
        files=[
            ("files", ("coyam.png", PNG_BYTES, "image/png")),
            ("files", ("casamigos.png", PNG_BYTES, "image/png")),
        ],
        data={
            "rows": json.dumps(
                [
                    {"filename": "coyam.png", "brand_name": "Coyam", "beverage_class": "wine"},
                    {"filename": "casamigos.png", "brand_name": "Casamigos", "beverage_class": "spirits"},
                ]
            )
        },
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def test_batch_rejects_misaligned_rows() -> None:
    client = make_test_client()

    response = client.post(
        "/api/batches",
        files=[("files", ("coyam.png", PNG_BYTES, "image/png"))],
        data={"rows": json.dumps([{"brand_name": "Coyam"}, {"brand_name": "Extra"}])},
    )

    assert response.status_code == 400


def test_sheet_parse_csv_normalizes_columns() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)
    csv_bytes = (
        "image,brand_name,class_type,beverage_class,alcohol_content,net_contents,name_address,country_of_origin\n"
        "coyam.png,Coyam,Red Wine,wine,14.5%,750 mL,Banfi Products Corp,Chile\n"
    ).encode("utf-8")

    response = client.post(
        "/api/sheets/parse",
        files={"file": ("sample_batch.csv", csv_bytes, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 1
    assert "brand_name" in body["columns"]
    row = body["rows"][0]
    assert row["image"] == "coyam.png"
    assert row["brand_name"] == "Coyam"
    assert row["class_type"] == "Red Wine"
    assert row["beverage_class"] == "wine"


def test_sheet_parse_xlsx() -> None:
    from openpyxl import Workbook

    app.dependency_overrides.clear()
    client = TestClient(app)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["image", "brand", "abv", "net"])
    worksheet.append(["monkey_47.png", "Monkey 47", "47%", "500 mL"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    response = client.post(
        "/api/sheets/parse",
        files={
            "file": (
                "sample_batch.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 1
    row = body["rows"][0]
    assert row["image"] == "monkey_47.png"
    assert row["brand_name"] == "Monkey 47"
    assert row["alcohol_content"] == "47%"
    assert row["net_contents"] == "500 mL"


def test_sheet_parse_rejects_unknown_extension() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.post(
        "/api/sheets/parse",
        files={"file": ("data.txt", b"image,brand_name\n", "text/plain")},
    )

    assert response.status_code == 400


def test_sheet_template_download() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/api/sheets/template.csv")

    assert response.status_code == 200
    assert "image" in response.text
    assert "brand_name" in response.text
    assert "country_of_origin" in response.text


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


def test_result_guard_fails_non_abv_text_for_alcohol_content() -> None:
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

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: alcohol content."
    assert result.fields.alcohol_content.status == "fail"
    assert "alcohol-content" in result.fields.alcohol_content.reason


def test_result_guard_passes_table_wine_alcohol_content_exception() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.fail,
            summary="Model failed the field.",
            fields=make_fields(
                alcohol_content=make_field(
                    status="fail",
                    application_value="Not required for table wine designation",
                    label_value="Not required for table wine designation",
                    reason="Alcohol content could not be confidently extracted as an alcohol-content value.",
                )
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.alcohol_content.status == "pass"
    assert result.fields.alcohol_content.reason == (
        "Alcohol content is not required for this table/light wine designation."
    )
