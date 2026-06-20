# Assumptions

## Structured Application Inputs

The label image is evidence. The application data is the comparison target.
Application values must be submitted as structured data to the backend and then
included in the verification prompt as `APPLICATION_VALUES_JSON`.

The application must collect these base inputs for every row:

- `beverage_class`: one of `wine`, `malt`, or `spirits`. This field must be
  collected before class-dependent fields are validated.
- `brand_name`: business/brand name submitted on the application.
- `class_type_designation`: type of wine, malt beverage, or distilled spirit.
- `net_contents`: submitted container size.
- `name_address`: submitted business name plus address. City and state are
  sufficient for this app, and a fuller address is acceptable.
- `country_of_origin`: free-text origin value. Use `Domestic` for domestic
  products, or enter the country name for imported products.

The application must also collect these conditional inputs:

- `alcohol_content`: required for distilled spirits; required for wine when the
  submitted wine is over 14 percent ABV; optional for 7-14 percent ABV wine when
  the mandatory class/type designation is `table wine` or `light wine`; required
  for malt beverages only when alcohol is derived from added flavors or other
  added nonbeverage ingredients containing alcohol.
- `malt_added_nonbeverage_alcohol`: boolean trigger used only for malt
  beverages. Without this trigger the app cannot reliably decide whether a malt
  ABV statement is mandatory.
- `malt_color_additive_applicable`: yes/no trigger used only for malt beverages.
  When true, the model verifies that a color additive disclosure is present.

The government warning and artifact legibility are label-only checks. They have
no user-entered comparison value.

## Verification Rule Assumptions

Use this section as the definitive list of variables the app checks and when it
checks them.

### Wine

| Check | When checked | Application input | Pass standard |
| --- | --- | --- | --- |
| Brand name | Always | `brand_name` | Label shows the same brand, allowing capitalization, punctuation, apostrophe, spacing, and trademark-symbol differences. |
| Class/type designation | Always | `class_type_designation` | Label shows the submitted type of wine or a clearly equivalent/specific designation within wine. |
| Name and address | Always | `name_address` | Label shows the submitted business name and at least city/state. More address detail is acceptable. The name should be identical or very close to the application. |
| Net contents | Always | `net_contents` | Label shows the same quantity and unit. Formatting differences such as `750 mL` vs `750ml` are acceptable. |
| Alcohol content | Conditional | `alcohol_content`, `class_type_designation` | Required for wine over 14 percent ABV. Optional for 7-14 percent ABV wine when `table wine` or `light wine` appears as the mandatory class/type designation. |
| Government warning | Always | None | Label shows the exact full federal government warning text word-for-word. The `GOVERNMENT WARNING:` prefix must be all caps and bold. Missing words, changed wording, paraphrases, or mixed/title/lowercase prefix fail. |
| Country/appellation of origin | Imports only | `country_of_origin` | If the application says `Domestic`, no country-of-origin statement is required unless the label indicates imported origin. If the application provides a country name, the label must show matching country/appellation/origin evidence. |

### Malt Beverages / Beer

| Check | When checked | Application input | Pass standard |
| --- | --- | --- | --- |
| Brand name | Always | `brand_name` | Label shows the same brand, allowing capitalization, punctuation, apostrophe, spacing, and trademark-symbol differences. |
| Net contents | Always | `net_contents` | Label shows the same quantity and unit. |
| Class/type designation | Always | `class_type_designation` | Label shows the submitted malt beverage type or a clearly equivalent/specific malt beverage designation. |
| Name and address | Always | `name_address` | Label shows the submitted business name and at least city/state. More address detail is acceptable. The name should be identical or very close to the application. |
| Color additive disclosures | If applicable | `malt_color_additive_applicable` | When applicable, label shows a required color additive disclosure. If not applicable, the check is skipped. |
| Country of origin | Imports only | `country_of_origin` | If the application says `Domestic`, no country-of-origin statement is required unless the label indicates imported origin. If the application provides a country name, the label must show matching country-of-origin evidence. |
| Alcohol content | Conditional | `alcohol_content`, `malt_added_nonbeverage_alcohol` | Required when alcohol comes from added flavors or other added nonbeverage ingredients containing alcohol. Otherwise optional federally for this app. |
| Government warning | Always | None | Label shows the exact full federal government warning text word-for-word. The `GOVERNMENT WARNING:` prefix must be all caps and bold. Missing words, changed wording, paraphrases, or mixed/title/lowercase prefix fail. |

### Distilled Spirits

| Check | When checked | Application input | Pass standard |
| --- | --- | --- | --- |
| Brand name | Always | `brand_name` | Label shows the same brand, allowing capitalization, punctuation, apostrophe, spacing, and trademark-symbol differences. |
| Class/type designation | Always | `class_type_designation` | Label shows the submitted spirits class/type or a clearly equivalent/specific spirits designation. |
| Alcohol content | Always | `alcohol_content` | Label shows the same alcohol content. Proof can be normalized to ABV when needed. |
| Net contents | Always | `net_contents` | Label shows the same quantity and unit. |
| Country of origin | Imports only | `country_of_origin` | If the application says `Domestic`, no country-of-origin statement is required unless the label indicates imported origin. If the application provides a country name, the label must show matching country-of-origin evidence. |
| Name and address | Always | `name_address` | Label shows the submitted business name and at least city/state. More address detail is acceptable. The name should be identical or very close to the application. |
| Government warning | Always | None | Label shows the exact full federal government warning text word-for-word. The `GOVERNMENT WARNING:` prefix must be all caps and bold. Missing words, changed wording, paraphrases, or mixed/title/lowercase prefix fail. |

### General Comparison Rules

- Missing, unreadable, ambiguous, cut-off, or insufficient label evidence fails
  a required field.
- Do not infer application values from the label image. The application values
  come only from structured inputs.
- Do not infer unreadable label text from regulatory expectations.
- Do not make type-size, placement-distance, or millimeter claims from the
  image.
- A broader application class/type can be satisfied by a more specific visible
  label designation only when the specific designation is clearly within the
  same beverage class and no conflicting designation appears.
- A different legal beverage class fails even if some wording overlaps.
- Country of origin is checked as an import-only requirement in this app.
  `Domestic` means no country-of-origin statement is required unless the label
  itself indicates imported origin. Any other application value is treated as a
  country name and must match visible label country/appellation/origin evidence.
- Conditional TTB disclosures outside the checks listed in this document are out
  of scope for this app.
- The government warning required text is:

```text
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
```

- The warning check is exact: the label must show every required word and the
  required punctuation. Creative rewrites, shortened versions, missing words,
  title-case/mixed-case/lowercase `Government Warning:` prefixes, and unreadable
  warning text fail.



## Sources

- Wine anatomy of a label - TTB:
  <https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/anatomy-of-a-label>
- Wine labeling - TTB:
  <https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling>
- Wine alcohol content - TTB:
  <https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling-wine/wine-labeling-alcohol-content>
- Malt beverage labeling - TTB:
  <https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling>
- Malt beverage mandatory label information - TTB:
  <https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling/malt-beverage-mandatory-label-information>
- Malt beverage alcohol content - TTB:
  <https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling/malt-beverage-alcohol-content>
- Distilled spirits anatomy of a label - TTB:
  <https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/anatomy-of-a-distilled-spirits-label-tool>
- Distilled spirits labeling - TTB:
  <https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling>
- Distilled spirits mandatory label information - TTB:
  <https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-brand-label>
- Alcoholic beverage health warning statement - eCFR 27 CFR Part 16:
  <https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-16>
