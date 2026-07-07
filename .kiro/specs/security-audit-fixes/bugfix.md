# Bugfix Requirements Document

## Introduction

This bugfix addresses findings from the completed Aikido security audit
(`docs/aikido_security_recon_report_v1.md`), verified against the current code.
Four items are in scope, in priority order:

- **BUG 1 (PRIMARY — Critical, actively exploitable):** the digitize endpoint
  (`POST /api/digitize`) has no authentication and derives the acting user from
  a caller-supplied `user_id` form field. Any anonymous caller can create records
  under any account and trigger the (now real) billed ML pipeline. **This is the
  must-fix.**
- **BUG 2 (High likelihood / Medium impact):** free-text digitize inputs
  (`cat_name`, `personality`) are interpolated directly into the Gemini prompt
  with no structural separation, and returned free-text fields are persisted
  without validation.
- **BUG 3 (Medium / hardening):** all queries use the Supabase service-role key
  (RLS bypassed), so per-handler ownership checks are the *only* access control.
  No active cross-user hole is known; the risk is the absence of a backstop.
- **BUG 4 (Low / config):** CORS origin and token-lifetime notes that are
  deployment/config concerns rather than code-logic defects.

The audit's scope was widened by Task 13, which wired the real ML pipeline
(Gemini + FLUX/HuggingFace + Supabase storage writes) into the digitize flow, so
each unauthenticated call now incurs real third-party cost. Fixing BUG 1
deliberately **reverses the earlier "digitize stays an open mock, no auth"
decision (Task 3.4)**, which was acceptable only while the pipeline was a mock.

The bug condition `C(X)` for each item, the expected secure behavior, and the
concrete verification steps are captured below. `F` denotes the current
(vulnerable) behavior and `F'` the behavior after the fix.

## Bug Analysis

### Current Behavior (Defect)

**BUG 1 — Unauthenticated digitize with caller-supplied identity.**
Bug condition `C(X)`: a `POST /api/digitize` request either carries no valid
Supabase JWT, or carries a valid JWT but supplies a `user_id`/`game_run_id`
belonging to another user. `backend/routers/digitize.py::digitize_cat` has no
auth dependency and reads `user_id` and `game_run_id` from `Form(...)`.

1.1 WHEN `POST /api/digitize` is called with no `Authorization` header THEN the system accepts the request, runs the full ML pipeline (Gemini + FLUX/HuggingFace), uploads to Supabase storage, and persists a `cat` row, its abilities, and a `game_run` update.
1.2 WHEN the request supplies a `user_id` form field THEN the system uses that caller-supplied value as the owner of the created `cat` row instead of a verified identity.
1.3 WHEN the request supplies a `game_run_id` that belongs to another user THEN the system updates that foreign `game_run` to `IN_PROGRESS` and links the new cat to it, with no ownership check.
1.4 WHEN an unauthenticated or spoofed request is made repeatedly THEN the system incurs billed Gemini and FLUX/HuggingFace calls and storage writes on every call, with no per-user rate limiting.
1.5 WHEN the frontend `frontend/src/api/digitize.ts::uploadCatPhoto` uploads a photo THEN it calls `/api/digitize` with a plain `fetch` (no JWT) and includes `user_id` in the form body.

**BUG 2 — Prompt injection via free-text digitize inputs.**
Bug condition `C(X)`: `cat_name` or `personality` contains instruction-override
or otherwise adversarial text. `backend/services/generate_card.py::build_prompt`
interpolates these fields directly into the Gemini prompt.

1.6 WHEN `cat_name` or `personality` contains instruction-override text THEN the system passes it into the Gemini prompt with no structural separation from the system instructions, allowing the model's behavior to be steered.
1.7 WHEN the model returns free-text fields (`name`, `lore`, `image_prompt`, and each ability `name`/`description`) THEN the system persists them without validation or trimming (`validate_card` bounds numeric stats and enforces ability count/type/effect/class only).
1.8 WHEN `cat_name` or `personality` is arbitrarily long THEN the system sends it to Gemini uncapped, wasting tokens and enabling larger injection payloads.

**BUG 3 — Application-layer-only ownership with no RLS backstop.**
Bug condition `C(X)`: a request targets user-scoped records through a handler
that omits or misconstructs its ownership filter. All queries use the
service-role key, which bypasses RLS entirely.

1.9 WHEN a handler that touches user-scoped records is missing an ownership filter THEN the system would return or mutate another user's data, with no database-level control to catch the gap. (No such handler is known today; `data.py` and `battle.py::_load_game_run` currently enforce ownership. This clause documents the latent architectural risk.)

**BUG 4 — CORS and token-lifetime configuration notes.**
Bug condition `C(X)`: the backend is deployed to production without
`CORS_ORIGINS` set to the real origin.

1.10 WHEN `CORS_ORIGINS` is unset in production THEN `backend/main.py` defaults `allow_origins` to `http://localhost:5173` with `allow_credentials=True`, which is incorrect for a deployed origin.
1.11 WHEN a user resets their password or signs out THEN previously issued Supabase JWTs remain valid until natural expiry (accepted risk, largely inherent to short-lived Supabase JWTs; `auth.get_user` is already a live check).

