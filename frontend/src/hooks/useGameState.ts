import { useState, useCallback } from "react";
import type { GameState, Ability } from "../types/game";
import { Phase } from "../types/game";
import { generateEnemy } from "../utils/enemyGen";
import { createEnemyAttack, regenMana, tickCooldowns } from "../utils/combat";

export function useGameState() {
  const [state, setState] = useState<GameState | null>(null);

  const initRound = useCallback(
    (catHp: number, catMaxHp: number, catMana: number, catMaxMana: number, round: number) => {
      const enemy = generateEnemy(round);
      setState({
        player_hp: catHp,
        player_max_hp: catMaxHp,
        player_mana: catMana,
        player_max_mana: catMaxMana,
        player_is_defending: false,
        player_shield: 0,
        player_ability_cooldowns: {},
        phase: Phase.PLAYER_TURN,
        current_round: round,
        enemy,
      });
    },
    []
  );

  const defend = useCallback(() => {
    setState((prev) => {
      if (!prev || prev.phase !== Phase.PLAYER_TURN) return prev;

      const playerMana = regenMana(prev.player_mana, prev.player_max_mana);
      const playerCooldowns = tickCooldowns(prev.player_ability_cooldowns);
      const enemyMana = regenMana(prev.enemy.mana, prev.enemy.max_mana);
      const enemyCooldowns = tickCooldowns(prev.enemy.ability_cooldowns);

      const afterDefend: GameState = {
        ...prev,
        player_mana: playerMana,
        player_ability_cooldowns: playerCooldowns,
        player_is_defending: true,
        enemy: {
          ...prev.enemy,
          mana: enemyMana,
          ability_cooldowns: enemyCooldowns,
        },
        phase: Phase.ENEMY_TURN,
      };

      return createEnemyAttack(afterDefend);
    });
  }, []);

  const attack = useCallback(() => {
    setState((prev) => {
      if (!prev || prev.phase !== Phase.PLAYER_TURN) return prev;

      const playerMana = regenMana(prev.player_mana, prev.player_max_mana);
      const playerCooldowns = tickCooldowns(prev.player_ability_cooldowns);
      const enemyMana = regenMana(prev.enemy.mana, prev.enemy.max_mana);
      const enemyCooldowns = tickCooldowns(prev.enemy.ability_cooldowns);

      const dmg = Math.max(
        prev.player_max_hp * 0.1 - prev.enemy.def * 0.5,
        1
      );

      const newEnemyHp = Math.max(prev.enemy.hp - dmg, 0);
      const enemyDead = newEnemyHp <= 0;

      const afterPlayer: GameState = {
        ...prev,
        player_hp: prev.player_hp,
        player_mana: playerMana,
        player_ability_cooldowns: playerCooldowns,
        enemy: {
          ...prev.enemy,
          hp: newEnemyHp,
          mana: enemyMana,
          ability_cooldowns: enemyCooldowns,
        },
        phase: Phase.ENEMY_TURN,
      };

      if (enemyDead) {
        const nextRound = prev.current_round + 1;
        const newEnemy = generateEnemy(nextRound);
        afterPlayer.enemy = newEnemy;
        afterPlayer.current_round = nextRound;
        afterPlayer.phase = Phase.PLAYER_TURN;
        return afterPlayer;
      }

      return createEnemyAttack(afterPlayer);
    });
  }, []);

  const useAbility = useCallback((abilityId: string, abilities: Ability[]) => {
    setState((prev) => {
      if (!prev || prev.phase !== Phase.PLAYER_TURN) return prev;

      const ability = abilities.find((a) => a.id === abilityId);
      if (!ability) return prev;

      const cooldown = prev.player_ability_cooldowns[abilityId] ?? 0;
      if (cooldown > 0) return prev;
      if (prev.player_mana < ability.mana_cost) return prev;

      const playerMana = regenMana(
        prev.player_mana - ability.mana_cost,
        prev.player_max_mana
      );
      const playerCooldowns = tickCooldowns({
        ...prev.player_ability_cooldowns,
        [abilityId]: ability.cooldown,
      });
      const enemyMana = regenMana(prev.enemy.mana, prev.enemy.max_mana);
      const enemyCooldowns = tickCooldowns(prev.enemy.ability_cooldowns);

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
      const afterPlayer: GameState = {
        ...prev,
        player_hp: playerHp,
        player_mana: playerMana,
        player_shield: playerShield,
        player_ability_cooldowns: playerCooldowns,
        enemy: {
          ...prev.enemy,
          hp: newEnemyHp,
          mana: enemyMana,
          ability_cooldowns: enemyCooldowns,
        },
        phase: Phase.ENEMY_TURN,
      };

      if (enemyDead) {
        const nextRound = prev.current_round + 1;
        const newEnemy = generateEnemy(nextRound);
        afterPlayer.enemy = newEnemy;
        afterPlayer.current_round = nextRound;
        afterPlayer.phase = Phase.PLAYER_TURN;
        return afterPlayer;
      }

      return createEnemyAttack(afterPlayer);
    });
  }, []);

  return { state, initRound, setState, attack, defend, useAbility };
}
