from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


class Class(str, Enum):
    STRENGTH = "STRENGTH"
    AGILITY = "AGILITY"
    INTELLIGENCE = "INTELLIGENCE"


class CatStatus(str, Enum):
    ALIVE = "ALIVE"
    MEMORIAL = "MEMORIAL"


class GameStatus(str, Enum):
    DIGITIZING = "DIGITIZING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class Phase(str, Enum):
    PLAYER_TURN = "PLAYER_TURN"
    ENEMY_TURN = "ENEMY_TURN"


class AbilityType(str, Enum):
    DMG = "DMG"
    HEAL = "HEAL"
    STEAL = "STEAL"
    SHIELD = "SHIELD"
    AOE = "AOE"
    COUNTER = "COUNTER"
    TRUE_DMG = "TRUE_DMG"


class Effect(str, Enum):
    STUN = "STUN"
    SILENCE = "SILENCE"
    BLEED = "BLEED"
    BURN = "BURN"
    BLIND = "BLIND"
    SLOW = "SLOW"
    TAUNT = "TAUNT"
    REGEN = "REGEN"


class Ability(BaseModel):
    id: str
    creature_id: str
    name: str
    dmg: int
    type: AbilityType
    effect: Effect | None = None
    cooldown: int
    mana_cost: int
    lore: str
    is_special: bool
    description: str

    @classmethod
    def from_db_row(cls, row: dict) -> "Ability":
        return cls(
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


class EnemyAbility(BaseModel):
    id: str
    name: str
    dmg: int
    type: AbilityType
    effect: Effect | None = None
    mana_cost: int
    cooldown: int
    is_special: bool
    description: str


class Enemy(BaseModel):
    name: str
    breed: str
    hp: int
    max_hp: int
    atk: int
    defence: int
    spd: int
    mana: int
    max_mana: int
    shield: int = 0
    ability_cooldowns: dict[str, int]
    abilities: list[EnemyAbility]
    avatar_url: str


class GameState(BaseModel):
    player_hp: int
    player_max_hp: int
    player_mana: int
    player_max_mana: int
    player_is_defending: bool
    player_shield: int
    lives_remaining: int
    player_ability_cooldowns: dict[str, int]
    phase: Phase
    current_round: int
    enemy: Enemy
    events: list[str] | None = None


class CreatureBase(BaseModel):
    name: str
    breed: str
    class_: Class
    current_hp: int
    max_hp: int
    dmg: int
    defence: int
    spd: int
    mana: int
    max_mana: int
    lore: str
    avatar_url: str
    lives_remaining: int
    abilities: list[Ability]


class CatResponse(CreatureBase):
    id: str
    user_id: str
    source_image_url: str
    status: CatStatus
    wins: int
    death_date: datetime | None = None
    personal_note: str | None = None
    personality: str | None = None
    created_at: datetime


class GameRunResponse(BaseModel):
    id: str
    cat_id: str | None = None
    status: GameStatus
    current_round: int
    created_at: datetime
    completed_at: datetime | None = None


# ─── Battle API Request/Response Models ──────────────────────────────────────


class BattleActionRequest(BaseModel):
    """Request body for `POST /api/battle/action`."""

    run_id: str
    action: Literal["attack", "defend", "ability"]
    ability_id: str | None = None


class BattleActionResponse(BaseModel):
    """Response for `POST /api/battle/action`.

    `events` is a transient, human-readable turn log for the frontend to
    display; it is never persisted to the database.
    """

    game_state: GameState
    cat: CatResponse  # player's cat — response-only, not persisted into game_run.state
    revival: bool = False
    game_over: bool = False
    events: list[str] = Field(default_factory=list)


class BattleStateResponse(BaseModel):
    """Response for `POST /api/battle/start` — the current persisted state."""

    game_state: GameState
    cat: CatResponse  # player's cat — response-only, not persisted into game_run.state


# ─── Data API Request/Response Models ────────────────────────────────────────


class CreateGameRunResponse(BaseModel):
    """Response for `POST /api/game-runs`.

    A freshly created game run always starts in the DIGITIZING status.
    """

    run_id: str
    status: GameStatus  # always DIGITIZING on creation


class ActiveGameRunResponse(BaseModel):
    """Response for `GET /api/game-runs/active`.

    Returns the authenticated user's most recent IN_PROGRESS game run whose
    linked cat is still ALIVE, or `run_id=None`/`cat=None` when there is none.
    """

    run_id: str | None = None
    cat: CatResponse | None = None


class UpdateNoteRequest(BaseModel):
    """Request body for `PATCH /api/cats/{cat_id}/note`.

    `note` is the personal note text; the ≤500 char limit is enforced
    server-side in the endpoint (Requirement 23.4).
    """

    note: str
