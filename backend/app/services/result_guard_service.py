import re

from app.models.verification import (
    VerificationFieldResult,
    VerificationFields,
    VerificationStatus,
)
from app.providers.base import ProviderResult


class ResultGuardService:
    def enforce(self, result: ProviderResult) -> ProviderResult:
        guarded_fields = VerificationFields(
            artifact_legibility=self._guard_required_values(result.fields.artifact_legibility),
            brand_name=self._guard_required_values(result.fields.brand_name),
            class_type_designation=self._guard_required_values(result.fields.class_type_designation),
            alcohol_content=self._guard_alcohol_content(result.fields.alcohol_content),
            net_contents=self._guard_required_values(result.fields.net_contents),
            name_address=self._guard_required_values(result.fields.name_address),
            country_of_origin=self._guard_required_values(result.fields.country_of_origin),
            government_warning=self._guard_required_values(result.fields.government_warning),
        )
        overall_status = self._overall_status(guarded_fields)
        return ProviderResult(
            status=overall_status,
            summary=self._summary(result.summary, overall_status, guarded_fields),
            fields=guarded_fields,
            model=result.model,
        )

    def _guard_required_values(self, field: VerificationFieldResult) -> VerificationFieldResult:
        if field.status == "pass" and (
            not self._has_reviewable_value(field.application_value)
            or not self._has_reviewable_value(field.label_value)
        ):
            return field.model_copy(
                update={
                    "status": "needs_review",
                    "reason": "A passing field must include reviewable application and label values.",
                }
            )
        return field

    def _guard_alcohol_content(self, field: VerificationFieldResult) -> VerificationFieldResult:
        if field.status == "pass" and self._has_clear_exception(field):
            return field

        application_abv = self._extract_abv(field.application_value)
        label_abv = self._extract_abv(field.label_value)

        if application_abv is None or label_abv is None:
            return field.model_copy(
                update={
                    "status": "needs_review",
                    "reason": "Alcohol content could not be confidently extracted as an alcohol-content value.",
                }
            )

        if abs(application_abv - label_abv) > 0.001:
            return field.model_copy(
                update={
                    "status": "fail",
                    "reason": "Application alcohol content and label alcohol content do not match exactly.",
                }
            )

        return field.model_copy(update={"status": "pass"})

    def _has_reviewable_value(self, value: str | None) -> bool:
        if not value:
            return False
        normalized = value.strip().lower()
        if not normalized:
            return False
        return normalized not in {"n/a", "na", "none", "unknown", "unreadable", "missing"}

    def _has_clear_exception(self, field: VerificationFieldResult) -> bool:
        combined = " ".join(
            value.lower()
            for value in [
                field.application_value or "",
                field.label_value or "",
                field.reason or "",
            ]
        )
        return "exception" in combined and any(
            marker in combined for marker in ["not required", "legitimately absent", "exempt"]
        )

    def _extract_abv(self, value: str | None) -> float | None:
        if not value:
            return None

        normalized = value.strip().lower()
        proof_match = re.search(r"(\d+(?:\.\d+)?)\s*proof\b", normalized)
        if proof_match:
            return float(proof_match.group(1)) / 2

        if re.search(r"\d", normalized) and (
            "%" in normalized
            or "alc" in normalized
            or "alcohol" in normalized
            or "abv" in normalized
            or self._is_bare_number(normalized)
        ):
            number_match = re.search(r"\d+(?:\.\d+)?", normalized)
            if number_match:
                return float(number_match.group(0))

        return None

    def _is_bare_number(self, value: str) -> bool:
        return re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", value) is not None

    def _overall_status(self, fields: VerificationFields) -> VerificationStatus:
        field_statuses = [
            fields.artifact_legibility.status,
            fields.brand_name.status,
            fields.class_type_designation.status,
            fields.alcohol_content.status,
            fields.net_contents.status,
            fields.name_address.status,
            fields.country_of_origin.status,
            fields.government_warning.status,
        ]
        if "fail" in field_statuses:
            return VerificationStatus.fail
        if "needs_review" in field_statuses:
            return VerificationStatus.needs_review
        return VerificationStatus.pass_status

    def _summary(
        self,
        original_summary: str,
        overall_status: VerificationStatus,
        fields: VerificationFields,
    ) -> str:
        if overall_status == VerificationStatus.pass_status:
            return original_summary

        failed_fields = self._field_labels(fields, "fail")
        if failed_fields:
            return f"Required checks failed: {', '.join(failed_fields)}."

        review_fields = self._field_labels(fields, "needs_review")
        if review_fields:
            return f"Manual review needed: {', '.join(review_fields)}."

        return original_summary

    def _field_labels(self, fields: VerificationFields, status: str) -> list[str]:
        labels = {
            "artifact_legibility": "artifact legibility",
            "brand_name": "brand name",
            "class_type_designation": "class/type designation",
            "alcohol_content": "alcohol content",
            "net_contents": "net contents",
            "name_address": "name/address",
            "country_of_origin": "country of origin",
            "government_warning": "government warning",
        }
        dumped = fields.model_dump()
        return [label for field_name, label in labels.items() if dumped[field_name]["status"] == status]
