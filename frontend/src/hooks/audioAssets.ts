/**
 * Static audio asset resolution via Vite `import.meta.glob`.
 */

const ambientModules = import.meta.glob("../assets/ambient/*.{wav,mp3,ogg}", {
  eager: true,
  query: "?url",
  import: "default",
});

export const AMBIENT_TRACKS: string[] = Object.keys(ambientModules)
  .sort((a, b) => a.localeCompare(b))
  .map((key) => ambientModules[key] as string);

const soundModules = import.meta.glob("../assets/sounds/*.{wav,mp3,ogg}", {
  eager: true,
  query: "?url",
  import: "default",
});

export const SOUND_EFFECTS: Record<string, string> = Object.entries(
  soundModules,
).reduce<Record<string, string>>((acc, [path, url]) => {
  const base = path.split("/").pop()?.replace(/\.[^.]+$/, "") ?? path;
  acc[base] = url as string;
  return acc;
}, {});

export type MoveSoundKind = "attack" | "defend" | "ability" | "ultimate";

/** Move kind → effect base filename. */
export const MOVE_SOUND_MAP: Record<MoveSoundKind, string> = {
  attack: "attack_sound",
  defend: "block_sound",
  ability: "ability_sound",
  ultimate: "ultimate_sound",
};
