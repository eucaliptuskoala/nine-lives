# Battle Loop — Design

> **Status:** Design doc
> **Last updated:** June 30, 2026

## Overview

The battle loop is a turn-based combat system that runs entirely on the backend. The frontend submits player actions via the Battle API and renders the `GameState` returned in the response. Every action persists the full game state to Supabase before the response is sent, so the player can refresh without losing progress.

## API

```
POST /api/battle/start   { run_id }
  → verify auth + ownership
  → if state already exists: return it (idempotent)
  → build initial GameState, generate enemy for round 1
  → persist to game_run.state
  → return BattleActionResponse

POST /api/battle/action  { run_id, action: "attack"|"defend"|"ability", ability_id? }
  → verify auth + ownership
  → 409 if game_run.status == COMPLETED
  → load + validate GameState
  → resolve full turn (player action → enemy turn)
  → persist updated state
  → return BattleActionResponse
```

Both endpoints require a valid Supabase JWT in the `Authorization` header.

`BattleActionResponse`:
```json
{
  "game_state": { ... },
  "revival": false,
  "game_over": false,
  "events": ["Player attacks for 12 damage", "Shadow uses Feral Swipe for 8 damage"]
}
```

## Flow

```
BattlePage mounts
  → call POST /api/battle/start {run_id}
  → render GameState from response
  ─────────────────────────────────
  PLAYER_TURN (backend, on receiving POST /api/battle/action):
    → regen 10% max_mana, tick player cooldowns
    → execute player action:
        attack:  damage = max(cat.dmg − enemy.def × 0.5, 1)
        defend:  player_is_defending = true
        ability: validate mana + cooldown, apply effect
    → if enemy HP ≤ 0:
        increment wins + round, generate new enemy, skip enemy turn
    → else → resolve enemy turn:
        regen enemy mana, tick enemy cooldowns
        AI picks: special (if available) → random ability → basic attack
        apply damage/effect to player
    → if player HP ≤ 0 and lives > 0:
        lives -= 1, restore HP/mana/shield, revival = true
    → if player HP ≤ 0 and lives = 0:
        cat.status = MEMORIAL, game_over = true
    → persist GameState
    → return BattleActionResponse
  ─────────────────────────────────
  Frontend on receiving response:
    → set gameState from response.game_state
    → if revival: show revival notification
    → if game_over: navigate to Memorial
```

## State Machine

### Phase transitions (all resolved server-side per action)

```
POST /api/battle/action received (PLAYER_TURN)
  ├── action="attack"  → apply damage → resolve enemy turn → return
  ├── action="defend"  → set defending → resolve enemy turn → return
  └── action="ability" → validate → apply effect → resolve enemy turn → return

Enemy turn (automatic, within same request)
  ├── AI picks action → apply → if player dead → revival or game_over
  └── return final state to frontend
```

### GameState (JSONB, written by backend only)

```typescript
interface GameState {
  player_hp: number;
  player_max_hp: number;
  player_mana: number;
  player_max_mana: number;
  player_is_defending: boolean;
  player_shield: number;
  player_ability_cooldowns: Record<string, number>;
  phase: Phase;             // always PLAYER_TURN in persisted state
  current_round: number;
  enemy: Enemy;
}
```

### EnemyAbility (embedded in GameState.enemy, not a standalone DB record)

```typescript
interface EnemyAbility {
  id: string;
  name: string;
  dmg: number;
  type: AbilityType;
  effect: Effect | null;
  mana_cost: number;
  cooldown: number;
  is_special: boolean;
  description: string;
}
```

## Combat Calculations

All calculations run in `services/combat.py` on the backend.

### Basic attack
```
damage = max(atk - def × 0.5, 1)
```

### Ability damage
```
damage = ability.dmg  (applied directly, no defence reduction)
```

### Defend + Shield stacking
```
1. Incoming damage halved if defending
2. Shield absorbs up to player_shield from remaining damage
3. Rest goes to HP
```

Example:
```
Incoming: 30
Defending? Yes → 15
Shield: 8       → shield consumed, 7 goes to HP
```

