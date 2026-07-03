"""
Data Router — /api (game-runs, memorial cats, personal notes)

Mediates all non-battle, non-digitize database access for the frontend. These
endpoints replace what were previously direct Supabase reads/writes from
frontend pages/hooks. Every endpoint requires a valid Supabase JWT in the
`Authorization` header (enforced by the `get_current_user` dependency → 401 on
missing/invalid) and enforces ownership against the authenticated user in this
API layer. RLS remains enabled as a defense-in-depth backstop.

The backend uses the Supabase service key (bypasses RLS) for the actual queries.

Endpoints:
    POST  /api/game-runs          — create a new game run (status DIGITIZING)
    GET   /api/cats/memorial      — list the authenticated user's MEMORIAL cats
    PATCH /api/cats/{cat_id}/note — update a cat's personal note (owner only)

Related: Requirements 1.3, 22.1, 23.1, 23.2, 23.3, 23.4, 24.1, 24.3.
"""

from fastapi import APIRouter, HTTPException, status

from auth import CurrentUser
from models.schemas import (
    Ability,
    AbilityType,
    ActiveGameRunResponse,
    CatResponse,
    CatStatus,
    Class,
    CreateGameRunResponse,
    Effect,
    GameStatus,
    UpdateNoteRequest,
)
from services.supabase_client import get_supabase_client

router = APIRouter(tags=["data"])

# Maximum allowed length for a personal note (Requirement 23.4).
MAX_NOTE_LENGTH = 500


# ─── Helpers ──────────────────────────────────────────────────────────────────


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
    """Build a `CatResponse` from a `cat` row and its abilities.

    Note the DB column `def` maps to `defence` and `class` maps to `class_`.
    """
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
        abilities=[_db_row_to_ability(r) for r in ability_rows],
    )


# ─── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/game-runs", response_model=CreateGameRunResponse)
async def create_game_run(user: CurrentUser) -> CreateGameRunResponse:
    """Create a new game run for the authenticated user (Req 1.3, 24.3).

    The run starts in DIGITIZING with no cat assigned and no persisted state.
    """
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
    """Return the authenticated user's active game run, if any (Req 24.6, 24.7).

    Selects the user's IN_PROGRESS `game_run` rows (newest first) and returns the
    most recent one whose linked cat still exists and is ALIVE, along with that
    cat (abilities attached). Returns `run_id=None`/`cat=None` when there is no
    such run. Ownership is enforced by filtering on `user_id`; RLS remains as a
    defense-in-depth backstop.
    """
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
    """List the authenticated user's MEMORIAL cats, newest death first (Req 22.1, 24.1).

    Ownership is enforced by filtering on `user_id`; each cat's abilities are
    attached to the returned `CatResponse`.
    """
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
    """Update a cat's personal note (Req 23.1–23.4, 24.1).

    Verifies ownership (403 if not owner, 404 if missing) and enforces the
    ≤500 char limit (400 if exceeded) before updating `personal_note`.
    """
    # Validate note length server-side (Req 23.4).
    if len(body.note) > MAX_NOTE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Personal note must be {MAX_NOTE_LENGTH} characters or fewer.",
        )

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

    # Update the personal note (Req 23.2).
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
