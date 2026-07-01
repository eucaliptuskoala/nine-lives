"""
Tests for the symmetric enemy shield mechanic (Task 4.10 / Property 31).

These exercise the higher-level turn orchestration in `services/battle_engine.py`
where the enemy shield is read/written:

- A player basic attack is absorbed by `enemy.shield` before HP (Req 14.5-14.8, 16.2).
- An enemy SHIELD-type ability adds its value to `enemy.shield` (Req 15.5, 16).
- Symmetry: an enemy DMG ability against a shielded player is absorbed by
  `player_shield` before player HP (Req 14.1-14.4).

Property 31: Enemy Shield Mechanics
**Validates: Requirements 11.8, 14.5, 15.5, 16.2**
"""

import math

from hypothesis import given, strategies as st

from models.schemas import (
    Ability,
    AbilityType,
    Class,
    CreatureBase,
    Enemy,
    EnemyAbility,
    GameState,
    Phase,
)
from services.battle_engine import resolve_enemy_turn, resolve_player_action


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------
def make_enemy(
    *,
    hp: int = 100,
    max_hp: int = 100,
    atk: int = 10,
    defence: int = 0,
    shield: int = 0,
    mana: int = 0,
    max_mana: int = 100,
    abilities: list[EnemyAbility] | None = None,
    cooldowns: dict[str, int] | None = None,
) -> Enemy:
    abilities = abilities if abilities is not None else []
    cooldowns = cooldowns if cooldowns is not None else {a.id: 0 for a in abilities}
    return Enemy(
        name="Shadow",
        breed="Alley",
        hp=hp,
        max_hp=max_hp,
        atk=atk,
        defence=defence,
        spd=5,
        mana=mana,
        max_mana=max_mana,
        shield=shield,
        ability_cooldowns=cooldowns,
        abilities=abilities,
        avatar_url="http://example.com/enemy.png",
    )


def make_state(
    *,
    enemy: Enemy,
    player_hp: int = 100,
    player_max_hp: int = 100,
    player_shield: int = 0,
    player_is_defending: bool = False,
    phase: Phase = Phase.PLAYER_TURN,
) -> GameState:
    return GameState(
        player_hp=player_hp,
        player_max_hp=player_max_hp,
        player_mana=100,
        player_max_mana=100,
        player_is_defending=player_is_defending,
        player_shield=player_shield,
        lives_remaining=9,
        player_ability_cooldowns={},
        phase=phase,
        current_round=1,
        enemy=enemy,
        events=None,
    )


def make_cat(*, dmg: int = 20, defence: int = 5, abilities: list[Ability] | None = None) -> CreatureBase:
    return CreatureBase(
        name="Hero",
        breed="Tabby",
        class_=Class.STRENGTH,
        current_hp=100,
        max_hp=100,
        dmg=dmg,
        defence=defence,
        spd=5,
        mana=100,
        max_mana=100,
        lore="brave",
        avatar_url="http://example.com/cat.png",
        lives_remaining=9,
        abilities=abilities if abilities is not None else [],
    )


def make_enemy_ability(ability_type: AbilityType, dmg: int, *, id="e1", is_special=False) -> EnemyAbility:
    return EnemyAbility(
        id=id,
        name="Enemy Move",
        dmg=dmg,
        type=ability_type,
        effect=None,
        mana_cost=0,
        cooldown=2,
        is_special=is_special,
        description="test",
    )


# ---------------------------------------------------------------------------
# Player basic attack absorbed by enemy.shield
# ---------------------------------------------------------------------------
def test_player_attack_fully_absorbed_by_enemy_shield():
    """Player basic attack absorbed entirely by a large enemy shield → HP intact."""
    enemy = make_enemy(hp=100, shield=100, defence=0)
    cat = make_cat(dmg=20)
    state = make_state(enemy=enemy)

    new_state, _events = resolve_player_action(state, "attack", None, cat)

    # raw = max(20 - 0*0.5, 1) = 20; shield absorbs all 20.
    assert new_state.enemy.shield == 80
    assert new_state.enemy.hp == 100


def test_player_attack_overflows_enemy_shield_to_hp():
    """Player basic attack overflows a small enemy shield onto HP."""
    enemy = make_enemy(hp=100, shield=5, defence=0)
    cat = make_cat(dmg=20)
    state = make_state(enemy=enemy)

    new_state, _events = resolve_player_action(state, "attack", None, cat)

    # raw = 20; shield 5 absorbed; 15 to HP.
    assert new_state.enemy.shield == 0
    assert new_state.enemy.hp == 85


