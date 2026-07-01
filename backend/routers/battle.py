"""
Battle Router — /api/battle

Exposes the Battle API. Authenticates requests (Supabase JWT), enforces
game_run ownership, loads/persists Game_State from `game_run.state`, and
delegates all combat resolution to the pure functions in
`services/battle_engine.py`. The frontend performs no combat calculations —
it only renders the Game_State returned here.

Endpoints:
    POST /api/battle/start   — initialize (or resume) a battle for a game_run
    POST /api/battle/action  — submit a player action and resolve the full turn

Auth & ownership (Requirement 21):
    * Every request requires a valid Auth_Token → 401 on missing/invalid (the
      `get_current_user` dependency raises this).
    * The authenticated user must own the game_run identified by `run_id`. The
      `game_run` table carries a `user_id` column directly (see migration.sql),
      so ownership is `game_run.user_id == authenticated user id` → 403 otherwise.

Persistence:
    * Uses the service-key Supabase client (bypasses RLS) for reads/writes.
    * Game_State is serialized via `model_dump(mode="json", exclude={"events"})`
      so the transient turn log is never persisted (Requirement 20.1/20.2).

Related: Requirements 7, 9, 10, 11, 15, 18, 19, 20, 21, 29.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from auth import CurrentUser
from models.schemas import (
    Ability,
    AbilityType,
    BattleActionRequest,
    BattleActionResponse,
    BattleStateResponse,
    CatResponse,
    CatStatus,
    Class,
    CreatureBase,
    Effect,
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
    """Request body for `POST /api/battle/start`.

    The frontend posts `{ "run_id": "<uuid>" }` (see frontend api/battle.ts).
    """

    run_id: str


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _build_creature(cat_row: dict, ability_rows: list[dict]) -> CreatureBase:
    """Build the `CreatureBase` the battle engine expects from DB rows.

    Note the DB column `def` maps to `defence` and `class` maps to `class_`.
    """
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
        abilities=[_db_row_to_ability(r) for r in ability_rows],
    )


def _cat_response_from_rows(cat_row: dict, ability_rows: list[dict]) -> CatResponse:
    """Build a `CatResponse` from a `cat` row and its abilities (Req 7.11, 9.8).

    This is the full player Cat returned in the battle responses. It is
    response-only and is never persisted into `game_run.state` (Req 7.12, 9.9).
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


def _load_game_run(supabase, run_id: str, user_id: str) -> dict:
    """Fetch the game_run, verifying it exists and is owned by the user.

    Raises 404 if the run does not exist, 403 if it belongs to another user
    (Requirement 21.3/21.4), and 500 on unexpected DB failures (Requirement 20.4).
    """
    try:
        result = supabase.table("game_run").select("*").eq("id", run_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load game run: {exc}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Game run not found.")

    game_run = result.data[0]

    if str(game_run.get("user_id")) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this game run.",
        )

    return game_run


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
    """Validate loaded Game_State invariants (Requirement 29).

    Phase validity is already guaranteed by pydantic enum parsing. HP/mana/lives
    bounds are checked here; on failure a 422 is returned so the frontend can
    surface the error and prevent further actions (Requirement 29.5).
    """
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
    """Persist Game_State (minus transient events) plus any extra columns.

    Raises 500 on failure (Requirement 20.4).
    """
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

    # 1. Auth (dependency) + ownership (Req 21.3/21.4).
    game_run = _load_game_run(supabase, body.run_id, user.user_id)

    # 2. Idempotency: return the existing state if already initialized (Req 7.10).
    #    Still load the cat so the response includes the player Cat (Req 7.11/7.12).
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

    # 3. Load the cat + abilities (Req 7.4).
    cat_id = game_run.get("cat_id")
    if not cat_id:
        raise HTTPException(
            status_code=400,
            detail="Game run has no cat assigned; digitize a cat first.",
        )
    cat_row, ability_rows = _load_cat_with_abilities(supabase, str(cat_id))
    cat = _build_creature(cat_row, ability_rows)

    # 4. Build the initial Game_State (Req 7.5). Special ability cooldowns start
    #    at their max to prevent first-turn ultimate usage; regular abilities at 0.
    player_ability_cooldowns = {
        ability.id: (ability.cooldown if ability.is_special else 0)
        for ability in cat.abilities
    }

    # 5. Generate the round-1 enemy (Req 7.6) and pre-set its special ability
    #    cooldown to max (Req 8.9).
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

    # 6. Persist state + mark the run IN_PROGRESS (Req 7.7).
    _persist_state(
        supabase,
        body.run_id,
        state,
        extra={"status": GameStatus.IN_PROGRESS.value},
    )

    # 7. Return the initial state + the player Cat (Req 7.8, 7.11). The cat is
    #    returned in the response only, never persisted into game_run.state.
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

    # 1. Auth (dependency) + ownership (Req 21.3/21.4).
    game_run = _load_game_run(supabase, body.run_id, user.user_id)

    # 2. Reject actions on a completed run (Req 20.5).
    if game_run.get("status") == GameStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This game run has already ended.",
        )

    # 3. Load + validate the current Game_State (Req 29).
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

    # 4. Load the player's creature (+abilities) for the engine.
    cat_id = game_run.get("cat_id")
    if not cat_id:
        raise HTTPException(status_code=400, detail="Game run has no cat assigned.")
    cat_row, ability_rows = _load_cat_with_abilities(supabase, str(cat_id))
    cat = _build_creature(cat_row, ability_rows)

    # 5. Resolve the player action. InvalidActionError → 400 WITHOUT persisting
    #    (Req 11.9): the engine never mutates the caller's state on failure.
    try:
        state, events = resolve_player_action(state, body.action, body.ability_id, cat)
    except InvalidActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    game_over = False
    revival = False
    cat_update: dict = {}
    run_extra: dict = {}

    if state.enemy.hp == 0:
        # Enemy defeated → advance the round and skip the enemy turn (Req 19).
        state = resolve_round_progression(state, cat)
        # Increment the cat's wins counter (Req 19.1).
        new_wins = int(cat_row.get("wins", 0)) + 1
        cat_update["wins"] = new_wins
    else:
        # Enemy still alive → enemy turn, then resolve death/revival.
        # player_defence is REQUIRED for correct basic-attack damage (Req 15.6).
        state, enemy_events = resolve_enemy_turn(state, player_defence=cat.defence)
        events += enemy_events
        state, game_over, revival = resolve_death_and_revival(state, cat)

    # 6. Game over → memorialize the cat and complete the run (Req 18.1–18.3).
    if game_over:
        cat_update["status"] = CatStatus.MEMORIAL.value
        cat_update["death_date"] = _now_iso()
        run_extra["status"] = GameStatus.COMPLETED.value
        run_extra["completed_at"] = _now_iso()

    # 7. Persist cat changes (wins / memorial) then the Game_State (Req 20.1).
    if cat_update:
        try:
            supabase.table("cat").update(cat_update).eq("id", str(cat_id)).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to update cat record: {exc}"
            )
        # Reflect the persisted cat changes in the row used for the response so
        # the returned Cat mirrors the DB (updated wins / MEMORIAL / death_date).
        cat_row.update(cat_update)

    _persist_state(supabase, body.run_id, state, extra=run_extra or None)

    # 8. Return the resolved turn + the player Cat (Req 9.8). The cat is returned
    #    in the response only, never persisted into game_run.state (Req 9.9).
    return BattleActionResponse(
        game_state=state,
        cat=_cat_response_from_rows(cat_row, ability_rows),
        revival=revival,
        game_over=game_over,
        events=events,
    )
