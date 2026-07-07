/**
 * Pure derivation functions for the Battle Info Tooltips feature.
 *
 * No React, no side effects — every function here is a plain projection of
 * data already present on `Ability`, `EnemyAbility`, `Cat`, and `Enemy`
 * (frontend/src/types/game.ts). See design.md "lib/battleInfo.ts — pure
 * derivations" for the field-mapping contract these implement.
 */
import type { Ability, Cat, Effect, Enemy, EnemyAbility } from "@/types/game";

export const PLACEHOLDER_TEXT = "No information available.";
export const NO_EFFECT_TEXT = "No effect.";

/** Requirement 2.7 / 3.5: missing or empty-string fields get placeholder text. */
export function withPlaceholder(value: string | null | undefined): string {
  return value == null || value === "" ? PLACEHOLDER_TEXT : value;
}

/** Requirement 2.8: null effect is a valid, distinct "no effect" state. */
export function formatEffect(effect: Effect | null): string {
  return effect === null ? NO_EFFECT_TEXT : effect;
}

export interface AbilityInfoFields {
  description: string;
  dmg: number;
  effect: string;
  /** Present only for player abilities (Ability has lore; EnemyAbility does not). */
  lore?: string;
}

/** Requirement 2.6/2.7/2.8: player Ability_Info_Panel content. */
export function getAbilityInfoFields(ability: Ability): AbilityInfoFields {
  return {
    description: withPlaceholder(ability.description),
    dmg: ability.dmg,
    effect: formatEffect(ability.effect),
    lore: withPlaceholder(ability.lore),
  };
}

/** Requirement 4.3: enemy Ability_Info_Panel content (no lore field exists on EnemyAbility). */
export function getEnemyAbilityInfoFields(ability: EnemyAbility): AbilityInfoFields {
  return {
    description: withPlaceholder(ability.description),
    dmg: ability.dmg,
    effect: formatEffect(ability.effect),
  };
}

export interface PlayerStatFields {
  dmg: number;
  defence: number;
  spd: number;
  maxHp: number;
  maxMana: number;
  breed: string;
  lore: string;
}

/** Requirement 3.1/3.4/3.5: player Stat_Info_Panel content, sourced from CatResponse. */
export function getPlayerStatFields(cat: Cat): PlayerStatFields {
  return {
    dmg: cat.dmg,
    defence: cat.defence,
    spd: cat.spd,
    maxHp: cat.max_hp,
    maxMana: cat.max_mana,
    breed: withPlaceholder(cat.breed),
    lore: withPlaceholder(cat.lore),
  };
}

export interface EnemyStatFields {
  breed: string;
  atk: number;
  defence: number;
  spd: number;
  maxHp: number;
  maxMana: number;
}

/**
 * Requirement 5.1/5.8/5.9: enemy Stat_Info_Panel content — EXACTLY these six
 * fields; `ability_cooldowns` is never read here.
 */
export function getEnemyStatFields(enemy: Enemy): EnemyStatFields {
  return {
    breed: enemy.breed,
    atk: enemy.atk,
    defence: enemy.defence,
    spd: enemy.spd,
    maxHp: enemy.max_hp,
    maxMana: enemy.max_mana,
  };
}

export interface EnemyAbilityListEntry {
  id: string;
  name: string;
}

/**
 * Requirement 4.1/4.2: Enemy_Ability_List entries — id+name only, never a
 * cooldown value, in the same order as `Enemy.abilities`.
 */
export function toEnemyAbilityList(enemy: Enemy): EnemyAbilityListEntry[] {
  return enemy.abilities.map((a) => ({ id: a.id, name: a.name }));
}

/** Requirement 1.1/1.2: cooldown lookup treats a missing key as 0. */
export function getRemainingCooldown(
  cooldowns: Record<string, number>,
  abilityId: string,
): number {
  return cooldowns[abilityId] ?? 0;
}

/** Requirement 1.3/1.4: the single predicate gating ability-button activation. */
export function canUseAbility(
  remainingCooldown: number,
  mana: number,
  manaCost: number,
  canAct: boolean,
): boolean {
  return remainingCooldown === 0 && mana >= manaCost && canAct;
}
