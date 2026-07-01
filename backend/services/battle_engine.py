"""
Battle Engine Service — pure turn orchestration for the Nine Lives battle system.

This module composes the low-level combat primitives in `services.combat` and the
enemy factory in `services.enemy_gen` into the higher-level "turn" operations that
the Battle Router (`routers/battle.py`, Task 4.6) drives in sequence.

Every function here is PURE: no database access, no I/O, no side effects. Inputs are
never mutated — each function works on a deep copy (`state.model_copy(deep=True)`)
and returns a new `GameState`. Given the same inputs the same outputs are produced
(the sole exception is enemy AI action selection, which uses `random` for choosing
among equally-valid regular abilities, mirroring the enemy generator's use of
`random`).

Composition contract (the Battle Router calls these in order):

    state, events = resolve_player_action(state, action, ability_id, cat)
    if state.enemy.hp == 0:
        state = resolve_round_progression(state, cat)     # skip enemy turn
    else:
        state, enemy_events = resolve_enemy_turn(state)
        state, game_over, revival = resolve_death_and_revival(state, cat)

Validation failures (wrong phase, unknown/unaffordable ability) are signalled by
raising `InvalidActionError`, which the router maps to an HTTP 4xx response. When an
`InvalidActionError` is raised the caller's original `state` is left untouched.

`events` are human-readable log strings returned to the router for inclusion in the
API response. They are intentionally NOT written into `GameState.events` here so that
they are never persisted to the database — persistence of transient turn logs is not
desired.

Related: Requirements 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 28.
"""

import random

from models.schemas import (
    AbilityType,
    CreatureBase,
    EnemyAbility,
    GameState,
    Phase,
)
from services.combat import (
    apply_ability_effect,
    calculate_damage,
    regen_mana,
    tick_cooldowns,
)
from services.enemy_gen import generate_enemy


class InvalidActionError(Exception):
    """Raised when a battle action cannot be legally performed.

    The Battle Router maps this to an HTTP 4xx response (e.g. 400 Bad Request /
    409 Conflict). When raised, the caller's original `GameState` is never
    mutated, satisfying Requirement 11.9 ("reject the action and return an error
    response without modifying Game_State").
    """


def resolve_player_action(
    state: GameState,
    action: str,
    ability_id: str | None,
    cat: CreatureBase,
) -> tuple[GameState, list[str]]:
    """Resolve the player's chosen action for the current turn.

    Turn-start bookkeeping (Requirements 10.4, 12.1-12.2, 13.1-13.2) is applied
    BEFORE the action itself:
        * reset `player_is_defending` to False
        * regenerate player mana
        * tick (decrement) all player ability cooldowns

    Supported actions:
        * "attack"  — basic attack against the enemy (Requirement 9). Damage is
          `calculate_damage(cat.dmg, enemy.defence, is_defending=False,
          shield=enemy.shield)`; the enemy's shield absorbs before HP
          (Req 14.5-14.8, 16.2). HP floored at 0.
        * "defend"  — set `player_is_defending = True` (Requirement 10.2).
        * "ability" — use the ability identified by `ability_id` from `cat.abilities`
          (Requirement 11). Requires `player_mana >= mana_cost` AND cooldown == 0,
          otherwise `InvalidActionError` is raised without further mutation. On
          success the effect is applied, mana is deducted, and the ability's
          cooldown is set to its maximum.

    Args:
        state: The current game state (phase must be PLAYER_TURN).
        action: One of "attack", "defend", "ability".
        ability_id: The ability id (required only for the "ability" action).
        cat: The player's creature (source of dmg, defence, abilities, maxes).

    Returns:
        A tuple of (updated_state, events) where `events` is a human-readable log.

    Raises:
        InvalidActionError: if the phase is not PLAYER_TURN, the action is
            unknown, the ability id is missing/unknown, or the ability is
            unaffordable or on cooldown.
    """
    if state.phase != Phase.PLAYER_TURN:
        raise InvalidActionError(
            f"Cannot act: expected phase PLAYER_TURN, got {state.phase.value}"
        )

    new_state = state.model_copy(deep=True)
    events: list[str] = []

    # ── Turn-start bookkeeping (before the action) ──
    new_state.player_is_defending = False  # Req 10.4
    new_state.player_mana = regen_mana(new_state.player_mana, new_state.player_max_mana)  # Req 12.1-12.2
    new_state.player_ability_cooldowns = tick_cooldowns(new_state.player_ability_cooldowns)  # Req 13.1-13.2

    if action == "attack":
        damage_to_hp, shield_remaining = calculate_damage(
            cat.dmg, new_state.enemy.defence, False, new_state.enemy.shield
        )
        new_state.enemy.shield = shield_remaining
        new_state.enemy.hp = max(0, new_state.enemy.hp - damage_to_hp)  # Req 9.4, 14.5-14.8, 16.2
        events.append(
            f"{cat.name} attacks {new_state.enemy.name} for {damage_to_hp} damage."
        )

    elif action == "defend":
        new_state.player_is_defending = True  # Req 10.2
        events.append(f"{cat.name} takes a defensive stance.")

    elif action == "ability":
        if not ability_id:
            raise InvalidActionError("ability action requires an ability_id")

        ability = next((a for a in cat.abilities if a.id == ability_id), None)
        if ability is None:
            raise InvalidActionError(f"Unknown ability id: {ability_id}")

        cooldown = new_state.player_ability_cooldowns.get(ability_id, 0)
        if new_state.player_mana < ability.mana_cost or cooldown > 0:  # Req 11.2, 11.3, 11.9
            raise InvalidActionError(
                f"Ability '{ability.name}' unavailable "
                f"(mana {new_state.player_mana}/{ability.mana_cost}, cooldown {cooldown})"
            )

        # Apply the effect (DMG→enemy, HEAL/SHIELD→player), then pay costs. Req 11.4-11.8
        new_state = apply_ability_effect(ability, new_state)
        new_state.player_mana -= ability.mana_cost
        new_state.player_ability_cooldowns[ability_id] = ability.cooldown
        events.append(f"{cat.name} uses {ability.name}.")

    else:
        raise InvalidActionError(f"Unknown action: {action}")

    return new_state, events


