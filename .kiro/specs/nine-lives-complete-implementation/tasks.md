# Implementation Plan: Nine Lives Complete Implementation

## Overview

This implementation plan covers the complete Nine Lives game. The work is split into two independent tracks:

**Track A — Playable Game (current focus):** Architecture refactoring, authentication, backend battle engine, frontend wiring, UI polish, and memorial system. This track produces a fully playable game end-to-end using the existing mock/random stat generation. No ML required.

**Track B — Digitization Pipeline (pending research):** HuggingFace breed classification, OpenCV color extraction, Claude Haiku card generation, and Gemini 2.5 Flash avatar generation. Blocked until ML research is complete. Plugs into the existing `/api/digitize` endpoint once ready.

**Architecture principle:** The backend is the sole owner of all data access. Beyond owning all combat logic and game state, the backend mediates every database read and write. The frontend never reads from or writes to the database directly — it uses the Supabase client solely for authentication (login, session, JWT) and performs all data operations (game_run creation, memorial reads, note updates, battle state) through authenticated backend HTTP endpoints. The frontend is a rendering and input layer only.

## Tasks

- [x] 1. Set up Supabase database schema and RLS policies
  - [x] 1.1 Create database tables for cats, abilities, and game_runs
    - Create `cats` table with user_id, breed, name, class, stats (max_hp, dmg, defence, spd, max_mana), status, lives_remaining, wins, lore, source_image_url, avatar_url, death_date, personal_note, created_at
    - Create `abilities` table with cat_id, name, dmg, type, effect, cooldown, mana_cost, lore, is_special, description
    - Create `game_runs` table with user_id, cat_id, status, current_round, state (JSONB), created_at, completed_at
    - Set up foreign key relationships (abilities.cat_id → cats.id, game_runs.cat_id → cats.id)
    - Add indexes on user_id, cat_id, and status fields
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 20.1, 29_

  - [x] 1.2 Implement Row Level Security (RLS) policies
    - Enable RLS on cats, abilities, and game_runs tables
    - Create policy: users can only SELECT/INSERT/UPDATE their own cats (WHERE user_id = auth.uid())
    - Create policy: abilities follow cat ownership (JOIN with cats)
    - Create policy: game_runs scoped directly to the owner via `game_run.user_id = auth.uid()` (SELECT/INSERT/UPDATE/DELETE)
    - _Requirements: 24.1, 24.2, 24.3_

  - [x] 1.3 Set up Supabase storage bucket for cat images
    - Create storage bucket named 'cat-images'
    - Configure bucket to accept JPEG, PNG, WebP files
    - Set up RLS policies for storage bucket
    - Configure public URL access
    - _Requirements: 5.2, 5.3_

- [x] 2. Checkpoint — Verify database setup
  - Ensure all tables created, RLS working (test with multiple accounts), storage bucket accessible

---
## Track A — Playable Game
---

