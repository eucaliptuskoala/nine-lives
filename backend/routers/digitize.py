"""
Digitize Router — /api/digitize

Accepts a cat photo upload plus metadata, generates random stats (mock ML pipeline),
persists the cat and abilities to Supabase, and returns a complete CatResponse.

This is a MOCK implementation. The real ML pipeline (HuggingFace breed classification,
color extraction, Gemini avatar generation, Claude lore) will replace the random stat
generation and placeholder avatar in a future task.

Related: Requirements 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 26.1, 26.2, 26.3, 26.4
"""

import random
import time
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from dotenv import load_dotenv

from models.schemas import (
    Ability,
    AbilityType,
    CatResponse,
    CatStatus,
    Class,
    Effect,
)
from services.supabase_client import get_supabase_client

load_dotenv()

router = APIRouter(prefix="/digitize", tags=["digitize"])

# ─── Constants ────────────────────────────────────────────────────────────────

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

CAT_BREEDS = [
    "Siamese",
    "Persian",
    "Maine Coon",
    "Tabby",
    "Bengal",
    "Ragdoll",
    "British Shorthair",
    "Sphynx",
    "Norwegian Forest",
    "Domestic Shorthair",
]

BUCKET_NAME = "cat-images"

# Placeholder avatar — replaced by real Gemini-generated image in full pipeline
PLACEHOLDER_AVATAR_URL = "https://placekitten.com/400/400"

# ─── Ability name pools per type ─────────────────────────────────────────────

ABILITY_POOL = {
    AbilityType.DMG: [
        ("Scratch Frenzy", "Unleash a rapid flurry of razor-sharp claws."),
        ("Pounce", "Leap at the enemy with devastating force."),
        ("Fang Strike", "Sink fangs deep into the opponent's neck."),
    ],
    AbilityType.HEAL: [
        ("Catnap Restore", "A brief nap mysteriously restores vitality."),
        ("Purr Mend", "Soothing vibrations knit wounds closed."),
    ],
    AbilityType.SHIELD: [
        ("Fur Barrier", "Dense fur hardens into a protective shell."),
        ("Hiss Ward", "A fearsome hiss keeps harm at bay."),
    ],
    AbilityType.STEAL: [
        ("Pickpocket Paw", "Swipe mana from the enemy mid-battle."),
        ("Energy Drain", "Leech life force from the foe."),
    ],
    AbilityType.AOE: [
        ("Hairball Barrage", "Volley of hairballs hits all enemies."),
        ("Sonic Yowl", "Ear-splitting shriek damages all foes."),
    ],
    AbilityType.COUNTER: [
        ("Reflexive Swipe", "Counter-attack triggers on any incoming hit."),
        ("Spring Back", "Every blow absorbed is returned twofold."),
    ],
    AbilityType.TRUE_DMG: [
        ("Nine Lives Curse", "Bypasses all defences — pure feline wrath."),
        ("Soul Scratch", "Damage that pierces armour and spirit alike."),
    ],
}

SPECIAL_ABILITY_POOL = [
    (
        AbilityType.TRUE_DMG,
        "Final Meow",
        "The last resort of a cat with nothing left to lose.",
        "An apocalyptic strike that ignores all protections.",
        Effect.STUN,
    ),
    (
        AbilityType.AOE,
        "Furpocalypse",
        "A storm of fur and fury engulfs every enemy.",
        "Deals AOE damage and leaves all targets blinded.",
        Effect.BLIND,
    ),
    (
        AbilityType.HEAL,
        "Rebirth Purr",
        "Channels the magic of nine lives into a single healing surge.",
        "Restores a significant portion of HP and cleanses debuffs.",
        None,
    ),
]

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _content_type_to_ext(content_type: str) -> str:
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]


def _generate_lore(name: str, breed: str, class_: Class) -> str:
    class_desc = {
        Class.STRENGTH: "a powerhouse warrior feared across the land",
        Class.AGILITY: "a nimble shadow that strikes before you blink",
        Class.INTELLIGENCE: "a cunning tactician who bends battles to their will",
    }[class_]
    return (
        f"{name} is a {breed} — {class_desc}. "
        f"Born under an unlucky moon yet gifted with nine lives, "
        f"this cat's legend grows with every victory."
    )


def _pick_ability(type_: AbilityType) -> tuple[str, str]:
    """Return (name, description) for a regular ability of the given type."""
    pool = ABILITY_POOL.get(type_)
    if not pool:
        # Fallback: DMG
        pool = ABILITY_POOL[AbilityType.DMG]
    return random.choice(pool)


