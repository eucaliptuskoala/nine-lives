# Implementation Plan: Nine Lives Complete Implementation

## Overview

This implementation plan covers the complete Nine Lives game. The work is split into two independent tracks:

**Track A — Playable Game (current focus):** Architecture refactoring, authentication, backend battle engine, frontend wiring, UI polish, and memorial system. This track produces a fully playable game end-to-end using the existing mock/random stat generation. No ML required.

**Track B — Digitization Pipeline (pending research):** HuggingFace breed classification, OpenCV color extraction, Claude Haiku card generation, and Gemini 2.5 Flash avatar generation. Blocked until ML research is complete. Plugs into the existing `/api/digitize` endpoint once ready.

**Architecture principle:** The backend is the sole owner of combat logic and game state. The frontend is a rendering and input layer only.

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
    - Create policy: game_runs follow cat ownership (JOIN with cats)
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
  - [ ] 3.1 Set up Supabase auth client on the frontend
    - Update `hooks/useSupabase.ts` — initialize Supabase client from env vars (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`)
    - Implement `onAuthStateChange` listener to track session
    - Expose current `user` and `session` from the hook
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [ ] 3.2 Add auth guard for protected pages
    - Create an `AuthGuard` wrapper component (or HOC) that checks for a valid session
    - Wrap DigitizePage, BattlePage, and MemorialPage with the guard
    - Redirect unauthenticated users to a login page (or Supabase hosted auth UI)
    - Preserve the intended destination URL for post-login redirect
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [ ] 3.3 Thread auth token into all backend API calls
    - Ensure `POST /api/digitize`, `POST /api/battle/start`, and `POST /api/battle/action` include the Supabase JWT in the `Authorization: Bearer <token>` header
    - Extract token from the active session via `supabase.auth.getSession()`
    - _Requirements: 21.1, 21.2_

  - [ ] 3.4 Implement JWT verification on the backend
    - In `main.py`, add a dependency or middleware that extracts and verifies the Supabase JWT on all `/api/battle/*` routes
    - Use `supabase-py` to verify the token and extract `user_id`
    - Return 401 if token is missing or invalid
    - _Requirements: 21.1, 21.2_

- [ ] 4. Backend battle engine
  - [ ] 4.1 Create `services/combat.py` — pure combat calculation functions (no DB access)
    - `calculate_damage(atk: int, def_: int, is_defending: bool, shield: int) -> tuple[int, int]`
      - `raw = max(atk - def_*0.5, 1)`; if defending: `raw = floor(raw*0.5)`; return `(floor(raw - min(shield, raw)), shield - min(shield, raw))`
    - `regen_mana(current: int, max_mana: int) -> int` — `min(max_mana, current + floor(max_mana*0.1))`
    - `tick_cooldowns(cooldowns: dict[str, int]) -> dict[str, int]` — decrement each by 1, floor at 0
    - `apply_ability_effect(ability: dict, state: GameState) -> GameState`
      - DMG: apply full dmg to enemy without defence reduction
      - HEAL: `new_hp = min(max_hp, current_hp + ability.dmg)`
      - SHIELD: `new_shield = current_shield + ability.dmg`
    - _Requirements: 9, 10, 11, 12, 13, 14, 28_

  - [ ]* 4.2 Write property tests for `combat.py` (pytest + hypothesis)
    - **Property 8**: `calculate_damage` always returns damage ≥ 1
    - **Property 9**: HP after damage always in [0, max_hp]
    - **Property 10**: Defending reduces damage by exactly 50%
    - **Property 17**: `regen_mana` never exceeds max_mana; adds exactly floor(max*0.1)
    - **Property 18**: `tick_cooldowns` decrements by 1 and never goes below 0

  - [ ] 4.3 Create `services/enemy_gen.py` — server-side enemy generation (no DB access)
    - `compute_enemy_stats(round_num: int) -> dict` — exact formulas from Requirement 8.1–8.6
    - `generate_enemy(round_num: int) -> dict`
      - Call `compute_enemy_stats`; pick random name/breed from pools
      - Call `pick_abilities()` — shuffle pool, pick 1 special + 3 regular
      - Starting mana = `floor(max_mana * 0.6)`; special cooldown at max; regular cooldowns at 0
    - Define full `ABILITY_POOL` list mirroring the current `enemyGen.ts` (12 abilities)
    - _Requirements: 8.1–8.9_

  - [ ]* 4.4 Write property tests for `enemy_gen.py` (pytest + hypothesis)
    - **Property 6**: Stats match exact scaling formulas for rounds 1–20
    - **Property 7**: Every generated enemy has exactly 4 abilities with exactly 1 `is_special=True`

  - [ ] 4.5 Create `services/battle_engine.py` — orchestrates a full turn (no DB access, pure functions)
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

  - [ ] 4.6 Create `routers/battle.py` and update `models/schemas.py`
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

  - [ ] 4.7 Write unit tests for `routers/battle.py` (pytest, mock Supabase)
    - `POST /api/battle/start` creates correct initial state (HP=max, mana=max, round=1, special CD at max)
    - `POST /api/battle/start` is idempotent (returns existing state on second call)
    - `POST /api/battle/action` with attack: enemy HP decreases, state persisted, events non-empty
    - Returns 401 when Authorization header missing or invalid
    - Returns 403 when game_run belongs to different user
    - Returns 409 when game_run.status is COMPLETED
    - Ability with insufficient mana returns error without mutating state
    - Action when phase is not PLAYER_TURN returns error
    - _Requirements: 7, 9, 10, 11, 20.5, 21_

- [ ] 5. Frontend wiring — connect battle UI to Battle API
  - [ ] 5.1 Gut and replace `hooks/useGameState.ts`
    - Remove all combat math: delete imports of `combat.ts`, `enemyGen.ts`; remove `initRound`, `attack`, `defend`, `useAbility`, `resolveEnemyTurn`
    - Implement `startBattle(runId: string): Promise<void>` — `POST /api/battle/start` with auth token; set `gameState`, `revival`, `events`, `gameOver` from response
    - Implement `submitAction(action, abilityId?): Promise<void>` — `POST /api/battle/action`; set state from response
    - Expose: `{ gameState, isLoading, error, revival, gameOver, startBattle, submitAction }`
    - `isLoading=true` while request in-flight (prevents duplicate submissions)
    - `error` set on API failure; cleared on next action attempt
    - Zero combat calculations — purely reflects API response
    - _Requirements: 7, 9, 10, 11, 20, 26_

  - [ ] 5.2 Update `BattlePage.tsx` to use real data from the API
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

  - [ ] 5.3 Delete `frontend/src/utils/combat.ts` and `frontend/src/utils/enemyGen.ts`
    - Verify no remaining imports before deleting (should be none after 5.1 and 5.2)
    - Also remove `frontend/src/data/mockCat.ts` if no longer referenced
    - **Must be done AFTER 5.1 and 5.2 are verified working**
    - _Requirements: 9.7, 28.5_

  - [ ]* 5.4 Write frontend tests for BattlePage (Vitest)
    - `startBattle` called on mount with correct runId
    - Action buttons call `submitAction` with correct action string and abilityId
    - Buttons disabled while `isLoading=true`
    - Revival notification renders when `revival=true`
    - Navigation to `/memorial` when `gameOver=true`
    - Error message renders and buttons re-enable when `error` is set

- [ ] 6. Update DigitizePage to create a game run and launch a battle
  - [ ] 6.1 Wire up DigitizePage for mock-based flow (no ML yet)
    - Implement file selection with client-side validation (type + size display, but upload not yet wired to real pipeline)
    - On submit: create a `game_run` record (status DIGITIZING) via Supabase client
    - Call `POST /api/digitize` with file, game_run_id, user_id, auth token — still uses the existing random-stat mock implementation
    - On success: navigate to `/battle/:runId`
    - Display processing state and handle errors with retry
    - _Requirements: 1.1–1.4, 7.1, 26.1, 26.2, 27.1–27.4_

- [ ] 7. Memorial system
  - [ ] 7.1 Update MemorialPage to load and display fallen cats
    - Query all cats with status=MEMORIAL for current user (via Supabase, RLS-filtered)
    - Display: name, breed, class, avatar, stats, abilities, lore, death_date, wins, personal_note
    - Implement UI for adding/editing personal notes; validate ≤500 chars
    - Handle empty state
    - _Requirements: 22.1–22.5, 23.1–23.3_

  - [ ] 7.2 Implement `hooks/useMemorial.ts`
    - Load memorial cats from Supabase (status=MEMORIAL, own cats only)
    - `updateNote(catId, note)` — validate ≤500 chars, update DB
    - `loading` and `error` states
    - _Requirements: 22.1, 22.2, 23.1–23.3_

  - [ ]* 7.3 Write integration test for memorial
    - Load cats, add/edit notes, 500-char limit, empty state display

- [ ] 8. Error handling and recovery
  - [ ] 8.1 Add comprehensive error handling
    - React error boundaries on all pages
    - User-friendly error messages for all API failures
    - Timeout handling: 30s for digitize, 5s for battle actions
    - _Requirements: 26.1, 26.2, 26.3, 26.4_

  - [ ] 8.2 Implement Battle API error recovery on frontend
    - On `POST /api/battle/action` error: display message, re-enable buttons for retry
    - Handle 401 (redirect to login, preserve game_run_id in session storage)
    - Handle 409 (display "game already ended", offer navigation to Memorial)
    - _Requirements: 20.4, 26.3, 26.4_

- [ ] 9. UI polish and final integration
  - [ ] 9.1 Verify initial ability cooldown behavior end-to-end
    - Confirm `POST /api/battle/start` sets player special cooldowns to max (no first-turn ultimate)
    - Confirm new enemies mid-run also have special cooldown at max
    - Confirm regular ability cooldowns start at 0
    - _Requirements: 7.5, 8.9_

  - [ ] 9.2 Add missing UI features and polish
    - Loading states for all async operations
    - Animations for combat actions (framer-motion)
    - Revival notification UI (triggered by `revival` flag from API response)
    - Round completion celebration
    - Responsive design for mobile

  - [ ] 9.3 Implement performance optimizations
    - React.memo for CatCard and HealthBar components
    - Lazy load MemorialPage
    - _Requirements: 27.1, 27.2_

  - [ ]* 9.4 Write E2E tests for complete game flow
    - Full flow: digitize (mock) → battle → die 9 times → memorial
    - Page refresh mid-battle (state restoration via `POST /api/battle/start`)
    - All ability types (DMG, HEAL, SHIELD)
    - Round progression across multiple rounds
    - Memorial display with multiple cats

- [ ] 10. Checkpoint — Track A complete
  - Run all pytest unit and property tests
  - Run all frontend (Vitest) tests
  - Test with multiple users to verify RLS and Battle API auth enforcement
  - Test error scenarios (invalid tokens, completed game actions, network timeouts)
  - Verify the frontend NEVER writes directly to game_run.state
  - Ask the user if questions arise.

---
## Track B — Digitization Pipeline (pending ML research)
---

- [ ] 11. Implement backend digitization pipeline services
  - [ ] 11.1 Implement breed classifier service
    - `services/classifier.py` — `classify_breed(image_bytes: bytes) -> str`
    - HuggingFace Inference API, retry with exponential backoff (3 attempts), fallback "Domestic Shorthair"
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 11.2 Write unit tests for breed classifier
    - Test success, retry logic with mocked failures, fallback, invalid image bytes

  - [ ] 11.3 Implement color extractor service
    - `services/color_extractor.py` — `extract_colors(image_bytes: bytes, n_colors: int = 3) -> list[str]`
    - OpenCV k-means clustering, hex output (#RRGGBB), retry up to 3 times
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 11.4 Write property test for color extraction
    - **Property 2: Hex Color Format** — all extracted colors match #[0-9A-Fa-f]{6}

  - [ ] 11.5 Implement card generator service
    - `services/card_generator.py` — `generate_card(breed: str, colors: list[str]) -> dict`
    - Claude Haiku API, validate stats in bounds, exactly 4 abilities (1 special), retry logic
    - _Requirements: 4.1–4.10, 31.1, 31.2_

  - [ ]* 11.6 Write property tests for card generation
    - **Property 3: Card Generation Schema Completeness**
    - **Property 4: Generated Stats Within Bounds**

  - [ ] 11.7 Implement avatar generator service
    - `services/image_generator.py` — `generate_avatar(image_prompt: str) -> str`
    - Gemini 2.5 Flash, upload to Supabase storage, return public URL, 30s timeout
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 11.8 Write integration test for avatar generation
    - prompt → API call → upload → valid public URL returned

- [ ] 12. Wire real ML pipeline into `/api/digitize`
  - [ ] 12.1 Replace random stat generation with real ML pipeline
    - Update `routers/digitize.py` to call classifier → color extractor → card generator → avatar generator in sequence
    - Replace the current random stat/ability generation with outputs from the ML services
    - Keep the same response shape (`CatResponse`) so the frontend requires no changes
    - _Requirements: 1.1–1.4, 2, 3, 4, 5, 6_

  - [ ]* 12.2 Write property test for image file validation
    - **Property 1: Image File Validation**

  - [ ]* 12.3 Write integration test for complete digitization pipeline
    - Full flow: upload → classify → extract → generate → persist → verify DB records

- [ ] 13. Final checkpoint — Track B complete
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
- Task 5.3 (deleting `combat.ts` and `enemyGen.ts`) must be the last step in Task 5

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2"] },
    { "id": 2, "tasks": ["3.1", "3.2"] },
    { "id": 3, "tasks": ["3.3", "3.4"] },
    { "id": 4, "tasks": ["4.1", "4.3"] },
    { "id": 5, "tasks": ["4.2", "4.4", "4.5"] },
    { "id": 6, "tasks": ["4.6"] },
    { "id": 7, "tasks": ["4.7", "5.1"] },
    { "id": 8, "tasks": ["5.2"] },
    { "id": 9, "tasks": ["5.3", "5.4", "6.1"] },
    { "id": 10, "tasks": ["7.1", "7.2", "8.1", "8.2"] },
    { "id": 11, "tasks": ["7.3", "9.1", "9.2", "9.3"] },
    { "id": 12, "tasks": ["9.4", "10"] },
    { "id": 13, "tasks": ["11.1", "11.3", "11.5", "11.7"] },
    { "id": 14, "tasks": ["11.2", "11.4", "11.6", "11.8", "12.1"] },
    { "id": 15, "tasks": ["12.2", "12.3", "13"] }
  ]
}
```
