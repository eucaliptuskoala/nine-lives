# Nine Lives — Master Project Document

> **Hackathon:** #HackTheKitty by coding.kitty
> **Dates:** June 24 – July 7, 2026
> **Format:** Online, solo
> **Goal:** Certificate + project in portfolio
> **Last updated:** June 24, 2026

---

## Concept

A web app where the user uploads a photo of their cat — real or from the internet — and it gets digitized into a playable roguelike character. The cat has 9 lives. Each time HP hits 0, it loses a life and revives. When all 9 lives are gone, the cat moves to the **Memorial** — a quiet space where all fallen cats can be visited. The mechanic references the real experience of losing a pet and gives the game emotional depth.

---

## Domain Flow

1. User signs in (Supabase Auth)
2. Creates a new game run (status: `DIGITIZING`)
3. Uploads cat photo → `POST /api/digitize` (FastAPI)
   - Classify breed via HuggingFace
   - OpenCV k-means extracts dominant fur color(s)
   - Claude Haiku generates name, stats, abilities, lore
   - Gemini 2.5 Flash generates stylized avatar
   - Cat row created and linked to run
4. Battle begins (status: `IN_PROGRESS`, state populated)
5. Turn-based combat loop (see Combat Rules)
6. HP hits 0 → lose 1 life, revive to full HP, continue same fight
7. Lives hit 0 → run over:
   - `cat.status = MEMORIAL`, set `death_date`
   - `game_run.status = COMPLETED`, set `completed_at`
8. Memorial page: all cats where `status = MEMORIAL`

---

## Digitizer Pipeline

```
Photo upload
  → HuggingFace Inference API   → breed name
  → OpenCV k-means              → dominant fur color(s)
  → Claude Haiku                → name, stats, class, abilities, lore, image prompt
  → Gemini 2.5 Flash Image      → stylized cat avatar
```

---

## Combat Rules

| Action  | Effect                                      |
|---------|---------------------------------------------|
| Attack  | damage = atk - def × 0.5 (min 1)           |
| Defend  | incoming damage halved for one turn         |
| Special | 2× damage, 3-turn cooldown                  |

Enemy scaling by round:
```
multiplier = 1 + (round - 1) * 0.3   // +30% per round
hp  = floor((20 + round * 5) * multiplier)
atk = floor((8  + round * 2) * multiplier)
def = floor((6  + round * 1.5) * multiplier)
spd = floor((7  + round * 2) * multiplier)
```

---

## Data Model (ERD)

### Inheritance
`Cat` and `Enemy` both extend `Creature`. Cat adds user/memorial fields. Enemy is procedurally generated, never persisted.

### Creature (abstract base)

| Column         | Type           | Notes                        |
|----------------|----------------|------------------------------|
| id             | UUID PK        |                              |
| name           | text           |                              |
| breed          | text           |                              |
| class          | Class          | STRENGTH / AGILITY / INTELLIGENCE |
| current_hp     | int            |                              |
| max_hp         | int            |                              |
| dmg            | int            |                              |
| def            | int            |                              |
| spd            | int            |                              |
| abilities      | list(Ability)  |                              |
| lore           | text           |                              |
| avatar_url     | text           | Gemini generated             |
| lives_remaining| int            |                              |
| created_at     | timestamptz    |                              |

### Cat (extends Creature)

| Column           | Type        | Notes                        |
|------------------|-------------|------------------------------|
| user_id          | UUID FK     | → auth.users.id              |
| source_image_url | text        | original user upload         |
| status           | CatStatus   | ALIVE / MEMORIAL             |
| wins             | int         | rounds survived across runs  |
| death_date       | timestamptz | nullable                     |
| personal_note    | text        | nullable, set in memorial    |

### game_run

| Column       | Type        | Notes                                    |
|--------------|-------------|------------------------------------------|
| id           | UUID PK     |                                          |
| cat_id       | UUID FK     | → cat.id, nullable until digitize done  |
| status       | GameStatus  | DIGITIZING / IN_PROGRESS / COMPLETED     |
| current_round| int         |                                          |
| state        | GameState   | JSONB, full mid-run battle state         |
| created_at   | timestamptz |                                          |
| completed_at | timestamptz | nullable                                 |

### GameState (JSONB structure)

```json
{
  "player_hp": 42,
  "player_max_hp": 50,
  "player_is_defending": false,
  "special_cooldown": 0,
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
    "ability": "Shadow Pounce",
    "avatar_url": "..."
  }
}
```

### Ability

| Column      | Type        | Notes                        |
|-------------|-------------|------------------------------|
| id          | UUID PK     |                              |
| creature_id | UUID FK     |                              |
| name        | text        |                              |
| dmg         | int         |                              |
| type        | AbilityType |                              |
| effect      | Effect      | nullable                     |
| cooldown    | int         |                              |
| lore        | text        | short flavour line           |
| is_special  | bool        |                              |
| description | text        | what it does mechanically    |

### Enums

