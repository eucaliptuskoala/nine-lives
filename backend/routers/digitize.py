"""
Digitize Router — /api/digitize

Accepts a cat photo upload plus metadata, runs the ML pipeline (breed
classification, color extraction, Gemini card generation, Gemini avatar
generation), persists the cat and abilities to Supabase, and returns
a complete CatResponse.

Related: Requirements 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 26.1, 26.2, 26.3, 26.4
"""

import io
import random
import time
from datetime import datetime
from typing import Optional

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
from services.card_generator import generate_card
from services.avatar_generator import generate_avatar

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

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _content_type_to_ext(content_type: str) -> str:
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]


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


def _ability_type_to_db(type_: str) -> AbilityType:
    return AbilityType(type_)


# ─── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("", response_model=CatResponse)
async def digitize_cat(
    file: UploadFile = File(...),
    game_run_id: str = Form(...),
    user_id: str = Form(...),
    cat_name: str = Form(...),
    personality: Optional[str] = Form(None),
) -> CatResponse:
    """
    Digitize a cat photo into a game card.

    Validates the uploaded image, classifies breed, extracts colours,
    generates stats + avatar via Gemini, persists cat + abilities to
    Supabase, and links the game run.
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

    # ── 4. Breed classification (placeholder: random) ────────────────────────
    # TODO: Replace with real ML inference via classifier service
    breed = random.choice(CAT_BREEDS)

    # ── 5. Colour extraction (placeholder: empty) ────────────────────────────
    # TODO: Replace with real color extraction via color_extractor service
    colors: list[str] = []

    # ── 6. Generate card stats via Gemini ────────────────────────────────────
    try:
        card = generate_card(
            cat_name=cat_name,
            breed=breed,
            colors=colors,
            personality=personality,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Card generation failed: {exc}",
        )

    # ── 7. Generate avatar via Gemini ────────────────────────────────────────
    try:
        avatar_img = generate_avatar(card["image_prompt"])
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Avatar generation failed: {exc}",
        )

    # ── 8. Upload avatar to storage ──────────────────────────────────────────
    avatar_buffer = io.BytesIO()
    avatar_img.save(avatar_buffer, format="PNG")
    avatar_bytes = avatar_buffer.getvalue()

    avatar_storage_path = f"{user_id}/avatar-{timestamp}.png"
    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            avatar_storage_path,
            avatar_bytes,
            file_options={
                "content-type": "image/png",
                "cache-control": "3600",
                "upsert": "false",
            },
        )
        avatar_url = supabase.storage.from_(BUCKET_NAME).get_public_url(avatar_storage_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Avatar upload failed: {exc}")

    # ── 9. Insert cat record ─────────────────────────────────────────────────
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
        raise HTTPException(status_code=500, detail=f"Failed to create cat record: {exc}")

    if not cat_result.data:
        raise HTTPException(status_code=500, detail="Cat insert returned no data.")

    cat_row = cat_result.data[0]
    cat_id = str(cat_row["id"])

    # ── 10. Insert abilities ─────────────────────────────────────────────────
    abilities_data = []
    for a in card["abilities"]:
        abilities_data.append(
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
        )

    try:
        abilities_result = supabase.table("ability").insert(abilities_data).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create abilities: {exc}")

    if not abilities_result.data:
        raise HTTPException(status_code=500, detail="Abilities insert returned no data.")

    # ── 11. Update game_run record ───────────────────────────────────────────
    try:
        supabase.table("game_run").update(
            {"cat_id": cat_id, "status": "IN_PROGRESS"}
        ).eq("id", game_run_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update game run: {exc}")

    # ── 12. Build and return CatResponse ─────────────────────────────────────
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
