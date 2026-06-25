import type { Enemy } from "../types/game";
import { computeEnemyStats } from "./combat";

const names = [
  "Shadow", "Whiskers", "Midnight", "Tiger", "Smokey",
  "Misty", "Oreo", "Simba", "Luna", "Felix",
];

const breeds = [
  "Black Shorthair", "Orange Tabby", "Calico", "Siamese",
  "Maine Coon", "Persian", "Bengal", "Ragdoll",
];

const abilities = [
  "Shadow Pounce", "Feral Swipe", "Scratch", "Tail Whip",
  "Dark Claw", "Fury Strikes", "Vicious Bite", "Paw Slam",
];

export function generateEnemy(round: number): Enemy {
  const stats = computeEnemyStats(round);
  const name = names[Math.floor(Math.random() * names.length)];
  const breed = breeds[Math.floor(Math.random() * breeds.length)];
  const ability = abilities[Math.floor(Math.random() * abilities.length)];

  return {
    name,
    breed,
    hp: stats.hp,
    max_hp: stats.hp,
    atk: stats.atk,
    def: stats.def,
    spd: stats.spd,
    ability,
    avatar_url: "",
  };
}