- [ ] 3. Authentication
  - [x] 3.1 Set up Supabase auth client on the frontend
    - Update `hooks/useSupabase.ts` — initialize Supabase client from env vars (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`)
    - Implement `onAuthStateChange` listener to track session
    - Expose current `user` and `session` from the hook
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [x] 3.2 Build the login/signup page (email + password)
    - Create a `LoginPage` component (`frontend/src/pages/LoginPage.tsx`) with an email + password sign-in form and a sign-up form (toggle between the two views, or render them as separate views)
    - Implement email/password auth via Supabase: sign up with `supabase.auth.signUp({ email, password })` and sign in with `supabase.auth.signInWithPassword({ email, password })`
    - Implement sign-out via `supabase.auth.signOut()`
    - Display auth errors to the user (invalid credentials, email already registered, weak password, etc.)
    - Add a `/login` route in `frontend/src/App.tsx`
    - On successful login, redirect to the originally intended destination (works together with the `AuthGuard` from task 3.3)
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [x] 3.3 Add auth guard for protected pages
    - Create an `AuthGuard` wrapper component (or HOC) that checks for a valid session
    - Wrap DigitizePage, BattlePage, and MemorialPage with the guard
    - Redirect unauthenticated users to the `/login` route (the custom email/password login page from task 3.2)
    - Preserve the intended destination URL for post-login redirect
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [x] 3.4 Add a shared authenticated-fetch mechanism and thread it into the endpoints that require auth
    - Create a single shared authenticated-fetch helper/wrapper (e.g. `frontend/src/api/authFetch.ts`) that pulls the JWT from the active session via `supabase.auth.getSession()` and sets the `Authorization: Bearer <token>` header on each request
    - Apply this mechanism to the Battle API calls that REQUIRE auth: `POST /api/battle/start` and `POST /api/battle/action`
    - Apply this mechanism to the new Data API calls that REQUIRE auth: `POST /api/game-runs`, `GET /api/cats/memorial`, and `PATCH /api/cats/{cat_id}/note`
    - `POST /api/digitize` does NOT require the token for now because it remains an open mock endpoint — digitize is intentionally excluded from required auth. The shared fetch helper MAY be reused for it later when the real ML pipeline is secured, but no token is required at this stage
    - _Requirements: 21.1, 21.2, 24.1_

  - [x] 3.5 Implement JWT verification on the backend
    - In `main.py`, add a dependency or middleware that extracts and verifies the Supabase JWT on all `/api/battle/*` routes
    - Use `supabase-py` to verify the token and extract `user_id`
    - Return 401 if token is missing or invalid
    - _Requirements: 21.1, 21.2_

  - [x] 3.6 Add sign-out control
    - Add a sign-out UI control (e.g. a button in a shared header/nav) shown on the authenticated pages — DigitizePage, BattlePage, and MemorialPage
    - On click, call `supabase.auth.signOut()`, clear the local session/user state, and redirect the user to `/login`
    - Ensure the `onAuthStateChange` listener from task 3.1 reacts to sign-out so the `AuthGuard` (task 3.3) immediately treats the user as unauthenticated
    - _Requirements: 25.4_

- [x] 4. Backend battle engine and Data Router
  - [x] 4.1 Create `services/combat.py` — pure combat calculation functions (no DB access)
    - `calculate_damage(atk: int, def_: int, is_defending: bool, shield: int) -> tuple[int, int]`
      - `raw = max(atk - def_*0.5, 1)`; if defending: `raw = floor(raw*0.5)`; return `(floor(raw - min(shield, raw)), shield - min(shield, raw))`
    - `regen_mana(current: int, max_mana: int) -> int` — `min(max_mana, current + floor(max_mana*0.1))`
    - `tick_cooldowns(cooldowns: dict[str, int]) -> dict[str, int]` — decrement each by 1, floor at 0
    - `apply_ability_effect(ability: dict, state: GameState) -> GameState`
      - DMG: apply full dmg to enemy without defence reduction
      - HEAL: `new_hp = min(max_hp, current_hp + ability.dmg)`
      - SHIELD: `new_shield = current_shield + ability.dmg`
    - _Requirements: 9, 10, 11, 12, 13, 14, 28_

  - [x]* 4.2 Write property tests for `combat.py` (pytest + hypothesis)
    - **Property 8**: `calculate_damage` always returns damage ≥ 1
    - **Property 9**: HP after damage always in [0, max_hp]
    - **Property 10**: Defending reduces damage by exactly 50%
    - **Property 17**: `regen_mana` never exceeds max_mana; adds exactly floor(max*0.1)
    - **Property 18**: `tick_cooldowns` decrements by 1 and never goes below 0

  - [x] 4.3 Create `services/enemy_gen.py` — server-side enemy generation (no DB access)
    - `compute_enemy_stats(round_num: int) -> dict` — exact formulas from Requirement 8.1–8.6
    - `generate_enemy(round_num: int) -> dict`
      - Call `compute_enemy_stats`; pick random name/breed from pools
      - Call `pick_abilities()` — shuffle pool, pick 1 special + 3 regular
      - Starting mana = `floor(max_mana * 0.6)`; special cooldown at max; regular cooldowns at 0
    - Define full `ABILITY_POOL` list mirroring the current `enemyGen.ts` (12 abilities)
    - _Requirements: 8.1–8.9_

  - [x]* 4.4 Write property tests for `enemy_gen.py` (pytest + hypothesis)
    - **Property 6**: Stats match exact scaling formulas for rounds 1–20
    - **Property 7**: Every generated enemy has exactly 4 abilities with exactly 1 `is_special=True`

  - [x] 4.5 Create `services/battle_engine.py` — orchestrates a full turn (no DB access, pure functions)
    - `resolve_player_action(state, action, ability_id, cat) -> tuple[GameState, list[str]]`
      - Validate phase is PLAYER_TURN; regen player mana; tick player cooldowns first
      - "attack": `calculate_damage(cat.dmg, enemy.def, False, 0)` → subtract from enemy HP
      - "defend": set `player_is_defending=True`
      - "ability": validate mana ≥ cost AND cooldown = 0; call `apply_ability_effect`; deduct mana; set cooldown
    - `resolve_enemy_turn(state) -> tuple[GameState, list[str]]`
      - Regen enemy mana; tick enemy cooldowns
      - Pick action: special ability (if cooldown=0 + mana) → random regular ability → basic attack
      - Apply damage/effect; return updated state + event log
    - `resolve_death_and_revival(state, cat) -> tuple[GameState, bool, bool]`
      - Returns `(new_state, game_over, revival)`
      - HP=0 + lives>0: decrement lives, restore HP/mana/shield to max, `revival=True`
      - HP=0 + lives=0: set `game_over=True`
    - `resolve_round_progression(state, cat) -> GameState`
      - enemy_hp=0: increment wins, increment current_round, `generate_enemy(new_round)`, set phase PLAYER_TURN, preserve player HP/mana/cooldowns
    - _Requirements: 15, 17, 18, 19_

  - [x] 4.6 Create `routers/battle.py` and update `models/schemas.py`
    - Add to `models/schemas.py`:
      - `BattleActionRequest(run_id, action: Literal["attack","defend","ability"], ability_id?)`
      - `BattleActionResponse(game_state, revival=False, game_over=False, events=[])`
    - Implement `POST /api/battle/start`:
      - Verify auth token → 401 if invalid; verify game_run ownership → 403 if wrong user
      - If `game_run.state` already set → return it (idempotent)
      - Load cat + abilities; build initial GameState (HP/mana from cat max, round=1, PLAYER_TURN, special cooldowns at max, shield=0)
      - Call `generate_enemy(1)`; persist state; return `BattleActionResponse`
    - Implement `POST /api/battle/action`:
      - Verify auth → 401; verify ownership → 403; verify not COMPLETED → 409
      - Load + validate GameState
      - Call: `resolve_player_action` → `resolve_round_progression` → `resolve_enemy_turn` (if round not over) → `resolve_death_and_revival`
      - Persist final state; update game_run.status=COMPLETED if game_over
      - Return `BattleActionResponse`
    - Register router in `main.py` with prefix `/api`
    - _Requirements: 7, 9, 10, 11, 20, 21, 29_

  - [x] 4.7 Write unit tests for `routers/battle.py` (pytest, mock Supabase)
    - `POST /api/battle/start` creates correct initial state (HP=max, mana=max, round=1, special CD at max)
    - `POST /api/battle/start` is idempotent (returns existing state on second call)
    - `POST /api/battle/action` with attack: enemy HP decreases, state persisted, events non-empty
    - Returns 401 when Authorization header missing or invalid
    - Returns 403 when game_run belongs to different user
    - Returns 409 when game_run.status is COMPLETED
    - Ability with insufficient mana returns error without mutating state
    - Action when phase is not PLAYER_TURN returns error
    - _Requirements: 7, 9, 10, 11, 20.5, 21_

  - [x] 4.8 Create `routers/data.py` and add data request/response models to `models/schemas.py`
    - Add to `models/schemas.py`:
      - `CreateGameRunResponse(run_id: str, status: GameStatus)` — status is always DIGITIZING on creation
      - `UpdateNoteRequest(note: str)` — max 500 chars, validated server-side
    - Implement `POST /api/game-runs`:
      - Reuse the auth dependency from task 3.5 to verify the Supabase JWT → 401 if missing/invalid
      - Insert a new `game_run` for the authenticated user with `status=DIGITIZING`, `cat_id=null`, `current_round=0`, `state=null`
      - Return the new `run_id` and status
    - Implement `GET /api/cats/memorial`:
      - Verify the Supabase JWT (reuse the auth dependency from task 3.5) → 401 if missing/invalid
      - Query `cat` rows WHERE `user_id = authenticated user` AND `status=MEMORIAL` (including their abilities), ordered by `death_date` descending
      - Return the list of cats
    - Implement `PATCH /api/cats/{cat_id}/note`:
      - Verify the Supabase JWT (reuse the auth dependency from task 3.5) → 401 if missing/invalid
      - Confirm the cat identified by `cat_id` belongs to the authenticated user → 403 if not owner
      - Validate `note` length ≤ 500 chars → 400 (with error message) if exceeded
      - Update the cat's `personal_note`; return the updated cat
    - Register the router in `main.py` with prefix `/api`
    - _Requirements: 1.3, 22.1, 23.1, 23.2, 23.3, 23.4, 24.1, 24.2, 24.3, 24.4_

  - [x]* 4.9 Write unit tests for `routers/data.py` (pytest, mock Supabase)
    - All three endpoints return 401 when the Authorization header is missing or invalid
    - `PATCH /api/cats/{cat_id}/note` returns 403 when the cat belongs to a different user
    - `PATCH /api/cats/{cat_id}/note` returns 400 when the note exceeds 500 chars
    - `GET /api/cats/memorial` returns only the authenticated user's MEMORIAL cats
    - `POST /api/game-runs` inserts a DIGITIZING game_run for the authenticated user and returns its run_id
    - _Requirements: 1.3, 22.1, 23.2, 23.3, 23.4, 24.1_

  - [x] 4.10 Add symmetric enemy shield mechanic (Enemy Shield, Option A)
    - Add `shield: int = 0` to the `Enemy` model in `models/schemas.py`
    - `services/enemy_gen.py`: initialize `shield=0` on generated enemies
    - `services/combat.py` / `services/battle_engine.py`: enemy SHIELD-type abilities add their value to `enemy.shield`
    - Route the player's basic attack through the enemy's shield first (already covered by `calculate_damage`), and route the player's DMG/TRUE_DMG ability damage through the enemy's shield as well — reuse `calculate_damage` with `def_=0` for ability damage so DEFENCE is ignored but shield still absorbs
    - Ensure `apply_ability_effect` (or the engine) routes DMG/TRUE_DMG ability damage through the target's shield for BOTH directions (player→enemy and enemy→player)
    - Keep the symmetric behavior on the player side (enemy DMG abilities already absorbed by `player_shield`)
    - _Requirements: 11.6, 11.8, 14.5, 14.6, 14.7, 14.8, 15.5, 16.2, 28.4_

  - [x]* 4.11 Write property/unit tests for enemy shield mechanic (pytest + hypothesis)
    - **Property 31: Enemy Shield Mechanics**
    - **Validates: Requirements 11.8, 14.5, 15.5, 16.2**
    - Enemy SHIELD-type ability adds its value to `enemy.shield`
    - Player basic attack is absorbed by `enemy.shield` before HP
    - Player DMG/TRUE_DMG ability damage is absorbed by `enemy.shield` before HP (DEFENCE still ignored)
  - [x] 5.1 Gut and replace `hooks/useGameState.ts`
    - Remove all combat math: delete imports of `combat.ts`, `enemyGen.ts`; remove `initRound`, `attack`, `defend`, `useAbility`, `resolveEnemyTurn`
    - Implement `startBattle(runId: string): Promise<void>` — `POST /api/battle/start` with auth token; set `gameState`, `revival`, `events`, `gameOver` from response
    - Implement `submitAction(action, abilityId?): Promise<void>` — `POST /api/battle/action`; set state from response
    - Expose: `{ gameState, isLoading, error, revival, gameOver, startBattle, submitAction }`
    - `isLoading=true` while request in-flight (prevents duplicate submissions)
    - `error` set on API failure; cleared on next action attempt
    - Zero combat calculations — purely reflects API response
    - _Requirements: 7, 9, 10, 11, 20, 26_

  - [x] 5.2 Update `BattlePage.tsx` to use real data from the API
    - Remove `MOCK_CAT` import and all references to `data/mockCat.ts`
    - Read `runId` from route params (`/battle/:runId`)
    - Call `startBattle(runId)` on mount via `useEffect`
    - Map all action buttons to `submitAction` calls: Attack → `submitAction("attack")`, Defend → `submitAction("defend")`, Ability → `submitAction("ability", ability.id)`
    - Disable all buttons while `isLoading=true`
    - Display `error` message when set; re-enable buttons
    - Show revival notification when `revival=true`
    - Navigate to `/memorial` when `gameOver=true`
    - Display cat name, stats, abilities from `gameState` (not from a local cat object)
    - _Requirements: 7.1, 7.9, 18.4, 26.3_

  - [x] 5.3 Delete `frontend/src/utils/combat.ts` and `frontend/src/utils/enemyGen.ts`
    - Verify no remaining imports before deleting (should be none after 5.1 and 5.2)
    - Also remove `frontend/src/data/mockCat.ts` if no longer referenced
    - **Must be done AFTER 5.1 and 5.2 are verified working**
    - _Requirements: 9.7, 28.5_

  - [x]* 5.4 Write frontend tests for BattlePage (Vitest)
    - `startBattle` called on mount with correct runId
    - Action buttons call `submitAction` with correct action string and abilityId
    - Buttons disabled while `isLoading=true`
    - Revival notification renders when `revival=true`
    - Navigation to `/memorial` when `gameOver=true`
    - Error message renders and buttons re-enable when `error` is set

- [x] 6. Update DigitizePage to create a game run and launch a battle
  - [x] 6.1 Backend: persist personality + accept digitization inputs
    - Add a DB migration to `supabase/migration.sql` (and note it MUST be applied to the Supabase database): `ALTER TABLE cat ADD COLUMN personality TEXT` with a `CHECK (personality IS NULL OR length(personality) <= 500)` constraint
    - Update `models/schemas.py`: add `personality: Optional[str] = None` to `CatResponse` (and to the `Cat`/creature representation as appropriate) so the field round-trips through serialization/deserialization
    - Update `routers/digitize.py`: the endpoint already takes `cat_name`; add an optional `personality: Optional[str] = Form(None)` form field; persist `personality` on the inserted `cat` record; include it in the returned `CatResponse`
    - Keep the mock stat generation unchanged — the mock still ignores `personality` for stat generation but stores it on the cat record so the real pipeline can use it later
    - _Requirements: 1.9, 4.11, 4.12, 6.2, 6.7, 30.1_

  - [x] 6.2 Frontend: DigitizePage inputs + flow
    - Update `frontend/src/api/digitize.ts` `uploadCatPhoto` to send `file`, `game_run_id`, `user_id`, `cat_name`, and optional `personality` as multipart form fields (keep it a plain `fetch` — digitize stays an open mock, no auth token required)
    - Implement `frontend/src/pages/DigitizePage.tsx`:
      - A required cat-name text input (non-empty, ≤100 chars)
      - A required photo file input with client-side validation via `utils/storage.ts` `validateImageFile` (type + ≤10MB) and a size display via `formatFileSize`
      - An optional personality description textarea (≤500 chars) with a live character counter
      - Enable submit only when a valid name and a valid photo are present
      - On submit: call `createGameRun()` from `api/data.ts` to get `run_id`, then `uploadCatPhoto(file, { gameRunId: run_id, userId: user.id, catName, personality })`, then navigate to `/battle/:runId`
      - Show processing/error states with retry (reuse the already-created `run_id` on retry rather than creating a new run each attempt)
      - Get `user` from `useAuth()`
    - The frontend must NOT insert into Supabase directly; the Supabase client is used only for the auth token/session
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 7.1, 26.1, 26.2, 27.1, 27.2, 27.3, 27.4_

  - [x]* 6.3 Write frontend tests for DigitizePage (Vitest + @testing-library/react)
    - Invalid file (wrong type or >10MB) → error shown and submit disabled
    - Missing/empty cat name → submit disabled
    - Happy path → `createGameRun` called, then `uploadCatPhoto` called with cat name, personality, and user id, then navigate to `/battle/:runId`
    - Digitize failure → error shown and retry reuses the existing `run_id` (does not create a new run)
    - _Requirements: 1.1, 1.4, 1.5, 1.7, 1.9, 26.1, 26.2, 27.1, 27.2, 27.3, 27.4_

- [x] 7. Memorial system
  - [x] 7.1 Update MemorialPage to load and display fallen cats
    - Load all fallen cats (status=MEMORIAL) for the current user via the backend `GET /api/cats/memorial` endpoint (with auth token) — **not** via a direct Supabase query
    - Display: name, breed, class, avatar, stats, abilities, lore, death_date, wins, personal_note
    - Implement UI for adding/editing personal notes; on save call the backend `PATCH /api/cats/{cat_id}/note` endpoint (with auth token); validate ≤500 chars client-side (authoritative validation is server-side)
    - Handle empty state
    - _Requirements: 22.1–22.5, 23.1–23.3, 24.1_

  - [x] 7.2 Implement `hooks/useMemorial.ts`
    - Load memorial cats via `GET /api/cats/memorial` (with auth token) — no direct Supabase reads
    - `updateNote(catId, note)` — client-side ≤500 char pre-check, then call `PATCH /api/cats/{cat_id}/note` (with auth token); authoritative validation is server-side — no direct Supabase writes
    - The Supabase client is used only for obtaining the auth token/session
    - `loading` and `error` states
    - _Requirements: 22.1, 22.2, 23.1–23.3, 24.1_

  - [x]* 7.3 Write integration test for memorial
    - Load cats, add/edit notes, 500-char limit, empty state display

- [x] 8. Error handling and recovery
  - [x] 8.1 Add comprehensive error handling
    - React error boundaries on all pages
    - User-friendly error messages for all API failures
    - Timeout handling: 30s for digitize, 5s for battle actions
    - _Requirements: 26.1, 26.2, 26.3, 26.4_

  - [x] 8.2 Implement Battle API error recovery on frontend
    - On `POST /api/battle/action` error: display message, re-enable buttons for retry
    - Handle 401 (redirect to login, preserve game_run_id in session storage)
    - Handle 409 (display "game already ended", offer navigation to Memorial)
    - _Requirements: 20.4, 26.3, 26.4_

- [x] 9. UI polish and final integration
  - [x] 9.1 Upgrade the frontend to Tailwind CSS v4
    - Install `tailwindcss@4` + `@tailwindcss/vite` via npm (`npm install -D tailwindcss@4 @tailwindcss/vite`); wire the `@tailwindcss/vite` plugin into `frontend/vite.config.ts`
    - Migrate the v3 `frontend/tailwind.config.js` content/theme (colors, fonts, extensions) to the Tailwind v4 CSS-first `@theme` block in the global stylesheet
    - Update the global CSS (`frontend/src/index.css`) to `@import "tailwindcss";` and define the theme (dark base) via `@theme`
    - Remove the now-unnecessary v3 PostCSS setup (`frontend/postcss.config.js`, `autoprefixer`) if no longer needed
    - Verify `npm run build` and `npx vitest run` stay green (the vitest `test.env` block in `frontend/vite.config.ts` MUST be preserved)
    - _Requirements: 27.1, 27.2_

  - [x] 9.2 Initialize shadcn/ui + 8bitcn base
    - Run the shadcn init for a Vite + Tailwind v4 project via `npx shadcn@latest init` (creates `components.json`, sets up the `@/*` path alias in `tsconfig`/vite `resolve.alias`, adds the `cn` util at `frontend/src/lib/utils.ts`, installs `class-variance-authority` + `tailwind-merge` + `clsx`, and the base theme CSS variables)
    - Add the "Press Start 2P" pixel font (Google Fonts import or self-hosted) and apply it as the app's display font in the `@theme`
    - Add the first 8bitcn component to validate the pipeline: `npx shadcn@latest add @8bitcn/button` (components land under `frontend/src/components/ui`)
    - Verify `npm run build` + `npx vitest run` stay green
    - _Requirements: 27.1, 27.2_

  - [x] 9.3 Migrate existing components to 8bitcn retro variants
    - Progressively restyle: the battle `ActionButtons` (use the 8bitcn Button), the auth/digitize/memorial inputs and textarea (8bitcn Input/Textarea), cards (8bitcn Card for CatCard/MemorialCatCard/BattleArena panels), and the HealthBar/ManaBar (8bitcn Progress or a retro bar)
    - Purely presentational — do NOT change data flow, props contracts that tests rely on, or accessible roles/names (tests query by role/label/text and must stay green)
    - Add any additional 8bitcn components needed (input, textarea, card, progress) via `npx shadcn@latest add @8bitcn/<component>`
    - Verify `npm run build` + `npx vitest run` after each swap; keep the suite green
    - _Requirements: 27.1, 27.2_

  - [x] 9.4 Verify initial ability cooldown behavior end-to-end
    - Confirm `POST /api/battle/start` sets player special cooldowns to max (no first-turn ultimate)
    - Confirm new enemies mid-run also have special cooldown at max
    - Confirm regular ability cooldowns start at 0
    - _Requirements: 7.5, 8.9_

  - [x] 9.5 Add missing UI features and polish
    - Loading states for all async operations
    - Animations for combat actions (framer-motion)
    - Revival notification UI (triggered by `revival` flag from API response)
    - Round completion celebration
    - Responsive design for mobile

  - [x] 9.6 Implement performance optimizations
    - React.memo for CatCard and HealthBar components
    - Lazy load MemorialPage
    - _Requirements: 27.1, 27.2_

  - [x]* 9.7 Write E2E tests for complete game flow
    - Full flow: digitize (mock) → battle → die 9 times → memorial
    - Page refresh mid-battle (state restoration via `POST /api/battle/start`)
    - All ability types (DMG, HEAL, SHIELD)
    - Round progression across multiple rounds
    - Memorial display with multiple cats

- [x] 10. Home & Overworld pages
  - [x] 10.1 Backend: add `GET /api/game-runs/active`
    - In `backend/routers/data.py`, add `GET /api/game-runs/active` (auth-required, reusing the existing auth dependency from task 3.5 → 401 if missing/invalid)
    - Return the authenticated user's most recent `game_run` with `status = IN_PROGRESS` whose associated cat has `status = ALIVE`, ordered by `created_at` descending, as `ActiveGameRunResponse { run_id, cat }` (serialize the cat via the existing `CatResponse`); enforce ownership by `user_id` (RLS as defense-in-depth)
    - Return `{ run_id: null, cat: null }` when the user has no such active run
    - Add `ActiveGameRunResponse` to `models/schemas.py` with `run_id: Optional[str] = None` and `cat: Optional[CatResponse] = None`
    - _Requirements: 24.6, 24.7_

  - [x]* 10.2 Write unit test for `GET /api/game-runs/active` (pytest, mock Supabase)
    - Returns `{ run_id, cat }` when an IN_PROGRESS run whose cat is ALIVE exists
    - Returns `{ run_id: null, cat: null }` when no active run exists
    - Returns 401 when the Authorization header is missing or invalid
    - _Requirements: 24.6, 24.7_

  - [x] 10.3 Frontend: routing change + HomePage
    - Update `frontend/src/App.tsx`: make `/` render the new public `HomePage` (OUTSIDE `AuthGuard`, still inside the `ErrorBoundary`); move DigitizePage to a protected `/digitize` route; add a protected `/overworld` route. Keep `/login` public and BattlePage/MemorialPage protected
    - Add `getActiveGameRun()` to `frontend/src/api/data.ts` (calls `GET /api/game-runs/active` with the auth token, returns `{ run_id, cat }`) plus a matching `ActiveGameRunResponse` type
    - Create `frontend/src/pages/HomePage.tsx` (public): render the title "Nine Lives"; logged-out → tagline + "Sign In" (→ `/login`); logged-in → intro + "New Game" (→ `/digitize`), "Memorial" (→ `/memorial`), and "Continue" (→ `/battle/:runId`) shown when `getActiveGameRun()` returns a non-null run. Use `useAuth()` and the existing 8bitcn components / retro theme
    - _Requirements: 25.1, 25.2, 32.1, 32.2, 32.3, 32.4, 32.5, 32.6_

  - [x] 10.4 Frontend: OverworldPage + post-victory routing + background assets
    - Create `frontend/src/assets/backgrounds/` with a placeholder file (e.g. a `README.md` note) since real background images are added manually later; reference a background via CSS `url()` with a solid-color fallback so a missing image does not break the build
    - Create `frontend/src/pages/OverworldPage.tsx` (protected): fullscreen background; nodes "Next Enemy" (→ `/battle/:runId`), "Memorial" (→ `/memorial`), and an optional disabled "Rest" placeholder. Resolve `run_id` via `getActiveGameRun()` on mount (refresh-safe). Style with 8bitcn components / retro theme
    - Update `frontend/src/pages/BattlePage.tsx`: when the player wins a round (enemy defeated / `current_round` advanced within the action response — reuse the existing round-increment detection from the round-completion polish), show a dismissible victory popup; on dismiss, navigate to `/overworld`. Do NOT change battle/combat logic or the game-over → `/memorial` behavior
    - _Requirements: 25.5, 33.1, 33.2, 33.3, 33.4, 33.5, 33.6, 33.7, 33.8_

  - [x]* 10.5 Write frontend tests for HomePage, OverworldPage, and BattlePage victory flow (Vitest)
    - HomePage: public render (title + logged-out "Sign In"); logged-in "New Game"/"Memorial"/"Continue" navigation ("Continue" shown only when an active run exists)
    - OverworldPage: resolves run id via `getActiveGameRun()`, "Next Enemy"/"Memorial" navigation, "Rest" rendered disabled
    - BattlePage: victory popup shown on round win and dismiss navigates to `/overworld`; game-over still navigates to `/memorial`
    - _Requirements: 32.1, 32.3, 32.4, 32.5, 33.2, 33.3, 33.4, 33.5, 33.6_

- [ ] 11. Checkpoint — Track A complete
  - Run all pytest unit and property tests
  - Run all frontend (Vitest) tests
  - Test with multiple users to verify RLS and Battle API auth enforcement
  - Test error scenarios (invalid tokens, completed game actions, network timeouts)
  - Verify the frontend NEVER writes directly to game_run.state
  - Ask the user if questions arise.

---
## Track B — Digitization Pipeline (pending ML research)
---

- [ ] 12. Implement backend digitization pipeline services
  - [ ] 12.1 Implement breed classifier service
    - `services/classifier.py` — `classify_breed(image_bytes: bytes) -> str`
    - HuggingFace Inference API, retry with exponential backoff (3 attempts), fallback "Domestic Shorthair"
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 12.2 Write unit tests for breed classifier
    - Test success, retry logic with mocked failures, fallback, invalid image bytes

  - [ ] 12.3 Implement color extractor service
    - `services/color_extractor.py` — `extract_colors(image_bytes: bytes, n_colors: int = 3) -> list[str]`
    - OpenCV k-means clustering, hex output (#RRGGBB), retry up to 3 times
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 12.4 Write property test for color extraction
    - **Property 2: Hex Color Format** — all extracted colors match #[0-9A-Fa-f]{6}

  - [ ] 12.5 Implement card generator service
    - `services/card_generator.py` — `generate_card(breed: str, colors: list[str], personality: Optional[str] = None) -> dict`
    - Claude Haiku API, validate stats in bounds, exactly 4 abilities (1 special), retry logic
    - When `personality` is provided, weave it into the Claude Haiku prompt so it influences the generated class, stats, abilities, and lore
    - _Requirements: 4.1–4.10, 4.11, 4.12, 31.1, 31.2_

  - [ ]* 12.6 Write property tests for card generation
    - **Property 3: Card Generation Schema Completeness**
    - **Property 4: Generated Stats Within Bounds**

  - [ ] 12.7 Implement avatar generator service
    - `services/image_generator.py` — `generate_avatar(image_prompt: str) -> str`
    - Wrap the per-cat `image_prompt` with the fixed positive/negative retro pixel-art style blocks from `docs/retro-avatar-prompt.md` (the single source of truth for avatar style) before calling the image model; keep the style block byte-for-byte identical across cats so every avatar is cohesive with the 8-bit UI. For prompt-only models (Gemini has no negative field) append the negatives as an "Avoid:" clause per the doc
    - Gemini 2.5 Flash, upload to Supabase storage, return public URL, 30s timeout
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 12.8 Write integration test for avatar generation
    - prompt → API call → upload → valid public URL returned

- [ ] 13. Wire real ML pipeline into `/api/digitize`
  - [ ] 13.1 Replace random stat generation with real ML pipeline
    - Update `routers/digitize.py` to call classifier → color extractor → card generator → avatar generator in sequence
    - Replace the current random stat/ability generation with outputs from the ML services
    - Pass the `personality` from the digitize request through to `generate_card` so it influences the generated card
    - The avatar step applies the canonical retro pixel-art style from `docs/retro-avatar-prompt.md` (wired in Task 12.7's `generate_avatar`)
    - Keep the same response shape (`CatResponse`) so the frontend requires no changes
    - _Requirements: 1.1–1.4, 2, 3, 4, 4.11, 5, 6_

  - [ ]* 13.2 Write property test for image file validation
    - **Property 1: Image File Validation**

  - [ ]* 13.3 Write integration test for complete digitization pipeline
    - Full flow: upload → classify → extract → generate → persist → verify DB records

- [ ] 14. Final checkpoint — Track B complete
  - All ML services working independently
  - `/api/digitize` orchestrates full pipeline correctly
  - Test with multiple real cat images
  - Verify data persisted to database correctly
  - Ask the user if questions arise.

## Notes

- Tasks marked `*` are optional and can be skipped for faster MVP
- TypeScript frontend, Python (FastAPI) backend
- **Track A is fully independent of Track B** — the game is playable end-to-end using the existing random stat mock in `/api/digitize` while ML research continues
- The backend is the sole owner of combat logic and game state; the frontend never computes damage, generates enemies, or writes to `game_run.state` directly
- The frontend uses the Supabase client **only for authentication** (obtaining the JWT/session); all data access — game_run creation, memorial reads, and note updates — goes through the authenticated backend Data Router (`routers/data.py`), never via direct Supabase reads/writes
- Task 5.3 (deleting `combat.ts` and `enemyGen.ts`) must be the last step in Task 5

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2"] },
    { "id": 2, "tasks": ["3.1"] },
    { "id": 3, "tasks": ["3.2", "3.4", "3.5"] },
    { "id": 4, "tasks": ["3.3"] },
    { "id": 5, "tasks": ["3.6", "4.1", "4.3"] },
    { "id": 6, "tasks": ["4.2", "4.4", "4.5"] },
    { "id": 7, "tasks": ["4.6"] },
    { "id": 8, "tasks": ["4.7", "4.8", "5.1"] },
    { "id": 9, "tasks": ["4.9", "4.10", "5.2"] },
    { "id": 10, "tasks": ["4.11", "5.3", "5.4", "6.1"] },
    { "id": 11, "tasks": ["6.2", "7.1", "7.2", "8.1", "8.2"] },
    { "id": 12, "tasks": ["6.3", "7.3"] },
    { "id": 13, "tasks": ["9.1"] },
    { "id": 14, "tasks": ["9.2"] },
    { "id": 15, "tasks": ["9.3"] },
    { "id": 16, "tasks": ["9.4", "9.5", "9.6"] },
    { "id": 17, "tasks": ["9.7", "10.1"] },
    { "id": 18, "tasks": ["10.2", "10.3"] },
    { "id": 19, "tasks": ["10.4"] },
    { "id": 20, "tasks": ["10.5"] },
    { "id": 21, "tasks": ["11"] },
    { "id": 22, "tasks": ["12.1", "12.3", "12.5", "12.7"] },
    { "id": 23, "tasks": ["12.2", "12.4", "12.6", "12.8", "13.1"] },
    { "id": 24, "tasks": ["13.2", "13.3", "14"] }
  ]
}
```
