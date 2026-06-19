import json
import time

import httpx

from app.models.verification import (
    ModelMetadata,
    VerificationEvidence,
    VerificationFieldResult,
    VerificationFields,
    VerificationStatus,
)
from app.providers.base import ProviderError, ProviderResult


VERIFICATION_FIELD_NAMES = (
    "artifact_legibility",
    "brand_name",
    "class_type_designation",
    "alcohol_content",
    "net_contents",
    "name_address",
    "country_of_origin",
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
) -> ProviderResult:
    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else content
        fields = _parse_fields(parsed["fields"])
        duration_ms = int((time.perf_counter() - started) * 1000)
        return ProviderResult(
            status=VerificationStatus(parsed["status"]),
            summary=parsed["summary"],
            fields=fields,
            model=ModelMetadata(
                provider=provider_name,
                model=model,
                provider_mode=provider_mode,
                duration_ms=duration_ms,
                fallback_attempts=max(0, len(attempted_models) - 1),
                attempted_models=attempted_models,
            ),
        )
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ProviderError(
            "The verification service returned an unreadable response. Please try again."
        ) from exc


def _parse_fields(raw_fields: dict) -> VerificationFields:
    def build_field(field_name: str) -> VerificationFieldResult:
        field = raw_fields[field_name]
        evidence = [_parse_evidence_item(item) for item in field.get("evidence", [])]
        return VerificationFieldResult(
            status=field["status"],
            application_value=field.get("application_value"),
            label_value=field.get("label_value") or field.get("extracted_value"),
            reason=field.get("reason") or field.get("explanation", ""),
            evidence=evidence,
        )

    return VerificationFields(
        **{field_name: build_field(field_name) for field_name in VERIFICATION_FIELD_NAMES}
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
