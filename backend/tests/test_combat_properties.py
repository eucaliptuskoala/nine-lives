"""
Property-based tests for `services/combat.py` (pytest + hypothesis).

These tests verify the named Correctness Properties from the design document
against the pure combat functions. Every function in `combat.py` is pure, so we
can exercise them across a wide range of inputs without any mocking or I/O.

Properties covered (design.md → Correctness Properties):
- Property 8:  Basic Attack Damage Formula — damage = max(atk - def*0.5, 1),
               guaranteeing a minimum of 1 to HP when there is no shield.
               **Validates: Requirements 9.2, 9.3, 28.1, 28.2**
- Property 9:  Damage Application to HP — HP stays within [0, max_hp]
               (damage floors at 0; healing caps at max_hp).
               **Validates: Requirements 9.4**
- Property 10: Defend Damage Reduction — defending reduces effective damage to
               exactly floor(raw * 0.5).
               **Validates: Requirements 10.3, 28.3**
- Property 17: Mana Regeneration Formula — regen adds floor(max_mana * 0.1)
               without ever exceeding max_mana.
               **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
- Property 18: Cooldown Decrement — each cooldown decremented by 1, floored at 0,
               without mutating the input dict.
               **Validates: Requirements 13.1, 13.2, 13.3**
"""

import math

import pytest
from hypothesis import given, strategies as st

