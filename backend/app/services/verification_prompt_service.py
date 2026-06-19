from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerificationPrompt:
    system_instruction: str
    user_instruction: str


class VerificationPromptService:
    def build_prompt(self) -> VerificationPrompt:
        return VerificationPrompt(
            system_instruction=self._build_system_instruction(),
            user_instruction=self._build_user_instruction(),
        )

    def _build_system_instruction(self) -> str:
        return (
            "You are an alcohol label verification assistant for TTB-style application and label "
            "artwork review. Return JSON only. Do not include markdown. Be conservative: if the "
            "application section, label artwork section, or a required value is missing, unreadable, "
            "or ambiguous, use needs_review instead of pass."
        )

    def _build_user_instruction(self) -> str:
        return (
            "Review this single combined application-and-label artifact. It should contain both "
            "the label application and the label artwork.\n\n"
            "First, mentally separate the artifact into two regions:\n"
            "- application: the form or application data submitted for approval.\n"
            "- label_artwork: the actual product label image/artwork.\n"
            "Do not compare two values from the same region. If you cannot tell which region a value "
            "came from, mark that field needs_review.\n\n"
            "Check exactly these fields:\n"
            "1. artifact_legibility: confirm the artifact contains both an application section and "
            "label artwork section, and that the label text needed for review is readable. Poor image "
            "quality is not an automatic fail; use needs_review with the specific unreadable area.\n"
            "2. brand_name: extract the brand name from the application and from the label artwork. "
            "Allow capitalization and punctuation-only differences, but fail substantive wording changes.\n"
            "3. class_type_designation: compare the application class/type to the label artwork "
            "class/type. Equivalent legal/category wording may pass, such as 'Red Wine' and 'Dry Red "
            "Table Wine', when the beverage type clearly matches. Fail conflicting alcohol types.\n"
            "4. alcohol_content: extract only alcohol content values from both regions when required "
            "or provided. Valid values look like '13% ALC/VOL', '13% alcohol by volume', '13.0% "
            "Alc./Vol.', or proof values such as '90 proof'. The label_value for alcohol_content must "
            "never be class/type text such as 'DRY RED TABLE WINE', 'bourbon whiskey', or net contents. "
            "Compare normalized alcohol values exactly. 49.5% is not the same as 50%. Proof may be "
            "converted to ABV. If alcohol content is legitimately absent because the application and "
            "beverage type show a clear exception, explain that and use pass. If the exception is not "
            "clear, use needs_review.\n"
            "5. net_contents: compare net contents from the application and label artwork, including "
            "units. Normalize obvious unit formatting only, not different quantities.\n"
            "6. name_address: verify the producer, bottler, packer, or importer name/address appears "
            "on the label and matches the application where available. For domestic malt beverages, "
            "an appropriate explanatory phrase such as BREWED BY, BREWED AND BOTTLED BY, BOTTLED BY, "
            "PACKED BY, or equivalent should appear with the name/address.\n"
            "7. country_of_origin: for imports, verify country of origin appears and matches the "
            "application. For clearly domestic products, pass when no import country-of-origin "
            "statement is required.\n"
            "8. government_warning: verify the following exact federal statement appears in full on "
            "the label artwork. Do not extract application_value from the artifact — always set it to "
            "the verbatim required text below. Set label_value to exactly what appears on the label "
            "(or 'Not present' if absent, or 'Partially legible' if obscured). "
            "Pass only if the full statement is present and readable. Fail if clearly absent. "
            "Use needs_review if partially obscured or unreadable. "
            "Required text: GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD "
            "NOT DRINK ALCOHOLIC BEVERAGES DURING PREGNANCY BECAUSE OF THE RISK OF BIRTH DEFECTS. "
            "(2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR OR OPERATE "
            "MACHINERY, AND MAY CAUSE HEALTH PROBLEMS.\n\n"
            "Status rules:\n"
            "- Use pass only when you extracted the application value and the label value from the correct "
            "regions and they satisfy the field rule.\n"
            "- Use fail when both values are readable and clearly do not satisfy the rule.\n"
            "- Use needs_review when either value is unreadable, region attribution is uncertain, or extraction "
            "may be wrong.\n"
            "- For alcohol_content, if either extracted value is not an alcohol-content value and no clear "
            "exception applies, status must be needs_review.\n"
            "- Do not make exact type-size or millimeter compliance claims from the image.\n\n"
            "Return this JSON shape exactly:\n"
            "{"
            '"status":"pass|fail|needs_review",'
            '"summary":"one short sentence",'
            '"fields":{'
            '"artifact_legibility":{"status":"pass|fail|needs_review","application_value":"...","label_value":"...","confidence":0.0,"reason":"short internal note","evidence":[]},'
            '"brand_name":{"status":"pass|fail|needs_review","application_value":"...","label_value":"...","confidence":0.0,"reason":"short internal note","evidence":[]},'
            '"class_type_designation":{"status":"pass|fail|needs_review","application_value":"...","label_value":"...","confidence":0.0,"reason":"short internal note","evidence":[]},'
            '"alcohol_content":{"status":"pass|fail|needs_review","application_value":"...","label_value":"...","confidence":0.0,"reason":"short internal note","evidence":[]},'
            '"net_contents":{"status":"pass|fail|needs_review","application_value":"...","label_value":"...","confidence":0.0,"reason":"short internal note","evidence":[]},'
            '"name_address":{"status":"pass|fail|needs_review","application_value":"...","label_value":"...","confidence":0.0,"reason":"short internal note","evidence":[]},'
            '"country_of_origin":{"status":"pass|fail|needs_review","application_value":"...","label_value":"...","confidence":0.0,"reason":"short internal note","evidence":[]},'
            '"government_warning":{"status":"pass|fail|needs_review","application_value":"GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES DURING PREGNANCY BECAUSE OF THE RISK OF BIRTH DEFECTS. (2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR OR OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS.","label_value":"<what appears on label or Not present>","confidence":0.0,"reason":"short internal note","evidence":[]}'
            "}"
            "}"
        )
