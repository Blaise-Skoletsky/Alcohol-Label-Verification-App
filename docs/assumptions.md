# Assumptions

This document is the working source of truth for the prototype's operating
assumptions and label-verification scope. It separates product and deployment
assumptions from the mandatory-label checks that drive the prompt, form, and
spreadsheet template.

## Deployment

- The primary demo deployment is Azure App Service for Linux running a single
  custom Docker container.
- The same Docker image must run locally and in Azure.
- Local setup should require as few commands as possible, with
  `docker compose up --build` as the default path.
- Local demo mode must not require a `.env` file.
- `.env` is required only when enabling OpenRouter or another credentialed
  model provider.
- The app is stateless by default. Restarting the container may clear in-flight
  work.
- The initial demo does not require accounts, sign-in, or role-based access
  control.
- The public unauthenticated deployment is demo-only and must not be described
  as the production government security posture.

## Model Providers

- The frontend must never call OpenRouter, a local model server, or any other
  model provider directly.
- The frontend only calls the FastAPI backend.
- All model-provider credentials stay server-side.
- OpenRouter is the default cloud model provider.
- Local mode must be able to run without an OpenRouter key when configured to
  use a free or open-source local model backend.
- Local mode should default to a non-credentialed provider such as `mock` until
  a local/free model backend is wired in.
- The frontend should not change when switching between OpenRouter and a local
  model backend.
- Backend responses must keep the same result schema regardless of which model
  provider produced the result.

## Storage

- The server must not store uploaded label artwork or application data in cloud
  storage for the initial prototype.
- Backend processing may use memory or temporary files while a request or
  in-process batch is active.
- Recent history should live in the browser where practical.
- Browser-local history should target roughly one day of retention.
- Server-side retention can be added later only as an explicit design change.

## Product

- The app is a verification aid, not final legal approval or TTB certification.
- The UI should stay simple enough for non-technical compliance users.
- The target workflow uses one uploaded label-artwork PNG or JPG plus structured
  application data entered by the user as hard text inputs.
- Every verification item must include a label photo plus the application inputs
  required by the beverage class and conditional rules below.
- The model flags uploads where the label artwork is missing, unreadable,
  ambiguous, or insufficient to verify against the submitted application data.
- The app validates required application-data fields before asking the model to
  compare them to the label.
- The primary demo traffic assumption is one to two concurrent users.
- The main stress case is one user submitting roughly 100-400 label images with
  corresponding application-data entries in a batch.
- Batch upload size and model-call concurrency are separate. A large upload
  should process through a small bounded worker pool, initially five concurrent
  model calls.
- Batch results should appear incrementally as soon as individual labels
  complete so a reviewer can begin working before the full batch finishes.
- The app should support PNG and JPG/JPEG label-artwork uploads.
- Real public or user-provided label artwork and application-data examples are
  preferred for tests. Synthetic labels are not the primary fixture strategy.

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

## Implementation Change Plan

### 1. Prompt Changes

- Move prompt applicability from scattered prose into a single beverage-class
  rule matrix that mirrors this document.
- Add `beverage_class` as the first decision point in the prompt and the backend
  plan builder.
- Add conditional field planning for:
  - wine alcohol content,
  - malt alcohol content,
  - malt color additive disclosure,
  - import-only country/origin checks.
- Stop asking the model to evaluate skipped fields. The backend should mark
  skipped fields as deterministic `pass` or `not_applicable` with an explanation
  so model output stays focused on label evidence.
- Keep government warning as a strict label-only check with the fixed federal
  text.
- Tighten name/address language so the model compares the submitted business
  name and accepts city/state as the minimum address evidence.
- Tighten country/origin language so domestic rows do not fail only because no
  country statement appears.

### 2. Prompt Inputs

The backend prompt payload should include these values:

```json
{
  "beverage_class": "wine | malt | spirits",
  "brand_name": "...",
  "class_type_designation": "...",
  "net_contents": "...",
  "name_address": "...",
  "country_of_origin": "Domestic | country name",
  "alcohol_content": "...",
  "malt_added_nonbeverage_alcohol": true,
  "malt_color_additive_applicable": false
}
```

Implementation should directly update the UI, spreadsheet parser, backend model,
prompt payload, tests, and sample data to these field semantics. Do not add a
parallel old/new prompt contract unless a verified rollout constraint requires
it.

### 3. Spreadsheet and Form Changes

- Make `beverage_class` the first user-facing application field in the manual
  form and the first required business column in the spreadsheet.
- Derive visible/required fields from `beverage_class`.
- Keep `country_of_origin` as a single free-text field that accepts `Domestic`
  or a country name.
- Add malt-only columns:
  - `malt_added_nonbeverage_alcohol`,
  - `malt_color_additive_applicable`.
- Keep `alcohol_content` present in the template, but validate it conditionally:
  - required for spirits,
  - required for wine unless the application is a 7-14 percent `table wine` or
    `light wine` case,
  - required for malt only when `malt_added_nonbeverage_alcohol` is true.
- Update spreadsheet parsing, template CSV generation, and consumers to the new
  canonical columns.
- Update row readiness validation so a row can be verified only when the fields
  required by its beverage class and triggers are complete.
- Update sample data to include the new origin and malt trigger fields.

### 4. Backend Model and Result Changes

- Update `ApplicationValues` to store the new trigger fields.
- Update batch row parsing to normalize booleans from spreadsheets and forms.
- Update `VerificationPromptService._build_plan()` so field applicability is
  deterministic and testable.
- Decide whether skipped fields stay omitted from model output or appear in the
  final normalized result as `not_applicable`. The current code omits some
  skipped fields from the prompt and synthesizes deterministic fields, so the
  lower-risk path is to preserve that pattern.
- Extend result guarding so required application values cannot be blank for the
  active beverage class.

### 5. Tests

- Add prompt-plan tests for each beverage class.
- Add wine tests for:
  - spirits-style always-required ABV equivalent does not leak into wine,
  - wine over 14 percent ABV requires alcohol content,
  - 7-14 percent `table wine` or `light wine` can skip alcohol content.
- Add malt tests for:
  - no added nonbeverage alcohol trigger skips ABV,
  - added nonbeverage alcohol trigger requires ABV,
  - color additive disclosure is checked only when applicable.
- Add domestic/country-name origin tests for all beverage classes.
- Add spreadsheet template and parser tests for new columns and aliases.
- Add UI readiness tests or component coverage for beverage-class-driven
  required fields.

## Security

- OpenRouter and local model credentials must never be exposed to the browser.
- OpenRouter and other real credentials are optional for local demo mode and
  required only when the selected provider needs them.
- Secrets must not be committed to Git.
- Request logs must not include secrets or full uploaded file contents.
- Uploaded files are untrusted input and must be validated before model
  processing.
- A production government deployment would need authentication, authorization,
  approved model routing, retention review, audit logging, and egress review.

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
