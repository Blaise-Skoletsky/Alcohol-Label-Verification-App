# Codebase Audit

Date: 2026-06-21

## Scope

This audit covers the current repository state for the Alcohol Label Verification
App, including the FastAPI backend, React frontend, provider integrations,
batch-processing flow, tests, scripts, and documentation. The focus is
correctness, maintainability, architecture boundaries, test quality, and
production-readiness risks.

## Validation Performed

- `python -m pytest backend` from the repository root: **61 passed**, 1 warning.
- `npm run build` from `frontend/`: **passed**.
- `python -m pytest` from `backend/`: **failed** because several tests reference
  sample images through repo-root-relative paths. This is listed as a test
  portability issue below.

## Executive Summary

The core architecture is coherent for a prototype: the frontend owns the
reviewer workspace, the backend owns model-provider access, the prompt/result
contract is structured, and the verification guard is a good protection against
overconfident model output.

The biggest risks are not framework choices. They are contract mismatches and
state-management seams:

- The batch UI says unfinished rows are preserved, but the implementation drops
  them when verifying only completed rows.
- The backend batch API accepts application rows by position only and ignores
  filename matching, which can pair the wrong application values with a label.
- The batch queue is in-memory and driven by untracked background tasks, which
  is fine for a demo but fragile for restart, multi-instance, or production use.
- Batch concurrency is item-based, but each item now fans out into three
  parallel model calls, so the actual provider call concurrency is higher than
  the configuration name suggests.
- Several important modules are becoming large string/state machines rather than
  small, explicit policy modules.

## Findings

### 1. Partial Batch Verification Drops Unfinished Rows

Severity: **High**

`BatchGridModal` confirms partial verification when only some rows are ready, but
`submitReadyRows()` builds `LabelRow` objects only from `readyRows` and passes
only those rows to `onComplete`.

Evidence:

- `frontend/src/components/BatchGridModal.tsx:237-263`
- `frontend/src/hooks/useLabelRows.ts:241-245`

The hook comment says every row should land in the workspace and unfinished rows
should stay as drafts. The modal currently does the opposite: unfinished rows are
skipped and disappear when the modal closes. This is a user-facing data-loss bug
because a reviewer can type several incomplete applications, choose to verify
the ready subset, and lose the unfinished work.

Recommended fix:

Create `LabelRow` objects for all grid rows, including incomplete rows. Pass all
rows as `allRows`, but pass only ready row IDs as `verifyIds`. If the intended
behavior is actually to discard unfinished rows, remove the stale hook comment
and make the confirmation copy explicitly say those rows will be discarded.

### 2. Batch Rows Are Matched To Files Only By Array Position

Severity: **High**

The batch API requires the `rows` JSON array length to match the uploaded file
count, then converts rows directly by index. It does not validate that
`row.filename` matches the corresponding uploaded file.

Evidence:

- `backend/app/controllers/batch_controller.py:117-142`
- `frontend/src/hooks/useLabelRows.ts:311-325`

The frontend currently submits files and rows in the same order, but the backend
contract is unsafe for direct API use, future spreadsheet import, retries, or any
client-side ordering bug. A row order mismatch would cause the app to compare a
label image against another product's application values and return a confident
but wrong review result.

Recommended fix:

Make `filename` part of the backend contract. Reject rows when filenames are
missing, duplicated, unmatched, or not in the same order. Better: build a
filename-to-application map and pair files by filename explicitly.

### 3. Batch Concurrency Understates Real Provider Fanout

Severity: **High**

`BatchService` limits concurrent batch items with `batch_concurrency`, but each
item is processed by `MultiPassVerificationProvider`, which runs three
specialist model calls in parallel. With the default batch concurrency of 5, the
system can issue up to 15 simultaneous provider calls before considering
OpenRouter fallback behavior.

Evidence:

- `backend/app/services/batch_service.py:89-124`
- `backend/app/providers/multi_pass_provider.py:18-48`
- `backend/app/core/settings.py:83`

This does not make the design wrong, but the control is mislabeled from an
operational perspective. It can surprise deployments that think they limited
provider pressure to five calls. In cloud mode this affects rate limits, cost
spikes, and timeout behavior. In local mode it can overload a single local
vision model.

Recommended fix:

Either rename the setting to clarify it is item concurrency, or introduce a
provider-call semaphore shared under the multi-pass provider. The second option
is cleaner if production needs an actual provider-call ceiling.

### 4. Batch State Is In-Memory And Background Tasks Are Untracked

Severity: **High for production, Medium for prototype**

`BatchService` stores all batch state in an instance dictionary and starts
processing with `asyncio.create_task()` without keeping a task handle.

Evidence:

- `backend/app/services/batch_service.py:22-27`
- `backend/app/services/batch_service.py:53-69`
- `backend/app/services/batch_service.py:77-80`

This means active batches disappear on process restart, do not work across
multiple app instances, and never expire from memory. If `_process_batch()` ever
raises outside the per-item verification path, the task can die without a
durable failure state. The design docs already frame durable storage as a later
production concern, so this is acceptable only if the app remains a single
process demo.

Recommended fix:

For the prototype, add explicit documentation in the API/design docs and add a
simple TTL cleanup for old completed batches. For production, move batch state
to durable storage and route processing through a real queue or at least a
tracked task registry with failure marking.

### 5. Provider Classes Keep A Legacy Single-Pass `verify()` Path That Is No Longer The Main Path

Severity: **Medium**

The provider factory always wraps `OpenRouterVerificationProvider` or
`LocalModelVerificationProvider` inside `MultiPassVerificationProvider`.
Multi-pass calls `runner.run_prompt()`, not the runner's `verify()`. Both
provider classes still carry a full single-pass `verify()` implementation.

Evidence:

- `backend/app/providers/factory.py:9-17`
- `backend/app/providers/openrouter_provider.py:34-98`
- `backend/app/providers/openrouter_provider.py:100-164`
- `backend/app/providers/local_provider.py:42-83`
- `backend/app/providers/local_provider.py:85-126`

This creates two behavior paths for prompt building, parsing, timeout messaging,
and deterministic fields. One path is mostly bypassed in normal runtime, which
makes it easy for future fixes to update the multi-pass path but leave the
single-pass path stale.

Recommended fix:

Split the concept explicitly:

- provider runner: knows how to run one prompt against OpenRouter or local model
- verification orchestrator: owns single-pass or multi-pass strategy

Then delete provider-level `verify()` unless there is a real runtime mode that
uses it.

### 6. Prompt Construction Is A Large String-Policy Module

Severity: **Medium**

`VerificationPromptService` is over 500 lines and mixes prompt text, field
policy, applicability planning, JSON formatting, normalization, ABV parsing, and
specialist prompt partitioning.

Evidence:

- `backend/app/services/verification_prompt_service.py`

This is understandable for a prototype, but it is now a central policy engine.
Any small wording change risks touching the same large file as applicability
logic. The tests mostly assert substrings, which catches some regressions but
does not make the policy model easier to reason about.

Recommended fix:

Extract a small verification policy model:

- field definitions and applicability rules
- specialist grouping
- prompt rendering
- deterministic skipped-field generation

Keep the actual prompt text close to field definitions, but separate rule
selection from string rendering. Add snapshot-style tests for generated prompts
or structured prompt plans so reviewers can see intentional changes clearly.

### 7. The Result Guard Depends On Model-Written Reason Text For Some Policy Decisions

Severity: **Medium**

The result guard is valuable, but some guard paths infer exceptions from freeform
`application_value`, `label_value`, and `reason` strings. For example,
`_has_clear_exception()` passes alcohol-content omissions when certain marker
phrases appear in model-returned text.

Evidence:

- `backend/app/services/result_guard_service.py:260-286`

This is brittle because the model can phrase the same idea differently, or worse,
include exception-like wording in a bad result. The guard should be the
deterministic layer, so it should rely as little as possible on model prose.

Recommended fix:

Move applicability decisions into `VerificationPromptService` or a shared policy
object and pass explicit structured applicability metadata into the guard. The
guard should validate extracted label facts, not infer policy mode from
freeform explanations.

### 8. Frontend Result Normalization Is Too Permissive For A Backend-Owned Contract

Severity: **Medium**

The frontend accepts many possible result shapes through generic `unknown`
lookup helpers and then defaults missing fields to pass in row display helpers.

Evidence:

- `frontend/src/lib/resultNormalization.ts`
- `frontend/src/lib/objectLookup.ts`
- `frontend/src/lib/rowView.ts:10-15`
- `frontend/src/lib/rowView.ts:36-41`

This made sense while the API shape was still moving, but the backend now owns a
typed response schema. Continuing to accept loose aliases can hide backend
contract drift. The default-to-pass behavior is especially risky: if a field is
missing from a malformed response, the UI can show a green mini-check rather
than surfacing a schema problem.

Recommended fix:

Define one strict frontend API type matching `VerificationResult`. Normalize
only at the network boundary, and treat missing required fields as
`processing-error` or an explicit UI error. Do not default missing verification
fields to pass.

### 9. Large Frontend Files Are Accumulating Too Many Responsibilities

Severity: **Medium**

Several hand-written frontend files are large enough that future feature work
will likely add more ad-hoc state and inline UI logic:

- `frontend/src/components/BatchGridModal.tsx`: 843 lines
- `frontend/src/hooks/useLabelRows.ts`: 475 lines
- `frontend/src/App.tsx`: 455 lines
- `frontend/src/components/DetailModal.tsx`: 420 lines
- `frontend/src/styles/app.css`: 1309 lines

The largest concern is `BatchGridModal.tsx`: it owns row modeling, validation,
file object URL lifecycle, partial-submit confirmation, zoom lightbox, and a
large grid UI with extensive inline styles.

Recommended fix:

Split `BatchGridModal` into a row model hook plus focused components:

- `useBatchGridRows`
- `BatchGridTable`
- `BatchGridRow`
- `BatchPartialConfirmDialog`
- `ImageZoomLightbox`

Move repeated inline styles into CSS classes or small presentational components.
This would make the partial-submit bug easier to see and test.

### 10. Test Suite Has Root-Path Coupling

Severity: **Medium**

Running tests from the repository root passes. Running the backend test command
from `backend/` fails because tests reference sample images using
`frontend/public/...` relative to the current working directory.

Evidence:

- `backend/tests/test_batch_routes.py:84-88`
- `backend/tests/test_batch_routes.py:158-160`
- `backend/tests/test_verify_routes.py:74-78`

This is a brittle test seam. A developer naturally running `python -m pytest`
inside `backend/` gets false failures.

Recommended fix:

Resolve fixture image paths from `Path(__file__).resolve().parents[...]` or add a
central `REPO_ROOT` helper in `backend/tests/helpers.py`.

### 11. Tooling Gaps Allow Quality Drift

Severity: **Medium**

The backend has pytest but no configured formatter, linter, type checker, or
coverage threshold in `backend/pyproject.toml`. The frontend has TypeScript build
checking but no lint command and no committed frontend tests.

Evidence:

- `backend/pyproject.toml`
- `frontend/package.json`

This matters because the app has several string-heavy and state-heavy paths
where static checks would catch drift early. The frontend in particular has a
lot of UI state behavior but no component or browser tests for workflows like
partial batch submission, edit/reverify, and polling.

Recommended fix:

Add at least:

- backend: Ruff, mypy or pyright, pytest coverage gate for core services
- frontend: ESLint, a small Vitest suite for pure helpers, and Playwright tests
  for one single-label and one partial-batch workflow

### 12. Documentation And Runtime Behavior Are Starting To Diverge

Severity: **Low to Medium**

The design docs describe some intended behavior that is not fully true in the
current implementation. The clearest example is the partial batch path:
comments say unfinished rows remain as drafts, while the modal skips them.

Evidence:

- `docs/design.md`
- `frontend/src/hooks/useLabelRows.ts:241-245`
- `frontend/src/components/BatchGridModal.tsx:237-263`

Docs are useful only if they remain tied to runtime truth. Because this app is a
prototype being judged partly on design rationale, stale behavior claims are
more damaging than they would be in purely internal docs.

Recommended fix:

Add a short "current limitations" section to design docs and make sure any
workflow comments are covered by tests. If a design doc says partial rows remain
available, write a test for it.

## Positive Findings

- The app has a clean high-level boundary: frontend submits structured
  application values and images; backend owns provider access and validation.
- The model response is structured JSON rather than freeform prose, which makes
  field-level review and backend guardrails possible.
- The government-warning guard is materially better than trusting model pass/fail
  alone.
- Upload validation checks extension, content bytes, size, and magic bytes.
- Backend route and provider tests cover many important failure cases.
- Batch item failures are isolated at the verification-service level, so a model
  failure for one item returns `processing_error` instead of crashing normal item
  processing.

## Recommended Fix Order

1. Fix partial batch submission so unfinished rows are preserved or explicitly
   discarded.
2. Enforce filename-to-row matching in the batch API.
3. Decide whether `batch_concurrency` means item concurrency or provider-call
   concurrency, then make the runtime match the name.
4. Add strict frontend response typing and stop defaulting missing fields to
   pass.
5. Remove or consolidate the unused provider-level single-pass `verify()` paths.
6. Extract prompt policy/applicability from prompt string rendering.
7. Refactor `BatchGridModal.tsx` before adding more batch UI behavior.
8. Make tests path-independent and add frontend workflow tests.

## Residual Risk

The app is in reasonable shape for a prototype, but the current batch workflow
and model-provider orchestration should not be treated as production-ready. The
main architectural smell is that several "demo acceptable" shortcuts now sit on
critical user workflows: in-memory batch state, order-based row matching, and
large stateful frontend components. Those should be addressed before expanding
batch upload, spreadsheet import, or public hosted usage.
