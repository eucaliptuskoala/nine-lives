"""
Battle Router — /api/battle
"""

import threading
import time
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from auth import CurrentUser
from routers._helpers import load_game_run
from models.schemas import (
    Ability,
    BattleActionRequest,
    BattleActionResponse,
    BattleStateResponse,
    CatResponse,
    CatStatus,
    Class,
    CreatureBase,
    GameState,
    GameStatus,
    Phase,
)
from services.battle_engine import (
    InvalidActionError,
    resolve_death_and_revival,
    resolve_enemy_turn,
    resolve_player_action,
    resolve_round_progression,
)
from services.enemy_gen import generate_enemy
from services.supabase_client import get_supabase_client

router = APIRouter(prefix="/battle", tags=["battle"])


class BattleStartRequest(BaseModel):
    """Request body for `POST /api/battle/start`."""

    run_id: str


_rate_limit_lock = threading.Lock()
_rate_limit_requests: dict[str, deque] = {}


def check_rate_limit(
    user_id: str, max_requests: int = 20, window_seconds: float = 60.0
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
                detail="Too many battle requests. Please wait and try again.",
            )



def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_creature(cat_row: dict, ability_rows: list[dict]) -> CreatureBase:
    """Build CreatureBase from DB rows. DB `def` → `defence`, `class` → `class_`."""
    return CreatureBase(
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
        abilities=[Ability.from_db_row(r) for r in ability_rows],
    )


def _cat_response_from_rows(cat_row: dict, ability_rows: list[dict]) -> CatResponse:
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