def _generate_abilities(cat_id: str) -> list[dict]:
    """Generate 3 regular + 1 special ability dicts ready for DB insert."""
    abilities: list[dict] = []

    regular_types = random.sample(list(AbilityType), k=min(3, len(AbilityType)))
    for ability_type in regular_types:
        name, description = _pick_ability(ability_type)
        abilities.append(
            {
                "creature_id": cat_id,
                "name": name,
                "dmg": random.randint(0, 30),
                "type": ability_type.value,
                "effect": random.choice([e.value for e in Effect] + [None]),
                "cooldown": random.randint(0, 5),
                "mana_cost": random.randint(0, 100),
                "lore": f"A technique mastered through countless battles.",
                "is_special": False,
                "description": description,
            }
        )

    # Special ability
    special = random.choice(SPECIAL_ABILITY_POOL)
    s_type, s_name, s_lore, s_desc, s_effect = special
    abilities.append(
        {
            "creature_id": cat_id,
            "name": s_name,
            "dmg": random.randint(15, 30),
            "type": s_type.value,
            "effect": s_effect.value if s_effect else None,
            "cooldown": random.randint(3, 5),
            "mana_cost": random.randint(50, 100),
            "lore": s_lore,
            "is_special": True,
            "description": s_desc,
        }
    )

    return abilities


def _db_row_to_ability(row: dict) -> Ability:
    return Ability(
        id=str(row["id"]),
        creature_id=str(row["creature_id"]),
        name=row["name"],
        dmg=row["dmg"],
        type=AbilityType(row["type"]),
        effect=Effect(row["effect"]) if row.get("effect") else None,
        cooldown=row["cooldown"],
        mana_cost=row["mana_cost"],
        lore=row["lore"],
        is_special=row["is_special"],
        description=row["description"],
    )


# ─── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("", response_model=CatResponse)
async def digitize_cat(
    file: UploadFile = File(...),
    game_run_id: str = Form(...),
    user_id: str = Form(...),
    cat_name: str = Form(...),
) -> CatResponse:
    """
    Digitize a cat photo into a game card.

    Validates the uploaded image, generates random stats (mock pipeline),
    persists the cat + abilities to Supabase, and links the game run.
    """
    # ── 1. Validate file type ────────────────────────────────────────────────
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}'. Allowed: JPEG, PNG, WebP.",
        )

    # ── 2. Read & validate file size ─────────────────────────────────────────
    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        size_mb = len(image_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed size is 10 MB.",
        )

    # ── 3. Upload source image to Supabase Storage ───────────────────────────
    supabase = get_supabase_client()

    ext = _content_type_to_ext(content_type)
    timestamp = int(time.time() * 1000)
    storage_path = f"{user_id}/source-{timestamp}.{ext}"

    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            storage_path,
            image_bytes,
            file_options={
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "false",
            },
        )
        source_image_url = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {exc}")

    # ── 4. Generate random stats ─────────────────────────────────────────────
    max_hp = random.randint(30, 200)
    dmg = random.randint(5, 50)
    defence = random.randint(3, 40)
    spd = random.randint(5, 50)
    max_mana = random.randint(50, 200)
    cat_class = random.choice(list(Class))
    breed = random.choice(CAT_BREEDS)
    lore = _generate_lore(cat_name, breed, cat_class)

    # ── 5. Insert cat record ─────────────────────────────────────────────────
    cat_data = {
        "user_id": user_id,
        "name": cat_name,
        "breed": breed,
        "class": cat_class.value,
        "current_hp": max_hp,
        "max_hp": max_hp,
        "dmg": dmg,
        "def": defence,
        "spd": spd,
        "mana": max_mana,
        "max_mana": max_mana,
        "lore": lore,
        "avatar_url": PLACEHOLDER_AVATAR_URL,
        "lives_remaining": 9,
        "source_image_url": source_image_url,
        "status": CatStatus.ALIVE.value,
        "wins": 0,
    }

    try:
        cat_result = supabase.table("cat").insert(cat_data).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create cat record: {exc}")

    if not cat_result.data:
        raise HTTPException(status_code=500, detail="Cat insert returned no data.")

    cat_row = cat_result.data[0]
    cat_id = str(cat_row["id"])

    # ── 6. Insert abilities ──────────────────────────────────────────────────
    abilities_data = _generate_abilities(cat_id)

    try:
        abilities_result = supabase.table("ability").insert(abilities_data).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create abilities: {exc}")

    if not abilities_result.data:
        raise HTTPException(status_code=500, detail="Abilities insert returned no data.")

    # ── 7. Update game_run record ────────────────────────────────────────────
    try:
        supabase.table("game_run").update(
            {"cat_id": cat_id, "status": "IN_PROGRESS"}
        ).eq("id", game_run_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update game run: {exc}")

    # ── 8. Build and return CatResponse ─────────────────────────────────────
    abilities = [_db_row_to_ability(row) for row in abilities_result.data]

    return CatResponse(
        id=cat_id,
        user_id=str(cat_row["user_id"]),
        name=cat_row["name"],
        breed=cat_row["breed"],
        class_=Class(cat_row["class"]),
        current_hp=cat_row["current_hp"],
        max_hp=cat_row["max_hp"],
        dmg=cat_row["dmg"],
        defence=cat_row["def"],
        spd=cat_row["spd"],
        mana=cat_row["mana"],
        max_mana=cat_row["max_mana"],
        lore=cat_row["lore"],
        avatar_url=cat_row["avatar_url"],
        lives_remaining=cat_row["lives_remaining"],
        source_image_url=cat_row["source_image_url"],
        status=CatStatus(cat_row["status"]),
        wins=cat_row["wins"],
        death_date=cat_row.get("death_date"),
        personal_note=cat_row.get("personal_note"),
        created_at=cat_row["created_at"],
        abilities=abilities,
    )
