# Alcohol Label Verification App

A prototype for checking alcohol label artwork against submitted application
values. The app uses a vision-capable LLM to read labels, then applies backend
guards so the final result is based on deterministic comparison rules rather
than model judgment alone.

## Contents

- [How It Works](#how-it-works)
- [Verification Scope](#verification-scope)
- [Demo Testing Controls](#demo-testing-controls)
- [Design Decisions](#design-decisions)
- [Hosting On Azure](#hosting-on-azure)
- [Running Locally](#running-locally)
- [Project Docs](#project-docs)

## How It Works

**Core principle:** the LLM reads; deterministic code judges.

Vision models are useful for extracting text from dense, imperfect label
artwork. Deterministic code is better for refusing false matches, such as
treating `40%` as a harmless typo for `11%`.

| Step | Responsibility | Output |
| --- | --- | --- |
| 1 | Reviewer submits structured application values and label artwork. | Explicit comparison target |
| 2 | Gemini-family vision model reads the uploaded label. | Structured label evidence |
| 3 | Backend parses the model response. | Typed field results |
| 4 | `backend/app/services/result_guard_service.py` applies deterministic guards. | Enforced pass/fail result |
| 5 | UI displays the overall result and field-level evidence. | Auditable reviewer view |

## Verification Scope

| Required element | What the app checks |
| --- | --- |
| Brand name | Brand and fanciful-name evidence, including meaningful spelling and spacing variants |
| Class/type | Broad beverage family alignment: wine, spirits, or malt |
| Alcohol content | Numeric ABV/proof comparison with tolerant parsing |
| Net contents | Visible quantity and unit |
| Name and address | Producer, bottler, importer, or responsible-party statement |
| Country of origin | Required imported-origin evidence and domestic/foreign contradictions |
| Government warning | Visible block, all-caps heading, legible text, and required federal wording |

The comparison rules are intentionally conservative:

- Alcohol content is compared numerically, including percent, proof, decimal
  comma, and bare-number formats.
- Class/type must match at the broad TTB-style family level before style details
  are considered.
- Brand matching allows meaningful spelling, spacing, and shared-word variants
  such as `STONE'S THROW` and `Stone's Throw`.
- Domestic applications fail when the label shows contradictory foreign-origin
  evidence.
- Government warning checks require a visible warning block, an all-caps
  `GOVERNMENT WARNING` heading, legible text, and the required statement.
- Missing, unreadable, ambiguous, or unsupported evidence cannot silently pass.

## Demo Testing Controls

The app includes demo-marked buttons for repeatable testing:

| Control | Purpose |
| --- | --- |
| Large demo batch | Creates a spreadsheet-style batch with roughly 300 labels to exercise batch handling. |
| Sample pass/fail set | Loads labels and applications with expected pass/fail outcomes. |

The sample set includes deliberate mismatches, such as removed or blurred
government warnings and alcohol-content values that do not match the label. It
also includes passing examples with glare or rotated labels, which should still
pass when the required information remains visible.

## Design Decisions

### Label Extraction

The app uses focused vision-model prompts instead of one large unstructured
request. Each prompt receives the full label artwork, but the requested evidence
is scoped:

- Legibility and government warning
- Product fields such as brand, class/type, alcohol content, net contents, and
  color disclosures
- Origin fields such as name/address and country of origin

This keeps the model focused on reading visible evidence while preserving a
JSON-first contract for the backend. The tradeoff is additional model calls, but
the calls are lightweight and can run in parallel.

After the model responds, the backend runs deterministic guards. These guards
exist because the model can still be overconfident about alcohol normalization,
beverage-class conflicts, missing values, and exact government-warning wording.

### Input Format

The first major design decision was the input format. When I started, I looked at
COLA examples where the label and application often appeared together in one
combined image. My first idea was to let users upload that combined image and
have the model pull out both the application text and the label text, then
compare the two.

That approach had some appeal. It felt native to the way the COLA source data was
already presented, and it would make batch upload very easy: users could upload a
large set of images without matching each label to a separate text record or
second image.

I moved away from that approach for two reasons. First, it did not seem aligned
with what the take-home assessment was asking for. Second, those scraped combined
images came from a place where the application and label were already matched.
That is not necessarily the real user workflow. If a user did not already have
the two documents joined together, asking them to create a combined screenshot
would add friction and create a new source of errors.

The current design uses one label image plus structured application fields. The
tradeoff is that batch upload becomes harder. For a single label, the form is
clear and easy to use. For 300 labels, nobody wants to type all of that
application data by hand.

I still think that is the right core contract for this prototype. It makes the
comparison target explicit, avoids asking the model to infer application values
from another document, and keeps the result easier to audit.

### Batch Upload

The input-format decision made batch upload the next major tradeoff. I initially
considered a spreadsheet where each row had application fields and a file path
linking to the matching label image. I decided against making that the primary
workflow because it is less approachable. A spreadsheet introduces schema errors,
missing columns, file path mistakes, and the extra burden of matching uploaded
images to text rows. That is powerful, but it is not the most intuitive first
experience for a non-technical reviewer.

If I were extending this product, I would support both workflows: a simple guided
form for manual review, and a spreadsheet-based batch path with a better mapping
step between rows and selected files. I did not build the full spreadsheet path
because I wanted to avoid complicating the prototype with extra controls and
branching workflows. The current flow is intentionally consolidated: select label
images, enter the required application details, verify, and inspect the result.

### Model Choice

OpenRouter is used for the hosted path because it provides one API surface for
multiple vision-capable models. That keeps model switching and fallback behavior
outside the core product workflow.

Local execution is supported through an OpenAI-compatible local provider path,
such as Ollama. Local mode is useful for demonstration, but it is slower and less
accurate than the hosted model path.

## Running Locally

Use [docs/startup.md](docs/startup.md) for the full local startup guide.

Local Ollama-based verification is slower than the deployed OpenRouter path.
Verification requests are sent as batches of 1 when running locally.

## Project Docs

| Document | Purpose |
| --- | --- |
| [docs/proposal.md](docs/proposal.md) | Product goals, invariants, architecture posture, and prototype scope |
| [docs/design.md](docs/design.md) | Runtime behavior, batch processing, provider strategy, failover expectations, and Azure deployment mechanics |
| [docs/assumptions.md](docs/assumptions.md) | Verification assumptions and label/application requirements |
| [docs/startup.md](docs/startup.md) | Local setup and startup instructions |
