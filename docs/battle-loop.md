# Battle Loop — Implementation Plan

> **Status:** Design doc
> **Last updated:** June 25, 2026

## Overview

The battle loop is a turn-based combat system that runs entirely on the frontend. The backend is only involved for the initial digitize pipeline. Every action persists the full game state to Supabase so the player can refresh without losing progress.

## Flow

```
BattlePage mounts
  → fetch game_run (status: IN_PROGRESS) + cat
  → restore GameState from game_run.state (JSONB)
  → if no state → init round 1 with first enemy
  ─────────────────────────────────
  PLAYER_TURN:
    → player chooses: Attack / Defend / Special
    → apply action to state
    → check if enemy HP ≤ 0
      → yes → increment round, spawn new enemy, keep player HP
      → no  → proceed to enemy turn
    → persist state to Supabase
  ─────────────────────────────────
  ENEMY_TURN:
    → animate enemy action (1-2s delay for drama)
    → apply damage to player
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
  ├── player clicks Attack     → apply dmg → if enemy dead → next round (new enemy) → ENEMY_TURN
  │                                           if enemy alive → ENEMY_TURN
  ├── player clicks Defend     → set defending=true → ENEMY_TURN
  └── player clicks Special    → apply 2× dmg, set cooldown=3 → same as Attack

ENEMY_TURN
  ├── enemy attacks            → apply dmg → if player dead → resolve death → PLAYER_TURN or GAME_OVER
  │                                           if player alive → PLAYER_TURN
  └── after resolution         → increment turn counter, persist
```

### GameState (JSONB)

```typescript
interface GameState {
  player_hp: number;
  player_max_hp: number;
  player_is_defending: boolean;
  special_cooldown: number;
  phase: Phase;                       // PLAYER_TURN | ENEMY_TURN
  current_round: number;
  enemy: Enemy;
}
```

## Combat Calculations

All formulas from the master doc:

```
damage = atk - def × 0.5   (min 1)
defending halves incoming damage

Special: 2× damage, 3-turn cooldown (tracked via special_cooldown)
```

### Enemy stats per round

```typescript
function computeEnemyStats(round: number) {
  const m = 1 + (round - 1) * 0.3;           // +30% per round
  return {
    hp:  Math.floor((20 + round * 5) * m),
    atk: Math.floor((8  + round * 2) * m),
    def: Math.floor((6  + round * 1.5) * m),
    spd: Math.floor((7  + round * 2) * m),
  };
}
```

## Death & Revival

```
Player HP ≤ 0
  → lives_remaining -= 1
  → if lives_remaining > 0:
      → player_hp = player_max_hp (full revive)
      → enemy HP unchanged (continue same fight)
      → phase = PLAYER_TURN
  → if lives_remaining = 0:
      → GAME_OVER
      → cat.status = MEMORIAL
      → game_run.status = COMPLETED
      → show FarewellScreen → navigate to Memorial
```

## Persistence Strategy

After every action (player *and* enemy), persist the full state:

```typescript
async function persistState(runId: string, state: GameState) {
  await supabase
    .from("game_run")
    .update({ state, current_round: state.current_round })
    .eq("id", runId);
}
```

### Performance notes

- Writing ~1KB JSONB per action is fine for turn-based gameplay
- No debounce needed — player can't act faster than the animation cycle
- On page load, fetch `game_run` + `cat` in one query via join

## UI Sequence (per turn)

```
1. Player sees enemy + their cat + action buttons
2. Player clicks Attack / Defend / Special
3. Brief animation (player attacks → damage numbers on enemy)
4. Enemy attack phase (1-2s delay)
5. Enemy attacks → damage numbers on player
6. Health bars update
7. Back to step 1
```

## Edge Cases

| Case | Handling |
|------|----------|
| **Page refresh mid-battle** | State restored from `game_run.state` JSONB on mount |
| **Multiple tabs** | Last write wins; state might be slightly stale but acceptable for MVP |
| **Enemy dies and player also dies same turn** | Enemy death resolved first (player wins the round), then player death checked after |
| **Special on cooldown** | Button is disabled; show cooldown counter |
| **Player at full HP after revive** | Healing is a flat `max_hp` restore, no overheal |
| **Network error on persist** | Continue playing locally; last successful state still saved |

## Implementation Order

1. Wire up `BattlePage` — load run + cat, restore or init state
2. Implement action handlers in `useGameState.ts` (attack/defend/special)
3. Add enemy turn logic with timeout for drama
4. Connect `persistState` after every action
5. Build out the UI components (HealthBar, ActionButtons, BattleArena, LivesDisplay)
6. Handle death → revival flow
7. Handle game over → memorial transition
8. Animations with framer-motion (iteration 2 polish)
