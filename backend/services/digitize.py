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

TIMING INSTRUMENTATION: Each major step logs elapsed time to stdout for debugging
and optimization. Timing data is not persisted; it's useful for profiling during
development and troubleshooting slow digitizations.

Related: Requirements 1.9, 2, 3, 4, 5, 6
"""

import logging
import time
from typing import Optional

from services.supabase_client import get_supabase_client
from services.classify import classify_breed
from services.extract_colors import extract_colors
from services.generate_card import generate_card
from services.generate_avatar import generate_avatar
from models.schemas import (
    Ability,
    CatResponse,
    CatStatus,
    Class,
)

BUCKET_NAME = "cat-images"

logger = logging.getLogger(__name__)


def _log_step(step_name: str, elapsed_sec: float) -> None:
    """Log a pipeline step with its elapsed time."""
    logger.info(f"[DIGITIZE TIMING] {step_name}: {elapsed_sec:.2f}s")


class DigitizeStorageError(Exception):
    """Raised when uploading the source image to storage fails (→ HTTP 500)."""


class DigitizeGenerationError(Exception):
    """Raised when card or avatar generation fails (→ HTTP 502)."""


class DigitizePersistenceError(Exception):
    """Raised when persisting the cat/abilities/game_run fails (→ HTTP 500)."""


def _content_type_to_ext(content_type: str) -> str:
    """Map an allowed image content type to its file extension."""
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]


def digitize(
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
    pipeline_start = time.perf_counter()
    logger.info(f"[DIGITIZE] Starting pipeline for cat '{cat_name}', run_id={game_run_id}, user_id={user_id}")

    # 1. Upload source image to Supabase Storage
    step_start = time.perf_counter()
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
        logger.error(f"[DIGITIZE] Image upload failed: {exc}", exc_info=True)
        raise DigitizeStorageError(f"Image upload failed: {exc}") from exc

    _log_step("1. Image Upload", time.perf_counter() - step_start)

    # 2. Breed classification
    step_start = time.perf_counter()
    try:
        breed = classify_breed(image_bytes)
    except Exception as exc:
        logger.error(f"[DIGITIZE] Breed classification failed: {exc}", exc_info=True)
        raise
    _log_step("2. Breed Classification", time.perf_counter() - step_start)

    # 3. Colour extraction
    # colors is a list[dict] of {"hex": str, "ratio": float}.
    step_start = time.perf_counter()
    try:
        colors = extract_colors(image_bytes)
    except Exception as exc:
        logger.error(f"[DIGITIZE] Color extraction failed: {exc}", exc_info=True)
        raise
    _log_step("3. Color Extraction", time.perf_counter() - step_start)

    # 4. Generate card stats via Gemini
    step_start = time.perf_counter()
    try:
        card = generate_card(
            cat_name=cat_name,
            breed=breed,
            colors=colors,
            personality=personality,
        )
    except Exception as exc:
        logger.error(f"[DIGITIZE] Card generation failed: {exc}", exc_info=True)
        raise DigitizeGenerationError(f"Card generation failed: {exc}") from exc

    _log_step("4. Card Generation (Gemini)", time.perf_counter() - step_start)

    # 5. Generate avatar via FLUX.1-schnell
    step_start = time.perf_counter()
    try:
        avatar_url = generate_avatar(card["image_prompt"])
    except Exception as exc:
        logger.error(f"[DIGITIZE] Avatar generation failed: {exc}", exc_info=True)
        raise DigitizeGenerationError(f"Avatar generation failed: {exc}") from exc

    _log_step("5. Avatar Generation (FLUX)", time.perf_counter() - step_start)

    # 6. Insert cat record
    step_start = time.perf_counter()
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
        logger.error(f"[DIGITIZE] Cat insert failed: {exc}", exc_info=True)
        raise DigitizePersistenceError(
            f"Failed to create cat record: {exc}"
        ) from exc

    if not cat_result.data:
        logger.error("[DIGITIZE] Cat insert returned no data")
        raise DigitizePersistenceError("Cat insert returned no data.")

    cat_row = cat_result.data[0]
    cat_id = str(cat_row["id"])

    _log_step("6. Cat Record Insert", time.perf_counter() - step_start)

    # 7. Insert abilities
    step_start = time.perf_counter()
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
        logger.error(f"[DIGITIZE] Abilities insert failed: {exc}", exc_info=True)
        raise DigitizePersistenceError(f"Failed to create abilities: {exc}") from exc

    if not abilities_result.data:
        logger.error("[DIGITIZE] Abilities insert returned no data")
        raise DigitizePersistenceError("Abilities insert returned no data.")

    _log_step("7. Abilities Insert", time.perf_counter() - step_start)

    # 8. Update game_run record
    step_start = time.perf_counter()
    try:
        supabase.table("game_run").update(
            {"cat_id": cat_id, "status": "IN_PROGRESS"}
        ).eq("id", game_run_id).execute()
    except Exception as exc:
        logger.error(f"[DIGITIZE] Game run update failed: {exc}", exc_info=True)
        raise DigitizePersistenceError(f"Failed to update game run: {exc}") from exc

    _log_step("8. Game Run Update", time.perf_counter() - step_start)

    # 9. Build and return CatResponse
    abilities = [Ability.from_db_row(row) for row in abilities_result.data]

    total_elapsed = time.perf_counter() - pipeline_start
    _log_step("TOTAL PIPELINE", total_elapsed)
    logger.info(f"[DIGITIZE] Completed for cat '{cat_row['name']}' (ID: {cat_id})")

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