def resolve_enemy_turn(
    state: GameState, player_defence: int = 0
) -> tuple[GameState, list[str]]:
    """Resolve the enemy's turn (Requirement 15).

    Turn-start bookkeeping (Requirements 12.3-12.4, 13.3):
        * regenerate enemy mana
        * tick (decrement) all enemy ability cooldowns

    Action selection (Requirement 15.3-15.4):
        1. If the special (is_special) ability is off cooldown AND affordable, use it.
        2. Otherwise, if any regular ability is off cooldown AND affordable, use a
           random one.
        3. Otherwise fall back to a basic attack.

    Damage application:
        * Basic attack (Req 15.6): `calculate_damage(enemy.atk, player_defence,
          player_is_defending, player_shield)` — defend halving is applied before
          shield absorption (Req 14.4). Player HP floored at 0; shield updated.
        * Ability DMG/TRUE_DMG: full ability value ignores the player's defence
          stat (Req 28.4) but is still routed through the defend reduction and
          shield absorption per the task contract — modelled as
          `calculate_damage(ability.dmg, def_=0, player_is_defending, player_shield)`.
        * Ability HEAL: heals the ENEMY, capped at enemy.max_hp (mirror of player).
        * Ability SHIELD: adds the ability value to `enemy.shield`, mirroring the
          player's SHIELD behavior (Req 15.5).

    Args:
        state: The current game state (typically ENEMY_TURN or mid-turn).
        player_defence: The player's defence stat, used for the enemy basic-attack
            formula (Req 15.6). `GameState` does not persist the player's defence,
            so the router supplies it from the cat (`cat.defence`). Defaults to 0
            so that the documented `resolve_enemy_turn(state)` signature remains
            callable; when 0, the enemy basic attack applies no defence reduction.

    Returns:
        A tuple of (updated_state, events).
    """
    new_state = state.model_copy(deep=True)
    events: list[str] = []
    enemy = new_state.enemy

    # ── Turn-start bookkeeping ──
    enemy.mana = regen_mana(enemy.mana, enemy.max_mana)  # Req 12.3-12.4
    enemy.ability_cooldowns = tick_cooldowns(enemy.ability_cooldowns)  # Req 13.3

    def _affordable(a: EnemyAbility) -> bool:
        return enemy.ability_cooldowns.get(a.id, 0) == 0 and enemy.mana >= a.mana_cost

    special = next((a for a in enemy.abilities if a.is_special), None)
    chosen: EnemyAbility | None = None

    if special is not None and _affordable(special):
        chosen = special
    else:
        regulars = [a for a in enemy.abilities if not a.is_special and _affordable(a)]
        if regulars:
            chosen = random.choice(regulars)

    if chosen is None:
        # ── Basic attack (Req 15.6) ──
        damage_to_hp, shield_remaining = calculate_damage(
            enemy.atk,
            player_defence,
            new_state.player_is_defending,
            new_state.player_shield,
        )
        new_state.player_shield = shield_remaining
        new_state.player_hp = max(0, new_state.player_hp - damage_to_hp)  # Req 16.1
        events.append(f"{enemy.name} attacks for {damage_to_hp} damage.")
    else:
        # ── Ability usage (Req 15.5): pay costs, then apply effect ──
        enemy.mana -= chosen.mana_cost
        enemy.ability_cooldowns[chosen.id] = chosen.cooldown

        if chosen.type in (AbilityType.DMG, AbilityType.TRUE_DMG):
            # Ability damage ignores defence (def_=0) but respects defend + shield.
            damage_to_hp, shield_remaining = calculate_damage(
                chosen.dmg, 0, new_state.player_is_defending, new_state.player_shield
            )
            new_state.player_shield = shield_remaining
            new_state.player_hp = max(0, new_state.player_hp - damage_to_hp)
            events.append(f"{enemy.name} uses {chosen.name} for {damage_to_hp} damage.")
        elif chosen.type == AbilityType.HEAL:
            enemy.hp = min(enemy.max_hp, enemy.hp + chosen.dmg)  # mirror of player HEAL
            events.append(f"{enemy.name} uses {chosen.name} and recovers HP.")
        elif chosen.type == AbilityType.SHIELD:
            enemy.shield += chosen.dmg  # Req 15.5, 16 (mirror of player SHIELD)
            events.append(f"{enemy.name} uses {chosen.name} and gains a shield.")
        else:
            events.append(f"{enemy.name} uses {chosen.name}.")

    return new_state, events


