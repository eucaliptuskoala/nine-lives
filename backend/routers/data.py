"""
Data Router — /api (game-runs, memorial cats, personal notes)
"""

import threading
import time
from collections import deque

from fastapi import APIRouter, HTTPException, status

from auth import CurrentUser
from models.schemas import (
    Ability,
    ActiveGameRunResponse,
    CatResponse,
    CatStatus,
    Class,
    CreateGameRunResponse,
    GameStatus,
    UpdateNoteRequest,
)
from services.supabase_client import get_supabase_client

router = APIRouter(tags=["data"])

# Maximum allowed length for a personal note.
MAX_NOTE_LENGTH = 500


# ─── In-process rate limiter ──────────────────────────────────────────────────

_rate_limit_lock = threading.Lock()
_rate_limit_requests: dict[str, deque] = {}


def check_rate_limit(
    user_id: str, max_requests: int = 30, window_seconds: float = 60.0
) -> None:
    now = time.time()
    with _rate_limit_lock:
        timestamps = _rate_limit_requests.setdefault(user_id, deque())
        timestamps.append(now)
        while timestamps and timestamps[0] <= now - window_seconds:
            timestamps.popleft()
        if len(timestamps) > max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait and try again.",
            )


def _load_abilities(supabase, cat_id: str) -> list[dict]:
    """Load the ability rows for a cat. Raises 500 on DB failure."""
    try:
        result = (
            supabase.table("ability").select("*").eq("creature_id", cat_id).execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load abilities: {exc}")
    return result.data or []


def _db_row_to_cat_response(cat_row: dict, ability_rows: list[dict]) -> CatResponse:
    """Build CatResponse from a `cat` row and its abilities."""
    return CatResponse(
        id=str(cat_row["id"]),
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
        abilities=[Ability.from_db_row(r) for r in ability_rows],
    )

# ─── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/game-runs", response_model=CreateGameRunResponse)
async def create_game_run(user: CurrentUser) -> CreateGameRunResponse:
    """Create a new game run for the authenticated user."""
    check_rate_limit(user.user_id)
    supabase = get_supabase_client()

    run_data = {
        "user_id": user.user_id,
        "status": GameStatus.DIGITIZING.value,
        "cat_id": None,
        "current_round": 0,
        "state": None,
    }

    try:
        result = supabase.table("game_run").insert(run_data).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create game run: {exc}"
        )

    if not result.data:
        raise HTTPException(
            status_code=500, detail="Game run insert returned no data."
        )

    run_id = str(result.data[0]["id"])
    return CreateGameRunResponse(run_id=run_id, status=GameStatus.DIGITIZING)


@router.get("/game-runs/active", response_model=ActiveGameRunResponse)
async def get_active_game_run(user: CurrentUser) -> ActiveGameRunResponse:
    """Return the authenticated user's active game run, if any."""
    supabase = get_supabase_client()

    # Fetch the user's IN_PROGRESS runs, newest first.
    try:
        run_result = (
            supabase.table("game_run")
            .select("*")
            .eq("user_id", user.user_id)
            .eq("status", GameStatus.IN_PROGRESS.value)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to load active game run: {exc}"
        )

    for run_row in run_result.data or []:
        cat_id = run_row.get("cat_id")
        if not cat_id:
            continue

        # Load the linked cat and verify it exists and is ALIVE.
        try:
            cat_result = (
                supabase.table("cat").select("*").eq("id", cat_id).execute()
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to load active cat: {exc}"
            )

        if not cat_result.data:
            continue

        cat_row = cat_result.data[0]
        if cat_row.get("status") != CatStatus.ALIVE.value:
            continue

        ability_rows = _load_abilities(supabase, str(cat_row["id"]))
        cat = _db_row_to_cat_response(cat_row, ability_rows)
        return ActiveGameRunResponse(run_id=str(run_row["id"]), cat=cat)

    return ActiveGameRunResponse(run_id=None, cat=None)


@router.get("/cats/memorial", response_model=list[CatResponse])
async def list_memorial_cats(user: CurrentUser) -> list[CatResponse]:
    """List the authenticated user's MEMORIAL cats, newest death first."""
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("cat")
            .select("*")
            .eq("user_id", user.user_id)
            .eq("status", CatStatus.MEMORIAL.value)
            .order("death_date", desc=True)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to load memorial cats: {exc}"
        )

    cats: list[CatResponse] = []
    for cat_row in result.data or []:
        ability_rows = _load_abilities(supabase, str(cat_row["id"]))
        cats.append(_db_row_to_cat_response(cat_row, ability_rows))

    return cats


@router.patch("/cats/{cat_id}/note", response_model=CatResponse)
async def update_cat_note(
    cat_id: str, body: UpdateNoteRequest, user: CurrentUser
) -> CatResponse:
    """Update a cat's personal note."""
    # Validate note length server-side.
    if len(body.note) > MAX_NOTE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Personal note must be {MAX_NOTE_LENGTH} characters or fewer.",
        )

    check_rate_limit(user.user_id)
    supabase = get_supabase_client()

    # Load the cat to verify existence and ownership.
    try:
        result = supabase.table("cat").select("*").eq("id", cat_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load cat: {exc}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Cat not found.")

    cat_row = result.data[0]

    if str(cat_row.get("user_id")) != str(user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this cat.",
        )

    # Update the personal note.
    try:
        update_result = (
            supabase.table("cat")
            .update({"personal_note": body.note})
            .eq("id", cat_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to update personal note: {exc}"
        )

    updated_row = update_result.data[0] if update_result.data else {**cat_row, "personal_note": body.note}
    ability_rows = _load_abilities(supabase, str(updated_row["id"]))
    return _db_row_to_cat_response(updated_row, ability_rows)
