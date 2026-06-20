import asyncio
import json
import time

import httpx
from fastapi.testclient import TestClient

from app.core.dependencies import get_batch_service, get_settings, get_verification_service
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
from app.providers.base import ProviderError, ProviderPromptResult, ProviderResult
from app.providers.chat_completion_parser import (
    parse_chat_completion_prompt_response,
    parse_chat_completion_response,
)
from app.providers.multi_pass_provider import MultiPassVerificationProvider
from app.services.batch_service import BatchService
from app.services.result_guard_service import (
    GOVERNMENT_WARNING_FULL_TEXT,
    ResultGuardService,
)
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
        "government_warning": make_field(
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
                    "government_warning": make_field(
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
    app.dependency_overrides[get_settings] = lambda: Settings(provider_mode="local")
    client = TestClient(app)

    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.json()
    assert body["provider_mode"] == "local"
    assert body["environment"] == "development"
    assert body["demo_batch_manifest_url"] is None
    assert body["tutorial_video_url"] is None
    assert body["max_batch_labels"] == 350
    assert ".png" in body["allowed_file_types"]
    assert ".pdf" not in body["allowed_file_types"]
    assert "openrouter_api_key" not in body
    app.dependency_overrides.clear()


def test_config_endpoint_exposes_demo_manifest_only_in_production() -> None:
    app.dependency_overrides.clear()
    app.dependency_overrides[get_settings] = lambda: Settings(
        provider_mode="local",
        environment="development",
        demo_batch_manifest_url="https://example.test/manifest.json",
        tutorial_video_url="https://example.test/tutorial.mp4",
    )
    client = TestClient(app)

    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "development"
    assert body["demo_batch_manifest_url"] is None
    assert body["tutorial_video_url"] is None

    app.dependency_overrides[get_settings] = lambda: Settings(
        provider_mode="local",
        environment="production",
        demo_batch_manifest_url="https://example.test/manifest.json",
        tutorial_video_url="https://example.test/tutorial.mp4",
    )

    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "production"
    assert body["demo_batch_manifest_url"] == "https://example.test/manifest.json"
    assert body["tutorial_video_url"] == "https://example.test/tutorial.mp4"
    app.dependency_overrides.clear()


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


def test_openrouter_payload_does_not_include_local_structured_output_fields() -> None:
    provider = OpenRouterVerificationProvider(Settings(openrouter_api_key="test-key"))
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    payload = provider._build_payload(model="google/gemini-3.5-flash", upload=upload)

    assert set(payload) == {
        "model",
        "messages",
        "response_format",
        "temperature",
        "max_tokens",
        "stream",
    }
    assert payload["response_format"] == {"type": "json_object"}
    assert "format" not in payload
    assert "options" not in payload


def test_local_provider_payload_uses_ollama_native_schema_and_image() -> None:
    provider = LocalModelVerificationProvider(
        Settings(provider_mode="local", local_model_name="qwen2.5-vl-7b-instruct")
    )
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )
    prompt = VerificationPromptService().build_specialist_prompts()[0]

    payload = provider._build_payload(upload=upload, prompt=prompt)

    assert payload["model"] == "qwen2.5-vl-7b-instruct"
    assert payload["messages"][0]["content"] == prompt.system_instruction
    assert payload["messages"][1]["content"] == prompt.user_instruction
    assert payload["messages"][1]["images"] == ["iVBORw0KGgp0ZXN0LXBuZw=="]
    assert payload["format"]["properties"]["fields"]["required"] == list(prompt.requested_fields)
    assert set(payload["format"]["properties"]["fields"]["properties"]) == set(
        prompt.requested_fields
    )
    assert "response_format" not in payload
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
    assert system_text.startswith("You verify TTB-style alcohol label artwork")
    assert "TTB-style alcohol label artwork" in system_text
    assert "artifact_legibility" in system_text
    assert "brand_name" in system_text
    assert "class_type_designation" in system_text
    assert "alcohol_content" in system_text
    assert "net_contents" in system_text
    assert "name_address" in system_text
    assert "country_of_origin" in system_text
    assert "government_warning" in system_text
    assert "Each field object must be" in system_text
    assert "Requested fields: artifact_legibility" in system_text
    assert "application_value='Required federal government warning'" in system_text
    assert "APPLICATION_VALUES_JSON" in system_text
    assert "The image is label artwork only" in system_text
    assert "never extract application values from it" in system_text
    assert "application_value='N/A - text entry form'" in system_text
    assert "FIELD 1 - artifact_legibility" in system_text
    assert "decimal comma = decimal point" in system_text
    assert "heading words GOVERNMENT WARNING in all caps" in system_text
    assert "missing, changed, reordered, or paraphrased words" in system_text
    assert "Treat punctuation, spacing, line breaks, and the colon after WARNING" in system_text
    assert "do not fail solely because the colon is missing" in system_text
    assert "including numbering and every required word" in system_text
    assert "sentence case or all" in system_text
    assert "lowercase, title-case, or mixed-case heading" in system_text
    assert "transcribe the full visible warning statement" in system_text
    assert "preserving heading case and punctuation when visible" in system_text
    assert "Never rewrite a lowercase, title-case, or mixed-case heading into all caps" in system_text
    assert "inferred from" in system_text
    assert "regulatory knowledge" in system_text
    assert "Review the attached label artwork image using the system rules." in user_text
    assert "APPLICATION_VALUES_JSON" in user_text
    assert '"brand_name": "{{brand_name}}"' in user_text
    assert '"beverage_class": "{{beverage_class}}"' in user_text
    assert "government_warning" not in user_text.split("APPLICATION_VALUES_JSON:")[1]


def test_openrouter_malformed_schema_does_not_retry_same_model(monkeypatch) -> None:
    calls = []

    class AsyncClientStub:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url, headers, json):
            calls.append(json)
            return make_provider_response(
                json_body={"choices": [{"message": {"content": "not-json"}}]}
            )

    monkeypatch.setattr("app.providers.openrouter_provider.httpx.AsyncClient", AsyncClientStub)
    provider = OpenRouterVerificationProvider(
        Settings(
            openrouter_api_key="test-key",
            openrouter_model_primary="test-model",
            openrouter_model_fallbacks="",
        )
    )
    prompt = VerificationPromptService().build_specialist_prompts()[0]
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    try:
        asyncio.run(provider.run_prompt(upload=upload, prompt=prompt, prompt_name=prompt.name))
    except ProviderError:
        pass
    else:
        raise AssertionError("Expected malformed OpenRouter response to raise ProviderError.")

    assert len(calls) == 1


