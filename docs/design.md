# Design

This document describes how the prototype behaves at runtime. The proposal owns
goals, invariants, architecture decisions, and open product questions. The
canonical verification scope, field applicability rules, assumptions, and source
links live in [assumptions.md](assumptions.md).

# Runtime Flow

- The user creates one verification item by uploading label artwork and filling
  out structured application text fields in the app.
- The frontend sends the label image and application-data form payload to
  FastAPI.
- FastAPI validates file type, file size, and form shape before processing.
- The backend calls the configured vision provider with the label artwork plus
  the normalized application-data payload.
- The model returns structured JSON containing extracted values, pass/fail
  statuses, reasons, and evidence.
- The backend normalizes and validates the model output before returning a result
  to the UI.
- The UI shows a compact result summary first, with visible evidence available
  for each field.
- Requests without either a label image or the required application-text fields
  are invalid.

# UI and User Experience

The UI should be minimal, light, and work-focused. Use a plain white interface
with restrained Azure-like styling: clean typography, simple borders, clear
status colors, and obvious primary actions. Do not add dark mode, decorative
visuals, or unnecessary configuration controls for the prototype.

## Primary Layout

- The first screen contains the primary verification workflow.
- Results appear directly below the input area.
- Submitting one or many verification items creates one result row per item.
- The upload and form controls should make the expected inputs obvious without
  requiring a long explanation.
- The user should understand the screen without reading instructions.

## Result Rows

- Each uploaded item appears as a compact horizontal status row.
- Each row shows the item name or identifier, current status, and overall result.
- Rows update progressively as uploads and model verification proceed.
- Rows should use familiar status indicators:
  - Green check for clear/pass.
  - Red X for fail or likely rejection.
  - Loading indicator for queued or processing.
- A row becomes clickable when enough information is available to inspect it.
- The list should remain useful when many items are present, so rows need to be
  compact and scannable.

## Detail View

- Clicking a result row opens a detail modal or focused detail panel.
- The detail view shows the submitted label image, the submitted
  application-data snapshot, and the verification summary together.
- The summary shows each checked requirement with a status:
  - Green/pass when the field matches.
  - Red/fail when the field does not match.
- The detail view must make the evidence visible: extracted label value, entered
  application value, reason, and supporting evidence.
- The detail view should not hide failed fields behind extra clicks.

## Navigation

- The detail view includes right and left navigation controls to move between
  uploaded items.
- Navigation should work while the batch is still processing.
- If the user navigates to an item that is still queued or processing, the detail
  view should show that item with a waiting/loading state instead of blocking
  navigation.
- When that item finishes processing, the detail view should update in place.
- The user should be able to keep moving forward or backward through the batch as
  results load.

## Progressive Workflow

- The UI must not wait for the entire batch to finish before showing useful
  results.
- The reviewer should be able to start with the first completed labels while
  later labels continue processing.
- Completed rows should remain stable in the list and should not jump around as
  other rows update.
- Batch progress should be visually obvious without dominating the page.

# Batch Processing

- Batch submission returns quickly with a batch identifier instead of blocking
  until all labels finish.
- Each batch item is processed as an independent job with its own status and
  result.
- Provider calls pass through a bounded queue.
- The queue must prevent large-batch fanout, including hundreds of simultaneous
  provider calls in cloud mode.
- The first processing wave should be small enough to return initial results
  within the single-label latency target when the provider is healthy.
- Batch results must be shown incrementally as each item completes.
- Interactive single-label requests should have priority over background batch
  work.
- Failed items must be isolated so one bad image, malformed row, timeout, or
  provider failure does not fail the whole batch.
- Batch progress should feel smooth in the UI. Prefer server-sent events for
  batch progress updates if the implementation stays simple in a single-container
  Azure App Service deployment; otherwise use short-interval polling as the
  fallback.
- If durable batch processing is intentionally added later, Azure Blob Storage,
  Azure Queue Storage, and Azure Table Storage, Cosmos DB, or Postgres are the
  likely Azure-native options.

# Production Large Batch Demo Dataset

The full 300-350 label demo dataset should not be committed to the Git
repository. In production, the large demo batch can be enabled by environment
configuration and loaded from Azure Blob Storage; local development should not
show the large demo batch button.

# Model Strategy

Use OpenRouter because it gives one API contract for multiple vision-capable
models and lets the service fail over when one provider is slow or unavailable.
Model IDs must be configuration, not hardcoded business logic.

OpenRouter is the default cloud provider. The backend should expose a provider
abstraction so local runs can use an alternate free/open-source model backend
without changing the frontend or verification result schema.

Recommended starting model order:

1. `google/gemini-3.1-flash-lite-preview` (quick and good performing)
2. `google/gemini-2.5-flash-lite`
3. `google/gemini-2.5-flash`


OpenRouter references:

- Vision model collection: https://openrouter.ai/collections/vision-models
- Model catalog API: https://openrouter.ai/api/v1/models
- Rate limits: https://openrouter.ai/docs/api/reference/limits

# Model Failover

- The backend should accept a configured ordered list such as
  `OPENROUTER_MODEL_PRIMARY`, `OPENROUTER_MODEL_FALLBACKS`, and
  `OPENROUTER_TIMEOUT_SECONDS`.
- Failover should trigger on provider timeout, `429`, selected `5xx`,
  unavailable model, and malformed model output.
- Failover must not hide uncertainty. If all models fail, the item returns
  `processing_error`.
- Every result must record which model produced it.
- Single-label failover must fit inside the 5-second hard ceiling. The service
  must use short per-model timeout budgets or skip fallback attempts once the
  request-level deadline is nearly exhausted.
- Model-swapping tests must prove that the backend:
  - Uses the primary model when it succeeds.
  - Falls back to the next model when the primary returns retryable failure.
  - Does not fall back on deterministic validation failures such as unsupported
    file type.
  - Records the selected model in result metadata.
  - Keeps output schema stable across model providers.

# Azure Deployment

- Build a Docker image from the repository.
- Push the image to Azure Container Registry.
- Run the image on Azure App Service for Linux as a custom container.
- Configure App Service to route traffic to container port `8000`.
- Keep the prototype as a single stateless Azure App Service container unless
  durable batch processing is intentionally added.
- Store secrets as Azure App Service application settings, not in GitHub Actions
  plaintext or repository files.
- Use Azure App Service logs and Application Insights for request latency,
  provider error rate, timeout rate, and model fallback rate.
- Use HTTPS at the public endpoint.
- Keep production-like configuration in environment variables so the same image
  can run locally and in Azure.
