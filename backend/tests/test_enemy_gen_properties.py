"""
Property-based tests for `services.enemy_gen`.

Covers two correctness properties from design.md:

- Property 6 — Enemy Stat Scaling Formula (Requirements 8.1–8.6):
    Enemy stats are computed with the exact scaling formulas; recomputed
    independently here and asserted equal. Also checks monotonic
    non-decreasing scaling across rounds.

- Property 7 — Enemy Structure Invariant (Requirement 8.8):
    Every generated enemy has exactly 4 abilities, exactly 1 special,
    starting mana == floor(max_mana * 0.6), and its `ability_cooldowns`
    keys correspond to its ability ids.

`generate_enemy` uses `random` internally, so it is exercised across many
rounds/examples to stress the structural invariants.
"""

import math

from hypothesis import given, strategies as st

from services.enemy_gen import ABILITY_POOL, compute_enemy_stats, generate_enemy


# ─── Property 6: Enemy Stat Scaling Formula ──────────────────────────────────

@given(round_num=st.integers(min_value=1, max_value=20))
def test_compute_enemy_stats_matches_exact_formulas(round_num):
    """compute_enemy_stats matches the exact scaling formulas.

    **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**
    """
    m = 1 + (round_num - 1) * 0.3
    expected = {
        "hp": math.floor((20 + round_num * 5) * m),
        "atk": math.floor((8 + round_num * 2) * m),
        "defence": math.floor((6 + round_num * 1.5) * m),
        "spd": math.floor((7 + round_num * 2) * m),
        "max_mana": 80 + round_num * 5,
    }

    assert compute_enemy_stats(round_num) == expected


@given(round_num=st.integers(min_value=1, max_value=19))
def test_stats_are_monotonically_non_decreasing(round_num):
    """Stats never decrease as the round number increases.

    **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**
    """
    current = compute_enemy_stats(round_num)
    nxt = compute_enemy_stats(round_num + 1)

    for key in ("hp", "atk", "defence", "spd", "max_mana"):
        assert nxt[key] >= current[key], f"{key} decreased from round {round_num}"


# ─── Property 7: Enemy Structure Invariant ───────────────────────────────────

@given(round_num=st.integers(min_value=1, max_value=20))
def test_generated_enemy_structure_invariant(round_num):
    """Every generated enemy has a valid ability/mana/cooldown structure.

    **Validates: Requirements 8.7, 8.8**
    """
    enemy = generate_enemy(round_num)

    # Exactly 4 abilities, exactly 1 special.
    assert len(enemy.abilities) == 4
    specials = [a for a in enemy.abilities if a.is_special]
    assert len(specials) == 1

    # Starting mana is exactly 60% of max mana (floored).
    assert enemy.mana == math.floor(enemy.max_mana * 0.6)

    # Cooldown keys correspond exactly to the enemy's ability ids.
    ability_ids = {a.id for a in enemy.abilities}
    assert set(enemy.ability_cooldowns.keys()) == ability_ids

    # HP is initialized to full.
    assert enemy.hp == enemy.max_hp

    # All chosen abilities come from the pool.
    pool_ids = {a.id for a in ABILITY_POOL}
    assert ability_ids <= pool_ids
