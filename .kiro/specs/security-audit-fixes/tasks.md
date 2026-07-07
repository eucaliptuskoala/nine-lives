# Implementation Plan: Security Audit Fixes

## Overview

This plan implements the four security-audit fixes in priority order, following the
exploratory bugfix methodology (explore → preserve → implement → validate). Each bug
group first surfaces counterexamples on the **unfixed** code (bug-condition tests),
then captures baseline behavior to preserve, then applies the fix, then re-runs both.

Work is grouped by bug to match the design's Fix Implementation:

- **BUG 1 (PRIMARY):** authenticate + owner-scope both digitize endpoints, remove the
  caller-supplied `user_id`, add task ownership, and add a per-user rate limiter;
  update the frontend to send the JWT and drop `user_id`.
- **BUG 2:** fence + length-cap free-text inputs in `build_prompt`, and validate/trim
  returned free-text before persistence.
- **BUG 3:** two-account cross-user integration tests (+ optional shared helper).
- **BUG 4:** config/docs note for `CORS_ORIGINS` and token-revocation accepted risk.

Tasks marked `*` are optional (exploratory / property / integration tests and the
optional refactor). The core auth/ownership unit tests are required — they verify the
security fix directly.

## Tasks

---
## BUG 1 — Authenticated, owner-scoped digitize (PRIMARY)
---

- [x]* 1. Write bug-condition exploration tests for the digitize endpoints (BEFORE the fix)
  - **Property 1: Bug Condition** - Digitize Auth & Ownership
  - **IMPORTANT**: Write these property-based tests BEFORE implementing the fix; do NOT fix code when they fail
  - **GOAL**: Surface counterexamples proving the endpoints are unauthenticated and trust caller-supplied identity
  - **Scoped PBT Approach**: scope the property to concrete failing cases (no token; valid token for user A with `user_id=B`; valid token for A with B's `game_run_id`; status poll of another user's `task_id`)
  - Mock the pipeline/thread (`services.digitize.digitize` / `threading.Thread`) so no billed work runs and record writes can be asserted absent
  - Assert the desired secure behavior from the design: 401 (no/invalid token), 403 (foreign `game_run_id`/`task_id`), owner derived from token, and NO `cat`/`ability`/`game_run`/storage/task writes
  - Run on UNFIXED code — **EXPECTED OUTCOME**: tests FAIL (confirms the bug exists)
  - Document counterexamples (e.g. "POST with no Authorization returns 202 and starts the pipeline"; "status poll returns another user's full CatResponse")
  - _Requirements: 1.1, 1.2, 1.3, 1.5, Design Property 1_

- [x]* 2. Write preservation property tests for owned/valid digitize flows (BEFORE the fix)
  - **Property 4: Preservation** - Non-Buggy Digitize Inputs Unchanged
  - **IMPORTANT**: Follow observation-first methodology — observe behavior on UNFIXED code, then assert it
  - Observe: owned happy-path POST returns `{task_id}` (202) and the status flow yields the same `CatResponse` shape (pipeline mocked)
  - Observe: unsupported content type and >10 MB uploads return 400 with the existing error messages, before any pipeline work
  - Write property-based tests capturing these observed patterns across the input domain (valid content types/sizes)
  - Run on UNFIXED code — **EXPECTED OUTCOME**: tests PASS (baseline to preserve)
  - _Requirements: 3.1, 3.2, Design Property 4_