def test_local_malformed_schema_retries_once_with_same_prompt(monkeypatch) -> None:
    calls = []
    prompt = VerificationPromptService().build_specialist_prompts()[0]
    responses = [
        make_provider_response(json_body={"message": {"content": "not-json"}}),
        make_provider_response(
            json_body={
                "message": {
                    "content": json.dumps(make_prompt_response_content(prompt.requested_fields))
                }
            },
        ),
    ]

    class AsyncClientStub:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url, headers, json):
            calls.append(json)
            return responses.pop(0)

    monkeypatch.setattr("app.providers.local_provider.httpx.AsyncClient", AsyncClientStub)
    provider = LocalModelVerificationProvider(
        Settings(provider_mode="local", local_model_name="qwen2.5vl-alv:latest")
    )
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    result = asyncio.run(
        provider.run_prompt(upload=upload, prompt=prompt, prompt_name=prompt.name)
    )

    assert result.status == VerificationStatus.pass_status
    assert len(calls) == 2
    assert calls[0]["messages"] == calls[1]["messages"]
    assert calls[0]["format"] == calls[1]["format"]


def test_local_schema_retry_can_be_disabled(monkeypatch) -> None:
    calls = []
    prompt = VerificationPromptService().build_specialist_prompts()[0]

    class AsyncClientStub:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url, headers, json):
            calls.append(json)
            return make_provider_response(json_body={"message": {"content": "not-json"}})

    monkeypatch.setattr("app.providers.local_provider.httpx.AsyncClient", AsyncClientStub)
    monkeypatch.setattr("app.providers.local_provider.LOCAL_SCHEMA_RETRY_COUNT", 0)
    provider = LocalModelVerificationProvider(
        Settings(
            provider_mode="local",
            local_model_name="qwen2.5vl-alv:latest",
        )
    )
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    try:
        asyncio.run(provider.run_prompt(upload=upload, prompt=prompt, prompt_name=prompt.name))
    except ProviderError:
        pass
    else:
        raise AssertionError("Expected malformed local response to raise ProviderError.")

    assert len(calls) == 1