def resolve_death_and_revival(
    state: GameState, cat: CreatureBase
) -> tuple[GameState, bool, bool]:
    """Resolve player death, revival, or game-over (Requirements 17, 18).

    * player_hp == 0 and lives_remaining > 0 → revival: decrement lives, restore
      HP and mana to max, reset shield to 0. Returns revival=True, game_over=False.
    * player_hp == 0 and lives_remaining == 0 → game over. Returns game_over=True,
      revival=False. (Cat/game_run status transitions are the router's job.)
    * otherwise → state unchanged, both flags False.

    Args:
        state: The current game state (after the enemy turn).
        cat: The player's creature (unused for maxes since GameState carries its
            own maxes, but kept for interface symmetry and future use).

    Returns:
        A tuple of (new_state, game_over, revival).
    """
    if state.player_hp != 0:
        return state, False, False

    if state.lives_remaining > 0:
        new_state = state.model_copy(deep=True)
        new_state.lives_remaining -= 1  # Req 17.1
        new_state.player_hp = new_state.player_max_hp  # Req 17.2
        new_state.player_mana = new_state.player_max_mana  # Req 17.3
        new_state.player_shield = 0  # Req 17.4
        return new_state, False, True

    # HP == 0 and no lives left → game over (Req 18.1-18.4 handled by router)
    return state, True, False


def resolve_round_progression(state: GameState, cat: CreatureBase) -> GameState:
    """Advance to the next round when the enemy is defeated (Requirement 19).

    When `enemy.hp == 0`:
        * increment `current_round` (Req 19.2)
        * generate a new, round-scaled enemy via `generate_enemy` (Req 19.3)
        * pre-set the NEW enemy's special ability cooldown to its max (Req 8.9)
        * set phase to PLAYER_TURN and skip the enemy turn (Req 19.5)
        * preserve player HP / mana / cooldowns (Req 19.4) — untouched here

    The wins counter (Req 19.1) is persisted on the cat by the router; there is no
    wins field on `GameState`, so it is intentionally not tracked here.

    If the enemy is still alive, the state is returned unchanged.

    Args:
        state: The current game state.
        cat: The player's creature (interface symmetry; not mutated here).

    Returns:
        The updated GameState (a copy when progression occurs, else the input).
    """
    if state.enemy.hp != 0:
        return state

    new_state = state.model_copy(deep=True)
    new_round = new_state.current_round + 1
    new_state.current_round = new_round

    new_enemy = generate_enemy(new_round)
    # Req 8.9: prevent immediate ultimate usage by starting the special on cooldown.
    for ability in new_enemy.abilities:
        if ability.is_special:
            new_enemy.ability_cooldowns[ability.id] = ability.cooldown
    new_state.enemy = new_enemy
    new_state.phase = Phase.PLAYER_TURN  # Req 19.5

    return new_state