- [x] 3. Fix BUG 1 — require auth, derive identity from token, verify ownership, rate-limit

  - [x] 3.1 Add `owner_id` to the in-process task record
    - In `backend/services/task_store.py`, add `owner_id: Optional[str] = None` to `DigitizeTask`
    - Update `create_task(owner_id: str)` to set it when the task is created
    - _Bug_Condition: status GET where `task(task_id).owner_id != verifiedUserId`_
    - _Expected_Behavior: task carries the verified owner so the status endpoint can enforce ownership_
    - _Requirements: 2.3, 2.4, Design Property 1_

  - [x] 3.2 Secure `digitize_cat` (POST) in `backend/routers/digitize.py`
    - Add the `CurrentUser` dependency (from `backend/auth.py`) so a missing/invalid token yields 401 before any work
    - Remove the `user_id: str = Form(...)` parameter; derive `user_id = user.user_id` from the verified token and pass it into `digitize(...)`
    - Load the `game_run` by `game_run_id` and verify ownership synchronously — 404 if missing, 403 if `game_run.user_id != user.user_id` (mirror `battle.py::_load_game_run`)
    - Perform auth, ownership, content-type, and size checks BEFORE `create_task()`/`thread.start()` so a rejected request writes no records and never starts the pipeline
    - Call `create_task(owner_id=user.user_id)`
    - _Bug_Condition: POST with missing/invalid token, or `user_id` form field present, or foreign `game_run_id`_
    - _Expected_Behavior: 401/403 with zero cat/ability/game_run/storage/task writes and no pipeline invocation; owner is always the token subject_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, Design Property 1_

  - [x] 3.3 Secure `get_digitize_status` (status) in `backend/routers/digitize.py`
    - Add the `CurrentUser` dependency so a missing/invalid token yields 401
    - After auth, return 403 when `task.owner_id != user.user_id` (closes the leak of any task's `CatResponse`)
    - Preserve the existing 404 for unknown `task_id` and the existing response shape for the owner
    - _Bug_Condition: status GET with missing/invalid token, or `task.owner_id != verifiedUserId`_
    - _Expected_Behavior: 401/403 with no result leaked; owner still receives status/result_
    - _Requirements: 2.1, 2.10, Design Property 1_

  - [x] 3.4 Add a pragmatic per-user in-process rate limiter
    - Implement a lightweight limiter (e.g. `dict[user_id] -> deque[timestamps]` guarded by a lock; drop timestamps older than 60s; raise 429 when count ≥ 5) as a FastAPI dependency keyed by `user.user_id`
    - Apply it to `digitize_cat` AFTER auth and BEFORE enqueue (so it is per-authenticated-user and rejects before billed work)
    - Add a code comment noting the limiter is per-process and should move to a shared store (e.g. Redis) if the API is horizontally scaled
    - _Bug_Condition: authenticated user exceeds target 5 req/min_
    - _Expected_Behavior: 429 without running the pipeline_
    - _Requirements: 1.4, 2.6, Design Property 1_

  - [x] 3.5 Attach the Supabase JWT in `frontend/src/api/digitize.ts`
    - Add a small local helper that reads the current token via `supabase.auth.getSession()` and returns `Authorization: Bearer <token>` headers, throwing `ApiError(401, ...)` when no session exists (mirroring `authFetch`)
    - Call it before the initial POST and AGAIN before EACH status poll (re-read the token so a mid-poll refresh is picked up), keeping the bespoke `AbortController`/timeout/poll control (do NOT route through `authFetch`)
    - Remove `form.append("user_id", ...)`
    - Remove `userId` from the `DigitizeParams` interface
    - _Bug_Condition: frontend sends no JWT and includes `user_id` in the body_
    - _Expected_Behavior: JWT sent on POST and every poll; no `user_id` in the form body_
    - _Requirements: 1.5, 2.3, 2.5, Design Property 1_

  - [x] 3.6 Update `DigitizePage.tsx` and its test to drop `userId`
    - Update `frontend/src/pages/DigitizePage.tsx` to stop passing `user.id` into `uploadCatPhoto`
    - Update `frontend/src/pages/DigitizePage.test.tsx` expectations so the `uploadCatPhoto` call args no longer include `userId`
    - _Requirements: 2.3, 2.5, Design Property 4_

  - [x] 3.7 Write required backend auth/ownership/rate-limit unit tests
    - POST: 401 without token; owner derived from token; `user_id` form field removed from the signature
    - POST: 403 on foreign `game_run_id` with NO records written and the pipeline never started (mock `digitize`/`Thread` to assert it is not started)
    - Status: 401 without token; 403 on foreign `task_id`; 200 for the owner
    - Rate limiter: 6th request within 60s for the same user → 429; a different user unaffected; window resets after 60s
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6, 2.10, Design Property 1_

  - [x] 3.8 Verify the bug-condition exploration tests now pass
    - **Property 1: Expected Behavior** - Digitize Auth & Ownership
    - **IMPORTANT**: Re-run the SAME tests from task 1 — do NOT write new tests
    - **EXPECTED OUTCOME**: tests PASS (confirms the bug is fixed)
    - _Requirements: Design Property 1_

  - [x] 3.9 Verify the preservation tests still pass
    - **Property 4: Preservation** - Non-Buggy Digitize Inputs Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - **EXPECTED OUTCOME**: tests PASS (confirms no regressions to owned/valid flows and 400 validations)
    - _Requirements: 3.1, 3.2, Design Property 4_

---
## BUG 2 — Prompt-injection hardening in generate_card.py
---

- [x]* 4. Write bug-condition exploration tests for prompt injection (BEFORE the fix)
  - **Property 2: Bug Condition** - Prompt Injection & Unvalidated Free-Text
  - **IMPORTANT**: Write BEFORE the fix; do NOT fix code when they fail
  - **GOAL**: Show adversarial/oversized free-text flows into the prompt unfenced and uncapped
  - Assert `build_prompt(...)` output contains the untrusted-data fence and that `cat_name`/`personality` are truncated to caps
  - Include an oversized case (e.g. 5,000-char `personality`) and an instruction-override `cat_name`
  - Run on UNFIXED code — **EXPECTED OUTCOME**: tests FAIL (no fence, no caps)
  - Document counterexamples (unfenced/uncapped prompt text)
  - _Requirements: 1.6, 1.8, Design Property 2_

- [x] 5. Fix BUG 2 — fence, cap, and validate free-text

  - [x] 5.1 Restructure `build_prompt` with an untrusted-data fence + length caps
    - In `backend/services/generate_card.py`, keep the system/game-designer instructions and JSON schema as trusted text; move `cat_name`, `personality`, and `breed` into a clearly delimited `<untrusted_user_data>` block that the instructions declare is data, never instructions
    - Length-cap before interpolation: `cat_name` ≤ 100, `personality` ≤ 500
    - _Bug_Condition: adversarial or oversized `cat_name`/`personality`_
    - _Expected_Behavior: user text always inside the fence and within caps_
    - _Requirements: 2.7, 2.8, Design Property 2_

  - [x] 5.2 Add a `sanitize_card` free-text validation step
    - Add a `sanitize_card` step invoked in `generate_card` after JSON parse and BEFORE the existing `validate_card` numeric checks
    - Length-cap and strip control characters from `name`, `lore`, `image_prompt`, and each ability `name`/`description`
    - Keep the existing `validate_card` numeric/structure checks unchanged
    - _Bug_Condition: returned free-text persisted without validation/trimming_
    - _Expected_Behavior: returned free-text length-capped + control-char stripped before persistence_
    - _Requirements: 1.7, 2.9, Design Property 2_

  - [x] 5.3 Write required unit tests for the fence, caps, and free-text validation
    - `build_prompt` output contains the untrusted-data fence; `cat_name`/`personality` truncated to caps
    - `sanitize_card` length-caps and strips control chars from returned free-text fields
    - Existing `validate_card` numeric/structure checks still reject out-of-spec cards (unchanged)
    - _Requirements: 2.7, 2.8, 2.9, 3.3, Design Property 2_

  - [x]* 5.4 Write property tests for the fencing invariant and preservation
    - **Property 2: Preservation** - Free-Text Fencing Invariant
    - For arbitrary `cat_name`/`personality` strings, user text always appears inside the fence and never outside it, and never exceeds the caps
    - Preservation: for generated benign in-cap inputs, card stat/structure decisions match current `validate_card` behavior
    - _Requirements: 3.3, 3.4, Design Property 2, Design Property 4_

  - [x] 5.5 Verify the bug-condition exploration tests now pass
    - **Property 2: Expected Behavior** - Prompt Injection & Unvalidated Free-Text
    - **IMPORTANT**: Re-run the SAME tests from task 4 — do NOT write new tests
    - **EXPECTED OUTCOME**: tests PASS (fence present, inputs capped)
    - _Requirements: Design Property 2_

---
## BUG 3 — Ownership backstop (regression-prevention)
---

- [x]* 6. Write two-account cross-user integration tests
  - **Property 3: Bug Condition** - Cross-User Access Rejected
  - With two authenticated users A and B, assert A cannot read/mutate B's records: memorial read (empty/403), note update (403), battle start/action (403), and digitize POST + status with B's `game_run_id`/`task_id` (403)
  - Assert B's own access still succeeds (200/empty as appropriate)
  - Optionally generalize as a property over generated `(actor, target)` pairs where `actor != target` → always 403 (or empty for list reads)
  - _Requirements: 1.9, 2.10, 3.5, 3.6, Design Property 3, Design Property 4_

- [ ]* 7. Extract a shared ownership helper and reuse it (optional refactor)
  - Extract the `game_run`/`cat` ownership check into a small shared helper (e.g. `backend/services/ownership.py` or a reused `_load_game_run`)
  - Reuse it in `digitize.py`, `battle.py`, and `data.py` so future handlers cannot silently omit the check
  - Framed as a refactor + tests, not a behavior change — the cross-user tests from task 6 must stay green
  - _Requirements: 2.11, 3.6, Design Property 3, Design Property 4_

---
## BUG 4 — Config guidance
---

- [x] 8. Document required `CORS_ORIGINS` production config and token-revocation risk
  - Add a note in `backend/.env.example` (comment near `CORS_ORIGINS`) that it MUST be set to the real deployed origin in production, keeping `allow_credentials=True` scoped to that origin
  - Add a matching note in `README.md` documenting the required deployment step and recording token revocation after password reset as an accepted risk (short-lived Supabase JWTs + live `auth.get_user` check)
  - Do NOT edit any `.env` file secret values
  - _Requirements: 1.10, 1.11, 2.12, 2.13, Design Property 5_

---
## Final Validation
---

- [x] 9. Checkpoint — ensure all tests pass
  - Run the backend suite (pytest) and the frontend suite (vitest --run); confirm the required auth/ownership/rate-limit and prompt-fencing unit tests pass, the exploration tests now pass, and preservation tests still pass with no regressions
  - Ask the user if questions arise

## Notes

- Tasks marked `*` are optional (exploratory, property, and integration tests, plus the
  optional ownership-helper refactor). The core auth/ownership/rate-limit unit tests
  (3.7) and prompt-fencing/validation unit tests (5.3) are required — they verify the
  security fix.
- BUG 1 is the must-fix and is implemented first. All auth and ownership checks run
  synchronously in the request handler BEFORE `thread.start()` so rejected requests
  never enqueue billed pipeline work.
- The in-process rate limiter is acceptable for the current single-process deployment;
  it is annotated to move to a shared store if the API is horizontally scaled.
- Config/docs changes (BUG 4) never touch `.env` secret values.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "2"] },
    { "id": 1, "tasks": ["3.1", "3.5", "3.6"] },
    { "id": 2, "tasks": ["3.2", "3.3", "3.4"] },
    { "id": 3, "tasks": ["3.7"] },
    { "id": 4, "tasks": ["3.8", "3.9"] },
    { "id": 5, "tasks": ["4"] },
    { "id": 6, "tasks": ["5.1", "5.2"] },
    { "id": 7, "tasks": ["5.3", "5.4"] },
    { "id": 8, "tasks": ["5.5"] },
    { "id": 9, "tasks": ["7"] },
    { "id": 10, "tasks": ["6"] },
    { "id": 11, "tasks": ["8"] },
    { "id": 12, "tasks": ["9"] }
  ]
}
```