### Mana regen (start of each creature's turn)
```
mana = min(max_mana, mana + floor(max_mana × 0.1))
```

### Cooldowns (ticked at start of creature's turn)
```
Each active cooldown decreases by 1 (floor 0).
Ability usable when cooldown === 0.
```

### Enemy stats per round

```python
def compute_enemy_stats(round_num: int) -> dict:
    m = 1 + (round_num - 1) * 0.3
    return {
        "hp":       floor((20 + round_num * 5) * m),
        "atk":      floor((8  + round_num * 2) * m),
        "def":      floor((6  + round_num * 1.5) * m),
        "spd":      floor((7  + round_num * 2) * m),
        "max_mana": 80 + round_num * 5,
    }
```

## Enemy AI

Runs in `services/combat.py` → `resolve_enemy_turn()`.

```
1. If can_use(ultimate): use ultimate
2. Else if can_use(any ability): pick random available
3. Else: basic attack
```

"Can use" = mana >= ability.mana_cost AND cooldown === 0.

## Death & Revival

Resolved by `services/battle_engine.py` → `resolve_death_and_revival()`.

```
Player HP ≤ 0
  → lives_remaining -= 1
  → if lives_remaining > 0:
      → player_hp = player_max_hp
      → player_mana = player_max_mana
      → player_shield = 0
      → enemy HP unchanged
      → revival = true in response
  → if lives_remaining = 0:
      → game_over = true in response
      → cat.status = MEMORIAL
      → game_run.status = COMPLETED
```

## Persistence Strategy

The backend persists state synchronously before returning each response. There is no debouncing or client-side write:

```python
# Inside POST /api/battle/action, after resolving the full turn:
supabase.table("game_run").update({
    "state": game_state.model_dump(),
    "current_round": game_state.current_round,
    "status": "COMPLETED" if game_over else "IN_PROGRESS"
}).eq("id", run_id).execute()
```

On page refresh: frontend calls `POST /api/battle/start` — the backend returns the existing persisted state (idempotent).

## UI Sequence (per turn)

```
1. Player sees enemy + their cat + action buttons
2. Player clicks Attack / Defend / Ability 1-4
3. Frontend sends POST /api/battle/action, disables buttons (loading)
4. Backend resolves full turn, returns response
5. Frontend re-enables buttons, renders updated GameState
6. If revival: show notification
7. If game_over: navigate to Memorial
```

## Edge Cases

| Case | Handling |
|------|----------|
| **Page refresh mid-battle** | Frontend calls `POST /api/battle/start` → backend returns persisted state |
| **Multiple tabs** | Last write wins (acceptable for MVP) |
| **Enemy dies and player also dies same turn** | Enemy death (round progression) takes priority; player death not possible if round ends |
| **Not enough mana** | Backend rejects ability action with error; frontend re-enables buttons |
| **All abilities on cooldown + no mana** | Only attack and defend actions are submitted |
| **Shield + Defend active** | Damage halved first (defend), then absorbed by shield |
| **HEAL at max HP** | Mana consumed; HP stays at max (no overflow) |
| **Network error on action** | Backend either succeeded or didn't — frontend retries from last persisted state |
| **Revive restores mana** | Full mana restore on revival |
| **Action on completed game** | Backend returns 409 Conflict |

## Implementation Order

1. Create `services/combat.py` — pure damage/mana/cooldown functions (Python port of former `combat.ts`)
2. Create `services/enemy_gen.py` — enemy stat scaling + ability pool
3. Create `services/battle_engine.py` — `resolve_player_action`, `resolve_enemy_turn`, `resolve_death_and_revival`, `resolve_round_progression`
4. Create `routers/battle.py` — `POST /api/battle/start` and `POST /api/battle/action`
5. Register battle router in `main.py`
6. Update `useGameState.ts` — replace all combat math with `startBattle()` and `submitAction()` API calls
7. Update `BattlePage.tsx` — wire all action buttons to `submitAction`, handle `revival` and `game_over` flags
8. Delete `frontend/src/utils/combat.ts` and `frontend/src/utils/enemyGen.ts`
