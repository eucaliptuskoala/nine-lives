export const Class = {
  STRENGTH: "STRENGTH",
  AGILITY: "AGILITY",
  INTELLIGENCE: "INTELLIGENCE",
} as const;
export type Class = (typeof Class)[keyof typeof Class];

export const CatStatus = {
  ALIVE: "ALIVE",
  MEMORIAL: "MEMORIAL",
} as const;
export type CatStatus = (typeof CatStatus)[keyof typeof CatStatus];

export const GameStatus = {
  DIGITIZING: "DIGITIZING",
  IN_PROGRESS: "IN_PROGRESS",
  COMPLETED: "COMPLETED",
} as const;
export type GameStatus = (typeof GameStatus)[keyof typeof GameStatus];

export const Phase = {
  PLAYER_TURN: "PLAYER_TURN",
  ENEMY_TURN: "ENEMY_TURN",
} as const;
export type Phase = (typeof Phase)[keyof typeof Phase];

export const AbilityType = {
  DMG: "DMG",
  HEAL: "HEAL",
  STEAL: "STEAL",
  SHIELD: "SHIELD",
  AOE: "AOE",
  COUNTER: "COUNTER",
  TRUE_DMG: "TRUE_DMG",
} as const;
export type AbilityType = (typeof AbilityType)[keyof typeof AbilityType];

export const Effect = {
  STUN: "STUN",
  SILENCE: "SILENCE",
  BLEED: "BLEED",
  BURN: "BURN",
  BLIND: "BLIND",
  SLOW: "SLOW",
  TAUNT: "TAUNT",
  REGEN: "REGEN",
} as const;
export type Effect = (typeof Effect)[keyof typeof Effect];

export interface Ability {
  id: string;
  creature_id: string;
  name: string;
  dmg: number;
  type: AbilityType;
  effect: Effect | null;
  cooldown: number;
  lore: string;
  is_special: boolean;
  description: string;
}

export interface Enemy {
  name: string;
  breed: string;
  hp: number;
  max_hp: number;
  atk: number;
  def: number;
  spd: number;
  ability: string;
  avatar_url: string;
}

export interface GameState {
  player_hp: number;
  player_max_hp: number;
  player_is_defending: boolean;
  special_cooldown: number;
  phase: Phase;
  current_round: number;
  enemy: Enemy;
}

export interface Creature {
  id: string;
  name: string;
  breed: string;
  class: Class;
  current_hp: number;
  max_hp: number;
  dmg: number;
  defence: number;
  spd: number;
  lore: string;
  avatar_url: string;
  lives_remaining: number;
  abilities: Ability[];
}

export interface Cat extends Creature {
  user_id: string;
  source_image_url: string;
  status: CatStatus;
  wins: number;
  death_date: string | null;
  personal_note: string | null;
  created_at: string;
}

export interface GameRun {
  id: string;
  cat_id: string | null;
  status: GameStatus;
  current_round: number;
  state: GameState | null;
  created_at: string;
  completed_at: string | null;
}
