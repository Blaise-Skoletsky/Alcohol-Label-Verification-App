import json
import time

import httpx

from app.core.settings import Settings
from app.providers.chat_completion_parser import (
    parse_chat_completion_prompt_response,
    parse_chat_completion_response,
)
from app.providers.openrouter_provider import OpenRouterVerificationProvider
from app.services.result_guard_service import (
    GOVERNMENT_WARNING_BODY,
    GOVERNMENT_WARNING_FULL_TEXT,
)
from helpers import (
    make_fields,
    make_prompt_response_content,
    make_raw_warning_field,
)


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


def test_parser_accepts_government_warning_extraction_fields_internally() -> None:
    requested_fields = ("government_warning",)
    response = httpx.Response(
        status_code=200,
        json={
            "message": {
                "content": json.dumps(
                    {
                        "status": "pass",
                        "summary": "Warning passed.",
                        "fields": {
                            "government_warning": make_raw_warning_field(
                                warning_heading_text="GOVERNMENT WARNING:",
                                warning_body_text=GOVERNMENT_WARNING_BODY,
                                warning_full_text=GOVERNMENT_WARNING_FULL_TEXT,
                            )
                        },
                    }
                )
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

    warning = result.fields["government_warning"]
    assert warning.warning_extraction is not None
    assert warning.warning_extraction.heading_text == "GOVERNMENT WARNING:"
    assert warning.warning_extraction.body_text == GOVERNMENT_WARNING_BODY
    assert warning.model_dump() == {
        "status": "pass",
        "application_value": "Required federal government warning",
        "label_value": GOVERNMENT_WARNING_FULL_TEXT,
        "reason": "Present.",
        "evidence": [],
    }


def test_parser_ignores_warning_extraction_fields_on_other_fields() -> None:
    requested_fields = ("brand_name",)
    response = httpx.Response(
        status_code=200,
        json={
            "message": {
                "content": json.dumps(
                    {
                        "status": "pass",
                        "summary": "Brand passed.",
                        "fields": {
                            "brand_name": {
                                "status": "pass",
                                "application_value": "Cleo",
                                "label_value": "Cleo",
                                "reason": "Brand matched.",
                                "evidence": [],
                                "warning_heading_text": "government warning:",
                            }
                        },
                    }
                )
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

    brand = result.fields["brand_name"]
    assert brand.status == "pass"
    assert brand.label_value == "Cleo"
    assert brand.warning_extraction is None


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
