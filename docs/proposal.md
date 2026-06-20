# Goals

- Accept one primary verification item made from two user-provided inputs: one uploaded label-artwork image and structured application text entered in an app form.
- Treat missing or incomplete form data as user-input validation or a field-level `fail` condition, depending on the requirement. Treat missing, unreadable, or ambiguous label artwork as a model-detected issue that returns `fail` or `processing_error` with evidence.
- Do not support a combined application+label image workflow. The app requires a label photo plus structured text entry.
- Verify the initial production scope with high confidence:
  - Brand name on the artwork matches the application form data.
  - Class/type designation on the artwork is compatible with the application form data.
  - Alcohol content on the artwork is present and consistent with the application form data when required.
  - Net contents on the artwork match the application form data.
  - Name and address of bottler/producer on the artwork match the application form data.
  - Country of origin appears and matches the application form data for imported products.
  - Government Health Warning Statement appears exactly on the container label.
- Treat TTB mandatory-label fields as the baseline compliance vocabulary: brand name, class/type designation, alcohol content where required, net contents, name/address, country of origin for imports, and health warning statement.
- Verify the Government Health Warning strictly, including required wording and the all-caps, visibly bold `GOVERNMENT WARNING:` prefix. If the warning is unreadable, partial, title case, rewritten, or approximate, return `fail`.
- Optimize for a cloud single-label result target of p95 <= 3 seconds from request receipt to structured result.
- Enforce a hard cloud single-label result ceiling of p95 <= 5 seconds. Anything slower is a product failure, not acceptable normal behavior.
- Keep the UI extremely simple: upload/select files, start verification, view result status, inspect mismatches, and export/download results. Avoid optional controls unless they directly improve the core review workflow.
- Provide a result that an agent can trust quickly: clear pass/fail status, visible evidence, and no buried controls.
- Design for older and less technical users: obvious primary action, minimal navigation, readable text, and no configuration-heavy workflow.
- Support batch submission up to a configurable maximum, initially 400 verification items in one user action.
- Make batch behavior operationally realistic: accepting a batch should be fast, each item should produce an independent result, and the user should see progress and per-item failures without losing the whole batch.
- Secure every endpoint and data path for government use: authenticated access, least-privilege authorization, encrypted transport, no accidental public access, no secret leakage, auditable request handling, and safe file processing.
- Treat cloud/API dependency risk as part of the design, including outbound network restrictions, provider failures, latency spikes, and rate limits.
- Keep the prototype deployable as a public/demo app while documenting what would need to change for a real government production deployment.
- Keep the app fully runnable both locally and in cloud deployment. If cloud egress or OpenRouter access is blocked, local mode should be able to run against a free/open-source model path without requiring an OpenRouter key.
- Avoid storing submitted label artwork or application data longer than needed for the prototype workflow unless explicitly configured.
- Keep the initial prototype stateless: no accounts, no server-side history, and no cloud persistence for submitted labels or application data.
- Preserve recent activity in the browser where practical, with a target retention window of one day.
- Build a test suite around real or realistic label artwork and application-data examples that includes both passing and failing cases.
- Prefer real public or user-provided label artwork and application data for test fixtures; synthetic fixtures should not be the primary testing strategy.
- Include subjective-quality fixtures in the test suite: borderline brand-name matches, partial warning text, difficult ABV formatting, glare, blur, skew, curved bottles, poor lighting, low contrast, and awkward camera angles.
- Include test cases for exact-warning failures, including changed wording, wrong capitalization, missing prefix, and warning text that is present but visually hard to read.
- Handle poor image quality as a first-class requirement. The system should attempt robust extraction and identify specific unreadable or ambiguous areas before asking for a better image.
- Return structured, reviewable evidence for each decision: extracted label value, entered application value or fixed warning requirement, pass/fail status, evidence, and reason.
- Prefer explicit failure outcomes over false certainty when evidence is incomplete, ambiguous, or internally inconsistent.

# Invariants

- A verification request must never return only an unstructured natural-language answer. Every result must include machine-readable statuses for brand name, class/type designation, alcohol content, net contents, name/address, country of origin, and government warning.
- A single-label cloud verification must meet p95 <= 5 seconds under the agreed production workload. If this cannot be met, the system must degrade explicitly with a timeout or retryable status rather than silently hanging.
- The p95 <= 3 second target is the design target; p95 > 5 seconds is a release blocker for the single-label path.
- Batch upload must accept up to the configured maximum label count without browser crashes, request-size failures, or all-or-nothing processing.
- A large batch must not be implemented as one long synchronous request that blocks until every label is fully verified.
- Upload capacity and processing concurrency are separate controls. Accepting 400 labels does not mean running 400 model calls at once.
- One bad label, unreadable image, model failure, or malformed application row must not fail the entire batch.
- The submitted label image and entered application-data snapshot must remain linked to every result so a reviewer can trace a decision back to its evidence.
- The system must distinguish these result states at minimum: `pass`, `fail`, and `processing_error`.
- Poor image quality must not be an automatic rejection by itself. The system must attempt extraction and identify the specific failure reason.
- The system must not mark a field as passing unless the extracted evidence supports the application value within documented tolerance rules.
- ABV comparison must use numeric normalization before comparison, including common equivalent forms such as percent ABV and proof where applicable, but the normalized values must match exactly. `49.5%` is not the same as `50%`.
- Brand-name comparison must allow documented formatting differences while still flagging substantive wording differences.
- Government warning detection must be strict: required statement wording, required `GOVERNMENT WARNING:` prefix, required all-caps capitalization, and visibly bold prefix formatting must be verified. Unreadable, partial, title-case, rewritten, or approximate warning text must fail.
- The UI and API must treat application fields as structured product data, not as separate provider-specific OpenRouter query controls. OpenRouter routing remains behind the backend provider abstraction.
- Security must be on by default for every non-local endpoint. Unauthenticated production verification endpoints are not allowed.
- The public unauthenticated deployment is demo-only and must not be represented as the production security posture.
- Secrets must never be committed, logged, returned to the client, embedded in test fixtures, or exposed in generated reports.
- The frontend must never call OpenRouter, a local model server, or any other model provider directly. All provider access must go through the backend.
- Uploaded files and submitted form values must be treated as untrusted input. The service must validate file type, file size, form shape, and processing boundaries before analysis.
- Test coverage must include representative pass and fail cases for each core requirement: brand name, ABV, and government warning.
- The test suite must include degraded-image fixtures and must assert that the system produces useful evidence or a specific failure reason.
- Any model-backed decision must be reproducible enough for review: prompt/version/config metadata, the submitted application-data snapshot, or equivalent execution context must be captured with the result.
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
