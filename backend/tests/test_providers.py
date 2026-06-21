import asyncio
import json


from app.core.settings import Settings
from app.models.application import ApplicationValues
from app.models.uploads import ValidatedUpload
from app.models.verification import (
    VerificationStatus,
)
from app.providers.base import ProviderError
from app.providers.local_provider import LocalModelVerificationProvider
from app.providers.multi_pass_provider import MultiPassVerificationProvider
from app.providers.openrouter_provider import OpenRouterVerificationProvider
from app.services.result_guard_service import (
    GOVERNMENT_WARNING_FULL_TEXT,
)
from app.services.verification_prompt_service import VerificationPromptService
from helpers import (
    PNG_BYTES,
    SpecialistRunner,
    make_provider_response,
    make_prompt_response_content,
)


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
    warning_schema = payload["format"]["properties"]["fields"]["properties"][
        "government_warning"
    ]
    assert "warning_heading_text" in warning_schema["required"]
    assert warning_schema["properties"]["warning_block_visible"]["type"] == "boolean"
    assert (
        "warning_heading_text"
        not in payload["format"]["properties"]["fields"]["properties"][
            "artifact_legibility"
        ]["properties"]
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


def test_local_provider_normalizes_blank_artifact_legibility_label_value(monkeypatch) -> None:
    prompt = VerificationPromptService().build_specialist_prompts()[0]
    content = make_prompt_response_content(prompt.requested_fields)
    content["fields"]["artifact_legibility"]["status"] = "pass"
    content["fields"]["artifact_legibility"]["label_value"] = ""
    content["fields"]["artifact_legibility"]["reason"] = "No label text visible."
    response_content = json.dumps(content)

    class AsyncClientStub:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url, headers, json):
            return make_provider_response(
                json_body={"message": {"content": response_content}},
            )

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

    assert result.fields["artifact_legibility"].status == "pass"
    assert result.fields["artifact_legibility"].label_value == "Label artwork readable"
    assert result.fields["artifact_legibility"].reason == "Local model marked the label artwork readable."


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
