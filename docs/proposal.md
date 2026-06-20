# Proposal

This document explains the product approach and the high-level system shape. The
canonical verification scope, operating assumptions, regulatory source links, and
field-by-field rule matrix live in [assumptions.md](assumptions.md).

## Goals

- Build a verification aid for alcohol label review, not a final legal approval
  or TTB certification system.
- Use a structured workflow: one label-artwork image plus application values
  entered as product data, rather than a combined application-and-label OCR flow.
- Return a result a reviewer can trust quickly: overall status, field-level
  status, submitted value, extracted label value, reason, and evidence.
- Keep the UI simple enough for non-technical compliance users: add labels,
  verify, inspect mismatches, and export or review results without extra
  configuration controls.
- Support both single-label review and operationally realistic batches where
  items finish independently and partial failures do not lose the whole batch.
- Optimize for a cloud single-label result target of p95 <= 5 seconds.
- Keep the app runnable locally and in a hosted demo environment, with provider
  routing hidden behind the backend.
- Keep the prototype stateless unless an explicit production persistence design
  is added later.

## Invariants

- A verification request must return structured, machine-readable results, not
  only a natural-language answer.
- The submitted label image and application-data snapshot must remain linked to
  each result so a reviewer can trace the decision back to its evidence.
- The system must distinguish at least `pass`, `fail`, and `processing_error`.
- Missing, unreadable, ambiguous, or internally inconsistent evidence must be
  handled explicitly instead of being treated as a confident pass.
- Batch upload must not be implemented as one long synchronous request that
  blocks until every label finishes.
- Upload capacity and processing concurrency are separate controls. Accepting a
  large batch must not mean starting a large number of simultaneous model calls.
- One bad label, unreadable image, malformed row, timeout, or provider failure
  must not fail the whole batch.
- Model provider access must go through the backend. The frontend must not call
  OpenRouter, local model servers, or any other model provider directly.
- Provider selection must be configuration-driven so local and hosted execution
  keep the same frontend and result schema.
- The prototype must not present itself as final legal approval.

## Architecture

## Proposed Stack

- Use a single repository containing both the frontend and backend.
- Backend: Python with FastAPI.
- Frontend: TypeScript with React.
- AI provider access: OpenRouter from the backend only.
- Local model access: configurable backend provider for a free/open-source local
  model path when OpenRouter is unavailable or intentionally disabled.
- Deployment target: Azure App Service for Linux running a custom container.
- Packaging: one Docker image for the prototype, with the backend serving the API
  and the built frontend assets.
- CI/CD: GitHub Actions workflow runs on pushes to `main`, builds the Docker
  image, runs tests, and deploys the service.

Detailed runtime behavior, UI behavior, batch-processing strategy, model
strategy, failover behavior, and Azure deployment mechanics live in
[design.md](design.md).

## Security Posture

The security posture for the prototype is intentionally limited: it can support a
public demo path, but that should not be represented as a production government
deployment posture.

The detailed security assumptions and production gaps are tracked in
[assumptions.md](assumptions.md). A real production deployment would need
approved model routing, authentication and authorization, retention review,
audit logging, egress review, and operational monitoring before processing
sensitive submissions.