@given(
    enemy_shield=st.integers(min_value=0, max_value=100),
    cat_dmg=st.integers(min_value=5, max_value=50),
    enemy_defence=st.integers(min_value=0, max_value=20),
    enemy_hp=st.integers(min_value=0, max_value=300),
)
def test_property_31_player_attack_shield_priority(
    enemy_shield, cat_dmg, enemy_defence, enemy_hp
):
    """Player basic attack reduces enemy shield first, remainder to HP."""
    enemy = make_enemy(hp=enemy_hp, max_hp=300, shield=enemy_shield, defence=enemy_defence)
    cat = make_cat(dmg=cat_dmg)
    state = make_state(enemy=enemy)

    new_state, _events = resolve_player_action(state, "attack", None, cat)

    raw = max(cat_dmg - enemy_defence * 0.5, 1)
    absorbed = min(enemy_shield, raw)
    expected_to_hp = math.floor(raw - absorbed)

    assert new_state.enemy.shield == enemy_shield - absorbed
    assert new_state.enemy.hp == max(0, enemy_hp - expected_to_hp)
    assert 0 <= new_state.enemy.hp <= new_state.enemy.max_hp
    assert new_state.enemy.shield >= 0


# ---------------------------------------------------------------------------
# Enemy SHIELD ability adds to enemy.shield
# ---------------------------------------------------------------------------
@given(base_shield=st.integers(min_value=0, max_value=100), value=st.integers(min_value=0, max_value=50))
def test_property_31_enemy_shield_ability_adds_to_shield(base_shield, value):
    """An enemy SHIELD ability adds its value to enemy.shield (no HP/player change)."""
    shield_ability = make_enemy_ability(AbilityType.SHIELD, value, id="shield", is_special=True)
    enemy = make_enemy(shield=base_shield, mana=100, abilities=[shield_ability])
    state = make_state(enemy=enemy, phase=Phase.ENEMY_TURN, player_hp=80)

    new_state, events = resolve_enemy_turn(state, player_defence=0)

    assert new_state.enemy.shield == base_shield + value
    assert new_state.player_hp == 80  # player untouched
    assert any("shield" in e.lower() for e in events)


# ---------------------------------------------------------------------------
# Symmetry: enemy DMG ability absorbed by player_shield first
# ---------------------------------------------------------------------------
def test_enemy_dmg_ability_absorbed_by_player_shield():
    """An enemy DMG ability is absorbed by player_shield before player HP (symmetry)."""
    dmg_ability = make_enemy_ability(AbilityType.DMG, 12, id="claw", is_special=True)
    enemy = make_enemy(mana=100, abilities=[dmg_ability])
    state = make_state(enemy=enemy, phase=Phase.ENEMY_TURN, player_hp=100, player_shield=5)

    new_state, _events = resolve_enemy_turn(state, player_defence=999)

    # Ability ignores player defence (def_=0): raw=12; shield 5 absorbs; 7 to HP.
    assert new_state.player_shield == 0
    assert new_state.player_hp == 93


@given(
    player_shield=st.integers(min_value=0, max_value=100),
    ability_dmg=st.integers(min_value=0, max_value=60),
    player_hp=st.integers(min_value=0, max_value=300),
)
def test_property_31_symmetry_enemy_dmg_ability_player_shield(
    player_shield, ability_dmg, player_hp
):
    """Enemy DMG ability: player shield absorbs first, remainder to player HP."""
    dmg_ability = make_enemy_ability(AbilityType.DMG, ability_dmg, id="claw", is_special=True)
    enemy = make_enemy(mana=100, abilities=[dmg_ability])
    state = make_state(
        enemy=enemy, phase=Phase.ENEMY_TURN, player_hp=player_hp,
        player_max_hp=300, player_shield=player_shield,
    )

    new_state, _events = resolve_enemy_turn(state, player_defence=100)

    raw = max(ability_dmg, 1)  # defence ignored for abilities
    absorbed = min(player_shield, raw)
    expected_to_hp = math.floor(raw - absorbed)

    assert new_state.player_shield == player_shield - absorbed
    assert new_state.player_hp == max(0, player_hp - expected_to_hp)
