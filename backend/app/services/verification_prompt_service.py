import json
import re
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class VerificationPrompt:
    system_instruction: str
    user_instruction: str
    requested_fields: tuple[str, ...]
    deterministic_fields: Mapping[str, dict]


@dataclass(frozen=True, slots=True)
class SpecialistVerificationPrompt:
    name: str
    system_instruction: str
    user_instruction: str
    requested_fields: tuple[str, ...]
    deterministic_fields: Mapping[str, dict]


@dataclass(frozen=True, slots=True)
class VerificationPlan:
    requested_fields: tuple[str, ...]
    deterministic_fields: Mapping[str, dict]
    alcohol_mode: str
    country_mode: str


ApplicationValues = Mapping[str, str | bool | None]


class VerificationPromptService:
    def build_prompt(self, application_values: ApplicationValues | None = None) -> VerificationPrompt:
        plan = self._build_plan(application_values)
        return VerificationPrompt(
            system_instruction=self._system(plan),
            user_instruction=self._user(application_values, plan),
            requested_fields=plan.requested_fields,
            deterministic_fields=plan.deterministic_fields,
        )

    def build_specialist_prompts(
        self,
        application_values: ApplicationValues | None = None,
    ) -> tuple[SpecialistVerificationPrompt, ...]:
        plan = self._build_plan(application_values)
        requested = set(plan.requested_fields)
        specialist_fields = {
            "warning_legibility": (
                "artifact_legibility",
                "government_warning",
            ),
            "product_fields": tuple(
                field
                for field in (
                    "brand_name",
                    "class_type_designation",
                    "alcohol_content",
                    "net_contents",
                    "color_additive_disclosure",
                )
                if field in requested
            ),
            "origin_fields": (
                "name_address",
                "country_of_origin",
            ),
        }
        return tuple(
            SpecialistVerificationPrompt(
                name=name,
                system_instruction=self._specialist_system(plan, name, fields),
                user_instruction=self._specialist_user(application_values, name, fields),
                requested_fields=fields,
                deterministic_fields=plan.deterministic_fields,
            )
            for name, fields in specialist_fields.items()
            if fields
        )

    # ------------------------------------------------------------------
    # System instruction
    # ------------------------------------------------------------------

    def _system(self, plan: VerificationPlan) -> str:
        sections = [
            (
                "You verify TTB-style alcohol label artwork against APPLICATION_VALUES_JSON. "
                "Return JSON only. The image is label artwork only; never extract application "
                "values from it. Use only visible label text for label_value and evidence."
            ),
            (
                "Government warning is strict and label-only: pass only when the label shows "
                "the exact federal warning statement word-for-word, with no missing, changed, "
                "reordered, or paraphrased words. The prefix 'GOVERNMENT WARNING:' must be "
                "all caps and visibly bold. For government_warning.label_value, transcribe the "
                "full visible warning statement when it is readable; preserve the prefix letter "
                "case exactly as printed and never rewrite a lowercase, title-case, or mixed-case "
                "prefix into all caps."
            ),
            self._task_intro(),
            self._overall_verdict_rules(),
            self._field_artifact_legibility(),
            self._field_brand_name(),
            self._field_class_type_designation(),
            self._field_alcohol_content(plan.alcohol_mode)
            if "alcohol_content" in plan.requested_fields
            else "",
            self._field_net_contents(),
            self._field_name_address(),
            self._field_country_of_origin(plan.country_mode),
            self._field_color_additive_disclosure()
            if "color_additive_disclosure" in plan.requested_fields
            else "",
            self._field_government_warning(),
            self._output_format(plan.requested_fields),
            self._hard_rules(),
        ]
        return "\n\n".join(section for section in sections if section)

    def _specialist_system(
        self,
        plan: VerificationPlan,
        specialist_name: str,
        requested_fields: tuple[str, ...],
    ) -> str:
        field_sections = {
            "artifact_legibility": self._field_artifact_legibility(),
            "brand_name": self._field_brand_name(),
            "class_type_designation": self._field_class_type_designation(),
            "alcohol_content": self._field_alcohol_content(plan.alcohol_mode),
            "net_contents": self._field_net_contents(),
            "name_address": self._field_name_address(),
            "country_of_origin": self._field_country_of_origin(plan.country_mode),
            "color_additive_disclosure": self._field_color_additive_disclosure(),
            "government_warning": self._field_government_warning(),
        }
        sections = [
            (
                "You are the "
                f"{specialist_name} specialist for TTB-style alcohol label artwork. "
                "Return JSON only. The image is label artwork only; never extract "
                "application values from it. Use only visible label text for "
                "label_value and evidence."
            ),
            (
                "Government warning is strict and label-only: pass only when the label shows "
                "the exact federal warning statement word-for-word, with no missing, changed, "
                "reordered, or paraphrased words. The prefix 'GOVERNMENT WARNING:' must be "
                "all caps and visibly bold. For government_warning.label_value, transcribe the "
                "full visible warning statement when it is readable; preserve the prefix letter "
                "case exactly as printed and never rewrite a lowercase, title-case, or mixed-case "
                "prefix into all caps."
            )
            if "government_warning" in requested_fields
            else "",
            self._task_intro(),
            self._overall_verdict_rules(),
            *[field_sections[field] for field in requested_fields],
            self._output_format(requested_fields),
            self._hard_rules(),
        ]
        return "\n\n".join(section for section in sections if section)

    # ------------------------------------------------------------------
    # User instruction
    # ------------------------------------------------------------------

    def _user(
        self,
        application_values: ApplicationValues | None,
        plan: VerificationPlan,
    ) -> str:
        return (
            "Review the attached label artwork image using the system rules. "
            "Compare only against APPLICATION_VALUES_JSON below. Use visible label text only for "
            "label_value and evidence; do not infer or fill missing label text from the rules. "
            "Return only the requested fields: "
            f"{', '.join(plan.requested_fields)}.\n\n"
            "APPLICATION_VALUES_JSON:\n"
            f"{self._application_values_json(application_values)}"
        )

    def _specialist_user(
        self,
        application_values: ApplicationValues | None,
        specialist_name: str,
        requested_fields: tuple[str, ...],
    ) -> str:
        return (
            "Review the attached label artwork image using only your assigned "
            f"{specialist_name} rules. Compare only against APPLICATION_VALUES_JSON below. "
            "Use visible label text only for label_value and evidence; do not infer or fill "
            "missing label text from the rules. Return only these field keys: "
            f"{', '.join(requested_fields)}.\n\n"
            "APPLICATION_VALUES_JSON:\n"
            f"{self._application_values_json(application_values)}"
        )

    def _application_values_json(self, application_values: ApplicationValues | None) -> str:
        values = {
            "brand_name": "{{brand_name}}",
            "beverage_class": "{{beverage_class}}",
            "class_type_designation": "{{class_type_designation}}",
            "alcohol_content": "{{alcohol_content}}",
            "net_contents": "{{net_contents}}",
            "name_address": "{{name_address}}",
            "country_of_origin": "{{country_of_origin}}",
            "malt_added_nonbeverage_alcohol": "{{malt_added_nonbeverage_alcohol}}",
            "malt_color_additive_applicable": "{{malt_color_additive_applicable}}",
        }
        if application_values is not None:
            values.update(
                {
                    key: "" if value is None else str(value)
                    for key, value in application_values.items()
                    if key in values
                }
            )
        return json.dumps(values, indent=2, sort_keys=True)

    # ------------------------------------------------------------------
    # Task intro
    # ------------------------------------------------------------------

    def _task_intro(self) -> str:
        return """\
TASK:
Compare APPLICATION_VALUES_JSON to the uploaded label image for only the requested
fields. For each requested field, copy the submitted value into application_value,
extract visible label text into label_value, then apply the PASS/FAIL rule. For
artifact_legibility use application_value='N/A - text entry form'. For
government_warning use application_value='Required federal government warning'."""

    # ------------------------------------------------------------------
    # Overall verdict rules
    # ------------------------------------------------------------------

    def _overall_verdict_rules(self) -> str:
        return """\
OVERALL VERDICT RULES:
Overall pass only if every returned field passes. Any failed field makes the
overall result fail. Fail fields with missing, unreadable, ambiguous, cut-off, or
insufficient label evidence. Do not make type-size or millimeter claims from the
image."""

    # ------------------------------------------------------------------
    # Field 1: artifact_legibility
    # ------------------------------------------------------------------

    def _field_artifact_legibility(self) -> str:
        return """\
FIELD 1 - artifact_legibility:
PASS: The image is label artwork/photo and the needed label text is readable.
Imperfect photos can pass when text remains readable.
FAIL: No label is visible, the image is not label artwork, or needed text is too
degraded, obscured, cut off, low-resolution, or ambiguous to extract. If this
fails, any field whose evidence cannot be read must also fail."""

    # ------------------------------------------------------------------
    # Field 2: brand_name
    # ------------------------------------------------------------------

    def _field_brand_name(self) -> str:
        return """\
FIELD 2 - brand_name:
Compare APPLICATION_VALUES_JSON.brand_name to the brand name printed on the label.
PASS: Same brand, allowing capitalization, punctuation, apostrophe, spacing, and
trademark-symbol differences.
FAIL: Different brand wording, brand absent, obscured brand text, or multiple
plausible brand names."""

    # ------------------------------------------------------------------
    # Field 3: class_type_designation
    # ------------------------------------------------------------------

    def _field_class_type_designation(self) -> str:
        return """\
FIELD 3 - class_type_designation:
Compare both APPLICATION_VALUES_JSON.beverage_class and
APPLICATION_VALUES_JSON.class_type_designation to the class/type printed on the
label. The broad beverage class must line up first: wine labels cannot pass for
malt/beer applications, malt/beer labels cannot pass for wine applications, and
distilled spirits labels cannot pass for wine or malt applications. In
application_value, include both submitted values, for example "malt / Beer". In
label_value, include the visible label class family and designation when
readable, for example "wine / Cabernet Sauvignon" or "malt / IPA".
PASS: The visible label class family matches APPLICATION_VALUES_JSON.beverage_class
and the visible type/designation is an exact/equivalent match or a recognized
member of that submitted broad class (spirits type, wine varietal/style,
beer/ale style). If the application says Table Wine or Light Wine, a visible
specific wine designation such as Chardonnay, Cabernet Sauvignon, red wine, white
wine, or rose wine can satisfy the class/type designation when no conflicting
class appears.
Harmless descriptive modifiers such as dry, off dry, sweet, reserve, estate, or
similar style terms can still pass when the core designation matches. Obvious
OCR/label spelling variants can pass when the intended designation is clear, such
as artifical matching artificial in "white grape wine with artificial flavor."
FAIL: Different broad beverage class, different legal class/type, absent/partly
legible type, or marketing language makes the legal class unclear. A wine label
submitted as Beer/Ale/Malt fails this field even if the brand and other fields
match."""

    # ------------------------------------------------------------------
    # Field 4: alcohol_content
    # ------------------------------------------------------------------

    def _field_alcohol_content(self, mode: str) -> str:
        if mode == "required":
            return """\
FIELD 4 - alcohol_content:
Alcohol content is required or was submitted for comparison. Extract the visible
label ABV/proof and compare it to APPLICATION_VALUES_JSON.alcohol_content.
Normalize before comparing: decimal comma = decimal point, and proof / 2 = ABV%.
PASS: Normalized application and label alcohol values match.
FAIL: Label alcohol content is absent, unreadable, not an alcohol quantity, or
mismatched after normalization. Alcohol is always required for distilled spirits
and for wine above 14% ABV or at/below 7% ABV."""

        return """\
FIELD 4 - alcohol_content:
Alcohol content may be optional for this beverage class/type.
Normalize before comparing: decimal comma = decimal point, and proof / 2 = ABV%.
PASS: Both values are present and normalized alcohol values match; or alcohol
content is omitted and allowed for a 7-14% table/light wine designation; or a
malt beverage omits alcohol content and no added-nonbeverage alcohol trigger is
visible.
FAIL: Values conflict, required alcohol content is absent, the label shows an
added-nonbeverage alcohol/flavor trigger without alcohol content, or the omission
cannot be evaluated confidently."""

    # ------------------------------------------------------------------
    # Field 5: net_contents
    # ------------------------------------------------------------------

    def _field_net_contents(self) -> str:
        return """\
FIELD 5 - net_contents:
Compare APPLICATION_VALUES_JSON.net_contents to net contents printed on the label.
PASS: Same quantity and unit, allowing formatting differences like 750 mL/750ml.
Pass only when the exact quantity and unit are visibly printed as net contents on
the label. Do not infer common bottle sizes from the application value, barcode,
UPC digits, container shape, or product category. Do not use an application value
as label_value unless the same quantity/unit is visible on the label.
FAIL: Missing, partly legible, different quantity/unit, outside the visible label,
or requires metric/customary conversion."""

    # ------------------------------------------------------------------
    # Field 6: name_address
    # ------------------------------------------------------------------

    def _field_name_address(self) -> str:
        return """\
FIELD 6 - name_address:
Compare APPLICATION_VALUES_JSON.name_address to the producer, bottler, packer, or
importer name and address printed on the label. Required on all labels.
PASS: Submitted name and city/state or country appear, with any required phrase
such as Produced By, Bottled By, Imported By, Brewed By, or Distilled By.
FAIL: Missing/different entity, incomplete or partly legible address, unconfirmed
city/state/country, or unclear importer/domestic attribution."""

    # ------------------------------------------------------------------
    # Field 7: country_of_origin
    # ------------------------------------------------------------------

    def _field_country_of_origin(self, mode: str) -> str:
        if mode == "domestic":
            return """\
FIELD 7 - country_of_origin:
Application says Domestic. PASS if the label does not show an imported origin
statement. A label with no country-of-origin statement can pass for Domestic.
When passing Domestic because no imported origin statement is visible, set
label_value exactly to "No imported origin statement visible"; do not use N/A.
FAIL if the label says Product of, Imported from, Made in a foreign country, or
otherwise indicates imported origin."""

        if mode.startswith("country:"):
            country = mode.split(":", 1)[1]
            return """\
FIELD 7 - country_of_origin:
Application provides a country name for an imported product. Compare the visible
label country/appellation/origin evidence to APPLICATION_VALUES_JSON.country_of_origin.
PASS: The label shows the same country or a clearly matching country/appellation/origin
statement for that country.
FAIL: No imported origin statement is visible, the country conflicts with the
application country, or the label appears clearly domestic with no matching
origin evidence.
Application country for this row: """ + country + "."

        return """\
FIELD 7 - country_of_origin:
APPLICATION_VALUES_JSON.country_of_origin must be Domestic or a country name.
If it is blank or unknown, fail this field as missing application origin value.
If the label indicates imported origin while the application is blank or unknown,
fail."""

    # ------------------------------------------------------------------
    # Field 8: color_additive_disclosure
    # ------------------------------------------------------------------

    def _field_color_additive_disclosure(self) -> str:
        return """\
FIELD 8 - color_additive_disclosure:
This check applies only to malt beverages when APPLICATION_VALUES_JSON.malt_color_additive_applicable is true.
PASS: A color additive disclosure is visible and readable on the label.
FAIL: The disclosure is absent, unreadable, obscured, or cannot be confidently
identified. Do not evaluate color-additive requirements outside this yes/no
applicability flag."""

    # ------------------------------------------------------------------
    # Field 9: government_warning
    # ------------------------------------------------------------------

    def _field_government_warning(self) -> str:
        return """\
FIELD 9 - government_warning:
Required exact text:
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.

PASS: The complete warning statement is visible/readable and matches the required
text word-for-word, including numbering, punctuation, and every required word.
The prefix 'GOVERNMENT WARNING:' is all caps and visibly bold. The warning body
may be sentence case or all caps; do not fail solely because the body text is all
caps when the words and punctuation are otherwise exact.
FAIL: Warning is absent, unreadable, partial, missing any required word, has any
changed/reordered/paraphrased wording, has different punctuation that changes the
required statement, has a lowercase/title-case/mixed-case prefix, lacks a visibly
bold prefix, is hidden/covered, or is inferred from regulatory knowledge.
For label_value, return the full visible warning statement when readable, not
only the heading. Preserve the visible heading case exactly as printed. If the
image shows 'government warning:', 'Government Warning:', or any other non-exact
case, return the full visible statement with that non-exact heading and fail the
field."""

    # ------------------------------------------------------------------
    # Output format
    # ------------------------------------------------------------------

    def _output_format(self, requested_fields: tuple[str, ...]) -> str:
        requested = ", ".join(requested_fields)
        return f"""\
Return this JSON object only:
{{"status":"pass|fail","summary":"one short sentence","fields":{{...}}}}

Each field object must be:
{{"status":"pass|fail","application_value":"...","label_value":"...","reason":"short internal note","evidence":[]}}

Requested fields: {requested}."""

    # ------------------------------------------------------------------
    # Hard rules recap
    # ------------------------------------------------------------------

    def _hard_rules(self) -> str:
        return """\
HARD RULES:
1. Return only the JSON object; do not include markdown or explanatory prose.
2. Application comparison fields use APPLICATION_VALUES_JSON for application_value.
3. artifact_legibility and government_warning are label-only checks with fixed application_value values.
4. Return only the requested field keys in fields; backend-only not-required fields are not requested.
5. Use the image only for label_value/evidence; missing, unreadable, ambiguous, or uncertain evidence fails.
6. Overall status is fail if any returned field fails."""

    # ------------------------------------------------------------------
    # Applicability planning
    # ------------------------------------------------------------------

    def _build_plan(self, application_values: ApplicationValues | None) -> VerificationPlan:
        requested_fields = [
            "artifact_legibility",
            "brand_name",
            "class_type_designation",
            "net_contents",
            "name_address",
            "country_of_origin",
            "government_warning",
        ]
        deterministic_fields: dict[str, dict] = {}
        alcohol_mode = self._alcohol_mode(application_values)
        if alcohol_mode.startswith("not_required"):
            deterministic_fields["alcohol_content"] = {
                "status": "pass",
                "application_value": "Not Required",
                "label_value": "Not Required",
                "reason": "Backend applicability: Alcohol content is not required for this row.",
                "evidence": [],
            }
        else:
            requested_fields.insert(3, "alcohol_content")

        color_mode = self._color_mode(application_values)
        if color_mode == "required":
            requested_fields.insert(-1, "color_additive_disclosure")
        else:
            deterministic_fields["color_additive_disclosure"] = {
                "status": "pass",
                "application_value": "Not Required",
                "label_value": "Not Required",
                "reason": (
                    "Backend applicability: Malt color additive disclosure is not "
                    "required for this row."
                ),
                "evidence": [],
            }

        return VerificationPlan(
            requested_fields=tuple(requested_fields),
            deterministic_fields=deterministic_fields,
            alcohol_mode="optional" if alcohol_mode == "optional" else "required",
            country_mode=self._country_mode(application_values),
        )

    def _alcohol_mode(self, application_values: ApplicationValues | None) -> str:
        if application_values is None:
            return "required"

        beverage_class = self._normalize_beverage_class(application_values.get("beverage_class"))
        alcohol_content = self._clean_text(application_values.get("alcohol_content"))
        class_type = application_values.get("class_type_designation")

        if beverage_class == "spirits":
            return "required"

        if beverage_class == "malt":
            if self._is_truthy(application_values.get("malt_added_nonbeverage_alcohol")):
                return "required"
            return "not_required_malt"

        if beverage_class == "wine":
            abv = self._parse_abv(alcohol_content)
            if abv is not None and abv > 14:
                return "required"
            if self._is_table_or_light_wine(class_type) and (
                abv is None or 7 <= abv <= 14
            ):
                return "not_required_table_wine"
            return "required"

        return "optional"

    def _color_mode(self, application_values: ApplicationValues | None) -> str:
        if application_values is None:
            return "not_required"
        beverage_class = self._normalize_beverage_class(application_values.get("beverage_class"))
        if beverage_class == "malt" and self._is_truthy(
            application_values.get("malt_color_additive_applicable")
        ):
            return "required"
        return "not_required"

    def _country_mode(self, application_values: ApplicationValues | None) -> str:
        if application_values is None:
            return "unknown"

        country = self._clean_text(application_values.get("country_of_origin"))
        normalized = country.lower()
        if not normalized:
            return "unknown"
        if normalized == "domestic":
            return "domestic"
        return f"country:{country}"

    def _normalize_beverage_class(self, value: str | bool | None) -> str | None:
        normalized = self._clean_text(value).lower().replace("-", "_").replace(" ", "_")
        if normalized in {"spirits", "distilled_spirits", "distilled"}:
            return "spirits"
        if normalized in {"wine", "wines"}:
            return "wine"
        if normalized in {"malt", "malt_beverage", "malt_beverages", "beer"}:
            return "malt"
        return None

    def _is_table_or_light_wine(self, value: str | bool | None) -> bool:
        normalized = self._clean_text(value).lower()
        return bool(re.search(r"\b(table|light)\s+wine\b", normalized))

    def _parse_abv(self, value: str | None) -> float | None:
        if not value:
            return None
        match = re.search(r"(\d+(?:[.,]\d+)?)", value)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None

    def _is_truthy(self, value: str | bool | None) -> bool:
        if isinstance(value, bool):
            return value
        return self._clean_text(value).lower() in {"1", "true", "yes", "y", "on"}

    def _clean_text(self, value: str | bool | None) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return (value or "").strip()
