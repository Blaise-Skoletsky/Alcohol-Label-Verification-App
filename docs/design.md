# Design

This document describes how the prototype should behave at runtime. The proposal owns goals, invariants, architecture decisions, and open product questions.

# Runtime Flow

- The user uploads one image or PDF page per verification item.
- Each uploaded item must contain both the label application and the label artwork in the same visual artifact.
- The frontend sends the combined application+label file to FastAPI.
- The frontend does not call model providers directly.
- FastAPI validates file type and file size before processing.
- The backend calls the configured vision provider with the combined application+label artifact.
- The model must identify when the application portion or label artwork portion is missing, unreadable, or ambiguous.
- The model returns structured JSON containing extracted values, pass/fail/needs-review statuses, confidence, and evidence.
- The backend normalizes and validates the model output before returning a result to the UI.
- The UI shows a compact result summary first, with visible evidence available for each field.
- The UI may keep recent client-side history in browser storage for up to one day. This history must not require server-side persistence.
- Supported combined application+label file types for the prototype are PNG, JPG/JPEG, and PDF.
- The demo flow is stateless and does not require accounts or per-user server-side history.

# UI and User Experience

The UI should be minimal, light, and work-focused. Use a plain white interface with restrained Azure-like styling: clean typography, simple borders, clear status colors, and obvious primary actions. Do not add dark mode, decorative visuals, or unnecessary configuration controls for the prototype.

## Primary Layout

- The first screen contains an upload area at the top.
- Results appear directly below the upload area.
- Uploading one or many combined application+label files creates one result row per file.
- The upload control should make the expected artifact obvious without requiring a long explanation.
- The user should understand the screen without reading instructions.

## Result Rows

- Each uploaded item appears as a compact horizontal status row.
- Each row shows the item name or identifier, current status, and overall result.
- Rows update progressively as uploads and model verification proceed.
- Rows should use familiar status indicators:
  - Green check for clear/pass.
  - Red X for fail or likely rejection.
  - Yellow warning for needs-review/manual verification.
  - Loading indicator for queued or processing.
- A row becomes clickable when enough information is available to inspect it.
- The list should remain useful when many items are present, so rows need to be compact and scannable.

## Detail View

- Clicking a result row opens a detail modal or focused detail panel.
- The detail view shows the submitted combined application+label artifact and the verification summary together.
- The summary shows each checked requirement with a status:
  - Green/pass when the field matches.
  - Red/fail when the field does not match.
  - Yellow/needs-review when the system cannot confidently decide.
- The detail view must make the evidence visible: extracted label value, application value, confidence, and reason.
- The detail view should not hide failed or needs-review fields behind extra clicks.

## Navigation

- The detail view includes right and left navigation controls to move between uploaded items.
- Navigation should work while the batch is still processing.
- If the user navigates to an item that is still queued or processing, the detail view should show that item with a waiting/loading state instead of blocking navigation.
- When that item finishes processing, the detail view should update in place.
- The user should be able to keep moving forward or backward through the batch as results load.

## Progressive Workflow

- The UI must not wait for the entire batch to finish before showing useful results.
- The reviewer should be able to start with the first completed labels while later labels continue processing.
- Completed rows should remain stable in the list and should not jump around as other rows update.
- Batch progress should be visually obvious without dominating the page.

# Batch Processing

