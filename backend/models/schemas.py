from enum import Enum
from pydantic import BaseModel
from typing import Optional
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
    effect: Optional[Effect] = None
    cooldown: int
    lore: str
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
    ability: str
    avatar_url: str


class GameState(BaseModel):
    player_hp: int
    player_max_hp: int
    player_is_defending: bool
    special_cooldown: int
    phase: Phase
    current_round: int
    enemy: Enemy


class CreatureBase(BaseModel):
    name: str
    breed: str
    class_: Class
    current_hp: int
    max_hp: int
    dmg: int
    defence: int
    spd: int
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
    death_date: Optional[datetime] = None
    personal_note: Optional[str] = None
    created_at: datetime


class GameRunResponse(BaseModel):
    id: str
    cat_id: Optional[str] = None
    status: GameStatus
    current_round: int
    created_at: datetime
    completed_at: Optional[datetime] = None
