# Nine Lives — Architecture v2

> Based on discussion (June 24, 2026) — updated June 30, 2026
> Hackathon: #HackTheKitty by coding.kitty

## Concept

Web app where user uploads a cat photo → ML detects breed → LLM generates a fighting card → turn-based roguelike combat → when all 9 lives are lost, cat goes to Memorial.

**Architecture principle:** The backend is the authoritative game engine. All combat logic, enemy generation, state mutations, and persistence happen on the backend. The frontend is a rendering and input layer — it submits player actions via the Battle API and renders the `GameState` returned in the response.

## ERD

```
auth.users 1──* cat 1──* game_run
```

### auth.users (Supabase Auth built-in)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | from auth.users |
| email | text | |
| created_at | timestamptz | |

### cat

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK | → auth.users.id |
| name | text | |
| breed | text | |
| class | text | STRENGTH / AGILITY / INTELLIGENCE |
| max_hp | int | range 30–200 |
| dmg | int | range 5–50 |
| def | int | range 3–40 |
| spd | int | range 5–50 |
| max_mana | int | range 50–200 |
| lore | text | |
| avatar_url | text | Gemini generated |
| source_image_url | text | original user upload |
| status | text | ALIVE / MEMORIAL |
| wins | int | rounds survived across all runs |
| lives_remaining | int | starts at 9 |
| death_date | timestamptz | nullable |
| personal_note | text | nullable, set in memorial |
| created_at | timestamptz | |

### ability

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| creature_id | UUID FK | → cat.id |
| name | text | |
| dmg | int | |
| type | text | DMG / HEAL / SHIELD / etc. |
| effect | text | nullable |
| cooldown | int | range 0–5 |
| mana_cost | int | range 0–100 |
| lore | text | |
| is_special | bool | exactly 1 per cat |
| description | text | |

### game_run

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK | → auth.users.id |
| cat_id | UUID FK | → cat.id, nullable until digitize done |
| status | text | DIGITIZING / IN_PROGRESS / COMPLETED |
| current_round | int | |
| state | jsonb | full mid-run battle state, written by backend only |
| created_at | timestamptz | |
| completed_at | timestamptz | nullable |

### game_run.state (JSONB structure)

```json
{
  "player_hp": 42,
  "player_max_hp": 50,
  "player_mana": 80,
  "player_max_mana": 100,
  "player_is_defending": false,
  "player_shield": 0,
  "player_ability_cooldowns": { "<ability_id>": 0 },
  "phase": "PLAYER_TURN",
  "current_round": 3,
  "enemy": {
    "name": "Shadow",
    "breed": "Black Shorthair",
    "hp": 18,
    "max_hp": 30,
    "atk": 12,
    "def": 8,
    "spd": 14,
    "mana": 60,
    "max_mana": 100,
    "ability_cooldowns": {},
    "abilities": [],
    "avatar_url": ""
  }
}
```

## Relationship Rules

- Each cat belongs to one user
- A cat can have multiple game runs
- When `lives_remaining` hits 0 → cat goes to memorial (no more runs)
- `game_run.cat_id` is nullable until digitization completes
- `game_run.state` stores full mid-run battle state for persistence

## Domain Flow

1. User signs in (Supabase Auth)
2. Creates a new game_run (status: `DIGITIZING`)
3. Uploads cat photo → `POST /api/digitize` (FastAPI)
   - Classify breed via HuggingFace
   - OpenCV k-means extracts dominant fur colors
   - Claude Haiku generates name, stats, abilities, lore
   - Gemini 2.5 Flash generates avatar
   - Cat row created, linked to run
4. Battle begins — frontend calls `POST /api/battle/start`
   - Backend builds initial GameState, generates first enemy, persists to DB
5. Turn-based combat loop — frontend submits actions via `POST /api/battle/action`
   - Backend resolves the full turn (player action + enemy response), persists state, returns updated GameState
6. HP hits 0 → lose 1 life — backend handles revival (restores HP/mana/shield), returns updated state
7. Lives hit 0 → run over — backend sets `cat.status = MEMORIAL`, `game_run.status = COMPLETED`, returns `game_over: true`
8. Memorial page: all user's cats where `status = MEMORIAL`