def test_local_malformed_schema_logs_capped_diagnostics(monkeypatch, caplog) -> None:
    prompt = VerificationPromptService().build_specialist_prompts()[0]
    malformed_content = "not-json-" + ("x" * 50)

    class AsyncClientStub:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url, headers, json):
            return make_provider_response(
                json_body={"message": {"content": malformed_content}},
            )

    monkeypatch.setattr("app.providers.local_provider.httpx.AsyncClient", AsyncClientStub)
    monkeypatch.setattr("app.providers.local_provider.LOCAL_SCHEMA_RETRY_COUNT", 0)
    monkeypatch.setattr("app.providers.local_provider.LOCAL_MODEL_DIAGNOSTIC_PREVIEW_CHARS", 12)
    caplog.set_level("WARNING", logger="alv.local_provider")
    provider = LocalModelVerificationProvider(
        Settings(
            provider_mode="local",
            local_model_name="qwen2.5vl-alv:latest",
        )
    )
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    try:
        asyncio.run(provider.run_prompt(upload=upload, prompt=prompt, prompt_name=prompt.name))
    except ProviderError:
        pass
    else:
        raise AssertionError("Expected malformed local response to raise ProviderError.")

    log_message = caplog.records[-1].getMessage()
    assert "specialist=warning_legibility" in log_message
    assert "artifact_legibility" in log_message
    assert "qwen2.5vl-alv:latest" in log_message
    assert "JSONDecodeError" in log_message
    assert "response_shape=" in log_message
    assert "response_preview=not-json-xxx" in log_message
    assert "not-json-xxxx" not in log_message


def test_verification_prompt_accepts_application_values() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "Stone's Throw",
            "beverage_class": "wine",
            "class_type_designation": "Wine",
            "alcohol_content": "13.5% ABV",
            "net_contents": "750 mL",
            "name_address": "Example Producer, Napa, CA",
            "country_of_origin": "Domestic",
        }
    )

    assert "\"brand_name\": \"Stone's Throw\"" in prompt.user_instruction
    assert '"beverage_class": "wine"' in prompt.user_instruction
    assert '"class_type_designation": "Wine"' in prompt.user_instruction
    assert '"alcohol_content": "13.5% ABV"' in prompt.user_instruction
    assert "The image is label artwork only" in prompt.system_instruction
    assert "never extract application values from it" in prompt.system_instruction
    assert "application_value='N/A - text entry form'" in prompt.system_instruction


def test_prompt_skips_table_wine_alcohol_content_when_not_required() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "Example",
            "beverage_class": "wine",
            "class_type_designation": "Table Wine",
            "alcohol_content": "",
            "net_contents": "750 mL",
            "name_address": "Example Producer, Napa, CA",
            "country_of_origin": "Domestic",
        }
    )

    assert "alcohol_content" not in prompt.requested_fields
    assert "FIELD 4 - alcohol_content" not in prompt.system_instruction
    assert "Requested fields:" in prompt.system_instruction
    assert "alcohol_content" not in prompt.system_instruction.split("Requested fields: ")[1]
    assert prompt.deterministic_fields["alcohol_content"]["status"] == "pass"
    assert "Backend applicability" in prompt.deterministic_fields["alcohol_content"]["reason"]


def test_prompt_allows_specific_wine_designation_for_table_wine_class_type() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "3 Steves Winery",
            "beverage_class": "wine",
            "class_type_designation": "Table Wine",
            "alcohol_content": "",
            "net_contents": "750 mL",
            "name_address": "Bottled By 3 Steves Winery, Livermore, CA",
            "country_of_origin": "Domestic",
        }
    )

    assert "If" in prompt.system_instruction
    assert "application says Table Wine or Light Wine" in prompt.system_instruction
    assert "Chardonnay" in prompt.system_instruction
    assert "no conflicting" in prompt.system_instruction
    assert "class appears" in prompt.system_instruction


def test_prompt_allows_class_type_modifiers_and_obvious_spelling_variants() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "Blue Ridge",
            "beverage_class": "wine",
            "class_type_designation": "White grape wine with artificial flavor",
            "alcohol_content": "Alc. 11% by vol.",
            "net_contents": "750 mL",
            "name_address": "Vinted and bottled by Blue Ridge Winery, LLC",
            "country_of_origin": "Domestic",
        }
    )

    assert "Harmless descriptive modifiers" in prompt.system_instruction
    assert "off dry" in prompt.system_instruction
    assert "OCR/label spelling variants" in prompt.system_instruction
    assert "artifical matching artificial" in prompt.system_instruction


