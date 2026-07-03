"""
Tests for round progression in `services/battle_engine.py` (Task 9.4).

Focus: when the enemy is defeated (`enemy.hp == 0`), `resolve_round_progression`
advances the round, generates a new round-scaled enemy, and PRE-SETS that new
enemy's SPECIAL ability cooldown to its max while regular abilities remain at 0
(Requirement 8.9 — prevents an immediate first-turn ultimate from a fresh enemy).

Player-side HP / mana / cooldowns must be preserved across the progression
(Requirement 19.4) and the phase reset to PLAYER_TURN (Requirement 19.5).

Because `generate_enemy` picks abilities randomly, the cooldown assertions are
repeated across many generated enemies to exercise the full ability pool.
"""

from models.schemas import Enemy, EnemyAbility, GameState, Phase
from services.battle_engine import resolve_round_progression


def _defeated_enemy() -> Enemy:
    """A minimal defeated enemy (hp == 0) to trigger round progression."""
    scratch = EnemyAbility(
        id="scratch",
        name="Scratch",
        dmg=6,
        type="DMG",
        effect=None,
        mana_cost=10,
        cooldown=0,
        is_special=False,
        description="A quick scratch.",
    )
    return Enemy(
        name="Fallen",
        breed="Alley",
        hp=0,
        max_hp=30,
        atk=10,
        defence=6,
        spd=7,
        mana=40,
        max_mana=80,
        shield=0,
        ability_cooldowns={"scratch": 0},
        abilities=[scratch],
        avatar_url="http://example.com/enemy.png",
    )


def _state_with_defeated_enemy() -> GameState:
    return GameState(
        player_hp=42,
        player_max_hp=60,
        player_mana=15,
        player_max_mana=90,
        player_is_defending=False,
        player_shield=7,
        lives_remaining=5,
        player_ability_cooldowns={"claw": 0, "ultimate": 2},
        phase=Phase.PLAYER_TURN,
        current_round=1,
        enemy=_defeated_enemy(),
        events=None,
    )


def test_round_progression_presets_new_enemy_special_cooldown_to_max():
    """A mid-run round-progression enemy has its SPECIAL CD at max, regulars at 0.

    Validates: Requirements 8.9, 19.
    """
    cat = None  # resolve_round_progression does not use the cat for maxes here.

    # Repeat to cover the randomised ability selection in generate_enemy.
    for _ in range(50):
        state = _state_with_defeated_enemy()
        new_state = resolve_round_progression(state, cat)

        enemy = new_state.enemy
        specials = [a for a in enemy.abilities if a.is_special]

        # Exactly one special ability, pre-set to its own max cooldown (Req 8.9).
        assert len(specials) == 1
        special = specials[0]
        assert enemy.ability_cooldowns[special.id] == special.cooldown
        assert special.cooldown > 0  # sanity: specials in the pool have a real CD

        # Every regular ability starts off cooldown.
        for ability in enemy.abilities:
            if not ability.is_special:
                assert enemy.ability_cooldowns[ability.id] == 0


def test_round_progression_advances_round_and_preserves_player_state():
    """Round increments, phase resets, and player HP/mana/cooldowns are preserved.

    Validates: Requirements 19.2, 19.4, 19.5.
    """
    state = _state_with_defeated_enemy()
    new_state = resolve_round_progression(state, None)

    # Round advanced and phase reset to the player's turn.
    assert new_state.current_round == state.current_round + 1
    assert new_state.phase == Phase.PLAYER_TURN

    # Player-side state carried over untouched (Req 19.4).
    assert new_state.player_hp == state.player_hp
    assert new_state.player_mana == state.player_mana
    assert new_state.player_shield == state.player_shield
    assert new_state.lives_remaining == state.lives_remaining
    assert new_state.player_ability_cooldowns == state.player_ability_cooldowns

    # A brand-new enemy was generated (defeated one replaced, full HP).
    assert new_state.enemy.hp == new_state.enemy.max_hp
    assert new_state.enemy.hp > 0


def test_round_progression_noop_when_enemy_alive():
    """No progression occurs while the enemy still has HP (guard clause)."""
    state = _state_with_defeated_enemy()
    state.enemy.hp = 10  # enemy alive

    new_state = resolve_round_progression(state, None)

    assert new_state is state  # unchanged input returned
    assert new_state.current_round == state.current_round
