# Goals

- Accept one primary input for every verification: a single image or PDF page that contains both the label application and the label artwork.
- Treat missing application content or missing label artwork inside the submitted image as a model-detected issue that returns `needs_review`, `fail`, or `processing_error` with evidence.
- Verify the initial production scope with high confidence:
  - Brand name on the artwork matches the label application.
  - Alcohol by volume (ABV) on the artwork is present and consistent with the label application.
  - Government Health Warning Statement is present on the container label.
- Treat TTB mandatory-label fields as the baseline compliance vocabulary: brand name, class/type designation, alcohol content where required, net contents, name/address, country of origin for imports, and health warning statement.
- Verify the Government Health Warning strictly when readable, including required wording and the `GOVERNMENT WARNING:` prefix formatting. If the warning is unreadable, return `needs_review` instead of passing it.
- Optimize for a cloud single-label result target of p95 <= 3 seconds from request receipt to structured result.
- Enforce a hard cloud single-label result ceiling of p95 <= 5 seconds. Anything slower is a product failure, not acceptable normal behavior.
- Keep the UI extremely simple: upload/select files, start verification, view result status, inspect mismatches, and export/download results. Avoid optional controls unless they directly improve the core review workflow.
- Provide a result that an agent can trust quickly: clear pass/fail/needs-review status, visible evidence, and no buried controls.
- Design for older and less technical users: obvious primary action, minimal navigation, readable text, and no configuration-heavy workflow.
- Support batch uploads up to a configurable maximum, initially 400 label applications in one user action.
- Make batch behavior operationally realistic: accepting a batch should be fast, each item should produce an independent result, and the user should see progress and per-item failures without losing the whole batch.
- Secure every endpoint and data path for government use: authenticated access, least-privilege authorization, encrypted transport, no accidental public access, no secret leakage, auditable request handling, and safe file processing.
- Treat cloud/API dependency risk as part of the design, including outbound network restrictions, provider failures, latency spikes, and rate limits.
- Keep the prototype deployable as a public/demo app while documenting what would need to change for a real government production deployment.
- Keep the app fully runnable both locally and in cloud deployment. If cloud egress or OpenRouter access is blocked, local mode should be able to run against a free/open-source model path without requiring an OpenRouter key.
- Avoid storing submitted label artwork or application data longer than needed for the prototype workflow unless explicitly configured.
- Keep the initial prototype stateless: no accounts, no server-side history, and no cloud persistence for submitted labels or application data.
- Preserve recent activity in the browser where practical, with a target retention window of one day.
- Build a test suite around real or realistic label applications and artwork that includes both passing and failing examples.
- Prefer real public or user-provided label/application examples for test fixtures; synthetic fixtures should not be the primary testing strategy.
- Include subjective-quality fixtures in the test suite: borderline brand-name matches, partial warning text, difficult ABV formatting, glare, blur, skew, curved bottles, poor lighting, low contrast, and awkward camera angles.
- Include test cases for exact-warning failures, including changed wording, wrong capitalization, missing prefix, and warning text that is present but visually hard to read.
- Handle poor image quality as a first-class requirement. The system should attempt robust extraction and confidence scoring before asking for a better image.
- Return structured, reviewable evidence for each decision: extracted field value, application value, pass/fail/needs-review status, confidence, and reason.
- Prefer clear "needs review" outcomes over false certainty when evidence is incomplete, ambiguous, or internally inconsistent.

# Invariants

- A verification request must never return only an unstructured natural-language answer. Every result must include machine-readable statuses for brand name match, ABV correctness, and government warning presence.
- A single-label cloud verification must meet p95 <= 5 seconds under the agreed production workload. If this cannot be met, the system must degrade explicitly with a timeout or retryable status rather than silently hanging.
- The p95 <= 3 second target is the design target; p95 > 5 seconds is a release blocker for the single-label path.
- Batch upload must accept up to the configured maximum label count without browser crashes, request-size failures, or all-or-nothing processing.
- A large batch must not be implemented as one long synchronous request that blocks until every label is fully verified.
- Upload capacity and processing concurrency are separate controls. Accepting 400 labels does not mean running 400 model calls at once.
- One bad label, unreadable image, model failure, or malformed application row must not fail the entire batch.
- The original combined application+label upload must remain linked to every result so a reviewer can trace a decision back to its evidence.
- The system must distinguish these result states at minimum: `pass`, `fail`, `needs_review`, and `processing_error`.
- Poor image quality must not be an automatic rejection by itself. The system must attempt extraction, report confidence, and identify the specific reason review is needed.
- The system must not mark a field as passing unless the extracted evidence supports the application value within documented tolerance rules.
- ABV comparison must use numeric normalization before comparison, including common equivalent forms such as percent ABV and proof where applicable, but the normalized values must match exactly. `49.5%` is not the same as `50%`.
- Brand-name comparison must allow documented formatting differences while still flagging substantive wording differences.
- Government warning detection must be strict: required statement wording, required `GOVERNMENT WARNING:` prefix, and required capitalization must be verified when readable. Partial or approximate warning text must not pass.
- Security must be on by default for every non-local endpoint. Unauthenticated production verification endpoints are not allowed.
- The public unauthenticated deployment is demo-only and must not be represented as the production security posture.
- Secrets must never be committed, logged, returned to the client, embedded in test fixtures, or exposed in generated reports.
- The frontend must never call OpenRouter, a local model server, or any other model provider directly. All provider access must go through the backend.
- Uploaded files must be treated as untrusted input. The service must validate file type, size, and processing boundaries before analysis.
- Test coverage must include representative pass, fail, and needs-review cases for each core requirement: brand name, ABV, and government warning.
- The test suite must include degraded-image fixtures and must assert that the system produces useful evidence or a specific needs-review reason.
- Any model-backed decision must be reproducible enough for review: prompt/version/config metadata or equivalent execution context must be captured with the result.
- The model provider must be selected by configuration. OpenRouter is the cloud default, but local execution must not require an OpenRouter key when a local/free model backend is configured.
- The product must not present itself as final legal approval. It is a verification aid that flags likely compliance issues and evidence for human review.

# Architecture

## Proposed Stack

- Use a single repository containing both the frontend and backend.
- Backend: Python with FastAPI.
- Frontend: TypeScript with React.
- AI provider access: OpenRouter from the backend only.
- Local model access: configurable backend provider for a free/open-source local model path when OpenRouter is unavailable or intentionally disabled.
- Deployment target: Azure App Service for Linux running a custom container.
- Packaging: one Docker image for the prototype, with the backend serving the API and the built frontend assets.
- CI/CD: GitHub Actions workflow runs on pushes to `main`, builds the Docker image, runs tests, and deploys the service.

Detailed runtime behavior, UI behavior, batch-processing strategy, model strategy, failover behavior, and Azure deployment mechanics live in [design.md](design.md).

## Security Posture

This prototype can use OpenRouter, but that is not automatically equivalent to a government production deployment. A real government deployment would need approved model-provider routing, egress allowlisting, retention policy review, audit logging, access control, and security review before processing sensitive submissions.

Prototype requirements:

- The demo deployment is intentionally public and unauthenticated. This is acceptable only because the prototype is stateless and not intended to process sensitive real submissions.
- OpenRouter keys stay server-side only.
- Uploaded files are treated as untrusted input.
- The backend enforces file size and content-type limits before calling a model.
- Request and result logs must not include secrets or full uploaded file contents.
- The service should avoid storing uploaded label artwork or application data beyond the active prototype workflow unless explicitly configured.
- A production or government deployment would need authentication and authorization before use.

## Open Design Questions

- None currently. Future production-only improvements are tracked in the README.
