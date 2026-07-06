"""
Tests for `services/generate_card.py` — Gemini card generation.

The Gemini REST call is fully mocked (monkeypatched `httpx.post`) so no network
or API quota is used. Includes:
  * a unit test of the happy path (parsed dict returned) and that `build_prompt`
    renders color ratios; and
  * property-based tests for the pure `validate_card` function.

Property 3 — Card Schema Completeness: a well-formed card (correct stat bounds,
    exactly 4 abilities with exactly 1 special, valid types/effects/classes)
    produces NO validation errors.
Property 4 — Card Stats Within Bounds: any card with an out-of-bounds stat or the
    wrong ability/special count is reported as invalid.

**Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 31.1, 31.2**
"""

import json

from hypothesis import given, strategies as st

import services.generate_card as gc
from services.generate_card import build_prompt, generate_card, validate_card


# ─── Fixtures / builders ──────────────────────────────────────────────────────


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


class _FakeResponse:
    def __init__(self, card):
        self._card = card

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(self._card)}]}}
            ]
        }


# ─── Unit tests (mocked Gemini) ───────────────────────────────────────────────


def test_generate_card_returns_parsed_dict(monkeypatch):
    """generate_card returns the parsed card dict from the mocked Gemini call."""
    monkeypatch.setattr(gc, "GEMINI_API_KEY", "test-key")

    card = _valid_card()

    def _fake_post(url, **kwargs):
        return _FakeResponse(card)

    monkeypatch.setattr(gc.httpx, "post", _fake_post)

    result = generate_card(
        cat_name="Sir Pounce",
        breed="Tabby",
        colors=[{"hex": "#C0A080", "ratio": 0.6}, {"hex": "#8B6F47", "ratio": 0.4}],
        personality="grumpy but loyal",
    )
    assert result == card


def test_generate_card_raises_without_api_key(monkeypatch):
    """No GEMINI_API_KEY -> ValueError before any network call."""
    monkeypatch.setattr(gc, "GEMINI_API_KEY", None)

    def _should_not_be_called(*a, **k):  # pragma: no cover
        raise AssertionError("httpx.post should not be called without an API key")

    monkeypatch.setattr(gc.httpx, "post", _should_not_be_called)

    try:
        generate_card("Sir Pounce", "Tabby", [{"hex": "#FFFFFF", "ratio": 1.0}])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_prompt_includes_color_ratios():
    """build_prompt renders each color's dominance as a percentage."""
    colors = [
        {"hex": "#C0A080", "ratio": 0.6},
        {"hex": "#8B6F47", "ratio": 0.25},
    ]
    prompt = build_prompt("Sir Pounce", "Tabby", colors)

    # Ratio must appear in the prompt text.
    assert "%" in prompt
    assert "#C0A080 (60%)" in prompt
    assert "#8B6F47 (25%)" in prompt


def test_build_prompt_handles_empty_colors():
    """Empty color list still produces a prompt (no crash)."""
    prompt = build_prompt("Sir Pounce", "Tabby", [])
    assert "Fur colors" in prompt


# ─── Property 3: Card Schema Completeness ─────────────────────────────────────
# **Validates: Requirements 4.2-4.10, 31.1**


@given(
    max_hp=st.integers(min_value=30, max_value=200),
    dmg=st.integers(min_value=5, max_value=50),
    defence=st.integers(min_value=3, max_value=40),
    spd=st.integers(min_value=5, max_value=50),
    max_mana=st.integers(min_value=50, max_value=200),
    class_=st.sampled_from(["STRENGTH", "AGILITY", "INTELLIGENCE"]),
)
def test_property_3_valid_card_has_no_errors(max_hp, dmg, defence, spd, max_mana, class_):
    """A well-formed card within all bounds produces no validation errors."""
    card = _valid_card(
        max_hp=max_hp, dmg=dmg, defence=defence, spd=spd, max_mana=max_mana, class_=class_
    )
    # `class` is a reserved word, so patch it directly.
    card["class"] = class_
    assert validate_card(card) == []


# ─── Property 4: Card Stats Within Bounds ─────────────────────────────────────
# **Validates: Requirements 4.2-4.10, 31.2**


@given(bad_hp=st.integers(min_value=201, max_value=1000))
def test_property_4_out_of_bounds_max_hp_is_flagged(bad_hp):
    """max_hp above the allowed range is reported as an error."""
    card = _valid_card(max_hp=bad_hp)
    errors = validate_card(card)
    assert any("max_hp" in e for e in errors)


@given(bad_dmg=st.integers(min_value=-100, max_value=4))
def test_property_4_out_of_bounds_dmg_is_flagged(bad_dmg):
    """dmg below the allowed range is reported as an error."""
    card = _valid_card(dmg=bad_dmg)
    errors = validate_card(card)
    assert any("dmg out of bounds" in e for e in errors)


@given(n_abilities=st.integers(min_value=0, max_value=6).filter(lambda n: n != 4))
def test_property_4_wrong_ability_count_is_flagged(n_abilities):
    """A card without exactly 4 abilities is reported as invalid."""
    abilities = [_valid_ability(f"A{i}") for i in range(n_abilities)]
    card = _valid_card(abilities=abilities)
    errors = validate_card(card)
    assert any("abilities" in e for e in errors)


@given(n_specials=st.integers(min_value=0, max_value=4).filter(lambda n: n != 1))
def test_property_4_wrong_special_count_is_flagged(n_specials):
    """Exactly one special ability is required; anything else is flagged."""
    abilities = [
        _valid_ability(f"A{i}", is_special=(i < n_specials)) for i in range(4)
    ]
    card = _valid_card(abilities=abilities)
    errors = validate_card(card)
    assert any("special" in e for e in errors)