## Combat Actions

| Action | Effect |
|---|---|
| Attack | damage = max(atk − def × 0.5, 1), resolved server-side |
| Defend | incoming damage halved for one turn, resolved server-side |
| Ability N | varies by AbilityType (DMG/HEAL/SHIELD/etc.), resolved server-side |

## Enemy Generation

Procedural only — no LLM per encounter. Generated server-side by `services/enemy_gen.py`. Scaled by round:

```python
multiplier = 1 + (round - 1) * 0.3  # +30% per round
hp  = floor((20 + round * 5) * multiplier)
atk = floor((8  + round * 2) * multiplier)
def = floor((6  + round * 1.5) * multiplier)
spd = floor((7  + round * 2) * multiplier)
max_mana = 80 + round * 5
```

Enemy names, breeds, abilities — random from fixed server-side lists. 4 abilities per enemy (3 regular + 1 special). Special ability cooldown pre-set to max on generation. Starting mana = 60% of max.

Enemy avatars: CSS/SVG procedural or pre-made silhouettes.

## Battle API

Two endpoints handle the entire game loop:

```
POST /api/battle/start   → verify auth, build initial GameState, persist, return state
POST /api/battle/action  → verify auth, resolve full turn (player + enemy), persist, return state
```

Both require a valid Supabase JWT in the `Authorization` header. The backend verifies ownership of the game_run before processing. Returns 401 (invalid token), 403 (wrong user), or 409 (game already completed) as appropriate.

The response includes `game_state`, `revival` (bool), `game_over` (bool), and `events` (turn log strings).

## Mid-Run Persistence

- The backend is the sole writer of `game_run.state`
- After every `POST /api/battle/action`: backend resolves the full turn, persists the updated state, then returns it
- On page load (or refresh): frontend calls `POST /api/battle/start` to retrieve the persisted state — no direct Supabase query from the frontend for game state
- The frontend has no write access to `game_run.state`

## Project Structure

```
nine-lives/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── DigitizePage.tsx
│   │   │   ├── BattlePage.tsx
│   │   │   └── MemorialPage.tsx
│   │   ├── components/
│   │   │   ├── CatCard.tsx
│   │   │   ├── BattleArena.tsx
│   │   │   ├── ActionButtons.tsx
│   │   │   ├── HealthBar.tsx
│   │   │   ├── LivesDisplay.tsx
│   │   │   └── FarewellScreen.tsx
│   │   ├── hooks/
│   │   │   ├── useGameState.ts   # thin API wrapper — no combat math
│   │   │   ├── useMemorial.ts
│   │   │   └── useSupabase.ts
│   │   ├── api/
│   │   │   └── digitize.ts
│   │   └── types/
│   │       └── game.ts
│   ├── index.html
│   └── vite.config.ts
├── backend/
│   ├── main.py
│   ├── routers/
│   │   ├── digitize.py
│   │   └── battle.py             # POST /api/battle/start + /action
│   ├── services/
│   │   ├── classifier.py         # HuggingFace breed detection
│   │   ├── color_extractor.py    # OpenCV k-means
│   │   ├── card_generator.py     # Claude Haiku
│   │   ├── image_generator.py    # Gemini 2.5 Flash
│   │   ├── combat.py             # pure combat calculations
│   │   ├── enemy_gen.py          # procedural enemy generation
│   │   └── battle_engine.py      # turn orchestration
│   └── models/
│       └── schemas.py
└── supabase/
    └── migration.sql
```

## Technical Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | Python FastAPI (digitize pipeline + authoritative game loop) |
| Database | Supabase (Postgres + Auth) |
| ML — breed classification | HuggingFace Inference API |
| Color extraction | OpenCV k-means |
| LLM — card generation | Claude Haiku API |
| Image generation | Gemini 2.5 Flash |
| Deployment | Vercel (frontend) + Render (backend) |

## RLS Policies

- `cat`: user can CRUD own cats (`WHERE user_id = auth.uid()`)
- `ability`: follows cat ownership (JOIN with cats)
- `game_run`: accessible via cat's user_id (subquery or join)
- `game_run.state`: no direct frontend write; all mutations go through the Battle API
