import type { Enemy, EnemyAbility } from "../types/game";
import { AbilityType } from "../types/game";
import { computeEnemyStats } from "./combat";

const names = [
  "Shadow", "Whiskers", "Midnight", "Tiger", "Smokey",
  "Misty", "Oreo", "Simba", "Luna", "Felix",
];

const breeds = [
  "Black Shorthair", "Orange Tabby", "Calico", "Siamese",
  "Maine Coon", "Persian", "Bengal", "Ragdoll",
];

const abilityPool: Omit<EnemyAbility, "id">[] = [
  { name: "Scratch", dmg: 6, type: AbilityType.DMG, effect: null, mana_cost: 10, cooldown: 0, is_special: false, description: "A quick scratch." },
  { name: "Feral Swipe", dmg: 9, type: AbilityType.DMG, effect: null, mana_cost: 15, cooldown: 1, is_special: false, description: "A powerful swipe." },
  { name: "Tail Whip", dmg: 5, type: AbilityType.DMG, effect: null, mana_cost: 8, cooldown: 0, is_special: false, description: "Whacks with its tail." },
  { name: "Dark Claw", dmg: 12, type: AbilityType.DMG, effect: null, mana_cost: 20, cooldown: 2, is_special: false, description: "Claws glowing with dark energy." },
  { name: "Vicious Bite", dmg: 14, type: AbilityType.DMG, effect: null, mana_cost: 25, cooldown: 2, is_special: false, description: "A devastating bite." },
  { name: "Paw Slam", dmg: 7, type: AbilityType.DMG, effect: null, mana_cost: 12, cooldown: 1, is_special: false, description: "Slams the ground with its paw." },
  { name: "Healing Purr", dmg: 10, type: AbilityType.HEAL, effect: null, mana_cost: 20, cooldown: 2, is_special: false, description: "Purrs to restore HP." },
  { name: "Shadow Shield", dmg: 0, type: AbilityType.SHIELD, effect: null, mana_cost: 18, cooldown: 3, is_special: false, description: "Conjures a shadow barrier." },
  { name: "Shadow Pounce", dmg: 18, type: AbilityType.DMG, effect: null, mana_cost: 40, cooldown: 3, is_special: true, description: "Leaps from the shadows for massive damage." },
  { name: "Fury Strikes", dmg: 16, type: AbilityType.DMG, effect: null, mana_cost: 35, cooldown: 3, is_special: true, description: "A flurry of relentless strikes." },
  { name: "Regen Aura", dmg: 15, type: AbilityType.HEAL, effect: null, mana_cost: 35, cooldown: 3, is_special: true, description: "Bathes in restorative energy." },
  { name: "Tortoise Shell", dmg: 0, type: AbilityType.SHIELD, effect: null, mana_cost: 30, cooldown: 3, is_special: true, description: "Hardens fur into an impenetrable shell." },
];

let abilityCounter = 0;

function pickAbilities(): EnemyAbility[] {
  const shuffled = [...abilityPool].sort(() => Math.random() - 0.5);
  const special = shuffled.find((a) => a.is_special) ?? shuffled[0];
  const normals = shuffled
    .filter((a) => !a.is_special && a.name !== special.name)
    .slice(0, 3);

  return [...normals, special].map((a) => ({
    ...a,
    id: `enemy-ability-${++abilityCounter}`,
  }));
}

export function generateEnemy(round: number): Enemy {
  const stats = computeEnemyStats(round);
  const name = names[Math.floor(Math.random() * names.length)];
  const breed = breeds[Math.floor(Math.random() * breeds.length)];
  const abilities = pickAbilities();

  const cooldowns: Record<string, number> = {};
  for (const a of abilities) {
    cooldowns[a.id] = 0;
  }

  return {
    name,
    breed,
    hp: stats.hp,
    max_hp: stats.hp,
    atk: stats.atk,
    def: stats.def,
    spd: stats.spd,
    mana: Math.floor(stats.max_mana * 0.6),
    max_mana: stats.max_mana,
    ability_cooldowns: cooldowns,
    abilities,
    avatar_url: "",
  };
}
