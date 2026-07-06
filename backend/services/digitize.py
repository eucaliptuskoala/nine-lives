"""
Digitize Orchestrator — `services/digitize.py`

Orchestrates the full backend digitization pipeline, replacing the previous
random-stat / empty-colors mock. Given the raw image bytes and cat metadata it:

1. Uploads the source image to Supabase storage (`cat-images` bucket) and gets
   its public URL.
2. Classifies the cat breed via the local ViT classifier (`classify_breed`).
3. Extracts the dominant fur colors via YOLO segmentation + KMeans
   (`extract_colors`).
4. Generates the card (stats, class, lore, abilities, image_prompt) via Gemini
   (`generate_card`).
5. Generates a pixel-art avatar via FLUX.1-schnell (`generate_avatar`).
6. Persists the cat + its 4 abilities and links the `game_run`.
7. Returns the complete `CatResponse`.

The ML service functions are imported at module level — that is safe because each
of them imports its heavy dependencies (`transformers`, `ultralytics`, `cv2`,
`sklearn`, `huggingface_hub`) lazily inside the functions that need them. This
module never triggers a heavy import merely by being imported.

Pipeline failures are surfaced as typed exceptions (`DigitizeStorageError`,
`DigitizeGenerationError`, `DigitizePersistenceError`) so the thin HTTP layer in
`routers/digitize.py` can map them to the appropriate status codes (500 for
storage/DB, 502 for generation) while keeping the orchestrator I/O-framework
agnostic.

Related: Requirements 1.9, 2, 3, 4, 5, 6
"""

import time
from typing import Optional

from services.supabase_client import get_supabase_client
from services.classify import classify_breed
from services.extract_colors import extract_colors
from services.generate_card import generate_card
from services.generate_avatar import generate_avatar
from models.schemas import (
    Ability,
    AbilityType,
    CatResponse,
    CatStatus,
    Class,
    Effect,
)

BUCKET_NAME = "cat-images"


# ─── Typed pipeline exceptions ────────────────────────────────────────────────


class DigitizeError(Exception):
    """Base class for digitization pipeline failures."""


class DigitizeStorageError(DigitizeError):
    """Raised when uploading the source image to storage fails (→ HTTP 500)."""


class DigitizeGenerationError(DigitizeError):
    """Raised when card or avatar generation fails (→ HTTP 502)."""


class DigitizePersistenceError(DigitizeError):
    """Raised when persisting the cat/abilities/game_run fails (→ HTTP 500)."""


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _content_type_to_ext(content_type: str) -> str:
    """Map an allowed image content type to its file extension."""
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]


def _db_row_to_ability(row: dict) -> Ability:
    """Convert an `ability` table row into an `Ability` model."""
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


# ─── Orchestrator ─────────────────────────────────────────────────────────────


async def digitize(
    image_bytes: bytes,
    content_type: str,
    cat_name: str,
    game_run_id: str,
    user_id: str,
    personality: Optional[str] = None,
) -> CatResponse:
    """Run the full digitization pipeline and return the created cat.

    Args:
        image_bytes: Raw bytes of the uploaded photo.
        content_type: The upload's MIME type (already validated by the router).
        cat_name: The user-supplied cat name.
        game_run_id: The DIGITIZING game run to link the new cat to.
        user_id: The owning user's id.
        personality: Optional free-text personality hint threaded into card gen.

    Returns:
        The fully populated `CatResponse` for the newly digitized cat.

    Raises:
        DigitizeStorageError: source image upload failed.
        DigitizeGenerationError: card or avatar generation failed.
        DigitizePersistenceError: persisting the cat / abilities / game_run failed.
    """
    supabase = get_supabase_client()

    # ── 1. Upload source image to Supabase Storage ───────────────────────────
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
        source_image_url = supabase.storage.from_(BUCKET_NAME).get_public_url(
            storage_path
        )
    except Exception as exc:
        raise DigitizeStorageError(f"Image upload failed: {exc}") from exc

    # ── 2. Breed classification (real, local ViT) ────────────────────────────
    breed = classify_breed(image_bytes)

    # ── 3. Colour extraction (real, YOLO + KMeans) ───────────────────────────
    # colors is a list[dict] of {"hex": str, "ratio": float}.
    colors = extract_colors(image_bytes)

    # ── 4. Generate card stats via Gemini ────────────────────────────────────
    try:
        card = generate_card(
            cat_name=cat_name,
            breed=breed,
            colors=colors,
            personality=personality,
        )
    except Exception as exc:
        raise DigitizeGenerationError(f"Card generation failed: {exc}") from exc

    # ── 5. Generate avatar via FLUX.1-schnell (returns a public storage URL) ──
    try:
        avatar_url = generate_avatar(card["image_prompt"])
    except Exception as exc:
        raise DigitizeGenerationError(f"Avatar generation failed: {exc}") from exc

    # ── 6. Insert cat record ─────────────────────────────────────────────────
    cat_data = {
        "user_id": user_id,
        "name": card["name"],
        "breed": breed,
        "class": card["class"],
        "current_hp": card["max_hp"],
        "max_hp": card["max_hp"],
        "dmg": card["dmg"],
        "def": card["defence"],
        "spd": card["spd"],
        "mana": card["max_mana"],
        "max_mana": card["max_mana"],
        "lore": card["lore"],
        "avatar_url": avatar_url,
        "lives_remaining": 9,
        "source_image_url": source_image_url,
        "status": CatStatus.ALIVE.value,
        "wins": 0,
        "personality": personality,
    }

    try:
        cat_result = supabase.table("cat").insert(cat_data).execute()
    except Exception as exc:
        raise DigitizePersistenceError(
            f"Failed to create cat record: {exc}"
        ) from exc

    if not cat_result.data:
        raise DigitizePersistenceError("Cat insert returned no data.")

    cat_row = cat_result.data[0]
    cat_id = str(cat_row["id"])

    # ── 7. Insert abilities ──────────────────────────────────────────────────
    abilities_data = [
        {
            "creature_id": cat_id,
            "name": a["name"],
            "dmg": a["dmg"],
            "type": a["type"],
            "effect": a.get("effect"),
            "cooldown": a["cooldown"],
            "mana_cost": a["mana_cost"],
            "lore": a["lore"],
            "is_special": a["is_special"],
            "description": a["description"],
        }
        for a in card["abilities"]
    ]

    try:
        abilities_result = supabase.table("ability").insert(abilities_data).execute()
    except Exception as exc:
        raise DigitizePersistenceError(f"Failed to create abilities: {exc}") from exc

    if not abilities_result.data:
        raise DigitizePersistenceError("Abilities insert returned no data.")

    # ── 8. Update game_run record ────────────────────────────────────────────
    try:
        supabase.table("game_run").update(
            {"cat_id": cat_id, "status": "IN_PROGRESS"}
        ).eq("id", game_run_id).execute()
    except Exception as exc:
        raise DigitizePersistenceError(f"Failed to update game run: {exc}") from exc

    # ── 9. Build and return CatResponse ──────────────────────────────────────
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
        personality=cat_row.get("personality"),
        created_at=cat_row["created_at"],
        abilities=abilities,
    )
