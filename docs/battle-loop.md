# Battle Loop — Implementation Plan

> **Status:** Design doc
> **Last updated:** June 25, 2026

## Overview

The battle loop is a turn-based combat system that runs entirely on the frontend. The backend is only involved for the initial digitize pipeline. Every action persists the full game state to Supabase so the player can refresh without losing progress.

## Flow

```
BattlePage mounts
  → fetch game_run (status: IN_PROGRESS) + cat + abilities
  → restore GameState from game_run.state (JSONB)
  → if no state → init round 1 with first enemy
  ─────────────────────────────────
  At start of creature's turn → regen 10% max_mana, tick cooldowns
  ─────────────────────────────────
  PLAYER_TURN:
    → player chooses: Attack / Defend / Ability 1-4
    → basic attack: free, formula atk − def × 0.5 (min 1)
    → ability: deduct mana_cost, set cooldown, apply effect
    → check if enemy HP ≤ 0
      → yes → increment round, spawn new enemy, keep player HP
      → no  → proceed to enemy turn
    → persist state to Supabase
  ─────────────────────────────────
  ENEMY_TURN:
    → AI picks best available ability (mana + cooldown check)
    → if none available → basic attack
    → apply damage/effect to player
    → check if player HP ≤ 0
      → yes → lose a life, revive to full HP, continue same fight
      → no  → back to PLAYER_TURN
    → persist state to Supabase
  ─────────────────────────────────
  If lives_remaining = 0:
    → show FarewellScreen
    → set cat.status = MEMORIAL, death_date = now
    → set game_run.status = COMPLETED
    → navigate to Memorial
```

## State Machine

### Phase transitions

```
PLAYER_TURN
  ├── Attack      → basic dmg, 0 mana → ENEMY_TURN
  ├── Defend      → set defending=true → ENEMY_TURN
  └── Ability N   → deduct mana, set cooldown, apply effect → ENEMY_TURN

ENEMY_TURN
  ├── AI picks: use ability (mana+cooldown) or basic attack
  ├── apply → if player dead → resolve death → PLAYER_TURN or GAME_OVER
  └── if player alive → PLAYER_TURN
```

### GameState (JSONB)

```typescript
interface GameState {
  player_hp: number;
  player_max_hp: number;
  player_mana: number;
  player_max_mana: number;
  player_is_defending: boolean;
  player_shield: number;
  player_ability_cooldowns: Record<string, number>;
  phase: Phase;
  current_round: number;
  enemy: {
    name: string;
    breed: string;
    hp: number;
    max_hp: number;
    atk: number;
    def: number;
    spd: number;
    mana: number;
    max_mana: number;
    ability_cooldowns: Record<string, number>;
    abilities: EnemyAbility[];
    avatar_url: string;
  };
}
```

### EnemyAbility (in GameState, not persisted in DB)

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

### Basic attack
```
damage = max(atk - def × 0.5, 1)
```

### Ability damage
```
damage = ability.dmg  (used directly, replaces atk)
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
Shield: 8         → shield consumed, 7 goes to HP
```

### Mana regen (start of each creature's turn)
```
mana = min(max_mana, mana + floor(max_mana × 0.1))
```

### Cooldowns (ticked at start of creature's turn)
```
Each active cooldown decreases by 1.
Ability can be used when its cooldown === 0.
```

### Enemy stats per round

```typescript
function computeEnemyStats(round: number) {
  const m = 1 + (round - 1) * 0.3;
  return {
    hp:  Math.floor((20 + round * 5) * m),
    atk: Math.floor((8  + round * 2) * m),
    def: Math.floor((6  + round * 1.5) * m),
    spd: Math.floor((7  + round * 2) * m),
    max_mana: 80 + round * 5,
  };
}
```

## Enemy AI

```
1. If can_use(ultimate): use ultimate
2. Else if can_use(any ability): pick random available
3. Else: basic attack
```

"Can use" = enough mana AND cooldown === 0.

## Death & Revival

```
Player HP ≤ 0
  → lives_remaining -= 1
  → if lives_remaining > 0:
      → player_hp = player_max_hp
      → player_mana = player_max_mana
      → player_shield = 0
      → enemy HP unchanged
      → phase = PLAYER_TURN
  → if lives_remaining = 0:
      → GAME_OVER
      → cat.status = MEMORIAL
      → game_run.status = COMPLETED
      → show FarewellScreen → navigate to Memorial
```

## Persistence Strategy

After every action (player and enemy), persist the full state:

```typescript
async function persistState(runId: string, state: GameState) {
  await supabase
    .from("game_run")
    .update({ state, current_round: state.current_round })
    .eq("id", runId);
}
```

## UI Sequence (per turn)

```
1. Player sees enemy + their cat + action buttons
2. Player clicks Attack / Defend / Ability 1-4
3. Brief animation (player action → effects on enemy)
4. Enemy phase (1-2s delay)
5. Enemy action → damage/effects on player
6. Health/Mana/Shield bars update
7. Back to step 1
```

## Edge Cases

| Case | Handling |
|------|----------|
| **Page refresh mid-battle** | State restored from `game_run.state` JSONB on mount |
| **Multiple tabs** | Last write wins; acceptable for MVP |
| **Enemy dies and player also dies same turn** | Enemy death resolved first, then player death |
| **Not enough mana** | Ability button disabled, tooltip shows cost |
| **All abilities on cooldown + no mana** | Only Attack + Defend available |
| **Shield + Defend active** | Damage halved first, then absorbed by shield |
| **HEAL at max HP** | Still consumes mana, heal is wasted |
| **Network error on persist** | Continue playing locally; last successful state still saved |
| **Revive restores mana** | Full mana restore on revive |

## Implementation Order

1. Wire up `BattlePage` — load run + cat, restore or init state
2. Implement action handlers in `useGameState.ts` (attack/defend/ability)
3. Add enemy AI with ability selection
4. Add mana tracking + regen + cooldown tick
5. Shield/Defend stacking logic
6. Connect `persistState` after every action
7. Build out the UI components (HealthBar, ManaBar, ActionButtons, BattleArena, LivesDisplay)
8. Handle death → revival flow
9. Handle game over → memorial transition
10. Animations with framer-motion (iteration 2 polish)
