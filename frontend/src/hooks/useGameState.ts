import { useState, useCallback } from "react";
import type { GameState } from "../types/game";
import { Phase } from "../types/game";
import { generateEnemy } from "../utils/enemyGen";
import { createEnemyAttack } from "../utils/combat";

export function useGameState() {
  const [state, setState] = useState<GameState | null>(null);

  const initRound = useCallback((catHp: number, catMaxHp: number, round: number) => {
    setState({
      player_hp: catHp,
      player_max_hp: catMaxHp,
      player_is_defending: false,
      special_cooldown: 0,
      phase: Phase.PLAYER_TURN,
      current_round: round,
      enemy: generateEnemy(round),
    });
  }, []);

  const defend = useCallback(() => {
    setState((prev) => {
      if (!prev || prev.phase !== Phase.PLAYER_TURN) return prev;
      return createEnemyAttack({ ...prev, player_is_defending: true });
    });
  }, []);

  const attack = useCallback(() => {
    setState((prev) => {
      if (!prev || prev.phase !== Phase.PLAYER_TURN) return prev;
      return createEnemyAttack(prev);
    });
  }, []);

  return { state, initRound, attack, defend, setState };
}
