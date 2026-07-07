"""
Combat Service

Pure combat calculation functions for the Nine Lives battle system. This module
is the authoritative source of combat math on the backend and is a Python port of
the former frontend `combat.ts` / `useGameState.ts` logic.

Every function here is PURE: no I/O, no database access, no side effects, and no
mutation of input arguments. Given the same inputs, each function always returns
the same output. This makes the combat rules deterministic and easy to verify with
unit and property-based tests.

Related: Requirements 9 (Basic Attack), 10 (Defend), 11 (Ability Usage),
12 (Mana Regeneration), 13 (Cooldown Management), 14 (Shield Mechanics),
16 (HP Bounds), 28 (Combat Formula Consistency).
"""

import math

from models.schemas import Ability, AbilityType, EnemyAbility, GameState


def calculate_damage(
    atk: int, def_: int, is_defending: bool, shield: int
) -> tuple[int, int]:
    """
    Calculate basic-attack damage against a target, accounting for defence,
    the defend action, and shield absorption.

    Formula (Requirements 9.2, 9.3, 10.3, 14.1-14.4, 28.1-28.3):
        raw = max(atk - def_ * 0.5, 1)          # minimum 1 damage guaranteed
        if is_defending: raw = floor(raw * 0.5) # defend halves incoming damage
        absorbed = min(shield, raw)             # shield absorbs first
        damage_to_hp = floor(raw - absorbed)
        shield_remaining = shield - absorbed

    Defend reduction is applied BEFORE shield absorption (Requirement 14.4).

    Args:
        atk: Attacker's attack/damage stat.
        def_: Defender's defence stat.
        is_defending: Whether the defender is defending this turn.
        shield: The defender's current shield value.

    Returns:
        A tuple of (damage_to_hp, shield_remaining).
    """
    raw = max(atk - def_ * 0.5, 1)
    if is_defending:
        raw = math.floor(raw * 0.5)
    absorbed = min(shield, raw)
    damage_to_hp = math.floor(raw - absorbed)
    shield_remaining = shield - absorbed
    return damage_to_hp, shield_remaining


def regen_mana(current: int, max_mana: int) -> int:
    """
    Regenerate mana by floor(max_mana * 0.1), capped at max_mana.

    Formula (Requirements 12.1-12.4):
        min(max_mana, current + floor(max_mana * 0.1))

    Args:
        current: Current mana value.
        max_mana: Maximum mana value.

    Returns:
        The new mana value, never exceeding max_mana.
    """
    return min(max_mana, current + math.floor(max_mana * 0.1))


def tick_cooldowns(cooldowns: dict[str, int]) -> dict[str, int]:
    """
    Decrement every ability cooldown by 1, flooring at 0.

    Returns a NEW dict; the input is never mutated (Requirements 13.1-13.3).

    Args:
        cooldowns: Mapping of ability id -> remaining cooldown turns.

    Returns:
        A new mapping with each cooldown decremented by 1 (minimum 0).
    """
    return {ability_id: max(0, remaining - 1) for ability_id, remaining in cooldowns.items()}


def apply_ability_effect(
    ability: Ability | EnemyAbility, state: GameState
) -> GameState:
    """
    Apply a player-cast ability's effect and return an updated GameState.

    The input state is not mutated; a deep copy is returned.

    Effects (Requirements 11.6, 11.7, 11.8, 14, 16.3, 28.4):
        - DMG / TRUE_DMG: apply the ability damage to the enemy WITHOUT defence
          reduction (def_=0), but the enemy's shield still absorbs the damage
          before it reaches HP (`calculate_damage(ability.dmg, def_=0,
          is_defending=False, shield=enemy.shield)`); enemy shield and HP are
          updated, with HP floored at 0.
        - HEAL: new player HP = min(player_max_hp, player_hp + ability.dmg).
        - SHIELD: new player shield = player_shield + ability.dmg.

    Mana consumption and cooldown reset are handled by the caller (Battle Router /
    battle engine), not here — this function applies only the effect.

    Args:
        ability: The ability being used (player Ability or EnemyAbility).
        state: The current game state.

    Returns:
        A new GameState with the ability's effect applied.
    """
    new_state = state.model_copy(deep=True)

    if ability.type in (AbilityType.DMG, AbilityType.TRUE_DMG):
        # Ability damage ignores DEFENCE (def_=0) but the enemy's shield still
        # absorbs before HP (Req 11.6, 14.5-14.8, 16.2, 28.4).
        damage_to_hp, shield_remaining = calculate_damage(
            ability.dmg, def_=0, is_defending=False, shield=new_state.enemy.shield
        )
        new_state.enemy.shield = shield_remaining
        new_state.enemy.hp = max(0, new_state.enemy.hp - damage_to_hp)
    elif ability.type == AbilityType.HEAL:
        new_state.player_hp = min(
            new_state.player_max_hp, new_state.player_hp + ability.dmg
        )
    elif ability.type == AbilityType.SHIELD:
        new_state.player_shield = new_state.player_shield + ability.dmg
    else:
        msg = f"Unimplemented ability type: {ability.type}"
        raise ValueError(msg)

    return new_state
