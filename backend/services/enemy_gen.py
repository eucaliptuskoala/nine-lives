"""
Enemy Gen Service — server-side enemy generation.

Pure, deterministic-where-possible enemy construction for the Battle_System.
Contains no I/O and no database access: stat scaling is fully deterministic,
while name/breed/ability selection uses `random`. Python port of the former
frontend `enemyGen.ts` (now deleted) — the backend is the sole authority for
enemy data.

Related: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9
"""

import math
import random

from models.schemas import AbilityType, Enemy, EnemyAbility

# ─── Constants ────────────────────────────────────────────────────────────────

# Placeholder avatar — enemies use procedural SVGs/real art in a future task.
# Kept consistent with the digitize router's placeholder convention.
PLACEHOLDER_AVATAR_URL = "https://placekitten.com/400/400"

# Server-side name/breed pools (ported from the former enemyGen.ts).
ENEMY_NAMES = [
    "Shadow",
    "Whiskers",
    "Midnight",
    "Tiger",
    "Smokey",
    "Misty",
    "Oreo",
    "Simba",
    "Luna",
    "Felix",
]

ENEMY_BREEDS = [
    "Black Shorthair",
    "Orange Tabby",
    "Calico",
    "Siamese",
    "Maine Coon",
    "Persian",
    "Bengal",
    "Ragdoll",
]

# ─── Ability pool ─────────────────────────────────────────────────────────────
# 12 abilities total: 8 regular + 4 special (is_special=True).
# Data reproduced verbatim from design.md's Enemy Gen Service table.
# `id` is assigned per-enemy via a stable slug of the name (see _slugify).
ABILITY_POOL: list[EnemyAbility] = [
    # ── 8 regular abilities ──
    EnemyAbility(id="scratch", name="Scratch", dmg=6, type=AbilityType.DMG, effect=None, mana_cost=10, cooldown=0, is_special=False, description="A quick scratch."),
    EnemyAbility(id="feral-swipe", name="Feral Swipe", dmg=9, type=AbilityType.DMG, effect=None, mana_cost=15, cooldown=1, is_special=False, description="A powerful swipe."),
    EnemyAbility(id="tail-whip", name="Tail Whip", dmg=5, type=AbilityType.DMG, effect=None, mana_cost=8, cooldown=0, is_special=False, description="Whacks with its tail."),
    EnemyAbility(id="dark-claw", name="Dark Claw", dmg=12, type=AbilityType.DMG, effect=None, mana_cost=20, cooldown=2, is_special=False, description="Claws glowing with dark energy."),
    EnemyAbility(id="vicious-bite", name="Vicious Bite", dmg=14, type=AbilityType.DMG, effect=None, mana_cost=25, cooldown=2, is_special=False, description="A devastating bite."),
    EnemyAbility(id="paw-slam", name="Paw Slam", dmg=7, type=AbilityType.DMG, effect=None, mana_cost=12, cooldown=1, is_special=False, description="Slams the ground with its paw."),
    EnemyAbility(id="healing-purr", name="Healing Purr", dmg=10, type=AbilityType.HEAL, effect=None, mana_cost=20, cooldown=2, is_special=False, description="Purrs to restore HP."),
    EnemyAbility(id="shadow-shield", name="Shadow Shield", dmg=0, type=AbilityType.SHIELD, effect=None, mana_cost=18, cooldown=3, is_special=False, description="Conjures a shadow barrier."),
    # ── 4 special abilities ──
    EnemyAbility(id="shadow-pounce", name="Shadow Pounce", dmg=18, type=AbilityType.DMG, effect=None, mana_cost=40, cooldown=3, is_special=True, description="Leaps from the shadows for massive damage."),
    EnemyAbility(id="fury-strikes", name="Fury Strikes", dmg=16, type=AbilityType.DMG, effect=None, mana_cost=35, cooldown=3, is_special=True, description="A flurry of relentless strikes."),
    EnemyAbility(id="regen-aura", name="Regen Aura", dmg=15, type=AbilityType.HEAL, effect=None, mana_cost=35, cooldown=3, is_special=True, description="Bathes in restorative energy."),
    EnemyAbility(id="tortoise-shell", name="Tortoise Shell", dmg=0, type=AbilityType.SHIELD, effect=None, mana_cost=30, cooldown=3, is_special=True, description="Hardens fur into an impenetrable shell."),
]


# ─── Stat scaling ─────────────────────────────────────────────────────────────

def compute_enemy_stats(round_num: int) -> dict:
    """Compute scaled enemy stats for a given round.

    Deterministic — the same round always yields the same stats.
    Formulas per Requirement 8.1–8.6:
        multiplier = 1 + (round - 1) * 0.3
        hp       = floor((20 + round * 5) * m)
        atk      = floor((8 + round * 2) * m)
        defence  = floor((6 + round * 1.5) * m)
        spd      = floor((7 + round * 2) * m)
        max_mana = 80 + round * 5   (not multiplied)
    """
    m = 1 + (round_num - 1) * 0.3
    return {
        "hp": math.floor((20 + round_num * 5) * m),
        "atk": math.floor((8 + round_num * 2) * m),
        "defence": math.floor((6 + round_num * 1.5) * m),
        "spd": math.floor((7 + round_num * 2) * m),
        "max_mana": 80 + round_num * 5,
    }


# ─── Ability selection ────────────────────────────────────────────────────────

def _pick_abilities() -> list[EnemyAbility]:
    """Select exactly 4 abilities: 1 special + 3 regular (Requirement 8.8).

    Shuffles the pool, then picks 1 random special and 3 random regular
    abilities. Returns fresh EnemyAbility copies so callers can't mutate the
    shared pool.
    """
    pool = list(ABILITY_POOL)
    random.shuffle(pool)

    specials = [a for a in pool if a.is_special]
    regulars = [a for a in pool if not a.is_special][:3]

    return [a.model_copy() for a in (regulars + specials[:1])]


# ─── Enemy construction ───────────────────────────────────────────────────────

def generate_enemy(round_num: int) -> Enemy:
    """Generate a round-scaled enemy.

    Stats are deterministic per round; name/breed/abilities are random.
    Starting mana is 60% of max mana (Requirement 8.7).

    Cooldowns: all abilities are initialized to 0 here. Per Requirement 8.9,
    the SPECIAL ability's cooldown is pre-set to its maximum by the Battle
    Router at round start (to prevent immediate ultimate usage) — this service
    intentionally leaves it at 0 so that responsibility stays with the router.
    """
    stats = compute_enemy_stats(round_num)
    abilities = _pick_abilities()

    # All cooldowns start at 0; the Battle Router pre-sets the special CD to max.
    ability_cooldowns = {a.id: 0 for a in abilities}

    return Enemy(
        name=random.choice(ENEMY_NAMES),
        breed=random.choice(ENEMY_BREEDS),
        hp=stats["hp"],
        max_hp=stats["hp"],
        atk=stats["atk"],
        defence=stats["defence"],
        spd=stats["spd"],
        mana=math.floor(stats["max_mana"] * 0.6),
        max_mana=stats["max_mana"],
        shield=0,
        ability_cooldowns=ability_cooldowns,
        abilities=abilities,
        avatar_url=PLACEHOLDER_AVATAR_URL,
    )
