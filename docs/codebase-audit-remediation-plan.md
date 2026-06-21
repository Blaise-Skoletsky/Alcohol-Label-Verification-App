# Codebase Audit Remediation Plan

Date: 2026-06-21

Source audit: [codebase-audit.md](codebase-audit.md)

This plan covers audit findings 1-6 and 8-12. Finding 7 is intentionally out of
scope.

## Regression Standard

The application should not report regressions while the codebase is refined.
Every remediation phase must preserve the current working baseline, add tests for
the behavior being changed, and run the full available verification set before
the phase is considered complete.

Current executable baseline:

- From repository root: `python -m pytest backend` passes with 61 tests and 1
  Starlette deprecation warning.
- From `frontend/`: `npm run build` passes.
- From `backend/`: `python -m pytest` currently fails 3 tests because fixture
  image paths are relative to the repository root. This is finding 10 and must be
  fixed early so local backend test runs are reliable.

Required phase gate after each change set:

1. `python -m pytest backend`
2. `python -m pytest` from `backend/`
3. `npm run build` from `frontend/`
4. Frontend unit tests once added
5. Playwright workflow tests once added

Any phase that changes provider orchestration, batch behavior, or response
contracts also needs focused regression tests before implementation is accepted.

## Architectural Risk

The main architectural smell is that prototype shortcuts now sit on critical
workflow boundaries:

- Batch row/file pairing is currently position-based in the backend.
- Batch state is memory-only and processing tasks are fire-and-forget.
- Batch UI state, validation, object URL lifecycle, partial submission, and
  lightbox behavior are concentrated in one large component.
- Prompt policy, result shaping, and frontend normalization are loose in places
  where the app now has stable contracts.

The plan below addresses boundary correctness first, then runtime pressure, then
refactoring and tooling.

## Current State Notes

- Finding 1 is still present: `BatchGridModal.submitReadyRows()` builds workspace
  rows only from ready rows, so unfinished rows are dropped.
- Finding 2 is partially prepared but not fixed: frontend batch rows include
  `filename`, and there are tests named for aligned/misaligned rows, but the
  backend still only checks row count and maps rows by index.
- Finding 10 is reproduced: backend tests pass from the repo root but fail from
  `backend/` because some tests open `frontend/public/...` as a current-working-
  directory-relative path.

## Phase 0: Freeze Baseline And Test Harness

Findings covered: 10, 11, foundation for all other findings.

Changes:

- Add a backend test helper that resolves paths from the repository root instead
  of the process working directory.
- Update route tests that read sample images to use that helper.
- Add scripts for repeatable verification:
  - backend root test command
  - backend package-directory test command
  - frontend build
  - frontend unit tests when introduced
  - frontend Playwright tests when introduced
- Add frontend test infrastructure before relying on frontend behavior changes:
  - Vitest for pure helper and hook-level tests.
  - Playwright script for browser workflows. The dependency already exists.
- Add backend Ruff and type-checking in a separate tooling commit after the
  behavioral baseline is stable, so formatter/linter churn is not mixed with
  functional fixes.

Tests:

- Prove `python -m pytest backend` and `python -m pytest` from `backend/` both
  pass.
- Add a minimal frontend test command that initially runs at least one smoke test
  for result/status helpers.

Acceptance:

- Existing backend 61-test suite still passes from both working directories.
- `npm run build` still passes.
- New test commands are documented and callable by npm or a repo-level script.

## Phase 1: Fix Partial Batch Preservation

Findings covered: 1, supports 9 and 12.

Decision:

- Preserve unfinished rows as drafts. This matches the existing hook comments and
  is safer than discarding reviewer input.

Changes:

- Change `BatchGridModal.submitReadyRows()` to create `LabelRow` objects for all
  grid rows, not only ready rows.
- Pass `allRows` to `onComplete`, but pass only ready row IDs as `verifyIds`.
- Update confirmation and toast copy so it says unfinished rows remain as drafts.
- Keep object URL ownership unchanged: rows that enter the workspace must keep
  their image URL; modal-only preview URLs must still be revoked when discarded.

Tests:

- Component or hook-level test: submit a batch grid with one complete row and one
  incomplete row; assert both rows enter the workspace and only the complete row
  starts verification.
- Browser workflow test: upload/select two batch rows, leave one incomplete,
  confirm partial verification, and assert the incomplete row remains visible as
  draft.
- Regression test for complete-only submission: all complete rows verify as
  before.

Acceptance:

- No reviewer-entered batch row disappears after partial verification.
- Ready rows still submit and poll normally.

## Phase 2: Enforce Filename-Based Batch Contracts

Findings covered: 2, supports 8 and 12.

Decision:

- Make `filename` a required backend batch row contract whenever `rows` is
  supplied.
- Pair uploaded files to application rows by filename, not array position.
- Reject ambiguous input instead of guessing.

