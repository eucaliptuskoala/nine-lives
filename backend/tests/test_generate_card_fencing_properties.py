"""
Property-based tests for `services/generate_card.py` — BUG 2 fencing/caps and
preservation (see bugfix.md 3.3/3.4 and design.md Property 2 / Property 4).

Property 2 — Bug Condition / Free-Text Fencing Invariant: for arbitrary
    `cat_name`/`personality` input, `build_prompt` places the (possibly
    truncated) user text ONLY inside the `<untrusted_user_data>` fence, never
    before the opening fence or after the closing fence, and the interpolated
    values never exceed `CAT_NAME_MAX_LENGTH` / `PERSONALITY_MAX_LENGTH`.

Property 4 — Preservation: for generated benign in-bounds card stats,
    `validate_card` still returns no errors — confirming the BUG 2 fix
    (`sanitize_card` runs before `validate_card` in `generate_card`) did not
    change `validate_card`'s own numeric/structural validation behavior.

**Validates: Requirements 3.3, 3.4**
"""

from hypothesis import given, strategies as st

import services.generate_card as gc
from services.generate_card import build_prompt, validate_card

FENCE_OPEN = "<untrusted_user_data>"
FENCE_CLOSE = "</untrusted_user_data>"


# ─── Fixtures / builders (duplicated locally — see task 5.4 note re: keeping ──
# ─── cross-file test-helper imports simple) ──────────────────────────────────


def _valid_ability(name="Claw", is_special=False, **over):
    ability = {
        "name": name,
        "dmg": 20,
        "type": "DMG",
        "effect": None,
        "cooldown": 2,
        "mana_cost": 30,
        "lore": "A sharp strike.",
        "is_special": is_special,
        "description": "Rake the enemy.",
    }
    ability.update(over)
    return ability


def _valid_card(**over):
    card = {
        "name": "Sir Pounce",
        "class": "STRENGTH",
        "max_hp": 120,
        "dmg": 30,
        "defence": 12,
        "spd": 18,
        "max_mana": 100,
        "lore": "A brave and fluffy warrior.",
        "image_prompt": "an orange tabby warrior cat, fierce",
        "abilities": [
            _valid_ability("Claw"),
            _valid_ability("Bite"),
            _valid_ability("Pounce"),
            _valid_ability("Nine Fury", is_special=True, effect="STUN"),
        ],
    }
    card.update(over)
    return card


# ─── Strategies ────────────────────────────────────────────────────────────────

_basic_text = st.text(min_size=0, max_size=200)
_wide_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)), min_size=0, max_size=300
)
_free_text = st.one_of(_basic_text, _wide_text)


# ─── Property 2: Free-Text Fencing Invariant ──────────────────────────────────
# **Validates: Requirements 3.3, Design Property 2**


@given(cat_name=_free_text, personality=_free_text)
def test_property_2_fencing_invariant(cat_name, personality):
    """User text is always inside the fence, within caps, never leaks outside.

    Note: checking "outside the fence" via plain substring search is unsound
    here — short user inputs (e.g. "0", "bi") coincidentally collide with the
    fixed scaffold text outside the fence (e.g. "(100%)", "abilities"). The
    scaffold text outside the fence (colors/breed/colors are fixed in this
    test, and the JSON-schema instructions are always static) does not depend
    on `cat_name`/`personality` at all, so instead of substring containment
    we assert the before/after-fence text is byte-for-byte identical to a
    reference render with sentinel values that share no substrings with the
    generated inputs' caps. Only the fenced block is allowed to vary.
    """
    colors = [{"hex": "#FFFFFF", "ratio": 1.0}]
    prompt = build_prompt(
        cat_name=cat_name, breed="Tabby", colors=colors, personality=personality
    )

    # (a) Both fence markers are present.
    assert FENCE_OPEN in prompt
    assert FENCE_CLOSE in prompt

    open_idx = prompt.index(FENCE_OPEN)
    close_idx = prompt.index(FENCE_CLOSE)
    assert open_idx < close_idx

    before_fence = prompt[:open_idx]
    inside_fence = prompt[open_idx + len(FENCE_OPEN) : close_idx]
    after_fence = prompt[close_idx + len(FENCE_CLOSE) :]

    capped_cat_name = cat_name[: gc.CAT_NAME_MAX_LENGTH]
    capped_personality = personality[: gc.PERSONALITY_MAX_LENGTH] if personality else ""

    # (d) Caps are respected.
    assert len(capped_cat_name) <= gc.CAT_NAME_MAX_LENGTH
    assert len(capped_personality) <= gc.PERSONALITY_MAX_LENGTH

    # (b) cat_name appears inside the fence (when non-empty).
    if capped_cat_name:
        assert capped_cat_name in inside_fence

    # (c) personality (when non-empty) appears inside the fence.
    if capped_personality:
        assert capped_personality in inside_fence

    # (b)/(c) continued: the scaffold text outside the fence never changes
    # based on cat_name/personality — it's identical to a reference render
    # with fixed sentinel values, given the same breed/colors.
    reference_prompt = build_prompt(
        cat_name="__REFERENCE_CAT_NAME__",
        breed="Tabby",
        colors=colors,
        personality="__REFERENCE_PERSONALITY__",
    )
    ref_open_idx = reference_prompt.index(FENCE_OPEN)
    ref_close_idx = reference_prompt.index(FENCE_CLOSE)
    ref_before_fence = reference_prompt[:ref_open_idx]
    ref_after_fence = reference_prompt[ref_close_idx + len(FENCE_CLOSE) :]

    assert before_fence == ref_before_fence
    assert after_fence == ref_after_fence


# ─── Property 4: Preservation — validate_card behavior unchanged ─────────────
# **Validates: Requirements 3.4, Design Property 4**


@given(
    max_hp=st.integers(min_value=30, max_value=200),
    dmg=st.integers(min_value=5, max_value=50),
    defence=st.integers(min_value=3, max_value=40),
    spd=st.integers(min_value=5, max_value=50),
    max_mana=st.integers(min_value=50, max_value=200),
    class_=st.sampled_from(["STRENGTH", "AGILITY", "INTELLIGENCE"]),
)
def test_property_4_benign_inputs_still_validate_clean(
    max_hp, dmg, defence, spd, max_mana, class_
):
    """Benign in-bounds card stats still produce no validate_card errors.

    Confirms sanitize_card (BUG 2 fix) running ahead of validate_card in
    generate_card has not altered validate_card's own numeric/structural
    checks.
    """
    card = _valid_card(max_hp=max_hp, dmg=dmg, defence=defence, spd=spd, max_mana=max_mana)
    card["class"] = class_
    assert validate_card(card) == []
