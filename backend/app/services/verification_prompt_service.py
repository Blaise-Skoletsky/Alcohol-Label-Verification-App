import json
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class VerificationPrompt:
    system_instruction: str
    user_instruction: str


ApplicationValues = Mapping[str, str | None]


class VerificationPromptService:
    def build_prompt(self, application_values: ApplicationValues | None = None) -> VerificationPrompt:
        return VerificationPrompt(
            system_instruction=self._system(),
            user_instruction=self._user(application_values),
        )

    # ------------------------------------------------------------------
    # System instruction
    # ------------------------------------------------------------------

    def _system(self) -> str:
        sections = [
            (
                "You verify TTB-style alcohol label artwork against APPLICATION_VALUES_JSON. "
                "Return JSON only. The image is label artwork only; never extract application "
                "values from it. Use only visible label text for label_value and evidence."
            ),
            (
                "Government warning is strict and label-only: pass only when the exact federal "
                "warning is visible and the prefix 'GOVERNMENT WARNING:' is all caps and bold."
            ),
            self._task_intro(),
            self._overall_verdict_rules(),
            self._field_artifact_legibility(),
            self._field_brand_name(),
            self._field_class_type_designation(),
            self._field_alcohol_content(),
            self._field_net_contents(),
            self._field_name_address(),
            self._field_country_of_origin(),
            self._field_government_warning(),
            self._output_format(),
            self._hard_rules(),
        ]
        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # User instruction
    # ------------------------------------------------------------------

    def _user(self, application_values: ApplicationValues | None) -> str:
        return (
            "Review the attached label artwork image using the system rules. "
            "Compare only against APPLICATION_VALUES_JSON below. Use visible label text only for "
            "label_value and evidence; do not infer or fill missing label text from the rules.\n\n"
            "APPLICATION_VALUES_JSON:\n"
            f"{self._application_values_json(application_values)}"
        )

    def _application_values_json(self, application_values: ApplicationValues | None) -> str:
        values = {
            "brand_name": "{{brand_name}}",
            "class_type_designation": "{{class_type_designation}}",
            "alcohol_content": "{{alcohol_content}}",
            "net_contents": "{{net_contents}}",
            "name_address": "{{name_address}}",
            "country_of_origin": "{{country_of_origin}}",
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
Compare APPLICATION_VALUES_JSON to the uploaded label image. For each field, copy
the submitted value into application_value, extract visible label text into
label_value, then apply the PASS/FAIL rule. For artifact_legibility use
application_value='N/A - text entry form'. For government_warning use
application_value='Required federal government warning'."""

    # ------------------------------------------------------------------
    # Overall verdict rules
    # ------------------------------------------------------------------

    def _overall_verdict_rules(self) -> str:
        return """\
OVERALL VERDICT RULES:
Overall pass only if every field passes. Any failed field makes the overall result
fail. Fail fields with missing, unreadable, ambiguous, cut-off, or insufficient
label evidence. Do not make type-size or millimeter claims from the image."""

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
Compare APPLICATION_VALUES_JSON.class_type_designation to the class/type printed
on the label.
PASS: Exact/equivalent match, or the label type is a recognized member of the
submitted broad class (spirits type, wine varietal/style, beer/ale style).
FAIL: Different legal class, absent/partly legible type, or marketing language
makes the legal class unclear."""

    # ------------------------------------------------------------------
    # Field 4: alcohol_content
    # ------------------------------------------------------------------

    def _field_alcohol_content(self) -> str:
        return """\
FIELD 4 - alcohol_content:
Compare alcohol quantities only; class/type or net contents are not alcohol values.
Normalize before comparing: decimal comma = decimal point, and proof / 2 = ABV%.
PASS: Normalized application and label values match; or wine is 7-14% with a
valid table/light wine omission; or beer/malt omission is allowed and not
contradicted by the label.
FAIL: Required alcohol content is absent, not an alcohol quantity, mismatched
after normalization, or an omission/beer trigger cannot be evaluated. Alcohol is
always required for spirits, required for wine above 14% ABV and at/below 7% ABV."""

    # ------------------------------------------------------------------
    # Field 5: net_contents
    # ------------------------------------------------------------------

    def _field_net_contents(self) -> str:
        return """\
FIELD 5 - net_contents:
Compare APPLICATION_VALUES_JSON.net_contents to net contents printed on the label.
PASS: Same quantity and unit, allowing formatting differences like 750 mL/750ml.
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

    def _field_country_of_origin(self) -> str:
        return """\
FIELD 7 - country_of_origin:
Compare APPLICATION_VALUES_JSON.country_of_origin to the origin statement printed
on the label for imported products.
PASS: Imported products show a matching origin statement such as Product of,
Imported from, or Made in [Country]. Domestic products may omit origin; if origin
appears, it must match.
FAIL: Imported product has no origin statement, origin country mismatches, only
'Imported by' appears, origin is partly legible, or domestic/imported status is
unclear."""

    # ------------------------------------------------------------------
    # Field 8: government_warning
    # ------------------------------------------------------------------

    def _field_government_warning(self) -> str:
        return """\
FIELD 8 - government_warning:
Required exact text:
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.

PASS: Required warning is visible/readable word-for-word, and the prefix
'GOVERNMENT WARNING:' is all caps and visibly bold.
FAIL: Warning is absent, unreadable, partial, altered, paraphrased, title-case,
missing bold all-caps prefix, hidden/covered, or inferred from regulatory knowledge."""

    # ------------------------------------------------------------------
    # Output format
    # ------------------------------------------------------------------

    def _output_format(self) -> str:
        return """\
Return this JSON object only:
{"status":"pass|fail","summary":"one short sentence","fields":{...}}

Each field object must be:
{"status":"pass|fail","application_value":"...","label_value":"...","reason":"short internal note","evidence":[]}

Required fields: artifact_legibility, brand_name, class_type_designation,
alcohol_content, net_contents, name_address, country_of_origin, government_warning."""

    # ------------------------------------------------------------------
    # Hard rules recap
    # ------------------------------------------------------------------

    def _hard_rules(self) -> str:
        return """\
HARD RULES:
1. Return only the JSON object; do not include markdown or explanatory prose.
2. Application comparison fields use APPLICATION_VALUES_JSON for application_value.
3. artifact_legibility and government_warning are label-only checks with fixed application_value values.
4. Use the image only for label_value/evidence; missing, unreadable, ambiguous, or uncertain evidence fails.
5. Overall status is fail if any field fails."""