def test_prompt_requires_beverage_class_to_match_label_class_family() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "Example",
            "beverage_class": "malt",
            "class_type_designation": "Beer",
            "alcohol_content": "5% by vol.",
            "net_contents": "12 fl. oz.",
            "name_address": "Example Brewery, Portland, OR",
            "country_of_origin": "Domestic",
        }
    )

    assert "Compare both APPLICATION_VALUES_JSON.beverage_class" in prompt.system_instruction
    assert "The broad beverage class must line up first" in prompt.system_instruction
    assert "wine labels cannot pass" in prompt.system_instruction
    assert "malt/beer applications" in prompt.system_instruction
    assert "wine label" in prompt.system_instruction
    assert "Beer/Ale/Malt" in prompt.system_instruction
    assert "fails this field" in prompt.system_instruction


def test_prompt_forbids_net_contents_inference() -> None:
    prompt = VerificationPromptService().build_prompt()

    assert "Do not infer common bottle sizes" in prompt.system_instruction
    assert "barcode" in prompt.system_instruction
    assert "unless the same quantity/unit is visible" in prompt.system_instruction


def test_prompt_requires_word_for_word_government_warning() -> None:
    prompt = VerificationPromptService().build_prompt()

    assert "required federal warning words in order" in prompt.system_instruction
    assert "missing any required word" in prompt.system_instruction
    assert "changed/reordered/paraphrased wording" in prompt.system_instruction
    assert "heading words" in prompt.system_instruction
    assert "GOVERNMENT WARNING are all caps" in prompt.system_instruction
    assert "colon after WARNING" in prompt.system_instruction
    assert "do not fail solely because the colon is missing" in prompt.system_instruction
    assert "sentence case or all" in prompt.system_instruction
    assert "mixed-case heading" in prompt.system_instruction
    assert "return the full visible warning statement when readable" in prompt.system_instruction
    assert "only the heading" in prompt.system_instruction
    assert "non-exact heading" in prompt.system_instruction
    assert "fail the" in prompt.system_instruction


def test_prompt_requires_distilled_spirits_alcohol_content() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "beverage_class": "spirits",
            "class_type_designation": "Vodka",
            "alcohol_content": "",
            "country_of_origin": "Domestic",
        }
    )

    assert "alcohol_content" in prompt.requested_fields
    assert "Alcohol content is required or was submitted for comparison." in prompt.system_instruction
    assert "distilled spirits" in prompt.system_instruction


def test_prompt_skips_malt_alcohol_content_without_added_nonbeverage_trigger() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "beverage_class": "malt",
            "class_type_designation": "Ale",
            "alcohol_content": "",
            "country_of_origin": "Domestic",
            "malt_added_nonbeverage_alcohol": False,
        }
    )

    assert "alcohol_content" not in prompt.requested_fields
    assert prompt.deterministic_fields["alcohol_content"]["status"] == "pass"


def test_prompt_requires_malt_alcohol_content_with_added_nonbeverage_trigger() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "beverage_class": "malt",
            "class_type_designation": "Ale",
            "alcohol_content": "",
            "country_of_origin": "Domestic",
            "malt_added_nonbeverage_alcohol": True,
        }
    )

    assert "alcohol_content" in prompt.requested_fields
    assert "Alcohol content is required" in prompt.system_instruction


def test_prompt_checks_malt_color_additive_only_when_applicable() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "beverage_class": "malt",
            "class_type_designation": "Ale",
            "country_of_origin": "Domestic",
            "malt_color_additive_applicable": True,
        }
    )

    assert "color_additive_disclosure" in prompt.requested_fields
    assert "FIELD 8 - color_additive_disclosure" in prompt.system_instruction


def test_prompt_targets_domestic_country_of_origin_check() -> None:
    prompt = VerificationPromptService().build_prompt({"country_of_origin": "Domestic"})

    assert "Application says Domestic" in prompt.system_instruction
    assert "Product of" in prompt.system_instruction
    assert "does not show an imported origin" in prompt.system_instruction
    assert "No imported origin statement visible" in prompt.system_instruction
    assert "do not use N/A" in prompt.system_instruction


