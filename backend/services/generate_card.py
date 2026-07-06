"""
Card Generator — Gemini-powered cat card stat generation.

Calls Gemini 2.5 Flash (via the httpx REST API) with the breed, extracted fur
colors (each with a dominance ratio), and optional personality to produce
bounded stats, a class, lore, exactly 4 abilities (exactly 1 special), and an
image_prompt.

Colors are provided as a list of {"hex": str, "ratio": float} dicts (the output
of services/extract_colors.py) so the prompt can convey each color's dominance.

Note: `google-genai` is listed as an optional alternative client in the `ml`
extra, but this module intentionally uses the lightweight httpx REST call so the
card generator has no hard dependency on the heavy ML packages.

Related: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 31.1, 31.2
"""

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models"
    f"/{GEMINI_MODEL}:generateContent"
)
REQUEST_TIMEOUT = 45


def _format_colors(colors: list[dict]) -> str:
    """Render colors with their dominance ratios as prompt-friendly lines.

    E.g. `#C0A080 (60%)`, `#8B6F47 (25%)` — the ratio (as a percentage) MUST
    appear so the LLM understands each color's dominance.
    """
    lines = []
    for color in colors:
        hex_code = color.get("hex", "")
        ratio = color.get("ratio", 0.0)
        percent = round(float(ratio) * 100)
        lines.append(f"{hex_code} ({percent}%)")
    return ", ".join(lines) if lines else "unknown"


def build_prompt(
    cat_name: str,
    breed: str,
    colors: list[dict],
    personality: str | None = None,
) -> str:
    personality_clause = ""
    if personality:
        personality_clause = f"\nThe cat's personality: {personality}\n"

    colors_text = _format_colors(colors)

    return f"""You are a game designer for a cat-themed roguelike. Generate a playable character card.

Cat name: {cat_name}
Breed: {breed}
Fur colors (with their dominance, most to least prominent): {colors_text}
{personality_clause}
Return ONLY valid JSON with these exact fields:
- "name": string (the cat's name)
- "class": "STRENGTH" | "AGILITY" | "INTELLIGENCE"
- "max_hp": int (30-200)
- "dmg": int (5-50)
- "defence": int (3-40)
- "spd": int (5-50)
- "max_mana": int (50-200)
- "lore": string (1-2 sentences of flavour text)
- "image_prompt": string (a concise subject description for an image generation model — cat breed, colors, class, mood — NO art style instructions, just the subject)
- "abilities": array of exactly 4 objects, exactly 1 with is_special: true
  each: {{"name": str, "dmg": int, "type": "DMG" | "HEAL" | "SHIELD" | "STEAL" | "AOE" | "COUNTER" | "TRUE_DMG", "effect": null | "STUN" | "SILENCE" | "BLEED" | "BURN" | "BLIND" | "SLOW" | "TAUNT" | "REGEN", "cooldown": int (0-5), "mana_cost": int (0-100), "lore": str, "is_special": bool, "description": str}}"""


def validate_card(card: dict) -> list[str]:
    errors: list[str] = []

    if not (30 <= card.get("max_hp", 0) <= 200):
        errors.append(f"max_hp out of bounds: {card.get('max_hp')}")
    if not (5 <= card.get("dmg", 0) <= 50):
        errors.append(f"dmg out of bounds: {card.get('dmg')}")
    if not (3 <= card.get("defence", 0) <= 40):
        errors.append(f"defence out of bounds: {card.get('defence')}")
    if not (5 <= card.get("spd", 0) <= 50):
        errors.append(f"spd out of bounds: {card.get('spd')}")
    if not (50 <= card.get("max_mana", 0) <= 200):
        errors.append(f"max_mana out of bounds: {card.get('max_mana')}")

    abilities = card.get("abilities", [])
    if len(abilities) != 4:
        errors.append(f"Expected 4 abilities, got {len(abilities)}")
    else:
        specials = [a for a in abilities if a.get("is_special")]
        if len(specials) != 1:
            errors.append(f"Expected 1 special ability, got {len(specials)}")

    valid_types = {"DMG", "HEAL", "SHIELD", "STEAL", "AOE", "COUNTER", "TRUE_DMG"}
    valid_effects = {None, "STUN", "SILENCE", "BLEED", "BURN", "BLIND", "SLOW", "TAUNT", "REGEN"}

    for a in abilities:
        if a.get("type") not in valid_types:
            errors.append(f"Invalid ability type for '{a.get('name')}': {a.get('type')}")
        if a.get("effect") not in valid_effects:
            errors.append(f"Invalid effect for '{a.get('name')}': {a.get('effect')}")
        if not (0 <= a.get("mana_cost", -1) <= 100):
            errors.append(f"mana_cost out of bounds for '{a.get('name')}': {a.get('mana_cost')}")
        if not (0 <= a.get("cooldown", -1) <= 5):
            errors.append(f"cooldown out of bounds for '{a.get('name')}': {a.get('cooldown')}")

    valid_classes = {"STRENGTH", "AGILITY", "INTELLIGENCE"}
    if card.get("class") not in valid_classes:
        errors.append(f"Invalid class: {card.get('class')}")

    return errors


def generate_card(
    cat_name: str,
    breed: str,
    colors: list[dict],
    personality: str | None = None,
) -> dict:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")

    prompt = build_prompt(cat_name, breed, colors, personality)

    response = httpx.post(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.7,
            },
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    card = json.loads(text)

    errors = validate_card(card)
    if errors:
        raise ValueError(f"Card validation failed: {errors}")

    return card
