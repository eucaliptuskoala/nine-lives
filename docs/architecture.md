# Nine Lives — Architecture v1

> Based on discussion (June 24, 2026)
> Hackathon: #HackTheKitty by coding.kitty

## Concept

Web app where user uploads a cat photo → ML detects breed → LLM generates a fighting card → turn-based roguelike combat → when all 9 lives are lost, cat goes to Memorial.

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
| base_hp | int | |
| base_atk | int | |
| base_def | int | |
| base_spd | int | |
| special_ability | text | |
| lore | text | |
| avatar_url | text | DALL-E generated |
| source_image_url | text | original user upload |
| status | text | 'alive' or 'memorial' |
| wins | int | rounds survived across all runs |
| lives_remaining | int | starts at 9 |
| death_date | timestamptz | nullable |
| personal_note | text | nullable |
| created_at | timestamptz | |

### game_run

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| cat_id | UUID FK | → cat.id |
| status | text | 'digitizing', 'in_progress', 'completed' |
| current_round | int | |
p| created_at | timestamptz | |
| completed_at | timestamptz | nullable |

### game_run.state (JSONB structure)

```json
{
  "player_hp": 42,
  "player_max_hp": 50,
  "player_is_defending": false,
  "special_cooldown": 0,
  "phase": "player_turn",
  "current_round": 3,
  "enemy": {
    "name": "Shadow",
    "breed": "Black Shorthair",
    "hp": 18,
    "max_hp": 30,
    "attack": 12,h
    "defense": 8,
    "speed": 14,
    "ability": "Shadow Pounce",
    "avatar_url": "..."
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
2. Creates a new game_run (status: `digitizing`)
3. Uploads cat photo → `POST /api/digitize` (FastAPI)
   - Classify breed via HuggingFace
   - Claude generates name, stats, ability, lore
   - DALL-E 3 generates avatar
   - Cat row created, linked to run
4. Battle begins (status: `in_progress`, state populated)
5. Turn-based combat loop:

| Action | Effect |
|---|---|
| Attack | damage = atk - def × 0.5 (min 1) |
| Defend | incoming damage halved for one turn |
| Special | 2× damage, 3-turn cooldown |

6. HP hits 0 → lose 1 life, revive to 100% HP, continue same fight
7. Lives hit 0 → run over:
   - `cat.status = 'memorial'`, set `death_date`, increment `wins`
   - `game_run.status = 'completed'`, set `completed_at`
8. Memorial page: all user's cats where `status = 'memorial'`

## Enemy Generation

Procedural only — no LLM per encounter. Scaled by round:
```typescript
multiplier = 1 + (round - 1) * 0.3  // +30% per round
hp  = floor((20 + round * 5) * multiplier)
atk = floor((8 + round * 2) * multiplier)
def = floor((6 + round * 1.5) * multiplier)
spd = floor((7 + round * 2) * multiplier)
```

Enemy names, breeds, abilities — random from fixed lists, seeded for reproducibility.

Enemy avatars: CSS/SVG procedural or pre-made silhouettes (not DALL-E).

## Mid-Run Persistence

- After every action: `supabase.from('game_run').update({ state }).eq('id', runId)`
- On page load: fetch `in_progress` run + cat in one query
- No FastAPI involvement in game loop — Supabase client direct from frontend

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
│   │   │   ├── useGameState.ts
│   │   │   ├── useMemorial.ts
│   │   │   └── useSupabase.ts
│   │   ├── api/
│   │   │   └── digitize.ts
│   │   ├── types/
│   │   │   └── game.ts
│   │   └── utils/
│   │       ├── combat.ts
│   │       └── enemyGen.ts
│   ├── index.html
│   └── vite.config.ts
├── backend/
│   ├── main.py
│   ├── routers/
│   │   └── digitize.py
│   ├── services/
│   │   ├── classifier.py
│   │   ├── card_generator.py
│   │   └── image_generator.py
│   └── models/
│       └── schemas.py
└── supabase/
    └── migration.sql
```

## Technical Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | Python FastAPI (AI pipeline only) |
| Database | Supabase (Postgres + Auth) |
| ML — breed classification | HuggingFace Inference API |
| LLM — card generation | Claude API |
| Image generation | DALL-E 3 |
| Deployment | Vercel (frontend) + Render (backend) |

## RLS Policies

- `cat`: user can CRUD own cats (`WHERE user_id = auth.uid()`)
- `game_run`: accessible via cat's user_id (subquery or join)