Changes:

- In `batch_controller`, validate rows before upload processing:
  - rows must be a list with the same count as files
  - every row must be an object
  - every row must include a non-empty `filename`
  - row filenames must be unique
  - uploaded filenames must be unique
  - every uploaded filename must have exactly one row
  - no row filename may be missing from uploads
- Build a filename-to-row map and derive `application_values` in upload order
  from the map.
- Keep the frontend payload as `BatchRowPayload` with `filename`, and add a
  frontend boundary test that `submitBatch()` sends filenames that match the file
  names.

Tests:

- Backend accepts rows supplied in a different order when filenames match.
- Backend rejects missing filename.
- Backend rejects duplicate row filenames.
- Backend rejects duplicate uploaded filenames when rows are supplied.
- Backend rejects unmatched filename.
- Backend rejects extra row.
- Existing batch success and progress tests still pass.

Acceptance:

- A direct API caller cannot accidentally compare label image A to application
  data B because of row ordering.

## Phase 3: Make Provider Concurrency Explicit

Findings covered: 3.

Decision:

- Separate item concurrency from provider-call concurrency.
- Use a provider-call semaphore shared by the multi-pass provider so the real
  provider fanout is bounded. Rename or document the item-level setting so the
  deployed operator can reason about both controls.

Changes:

- Add explicit settings:
  - `batch_item_concurrency`: how many batch items may be in progress.
  - `provider_call_concurrency`: how many model calls may be in flight.
- Update docs, `.env.example`, config API, and frontend display names to avoid
  implying that item concurrency equals provider-call concurrency.
- Thread the provider-call limiter through the provider factory or the
  verification service boundary so all specialist calls use the same limit.
- Ensure single-label interactive requests do not get starved by background
  batch work. If a shared global semaphore is used, reserve capacity or document
  the fairness decision explicitly.

Tests:

- Unit test the multi-pass provider with a fake runner that records concurrent
  calls; prove the maximum in-flight calls never exceeds
  `provider_call_concurrency`.
- Batch service test proves no more than `batch_item_concurrency` items enter
  processing at once.
- Config endpoint test proves both concurrency values are exposed with clear
  names.

Acceptance:

- Runtime behavior matches configuration names.
- Batch fanout cannot exceed the configured provider-call ceiling.

## Phase 4: Track Batch Tasks And Add Prototype Cleanup

Findings covered: 4.

Decision:

- Keep the prototype single-process and in-memory for now, but make that runtime
  mode explicit and safer.
- Do not add a compatibility queue or durable storage layer until production
  durability is actually in scope.

Changes:

- Store created task handles in `BatchService`.
- Add a done callback that logs unexpected task failures and marks the batch as
  failed or completed with per-item `processing_error` states where possible.
- Add TTL cleanup for completed batches and their task handles.
- Add API/design documentation that batch state is process-local and not durable
  across restart or multiple app instances.

Tests:

- Batch service test: an unexpected processor exception marks remaining items as
  `processing_error` and does not leave the batch permanently `processing`.
- Batch service test: completed batches older than TTL are removed.
- Batch service test: active batches are not cleaned up.
- Logging test: unexpected task failures emit a useful log line without payload
  contents or secrets.

Acceptance:

- No background task can die silently.
- Prototype limits are visible in documentation and behavior.

## Phase 5: Tighten Frontend Response Contracts

Findings covered: 8.

Decision:

- Normalize only at the network boundary and stop treating missing backend fields
  as passing checks.

Changes:

- Define strict frontend API response types matching backend
  `VerificationResult`, `BatchState`, and `BatchItemState`.
- Replace broad alias lookup in normal runtime paths with explicit parsing.
- Keep any transitional parsing only in tests or removed dead paths; do not keep
  old/new production compatibility branches unless a live consumer requires it.
- Change row display helpers so missing required verification fields render as
  `processing-error` or an explicit schema error, not pass.

Tests:

- Unit test valid `VerificationResult` normalization.
- Unit test missing field result becomes schema error / processing error.
- Unit test malformed batch item does not show green mini-checks.
- Browser test for one successful single-label verification still displays the
  same user-visible pass summary.

Acceptance:

- Backend contract drift is visible in the UI and tests.
- No missing field defaults to pass.

## Phase 6: Consolidate Provider Runner And Verification Strategy

Findings covered: 5.

Decision:

- Split provider runner from verification strategy and remove the unused
  provider-level single-pass `verify()` path unless a real runtime mode is added
  for it.

Changes:

- Define a runner interface that only executes one prompt against a provider.
- Make `MultiPassVerificationProvider` or a renamed orchestrator own the
  verification strategy.
- Move shared timeout, parse, model metadata, and error handling into the runner
  path used by all provider calls.
- Delete dead provider-level `verify()` implementations after tests prove no
  factory or route still calls them.

Tests:

