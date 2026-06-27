import { Phase } from "../types/game";
import type { GameState, EnemyAbility } from "../types/game";

export function calculateDamage(
  atk: number,
  def: number,
  isDefending: boolean,
  shield: number
): { damage: number; shieldRemaining: number } {
  let raw = Math.max(atk - def * 0.5, 1);
  if (isDefending) raw = Math.floor(raw * 0.5);
  const absorbed = Math.min(shield, raw);
  return { damage: Math.floor(raw - absorbed), shieldRemaining: shield - absorbed };
}

export function applyAbilityDamage(
  ability: EnemyAbility,
  def: number,
  isDefending: boolean,
  shield: number
): { damage: number; shieldRemaining: number } {
  return calculateDamage(ability.dmg, def, isDefending, shield);
}

export function regenMana(current: number, max: number): number {
  return Math.min(max, current + Math.floor(max * 0.1));
}

export function tickCooldowns(
  cooldowns: Record<string, number>
): Record<string, number> {
  const next: Record<string, number> = {};
  for (const [id, remaining] of Object.entries(cooldowns)) {
    next[id] = Math.max(0, remaining - 1);
  }
  return next;
}

export function createEnemyAttack(state: GameState): GameState {
  const { enemy, player_is_defending, player_shield } = state;

  const available = enemy.abilities.filter(
    (a) =>
      enemy.mana >= a.mana_cost && (enemy.ability_cooldowns[a.id] ?? 0) === 0
  );

  const ultimate = available.find((a) => a.is_special);
  const chosen = ultimate ?? (available.length > 0
    ? available[Math.floor(Math.random() * available.length)]
    : null);

  let dmgDealt: number;
  let shieldRemaining = player_shield;

  if (chosen) {
    const result = applyAbilityDamage(chosen, state.player_max_hp * 0.1, player_is_defending, player_shield);
    dmgDealt = result.damage;
    shieldRemaining = result.shieldRemaining;
  } else {
    const result = calculateDamage(enemy.atk, state.player_max_hp * 0.1, player_is_defending, player_shield);
    dmgDealt = result.damage;
    shieldRemaining = result.shieldRemaining;
  }

  const newEnemyMana = chosen ? enemy.mana - chosen.mana_cost : enemy.mana;
  const newEnemyCooldowns = chosen
    ? { ...enemy.ability_cooldowns, [chosen.id]: chosen.cooldown }
    : enemy.ability_cooldowns;

  return {
    ...state,
    player_hp: Math.max(state.player_hp - dmgDealt, 0),
    player_shield: shieldRemaining,
    player_is_defending: false,
    enemy: {
      ...enemy,
      mana: newEnemyMana,
      ability_cooldowns: newEnemyCooldowns,
    },
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
    max_mana: 80 + round * 5,
  };
}
