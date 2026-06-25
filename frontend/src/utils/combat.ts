import type { GameState } from "../types/game";
import { Phase } from "../types/game";

export function calculateDamage(
  atk: number,
  def: number,
  isDefending: boolean
): number {
  const raw = Math.max(atk - def * 0.5, 1);
  return isDefending ? Math.floor(raw * 0.5) : Math.floor(raw);
}

export function createEnemyAttack(state: GameState): GameState {
  const { enemy, player_is_defending } = state;
  const dmg = calculateDamage(enemy.atk, state.player_max_hp * 0.1, player_is_defending);

  return {
    ...state,
    player_hp: Math.max(state.player_hp - dmg, 0),
    player_is_defending: false,
    phase: Phase.PLAYER_TURN,
  };
}

export function computeEnemyStats(round: number) {
  const m = 1 + (round - 1) * 0.3;
  return {
    hp: Math.floor((20 + round * 5) * m),
    atk: Math.floor((8 + round * 2) * m),
    def: Math.floor((6 + round * 1.5) * m),
    spd: Math.floor((7 + round * 2) * m),
  };
}