- Factory test proves the configured provider is wrapped in the orchestrator.
- Provider runner tests prove OpenRouter/local runners still format requests and
  parse responses correctly.
- Verification service tests prove route behavior and result metadata are stable.

Acceptance:

- There is one production verification path for prompt orchestration.
- Provider-specific classes do not carry stale single-pass policy behavior.

## Phase 7: Extract Prompt Policy From Prompt Rendering

Findings covered: 6. Finding 7 remains excluded.

Decision:

- Extract deterministic policy data and prompt planning without changing result
  guard semantics from finding 7.

Changes:

- Create a small policy model for:
  - field definitions
  - beverage-class applicability rules
  - specialist grouping
  - deterministic skipped-field output
- Keep prompt text close to the field definitions, but make prompt rendering a
  consumer of a structured prompt plan.
- Avoid reworking guard exception logic in this phase because finding 7 is out of
  scope.

Tests:

- Snapshot or structured-plan tests for each beverage class.
- Existing prompt substring tests remain until snapshots cover the same risk.
- Golden tests prove skipped fields and specialist group assignments are
  unchanged.

Acceptance:

- Prompt behavior is easier to review without intentional wording drift.
- No out-of-scope result guard policy change is introduced.

## Phase 8: Refactor Batch UI Into Smaller Units

Findings covered: 9, also protects 1.

Decision:

- Refactor after the partial-submit behavior is fixed and covered by browser
  tests. Do not combine behavior changes with the component split.

Changes:

- Extract `useBatchGridRows` for row modeling, validation, edits, and status
  derivation.
- Extract presentational components:
  - `BatchGridTable`
  - `BatchGridRow`
  - `BatchPartialConfirmDialog`
  - `ImageZoomLightbox`
- Move repeated inline style objects into CSS classes.
- Keep public props for `BatchGridModal` stable unless all callers are updated in
  the same change.

Tests:

- Existing partial-batch Playwright test must pass before and after the split.
- Component tests for row validation and partial confirmation.
- Manual visual/browser screenshot check at desktop and mobile widths after CSS
  movement.

Acceptance:

- No user-visible behavior change except previously fixed partial preservation.
- The modal no longer owns unrelated row modeling, dialog, table, and lightbox
  logic directly.

## Phase 9: Documentation Alignment

Findings covered: 12.

Changes:

- Update `docs/design.md` current limitations:
  - in-memory process-local batch state
  - polling behavior
  - provider-call concurrency limit
  - partial batch draft preservation
- Update README startup/test instructions with the final verification commands.
- Ensure comments in `useLabelRows` and batch components match tested behavior.

Tests:

- Documentation-only changes still run the standard phase gate.
- When docs claim a workflow behavior, confirm there is a matching automated
  test or explicitly label it as a current limitation.

Acceptance:

- Runtime behavior, tests, and docs describe the same system.

## Phase 10: Quality Tooling And CI Hardening

Findings covered: 11.

Changes:

- Backend:
  - Add Ruff for lint and formatting.
  - Add mypy or pyright after type-surface cleanup.
  - Add coverage for core services once tests are stable.
- Frontend:
  - Add ESLint with React/TypeScript rules.
  - Add Vitest for pure helpers and hooks.
  - Add Playwright tests for:
    - single-label verification
    - partial batch workflow
    - batch polling with one pass and one fail
- CI:
  - Run backend tests from repo root and from `backend/`.
  - Run frontend build.
  - Run frontend unit tests.
  - Run Playwright tests with mocked provider/network responses for deterministic
    behavior.

Acceptance:

- CI blocks contract drift and workflow regressions before review.
- Local commands match CI commands.

## Recommended Implementation Order

1. Phase 0: test path portability and harness commands.
2. Phase 1: partial batch preservation.
3. Phase 2: filename-based backend batch pairing.
4. Phase 3: explicit provider-call concurrency.
5. Phase 4: tracked batch tasks and TTL cleanup.
6. Phase 5: strict frontend response contract.
7. Phase 6: provider runner/orchestrator split.
8. Phase 7: prompt policy extraction, excluding finding 7.
9. Phase 8: BatchGridModal split.
10. Phase 9: documentation alignment.
11. Phase 10: broader tooling and CI hardening.

## Final No-Regression Checklist

Before reporting completion for the whole audit remediation:

- `python -m pytest backend` passes.
- `python -m pytest` from `backend/` passes.
- Backend lint and type checks pass if introduced.
- `npm run build` passes.
- Frontend unit tests pass.
- Playwright workflow tests pass.
- Partial batch workflow proves unfinished rows remain drafts.
- Batch filename mismatch tests prove wrong row/file pairing is rejected.
- Provider concurrency tests prove configured call ceilings are enforced.
- Strict frontend contract tests prove malformed results do not render as pass.
- Docs accurately state the remaining prototype limitations.
