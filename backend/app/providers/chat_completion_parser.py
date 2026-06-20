import json
import time
from typing import Mapping

import httpx

from app.models.verification import (
    ModelMetadata,
    VerificationEvidence,
    VerificationFieldResult,
    VerificationFields,
    VerificationStatus,
)
from app.providers.base import ProviderError, ProviderResult
from app.providers.base import ProviderPromptResult


VERIFICATION_FIELD_NAMES = (
    "artifact_legibility",
    "brand_name",
    "class_type_designation",
    "alcohol_content",
    "net_contents",
    "name_address",
    "country_of_origin",
    "color_additive_disclosure",
    "government_warning",
)


def parse_chat_completion_response(
    *,
    response: httpx.Response,
    model: str,
    provider_name: str,
    provider_mode: str,
    started: float,
    attempted_models: list[str],
    deterministic_fields: Mapping[str, dict] | None = None,
) -> ProviderResult:
    try:
        parsed = _parse_response_content(response)
        fields = _parse_fields(parsed["fields"], deterministic_fields or {})
        return ProviderResult(
            status=VerificationStatus(parsed["status"]),
            summary=parsed["summary"],
            fields=fields,
            model=_model_metadata(
                model=model,
                provider_name=provider_name,
                provider_mode=provider_mode,
                started=started,
                attempted_models=attempted_models,
            ),
        )
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ProviderError(
            "The verification service returned an unreadable response. Please try again."
        ) from exc


def parse_chat_completion_prompt_response(
    *,
    response: httpx.Response,
    model: str,
    provider_name: str,
    provider_mode: str,
    started: float,
    attempted_models: list[str],
    requested_fields: tuple[str, ...],
) -> ProviderPromptResult:
    try:
        parsed = _parse_response_content(response)
        raw_fields = parsed["fields"]
        fields = {
            field_name: _parse_field(raw_fields[field_name])
            for field_name in requested_fields
        }
        return ProviderPromptResult(
            status=VerificationStatus(parsed["status"]),
            summary=parsed["summary"],
            fields=fields,
            model=_model_metadata(
                model=model,
                provider_name=provider_name,
                provider_mode=provider_mode,
                started=started,
                attempted_models=attempted_models,
            ),
        )
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ProviderError(
            "The verification service returned an unreadable response. Please try again."
        ) from exc


def _parse_response_content(response: httpx.Response) -> dict:
    body = response.json()
    if "choices" in body:
        content = body["choices"][0]["message"]["content"]
    else:
        content = body["message"]["content"]
    parsed = json.loads(content) if isinstance(content, str) else content
    if not isinstance(parsed, dict):
        raise TypeError("Chat completion content did not contain a JSON object.")
    return parsed


def _model_metadata(
    *,
    model: str,
    provider_name: str,
    provider_mode: str,
    started: float,
    attempted_models: list[str],
) -> ModelMetadata:
    duration_ms = int((time.perf_counter() - started) * 1000)
    return ModelMetadata(
        provider=provider_name,
        model=model,
        provider_mode=provider_mode,
        duration_ms=duration_ms,
        fallback_attempts=max(0, len(attempted_models) - 1),
        attempted_models=attempted_models,
    )


def _parse_fields(raw_fields: dict, deterministic_fields: Mapping[str, dict]) -> VerificationFields:
    def build_field(field_name: str) -> VerificationFieldResult:
        field = deterministic_fields.get(field_name) or raw_fields[field_name]
        return _parse_field(field)

    return VerificationFields(
        **{field_name: build_field(field_name) for field_name in VERIFICATION_FIELD_NAMES}
    )


def _parse_field(field: dict) -> VerificationFieldResult:
    evidence = [_parse_evidence_item(item) for item in field.get("evidence", [])]
    return VerificationFieldResult(
        status=field["status"],
        application_value=field.get("application_value"),
        label_value=field.get("label_value") or field.get("extracted_value"),
        reason=field.get("reason") or field.get("explanation", ""),
        evidence=evidence,
    )


def _parse_evidence_item(item: object) -> VerificationEvidence:
    if isinstance(item, str):
        return VerificationEvidence(summary=item)
    if isinstance(item, dict):
        return VerificationEvidence(
            summary=str(item.get("summary") or item.get("text") or item.get("message") or ""),
            source_excerpt=item.get("source_excerpt") or item.get("excerpt"),
        )
    return VerificationEvidence(summary=str(item))