### Expected Behavior (Correct)

**BUG 1 — Authenticated digitize, identity from token only.**
Property (fix checking): `FOR ALL X WHERE C(X)` (missing/invalid token, or
foreign `user_id`/`game_run_id`) the fixed endpoint `F'(X)` rejects the request
(401 or 403) and creates **no** database or storage records.

2.1 WHEN `POST /api/digitize` is called THEN the system SHALL require a valid Supabase JWT by reusing the existing `get_current_user` / `CurrentUser` dependency from `backend/auth.py`.
2.2 WHEN the request has no valid `Authorization` token THEN the system SHALL return 401 and SHALL create no `cat`, `ability`, `game_run`, or storage records and SHALL NOT invoke the Gemini or FLUX/HuggingFace pipeline.
2.3 WHEN the request is authenticated THEN the system SHALL derive the acting `user_id` exclusively from the verified token, and the `user_id` form field SHALL be removed from the endpoint.
2.4 WHEN the supplied `game_run_id` does not belong to the authenticated user THEN the system SHALL return 403 and SHALL create no records.
2.5 WHEN the frontend `uploadCatPhoto` uploads a photo THEN it SHALL send the JWT via the shared `authFetch` helper (`frontend/src/api/authFetch.ts`) and SHALL stop sending `user_id` in the form body.
2.6 WHEN an authenticated user exceeds the request rate (target: 5 requests per minute per user) THEN the system SHALL reject further digitize requests (429) without running the pipeline.

**BUG 2 — Isolate and validate free-text.**
Property (fix checking): `FOR ALL X WHERE C(X)` (adversarial `cat_name` /
`personality`) the fixed prompt keeps user text fenced as untrusted data, and
all stored free-text is validated/trimmed.

2.7 WHEN user-supplied text is added to the Gemini prompt THEN the system SHALL structurally isolate it from the system instructions, clearly fenced as untrusted data the model must treat as data and never as instructions.
2.8 WHEN `cat_name` or `personality` is received THEN the system SHALL length-cap each field before sending it to Gemini.
2.9 WHEN Gemini returns free-text fields (`name`, `lore`, `image_prompt`, ability `name`/`description`) THEN the system SHALL validate and trim them before persistence.

Note on impact: React escapes output by default and cats are user-scoped, so
this is **not** confirmed stored cross-user XSS. The realistic risk is prompt
steering, junk/inappropriate content, and token waste.

**BUG 3 — Add a mandatory, tested ownership layer.**
Property (fix checking, regression-prevention framing): `FOR ALL X` where an
authenticated user targets another user's records, every handler SHALL reject
with 403 (or return empty), and this SHALL be covered by automated tests.

2.10 WHEN a signed-in user requests memorial reads, note updates, battle start/action, or digitize using IDs belonging to a different user THEN the system SHALL return 403 (or an empty result for list reads), verified by two-account cross-user integration tests.
2.11 WHEN adding the ownership layer THEN the fix MAY centralize the ownership check into a shared, audited helper so future handlers cannot silently omit it.

**BUG 4 — Config guidance (low priority).**

2.12 WHEN deploying to production THEN `CORS_ORIGINS` SHALL be set to the real deployed origin (documented as a required deployment step), keeping `allow_credentials=True` scoped to that origin.
2.13 WHEN considering token revocation after password reset THEN the system MAY document it as an accepted risk / optional item, given short-lived Supabase JWTs and the existing live `auth.get_user` check.

### Unchanged Behavior (Regression Prevention)

Property (preservation checking): `FOR ALL X WHERE NOT C(X)` the fixed behavior
`F'(X)` equals the original behavior `F(X)`.

3.1 WHEN an authenticated user submits a valid digitize request with their own `game_run_id` and a supported image THEN the system SHALL CONTINUE TO run the full pipeline and return the same `CatResponse` shape (via the existing task/status polling flow) as before.
3.2 WHEN a digitize upload has an unsupported content type or exceeds the 10 MB limit THEN the system SHALL CONTINUE TO return 400 with the existing error messages.
3.3 WHEN Gemini returns numeric stats, ability counts, types, effects, or class THEN the system SHALL CONTINUE TO enforce the existing `validate_card` bounds and reject out-of-spec cards.
3.4 WHEN a benign `cat_name` or `personality` (within the length cap) is submitted THEN the system SHALL CONTINUE TO generate a card whose stats and structure match current behavior.
3.5 WHEN an authenticated user accesses their own memorial cats, notes, game runs, and battles THEN the system SHALL CONTINUE TO return and mutate their own records exactly as today.
3.6 WHEN the existing `battle.py` and `data.py` ownership checks run for owned records THEN the system SHALL CONTINUE TO succeed (200) without behavioral change.
3.7 WHEN the app runs locally with `CORS_ORIGINS` unset THEN the system SHALL CONTINUE TO allow the `http://localhost:5173` dev origin.