- Batch upload supports up to the configured maximum item count, initially 400 combined application+label files in one user action.
- Batch submission returns quickly with a batch identifier instead of blocking until all labels finish.
- Each batch item is processed as an independent job with its own status and result.
- Provider calls pass through a bounded queue with an initial application default of five concurrent model calls.
- The queue must prevent large-batch fanout, including hundreds of simultaneous OpenRouter calls in cloud mode.
- The first processing wave should be small enough to return initial results within the single-label latency target when the provider is healthy.
- Batch results must be shown incrementally as each item completes. The UI must not wait for the entire batch before showing the first successful, failed, or needs-review result.
- The reviewer should be able to begin work as soon as the first completed results are available.
- Interactive single-label requests should have priority over background batch work.
- Failed items must be isolated so one bad image, malformed row, timeout, or provider failure does not fail the whole batch.
- For the initial demo, the queue can be in-process only if the README clearly states that in-flight batches are not durable across restarts.
- Batch progress should feel smooth in the UI. Prefer server-sent events for batch progress updates if the implementation stays simple in a single-container Azure App Service deployment; otherwise use short-interval polling as the fallback.
- The default architecture is stateless and must not store label artwork or application data in cloud storage.
- The expected demo load is one to two concurrent users, with the primary stress case being one user uploading 100-400 combined application+label files while processing proceeds five at a time.
- If durable batch processing is intentionally added later, Azure Blob Storage, Azure Queue Storage, and Azure Table Storage, Cosmos DB, or Postgres are the likely Azure-native options.

# Model Strategy

Use OpenRouter because it gives one API contract for multiple vision-capable models and lets the service fail over when one provider is slow or unavailable. Model IDs must be configuration, not hardcoded business logic.

OpenRouter is the default cloud provider. The backend should expose a provider abstraction so local runs can use an alternate free/open-source model backend without changing the frontend or verification result schema.

Recommended starting model order:

1. `google/gemini-3.5-flash`
   - Primary candidate for the prototype.
   - Fast multimodal model with image input, large context, and strong structured extraction fit.
   - Good first choice when latency matters but quality still needs to be high.

2. `google/gemini-3.1-flash-lite`
   - Second-tier Google fallback.
   - Vision-capable and optimized for low-latency, high-volume workloads.
   - Useful when the primary Gemini model is slow, unavailable, or too expensive for a batch run.

3. `openai/gpt-4.1-mini`
   - Third-tier provider-diverse fallback.
   - Vision-capable, relatively fast, and suitable for structured comparison tasks.
   - Useful if Google-hosted model routes are degraded.

4. `anthropic/claude-haiku-4.5`
   - Fourth-tier Anthropic fallback.
   - Fast vision-capable fallback for resilience if Google and OpenAI routes are degraded.

OpenRouter references:

- Vision model collection: https://openrouter.ai/collections/vision-models
- Model catalog API: https://openrouter.ai/api/v1/models
- Rate limits: https://openrouter.ai/docs/api/reference/limits

# Model Failover

- The backend should accept a configured ordered list such as `OPENROUTER_MODEL_PRIMARY`, `OPENROUTER_MODEL_FALLBACKS`, and `OPENROUTER_TIMEOUT_SECONDS`.
- Failover should trigger on provider timeout, `429`, selected `5xx`, unavailable model, and malformed model output.
- Failover must not hide uncertainty. If all models fail, the item returns `processing_error`.
- Every result must record which model produced it.
- Single-label failover must fit inside the 5-second hard ceiling. The service must use short per-model timeout budgets or skip fallback attempts once the request-level deadline is nearly exhausted.
- Model-swapping tests must prove that the backend:
  - Uses the primary model when it succeeds.
  - Falls back to the next model when the primary returns retryable failure.
  - Does not fall back on deterministic validation failures such as unsupported file type.
  - Records the selected model in result metadata.
  - Keeps output schema stable across model providers.

# Azure Deployment

- Build a Docker image from the repository.
- Push the image to Azure Container Registry.
- Run the image on Azure App Service for Linux as a custom container.
- Configure App Service to route traffic to container port `8000`.
- Keep the prototype as a single stateless Azure App Service container unless durable batch processing is intentionally added.
- Store secrets as Azure App Service application settings, not in GitHub Actions plaintext or repository files.
- Use Azure App Service logs and Application Insights for request latency, provider error rate, timeout rate, and model fallback rate.
- Use HTTPS at the public endpoint.
- Keep production-like configuration in environment variables so the same image can run locally and in Azure.