def test_prompt_targets_country_name_origin_check() -> None:
    prompt = VerificationPromptService().build_prompt({"country_of_origin": "Chile"})

    assert "Application provides a country name" in prompt.system_instruction
    assert "country conflicts" in prompt.system_instruction
    assert "Application country for this row: Chile" in prompt.system_instruction


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
            "malt_added_nonbeverage_alcohol": "false",
            "malt_color_additive_applicable": "false",
        },
    )

    assert response.status_code == 200
    values = service.last_application_values
    assert isinstance(values, ApplicationValues)
    assert values.brand_name == "Coyam"
    assert values.beverage_class == "wine"
    assert values.net_contents == "750 mL"
    assert values.country_of_origin == "Chile"
    assert values.malt_added_nonbeverage_alcohol is False
    assert values.malt_color_additive_applicable is False
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
                                    "color_additive_disclosure": {
                                        "status": "pass",
                                        "application_value": "Not Required",
                                        "label_value": "Not Required",
                                        "confidence": 1.0,
                                        "reason": "Backend applicability: Malt color additive disclosure is not required for this row.",
                                        "evidence": [],
                                    },
                                    "government_warning": {
                                        "status": "pass",
                                        "application_value": "Required federal government warning",
                                        "label_value": GOVERNMENT_WARNING_FULL_TEXT,
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


def test_parser_accepts_ollama_native_message_content() -> None:
    requested_fields = ("brand_name",)
    response = httpx.Response(
        status_code=200,
        json={
            "message": {
                "content": json.dumps(make_prompt_response_content(requested_fields))
            }
        },
    )

    result = parse_chat_completion_prompt_response(
        response=response,
        model="qwen2.5vl-alv:latest",
        provider_name="local",
        provider_mode="local",
        started=time.perf_counter(),
        attempted_models=["qwen2.5vl-alv:latest"],
        requested_fields=requested_fields,
    )

    assert result.fields["brand_name"].status == "pass"
    assert result.model.provider == "local"


def test_parser_fills_backend_deterministic_fields() -> None:
    raw_fields = make_fields().model_dump()
    raw_fields.pop("alcohol_content")
    deterministic_fields = {
        "alcohol_content": {
            "status": "pass",
            "application_value": "Not Required",
            "label_value": "Not Required",
            "reason": (
                "Backend applicability: Alcohol content is not required for this "
                "table/light wine designation."
            ),
            "evidence": [],
        }
    }
    response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "status": "pass",
                                "summary": "Requested fields passed.",
                                "fields": raw_fields,
                            }
                        )
                    }
                }
            ]
        },
    )

    result = parse_chat_completion_response(
        response=response,
        model="test-model",
        provider_name="test",
        provider_mode="local",
        started=time.perf_counter(),
        attempted_models=["test-model"],
        deterministic_fields=deterministic_fields,
    )

    assert result.fields.alcohol_content.status == "pass"
    assert result.fields.alcohol_content.application_value == "Not Required"
    assert "Backend applicability" in result.fields.alcohol_content.reason