```
Class:       STRENGTH | AGILITY | INTELLIGENCE
CatStatus:   ALIVE | MEMORIAL
GameStatus:  DIGITIZING | IN_PROGRESS | COMPLETED
Phase:       PLAYER_TURN | ENEMY_TURN

AbilityType: DMG | HEAL | STEAL | SHIELD | AOE | COUNTER | TRUE_DMG
Effect:      STUN | SILENCE | BLEED | BURN | BLIND | SLOW | TAUNT | REGEN
```

### Class → Ability affinity
- **STRENGTH** — DMG, TRUE_DMG, BLEED
- **AGILITY** — COUNTER, BLIND, SLOW
- **INTELLIGENCE** — STUN, SILENCE, AOE, REGEN

### Relationship rules
- Each cat belongs to one user
- A cat can have multiple game runs
- When `lives_remaining` hits 0 → cat moves to memorial, no more runs
- `game_run.state` stores full mid-run state for persistence

---

## Enemy Generation

Procedural only — no LLM per encounter (too slow mid-battle).

- Stats: scaled by round using formula above
- Name, breed: random from fixed seed-based lists
- Abilities: 4 random from preset pool, filtered by class affinity (1 must be `is_special = true`)
- Avatar: CSS/SVG procedural silhouettes or pre-made assets — not Gemini

LLM is only called once per run: during digitization of the player's cat.

---

## Mid-Run Persistence

- After every action: `supabase.from('game_run').update({ state }).eq('id', runId)`
- On page load: fetch `in_progress` run + cat in one query
- Game loop runs entirely on frontend — no FastAPI involvement
- FastAPI handles only: digitize pipeline + any heavy AI calls

---

## Technical Stack

| Layer                   | Technology                        | Cost              |
|-------------------------|-----------------------------------|-------------------|
| Frontend                | React + Vite + TypeScript         | Free              |
| Styling                 | Tailwind CSS + framer-motion      | Free              |
| Backend                 | Python FastAPI                    | Free              |
| Database + Auth         | Supabase                          | Free tier         |
| Breed classification    | HuggingFace Inference API         | Free tier         |
| Fur color extraction    | OpenCV k-means                    | Free (no API)     |
| Card + ability generation | Claude Haiku (Anthropic API)    | Free tier         |
| Avatar generation       | Gemini 2.5 Flash Image            | Free — 500 req/day|
| Icons                   | game-icons.net (SVG, MIT)         | Free              |
| Sound                   | freesound.org                     | Free              |
| Deployment              | Vercel (frontend) + Render (backend) | Free           |

---

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
│   │   ├── classifier.py       # HuggingFace breed detection
│   │   ├── color_extractor.py  # OpenCV k-means
│   │   ├── card_generator.py   # Claude Haiku
│   │   └── image_generator.py  # Gemini 2.5 Flash
│   └── models/
│       └── schemas.py
└── supabase/
    └── migration.sql
```

---

## RLS Policies (Supabase)

- `cat`: user can CRUD own cats (`WHERE user_id = auth.uid()`)
- `game_run`: accessible via cat's user_id (subquery or join)

---

## Two-Iteration Plan

### Iteration 1 — "Working Game" (days 1–7, through June 30)
Full loop: photo upload → digitize → battle → memorial. Mechanics simple but connected end-to-end.

### Iteration 2 — "Make It Better" (days 8–14, July 1–7)
Improve what exists. Priority order:
1. Visual polish and animations (framer-motion)
2. Isaac-style rooms and movement — only if iteration 1 is solid
3. Supabase instead of localStorage (already planned in stack)
4. Sound (freesound.org + howler.js)
5. Memorial UX polish

### Day-by-Day

| Days       | Game / Frontend                          | ML / AI Pipeline                          |
|------------|------------------------------------------|-------------------------------------------|
| Jun 24–25  | Repo setup, project structure, basic UI  | HuggingFace model research, OpenCV color test |
| Jun 26–27  | Card component, battle state machine     | Breed classification integration          |
| Jun 28–29  | Battle loop: player turn → enemy → result| Claude card gen + Gemini avatar gen       |
| Jun 30     | Connect full loop end-to-end             | Integration tests, edge cases             |
| Jul 1–2    | Memorial UI + save logic + personal notes|                                           |
| Jul 3–4    | Iteration 2 improvements                 |                                           |
| Jul 5–6    | Final polish, deploy, README             |                                           |
| Jul 7      | Video demo + submit                      |                                           |

**Checkpoint June 30:** full game loop works end-to-end.

---

## Out of Scope (MVP)

- Multiplayer
- Inventory / item drops (planned for post-hackathon)
- Damage type resistances (planned for post-hackathon)
- Attribute scaling system (STR/AGI/INT affecting stats)
- Complex narrative and dialogue
- Mobile adaptation
- User authentication beyond Supabase basic auth

---

## Judging Criteria Coverage

| Criterion              | How this project covers it                                     |
|------------------------|----------------------------------------------------------------|
| **Technical execution**| ML + OpenCV + LLM + image gen + game mechanics — complex stack |
| **Innovation**         | Digitizing a real cat as a game character — genuinely novel    |
| **Theme relevance**    | 100% — cats central to every mechanic                         |
| **Documentation**      | README + architecture diagram + video demo                     |
| **UX/UI**              | Two contrasting spaces: battle vs memorial                     |
| **Security**           | API keys in env, file upload validation, RLS policies          |