def _load_cat_with_abilities(supabase, cat_id: str) -> tuple[dict, list[dict]]:
    """Load a cat row and its abilities. Raises 404/500 as appropriate."""
    try:
        cat_result = supabase.table("cat").select("*").eq("id", cat_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load cat: {exc}")

    if not cat_result.data:
        raise HTTPException(status_code=404, detail="Cat not found for this game run.")

    cat_row = cat_result.data[0]

    try:
        ability_result = (
            supabase.table("ability").select("*").eq("creature_id", cat_id).execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load abilities: {exc}")

    return cat_row, (ability_result.data or [])


def _validate_state_invariants(state: GameState) -> None:
    """Validate loaded Game_State invariants."""
    if not (0 <= state.player_hp <= state.player_max_hp):
        raise HTTPException(
            status_code=422,
            detail="Corrupted game state: player_hp out of bounds.",
        )
    if not (0 <= state.player_mana <= state.player_max_mana):
        raise HTTPException(
            status_code=422,
            detail="Corrupted game state: player_mana out of bounds.",
        )
    if not (0 <= state.lives_remaining <= 9):
        raise HTTPException(
            status_code=422,
            detail="Corrupted game state: lives_remaining out of bounds.",
        )


def _persist_state(supabase, run_id: str, state: GameState, extra: dict | None = None) -> None:
    """Persist Game_State (minus transient events) plus any extra columns."""
    payload: dict = {
        "state": state.model_dump(mode="json", exclude={"events"}),
        "current_round": state.current_round,
    }
    if extra:
        payload.update(extra)

    try:
        supabase.table("game_run").update(payload).eq("id", run_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist game state: {exc}")


# ─── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/start", response_model=BattleStateResponse)
async def start_battle(body: BattleStartRequest, user: CurrentUser) -> BattleStateResponse:
    """Initialize (or resume) the battle for a game_run.

    Idempotent: if the game_run already has a persisted Game_State, that state is
    returned as-is rather than recreating it (Requirement 7.10).
    """
    supabase = get_supabase_client()

    game_run = load_game_run(supabase, body.run_id, user.user_id)

    check_rate_limit(user.user_id)

    existing_state = game_run.get("state")
    if existing_state:
        cat_id = game_run.get("cat_id")
        if not cat_id:
            raise HTTPException(
                status_code=400,
                detail="Game run has no cat assigned; digitize a cat first.",
            )
        cat_row, ability_rows = _load_cat_with_abilities(supabase, str(cat_id))
        return BattleStateResponse(
            game_state=GameState(**existing_state),
            cat=_cat_response_from_rows(cat_row, ability_rows),
        )

    cat_row, ability_rows = _load_cat_with_abilities(supabase, str(cat_id))
    cat = _build_creature(cat_row, ability_rows)

    # Special ability cooldowns start at max to prevent first-turn ultimate usage.
    player_ability_cooldowns = {
        ability.id: (ability.cooldown if ability.is_special else 0)
        for ability in cat.abilities
    }

    # Generate the round-1 enemy; pre-set its special ability cooldown to max.
    enemy = generate_enemy(1)
    for ability in enemy.abilities:
        if ability.is_special:
            enemy.ability_cooldowns[ability.id] = ability.cooldown

    state = GameState(
        player_hp=cat.max_hp,
        player_max_hp=cat.max_hp,
        player_mana=cat.max_mana,
        player_max_mana=cat.max_mana,
        player_is_defending=False,
        player_shield=0,
        lives_remaining=cat.lives_remaining,
        player_ability_cooldowns=player_ability_cooldowns,
        phase=Phase.PLAYER_TURN,
        current_round=1,
        enemy=enemy,
    )

    _persist_state(
        supabase,
        body.run_id,
        state,
        extra={"status": GameStatus.IN_PROGRESS.value},
    )

    return BattleStateResponse(
        game_state=state,
        cat=_cat_response_from_rows(cat_row, ability_rows),
    )


@router.post("/action", response_model=BattleActionResponse)
async def submit_action(
    body: BattleActionRequest, user: CurrentUser
) -> BattleActionResponse:
    """Submit a player action and resolve the full turn.

    Composes the battle engine: player action → (round progression | enemy turn +
    death/revival) → persist → respond.
    """
    supabase = get_supabase_client()

    game_run = load_game_run(supabase, body.run_id, user.user_id)

    check_rate_limit(user.user_id)

    if game_run.get("status") == GameStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This game run has already ended.",
        )

    # Load + validate the current Game_State.
    raw_state = game_run.get("state")
    if not raw_state:
        raise HTTPException(
            status_code=409,
            detail="Battle has not been started for this game run.",
        )
    try:
        state = GameState(**raw_state)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Corrupted game state: {exc}")
    _validate_state_invariants(state)

    # Load the player's creature for the engine.
    cat_id = game_run.get("cat_id")
    if not cat_id:
        raise HTTPException(status_code=400, detail="Game run has no cat assigned.")
    cat_row, ability_rows = _load_cat_with_abilities(supabase, str(cat_id))
    cat = _build_creature(cat_row, ability_rows)

    # Resolve the player action. InvalidActionError → 400 without persisting.
    try:
        state, events = resolve_player_action(state, body.action, body.ability_id, cat)
    except InvalidActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    game_over = False
    revival = False
    cat_update: dict = {}
    run_extra: dict = {}

    if state.enemy.hp == 0:
        state = resolve_round_progression(state, cat)
        new_wins = int(cat_row.get("wins", 0)) + 1
        cat_update["wins"] = new_wins
    else:
        state, enemy_events = resolve_enemy_turn(state, player_defence=cat.defence)
        events += enemy_events
        state, game_over, revival = resolve_death_and_revival(state, cat)

    if game_over:
        cat_update["status"] = CatStatus.MEMORIAL.value
        cat_update["death_date"] = _now_iso()
        run_extra["status"] = GameStatus.COMPLETED.value
        run_extra["completed_at"] = _now_iso()

    if cat_update:
        try:
            supabase.table("cat").update(cat_update).eq("id", str(cat_id)).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to update cat record: {exc}"
            )
        cat_row.update(cat_update)

    _persist_state(supabase, body.run_id, state, extra=run_extra or None)

    return BattleActionResponse(
        game_state=state,
        cat=_cat_response_from_rows(cat_row, ability_rows),
        revival=revival,
        game_over=game_over,
        events=events,
    )