def test_multi_pass_provider_runs_three_specialists_and_merges_fields() -> None:
    runner = SpecialistRunner()
    provider = MultiPassVerificationProvider(
        runner=runner,
        prompt_service=VerificationPromptService(),
    )
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    result = asyncio.run(
        provider.verify(
            upload=upload,
            item_id="sample",
            application_values=ApplicationValues(
                beverage_class="spirits",
                class_type_designation="Gin",
                alcohol_content="40% Alc/Vol",
                country_of_origin="Domestic",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.artifact_legibility.status == "pass"
    assert result.fields.government_warning.label_value == GOVERNMENT_WARNING_FULL_TEXT
    assert result.fields.color_additive_disclosure.application_value == "Not Required"
    assert result.model.model.startswith("multi-pass(")
    assert [name for name, _fields in runner.calls] == [
        "warning_legibility",
        "product_fields",
        "origin_fields",
    ]
    assert runner.calls[0][1] == ("artifact_legibility", "government_warning")
    assert runner.calls[1][1] == (
        "brand_name",
        "class_type_designation",
        "alcohol_content",
        "net_contents",
    )
    assert runner.calls[2][1] == ("name_address", "country_of_origin")


def test_multi_pass_provider_fails_when_specialist_omits_required_field() -> None:
    runner = SpecialistRunner(omit_fields={"government_warning"})
    provider = MultiPassVerificationProvider(
        runner=runner,
        prompt_service=VerificationPromptService(),
    )
    upload = ValidatedUpload(
        filename="sample.png",
        content_type="image/png",
        extension=".png",
        content=PNG_BYTES,
    )

    try:
        asyncio.run(provider.verify(upload=upload, item_id="sample"))
    except ProviderError as exc:
        assert "government_warning" in exc.message
    else:
        raise AssertionError("Expected missing specialist field to raise ProviderError.")


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


def test_result_guard_fails_passing_class_type_when_beverage_class_conflicts() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "class_type_designation": make_field(
                        application_value="malt / Beer",
                        label_value="wine / Cabernet Sauvignon",
                        reason="Model incorrectly accepted a class mismatch.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: class/type designation."
    assert result.fields.class_type_designation.status == "fail"
    assert "beverage class" in result.fields.class_type_designation.reason


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


def test_result_guard_passes_optional_malt_omission_without_trigger() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model passed optional malt omission.",
            fields=make_fields(
                alcohol_content=make_field(
                    application_value="Not required for malt beverage",
                    label_value="Not required for malt beverage",
                    reason=(
                        "Malt beverage alcohol content is federally optional; "
                        "no added nonbeverage alcohol trigger is visible."
                    ),
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


def test_result_guard_treats_decimal_comma_as_matching_abv() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.fail,
            summary="Model failed the field.",
            fields=make_fields(
                alcohol_content=make_field(
                    status="fail",
                    application_value="Alc. 14.5% by vol.",
                    label_value="ALC. 14,5% BY VOL.",
                    reason="Application alcohol content and label alcohol content do not match exactly.",
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


def test_result_guard_fails_mixed_case_government_warning_prefix() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_field(
                        application_value="Required federal government warning",
                        label_value=GOVERNMENT_WARNING_FULL_TEXT.replace(
                            "GOVERNMENT WARNING:", "Government Warning:"
                        ),
                        reason="Model incorrectly accepted title-case prefix.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: government warning."
    assert result.fields.government_warning.status == "fail"
    assert "heading words 'GOVERNMENT WARNING' are visible in all caps" in (
        result.fields.government_warning.reason
    )


def test_result_guard_fails_partial_government_warning_text() -> None:
    partial_warning = (
        "GOVERNMENT WARNING: (1) According to the Surgeon General, women should "
        "not drink alcoholic beverages during pregnancy. (2) Consumption of alcoholic "
        "beverages impairs your ability to drive a car or operate machinery."
    )
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_field(
                        application_value="Required federal government warning",
                        label_value=partial_warning,
                        reason="Model incorrectly accepted partial warning.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: government warning."
    assert result.fields.government_warning.status == "fail"
    assert "because" in result.fields.government_warning.reason


def test_result_guard_allows_warning_spacing_ocr_variants() -> None:
    compact_warning = (
        "GOVERNMENT WARNING (1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD "
        "NOT DRINK ALCOHOLIC BEVERAGES DURING PREGNANCY BECAUSE OF THE RISK "
        "OF BIRTH DEFECTS.(2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR "
        "ABILITY TO DRIVE A CAR OR OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS."
    )
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_field(
                        application_value="Required federal government warning",
                        label_value=compact_warning,
                        reason="Warning text is present.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.government_warning.status == "pass"


def test_result_guard_reports_first_warning_word_mismatch() -> None:
    altered_warning = GOVERNMENT_WARNING_FULL_TEXT.replace("Surgeon", "Attorney")
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_field(
                        application_value="Required federal government warning",
                        label_value=altered_warning,
                        reason="Model incorrectly accepted changed warning.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert "surgeon" in result.fields.government_warning.reason
    assert "attorney" in result.fields.government_warning.reason


def test_result_guard_allows_domestic_origin_without_origin_statement() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "country_of_origin": make_field(
                        application_value="Domestic",
                        label_value="N/A",
                        reason="No imported origin statement is visible on this domestic label.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.country_of_origin.status == "pass"
    assert result.fields.country_of_origin.label_value == "No imported origin statement visible"


def test_result_guard_allows_artifact_legibility_application_na() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "artifact_legibility": make_field(
                        application_value="N/A - text entry form",
                        label_value="Label artwork readable",
                        reason="Label artwork is readable.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.artifact_legibility.status == "pass"


def test_result_guard_fails_artifact_legibility_when_label_unreadable() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "artifact_legibility": make_field(
                        application_value="N/A - text entry form",
                        label_value="Unreadable",
                        reason="Model incorrectly accepted unreadable label artwork.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: artifact legibility."
    assert result.fields.artifact_legibility.status == "fail"
    assert "label image is readable" in result.fields.artifact_legibility.reason