from models.schemas import (
    Ability,
    AbilityType,
    Enemy,
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

# ---------------------------------------------------------------------------
# Strategies — constrained to the design's stat bounds to stay realistic/fast.
# ---------------------------------------------------------------------------
atk_st = st.integers(min_value=5, max_value=50)
def_st = st.integers(min_value=3, max_value=40)
shield_st = st.integers(min_value=0, max_value=100)
mana_st = st.integers(min_value=0, max_value=200)
max_mana_st = st.integers(min_value=1, max_value=200)
hp_st = st.integers(min_value=0, max_value=300)
max_hp_st = st.integers(min_value=1, max_value=300)
dmg_st = st.integers(min_value=0, max_value=100)
cooldown_st = st.integers(min_value=0, max_value=10)


# ---------------------------------------------------------------------------
# Factories — minimal valid domain objects for apply_ability_effect tests.
# ---------------------------------------------------------------------------
def make_enemy(hp: int, max_hp: int, shield: int = 0) -> Enemy:
    return Enemy(
        name="Test Enemy",
        breed="Alley",
        hp=hp,
        max_hp=max_hp,
        atk=10,
        defence=5,
        spd=5,
        mana=50,
        max_mana=100,
        shield=shield,
        ability_cooldowns={},
        abilities=[],
        avatar_url="http://example.com/enemy.png",
    )


def make_game_state(
    player_hp: int,
    player_max_hp: int,
    player_shield: int = 0,
    enemy_hp: int = 100,
    enemy_max_hp: int = 100,
    enemy_shield: int = 0,
) -> GameState:
    return GameState(
        player_hp=player_hp,
        player_max_hp=player_max_hp,
        player_mana=50,
        player_max_mana=100,
        player_is_defending=False,
        player_shield=player_shield,
        lives_remaining=9,
        player_ability_cooldowns={},
        phase=Phase.PLAYER_TURN,
        current_round=1,
        enemy=make_enemy(enemy_hp, enemy_max_hp, enemy_shield),
        events=None,
    )


def make_ability(ability_type: AbilityType, dmg: int) -> Ability:
    return Ability(
        id="ability-1",
        creature_id="creature-1",
        name="Test Ability",
        dmg=dmg,
        type=ability_type,
        effect=None,
        cooldown=3,
        mana_cost=10,
        lore="test lore",
        is_special=False,
        description="test description",
    )


def make_enemy_ability(ability_type: AbilityType, dmg: int) -> EnemyAbility:
    return EnemyAbility(
        id="enemy-ability-1",
        name="Test Enemy Ability",
        dmg=dmg,
        type=ability_type,
        effect=None,
        mana_cost=10,
        cooldown=3,
        is_special=False,
        description="test description",
    )


# ---------------------------------------------------------------------------
# Property 8: Basic Attack Damage Formula
# **Validates: Requirements 9.2, 9.3, 28.1, 28.2**
# ---------------------------------------------------------------------------
@given(atk=atk_st, def_=def_st)
def test_property_8_minimum_one_damage_to_hp_when_no_shield(atk, def_):
    """With no shield, a basic (non-defending) attack always deals >= 1 to HP."""
    damage_to_hp, shield_remaining = calculate_damage(atk, def_, False, 0)
    assert damage_to_hp >= 1
    assert shield_remaining == 0


@given(atk=atk_st, def_=def_st, is_defending=st.booleans(), shield=shield_st)
def test_property_8_formula_matches_and_raw_at_least_one(atk, def_, is_defending, shield):
    """The output matches the documented formula, and the min-1 raw guarantee holds.

    The min-1 guarantee applies to the raw pre-shield, pre-defend damage:
    raw = max(atk - def*0.5, 1) is always >= 1. Defend then halves it (and may
    floor it to 0), and shield absorbs before it reaches HP.
    """
    # Raw damage before defend/shield is always at least 1 (the guarantee).
    raw = max(atk - def_ * 0.5, 1)
    assert raw >= 1

    # Recompute the full expected result using the documented semantics.
    effective = math.floor(raw * 0.5) if is_defending else raw
    absorbed = min(shield, effective)
    expected_damage_to_hp = math.floor(effective - absorbed)
    expected_shield_remaining = shield - absorbed

    damage_to_hp, shield_remaining = calculate_damage(atk, def_, is_defending, shield)

    assert damage_to_hp == expected_damage_to_hp
    assert shield_remaining == expected_shield_remaining
    assert damage_to_hp >= 0
    assert shield_remaining >= 0


# ---------------------------------------------------------------------------
# Property 9: Damage Application to HP  (HP stays within [0, max_hp])
# **Validates: Requirements 9.4**
# ---------------------------------------------------------------------------
@given(
    enemy_hp=hp_st,
    enemy_max_hp=max_hp_st,
    dmg=dmg_st,
    ability_type=st.sampled_from([AbilityType.DMG, AbilityType.TRUE_DMG]),
)
def test_property_9_damage_never_drives_enemy_hp_below_zero(
    enemy_hp, enemy_max_hp, dmg, ability_type
):
    """Applying DMG/TRUE_DMG floors enemy HP at 0 and never exceeds max_hp.

    Ability damage is routed through `calculate_damage(dmg, def_=0, shield=0)`,
    which enforces the minimum-1-damage guarantee (raw = max(dmg, 1)) before
    shield absorption. With no shield the full raw amount reaches HP.
    """
    enemy_hp = min(enemy_hp, enemy_max_hp)
    state = make_game_state(
        player_hp=50,
        player_max_hp=100,
        enemy_hp=enemy_hp,
        enemy_max_hp=enemy_max_hp,
    )
    ability = make_ability(ability_type, dmg)

    new_state = apply_ability_effect(ability, state)

    raw = max(dmg, 1)  # def_=0, no shield, min-1 guarantee
    assert 0 <= new_state.enemy.hp <= new_state.enemy.max_hp
    assert new_state.enemy.hp == max(0, enemy_hp - raw)


@given(player_hp=hp_st, player_max_hp=max_hp_st, dmg=dmg_st)
def test_property_9_heal_never_exceeds_max_hp(player_hp, player_max_hp, dmg):
    """HEAL raises player HP toward max_hp but never above it, and never below 0."""
    player_hp = min(player_hp, player_max_hp)
    state = make_game_state(player_hp=player_hp, player_max_hp=player_max_hp)
    ability = make_ability(AbilityType.HEAL, dmg)

    new_state = apply_ability_effect(ability, state)

    assert 0 <= new_state.player_hp <= new_state.player_max_hp
    assert new_state.player_hp == min(player_max_hp, player_hp + dmg)


# ---------------------------------------------------------------------------
# Property 10: Defend Damage Reduction  (defending == floor(raw * 0.5))
# **Validates: Requirements 10.3, 28.3**
# ---------------------------------------------------------------------------
@given(atk=atk_st, def_=def_st)
def test_property_10_defend_halves_effective_damage(atk, def_):
    """Defending reduces effective (no-shield) damage to exactly floor(raw * 0.5)."""
    raw = max(atk - def_ * 0.5, 1)

    non_defending_dmg, _ = calculate_damage(atk, def_, False, 0)
    defending_dmg, _ = calculate_damage(atk, def_, True, 0)

    assert non_defending_dmg == math.floor(raw)
    assert defending_dmg == math.floor(raw * 0.5)


# ---------------------------------------------------------------------------
# Property 17: Mana Regeneration Formula
# **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
# ---------------------------------------------------------------------------
@given(current=mana_st, max_mana=max_mana_st)
def test_property_17_regen_never_exceeds_max_and_adds_exact_amount(current, max_mana):
    """regen_mana caps at max_mana and adds exactly floor(max_mana * 0.1) below cap."""
    current = min(current, max_mana)
    result = regen_mana(current, max_mana)
    increment = math.floor(max_mana * 0.1)

    # Never exceeds the cap and never decreases.
    assert result <= max_mana
    assert result >= current

    if current + increment <= max_mana:
        # Below the cap: exact increment applied.
        assert result == current + increment
    else:
        # At/over the cap after increment: clamped to max_mana.
        assert result == max_mana


# ---------------------------------------------------------------------------
# Property 18: Cooldown Decrement
# **Validates: Requirements 13.1, 13.2, 13.3**
# ---------------------------------------------------------------------------
@given(
    cooldowns=st.dictionaries(
        keys=st.text(min_size=1, max_size=8),
        values=cooldown_st,
        max_size=6,
    )
)
def test_property_18_tick_decrements_by_one_floored_at_zero_no_mutation(cooldowns):
    """Each cooldown decremented by 1 (floored at 0); input dict is not mutated."""
    original = dict(cooldowns)

    result = tick_cooldowns(cooldowns)

    # Same keys preserved.
    assert set(result.keys()) == set(original.keys())

    # Each value decremented by exactly 1, never below 0.
    for key, old_value in original.items():
        assert result[key] == max(0, old_value - 1)
        assert result[key] >= 0

    # Input dict must not be mutated.
    assert cooldowns == original


# ---------------------------------------------------------------------------
# Property 14: Ability Damage Direct Application (DEFENCE ignored, shield absorbs)
# **Validates: Requirements 11.6, 28.4**
# ---------------------------------------------------------------------------
@given(
    enemy_hp=st.integers(min_value=0, max_value=300),
    enemy_shield=shield_st,
    dmg=dmg_st,
    enemy_max_hp=max_hp_st,
    ability_type=st.sampled_from([AbilityType.DMG, AbilityType.TRUE_DMG]),
)
def test_property_14_ability_ignores_defence_but_shield_absorbs(
    enemy_hp, enemy_shield, dmg, enemy_max_hp, ability_type
):
    """A DMG/TRUE_DMG ability ignores DEFENCE, but the enemy shield absorbs first.

    Because DEFENCE is ignored (def_=0), the raw damage equals the ability value
    (min 1). The enemy shield absorbs min(shield, dmg); HP only drops by the
    overflow max(0, dmg - shield).
    """
    enemy_hp = min(enemy_hp, enemy_max_hp)
    state = make_game_state(
        player_hp=50,
        player_max_hp=100,
        enemy_hp=enemy_hp,
        enemy_max_hp=enemy_max_hp,
        enemy_shield=enemy_shield,
    )
    ability = make_ability(ability_type, dmg)

    new_state = apply_ability_effect(ability, state)

    # DEFENCE ignored → raw = max(dmg, 1). Shield absorbs first.
    raw = max(dmg, 1)
    expected_absorbed = min(enemy_shield, raw)
    expected_to_hp = raw - expected_absorbed

    assert new_state.enemy.shield == enemy_shield - expected_absorbed
    assert new_state.enemy.hp == max(0, enemy_hp - expected_to_hp)
    assert 0 <= new_state.enemy.hp <= new_state.enemy.max_hp
    assert new_state.enemy.shield >= 0


@given(enemy_hp=st.integers(min_value=20, max_value=300), enemy_shield=st.integers(min_value=1, max_value=100))
def test_property_14_shield_fully_absorbs_when_ge_damage(enemy_hp, enemy_shield):
    """When enemy shield >= ability damage, HP is untouched and shield drops by dmg."""
    dmg = min(enemy_shield, 10)  # ensure dmg <= shield
    state = make_game_state(
        player_hp=50, player_max_hp=100, enemy_hp=enemy_hp, enemy_max_hp=300,
        enemy_shield=enemy_shield,
    )
    ability = make_ability(AbilityType.DMG, dmg)

    new_state = apply_ability_effect(ability, state)

    assert new_state.enemy.hp == enemy_hp  # no HP lost
    assert new_state.enemy.shield == enemy_shield - dmg


# ---------------------------------------------------------------------------
# Property 31: Enemy Shield Mechanics (via player ability path)
# **Validates: Requirements 11.8, 14.5, 15.5, 16.2**
# ---------------------------------------------------------------------------
@given(enemy_shield=shield_st, dmg=dmg_st, enemy_hp=st.integers(min_value=0, max_value=300))
def test_property_31_player_dmg_ability_absorbed_by_enemy_shield(
    enemy_shield, dmg, enemy_hp
):
    """A player DMG ability is absorbed by enemy.shield before HP (DEFENCE ignored)."""
    enemy_hp = min(enemy_hp, 300)
    state = make_game_state(
        player_hp=50, player_max_hp=100, enemy_hp=enemy_hp, enemy_max_hp=300,
        enemy_shield=enemy_shield,
    )
    ability = make_ability(AbilityType.DMG, dmg)

    new_state = apply_ability_effect(ability, state)

    raw = max(dmg, 1)
    absorbed = min(enemy_shield, raw)
    assert new_state.enemy.shield == enemy_shield - absorbed
    assert new_state.enemy.hp == max(0, enemy_hp - (raw - absorbed))


def test_property_31_sanity_shield_minus_x_and_hp_overflow():
    """Concrete sanity: shield S=5, dmg X=8 → shield 0, HP drops by 3."""
    state = make_game_state(
        player_hp=50, player_max_hp=100, enemy_hp=100, enemy_max_hp=100,
        enemy_shield=5,
    )
    ability = make_ability(AbilityType.DMG, 8)

    new_state = apply_ability_effect(ability, state)

    assert new_state.enemy.shield == 0
    assert new_state.enemy.hp == 97  # 100 - (8 - 5)


@pytest.mark.parametrize("unhandled_type", [AbilityType.STEAL, AbilityType.AOE, AbilityType.COUNTER])
def test_unhandled_ability_types_raise_valueerror(unhandled_type):
    """STEAL, AOE, and COUNTER are not yet implemented — must raise ValueError
    instead of silently doing nothing (BUG-4 regression prevention)."""
    state = make_game_state(
        player_hp=50, player_max_hp=100, enemy_hp=100, enemy_max_hp=100,
    )
    ability = make_ability(unhandled_type, 20)
    with pytest.raises(ValueError, match="Unimplemented ability type"):
        apply_ability_effect(ability, state)
