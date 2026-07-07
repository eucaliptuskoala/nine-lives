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
from services.generate_card import build_prompt, generate_card, sanitize_card, validate_card


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


# ─── BUG 2 fix — untrusted-data fencing, length caps, sanitize_card ──────────
# **Validates: Requirements 2.7, 2.8, 2.9, 3.3**


def test_build_prompt_fences_user_text():
    """cat_name, breed, and personality all appear strictly between the
    <untrusted_user_data> fence markers."""
    prompt = build_prompt(
        "Sir Pounce",
        "Maine Coon",
        [{"hex": "#C0A080", "ratio": 0.6}],
        personality="grumpy but loyal",
    )

    assert "<untrusted_user_data>" in prompt
    assert "</untrusted_user_data>" in prompt

    open_idx = prompt.index("<untrusted_user_data>")
    close_idx = prompt.index("</untrusted_user_data>")
    assert open_idx < close_idx

    name_idx = prompt.index("Sir Pounce")
    breed_idx = prompt.index("Maine Coon")
    personality_idx = prompt.index("grumpy but loyal")

    assert open_idx < name_idx < close_idx
    assert open_idx < breed_idx < close_idx
    assert open_idx < personality_idx < close_idx


def test_build_prompt_caps_cat_name_length():
    """A cat_name longer than CAT_NAME_MAX_LENGTH is truncated in the prompt."""
    oversized_name = "A" * (gc.CAT_NAME_MAX_LENGTH + 500)
    prompt = build_prompt(oversized_name, "Tabby", [{"hex": "#FFFFFF", "ratio": 1.0}])

    truncated_name = oversized_name[: gc.CAT_NAME_MAX_LENGTH]
    assert truncated_name in prompt
    assert oversized_name not in prompt


def test_build_prompt_caps_personality_length():
    """A personality longer than PERSONALITY_MAX_LENGTH is truncated in the prompt."""
    oversized_personality = "B" * (gc.PERSONALITY_MAX_LENGTH + 500)
    prompt = build_prompt(
        "Sir Pounce",
        "Tabby",
        [{"hex": "#FFFFFF", "ratio": 1.0}],
        personality=oversized_personality,
    )

    truncated_personality = oversized_personality[: gc.PERSONALITY_MAX_LENGTH]
    assert truncated_personality in prompt
    assert oversized_personality not in prompt


def test_sanitize_card_strips_control_chars_and_caps_length():
    """sanitize_card strips control chars and length-caps free-text fields,
    leaving numeric/structural fields untouched."""
    control_chars = "\x00\x01\x1f\x7f"

    oversized_name = control_chars + ("N" * (gc.NAME_MAX_LENGTH + 50))
    oversized_lore = control_chars + ("L" * (gc.LORE_MAX_LENGTH + 50))
    oversized_image_prompt = control_chars + ("I" * (gc.IMAGE_PROMPT_MAX_LENGTH + 50))
    oversized_ability_name = control_chars + ("Q" * (gc.ABILITY_NAME_MAX_LENGTH + 50))
    oversized_ability_description = control_chars + (
        "D" * (gc.ABILITY_DESCRIPTION_MAX_LENGTH + 50)
    )

    card = _valid_card(
        name=oversized_name,
        lore=oversized_lore,
        image_prompt=oversized_image_prompt,
        abilities=[
            _valid_ability(
                name=oversized_ability_name,
                description=oversized_ability_description,
                dmg=42,
                type="AOE",
                is_special=True,
            ),
        ],
    )

    result = sanitize_card(card)

    for control_char in control_chars:
        assert control_char not in result["name"]
        assert control_char not in result["lore"]
        assert control_char not in result["image_prompt"]
        assert control_char not in result["abilities"][0]["name"]
        assert control_char not in result["abilities"][0]["description"]

    assert len(result["name"]) == gc.NAME_MAX_LENGTH
    assert len(result["lore"]) == gc.LORE_MAX_LENGTH
    assert len(result["image_prompt"]) == gc.IMAGE_PROMPT_MAX_LENGTH
    assert len(result["abilities"][0]["name"]) == gc.ABILITY_NAME_MAX_LENGTH
    assert (
        len(result["abilities"][0]["description"])
        == gc.ABILITY_DESCRIPTION_MAX_LENGTH
    )

    # Numeric/structural fields must be unchanged.
    assert result["max_hp"] == card["max_hp"]
    assert result["dmg"] == card["dmg"]
    assert result["defence"] == card["defence"]
    assert result["spd"] == card["spd"]
    assert result["max_mana"] == card["max_mana"]
    assert result["class"] == card["class"]
    assert result["abilities"][0]["dmg"] == 42
    assert result["abilities"][0]["type"] == "AOE"
    assert result["abilities"][0]["is_special"] is True
    assert result["abilities"][0]["cooldown"] == card["abilities"][0]["cooldown"]
    assert result["abilities"][0]["mana_cost"] == card["abilities"][0]["mana_cost"]


def test_sanitize_card_does_not_mutate_input():
    """sanitize_card returns a new dict; the original card dict is unchanged."""
    original = _valid_card(
        name="\x00Sir Pounce",
        abilities=[_valid_ability(name="\x01Claw")],
    )
    # Deep-ish snapshot of the original values to compare against after the call.
    original_name = original["name"]
    original_ability_name = original["abilities"][0]["name"]

    sanitize_card(original)

    assert original["name"] == original_name
    assert original["abilities"][0]["name"] == original_ability_name
    assert original["name"] == "\x00Sir Pounce"
    assert original["abilities"][0]["name"] == "\x01Claw"


def test_generate_card_end_to_end_sanitizes_before_validate(monkeypatch):
    """generate_card wires sanitize_card in before validate_card: control-char
    polluted free text returned by the (mocked) Gemini call comes back clean."""
    monkeypatch.setattr(gc, "GEMINI_API_KEY", "test-key")

    polluted_card = _valid_card(
        name="\x00\x01Sir Pounce\x7f",
        lore="\x1fA brave\x00 and fluffy warrior.",
        image_prompt="\x01an orange tabby warrior cat\x7f",
        abilities=[
            _valid_ability("\x00Claw\x01"),
            _valid_ability("Bite"),
            _valid_ability("Pounce"),
            _valid_ability(
                "\x7fNine Fury",
                is_special=True,
                effect="STUN",
                description="\x00Unleash nine lives of fury\x01",
            ),
        ],
    )

    def _fake_post(url, **kwargs):
        return _FakeResponse(polluted_card)

    monkeypatch.setattr(gc.httpx, "post", _fake_post)

    result = generate_card(
        cat_name="Sir Pounce",
        breed="Tabby",
        colors=[{"hex": "#C0A080", "ratio": 0.6}],
        personality="grumpy but loyal",
    )

    control_chars = "\x00\x01\x1f\x7f"
    for control_char in control_chars:
        assert control_char not in result["name"]
        assert control_char not in result["lore"]
        assert control_char not in result["image_prompt"]
        for ability in result["abilities"]:
            assert control_char not in ability["name"]
            assert control_char not in ability["description"]

    assert len(result["name"]) <= gc.NAME_MAX_LENGTH
    assert len(result["lore"]) <= gc.LORE_MAX_LENGTH
    assert len(result["image_prompt"]) <= gc.IMAGE_PROMPT_MAX_LENGTH
    for ability in result["abilities"]:
        assert len(ability["name"]) <= gc.ABILITY_NAME_MAX_LENGTH
        assert len(ability["description"]) <= gc.ABILITY_DESCRIPTION_MAX_LENGTH

    # Result must still be a valid card (sanitize happens before validate).
    assert validate_card(result) == []
