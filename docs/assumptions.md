# Assumptions

This prototype is intended for a Treasury-facing rollout demo. The preferred path is an online hosted app, but the app must remain easy to run locally if Treasury network policy, firewall rules, outbound model-provider access, or cloud deployment constraints block the hosted version.

## Deployment Assumptions

- The primary demo deployment is Azure App Service for Linux running a single custom Docker container.
- The same Docker image must run locally and in Azure.
- Local setup should require as few commands as possible, with `docker compose up --build` as the default path.
- Local demo mode must not require a `.env` file.
- `.env` is required only when enabling OpenRouter or other real credentials.
- The app is stateless by default. Restarting the container may clear in-flight work.
- The initial demo does not require accounts, sign-in, or role-based access control.
- The public unauthenticated deployment is demo-only and must not be described as the production government security posture.

## Model Provider Assumptions

- The frontend must never call OpenRouter, a local model server, or any other model provider directly.
- The frontend only calls the FastAPI backend.
- All model-provider credentials stay server-side.
- OpenRouter is the default cloud model provider.
- Local mode must be able to run without an OpenRouter key when configured to use a free/open-source local model backend.
- Local mode should default to a non-credentialed provider such as `mock` until a local/free model backend is wired in.
- The frontend should not change when switching between OpenRouter and a local model backend.
- Backend responses must keep the same result schema regardless of which model provider produced the result.

## Storage Assumptions

- The server must not store uploaded label artwork, PDFs, or application data in cloud storage for the initial prototype.
- Backend processing may use memory or temporary files while a request or in-process batch is active.
- Recent history should live in the browser where practical.
- Browser-local history should target roughly one day of retention.
- Server-side retention can be added later only as an explicit design change.

## Product Assumptions

- The app is a verification aid, not final legal approval or TTB certification.
- The UI should stay simple enough for non-technical compliance users.
- The current workflow uses one uploaded image or PDF page containing both the application and the label artwork.
- The model is responsible for flagging uploads where the application portion or label artwork portion is missing, unreadable, or ambiguous.
- The primary demo traffic assumption is one to two concurrent users.
- The main stress case is one user uploading roughly 100-400 combined application+label files in a batch.
- Batch upload size and model-call concurrency are separate. A large upload should process through a small bounded worker pool, initially five concurrent model calls.
- Batch results should appear incrementally as soon as individual labels complete so a reviewer can begin working before the full batch finishes.
- The app should support PNG, JPG/JPEG, and PDF combined application+label artifacts.
- Real public or user-provided label/application examples are preferred for tests. Synthetic labels are not the primary fixture strategy.

## Security Assumptions

- OpenRouter and local model credentials must never be exposed to the browser.
- OpenRouter and other real credentials are optional for local demo mode and required only when the selected provider needs them.
- Secrets must not be committed to Git.
- Request logs must not include secrets or full uploaded file contents.
- Uploaded files are untrusted input and must be validated before model processing.
- A production government deployment would need authentication, authorization, approved model routing, retention review, audit logging, and egress review.
