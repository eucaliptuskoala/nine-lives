import { useState, useCallback } from "react";
import type { GameState, Ability } from "../types/game";
import { Phase } from "../types/game";
import { generateEnemy } from "../utils/enemyGen";
import { createEnemyAttack, regenMana, tickCooldowns } from "../utils/combat";

export function useGameState() {
  const [state, setState] = useState<GameState | null>(null);

  const initRound = useCallback(
    (
      catHp: number,
      catMaxHp: number,
      catMana: number,
      catMaxMana: number,
      lives: number,
      round: number
    ) => {
      const enemy = generateEnemy(round);
      setState({
        player_hp: catHp,
        player_max_hp: catMaxHp,
        player_mana: catMana,
        player_max_mana: catMaxMana,
        player_is_defending: false,
        player_shield: 0,
        lives_remaining: lives,
        player_ability_cooldowns: {},
        phase: Phase.PLAYER_TURN,
        current_round: round,
        enemy,
      });
    },
    []
  );

  const attack = useCallback(() => {
    setState((prev) => {
      if (!prev || prev.phase !== Phase.PLAYER_TURN) return prev;

      const playerMana = regenMana(prev.player_mana, prev.player_max_mana);
      const playerCooldowns = tickCooldowns(prev.player_ability_cooldowns);
      const dmg = Math.max(prev.player_max_hp * 0.1 - prev.enemy.def * 0.5, 1);
      const newEnemyHp = Math.max(prev.enemy.hp - dmg, 0);
      const enemyDead = newEnemyHp <= 0;

      if (enemyDead) {
        const nextRound = prev.current_round + 1;
        return {
          ...prev,
          player_mana: playerMana,
          player_ability_cooldowns: playerCooldowns,
          enemy: generateEnemy(nextRound),
          phase: Phase.PLAYER_TURN,
          current_round: nextRound,
        } satisfies GameState;
      }

      return {
        ...prev,
        player_mana: playerMana,
        player_ability_cooldowns: playerCooldowns,
        enemy: { ...prev.enemy, hp: newEnemyHp },
        phase: Phase.ENEMY_TURN,
      } satisfies GameState;
    });
  }, []);

  const defend = useCallback(() => {
    setState((prev) => {
      if (!prev || prev.phase !== Phase.PLAYER_TURN) return prev;

      const playerMana = regenMana(prev.player_mana, prev.player_max_mana);
      const playerCooldowns = tickCooldowns(prev.player_ability_cooldowns);

      return {
        ...prev,
        player_mana: playerMana,
        player_ability_cooldowns: playerCooldowns,
        player_is_defending: true,
        phase: Phase.ENEMY_TURN,
      } satisfies GameState;
    });
  }, []);

  const useAbility = useCallback(
    (abilityId: string, abilities: Ability[]) => {
      setState((prev) => {
        if (!prev || prev.phase !== Phase.PLAYER_TURN) return prev;

        const ability = abilities.find((a) => a.id === abilityId);
        if (!ability) return prev;
        if ((prev.player_ability_cooldowns[abilityId] ?? 0) > 0) return prev;
        if (prev.player_mana < ability.mana_cost) return prev;

        const playerMana = regenMana(
          prev.player_mana - ability.mana_cost,
          prev.player_max_mana
        );
        const playerCooldowns = tickCooldowns({
          ...prev.player_ability_cooldowns,
          [abilityId]: ability.cooldown,
        });

        let playerHp = prev.player_hp;
        let playerShield = prev.player_shield;
        let newEnemyHp = prev.enemy.hp;

        if (ability.type === "DMG" || ability.type === "TRUE_DMG") {
          const raw = Math.max(ability.dmg - prev.enemy.def * 0.5, 1);
          newEnemyHp = Math.max(prev.enemy.hp - raw, 0);
        } else if (ability.type === "HEAL") {
          playerHp = Math.min(prev.player_max_hp, prev.player_hp + ability.dmg);
        } else if (ability.type === "SHIELD") {
          playerShield = ability.dmg;
        }

        const enemyDead = newEnemyHp <= 0;

        if (enemyDead) {
          const nextRound = prev.current_round + 1;
          return {
            ...prev,
            player_hp: playerHp,
            player_mana: playerMana,
            player_shield: playerShield,
            player_ability_cooldowns: playerCooldowns,
            enemy: generateEnemy(nextRound),
            phase: Phase.PLAYER_TURN,
            current_round: nextRound,
          } satisfies GameState;
        }

        return {
          ...prev,
          player_hp: playerHp,
          player_mana: playerMana,
          player_shield: playerShield,
          player_ability_cooldowns: playerCooldowns,
          enemy: { ...prev.enemy, hp: newEnemyHp },
          phase: Phase.ENEMY_TURN,
        } satisfies GameState;
      });
    },
    []
  );

  const resolveEnemyTurn = useCallback(() => {
    setState((prev) => {
      if (!prev || prev.phase !== Phase.ENEMY_TURN) return prev;

      const withRegen = {
        ...prev,
        enemy: {
          ...prev.enemy,
          mana: regenMana(prev.enemy.mana, prev.enemy.max_mana),
          ability_cooldowns: tickCooldowns(prev.enemy.ability_cooldowns),
        },
      };

      const result = createEnemyAttack(withRegen);

      if (result.player_hp <= 0) {
        const newLives = result.lives_remaining - 1;
        if (newLives <= 0) {
          return {
            ...result,
            lives_remaining: 0,
            player_hp: 0,
            phase: Phase.PLAYER_TURN,
          } satisfies GameState;
        }
        return {
          ...result,
          player_hp: result.player_max_hp,
          player_mana: result.player_max_mana,
          player_shield: 0,
          lives_remaining: newLives,
          phase: Phase.PLAYER_TURN,
        } satisfies GameState;
      }

      return {
        ...result,
        phase: Phase.PLAYER_TURN,
      } satisfies GameState;
    });
  }, []);

  return { state, setState, initRound, attack, defend, useAbility, resolveEnemyTurn };
}
