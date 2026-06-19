from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerificationPrompt:
    system_instruction: str
    user_instruction: str


class VerificationPromptService:
    def build_prompt(self) -> VerificationPrompt:
        return VerificationPrompt(
            system_instruction=self._system(),
            user_instruction=self._user(),
        )

    # ------------------------------------------------------------------
    # System instruction
    # ------------------------------------------------------------------

    def _system(self) -> str:
        return (
            "You are an alcohol label verification assistant for TTB-style application and label "
            "artwork review. Return JSON only. Do not include markdown. Be conservative: if the "
            "application section, label artwork section, or a required value is missing, unreadable, "
            "or ambiguous, use needs_review instead of pass. Exception: government_warning is a "
            "binary field; if the required warning is missing, unreadable, ambiguous, covered, or "
            "not visibly printed on the label artwork, government_warning must be fail."
        )

    # ------------------------------------------------------------------
    # User instruction — assembled from one method per section
    # ------------------------------------------------------------------

    def _user(self) -> str:
        sections = [
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
        ]
        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Task intro
    # ------------------------------------------------------------------

    def _task_intro(self) -> str:
        return """\
Review this single combined application-and-label artifact. It should contain both the label \
application and the label artwork.

First, mentally separate the artifact into two regions:
- application: the form or application data submitted for approval.
- label_artwork: the actual product label image/artwork.

Do not compare two values from the same region. If you cannot tell which region a value came \
from, mark that field needs_review."""

    # ------------------------------------------------------------------
    # Overall verdict rules
    # ------------------------------------------------------------------

    def _overall_verdict_rules(self) -> str:
        return """\
OVERALL VERDICT RULES:
- pass: every field is pass.
- needs_review: any field is needs_review and none are fail.
- fail: any field is fail.

PER-FIELD STATUS RULES (apply to every field):
- pass: you extracted the application value and label value from the correct regions and they \
satisfy the field rule.
- fail: both values are readable and clearly do not satisfy the rule.
- needs_review: either value is unreadable, region attribution is uncertain, extraction may be \
wrong, or the rule cannot be applied with confidence.
- Do not make exact type-size or millimeter compliance claims from the image."""

    # ------------------------------------------------------------------
    # Field 1: artifact_legibility
    # ------------------------------------------------------------------

    def _field_artifact_legibility(self) -> str:
        return """\
FIELD 1 — artifact_legibility:
Confirm the artifact contains both an application section and a label artwork section, and that \
the text needed for review is readable.

PASS: Both regions are identifiable, and the required application values and label values can be read confidently. Do not fail only \
because the photo is imperfect. Glare, dim lighting, scan noise, or mild skew can still pass when the required text remains readable. 

NEEDS REVIEW: Both regions are present but partially obscured, low-resolution, or cut off in a \
way that limits specific field extractions. Note which areas are affected.

FAIL: The image is so degraded that no meaningful extraction is possible, or the document is \
clearly not an alcohol label application.

Cascade rule: if artifact_legibility is needs_review or fail, all other fields except \
government_warning must also be needs_review — do not pass or fail those other fields when the \
artifact cannot be reliably read. Government warning is always binary: if the required warning \
cannot be confirmed in full, government_warning must be fail."""

    # ------------------------------------------------------------------
    # Field 2: brand_name
    # ------------------------------------------------------------------

    def _field_brand_name(self) -> str:
        return """\
FIELD 2 — brand_name:
Extract the brand name from the application and from the label artwork and compare them.

PASS: Names match exactly, or differ only in capitalization, trademark symbols (® ™), or \
punctuation such as apostrophe presence/absence.

FAIL: Substantively different wording (e.g. application "Eagle Rare" vs. label "Eagle Reserve"); \
brand name absent from label entirely.

No beverage-type differences for this field."""

    # ------------------------------------------------------------------
    # Field 3: class_type_designation
    # ------------------------------------------------------------------

    def _field_class_type_designation(self) -> str:
        return """\
FIELD 3 — class_type_designation:
The application states a broad legal class; the label may state a more specific subtype within \
that class. A recognized subtype always passes. Only fail on a genuine cross-class conflict.

PASS:
- Exact or equivalent match (e.g. "Red Wine" and "Dry Red Table Wine" are equivalent).
- The label type is a recognized member of the application's class:
  - Application "Distilled Spirits" passes with label: Gin, Gin Specialties, Vodka, Rum, \
Whiskey, Bourbon Whiskey, Tennessee Whiskey, Straight Bourbon, Rye Whiskey, Brandy, Cognac, \
Tequila, Mezcal, Aquavit, Schnapps, Liqueur, Cordial, or any other recognized distilled \
spirits designation. Distilled spirits also pass when the label uses flavor, specialty, or \
marketing wording such as "cider", "apple cider", "winter cider", "punch", "cream", or \
"cocktail" but the label still shows distilled-spirits context such as whiskey/gin/liqueur, \
proof, or % alc/vol. Do not treat that flavor wording as a malt beverage or wine class by itself.
  - Application "Wine" passes with label: Chardonnay, Cabernet Sauvignon, Merlot, Pinot Noir, \
Rosé, Dry Red Table Wine, Table Wine, Sparkling Wine, Champagne, Prosecco, Cava, Moscato, \
Riesling, Sake (if Japanese or domestically brewed), Dessert Wine, Port-style, any grape \
varietal or recognized wine designation.
  - Application "Malt Beverage" passes with label: India Pale Ale, Stout, Porter, Lager, \
Pilsner, Ale, Wheat Beer, Hefeweizen, Sour, Belgian Tripel, or any recognized beer/ale style.

FAIL: The label designates a genuinely different legal class from the application — e.g. Wine \
application with Vodka label, Distilled Spirits application with Lager/Beer/Ale label and no \
spirits proof/ABV context, Malt Beverage application with Wine label."""

    # ------------------------------------------------------------------
    # Field 4: alcohol_content
    # ------------------------------------------------------------------

    def _field_alcohol_content(self) -> str:
        return """\
FIELD 4 — alcohol_content:
First identify the beverage class from the application. Rules differ by class.

Valid alcohol content formats: "13% ALC/VOL", "13% alcohol by volume", "13.0% Alc./Vol.", \
"90 proof", ranges such as "80-89 proof", lower bounds such as "48 proof up".
The label_value must never be class/type text (e.g. "DRY RED TABLE WINE") or net contents. \
If the extracted value is not an alcohol quantity, status must be needs_review.

--- Distilled Spirits: ABV/proof is always required ---

PASS: Application and label values match when normalized (proof ÷ 2 = ABV%). For a stated \
range such as "80–89 proof," the label value falls within that range. For a lower bound such \
as "48 proof up," the label value is at or above that bound. Exact values must match exactly \
after normalization; 49.5% is not the same as 50%.

NEEDS REVIEW: Value present but region attribution is unclear; proof vs. ABV is ambiguous and \
cannot be normalized; extracted value is not an alcohol quantity.

FAIL: Both values are readable and clearly do not match after normalization; ABV/proof is \
entirely absent from the label.

--- Wine: ABV is conditionally required ---

Required when ABV is above 14%. Required when ABV is at or below 7%. Legitimately omittable \
for still wines in the 7–14% range that carry a "table wine" or "light wine" designation on \
the label.

PASS: Values match when normalized; OR ABV is omitted on both the application and the label \
for a 7–14% wine with a table wine or light wine designation (set reason: "not required for \
table wine designation").

NEEDS REVIEW: ABV is present on one region but not the other; cannot determine whether the \
product exceeds 14% or whether a table/light wine designation applies; value is partially legible.

FAIL: ABV is clearly required (above 14% or at/below 7%) but is missing from the label; both \
values are readable and clearly do not match.

--- Malt Beverage: ABV is federally optional ---

ABV is optional unless the product contains alcohol from added nonbeverage flavors or \
ingredients other than hops extract, or state law requires it.

PASS: Both provided and they match; both omitted and the class allows omission; application \
omits ABV but label provides one with no contradiction.

NEEDS REVIEW: One region has ABV and the other does not; unclear whether added flavors trigger \
the requirement; extracted value is not an alcohol quantity.

FAIL: Both values are provided and clearly do not match."""

    # ------------------------------------------------------------------
    # Field 5: net_contents
    # ------------------------------------------------------------------

    def _field_net_contents(self) -> str:
        return """\
FIELD 5 — net_contents:
Compare net contents from the application and label artwork, including units. Required on all \
labels regardless of beverage type.

PASS: Quantities and units match, allowing only formatting normalization — e.g. "750 mL" = \
"750ml" = "750 ML".

FAIL: Different quantity (e.g. "750 mL" vs. "1 L"); different unit system even at equivalent \
volume (e.g. application "750 mL" vs. label "25.4 fl oz" — same physical volume but different \
representation is a mismatch); net contents entirely absent from label.

Unit normalization only — never convert between metric and customary even if numerically equivalent."""

    # ------------------------------------------------------------------
    # Field 6: name_address
    # ------------------------------------------------------------------

    def _field_name_address(self) -> str:
        return """\
FIELD 6 — name_address:
Verify the producer, bottler, packer, or importer name and address appears on the label and \
matches the application. Required on all labels.

PASS: Name and city/state (or country for imports) appear on the label and match the \
application; an appropriate explanatory phrase is present for domestic products (see below). 

NEEDS REVIEW: Address partially legible and city/state cannot be confirmed; explanatory phrase \
absent but may be on a panel not shown; importer vs. domestic attribution unclear.

FAIL: Name and address completely absent from the label; entity named on the label is clearly \
a different company from the application.

Required explanatory phrases by class (domestic products only):
- Distilled Spirits: Distilled By, Distilled and Bottled By, Bottled By, Produced By, \
Manufactured By.
- Wine: Produced and Bottled By, Cellared and Bottled By, Vinted and Bottled By, Bottled By, \
Packed By.
- Malt Beverage: Brewed By, Brewed and Bottled By, Brewed and Canned By, Bottled By, Packed By.

For imported products: the importer name and address are required on the label; the foreign \
producer name and address are optional. The phrase requirement applies to the importer statement."""

    # ------------------------------------------------------------------
    # Field 7: country_of_origin
    # ------------------------------------------------------------------

    def _field_country_of_origin(self) -> str:
        return """\
FIELD 7 — country_of_origin:
Applies to imported products only. For clearly domestic products, pass when no import \
country-of-origin statement is required.

PASS:
- Imported: a statement such as "Product of [Country]," "Imported from [Country]," or \
"Made in [Country]" appears on the label and matches the application's stated origin. \
Note: "Imported by" alone does not satisfy this requirement.
- Domestic: no import statement is required; if one appears anyway it must match the application.

NEEDS REVIEW: Origin statement is partially legible; cannot determine from the application or \
context whether the product is domestic or imported.

FAIL: Product is clearly imported (application states a foreign country of origin) but the \
label has no country of origin statement; the country stated on the label does not match \
the application."""

    # ------------------------------------------------------------------
    # Field 8: government_warning
    # ------------------------------------------------------------------

    def _field_government_warning(self) -> str:
        required_text = (
            "GOVERNMENT WARNING: "
            "(1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES "
            "DURING PREGNANCY BECAUSE OF THE RISK OF BIRTH DEFECTS. "
            "(2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR OR "
            "OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS."
        )
        return (
            "FIELD 8 — government_warning:\n"
            "Same rule for all beverage classes. Do not extract application_value from the "
            "artifact — always set it to the verbatim required text below. Set label_value to "
            "the exact warning text you can read from the label artwork when readable (or "
            "'Warning block visibly present' when the label is small or rotated but the warning "
            "block is visibly present, or 'Not present' if absent, or "
            "'Unreadable or incomplete' if obscured).\n\n"
            "Use only the affixed label artwork region, usually below the application form heading "
            "'AFFIX COMPLETE SET OF LABELS BELOW'. Ignore the application form, instructions, "
            "certification text, TTB form footer, and any other non-label text. Do not infer that "
            "the warning exists because the product is alcoholic; it must be visibly printed on "
            "the label artwork itself. The words 'GOVERNMENT WARNING' must be visibly printed on "
            "the label artwork for this field to pass. A blank white strip, covered/whited-out "
            "area, barcode area, UPC placeholder, ingredient paragraph, sulfite statement, or "
            "importer/address text is not a government warning. If the label has a white or blank "
            "rectangle where text appears to have been removed or covered, treat the government "
            "warning as absent and fail.\n\n"
            "This field has only two allowed statuses: pass or fail. Never return needs_review "
            "for government_warning.\n\n"
            f"Required text: {required_text}\n\n"
            "Before assigning pass, verify from the image itself that the literal heading "
            "'GOVERNMENT WARNING' is visible on the label artwork. Do not copy the Required text "
            "into label_value unless you actually read it from the label artwork. If you are "
            "guessing, fail.\n\n"
            "PASS: The complete warning statement appears on the label artwork. Prefer reading "
            "all words in order. Minor OCR variance in capitalization or spacing is acceptable. "
            "For small, skewed, or rotated affixed labels, do not fail solely because the text is "
            "hard to OCR when a government-warning block is visibly present on the label artwork "
            "and you can identify the GOVERNMENT WARNING heading plus the two numbered sentence "
            "structure. To pass, label_value must be either the full warning text as read from "
            "the label artwork or 'Warning block visibly present' for small/rotated label artwork "
            "where the complete required warning block is visibly present.\n\n"
            "FAIL: The statement is absent, partially visible, partially legible, obscured, cut "
            "off, incomplete, truncated, altered, paraphrased, missing either numbered sentence, "
            "missing the GOVERNMENT WARNING heading, or not word-for-word identical to the "
            "required government warning when readable. If there is no visible warning block on "
            "the label artwork itself, fail this field. If the label has a blank or covered area "
            "where warning text would normally appear, treat the warning as absent and fail."
        )

    # ------------------------------------------------------------------
    # Output format
    # ------------------------------------------------------------------

    def _output_format(self) -> str:
        gov_warning = (
            "GOVERNMENT WARNING: "
            "(1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES "
            "DURING PREGNANCY BECAUSE OF THE RISK OF BIRTH DEFECTS. "
            "(2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR OR "
            "OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS."
        )
        field_shape = (
            '"status":"pass|fail|needs_review",'
            '"application_value":"...",'
            '"label_value":"...",'
            '"reason":"short internal note",'
            '"evidence":[]'
        )
        return (
            "Return this JSON shape exactly:\n"
            "{\n"
            '  "status": "pass|fail|needs_review",\n'
            '  "summary": "one short sentence",\n'
            '  "fields": {\n'
            f'    "artifact_legibility":       {{{field_shape}}},\n'
            f'    "brand_name":                {{{field_shape}}},\n'
            f'    "class_type_designation":    {{{field_shape}}},\n'
            f'    "alcohol_content":           {{{field_shape}}},\n'
            f'    "net_contents":              {{{field_shape}}},\n'
            f'    "name_address":              {{{field_shape}}},\n'
            f'    "country_of_origin":         {{{field_shape}}},\n'
            '    "government_warning":        {'
            '"status":"pass|fail",'
            f'"application_value":"{gov_warning}",'
            '"label_value":"<what appears on label, Warning block visibly present, Not present, or Unreadable or incomplete>",'
            '"reason":"short internal note",'
            '"evidence":[]'
            "}\n"
            "  }\n"
            "}"
        )
